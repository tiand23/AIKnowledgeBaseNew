"""
测试 Elasticsearch 连接
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.clients.elasticsearch_client import es_client
from app.core.config import settings


async def test_elasticsearch():
    print("=" * 50)
    print("测试： Elasticsearch 连接")
    print("=" * 50)
    print(f"\n测试：Elasticsearch 主机：{settings.ES_HOST}")
    print(f"测试：Elasticsearch 用户：{settings.ES_USER if settings.ES_USER else '无'}")
    print(f"测试：验证证书：{settings.ES_VERIFY_CERTS}\n")

    try:
        print("测试：正在连接 Elasticsearch...")
        await es_client.connect()

        info = await es_client.client.info()
        print(f"\n测试：集群名称：{info['cluster_name']}")
        print(f"测试：版本：{info['version']['number']}")
        print(f"测试：Lucene 版本：{info['version']['lucene_version']}")

        print("\n测试：执行健康检查...")
        is_healthy = await es_client.health_check()
        
        if is_healthy:
            print("测试：健康检查通过")
        else:
            print("测试：健康检查警告（集群状态可能不是 green）")

        test_index = "test_connection_index"
        print(f"\n测试：创建测试索引：{test_index}")
        
        if await es_client.index_exists(test_index):
            await es_client.delete_index(test_index)
            print(f"测试：删除已存在的测试索引")
        
        success = await es_client.create_index(
            index=test_index,
            mappings={
                "properties": {
                    "message": {"type": "text"},
                    "timestamp": {"type": "date"}
                }
            }
        )
        
        if success:
            print(f"测试：索引创建成功")
        else:
            print(f"测试：索引创建失败")
            return False

        test_doc = {
            "message": "Hello Elasticsearch!",
            "timestamp": "2024-01-01T00:00:00"
        }
        print(f"\n测试：索引测试文档：{test_doc}")
        
        doc_id = await es_client.index_document(
            index=test_index,
            document=test_doc,
            doc_id="test_doc_1"
        )
        
        if doc_id:
            print(f"测试：文档索引成功，ID：{doc_id}")
        else:
            print("测试：文档索引失败")
            return False

        await es_client.refresh_index(test_index)

        print("\n测试：获取文档...")
        retrieved_doc = await es_client.get_document(test_index, doc_id)
        
        if retrieved_doc:
            print(f"测试：文档获取成功：{retrieved_doc}")
        else:
            print("测试：文档获取失败")
            return False

        print("\n测试：搜索文档...")
        search_result = await es_client.search(
            index=test_index,
            query={"match": {"message": "Hello"}},
            size=10
        )
        
        if search_result and search_result["hits"]["total"]["value"] > 0:
            print(f"测试：搜索成功，找到 {search_result['hits']['total']['value']} 个文档")
        else:
            print("测试：搜索未找到文档")

        count = await es_client.count(test_index)
        print(f"测试：索引文档总数：{count}")

        print(f"\n测试：清理测试数据...")
        await es_client.delete_index(test_index)
        print(f"测试：测试索引已删除")

        print("\n测试：获取集群状态...")
        status = await es_client.get_status()
        print("测试：集群状态信息：")
        for key, value in status.items():
            if key != "存储大小":
                print(f"  {key}: {value}")
            else:
                size_bytes = value
                if size_bytes < 1024:
                    size_str = f"{size_bytes} B"
                elif size_bytes < 1024 * 1024:
                    size_str = f"{size_bytes / 1024:.2f} KB"
                elif size_bytes < 1024 * 1024 * 1024:
                    size_str = f"{size_bytes / (1024 * 1024):.2f} MB"
                else:
                    size_str = f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"
                print(f"  {key}: {size_str}")

        print("\n" + "=" * 50)
        print("测试：Elasticsearch 连接成功！")
        print("=" * 50)
        print("测试：所有功能测试通过")

        await es_client.close()
        print("\n测试：连接已正常关闭")
        return True

    except Exception as e:
        print("\n" + "=" * 50)
        print("测试：Elasticsearch 连接失败！")
        print("=" * 50)
        print(f"测试：错误类型: {type(e).__name__}")
        print(f"测试：错误信息: {str(e)}")
        
        try:
            await es_client.close()
        except:
            pass
        
        return False


if __name__ == "__main__":
    print("\n测试：启动 Elasticsearch 连接测试...\n")
    success = asyncio.run(test_elasticsearch())

    if success:
        print("\n测试：所有测试通过！")
        sys.exit(0)
    else:
        print("\n测试：提示排查问题后重试")
        sys.exit(1)

