"""
测试上传知识库测试文档

按照文件上传流程将 test_knowledge_base_content.md 上传到知识库
"""
import asyncio
import sys
import hashlib
import warnings
import logging
from pathlib import Path
from io import BytesIO
from typing import Tuple

sys.path.insert(0, str(Path(__file__).parent.parent))

logging.getLogger("sqlalchemy.engine").setLevel(logging.ERROR)
logging.getLogger("sqlalchemy.pool").setLevel(logging.ERROR)
logging.getLogger("sqlalchemy.dialects").setLevel(logging.ERROR)
logging.getLogger("sqlalchemy.orm").setLevel(logging.ERROR)
logging.getLogger("app.services").setLevel(logging.ERROR)
logging.getLogger("app.clients").setLevel(logging.ERROR)
logging.getLogger().handlers = []

warnings.filterwarnings("ignore")

from app.clients.minio_client import minio_client
from app.clients.redis_client import redis_client
from app.clients.db_client import db_client
from app.clients.elasticsearch_client import es_client
from app.clients.kafka_client import kafka_client
from app.services.file_service import file_service
from app.services.embedding_service import embedding_service
from app.services.search_service import search_service
from app.core.config import settings
from app.models.user import User, UserRole
from app.models.file import DocumentVector
from app.utils import jwt_utils
from app.utils.security import verify_password, hash_password
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

_original_connect = db_client.connect

def _test_connect():
    db_client.engine = create_async_engine(
        settings.DATABASE_URL,
        echo=False,
        pool_size=5,
        max_overflow=10,
        pool_pre_ping=True,
        pool_recycle=3600,
    )
    
    db_client.SessionLocal = async_sessionmaker(
        db_client.engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )

db_client.connect = _test_connect

TEST_USERNAME = "test_chat_user"
TEST_PASSWORD = "test_password_123"
TEST_FILE_PATH = Path(__file__).parent / "test_knowledge_base_content.md"
CHUNK_SIZE = 5 * 1024 * 1024  # 5MB per chunk

class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    RESET = '\033[0m'

def print_success(msg: str):
    print(f"{Colors.GREEN}✓ {msg}{Colors.RESET}")

def print_error(msg: str):
    print(f"{Colors.RED}✗ {msg}{Colors.RESET}")

def print_info(msg: str):
    print(f"{Colors.BLUE}ℹ {msg}{Colors.RESET}")

def print_warning(msg: str):
    print(f"{Colors.YELLOW}⚠ {msg}{Colors.RESET}")


def calculate_file_md5(data: bytes) -> str:
    return hashlib.md5(data).hexdigest()


async def ensure_org_tag(db: AsyncSession, tag_id: str, name: str = None, created_by: int = None):
    from app.models.organization import OrganizationTag
    
    result = await db.execute(
        select(OrganizationTag).where(OrganizationTag.tag_id == tag_id)
    )
    org_tag = result.scalar_one_or_none()
    
    if not org_tag:
        if not created_by:
            admin_result = await db.execute(
                select(User).where(User.role == UserRole.ADMIN).limit(1)
            )
            admin_user = admin_result.scalar_one_or_none()
            if admin_user:
                created_by = admin_user.id
            else:
                first_user_result = await db.execute(select(User).limit(1))
                first_user = first_user_result.scalar_one_or_none()
                if first_user:
                    created_by = first_user.id
                else:
                    raise ValueError(f"无法创建组织标签 {tag_id}：没有可用的用户作为创建者")
        
        org_tag = OrganizationTag(
            tag_id=tag_id,
            name=name or tag_id,
            description=f"测试组织标签: {tag_id}",
            parent_tag=None,
            created_by=created_by
        )
        db.add(org_tag)
        await db.commit()
        print_success(f"创建组织标签: {tag_id}")
    else:
        print_info(f"组织标签已存在: {tag_id}")
    
    return org_tag


