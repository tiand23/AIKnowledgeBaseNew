"""
检索服务 - 混合检索核心逻辑
"""
import asyncio
import re
from typing import List, Dict, Optional, Any
from uuid import uuid4
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_, tuple_
from app.models.file import FileUpload, DocumentVector, ChildChunk
from app.models.user import User, UserRole
from app.clients.elasticsearch_client import es_client
from app.services.embedding_service import embedding_service
from app.services.permission_service import permission_service
from app.services.profile_service import profile_service
from app.core.config import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)


class SearchService:
    
    INDEX_NAME = settings.ES_DEFAULT_INDEX
    
    VECTOR_DIMENSIONS = settings.OPENAI_EMBEDDING_DIMENSIONS

    ANALYZER_MODE_JA = "ja_kuromoji"
    ANALYZER_MODE_STANDARD = "standard"

    @staticmethod
    async def _supports_ja_analyzer() -> bool:
        """
        检测当前 ES 环境是否可用 kuromoji 相关能力。
        通过内置 _analyze API 直接校验 tokenizer/filter，避免盲创建失败。
        """
        try:
            if not es_client.client:
                return False
            await es_client.client.indices.analyze(
                body={
                    "tokenizer": "kuromoji_tokenizer",
                    "filter": ["kuromoji_baseform", "ja_stop", "kuromoji_stemmer"],
                    "text": "システム構成図",
                }
            )
            return True
        except Exception as e:
            logger.warning("kuromoji analyzer 能力探测失败，将回退 standard: %s", e)
            return False
    
    @staticmethod
    def get_index_mappings(analyzer_mode: str = ANALYZER_MODE_JA) -> Dict[str, Any]:
        """
        获取Elasticsearch索引的mapping配置
        
        Returns:
            索引mapping配置
        """
        text_mapping: Dict[str, Any] = {
            "type": "text",
            "analyzer": "ja_kuromoji",
            "search_analyzer": "ja_kuromoji_search",
            "fields": {
                "keyword": {
                    "type": "keyword",
                    "ignore_above": 256
                }
            }
        }
        if analyzer_mode == SearchService.ANALYZER_MODE_STANDARD:
            text_mapping = {
                "type": "text",
                "analyzer": "standard",
                "search_analyzer": "standard",
                "fields": {
                    "keyword": {
                        "type": "keyword",
                        "ignore_above": 256
                    }
                }
            }

        return {
            "properties": {
                "file_md5": {
                    "type": "keyword"
                },
                "chunk_id": {
                    "type": "integer"
                },
                "text_content": text_mapping,
                "vector": {
                    "type": "dense_vector",
                    "dims": SearchService.VECTOR_DIMENSIONS,  # Embedding dimensions (1536)
                    "index": True,  # Enable ANN indexing for faster retrieval
                    "similarity": "cosine"  # Cosine similarity
                },
                "user_id": {
                    "type": "long"
                },
                "org_tag": {
                    "type": "keyword"
                },
                "kb_profile": {
                    "type": "keyword"
                },
                "is_public": {
                    "type": "boolean"
                },
                "file_name": {
                    "type": "keyword"
                },
                "model_version": {
                    "type": "keyword"
                },
                "chunk_type": {
                    "type": "keyword"
                },
                "page": {
                    "type": "integer"
                },
                "section": {
                    "type": "keyword",
                    "ignore_above": 512
                },
                "sheet": {
                    "type": "keyword",
                    "ignore_above": 512
                },
                "image_path": {
                    "type": "keyword",
                    "ignore_above": 512
                },
                "quality_status": {
                    "type": "keyword"
                }
            }
        }
    
    @staticmethod
    def get_index_settings(analyzer_mode: str = ANALYZER_MODE_JA) -> Dict[str, Any]:
        """
        获取Elasticsearch索引的settings配置
        
        Returns:
            索引settings配置
        """
        base_settings: Dict[str, Any] = {
            "number_of_shards": 1,  # Shard count (tune for dataset size)
            "number_of_replicas": 0,  # Replica count (0 is acceptable for local/dev)
        }

        if analyzer_mode == SearchService.ANALYZER_MODE_STANDARD:
            return base_settings

        base_settings["analysis"] = {
            "filter": {
                "ja_pos_filter": {
                    "type": "kuromoji_part_of_speech",
                    "stoptags": [
                        "助詞-格助詞-一般",
                        "助詞-終助詞",
                        "助詞-副助詞",
                        "助詞-連体化",
                        "助詞-係助詞",
                        "助詞-接続助詞"
                    ]
                }
            },
            "analyzer": {
                "ja_kuromoji": {
                    "type": "custom",
                    "tokenizer": "kuromoji_tokenizer",
                    "filter": [
                        "kuromoji_baseform",
                        "ja_pos_filter",
                        "cjk_width",
                        "ja_stop",
                        "kuromoji_stemmer",
                        "lowercase"
                    ]
                },
                "ja_kuromoji_search": {
                    "type": "custom",
                    "tokenizer": "kuromoji_tokenizer",
                    "filter": [
                        "kuromoji_baseform",
                        "cjk_width",
                        "ja_stop",
                        "kuromoji_stemmer",
                        "lowercase"
                    ]
                }
            }
        }
        return base_settings
    
    @staticmethod
    async def ensure_index_exists() -> bool:
        """
        确保Elasticsearch索引存在，如果不存在则创建
        
        Returns:
            是否成功
        """
        try:
            exists = await es_client.index_exists(SearchService.INDEX_NAME)
            
            if exists:
                logger.info(f"索引 {SearchService.INDEX_NAME} 已存在")
                return True
            
            logger.info(f"创建索引 {SearchService.INDEX_NAME}...")
            try:
                analyzer_modes: List[str] = [SearchService.ANALYZER_MODE_STANDARD]
                if await SearchService._supports_ja_analyzer():
                    analyzer_modes = [
                        SearchService.ANALYZER_MODE_JA,
                        SearchService.ANALYZER_MODE_STANDARD,
                    ]
                else:
                    logger.info("ES 不支持 kuromoji，索引将使用 standard analyzer")

                for analyzer_mode in analyzer_modes:
                    success = await es_client.create_index(
                        index=SearchService.INDEX_NAME,
                        mappings=SearchService.get_index_mappings(analyzer_mode=analyzer_mode),
                        settings=SearchService.get_index_settings(analyzer_mode=analyzer_mode)
                    )
                    if success:
                        logger.info(
                            f"索引 {SearchService.INDEX_NAME} 创建成功，analyzer_mode={analyzer_mode}"
                        )
                        return True
                    logger.warning(f"索引创建失败，尝试下一个分析器模式: {analyzer_mode}")

                logger.error(f"索引 {SearchService.INDEX_NAME} 创建失败（所有分析器模式均失败）")
                logger.error("⚠️ 索引创建失败，后续查询可能无法正常工作")
                logger.error("常见原因：")
                logger.error("  1. Elasticsearch 连接失败")
                logger.error("  2. 索引配置错误（若需日语分词请确认已安装 analysis-kuromoji）")
                logger.error("  3. 认证或权限问题")
                return False
            except Exception as create_error:
                logger.error(f"调用 create_index 时发生异常: {type(create_error).__name__}: {create_error}")
                logger.error(f"异常详情: {repr(create_error)}", exc_info=True)
                logger.error("这可能是由于：")
                logger.error("  1. Elasticsearch 服务未运行或无法连接")
                logger.error("  2. 网络连接问题")
                logger.error("  3. 索引配置不兼容")
                return False
            
        except Exception as e:
            logger.error(f"确保索引存在时出错: {e}", exc_info=True)
            return False
    
    @staticmethod
    def build_hybrid_query(
        query_vector: List[float],
        query_text: str,
        permission_filters: List[Dict[str, Any]],
        vector_weight: Optional[float] = None,
        text_weight: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        构建混合检索查询（向量检索 + 全文检索）
        
        Args:
            query_vector: 查询向量
            query_text: 查询文本
            permission_filters: 权限过滤条件
            vector_weight: 向量检索权重（如果为None则使用配置中的值）
            text_weight: 全文检索权重（如果为None则使用配置中的值）
            
        Returns:
            Elasticsearch查询DSL
        """
        if vector_weight is None:
            vector_weight = settings.SEARCH_VECTOR_WEIGHT
        if text_weight is None:
            text_weight = settings.SEARCH_TEXT_WEIGHT
        
        if vector_weight < 0:
            logger.warning(f"向量权重不能为负数 ({vector_weight})，使用默认值 0.7")
            vector_weight = 0.7
        if text_weight < 0:
            logger.warning(f"文本权重不能为负数 ({text_weight})，使用默认值 0.3")
            text_weight = 0.3
        
        if vector_weight == 0 and text_weight == 0:
            logger.warning("向量权重和文本权重都为0，使用默认值: vector=0.7, text=0.3")
            vector_weight = 0.7
            text_weight = 0.3
        
        should_clauses = []
        
        if query_vector:
            if len(query_vector) != SearchService.VECTOR_DIMENSIONS:
                logger.warning(f"查询向量维度({len(query_vector)})与配置维度({SearchService.VECTOR_DIMENSIONS})不匹配")
            
            should_clauses.append({
                "script_score": {
                    "query": {"match_all": {}},
                    "script": {
                        "source": """
                            // 检查向量字段是否存在且不为空
                            if (doc['vector'].size() == 0) {
                                return 0.0;
                            }
                            
                            int vectorSize = doc['vector'].size();
                            
                            // 检查维度是否匹配
                            if (params.query_vector.length != vectorSize) {
                                return 0.0;
                            }
                            
                            // 计算余弦相似度
                            double dotProduct = 0.0;
                            double normA = 0.0;
                            double normB = 0.0;
                            
                            for (int i = 0; i < params.query_vector.length; i++) {
                                double v1 = params.query_vector[i];
                                double v2 = doc['vector'].get(i);
                                dotProduct += v1 * v2;
                                normA += v1 * v1;
                                normB += v2 * v2;
                            }
                            
                            // 避免除以零
                            double denominator = Math.sqrt(normA) * Math.sqrt(normB);
                            if (denominator == 0.0) {
                                return 0.0;
                            }
                            
                            double similarity = dotProduct / denominator;
                            
                            // 确保返回值在合理范围内（-1到1之间）
                            if (Double.isNaN(similarity) || Double.isInfinite(similarity)) {
                                return 0.0;
                            }
                            
                            return similarity;
                        """,
                        "params": {
                            "query_vector": query_vector
                        }
                    },
                    "boost": vector_weight
                }
            })
        
        if query_text and query_text.strip():
            should_clauses.append({
                "bool": {
                    "should": [
                        {
                            "match": {
                                "text_content": {
                                    "query": query_text,
                                    "boost": text_weight,
                                    "minimum_should_match": "60%"
                                }
                            }
                        },
                        {
                            "match_phrase": {
                                "text_content": {
                                    "query": query_text,
                                    "boost": round(text_weight * 1.3, 3)
                                }
                            }
                        }
                    ],
                    "minimum_should_match": 1
                }
            })

            if len(query_text.strip()) <= 24:
                should_clauses.append({
                    "match_phrase_prefix": {
                        "text_content": {
                            "query": query_text,
                            "boost": round(text_weight * 0.7, 3)
                        }
                    }
                })
        
        if permission_filters:
            if len(permission_filters) == 1:
                permission_filter = permission_filters[0]
            else:
                permission_filter = {
                    "bool": {
                        "should": permission_filters,
                        "minimum_should_match": 1
                    }
                }
        else:
            permission_filter = {"match_all": {}}
        
        query = {
            "query": {
                "bool": {
                    "should": should_clauses,
                    "filter": [permission_filter],
                    "minimum_should_match": 1 if should_clauses else 0
                }
            }
        }
        
        return query
    
    @staticmethod
    def _extract_query_keywords(query_text: str) -> List[str]:
        text = (query_text or "").strip()
        if not text:
            return []
        keywords: List[str] = []
        keywords.extend(re.findall(r"[\u3040-\u30ff\u3400-\u9fff]{2,16}", text))
        keywords.extend(re.findall(r"[A-Za-z][A-Za-z0-9_-]{1,31}", text))
        seen = set()
        deduped: List[str] = []
        for kw in keywords:
            k = kw.strip()
            if not k or k in seen:
                continue
            seen.add(k)
            deduped.append(k)
        return deduped[:6]

    @staticmethod
    async def keyword_fallback_search(
        db: AsyncSession,
        user: User,
        query_text: str,
        kb_profile: Optional[str] = None,
        top_k: int = 6,
    ) -> List[Dict[str, Any]]:
        """
        关键词兜底检索（数据库 LIKE），用于修复短查询/姓名/术语在 ES 分词下的漏召回。
        """
        keywords = SearchService._extract_query_keywords(query_text)
        if not keywords:
            return []

        if user.role == UserRole.ADMIN:
            file_stmt = select(FileUpload.file_md5, FileUpload.file_name, FileUpload.kb_profile)
            if kb_profile:
                file_stmt = file_stmt.where(FileUpload.kb_profile == kb_profile)
        else:
            accessible_tags = await permission_service.get_user_accessible_tags(db, user)
            conditions = permission_service.build_db_file_access_conditions(
                user=user,
                accessible_tags=accessible_tags,
            )
            file_stmt = select(FileUpload.file_md5, FileUpload.file_name, FileUpload.kb_profile).where(or_(*conditions))
            if kb_profile:
                file_stmt = file_stmt.where(FileUpload.kb_profile == kb_profile)

        file_rows = await db.execute(file_stmt)
        file_pairs = file_rows.all()
        if not file_pairs:
            return []

        md5_list = [row[0] for row in file_pairs if row and row[0]]
        file_name_map = {row[0]: row[1] for row in file_pairs if row and row[0]}
        profile_map = {row[0]: row[2] for row in file_pairs if row and row[0]}
        if not md5_list:
            return []

        like_conditions = []
        for kw in keywords:
            like_conditions.append(DocumentVector.text_content.ilike(f"%{kw}%"))
            compact = " ".join(list(kw)) if len(kw) <= 6 else ""
            if compact:
                like_conditions.append(DocumentVector.text_content.ilike(f"%{compact}%"))

        stmt = (
            select(DocumentVector.file_md5, DocumentVector.chunk_id, DocumentVector.text_content)
            .where(DocumentVector.file_md5.in_(md5_list))
            .where(or_(*like_conditions))
            .order_by(DocumentVector.vector_id.asc())
            .limit(max(1, top_k))
        )
        rows = await db.execute(stmt)
        raw_results: List[Dict[str, Any]] = []
        for row in rows.all():
            file_md5 = row[0]
            chunk_id = int(row[1] or 0)
            text_content = str(row[2] or "")
            score = 3.0
            lower_text = text_content.lower()
            for kw in keywords:
                if kw.lower() in lower_text:
                    score += 0.6
            if kb_profile and profile_map.get(file_md5) == kb_profile:
                score += 0.3
            raw_results.append(
                {
                    "file_md5": file_md5,
                    "chunk_id": chunk_id,
                    "text_content": text_content,
                    "score": round(score, 4),
                    "file_name": file_name_map.get(file_md5, "未知文件"),
                    "kb_profile": profile_map.get(file_md5),
                }
            )

        quality_map = await SearchService._load_chunk_quality_map(db, raw_results)
        for row in raw_results:
            key = (str(row.get("file_md5") or ""), int(row.get("chunk_id") or 0))
            row["quality_status"] = quality_map.get(key, "weak")

        return SearchService._prioritize_quality_rows(raw_results, top_k)

    @staticmethod
    async def _load_accessible_file_metadata(
        db: AsyncSession,
        user: User,
    ) -> Dict[str, FileUpload]:
        if user.role == UserRole.ADMIN:
            rows = await db.execute(select(FileUpload))
            files = rows.scalars().all()
            return {f.file_md5: f for f in files}

        accessible_tags = await permission_service.get_user_accessible_tags(db, user)
        conditions = permission_service.build_db_file_access_conditions(
            user=user,
            accessible_tags=accessible_tags,
        )
        rows = await db.execute(select(FileUpload).where(or_(*conditions)))
        files = rows.scalars().all()
        return {f.file_md5: f for f in files}

    @staticmethod
    def _extract_hits(
        search_result: Optional[Dict[str, Any]],
        source_name: str,
    ) -> List[Dict[str, Any]]:
        if not search_result:
            return []
        hits = search_result.get("hits", {}).get("hits", [])
        parsed: List[Dict[str, Any]] = []
        for rank, hit in enumerate(hits, 1):
            source = hit.get("_source", {})
            parsed.append(
                {
                    "file_md5": source.get("file_md5"),
                    "chunk_id": source.get("chunk_id"),
                    "text_content": source.get("text_content", ""),
                    "score": float(hit.get("_score", 0.0) or 0.0),
                    "file_name": source.get("file_name", "未知文件"),
                    "page": source.get("page"),
                    "sheet": source.get("sheet"),
                    "chunk_type": source.get("chunk_type"),
                    "quality_status": source.get("quality_status"),
                    "kb_profile": source.get("kb_profile"),
                    "source_type": source_name,
                    "rank": rank,
                }
            )
        return parsed

    @staticmethod
    def _profile_channel_weights(selected_profile: Optional[str]) -> Dict[str, float]:
        strategy = profile_service.get_strategy(selected_profile)
        vector = max(0.0, float(strategy.retrieval_weight_vector))
        bm25 = max(0.0, float(strategy.retrieval_weight_bm25))
        total_text = vector + bm25
        if total_text <= 0:
            return {"vector": 0.425, "bm25": 0.425, "entity": 0.15}
        entity = 0.15
        text_budget = 1.0 - entity
        return {
            "vector": text_budget * (vector / total_text),
            "bm25": text_budget * (bm25 / total_text),
            "entity": entity,
        }

    @staticmethod
    async def _load_chunk_quality_map(
        db: AsyncSession,
        rows: List[Dict[str, Any]],
    ) -> Dict[tuple[str, int], str]:
        keys = {
            (str(row.get("file_md5") or ""), int(row.get("chunk_id") or 0))
            for row in rows
            if row.get("file_md5") and int(row.get("chunk_id") or 0) >= 0
        }
        if not keys:
            return {}

        result = await db.execute(
            select(ChildChunk.file_md5, ChildChunk.child_chunk_id, ChildChunk.quality_status)
            .where(tuple_(ChildChunk.file_md5, ChildChunk.child_chunk_id).in_(list(keys)))
        )
        quality_map: Dict[tuple[str, int], str] = {}
        for file_md5, child_chunk_id, quality_status in result.all():
            quality_map[(str(file_md5 or ""), int(child_chunk_id or 0))] = str(quality_status or "weak")
        return quality_map

    @staticmethod
    def _prioritize_quality_rows(
        rows: List[Dict[str, Any]],
        top_k: int,
    ) -> List[Dict[str, Any]]:
        accepted: List[Dict[str, Any]] = []
        weak: List[Dict[str, Any]] = []
        for row in rows:
            status = str(row.get("quality_status") or "weak")
            if status == "rejected":
                continue
            if status == "accepted":
                accepted.append(row)
            else:
                weak.append(row)

        selected = accepted[: max(1, top_k)]
        if len(selected) < max(1, top_k):
            selected.extend(weak[: max(1, top_k) - len(selected)])
        return selected

    @staticmethod
    def _rrf_fuse(
        vectors: List[Dict[str, Any]],
        bm25: List[Dict[str, Any]],
        entity: List[Dict[str, Any]],
        selected_profile: Optional[str],
        entities: Optional[List[str]],
        top_k: int,
    ) -> List[Dict[str, Any]]:
        k = 60.0
        channel_weights = SearchService._profile_channel_weights(selected_profile)
        merged: Dict[str, Dict[str, Any]] = {}

        for bucket_name, bucket in (("vector", vectors), ("bm25", bm25), ("entity", entity)):
            for row in bucket:
                file_md5 = str(row.get("file_md5") or "")
                chunk_id = int(row.get("chunk_id") or 0)
                if not file_md5:
                    continue
                key = f"{file_md5}_{chunk_id}"
                if key not in merged:
                    merged[key] = dict(row)
                    merged[key]["rrf_score"] = 0.0
                    merged[key]["channels"] = set()
                channel_w = float(channel_weights.get(bucket_name, 0.33))
                merged[key]["rrf_score"] += channel_w * (1.0 / (k + float(row.get("rank", 999))))
                merged[key]["channels"].add(bucket_name)
                merged[key]["score"] = max(float(merged[key].get("score", 0.0)), float(row.get("score", 0.0)))

        for row in merged.values():
            bonus = 0.0
            if selected_profile and row.get("kb_profile") == selected_profile:
                bonus += 0.12
            channels = row.get("channels") or set()
            if "entity" in channels:
                bonus += 0.08
            if len(channels) >= 2:
                bonus += 0.05
            if entities:
                content = str(row.get("text_content") or "").lower()
                if any((e or "").lower() in content for e in entities):
                    bonus += 0.08
            row["final_score"] = float(row.get("rrf_score", 0.0)) + bonus
            row["channels"] = sorted(list(channels))

        fused = sorted(merged.values(), key=lambda x: x.get("final_score", 0.0), reverse=True)
        return fused[: max(1, top_k)]

    @staticmethod
    async def hybrid_search(
        db: AsyncSession,
        user: User,
        query_text: str,
        top_k: int = 10,
        entities: Optional[List[str]] = None,
        selected_profile: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        执行混合检索
        
        Args:
            db: 数据库会话
            user: 当前用户
            query_text: 查询文本
            top_k: 返回结果数量
            
        Returns:
            检索结果列表，每个结果包含：
            - file_md5: 文件MD5
            - chunk_id: 分块ID
            - text_content: 文本内容
            - score: 相关性分数
            - file_name: 文件名（从数据库查询）
        """
        query_id = uuid4().hex[:12]
        logger.info(
            f"[retrieval:{query_id}] hybrid_search start user={user.id} top_k={top_k} "
            f"query='{(query_text or '')[:120]}' entities={entities or []}"
        )

        selected_profile = selected_profile or await profile_service.get_selected_profile(db)
        if not selected_profile:
            logger.warning(f"[retrieval:{query_id}] 未初始化知识库场景，拒绝检索")
            return []

        index_exists = await SearchService.ensure_index_exists()
        if not index_exists:
            logger.error(f"[retrieval:{query_id}] ⚠️ 索引创建失败，无法执行检索")
            logger.error(f"[retrieval:{query_id}] 请检查 Elasticsearch 连接，以及日语分词插件 analysis-kuromoji（可选）是否可用")
            return await SearchService.keyword_fallback_search(
                db=db,
                user=user,
                query_text=query_text,
                kb_profile=None,
                top_k=top_k,
            )
        
        logger.info(f"[retrieval:{query_id}] 向量化查询文本: {query_text[:80]}...")
        query_vector = await embedding_service.embed_query(query_text)
        
        if not query_vector:
            logger.error(f"[retrieval:{query_id}] 查询向量化失败")
            return await SearchService.keyword_fallback_search(
                db=db,
                user=user,
                query_text=query_text,
                kb_profile=None,
                top_k=top_k,
            )
        
        if user.role == UserRole.ADMIN:
            permission_filters = []
        else:
            accessible_tags = await permission_service.get_user_accessible_tags(db, user)
            permission_filters = permission_service.build_elasticsearch_permission_filters(
                user_id=user.id,
                accessible_tags=accessible_tags
            )

        permission_filter = (
            permission_filters[0]
            if len(permission_filters) == 1
            else {
                "bool": {
                    "should": permission_filters,
                    "minimum_should_match": 1,
                }
            } if permission_filters else {"match_all": {}}
        )

        structured_terms: List[str] = []
        structured_seen: set[str] = set()
        for t in (entities or []) + SearchService._extract_query_keywords(query_text):
            term = str(t or "").strip()
            if not term or term in structured_seen:
                continue
            structured_seen.add(term)
            structured_terms.append(term)
        raw_query_text = (query_text or "").strip()
        if raw_query_text and raw_query_text not in structured_seen:
            structured_terms.append(raw_query_text)
        structured_terms = structured_terms[:8]

        structured_should: List[Dict[str, Any]] = []
        for term in structured_terms:
            # exact
            structured_should.append({"term": {"sheet": {"value": term, "boost": 3.2}}})
            structured_should.append({"term": {"section": {"value": term, "boost": 2.8}}})  # "title" maps to section
            structured_should.append({"term": {"file_name.keyword": {"value": term, "boost": 2.6}}})
            if len(term) >= 2:
                structured_should.append({"wildcard": {"file_name.keyword": {"value": f"*{term}*", "boost": 1.25}}})

        vector_query = {
            "bool": {
                "should": [
                    {
                        "script_score": {
                            "query": {"match_all": {}},
                            "script": {
                                "source": "cosineSimilarity(params.query_vector, 'vector') + 1.0",
                                "params": {"query_vector": query_vector},
                            },
                        }
                    }
                ],
                "filter": [permission_filter],
                "minimum_should_match": 1,
            }
        }
        bm25_query = {
            "bool": {
                "should": [
                    {"match": {"text_content": {"query": query_text, "boost": 1.0, "minimum_should_match": "60%"}}},
                    {"match_phrase": {"text_content": {"query": query_text, "boost": 1.2}}},
                ] + structured_should,
                "filter": [permission_filter],
                "minimum_should_match": 1,
            }
        }
        entity_should: List[Dict[str, Any]] = []
        for ent in entities or []:
            if not ent:
                continue
            entity_should.append({"match_phrase": {"text_content": {"query": ent, "boost": 2.0}}})
            entity_should.append({"term": {"file_name.keyword": {"value": ent, "boost": 1.8}}})
            entity_should.append({"term": {"sheet": {"value": ent, "boost": 2.0}}})
            entity_should.append({"term": {"section": {"value": ent, "boost": 1.9}}})
            if len(ent) >= 2:
                entity_should.append({"wildcard": {"file_name.keyword": {"value": f"*{ent}*", "boost": 1.2}}})
        entity_query = {
            "bool": {
                "should": entity_should if entity_should else [{"match_none": {}}],
                "filter": [permission_filter],
                "minimum_should_match": 1,
            }
        }

        search_size = max(top_k * 4, 20)
        try:
            vector_task = es_client.search(index=SearchService.INDEX_NAME, query=vector_query, size=search_size)
            bm25_task = es_client.search(index=SearchService.INDEX_NAME, query=bm25_query, size=search_size)
            entity_task = (
                es_client.search(index=SearchService.INDEX_NAME, query=entity_query, size=max(top_k * 2, 10))
                if entity_should
                else None
            )
            tasks: List[Any] = [vector_task, bm25_task]
            if entity_task is not None:
                tasks.append(entity_task)
            raw_results = await asyncio.gather(*tasks, return_exceptions=True)
        except Exception as e:
            logger.error(f"[retrieval:{query_id}] 并行检索执行失败，降级到关键词兜底: {e}", exc_info=True)
            return await SearchService.keyword_fallback_search(
                db=db,
                user=user,
                query_text=query_text,
                kb_profile=None,
                top_k=top_k,
            )

        vector_raw: Dict[str, Any] = {"hits": {"hits": []}}
        bm25_raw: Dict[str, Any] = {"hits": {"hits": []}}
        entity_raw: Dict[str, Any] = {"hits": {"hits": []}}
        if raw_results:
            if isinstance(raw_results[0], Exception):
                logger.warning(f"[retrieval:{query_id}] vector 通道失败，降级为空: {raw_results[0]}")
            else:
                vector_raw = raw_results[0] or vector_raw
        if len(raw_results) > 1:
            if isinstance(raw_results[1], Exception):
                logger.warning(f"[retrieval:{query_id}] bm25 通道失败，降级为空: {raw_results[1]}")
            else:
                bm25_raw = raw_results[1] or bm25_raw
        if entity_task is not None and len(raw_results) > 2:
            if isinstance(raw_results[2], Exception):
                logger.warning(f"[retrieval:{query_id}] entity 通道失败，降级为空: {raw_results[2]}")
            else:
                entity_raw = raw_results[2] or entity_raw

        vector_hits = SearchService._extract_hits(vector_raw, "vector")
        bm25_hits = SearchService._extract_hits(bm25_raw, "bm25")
        entity_hits = SearchService._extract_hits(entity_raw, "entity")
        vector_top = [f"{r.get('file_md5', '')}_{r.get('chunk_id', 0)}" for r in vector_hits[:3]]
        bm25_top = [f"{r.get('file_md5', '')}_{r.get('chunk_id', 0)}" for r in bm25_hits[:3]]
        entity_top = [f"{r.get('file_md5', '')}_{r.get('chunk_id', 0)}" for r in entity_hits[:3]]
        logger.info(
            f"[retrieval:{query_id}] channel_hits vector={len(vector_hits)} "
            f"bm25={len(bm25_hits)} entity={len(entity_hits)} profile={selected_profile}"
        )
        logger.info(
            f"[retrieval:{query_id}] pre_fuse_top vector={vector_top} bm25={bm25_top} entity={entity_top}"
        )

        fused = SearchService._rrf_fuse(
            vectors=vector_hits,
            bm25=bm25_hits,
            entity=entity_hits,
            selected_profile=selected_profile,
            entities=entities,
            top_k=max(top_k * 3, 20),
        )

        if not fused:
            logger.warning(f"[retrieval:{query_id}] fused 为空，走关键词兜底")
            return await SearchService.keyword_fallback_search(
                db=db,
                user=user,
                query_text=query_text,
                kb_profile=None,
                top_k=top_k,
            )

        quality_map = await SearchService._load_chunk_quality_map(db, fused)
        for row in fused:
            key = (str(row.get("file_md5") or ""), int(row.get("chunk_id") or 0))
            row["quality_status"] = quality_map.get(key, str(row.get("quality_status") or "weak"))
        fused = SearchService._prioritize_quality_rows(fused, top_k)

        file_metadata = await SearchService._load_accessible_file_metadata(db, user)
        results: List[Dict[str, Any]] = []
        for row in fused:
            file_md5 = str(row.get("file_md5") or "")
            file_info = file_metadata.get(file_md5)
            profile_value = row.get("kb_profile")
            if file_info:
                profile_value = file_info.kb_profile
            final_score = float(row.get("final_score", 0.0))
            results.append(
                {
                    "file_md5": file_md5,
                    "chunk_id": int(row.get("chunk_id") or 0),
                    "text_content": str(row.get("text_content") or ""),
                    "score": round(final_score, 4),
                    "file_name": file_info.file_name if file_info else row.get("file_name", "未知文件"),
                    "kb_profile": profile_value,
                    "channels": row.get("channels", []),
                    "quality_status": row.get("quality_status", "weak"),
                }
            )
        post_top = [f"{r.get('file_md5', '')}_{r.get('chunk_id', 0)}:{r.get('score', 0)}" for r in results[:5]]
        logger.info(f"[retrieval:{query_id}] post_fuse_top={post_top}")
        return results

    @staticmethod
    async def get_file_chunks(
        db: AsyncSession,
        file_md5: str,
        limit: int = 8,
    ) -> List[Dict[str, Any]]:
        stmt = (
            select(DocumentVector.file_md5, DocumentVector.chunk_id, DocumentVector.text_content, FileUpload.file_name)
            .join(FileUpload, FileUpload.file_md5 == DocumentVector.file_md5)
            .where(DocumentVector.file_md5 == file_md5)
            .order_by(DocumentVector.chunk_id.asc())
            .limit(max(1, limit))
        )
        rows = await db.execute(stmt)
        results: List[Dict[str, Any]] = []
        for row in rows.all():
            results.append(
                {
                    "file_md5": row[0],
                    "chunk_id": int(row[1] or 0),
                    "text_content": str(row[2] or ""),
                    "score": 1.0,
                    "file_name": row[3] or "未知文件",
                }
            )
        quality_map = await SearchService._load_chunk_quality_map(db, results)
        for row in results:
            key = (str(row.get("file_md5") or ""), int(row.get("chunk_id") or 0))
            row["quality_status"] = quality_map.get(key, "weak")
        return SearchService._prioritize_quality_rows(results, limit)


search_service = SearchService()
