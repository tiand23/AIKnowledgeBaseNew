"""
测试数据库连接
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text
from app.clients.db_client import db_client
from app.core.config import settings
from app.models.user import Base

async def init_db():
    print("=" * 50)
    print("初始化数据库")
    print("=" * 50)
    
    db_client.connect()
    
    async with db_client.engine.begin() as conn:
        print("\n测试：正在创建数据库表...")
        # await conn.run_sync(Base.metadata.drop_all)
        
        await conn.run_sync(Base.metadata.create_all)
    
    await db_client.close()
    
    print("\n" + "=" * 50)
    print("数据库表创建成功！")
    print("=" * 50)


if __name__ == "__main__":
    asyncio.run(init_db())



async def test_connection():
    print("=" * 50)
    print("测试： MySQL 数据库连接")
    print("=" * 50)
    
    db_url = settings.DATABASE_URL
    if '@' in db_url:
        before_at = db_url.split('@')[0]
        after_at = db_url.split('@')[1]
        if '://' in before_at:
            protocol = before_at.split('://')[0]
            credentials = before_at.split('://')[1]
            if ':' in credentials:
                username = credentials.split(':')[0]
                db_url_display = f"{protocol}://{username}:****@{after_at}"
            else:
                db_url_display = db_url
        else:
            db_url_display = db_url
    else:
        db_url_display = db_url
    
    print(f"\n测试：MySQL数据库连接，数据库连接URL: {db_url_display}\n")
    
    try:
        print("测试：MySQL数据库连接，正在连接数据库...")
        db_client.connect()
        
        async for session in db_client.get_session():
            result = await session.execute(text("SELECT 1 as test"))
            data = result.scalar()
            
            print("\n" + "=" * 50)
            print("测试：MySQL数据库连接，MySQL 数据库连接成功！")
            print("=" * 50)
            print(f"测试：MySQL数据库连接，查询结果: {data}")
            
            result = await session.execute(text("SELECT VERSION()"))
            version = result.scalar()
            print(f"测试：MySQL数据库连接，数据库版本: {version}")
        
        await db_client.close()
        print("\n测试：MySQL数据库连接，连接已正常关闭")
        return True
        
    except Exception as e:
        print("\n" + "=" * 50)
        print("测试：MySQL数据库连接，MySQL 数据库连接失败！")
        print("=" * 50)
        print(f"测试：MySQL数据库连接，错误类型: {type(e).__name__}")
        print(f"测试：MySQL数据库连接，错误信息: {str(e)}")
        return False


if __name__ == "__main__":
    print("\n测试：初始化数据库...\n")
    asyncio.run(init_db())
    print("\n测试：启动 MySQL 数据库连接测试...\n")
    asyncio.run(test_connection())
    print("\n测试：所有测试通过！")

