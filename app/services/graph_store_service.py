"""
Graph store abstraction.

Phase 3 currently introduces the AGE-facing schema contract and startup checks
without changing the existing relation table query path. The current runtime
can keep using relation_nodes/relation_edges while we prepare PostgreSQL + AGE
as the long-term graph backend.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
import re
from typing import Dict, List, Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class GraphSchemaSummary:
    backend: str
    graph_name: str
    enabled: bool
    node_labels: List[str]
    edge_labels: List[str]


@dataclass(frozen=True)
class GraphNodeFact:
    file_md5: str
    node_key: str
    node_name: str
    node_type: Optional[str] = None
    page: Optional[int] = None
    evidence_text: Optional[str] = None
    document_unit_id: Optional[int] = None
    visual_page_id: Optional[int] = None
    source_provider: Optional[str] = None
    source_parser: Optional[str] = None
    quality_status: str = "accepted"


@dataclass(frozen=True)
class GraphEdgeFact:
    file_md5: str
    src_node_key: str
    dst_node_key: str
    relation_type: str
    relation_text: Optional[str] = None
    page: Optional[int] = None
    evidence_text: Optional[str] = None
    document_unit_id: Optional[int] = None
    visual_page_id: Optional[int] = None
    source_provider: Optional[str] = None
    source_parser: Optional[str] = None
    quality_status: str = "accepted"


class GraphStoreService:
    """
    Minimal AGE scaffold.

    Design intent:
    1. The current system continues to use PostgreSQL relation tables for query.
    2. AGE becomes the target graph backend when enabled by configuration.
    3. Startup only checks/initializes AGE; it does not rewrite existing graph logic.
    """

    NODE_LABELS = (
        "Page",
        "Component",
        "FlowNode",
        "Task",
        "Entity",
    )

    EDGE_LABELS = (
        "NAVIGATES_TO",
        "CONTAINS",
        "TRIGGERS",
        "DEPENDS_ON",
        "FLOWS_TO",
        "BELONGS_TO",
    )

    NODE_TYPE_TO_LABEL = {
        "page": "Page",
        "component": "Component",
        "flow_node": "FlowNode",
        "task": "Task",
        "entity": "Entity",
    }

    EDGE_TYPE_TO_LABEL = {
        "连接": "FLOWS_TO",
        "输入": "TRIGGERS",
        "输出": "BELONGS_TO",
        "调用": "TRIGGERS",
        "依赖": "DEPENDS_ON",
        "获取": "DEPENDS_ON",
        "反映": "FLOWS_TO",
        "接続": "NAVIGATES_TO",
    }

    @property
    def backend(self) -> str:
        return str(getattr(settings, "GRAPH_BACKEND", "postgres_relational") or "postgres_relational").strip()

    @property
    def graph_name(self) -> str:
        return str(getattr(settings, "POSTGRES_AGE_GRAPH_NAME", "knowledge_graph") or "knowledge_graph").strip()

    def is_age_target(self) -> bool:
        return self.backend == "postgres_age"

    def is_age_enabled(self) -> bool:
        db_dialect = str(getattr(settings, "DB_DIALECT", "") or "").lower().strip()
        return self.is_age_target() and bool(getattr(settings, "POSTGRES_AGE_ENABLED", False)) and db_dialect in {
            "postgresql",
            "postgres",
            "pg",
        }

    def get_schema_summary(self) -> GraphSchemaSummary:
        return GraphSchemaSummary(
            backend=self.backend,
            graph_name=self.graph_name,
            enabled=self.is_age_enabled(),
            node_labels=list(self.NODE_LABELS),
            edge_labels=list(self.EDGE_LABELS),
        )

    @staticmethod
    def _quote(value: object) -> str:
        return json.dumps(value, ensure_ascii=False)

    @staticmethod
    def _sanitize_label(label: str, fallback: str) -> str:
        candidate = re.sub(r"[^A-Za-z0-9_]", "_", (label or "").strip())
        if not candidate:
            return fallback
        if candidate[0].isdigit():
            candidate = f"_{candidate}"
        return candidate

    def _node_label(self, node_type: Optional[str]) -> str:
        mapped = self.NODE_TYPE_TO_LABEL.get(str(node_type or "").strip().lower(), "Entity")
        return self._sanitize_label(mapped, "Entity")

    def _edge_label(self, relation_type: Optional[str]) -> str:
        mapped = self.EDGE_TYPE_TO_LABEL.get(str(relation_type or "").strip(), "FLOWS_TO")
        return self._sanitize_label(mapped, "FLOWS_TO")

    async def _exec_cypher(self, db: AsyncSession, query: str) -> None:
        await db.execute(
            text("SELECT * FROM cypher(:graph_name, :query) as (result agtype)"),
            {"graph_name": self.graph_name, "query": query},
        )

    async def ensure_backend_ready(self, db: AsyncSession) -> Dict[str, object]:
        """
        Make AGE ready for later graph writes.

        This is intentionally lightweight:
        - if AGE is not enabled, return a skipped result
        - if AGE is enabled, ensure extension exists and graph name is registered
        """
        if not self.is_age_enabled():
            return {
                "status": "skipped",
                "backend": self.backend,
                "reason": "age_not_enabled",
                "graph_name": self.graph_name,
            }

        try:
            await db.execute(text("CREATE EXTENSION IF NOT EXISTS age"))
            await db.execute(text("LOAD 'age'"))
            await db.execute(text('SET search_path = ag_catalog, "$user", public'))

            exists = await db.execute(
                text("SELECT 1 FROM ag_catalog.ag_graph WHERE name = :graph_name LIMIT 1"),
                {"graph_name": self.graph_name},
            )
            if exists.scalar() is None:
                await db.execute(
                    text("SELECT create_graph(:graph_name)"),
                    {"graph_name": self.graph_name},
                )
                logger.info("AGE graph created: %s", self.graph_name)

            return {
                "status": "ready",
                "backend": self.backend,
                "graph_name": self.graph_name,
                "node_labels": list(self.NODE_LABELS),
                "edge_labels": list(self.EDGE_LABELS),
            }
        except Exception as e:
            logger.warning("AGE backend bootstrap skipped/failed: backend=%s graph=%s err=%s", self.backend, self.graph_name, e)
            return {
                "status": "error",
                "backend": self.backend,
                "graph_name": self.graph_name,
                "reason": str(e),
            }

    async def clear_file_graph(self, db: AsyncSession, file_md5: str) -> Dict[str, object]:
        if not self.is_age_enabled():
            return {
                "status": "skipped",
                "backend": self.backend,
                "reason": "age_not_enabled",
                "file_md5": file_md5,
            }

        try:
            await self._exec_cypher(
                db,
                f"""
                MATCH (n {{file_md5: {self._quote(file_md5)}}})
                DETACH DELETE n
                RETURN count(n)
                """.strip(),
            )
            return {
                "status": "cleared",
                "backend": self.backend,
                "graph_name": self.graph_name,
                "file_md5": file_md5,
            }
        except Exception as e:
            logger.warning("AGE clear file graph failed: file_md5=%s err=%s", file_md5, e)
            return {
                "status": "error",
                "backend": self.backend,
                "graph_name": self.graph_name,
                "file_md5": file_md5,
                "reason": str(e),
            }

    async def sync_relation_facts(
        self,
        db: AsyncSession,
        file_md5: str,
        nodes: List[GraphNodeFact],
        edges: List[GraphEdgeFact],
    ) -> Dict[str, object]:
        if not self.is_age_enabled():
            return {
                "status": "skipped",
                "backend": self.backend,
                "reason": "age_not_enabled",
                "file_md5": file_md5,
                "nodes": len(nodes),
                "edges": len(edges),
            }

        summary: Dict[str, object] = {
            "status": "ready",
            "backend": self.backend,
            "graph_name": self.graph_name,
            "file_md5": file_md5,
            "nodes": 0,
            "edges": 0,
        }
        try:
            await self.clear_file_graph(db, file_md5)

            for node in nodes:
                label = self._node_label(node.node_type)
                cypher = f"""
                MERGE (n:{label} {{file_md5: {self._quote(node.file_md5)}, node_key: {self._quote(node.node_key)}}})
                SET n.node_name = {self._quote(node.node_name)},
                    n.node_type = {self._quote(node.node_type or "entity")},
                    n.page = {self._quote(node.page)},
                    n.evidence_text = {self._quote(node.evidence_text)},
                    n.document_unit_id = {self._quote(node.document_unit_id)},
                    n.visual_page_id = {self._quote(node.visual_page_id)},
                    n.source_provider = {self._quote(node.source_provider)},
                    n.source_parser = {self._quote(node.source_parser)},
                    n.quality_status = {self._quote(node.quality_status)}
                RETURN n
                """.strip()
                await self._exec_cypher(db, cypher)
                summary["nodes"] = int(summary["nodes"]) + 1

            for edge in edges:
                edge_label = self._edge_label(edge.relation_type)
                cypher = f"""
                MATCH (src {{file_md5: {self._quote(edge.file_md5)}, node_key: {self._quote(edge.src_node_key)}}})
                MATCH (dst {{file_md5: {self._quote(edge.file_md5)}, node_key: {self._quote(edge.dst_node_key)}}})
                MERGE (src)-[r:{edge_label} {{file_md5: {self._quote(edge.file_md5)}, edge_key: {self._quote(f"{edge.src_node_key}->{edge.relation_type}->{edge.dst_node_key}")}}}]->(dst)
                SET r.relation_type = {self._quote(edge.relation_type)},
                    r.relation_text = {self._quote(edge.relation_text)},
                    r.page = {self._quote(edge.page)},
                    r.evidence_text = {self._quote(edge.evidence_text)},
                    r.document_unit_id = {self._quote(edge.document_unit_id)},
                    r.visual_page_id = {self._quote(edge.visual_page_id)},
                    r.source_provider = {self._quote(edge.source_provider)},
                    r.source_parser = {self._quote(edge.source_parser)},
                    r.quality_status = {self._quote(edge.quality_status)}
                RETURN r
                """.strip()
                await self._exec_cypher(db, cypher)
                summary["edges"] = int(summary["edges"]) + 1

            return summary
        except Exception as e:
            logger.warning("AGE sync relation facts failed: file_md5=%s err=%s", file_md5, e, exc_info=True)
            return {
                "status": "error",
                "backend": self.backend,
                "graph_name": self.graph_name,
                "file_md5": file_md5,
                "nodes": int(summary["nodes"]),
                "edges": int(summary["edges"]),
                "reason": str(e),
            }


graph_store_service = GraphStoreService()
