"""
调试 Elasticsearch 索引数据
检查索引中是否有数据，以及权限过滤是否正确
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.clients.elasticsearch_client import es_client
from app.clients.db_client import db_client
from app.services.search_service import search_service
from app.models.user import User
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from app.core.config import settings

import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def check_elasticsearch_data():
    print("=" * 60)
    print("检查 Elasticsearch 索引数据")
    print("=" * 60)
    print()
    
    async_engine = None
    try:
        print("连接 Elasticsearch...")
        await es_client.connect()
        db_client.connect()
        print("连接成功\n")
        
        index_name = search_service.INDEX_NAME
        print(f"1. 检查索引是否存在: {index_name}")
        index_exists = await es_client.index_exists(index_name)
        if index_exists:
            print(f"   ✓ 索引存在")
        else:
            print(f"   ✗ 索引不存在")
            return
        print()
        
        print("2. 统计索引中的文档数量")
        try:
            stats = await es_client.client.indices.stats(index=index_name)
            doc_count = stats['indices'][index_name]['total']['docs']['count']
            print(f"   ✓ 文档总数: {doc_count}")
        except Exception as e:
            print(f"   ✗ 获取统计信息失败: {e}")
        print()
        
        print("3. 查询所有文档（前10个）")
        try:
            search_result = await es_client.search(
                index=index_name,
                query={"match_all": {}},
                size=10
            )
            
            hits = search_result.get("hits", {}).get("hits", [])
            print(f"   ✓ 找到 {len(hits)} 个文档")
            
            for i, hit in enumerate(hits[:5], 1):
                source = hit.get("_source", {})
                print(f"   文档 {i}:")
                print(f"     - doc_id: {hit.get('_id')}")
                print(f"     - file_md5: {source.get('file_md5')}")
                print(f"     - chunk_id: {source.get('chunk_id')}")
                print(f"     - user_id: {source.get('user_id')}")
                print(f"     - org_tag: {source.get('org_tag')}")
                print(f"     - is_public: {source.get('is_public')}")
                print(f"     - file_name: {source.get('file_name')}")
                print(f"     - text_content: {source.get('text_content', '')[:50]}...")
                print()
        except Exception as e:
            print(f"   ✗ 查询失败: {e}")
            import traceback
            traceback.print_exc()
        print()
        
        print("4. 检查测试用户")
        async_engine = create_async_engine(
            settings.DATABASE_URL,
            echo=False
        )
        async_session = async_sessionmaker(async_engine, expire_on_commit=False)
        
        async with async_session() as db:
            result = await db.execute(
                select(User).where(User.username == "test_chat_user")
            )
            user = result.scalar_one_or_none()
            
            if user:
                print(f"   ✓ 找到测试用户: {user.username}")
                print(f"     - user_id: {user.id}")
                print(f"     - primary_org: {user.primary_org}")
                print(f"     - org_tags: {user.org_tags}")
            else:
                print(f"   ✗ 未找到测试用户")
                return
        print()
        
        print("5. 使用测试用户进行权限过滤查询")
        async with async_session() as db:
            from app.services.permission_service import permission_service
            
            accessible_tags = await permission_service.get_user_accessible_tags(db, user)
            print(f"   用户可访问的标签: {accessible_tags}")
            
            permission_filters = permission_service.build_elasticsearch_permission_filters(
                user_id=user.id,
                accessible_tags=accessible_tags
            )
            print(f"   权限过滤条件数量: {len(permission_filters)}")
            for i, filter_cond in enumerate(permission_filters, 1):
                print(f"     条件 {i}: {filter_cond}")
            
            if len(permission_filters) == 1:
                permission_filter = permission_filters[0]
            else:
                permission_filter = {
                    "bool": {
                        "should": permission_filters,
                        "minimum_should_match": 1
                    }
                }
            
            query = {
                "query": {
                    "bool": {
                        "should": [
                            {"match_all": {}}
                        ],
                        "filter": [permission_filter],
                        "minimum_should_match": 1
                    }
                }
            }
            
            search_result = await es_client.search(
                index=index_name,
                query=query["query"],
                size=10
            )
            
            hits = search_result.get("hits", {}).get("hits", [])
            print(f"   ✓ 权限过滤后找到 {len(hits)} 个文档")
            
            if hits:
                print("   前3个匹配的文档:")
                for i, hit in enumerate(hits[:3], 1):
                    source = hit.get("_source", {})
                    print(f"     文档 {i}:")
                    print(f"       - user_id: {source.get('user_id')}")
                    print(f"       - org_tag: {source.get('org_tag')}")
                    print(f"       - is_public: {source.get('is_public')}")
                    print(f"       - text_content: {source.get('text_content', '')[:50]}...")
            else:
                print("   ⚠️  没有找到匹配的文档")
                print("   可能的原因:")
                print("     1. 索引中的 user_id 与测试用户的 user_id 不匹配")
                print("     2. org_tag 不匹配")
                print("     3. is_public 为 False 且不是用户自己的文档")
        print()
        
    except Exception as e:
        print(f"❌ 错误: {e}")
        import traceback
        traceback.print_exc()
    finally:
        try:
            if async_engine:
                await asyncio.wait_for(async_engine.dispose(close=True), timeout=2.0)
        except (asyncio.TimeoutError, asyncio.CancelledError, RuntimeError, AttributeError, Exception):
            pass
        
        try:
            if db_client.engine:
                await asyncio.wait_for(db_client.close(), timeout=2.0)
        except (asyncio.TimeoutError, asyncio.CancelledError, RuntimeError, AttributeError, Exception):
            pass
        
        try:
            await asyncio.wait_for(es_client.close(), timeout=2.0)
        except (asyncio.TimeoutError, asyncio.CancelledError, RuntimeError, Exception):
            pass
        
        await asyncio.sleep(0.1)


if __name__ == "__main__":
    asyncio.run(check_elasticsearch_data())

