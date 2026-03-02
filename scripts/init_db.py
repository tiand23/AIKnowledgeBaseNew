"""
初始化数据库表（通用：SQLite/MySQL/PostgreSQL）

用法：
  python scripts/init_db.py
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.clients.db_client import db_client
from app.models import Base  # Import all models to ensure metadata is complete


async def init_db() -> None:
    db_client.connect()
    async with db_client.engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await db_client.close()
    print("数据库初始化完成：已创建/校验所有表")


if __name__ == "__main__":
    asyncio.run(init_db())
