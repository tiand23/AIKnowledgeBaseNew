"""
Redis 客户端（连接池模式）
"""
import redis.asyncio as aioredis
from redis.asyncio.connection import ConnectionPool
from typing import Optional
from app.core.config import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)


class RedisClient:
    
    def __init__(self):
        self.redis: Optional[aioredis.Redis] = None
        self.pool: Optional[ConnectionPool] = None
    
    async def connect(self):
        self.pool = ConnectionPool(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            db=settings.REDIS_DB,
            password=settings.REDIS_PASSWORD if settings.REDIS_PASSWORD else None,
            encoding="utf-8",
            decode_responses=True,
            max_connections=10,
            socket_connect_timeout=5,
            socket_keepalive=True,
            health_check_interval=30,
        )
        
        self.redis = aioredis.Redis(connection_pool=self.pool)
    
    async def close(self):
        if self.redis:
            await self.redis.close()
        if self.pool:
            await self.pool.disconnect()
    
    async def set(self, key: str, value: str, expire: int = None) -> bool:
        try:
            if expire:
                await self.redis.setex(key, expire, value)
            else:
                await self.redis.set(key, value)
            return True
        except Exception as e:
            logger.error(f"Redis set error: {e}")
            return False
    
    async def get(self, key: str) -> Optional[str]:
        try:
            return await self.redis.get(key)
        except Exception as e:
            logger.error(f"Redis get error: {e}")
            return None
    
    async def delete(self, key: str) -> bool:
        try:
            await self.redis.delete(key)
            return True
        except Exception as e:
            logger.error(f"Redis delete error: {e}")
            return False
    
    async def exists(self, key: str) -> bool:
        try:
            return await self.redis.exists(key) > 0
        except Exception as e:
            logger.error(f"Redis exists error: {e}")
            return False
    
    async def incr(self, key: str, expire: int = None) -> int:
        try:
            count = await self.redis.incr(key)
            if expire and count == 1:
                await self.redis.expire(key, expire)
            return count
        except Exception as e:
            logger.error(f"Redis incr error: {e}")
            return 0
    
    async def ttl(self, key: str) -> int:
        try:
            return await self.redis.ttl(key)
        except Exception as e:
            logger.error(f"Redis ttl error: {e}")
            return -1

    async def set_bit(self, key: str, offset: int, value: int) -> int:
        """
        设置位图中某一位的值（0/1）。
        等价于 Redis: SETBIT key offset value
        返回旧值（0/1）。
        """
        try:
            return int(await self.redis.setbit(key, offset, value))
        except Exception as e:
            logger.error(f"Redis setbit error: {e}")
            return 0

    async def get_bit(self, key: str, offset: int) -> int:
        """
        获取位图中某一位的值（0/1）。等价于 Redis: GETBIT key offset
        """
        try:
            return int(await self.redis.getbit(key, offset))
        except Exception as e:
            logger.error(f"Redis getbit error: {e}")
            return 0

    async def bitcount(self, key: str) -> int:
        """
        统计位图中值为 1 的位个数。等价于 Redis: BITCOUNT key
        """
        try:
            return int(await self.redis.bitcount(key))
        except Exception as e:
            logger.error(f"Redis bitcount error: {e}")
            return 0

    async def get_bitmap_progress(self, key: str, total_bits: int) -> float:
        """
        计算位图进度（已上传分片数 / 总分片数）。
        返回值范围 0.0~1.0；当 total_bits<=0 或 key 不存在时返回 0.0。
        """
        try:
            if total_bits <= 0:
                return 0.0
            if not await self.exists(key):
                return 0.0
            done = await self.bitcount(key)
            return min(1.0, max(0.0, done / float(total_bits)))
        except Exception as e:
            logger.error(f"Redis bitmap progress error: {e}")
            return 0.0

    async def clear_bitmap(self, key: str) -> bool:
        """
        清理位图键（上传完成或取消时调用）。
        """
        return await self.delete(key)
    
    async def health_check(self) -> bool:
        try:
            await self.redis.ping()
            return True
        except Exception as e:
            logger.error(f"Redis 健康检查失败: {e}")
            return False
    
    def get_pool_status(self) -> dict:
        if not self.pool:
            return {"error": "Redis 连接池未初始化"}
        
        pool = self.pool
        
        return {
            "最大连接数": pool.max_connections,
            "当前活跃连接数": len(pool._in_use_connections) if hasattr(pool, '_in_use_connections') else "N/A",
            "可用连接数": len(pool._available_connections) if hasattr(pool, '_available_connections') else "N/A",
            "连接池状态": "healthy" if self.pool else "not initialized",
            "配置": {
                "host": pool.connection_kwargs.get('host'),
                "port": pool.connection_kwargs.get('port'),
                "db": pool.connection_kwargs.get('db'),
                "max_connections": pool.max_connections,
            }
        }


redis_client = RedisClient()

