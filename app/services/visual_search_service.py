"""
视觉检索索引服务
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.elasticsearch_client import es_client
from app.core.config import settings
from app.models.file import DocumentUnit, FileUpload, ParentChunk, VisualPage, VisualPageEmbedding
from app.models.user import User, UserRole
from app.services.permission_service import permission_service
from app.services.visual_embedding_service import visual_embedding_service
from app.utils.logger import get_logger

logger = get_logger(__name__)


class VisualSearchService:

    INDEX_NAME = settings.ES_VISUAL_INDEX
    VECTOR_DIMENSIONS = settings.GEMINI_VISUAL_EMBEDDING_DIMENSIONS

    @staticmethod
    def get_index_mappings() -> Dict[str, Any]:
        return {
            "properties": {
                "visual_page_id": {"type": "long"},
                "file_md5": {"type": "keyword"},
                "document_unit_id": {"type": "long"},
                "unit_type": {"type": "keyword"},
                "page": {"type": "integer"},
                "sheet": {"type": "keyword", "ignore_above": 512},
                "section": {"type": "keyword", "ignore_above": 512},
                "page_label": {
                    "type": "text",
                    "fields": {"keyword": {"type": "keyword", "ignore_above": 256}},
                },
                "image_path": {"type": "keyword", "ignore_above": 512},
                "render_source": {"type": "keyword"},
                "render_version": {"type": "keyword"},
                "quality_status": {"type": "keyword"},
                "provider": {"type": "keyword"},
                "model_name": {"type": "keyword"},
                "embedding_backend": {"type": "keyword"},
                "embedding_status": {"type": "keyword"},
                "embedding_error": {"type": "text"},
                "indexed_at": {"type": "date"},
                "org_tag": {"type": "keyword"},
                "kb_profile": {"type": "keyword"},
                "is_public": {"type": "boolean"},
                "user_id": {"type": "long"},
                "visual_vector": {
                    "type": "dense_vector",
                    "dims": VisualSearchService.VECTOR_DIMENSIONS,
                    "index": True,
                    "similarity": "cosine",
                },
            }
        }

    @staticmethod
    def get_index_settings() -> Dict[str, Any]:
        return {
            "number_of_shards": 1,
            "number_of_replicas": 0,
        }

    @staticmethod
    async def ensure_index_exists() -> bool:
        try:
            exists = await es_client.index_exists(VisualSearchService.INDEX_NAME)
            if exists:
                return True
            success = await es_client.create_index(
                index=VisualSearchService.INDEX_NAME,
                mappings=VisualSearchService.get_index_mappings(),
                settings=VisualSearchService.get_index_settings(),
            )
            if success:
                logger.info("视觉索引已创建: %s", VisualSearchService.INDEX_NAME)
            return success
        except Exception as e:
            logger.error("确保视觉索引存在失败: %s", e, exc_info=True)
            return False

    @staticmethod
    async def rebuild_for_file(
        db: AsyncSession,
        file_md5: str,
        user_id: int,
        org_tag: str,
        kb_profile: str,
        is_public: bool,
    ) -> Dict[str, Any]:
        stats = {
            "pages": 0,
            "indexed": 0,
            "es_docs": 0,
            "pending": 0,
            "errors": 0,
        }

        pages = (
            await db.execute(
                select(VisualPage)
                .where(VisualPage.file_md5 == file_md5)
                .order_by(VisualPage.id.asc())
            )
        ).scalars().all()
        stats["pages"] = len(pages)
        if not pages:
            return stats

        await db.execute(VisualPageEmbedding.__table__.delete().where(VisualPageEmbedding.file_md5 == file_md5))
        await es_client.delete_by_query(
            index=VisualSearchService.INDEX_NAME,
            query={"term": {"file_md5": file_md5}},
        )

        await VisualSearchService.ensure_index_exists()

        docs: List[Dict[str, Any]] = []
        rows: List[VisualPageEmbedding] = []
        for page in pages:
            contextual_text = page.page_label or page.sheet or page.section or page.unit_type
            result = await visual_embedding_service.embed_image(
                page.image_path,
                contextual_text=contextual_text,
            )
            es_doc_id = f"visual_{page.id}"
            indexed_at = datetime.utcnow()
            doc_source = {
                "visual_page_id": page.id,
                "file_md5": page.file_md5,
                "document_unit_id": page.document_unit_id,
                "unit_type": page.unit_type,
                "page": page.page,
                "sheet": page.sheet,
                "section": page.section,
                "page_label": page.page_label,
                "image_path": page.image_path,
                "render_source": page.render_source,
                "render_version": page.render_version,
                "quality_status": page.quality_status,
                "provider": result.provider or visual_embedding_service.provider,
                "model_name": result.model_name or visual_embedding_service.model_name,
                "embedding_backend": result.backend or visual_embedding_service.backend,
                "embedding_status": result.status,
                "embedding_error": result.error_message,
                "indexed_at": indexed_at.isoformat(),
                "org_tag": org_tag,
                "kb_profile": kb_profile,
                "is_public": bool(is_public),
                "user_id": user_id,
            }
            if result.vector:
                doc_source["visual_vector"] = result.vector
                stats["indexed"] += 1
            elif result.status in {"pending_config", "pending_provider", "skipped"}:
                stats["pending"] += 1
            else:
                stats["errors"] += 1
            docs.append(
                {
                    "_id": es_doc_id,
                    "_source": doc_source,
                }
            )
            stats["es_docs"] += 1

            rows.append(
                VisualPageEmbedding(
                    file_md5=file_md5,
                    visual_page_id=page.id,
                    provider=result.provider or visual_embedding_service.provider,
                    model_name=result.model_name or visual_embedding_service.model_name,
                    embedding_dim=result.embedding_dim if result.vector else None,
                    status=result.status,
                    es_doc_id=es_doc_id,
                    error_message=result.error_message,
                    indexed_at=indexed_at,
                )
            )

        for row in rows:
            db.add(row)

        if docs:
            for doc in docs:
                ok = await es_client.index_document(
                    index=VisualSearchService.INDEX_NAME,
                    document=doc["_source"],
                    doc_id=doc["_id"],
                )
                if not ok:
                    raise RuntimeError(
                        f"视觉索引文档写入失败: file_md5={file_md5}, doc_id={doc['_id']}"
                    )
            await es_client.refresh_index(VisualSearchService.INDEX_NAME)

        logger.info(
            "视觉索引构建完成: file_md5=%s, pages=%s, es_docs=%s, indexed=%s, pending=%s, errors=%s",
            file_md5,
            stats["pages"],
            stats["es_docs"],
            stats["indexed"],
            stats["pending"],
            stats["errors"],
        )
        return stats

    @staticmethod
    async def search_visual_pages(
        db: AsyncSession,
        user: User,
        query_text: str,
        top_k: int = 8,
        selected_profile: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        cleaned_query = str(query_text or "").strip()
        if not cleaned_query:
            return []

        if not await VisualSearchService.ensure_index_exists():
            return []

        query_embedding = await visual_embedding_service.embed_query_text(cleaned_query)
        if not query_embedding.vector:
            logger.info(
                "视觉检索跳过: query='%s', status=%s, error=%s",
                cleaned_query[:120],
                query_embedding.status,
                query_embedding.error_message,
            )
            return []

        if user.role == UserRole.ADMIN:
            permission_filters: List[Dict[str, Any]] = []
        else:
            accessible_tags = await permission_service.get_user_accessible_tags(db, user)
            permission_filters = permission_service.build_elasticsearch_permission_filters(
                user_id=int(user.id),
                accessible_tags=accessible_tags,
            )

        filter_clauses: List[Dict[str, Any]] = [
            {"term": {"embedding_status": "indexed"}},
            {"terms": {"quality_status": ["accepted", "weak"]}},
        ]
        if selected_profile:
            filter_clauses.append({"term": {"kb_profile": selected_profile}})
        if permission_filters:
            filter_clauses.append(
                permission_filters[0]
                if len(permission_filters) == 1
                else {
                    "bool": {
                        "should": permission_filters,
                        "minimum_should_match": 1,
                    }
                }
            )

        should_clauses: List[Dict[str, Any]] = [
            {
                "script_score": {
                    "query": {"match_all": {}},
                    "script": {
                        "source": "cosineSimilarity(params.query_vector, 'visual_vector') + 1.0",
                        "params": {"query_vector": query_embedding.vector},
                    },
                }
            },
            {"match": {"page_label": {"query": cleaned_query, "boost": 0.35}}},
            {"match": {"sheet": {"query": cleaned_query, "boost": 0.30}}},
            {"match": {"section": {"query": cleaned_query, "boost": 0.20}}},
        ]

        query = {
            "bool": {
                "filter": filter_clauses,
                "should": should_clauses,
                "minimum_should_match": 1,
            }
        }

        raw = await es_client.search(
            index=VisualSearchService.INDEX_NAME,
            query=query,
            size=max(top_k * 3, 12),
        )
        hits = (raw or {}).get("hits", {}).get("hits", [])
        if not hits:
            return []

        sources = [hit.get("_source") or {} for hit in hits]
        file_md5s = sorted({str(src.get("file_md5") or "") for src in sources if src.get("file_md5")})
        unit_ids = sorted({int(src.get("document_unit_id")) for src in sources if src.get("document_unit_id") is not None})

        file_rows = (
            await db.execute(select(FileUpload).where(FileUpload.file_md5.in_(file_md5s)))
        ).scalars().all() if file_md5s else []
        file_map = {row.file_md5: row for row in file_rows}

        unit_rows = (
            await db.execute(select(DocumentUnit).where(DocumentUnit.id.in_(unit_ids)))
        ).scalars().all() if unit_ids else []
        unit_map = {int(row.id): row for row in unit_rows}

        unit_pairs = {
            (row.file_md5, row.unit_key)
            for row in unit_rows
            if row.file_md5 and row.unit_key
        }
        parent_rows = (
            await db.execute(
                select(ParentChunk)
                .where(
                    or_(*[
                        and_(
                            ParentChunk.file_md5 == file_md5,
                            ParentChunk.document_unit_key == unit_key,
                        )
                        for file_md5, unit_key in unit_pairs
                    ])
                )
                .where(ParentChunk.quality_status.in_(["accepted", "weak"]))
                .order_by(ParentChunk.quality_score.desc(), ParentChunk.parent_chunk_id.asc())
            )
        ).scalars().all() if unit_pairs else []
        parent_map: Dict[tuple[str, str], ParentChunk] = {}
        for row in parent_rows:
            key = (str(row.file_md5 or ""), str(row.document_unit_key or ""))
            if key not in parent_map:
                parent_map[key] = row

        results: List[Dict[str, Any]] = []
        for rank, hit in enumerate(hits, 1):
            source = hit.get("_source") or {}
            file_md5 = str(source.get("file_md5") or "")
            unit_id = source.get("document_unit_id")
            unit = unit_map.get(int(unit_id)) if unit_id is not None else None
            file_row = file_map.get(file_md5)
            parent_row = None
            if unit and unit.unit_key:
                parent_row = parent_map.get((file_md5, unit.unit_key))

            page_label = str(source.get("page_label") or "")
            text_content = ""
            if parent_row and parent_row.text_content:
                text_content = str(parent_row.text_content)
            else:
                parts = ["[visual_page]"]
                if page_label:
                    parts.append(f"label={page_label}")
                if unit and unit.unit_name:
                    parts.append(f"name={unit.unit_name}")
                if source.get("sheet"):
                    parts.append(f"sheet={source.get('sheet')}")
                if source.get("page") is not None:
                    parts.append(f"page={source.get('page')}")
                text_content = " ".join(parts)

            score = float(hit.get("_score", 0.0) or 0.0)
            if selected_profile and source.get("kb_profile") == selected_profile:
                score += 0.08

            results.append(
                {
                    "file_md5": file_md5,
                    "chunk_id": -(int(source.get("visual_page_id") or rank)),
                    "text_content": text_content,
                    "score": round(score, 4),
                    "file_name": file_row.file_name if file_row else str(source.get("file_name") or "未知文件"),
                    "kb_profile": file_row.kb_profile if file_row else source.get("kb_profile"),
                    "page": source.get("page"),
                    "sheet": source.get("sheet"),
                    "chunk_type": "visual_page",
                    "source_type": "visual",
                    "image_path": source.get("image_path"),
                    "visual_page_id": source.get("visual_page_id"),
                    "document_unit_id": unit_id,
                    "page_label": page_label or (unit.unit_name if unit else ""),
                    "rank": rank,
                }
            )

        return results[: max(1, top_k)]


visual_search_service = VisualSearchService()
