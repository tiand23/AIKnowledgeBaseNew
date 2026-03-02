"""
数据库客户端（SQLite/MySQL/PostgreSQL）
"""
import asyncio
from pathlib import Path
from sqlalchemy import text, event
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from typing import AsyncGenerator
from app.core.config import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)


class DatabaseClient:
    
    def __init__(self):
        self.engine = None
        self.SessionLocal = None
    
    def connect(self):
        database_url = settings.DATABASE_URL
        dialect = settings.DB_DIALECT.lower().strip()

        if dialect == "sqlite" and settings.SQLITE_PATH != ":memory:":
            sqlite_path = Path(settings.SQLITE_PATH)
            if not sqlite_path.is_absolute():
                sqlite_path = Path.cwd() / sqlite_path
            sqlite_path.parent.mkdir(parents=True, exist_ok=True)

        engine_kwargs = {
            "echo": settings.DEBUG,
        }

        if dialect == "sqlite":
            engine_kwargs["connect_args"] = {
                "check_same_thread": False,
                "timeout": 30,
            }
        else:
            engine_kwargs.update(
                {
                    "pool_size": 5,
                    "max_overflow": 10,
                    "pool_pre_ping": True,
                    "pool_recycle": 3600,
                }
            )

        self.engine = create_async_engine(database_url, **engine_kwargs)

        if dialect == "sqlite":
            @event.listens_for(self.engine.sync_engine, "connect")
            def _set_sqlite_pragmas(dbapi_connection, _connection_record):
                cursor = dbapi_connection.cursor()
                try:
                    cursor.execute("PRAGMA journal_mode=WAL")
                    cursor.execute("PRAGMA synchronous=NORMAL")
                    cursor.execute("PRAGMA busy_timeout=30000")
                finally:
                    cursor.close()

        self.SessionLocal = async_sessionmaker(
            self.engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autocommit=False,
            autoflush=False,
        )

    async def close(self):
        if self.engine:
            try:
                await self.engine.dispose(close=True)
            except (asyncio.CancelledError, RuntimeError) as e:
                pass
            except AttributeError:
                pass
            except Exception:
                pass
            finally:
                self.engine = None
                self.SessionLocal = None
    
    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        if not self.SessionLocal:
            raise RuntimeError("数据库未连接，请先调用 connect()")
        
        async with self.SessionLocal() as session:
            try:
                yield session
            finally:
                await session.close()
    
    async def health_check(self) -> bool:
        try:
            async with self.SessionLocal() as session:
                result = await session.execute(text("SELECT 1"))
                result.scalar()
                return True
        except Exception as e:
            logger.error(f"数据库健康检查失败: {e}")
            return False
    
    def get_pool_status(self) -> dict:
        if not self.engine:
            return {"error": "数据库引擎未初始化"}
        
        pool = self.engine.pool
        if not all(hasattr(pool, method) for method in ("size", "checkedin", "checkedout", "overflow")):
            return {
                "数据库连接池类型": type(pool).__name__,
                "数据库连接池状态": "not_applicable"
            }

        return {
            "数据库连接池大小": pool.size(),
            "数据库连接池可用连接数": pool.checkedin(),
            "数据库连接池正在使用的连接数": pool.checkedout(),
            "数据库连接池溢出连接数": pool.overflow(),
            "数据库连接池总连接数": pool.size() + pool.overflow(),
            "数据库连接池状态": "healthy" if pool.checkedin() > 0 else "busy"
        }


db_client = DatabaseClient()
