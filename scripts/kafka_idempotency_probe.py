"""
Kafka 幂等/并发探针

用途：
1. 对同一 file_md5 并发发送重复 document_parse 消息
2. 观察处理后 document_vectors 数量是否异常增长

示例：
PYTHONPATH=. python3 scripts/kafka_idempotency_probe.py \
  --file-md5 db0d61fb55889cf546b16b7ea060a941 \
  --user-id 123 \
  --count 20 \
  --concurrency 10
"""
import argparse
import asyncio
import json
from typing import Optional

from sqlalchemy import select, func

from app.clients.db_client import db_client
from app.clients.kafka_client import kafka_client
from app.models.file import FileUpload, DocumentVector


async def _fetch_file_record(file_md5: str, user_id: int) -> Optional[FileUpload]:
    async with db_client.SessionLocal() as db:
        result = await db.execute(
            select(FileUpload).where(
                FileUpload.file_md5 == file_md5,
                FileUpload.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()


async def _fetch_vector_count(file_md5: str) -> int:
    async with db_client.SessionLocal() as db:
        result = await db.execute(
            select(func.count(DocumentVector.vector_id)).where(DocumentVector.file_md5 == file_md5)
        )
        return int(result.scalar_one() or 0)


async def _send_burst(message: dict, file_md5: str, count: int, concurrency: int) -> int:
    sem = asyncio.Semaphore(max(1, concurrency))
    success = 0

    async def _one(_: int) -> int:
        async with sem:
            ok = await kafka_client.send_message(topic="document_parse", value=message, key=file_md5)
            return 1 if ok else 0

    results = await asyncio.gather(*[_one(i) for i in range(count)])
    success = sum(results)
    return success


async def main() -> int:
    parser = argparse.ArgumentParser(description="Kafka 幂等探针")
    parser.add_argument("--file-md5", required=True, help="目标文件 MD5")
    parser.add_argument("--user-id", required=True, type=int, help="目标用户 ID")
    parser.add_argument("--count", default=20, type=int, help="发送消息总数")
    parser.add_argument("--concurrency", default=10, type=int, help="发送并发数")
    parser.add_argument("--wait-seconds", default=8, type=int, help="发送后等待处理秒数")
    parser.add_argument(
        "--storage-path",
        default="probe/placeholder",
        help="消息里的 storage_path（done 文件去重场景可使用默认值）",
    )
    args = parser.parse_args()

    db_client.connect()
    await kafka_client.connect()

    try:
        file_record = await _fetch_file_record(args.file_md5, args.user_id)
        if not file_record:
            print(f"[ERROR] file 不存在: file_md5={args.file_md5}, user_id={args.user_id}")
            return 2

        before_count = await _fetch_vector_count(args.file_md5)
        print(f"[INFO] 目标文件: {file_record.file_name}")
        print(f"[INFO] 初始状态: status={file_record.status}, org_tag={file_record.org_tag}, is_public={file_record.is_public}")
        print(f"[INFO] 初始向量数: {before_count}")

        payload = {
            "file_md5": args.file_md5,
            "file_name": file_record.file_name,
            "storage_path": args.storage_path,
            "user_id": args.user_id,
            "org_tag": file_record.org_tag,
            "is_public": bool(file_record.is_public),
            "kb_profile": file_record.kb_profile,
            "probe": {"type": "idempotency_probe"},
        }
        print(f"[INFO] probe payload: {json.dumps(payload, ensure_ascii=False)}")
        sent_ok = await _send_burst(
            message=payload,
            file_md5=args.file_md5,
            count=max(1, args.count),
            concurrency=max(1, args.concurrency),
        )
        await kafka_client.flush()
        print(f"[INFO] 已发送: success={sent_ok}/{args.count}")

        await asyncio.sleep(max(1, args.wait_seconds))

        after_count = await _fetch_vector_count(args.file_md5)
        latest_record = await _fetch_file_record(args.file_md5, args.user_id)
        print(f"[INFO] 处理后状态: status={latest_record.status if latest_record else 'N/A'}")
        print(f"[INFO] 处理后向量数: {after_count}")
        print(f"[INFO] 向量增量: {after_count - before_count}")

        if after_count - before_count > 0 and file_record.status == 3:
            print("[WARN] 已完成文件出现向量增量，需检查幂等逻辑。")
            return 1

        print("[OK] 探针执行完成。")
        return 0
    finally:
        await kafka_client.close()
        await db_client.close()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
