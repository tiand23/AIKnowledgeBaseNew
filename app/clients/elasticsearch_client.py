"""
Elasticsearch 客户端
"""
from elasticsearch import AsyncElasticsearch
from typing import Optional, Dict, List, Any
from app.core.config import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)


class ElasticsearchClient:
    
    def __init__(self):
        self.client: Optional[AsyncElasticsearch] = None
    
    async def connect(self):
        try:
            es_config = {
                "hosts": [settings.ES_HOST],
                "basic_auth": (settings.ES_USER, settings.ES_PASSWORD) if settings.ES_USER else None,
                "verify_certs": settings.ES_VERIFY_CERTS,
                "request_timeout": 30,
                "max_retries": 3,
                "retry_on_timeout": True,
            }
            
            if hasattr(settings, 'ES_API_KEY') and settings.ES_API_KEY:
                es_config["api_key"] = settings.ES_API_KEY
                es_config.pop("basic_auth", None)
            
            self.client = AsyncElasticsearch(**es_config)
            
            info = await self.client.info()
            logger.info(f"Elasticsearch 客户端初始化成功: {info['version']['number']}")
        except Exception as e:
            logger.error(f"Elasticsearch 客户端初始化失败: {e}")
            raise
    
    async def close(self):
        if self.client:
            await self.client.close()
            logger.info("Elasticsearch 连接已关闭")
    
    async def create_index(
        self,
        index: str,
        mappings: Optional[Dict] = None,
        settings: Optional[Dict] = None
    ) -> bool:
        """
        创建索引
        
        Args:
            index: 索引名称
            mappings: 字段映射配置
            settings: 索引设置
            
        Returns:
            bool: 是否创建成功
        """
        try:
            exists = await self.index_exists(index)
            if exists:
                logger.info(f"索引 {index} 已存在，跳过创建")
                return True
            
            body = {}
            if mappings:
                body["mappings"] = mappings
            if settings:
                body["settings"] = settings
            
            await self.client.indices.create(index=index, body=body)
            logger.info(f"索引创建成功: {index}")
            return True
        except Exception as e:
            import sys
            print(f"\n[ERROR] 索引创建异常: {type(e).__name__}: {e}", file=sys.stderr, flush=True)
            print(f"[ERROR] 错误详情: {repr(e)}", file=sys.stderr, flush=True)
            error_str = str(e).lower()
            if "resource_already_exists_exception" in error_str or "already_exists" in error_str:
                logger.info(f"索引 {index} 已存在（创建时发现），跳过")
                return True
            
            logger.error(f"索引创建失败: {type(e).__name__}: {e}")
            logger.error(f"错误详情: {repr(e)}")
            
            if "analyzer" in error_str or "not found" in error_str:
                logger.error("⚠️ 分词器配置可能不兼容当前 Elasticsearch 环境")
                logger.error("   建议：")
                logger.error("   1. 使用内置 standard analyzer（推荐）")
                logger.error("   2. 如需特定语言分词，再安装对应插件")
            
            return False
    
    async def delete_index(self, index: str) -> bool:
        """
        删除索引
        
        Args:
            index: 索引名称
            
        Returns:
            bool: 是否删除成功
        """
        try:
            await self.client.indices.delete(index=index)
            logger.info(f"索引删除成功: {index}")
            return True
        except Exception as e:
            logger.error(f"索引删除失败: {e}")
            return False
    
    async def index_exists(self, index: str) -> bool:
        """
        检查索引是否存在
        
        Args:
            index: 索引名称
            
        Returns:
            bool: 索引是否存在
        """
        try:
            return await self.client.indices.exists(index=index)
        except Exception as e:
            logger.error(f"检查索引失败: {e}")
            return False
    
    async def index_document(
        self,
        index: str,
        document: Dict,
        doc_id: Optional[str] = None
    ) -> Optional[str]:
        """
        索引文档（添加或更新）
        
        Args:
            index: 索引名称
            document: 文档数据
            doc_id: 文档 ID（可选，不提供则自动生成）
            
        Returns:
            Optional[str]: 文档 ID，失败返回 None
        """
        try:
            if doc_id:
                result = await self.client.index(index=index, id=doc_id, document=document)
            else:
                result = await self.client.index(index=index, document=document)
            
            logger.info(f"文档索引成功: {index}/{result['_id']}")
            return result["_id"]
        except Exception as e:
            logger.error(f"文档索引失败: {e}")
            return None
    
    async def get_document(self, index: str, doc_id: str) -> Optional[Dict]:
        """
        获取文档
        
        Args:
            index: 索引名称
            doc_id: 文档 ID
            
        Returns:
            Optional[Dict]: 文档数据，失败返回 None
        """
        try:
            result = await self.client.get(index=index, id=doc_id)
            return result["_source"]
        except Exception as e:
            logger.error(f"获取文档失败: {e}")
            return None
    
    async def update_document(
        self,
        index: str,
        doc_id: str,
        document: Dict
    ) -> bool:
        """
        更新文档
        
        Args:
            index: 索引名称
            doc_id: 文档 ID
            document: 要更新的字段
            
        Returns:
            bool: 是否更新成功
        """
        try:
            await self.client.update(index=index, id=doc_id, doc=document)
            logger.info(f"文档更新成功: {index}/{doc_id}")
            return True
        except Exception as e:
            logger.error(f"文档更新失败: {e}")
            return False
    
    async def delete_document(self, index: str, doc_id: str) -> bool:
        """
        删除文档
        
        Args:
            index: 索引名称
            doc_id: 文档 ID
            
        Returns:
            bool: 是否删除成功
        """
        try:
            await self.client.delete(index=index, id=doc_id)
            logger.info(f"文档删除成功: {index}/{doc_id}")
            return True
        except Exception as e:
            logger.error(f"文档删除失败: {e}")
            return False

    async def delete_by_query(self, index: str, query: Dict[str, Any]) -> bool:
        """
        按查询条件删除文档。

        Args:
            index: 索引名称
            query: ES query 子句

        Returns:
            bool: 是否成功
        """
        try:
            if not self.client:
                logger.error("Elasticsearch 客户端未初始化")
                return False
            exists = await self.index_exists(index)
            if not exists:
                return True
            resp = await self.client.delete_by_query(
                index=index,
                body={"query": query},
                refresh=True,
                conflicts="proceed",
                wait_for_completion=True,
            )
            logger.info(
                "按条件删除文档完成: index=%s, deleted=%s, total=%s",
                index,
                resp.get("deleted", 0),
                resp.get("total", 0),
            )
            return True
        except Exception as e:
            logger.error(f"按条件删除文档失败: {e}", exc_info=True)
            return False
    
    async def search(
        self,
        index: str,
        query: Dict,
        size: int = 10,
        from_: int = 0,
        sort: Optional[List] = None
    ) -> Optional[Dict]:
        """
        搜索文档
        
        Args:
            index: 索引名称
            query: 查询条件
            size: 返回结果数量
            from_: 分页起始位置
            sort: 排序条件
            
        Returns:
            搜索结果字典，失败返回 None
        """
        try:
            if not self.client:
                logger.error("Elasticsearch 客户端未初始化")
                return None
            
            exists = await self.index_exists(index)
            if not exists:
                logger.warning(f"索引 {index} 不存在，无法搜索")
                return None
            
            search_params = {
                "index": index,
                "body": {"query": query},
                "size": size,
                "from": from_
            }
            
            if sort:
                search_params["body"]["sort"] = sort
            
            result = await self.client.search(**search_params)
            return result
            
        except Exception as e:
            logger.error(f"搜索失败: {type(e).__name__}: {e}")
            logger.error(f"搜索错误详情: {repr(e)}", exc_info=True)
            return None
    
    async def bulk_index(self, index: str, documents: List[Dict]) -> bool:
        """
        批量索引文档
        
        Args:
            index: 索引名称
            documents: 文档列表，每个文档应包含 _id（可选）和 _source
            
        Returns:
            bool: 是否成功
        """
        try:
            from elasticsearch.helpers import async_bulk
            
            actions = []
            for doc in documents:
                action = {
                    "_index": index,
                    "_source": doc.get("_source", doc)
                }
                if "_id" in doc:
                    action["_id"] = doc["_id"]
                actions.append(action)
            
            success, failed = await async_bulk(self.client, actions)
            logger.info(f"批量索引完成: 成功 {success}, 失败 {failed}")
            return failed == 0
        except Exception as e:
            logger.error(f"批量索引失败: {e}")
            return False
    
    async def count(self, index: str, query: Optional[Dict] = None) -> Optional[int]:
        """
        统计文档数量
        
        Args:
            index: 索引名称
            query: 查询条件（可选）
            
        Returns:
            Optional[int]: 文档数量，失败返回 None
        """
        try:
            body = {"query": query} if query else None
            result = await self.client.count(index=index, body=body)
            return result["count"]
        except Exception as e:
            logger.error(f"统计文档数量失败: {e}")
            return None
    
    async def refresh_index(self, index: str) -> bool:
        """
        刷新索引（使最近的更改可搜索）
        
        Args:
            index: 索引名称
            
        Returns:
            bool: 是否成功
        """
        try:
            await self.client.indices.refresh(index=index)
            return True
        except Exception as e:
            logger.error(f"刷新索引失败: {e}")
            return False
    
    async def health_check(self) -> bool:
        try:
            health = await self.client.cluster.health()
            return health["status"] in ["green", "yellow"]
        except Exception as e:
            logger.error(f"Elasticsearch 健康检查失败: {e}")
            return False
    
    async def get_status(self) -> Dict[str, Any]:
        if not self.client:
            return {"error": "Elasticsearch 客户端未初始化"}
        
        try:
            info = await self.client.info()
            health = await self.client.cluster.health()
            stats = await self.client.cluster.stats()
            
            return {
                "状态": health["status"],
                "版本": info["version"]["number"],
                "集群名称": health["cluster_name"],
                "节点数量": health["number_of_nodes"],
                "数据节点数量": health["number_of_data_nodes"],
                "活跃分片": health["active_shards"],
                "索引数量": stats["indices"]["count"],
                "文档总数": stats["indices"]["docs"]["count"],
                "存储大小": stats["indices"]["store"]["size_in_bytes"]
            }
        except Exception as e:
            return {
                "状态": "连接失败",
                "错误": str(e)
            }


es_client = ElasticsearchClient()
