"""
测试 Elasticsearch 索引创建问题
诊断三个常见问题：
1. IK 分词器插件未安装
2. Elasticsearch 连接失败
3. 索引配置错误
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.clients.elasticsearch_client import es_client
from app.services.search_service import SearchService
from app.core.config import settings


def print_section(title: str):
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)


def print_test(test_name: str):
    print(f"\n[测试] {test_name}")


def print_success(message: str):
    print(f"  ✅ {message}")


def print_error(message: str):
    print(f"  ❌ {message}")


def print_warning(message: str):
    print(f"  ⚠️  {message}")


def print_info(message: str):
    print(f"  ℹ️  {message}")


async def test_elasticsearch_connection():
    print_section("测试1: Elasticsearch 连接")
    
    try:
        print_test("连接 Elasticsearch")
        await es_client.connect()
        print_success("Elasticsearch 连接成功")
        
        info = await es_client.client.info()
        print_info(f"集群名称: {info['cluster_name']}")
        print_info(f"版本: {info['version']['number']}")
        print_info(f"Lucene 版本: {info['version']['lucene_version']}")
        
        health = await es_client.client.cluster.health()
        status = health['status']
        if status == 'green':
            print_success(f"集群状态: {status}")
        elif status == 'yellow':
            print_warning(f"集群状态: {status}（部分副本不可用）")
        else:
            print_error(f"集群状态: {status}（不健康）")
        
        return True
    except Exception as e:
        print_error(f"Elasticsearch 连接失败: {e}")
        print_info("请检查：")
        print_info("  1. Elasticsearch 服务是否运行")
        print_info(f"  2. 连接地址是否正确: {settings.ES_HOST}")
        print_info("  3. 网络连接是否正常")
        print_info("  4. 认证信息是否正确")
        return False


async def test_ik_plugin():
    print_section("测试2: IK 分词器插件检查")
    
    try:
        print_test("检查已安装的插件")
        
        try:
            plugins_response = await es_client.client.cat.plugins(format="json", h="name,component")
            plugins = plugins_response if isinstance(plugins_response, list) else []
        except:
            try:
                plugins_raw = await es_client.client.cat.plugins(format="text")
                plugins = []
                for line in plugins_raw.strip().split('\n'):
                    if line.strip():
                        parts = line.split()
                        if len(parts) >= 2:
                            plugins.append({'name': parts[0], 'component': parts[1]})
            except:
                plugins = []
        
        if not plugins:
            print_warning("无法获取插件列表或未找到任何插件")
            print_info("将通过测试索引创建来验证 IK 插件（更可靠的方法）")
            return None  # Return None when uncertain; validate via index-creation test
        
        ik_plugins = []
        for p in plugins:
            plugin_name = str(p.get('name', '') + ' ' + p.get('component', '')).lower()
            if 'ik' in plugin_name:
                ik_plugins.append(p)
        
        if ik_plugins:
            print_success("IK 分词器插件已安装")
            for plugin in ik_plugins:
                plugin_name = plugin.get('name', 'Unknown') or plugin.get('component', 'Unknown')
                print_info(f"  - {plugin_name}")
            return True
        else:
            print_error("IK 分词器插件未安装")
            print_info("解决方案：")
            print_info("  安装 IK 插件命令:")
            version = await es_client.client.info()
            es_version = version['version']['number']
            print_info(f"  ./elasticsearch-plugin install https://github.com/medcl/elasticsearch-analysis-ik/releases/download/v{es_version}/elasticsearch-analysis-ik-{es_version}.zip")
            print_info("  安装后需要重启 Elasticsearch")
            return False
            
    except Exception as e:
        print_warning(f"检查插件时出错: {e}")
        print_info("将通过测试索引创建来验证 IK 插件")
        return None  # Return None when uncertain


async def test_index_creation_with_ik():
    print_section("测试3: 使用 IK 分词器创建索引")
    
    test_index = "test_index_ik"
    
    try:
        if await es_client.index_exists(test_index):
            print_test(f"删除已存在的测试索引: {test_index}")
            await es_client.delete_index(test_index)
            print_success("旧索引已删除")
        
        print_test(f"创建测试索引: {test_index} (使用 IK 分词器)")
        
        mappings = SearchService.get_index_mappings()
        settings_config = SearchService.get_index_settings()
        
        print_info("索引配置:")
        print_info(f"  - 文本分析器: ik_max_word")
        print_info(f"  - 搜索分析器: ik_smart")
        
        success = await es_client.create_index(
            index=test_index,
            mappings=mappings,
            settings=settings_config
        )
        
        if success:
            print_success(f"索引 {test_index} 创建成功（使用 IK 分词器）")
            
            exists = await es_client.index_exists(test_index)
            if exists:
                print_success("索引验证成功")
                
                mapping = await es_client.client.indices.get_mapping(index=test_index)
                text_content_config = mapping[test_index]["mappings"]["properties"]["text_content"]
                analyzer = text_content_config.get("analyzer", "default")
                print_info(f"实际使用的分析器: {analyzer}")
                
                await es_client.delete_index(test_index)
                print_info("测试索引已清理")
                return True
            else:
                print_error("索引创建后验证失败")
                return False
        else:
            print_error(f"索引 {test_index} 创建失败")
            print_info("可能的原因：")
            print_info("  1. IK 分词器插件未安装")
            print_info("  2. 索引配置错误")
            print_info("  3. Elasticsearch 版本不兼容")
            return False
            
    except Exception as e:
        error_str = str(e).lower()
        print_error(f"创建索引时发生异常: {type(e).__name__}: {e}")
        
        if "ik" in error_str or "analyzer" in error_str or "not found" in error_str:
            print_error("确认：这是 IK 分词器相关的错误")
            print_info("解决方案：")
            print_info("  1. 安装 IK 分词器插件")
            print_info("  2. 或使用标准分词器（见测试4）")
        elif "connection" in error_str or "timeout" in error_str:
            print_error("确认：这是连接相关的错误")
        else:
            print_error("确认：这是其他配置错误")
            print_info(f"错误详情: {repr(e)}")
        
        return False


async def test_index_creation_with_standard():
    print_section("测试4: 使用标准分词器创建索引（备选方案）")
    
    test_index = "test_index_standard"
    
    try:
        if await es_client.index_exists(test_index):
            print_test(f"删除已存在的测试索引: {test_index}")
            await es_client.delete_index(test_index)
            print_success("旧索引已删除")
        
        print_test(f"创建测试索引: {test_index} (使用标准分词器)")
        
        mappings = SearchService.get_index_mappings()
        mappings["properties"]["text_content"]["analyzer"] = "standard"
        mappings["properties"]["text_content"]["search_analyzer"] = "standard"
        
        settings_config = {
            "number_of_shards": 1,
            "number_of_replicas": 0
        }
        
        print_info("索引配置:")
        print_info(f"  - 文本分析器: standard")
        print_info(f"  - 搜索分析器: standard")
        print_warning("注意：标准分词器不支持中文分词，只适合英文或测试使用")
        
        success = await es_client.create_index(
            index=test_index,
            mappings=mappings,
            settings=settings_config
        )
        
        if success:
            print_success(f"索引 {test_index} 创建成功（使用标准分词器）")
            
            exists = await es_client.index_exists(test_index)
            if exists:
                print_success("索引验证成功")
                
                await es_client.delete_index(test_index)
                print_info("测试索引已清理")
                return True
            else:
                print_error("索引创建后验证失败")
                return False
        else:
            print_error(f"索引 {test_index} 创建失败（即使使用标准分词器）")
            print_info("这表明问题不在 IK 分词器，可能是其他配置问题")
            return False
            
    except Exception as e:
        print_error(f"创建索引时发生异常: {type(e).__name__}: {e}")
        print_info(f"错误详情: {repr(e)}")
        return False


async def test_default_index_exists(ik_plugin_available: bool = False):
    print_section("测试5: 检查默认索引状态")
    
    index_name = SearchService.INDEX_NAME
    print_test(f"检查索引: {index_name}")
    
    try:
        exists = await es_client.index_exists(index_name)
        
        if exists:
            print_success(f"索引 {index_name} 已存在")
            
            try:
                stats = await es_client.client.indices.stats(index=index_name)
                doc_count = stats['indices'][index_name]['total']['docs']['count']
                print_info(f"文档数量: {doc_count}")
                
                mapping = await es_client.client.indices.get_mapping(index=index_name)
                text_config = mapping[index_name]["mappings"]["properties"].get("text_content", {})
                if text_config:
                    analyzer = text_config.get("analyzer", "default")
                    print_info(f"使用的分析器: {analyzer}")
                    if analyzer in ["ik_max_word", "ik_smart"]:
                        if ik_plugin_available:
                            print_success("当前索引使用 IK 分词器，且插件已安装，索引正常工作")
                        else:
                            print_warning("当前索引使用 IK 分词器，如果 IK 插件未安装，索引可能无法正常工作")
                
            except Exception as e:
                print_warning(f"获取索引信息时出错: {e}")
            
            return True
        else:
            print_warning(f"索引 {index_name} 不存在")
            print_info("需要创建索引才能使用检索功能")
            return False
            
    except Exception as e:
        print_error(f"检查索引时出错: {e}")
        return False


async def main():
    print("\n" + "=" * 60)
    print("  Elasticsearch 索引问题诊断工具")
    print("=" * 60)
    print("\n此工具将测试以下问题：")
    print("  1. Elasticsearch 连接是否正常")
    print("  2. IK 分词器插件是否已安装")
    print("  3. 使用 IK 分词器创建索引是否成功")
    print("  4. 使用标准分词器创建索引是否成功（备选方案）")
    print("  5. 默认索引是否存在")
    
    results = {
        "连接测试": False,
        "IK插件检查": False,
        "IK索引创建": False,
        "标准索引创建": False,
        "默认索引检查": False
    }
    
    try:
        results["连接测试"] = await test_elasticsearch_connection()
        
        if not results["连接测试"]:
            print_section("诊断结果")
            print_error("Elasticsearch 连接失败，无法继续测试")
            print_info("请先解决连接问题，然后重新运行测试")
            return
        
        ik_result = await test_ik_plugin()
        
        results["IK索引创建"] = await test_index_creation_with_ik()
        
        if ik_result is None and results["IK索引创建"]:
            print_info("\n注：虽然无法通过 API 获取插件列表，但 IK 索引创建成功，说明 IK 插件已安装")
            results["IK插件检查"] = True
        else:
            results["IK插件检查"] = ik_result if ik_result is not None else False
        
        results["标准索引创建"] = await test_index_creation_with_standard()
        
        ik_plugin_available = results["IK索引创建"]  # IK plugin is considered available if index creation succeeds
        results["默认索引检查"] = await test_default_index_exists(ik_plugin_available=ik_plugin_available)
        
        print_section("诊断总结")
        
        total = len(results)
        passed = sum(1 for v in results.values() if v)
        
        print(f"\n测试结果: {passed}/{total} 通过\n")
        
        for test_name, result in results.items():
            if result:
                print_success(f"{test_name}: 通过")
            else:
                print_error(f"{test_name}: 失败")
        
        print("\n" + "-" * 60)
        print("建议:")
        
        if not results["连接测试"]:
            print_error("1. 请先解决 Elasticsearch 连接问题")
        
        if not results["IK插件检查"] and results["IK索引创建"]:
            print_success("2. IK 分词器插件已安装（通过索引创建测试验证）")
            print_info("   虽然无法通过 API 获取插件列表，但 IK 索引创建成功，说明插件正常工作")
        elif not results["IK插件检查"] and not results["IK索引创建"]:
            print_warning("2. IK 分词器插件未安装或未正常工作，建议安装以支持中文分词")
            print_info("   安装命令：")
            info = await es_client.client.info()
            es_version = info['version']['number']
            print_info(f"   ./elasticsearch-plugin install https://github.com/medcl/elasticsearch-analysis-ik/releases/download/v{es_version}/elasticsearch-analysis-ik-{es_version}.zip")
        
        if not results["IK索引创建"] and results["标准索引创建"]:
            print_warning("3. IK 分词器索引创建失败，但标准分词器可以创建")
            print_info("   建议：安装 IK 插件，或临时使用标准分词器")
        
        if not results["IK索引创建"] and not results["标准索引创建"]:
            print_error("4. 索引创建完全失败，可能是配置问题")
            print_info("   请检查 Elasticsearch 版本和配置")
        
        if not results["默认索引检查"]:
            print_warning("5. 默认索引不存在，需要创建索引后才能使用检索功能")
            print_info("   可以运行 test_upload_knowledge_base.py 来创建索引")
        
        print("\n" + "=" * 60)
        
    except Exception as e:
        print_error(f"测试过程中发生异常: {e}")
        import traceback
        traceback.print_exc()
    finally:
        try:
            await es_client.close()
        except:
            pass


if __name__ == "__main__":
    asyncio.run(main())

