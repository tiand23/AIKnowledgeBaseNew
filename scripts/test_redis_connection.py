"""
测试 Redis 连接
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.clients.redis_client import redis_client
from app.core.config import settings


async def test_redis():
    print("=" * 50)
    print("测试： Redis 连接")
    print("=" * 50)
    print(f"\n测试：Redis 主机：{settings.REDIS_HOST}")
    print(f"测试：Redis 端口：{settings.REDIS_PORT}")
    print(f"测试：Redis 数据库：{settings.REDIS_DB}\n")

    try:
        print("测试：正在连接 Redis...")
        await redis_client.connect()

        test_key = "test:connection"
        test_value = "Hello Redis!"

        print(f"\n测试：写入测试数据: {test_key} = {test_value}")
        await redis_client.set(test_key, test_value, expire=60)

        result = await redis_client.get(test_key)
        print(f"测试：读取测试数据: {result}")

        if result == test_value:
            print("\n" + "=" * 50)
            print("测试：Redis 连接成功！")
            print("=" * 50)
            print("测试：读写测试通过")
        else:
            print("\n测试：数据不匹配")
            return False

        ttl = await redis_client.ttl(test_key)
        print(f"测试：TTL (剩余时间): {ttl} 秒")

        await redis_client.delete(test_key)
        print("测试：测试数据已清理")

        await redis_client.close()
        print("\n测试：连接已正常关闭")
        return True

    except Exception as e:
        print("\n" + "=" * 50)
        print("测试：Redis 连接失败！")
        print("=" * 50)
        print(f"测试：错误类型: {type(e).__name__}")
        print(f"测试：错误信息: {str(e)}")
        return False


if __name__ == "__main__":
    print("\n测试：启动 Redis 连接测试...\n")
    success = asyncio.run(test_redis())

    if success:
        print("\n测试：所有测试通过！")
        sys.exit(0)
    else:
        print("\n测试：提示排查问题后重试")
        sys.exit(1)