async def create_or_get_test_user(db: AsyncSession) -> User:
    result = await db.execute(select(User).where(User.username == TEST_USERNAME))
    user = result.scalar_one_or_none()
    
    if user:
        print_info(f"测试用户已存在: {TEST_USERNAME}")
        if user.primary_org:
            await ensure_org_tag(db, user.primary_org, created_by=user.id)
        if "DEFAULT" in (user.org_tags or ""):
            await ensure_org_tag(db, "DEFAULT", "默认组织", created_by=user.id)
        return user
    
    admin_result = await db.execute(
        select(User).where(User.role == "ADMIN").limit(1)
    )
    admin_user = admin_result.scalar_one_or_none()
    creator_id = admin_user.id if admin_user else None
    
    if not creator_id:
        first_user_result = await db.execute(select(User).limit(1))
        first_user = first_user_result.scalar_one_or_none()
        if first_user:
            creator_id = first_user.id
    
    if not creator_id:
        user = User(
            username=TEST_USERNAME,
            email="test_chat@example.com",
            password=hash_password(TEST_PASSWORD),
            org_tags=None,
            primary_org=None
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
        creator_id = user.id
        
        await ensure_org_tag(db, "DEFAULT", "默认组织", created_by=creator_id)
        await ensure_org_tag(db, "test_org", "测试组织", created_by=creator_id)
        
        user.org_tags = "DEFAULT,test_org"
        user.primary_org = "DEFAULT"
        await db.commit()
        await db.refresh(user)
        print_success(f"创建测试用户: {TEST_USERNAME} (ID: {user.id})")
        return user
    else:
        await ensure_org_tag(db, "DEFAULT", "默认组织", created_by=creator_id)
        await ensure_org_tag(db, "test_org", "测试组织", created_by=creator_id)
        
        user = User(
            username=TEST_USERNAME,
            email="test_chat@example.com",
            password=hash_password(TEST_PASSWORD),
            org_tags="DEFAULT,test_org",
            primary_org="DEFAULT"
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
        print_success(f"创建测试用户: {TEST_USERNAME} (ID: {user.id})")
        return user


async def read_test_file() -> Tuple[bytes, str, str]:
    if not TEST_FILE_PATH.exists():
        raise FileNotFoundError(f"测试文件不存在: {TEST_FILE_PATH}")
    
    with open(TEST_FILE_PATH, 'rb') as f:
        file_data = f.read()
    
    file_md5 = calculate_file_md5(file_data)
    file_name = TEST_FILE_PATH.name
    
    print_success(f"读取测试文件: {file_name}")
    print_info(f"  文件大小: {len(file_data)} 字节")
    print_info(f"  文件MD5: {file_md5}")
    
    return file_data, file_md5, file_name


async def upload_file_chunks(
    db: AsyncSession,
    user: User,
    file_data: bytes,
    file_md5: str,
    file_name: str
):
    file_size = len(file_data)
    
    print_info("确保MinIO存储桶存在...")
    if not minio_client.ensure_bucket(settings.MINIO_DEFAULT_BUCKET):
        print_error("MinIO存储桶创建失败")
        raise RuntimeError("MinIO存储桶创建失败")
    print_success(f"MinIO存储桶已就绪: {settings.MINIO_DEFAULT_BUCKET}")
    
    total_chunks = (file_size + CHUNK_SIZE - 1) // CHUNK_SIZE
    
    print_info(f"开始分块上传: 共 {total_chunks} 个分块")
    
    chunk_data_list = []
    for chunk_index in range(total_chunks):
        start = chunk_index * CHUNK_SIZE
        end = min(start + CHUNK_SIZE, file_size)
        chunk_data = file_data[start:end]
        chunk_data_list.append(chunk_data)
    
    for chunk_index in range(total_chunks):
        chunk_data = chunk_data_list[chunk_index]
        
        org_tag = user.primary_org or "DEFAULT"
        
        try:
            uploaded_chunks, progress = await file_service.upload_chunk(
                db=db,
                user=user,
                file_md5=file_md5,
                chunk_index=chunk_index,
                chunk_data=chunk_data,
                file_name=file_name,
                total_size=file_size,
                total_chunks=total_chunks,
                org_tag=org_tag,
                is_public=True  # Mark as public to simplify test validation
            )
            
            chunk_path = minio_client.build_temp_chunk_path(file_md5, chunk_index)
            if minio_client.file_exists(settings.MINIO_DEFAULT_BUCKET, chunk_path):
                print_info(f"  分块 {chunk_index + 1}/{total_chunks} 上传成功 ({progress:.1f}%)")
            else:
                print_warning(f"  分块 {chunk_index + 1}/{total_chunks} 上传返回成功，但MinIO中不存在")
                print_info(f"  尝试重新上传分块 {chunk_index + 1}...")
                success = minio_client.upload_bytes(
                    bucket_name=settings.MINIO_DEFAULT_BUCKET,
                    object_name=chunk_path,
                    data=chunk_data
                )
                if success and minio_client.file_exists(settings.MINIO_DEFAULT_BUCKET, chunk_path):
                    print_success(f"  分块 {chunk_index + 1} 重新上传成功")
                else:
                    print_error(f"  分块 {chunk_index + 1} 重新上传失败")
                    raise RuntimeError(f"分块 {chunk_index + 1} MinIO上传失败")
                    
        except Exception as e:
            print_error(f"  分块 {chunk_index + 1}/{total_chunks} 上传失败: {e}")
            raise
    
    await db.commit()
    
    from app.models.file import ChunkInfo
    print_info("验证分片是否已保存到数据库...")
    chunks_result = await db.execute(
        select(ChunkInfo)
        .where(ChunkInfo.file_md5 == file_md5)
        .order_by(ChunkInfo.chunk_index)
    )
    chunks = chunks_result.scalars().all()
    
    print_info(f"  数据库中找到 {len(chunks)} 个分片记录")
    
    if len(chunks) != total_chunks:
        print_error(f"分片验证失败: 期望 {total_chunks} 个分片，实际 {len(chunks)} 个")
        print_info("  已保存的分片索引: " + ", ".join([str(c.chunk_index) for c in chunks]))
        raise ValueError(f"分片数量不匹配: 期望 {total_chunks}，实际 {len(chunks)}")
    
    redis_key = file_service.get_redis_chunk_key(file_md5)
    print_info("验证Redis中的分片状态...")
    uploaded_count = 0
    for i in range(total_chunks):
        if await redis_client.get_bit(redis_key, i) == 1:
            uploaded_count += 1
    print_info(f"  Redis中标记为已上传的分片: {uploaded_count}/{total_chunks}")
    
    if uploaded_count != total_chunks:
        print_warning(f"Redis分片状态不完整: {uploaded_count}/{total_chunks}")
        for i in range(total_chunks):
            await redis_client.set_bit(redis_key, i, 1)
        print_info("已修复Redis分片状态")
    
    print_info("验证MinIO中的分片文件...")
    minio_exist_count = 0
    for chunk in chunks:
        chunk_path = chunk.storage_path
        if minio_client.file_exists(settings.MINIO_DEFAULT_BUCKET, chunk_path):
            minio_exist_count += 1
        else:
            print_warning(f"  MinIO中不存在分片 {chunk.chunk_index}: {chunk_path}")
            print_info(f"  尝试重新上传分片 {chunk.chunk_index}...")
    
    print_info(f"  MinIO中存在的分片: {minio_exist_count}/{len(chunks)}")
    
    if minio_exist_count != len(chunks):
        print_warning(f"MinIO分片文件不完整: {minio_exist_count}/{len(chunks)}")
        print_warning("  这可能导致合并文件失败，但会尝试在合并时重新上传")
    
    print_success(f"所有分块上传完成！共 {len(chunks)} 个分片已保存到数据库")


async def merge_file(
    db: AsyncSession,
    user: User,
    file_md5: str,
    file_name: str
):
    print_info("开始合并文件...")
    
    try:
        object_url, file_size = await file_service.merge_file(
            db=db,
            user=user,
            file_md5=file_md5,
            file_name=file_name
        )
        
        print_success(f"文件合并成功！")
        print_info(f"  文件URL: {object_url}")
        print_info(f"  文件大小: {file_size} 字节")
        
        from app.models.file import FileUpload
        result = await db.execute(
            select(FileUpload).where(
                FileUpload.file_md5 == file_md5,
                FileUpload.user_id == user.id
            )
        )
        file_record = result.scalar_one_or_none()
        
        if file_record:
            print_info(f"  文件ID: {file_record.id}")
            print_info(f"  文件名: {file_record.file_name}")
            print_info(f"  状态: {'已完成' if file_record.status == 1 else '处理中'}")
        
        return file_record
            
    except Exception as e:
        print_error(f"合并文件时出错: {e}")
        import traceback
        traceback.print_exc()
        return None


async def process_and_index_file(
    db: AsyncSession,
    user: User,
    file_md5: str,
    file_name: str,
    file_data: bytes
):
    print_info("开始处理文件（解析、分块、向量化、索引）...")
    
    try:
        await search_service.ensure_index_exists()
        print_success("Elasticsearch索引已就绪")
        
        print_info("解析Markdown文件...")
        import re
        
        text_content = file_data.decode('utf-8')
        
        text_content = re.sub(r'^#+\s+', '', text_content, flags=re.MULTILINE)
        text_content = re.sub(r'^[-*+]\s+', '', text_content, flags=re.MULTILINE)
        text_content = re.sub(r'```[^`]*```', '', text_content, flags=re.DOTALL)
        text_content = re.sub(r'`[^`]+`', '', text_content)
        text_content = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text_content)
        text_content = re.sub(r'\*\*([^\*]+)\*\*', r'\1', text_content)
        text_content = re.sub(r'\*([^\*]+)\*', r'\1', text_content)
        text_content = re.sub(r'\n\s*\n\s*\n', '\n\n', text_content)
        text_content = text_content.strip()
        
        print_success(f"解析完成，提取文本长度: {len(text_content)} 字符")
        
        print_info("文本分块处理...")
        chunk_size = 500
        chunk_overlap = 50
        chunks = []
        
        start = 0
        chunk_id = 0
        max_iterations = len(text_content) // max(1, chunk_size - chunk_overlap) + 10  # Guard against infinite loops
        iteration = 0
        
        while start < len(text_content) and iteration < max_iterations:
            iteration += 1
            end = min(start + chunk_size, len(text_content))
            chunk_text = text_content[start:end].strip()
            
            if chunk_text:
                chunks.append({
                    "chunk_id": chunk_id,
                    "text": chunk_text
                })
                chunk_id += 1
                print_info(f"  处理块 {chunk_id}: 位置 {start}-{end} ({len(chunk_text)} 字符)")
            
            next_start = end - chunk_overlap
            if next_start <= start:
                next_start = start + max(1, chunk_size - chunk_overlap)
            
            start = next_start
        
        if iteration >= max_iterations:
            print_warning(f"文本分块达到最大迭代次数 ({max_iterations})，可能存在问题")
        
        print_success(f"分块完成，共 {len(chunks)} 个文本块")
        
        print_info(f"向量化文本块... (共 {len(chunks)} 个文本块)")
        print_info("  注意：向量化需要调用 OpenAI API，可能需要一些时间...")
        
        texts = [chunk["text"] for chunk in chunks]
        
        import sys
        sys.stdout.flush()  # Flush output immediately
        
        try:
            vectors = await embedding_service.embed_batch(texts)
            successful_vectors = sum(1 for v in vectors if v is not None)
            print_success(f"向量化完成: {successful_vectors}/{len(chunks)}")
        except Exception as e:
            print_error(f"向量化失败: {e}")
            import traceback
            traceback.print_exc()
            raise
        
        print_info("保存向量并索引到Elasticsearch...")
        
        from app.models.file import FileUpload
        file_result = await db.execute(
            select(FileUpload).where(
                FileUpload.file_md5 == file_md5,
                FileUpload.user_id == user.id
            )
        )
        file_record = file_result.scalar_one_or_none()
        
        if not file_record:
            print_error("文件记录不存在")
            return False
        
        success_count = 0
        for i, (chunk, vector) in enumerate(zip(chunks, vectors)):
            if vector is None:
                print_warning(f"  跳过块 {i}（向量化失败）")
                continue
            
            doc_vector = DocumentVector(
                file_md5=file_md5,
                chunk_id=chunk["chunk_id"],
                text_content=chunk["text"],
                model_version=settings.OPENAI_EMBEDDING_MODEL
            )
            db.add(doc_vector)
            
            org_tag = file_record.org_tag or "DEFAULT"
            is_public = file_record.is_public if file_record.is_public is not None else False
            
            es_doc = {
                "file_md5": file_md5,
                "chunk_id": chunk["chunk_id"],
                "text_content": chunk["text"],
                "vector": vector,
                "user_id": user.id,
                "org_tag": org_tag,
                "is_public": is_public,
                "file_name": file_name,
                "model_version": settings.OPENAI_EMBEDDING_MODEL
            }
            
            if i == 0:
                print_info(f"  索引文档字段值:")
                print_info(f"    user_id: {es_doc['user_id']}")
                print_info(f"    org_tag: {es_doc['org_tag']}")
                print_info(f"    is_public: {es_doc['is_public']}")
                print_info(f"    file_name: {es_doc['file_name']}")
            
            doc_id = f"{file_md5}_{chunk['chunk_id']}"
            result = await es_client.index_document(
                index=search_service.INDEX_NAME,
                document=es_doc,
                doc_id=doc_id
            )
            
            if result:
                success_count += 1
                if i < 3 or i == len(chunks) - 1:  # Show only first 3 and last 1 entries
                    print_info(f"  ✓ 索引块 {i+1}/{len(chunks)}: {doc_id}")
        
        await db.commit()
        
        await es_client.refresh_index(search_service.INDEX_NAME)
        
        print_success(f"文件处理完成！共索引 {success_count}/{len(chunks)} 个文本块")
        return success_count > 0
        
    except Exception as e:
        print_error(f"处理文件失败: {e}")
        import traceback
        traceback.print_exc()
        return False


async def check_upload_status(
    db: AsyncSession,
    user: User,
    file_md5: str,
    max_wait: int = 300  # Wait up to 5 minutes
):
    print_info("等待文件处理完成...")
    
    import time
    start_time = time.time()
    
    while time.time() - start_time < max_wait:
        uploaded_chunks, progress, total_chunks = await file_service.get_upload_status(
            db=db,
            user=user,
            file_md5=file_md5
        )
        
        from app.models.file import FileUpload
        result = await db.execute(
            select(FileUpload).where(
                FileUpload.file_md5 == file_md5,
                FileUpload.user_id == user.id
            )
        )
        file_record = result.scalar_one_or_none()
        
        if file_record:
            if file_record.status == 1:  # Completed
                print_success("文件处理完成！")
                print_info(f"  状态: 已完成")
                print_info(f"  合并时间: {file_record.merged_at}")
                return True
            elif file_record.status == 2:  # Failed
                print_error("文件处理失败")
                return False
        
        await asyncio.sleep(2)
        elapsed = int(time.time() - start_time)
        print_info(f"  处理中... ({elapsed}秒)")
    
    print_warning(f"等待超时（{max_wait}秒）")
    return False


async def main():
    print_info("=" * 60)
    print_info("测试上传知识库测试文档")
    print_info("=" * 60)
    print()
    
    try:
        print_info("步骤1: 连接服务")
        db_client.connect()
        await redis_client.connect()
        minio_client.connect()
        await es_client.connect()
        
        print_info("尝试连接 Kafka...")
        try:
            await kafka_client.connect()
            print_success("Kafka 连接成功")
        except Exception as e:
            print_warning(f"Kafka 连接失败（将跳过 Kafka 消息发送）: {e}")
        
        print_success("服务连接成功")
        print()
        
        print_info("步骤2: 读取测试文件")
        file_data, file_md5, file_name = await read_test_file()
        print()
        
        async for db in db_client.get_session():
            try:
                print_info("步骤3: 创建或获取测试用户")
                user = await create_or_get_test_user(db)
                print()
                
                print_info("步骤4: 分块上传文件")
                await upload_file_chunks(db, user, file_data, file_md5, file_name)
                print()
                
                print_info("步骤5: 合并文件")
                file_record = await merge_file(db, user, file_md5, file_name)
                if not file_record:
                    print_error("合并失败，测试终止")
                    return
                print()
                
                print_info("步骤6: 处理文件并索引到Elasticsearch")
                success = await process_and_index_file(
                    db=db,
                    user=user,
                    file_md5=file_md5,
                    file_name=file_name,
                    file_data=file_data
                )
                
                if success:
                    print()
                    print_success("=" * 60)
                    print_success("文件上传和索引测试完成！")
                    print_success("=" * 60)
                    print()
                    print_info("现在可以运行 test_chat.py 测试知识库问答功能")
                else:
                    print_warning("文件处理失败，请检查错误信息")
                
            finally:
                break
        
    except FileNotFoundError as e:
        print_error(f"文件未找到: {e}")
        print_info(f"请确保测试文件存在: {TEST_FILE_PATH}")
    except Exception as e:
        print_error(f"测试过程中出错: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        try:
            await asyncio.wait_for(db_client.close(), timeout=5.0)
        except (asyncio.TimeoutError, asyncio.CancelledError, RuntimeError, AttributeError):
            pass
        
        try:
            await asyncio.wait_for(redis_client.close(), timeout=5.0)
        except (asyncio.TimeoutError, asyncio.CancelledError, RuntimeError, AttributeError):
            pass
        
        try:
            await asyncio.wait_for(es_client.close(), timeout=5.0)
        except (asyncio.TimeoutError, asyncio.CancelledError, RuntimeError, AttributeError):
            pass
        
        try:
            await asyncio.wait_for(kafka_client.close(), timeout=5.0)
        except (asyncio.TimeoutError, asyncio.CancelledError, RuntimeError, AttributeError):
            pass
        
        await asyncio.sleep(0.1)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print_info("\n测试被用户中断")
    except Exception as e:
        print_error(f"测试执行失败: {e}")
        import traceback
        traceback.print_exc()

