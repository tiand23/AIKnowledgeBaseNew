"""
关系索引与流程检索服务

目标：
1) 针对“构成图/流程图”类文档，从解析文本块中抽取节点与关系边，写入 SQLite。
2) 对流程类问题优先执行关系检索，结果不足时由上层回退到向量检索。
"""
from __future__ import annotations

import re
from collections import deque
from typing import Any, Dict, List, Optional, Set, Tuple

from sqlalchemy import delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.file import FileUpload, RelationEdge, RelationNode
from app.models.user import User, UserRole
from app.services.permission_service import permission_service
from app.utils.logger import get_logger

logger = get_logger(__name__)


class RelationSearchService:

    DOC_HINTS = (
        "構成図", "システム図", "システム構成図", "構成", "アーキテクチャ", "architecture", "flow", "フロー",
        "流程", "流程图", "架构图", "系统构成"
    )

    RELATION_KEYWORDS: Dict[str, Tuple[str, ...]] = {
        "输入": ("输入", "入力", "ingest", "input"),
        "输出": ("输出", "出力", "output"),
        "调用": ("调用", "呼び出", "call", "invoke", "mcp経由"),
        "依赖": ("依赖", "依存", "depends", "連携"),
        "获取": ("取得", "获取", "fetch", "read"),
        "反映": ("反映", "同期"),
        "连接": ("接続", "连接", "connect"),
    }

    RELATION_QUERY_HINTS = (
        "流程", "路径", "链路", "上游", "下游", "依赖", "经过",
        "flow", "route", "path", "from", "to", "→", "->",
        "順序", "経路", "入力", "出力", "連携", "呼び出し",
        "構成図", "システム図", "システム構成図", "構成", "アーキテクチャ"
    )

    STOP_TERMS = {
        "请", "帮我", "说明", "解释", "是什么", "怎么", "如何", "一下",
        "流程", "路径", "链路", "上游", "下游", "依赖", "关系",
        "構成図", "システム図", "システム構成図", "構成", "アーキテクチャ",
        "教えて", "ください", "ですか", "について",
        "from", "to", "flow", "path", "route", "and", "or", "the", "a", "an",
    }

    ARROW_RE = re.compile(
        r"(?P<src>[A-Za-z0-9_\-\(\)（）/\u3040-\u30ff\u3400-\u9fff・\s]{2,80})\s*"
        r"(?:->|→|⇒|⇢|＞)\s*"
        r"(?P<dst>[A-Za-z0-9_\-\(\)（）/\u3040-\u30ff\u3400-\u9fff・\s]{2,80})"
    )

    @staticmethod
    def is_relation_query(query: str) -> bool:
        text = (query or "").lower()
        if not text:
            return False
        return any(h.lower() in text for h in RelationSearchService.RELATION_QUERY_HINTS)

    @staticmethod
    def should_build_relation_index(file_name: str, blocks: List[Dict[str, Any]]) -> bool:
        name = (file_name or "").lower()
        if any(h.lower() in name for h in RelationSearchService.DOC_HINTS):
            return True

        for block in blocks or []:
            if str(block.get("type") or "") in ("diagram_edge", "diagram_node", "diagram_page"):
                return True
            if str(block.get("source_parser") or "") == "xlsx_diagram":
                return True

        signals = 0
        short_lines = 0
        total_lines = 0
        relation_token_hits = 0
        arrow_hits = 0

        for block in blocks:
            text = str(block.get("text") or "")
            if not text:
                continue
            lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
            for ln in lines:
                total_lines += 1
                if 1 <= len(ln) <= 28:
                    short_lines += 1
                if any(tok in ln.lower() for tok in ("->", "→", "⇒", "⇢")):
                    arrow_hits += 1

                lower_ln = ln.lower()
                if any(
                    kw.lower() in lower_ln
                    for kws in RelationSearchService.RELATION_KEYWORDS.values()
                    for kw in kws
                ):
                    relation_token_hits += 1

        if total_lines > 0 and short_lines / total_lines > 0.35:
            signals += 1
        if relation_token_hits >= 3:
            signals += 1
        if arrow_hits >= 1:
            signals += 1
        return signals >= 2

    @staticmethod
    def _normalize_node_key(name: str) -> str:
        return re.sub(r"\s+", "", (name or "").strip().lower())

    @staticmethod
    def _clean_line(line: str) -> str:
        text = re.sub(r"\s+", " ", (line or "").strip())
        return text.strip("[]()（）")

    @staticmethod
    def _is_likely_node(line: str) -> bool:
        text = RelationSearchService._clean_line(line)
        if not text:
            return False
        if len(text) < 2 or len(text) > 80:
            return False
        if re.fullmatch(r"[0-9０-９一二三四五六七八九十]+", text):
            return False
        if any(kw in text.lower() for kw in ("http://", "https://", "www.")):
            return False

        has_word = re.search(r"[A-Za-z\u3040-\u30ff\u3400-\u9fff]", text) is not None
        if not has_word:
            return False

        if RelationSearchService._detect_relation_type(text):
            return False
        return True

    @staticmethod
    def _detect_relation_type(line: str) -> Optional[str]:
        lower_ln = (line or "").lower()
        for rel_type, kws in RelationSearchService.RELATION_KEYWORDS.items():
            if any(kw.lower() in lower_ln for kw in kws):
                return rel_type
        if any(tok in lower_ln for tok in ("->", "→", "⇒", "⇢")):
            return "连接"
        return None

    @staticmethod
    def _collect_lines(blocks: List[Dict[str, Any]]) -> List[Tuple[int, str]]:
        """
        将 blocks 展平为 (page, line) 列表，保留顺序。
        page 不存在时记为 0。
        """
        diagram_blocks = [
            b for b in (blocks or [])
            if str(b.get("type") or "") in {"diagram_node", "diagram_edge", "diagram_summary"}
            or str(b.get("source_parser") or "") in {"xlsx_diagram", "vlm_diagram"}
        ]
        target_blocks = diagram_blocks if diagram_blocks else (blocks or [])

        rows: List[Tuple[int, str]] = []
        for block in target_blocks:
            page = int(block.get("page") or 0)
            text = str(block.get("text") or "")
            if not text:
                continue
            for raw_line in text.splitlines():
                line = (raw_line or "").strip()
                if not line:
                    continue
                if line.startswith("[diagram_node]"):
                    line = line.replace("[diagram_node]", "", 1).strip()
                elif line.startswith("[diagram_edge]"):
                    line = line.replace("[diagram_edge]", "", 1).strip()
                elif line.startswith("[diagram_summary]"):
                    line = line.replace("[diagram_summary]", "", 1).strip()
                line = re.sub(r"^(diagram_node|diagram_edge|diagram_summary)\]\s*", "", line, flags=re.IGNORECASE)
                line = RelationSearchService._clean_line(line)
                if line:
                    rows.append((page, line))
        return rows

    @staticmethod
    def _extract_edges_from_lines(lines: List[Tuple[int, str]]) -> List[Dict[str, Any]]:
        """
        从文本行抽取边：
        1) 直接箭头语法 A -> B。
        2) 关系词行：在邻近窗口中寻找前后节点。
        """
        edges: List[Dict[str, Any]] = []

        node_candidates: List[Tuple[int, int, str]] = []
        for idx, (page, line) in enumerate(lines):
            if RelationSearchService._is_likely_node(line):
                node_candidates.append((idx, page, line))

        explicit_arrow_hits = 0
        for idx, (page, line) in enumerate(lines):
            m = RelationSearchService.ARROW_RE.search(line)
            if not m:
                continue
            explicit_arrow_hits += 1
            src = RelationSearchService._clean_line(m.group("src"))
            dst = RelationSearchService._clean_line(m.group("dst"))
            if not RelationSearchService._is_likely_node(src) or not RelationSearchService._is_likely_node(dst):
                continue
            edges.append(
                {
                    "src": src,
                    "dst": dst,
                    "relation_type": RelationSearchService._detect_relation_type(line) or "连接",
                    "relation_text": line[:255],
                    "page": page,
                    "evidence_text": line,
                }
            )

        if explicit_arrow_hits >= 2:
            uniq: Dict[Tuple[str, str, str, int], Dict[str, Any]] = {}
            for edge in edges:
                key = (
                    RelationSearchService._normalize_node_key(edge["src"]),
                    RelationSearchService._normalize_node_key(edge["dst"]),
                    edge["relation_type"],
                    int(edge.get("page") or 0),
                )
                if key not in uniq:
                    uniq[key] = edge
            return list(uniq.values())

        for idx, (page, line) in enumerate(lines):
            rel_type = RelationSearchService._detect_relation_type(line)
            if not rel_type:
                continue
            if RelationSearchService.ARROW_RE.search(line):
                continue

            prev_node: Optional[str] = None
            next_node: Optional[str] = None

            for c_idx, _c_page, c_name in reversed(node_candidates):
                if c_idx >= idx:
                    continue
                if idx - c_idx > 6:
                    break
                prev_node = c_name
                break

            for c_idx, _c_page, c_name in node_candidates:
                if c_idx <= idx:
                    continue
                if c_idx - idx > 6:
                    break
                next_node = c_name
                break

            if prev_node and next_node and prev_node != next_node:
                edges.append(
                    {
                        "src": prev_node,
                        "dst": next_node,
                        "relation_type": rel_type,
                        "relation_text": line[:255],
                        "page": page,
                        "evidence_text": line,
                    }
                )

        uniq: Dict[Tuple[str, str, str, int], Dict[str, Any]] = {}
        for edge in edges:
            key = (
                RelationSearchService._normalize_node_key(edge["src"]),
                RelationSearchService._normalize_node_key(edge["dst"]),
                edge["relation_type"],
                int(edge.get("page") or 0),
            )
            if key not in uniq:
                uniq[key] = edge
        return list(uniq.values())

    @staticmethod
    async def build_relation_index(
        db: AsyncSession,
        file_md5: str,
        file_name: str,
        blocks: List[Dict[str, Any]],
    ) -> Dict[str, int]:
        """
        为文档构建关系索引（先清后建）。
        """
        lines = RelationSearchService._collect_lines(blocks)
        edges_raw = RelationSearchService._extract_edges_from_lines(lines)
        if not edges_raw:
            await db.execute(delete(RelationEdge).where(RelationEdge.file_md5 == file_md5))
            await db.execute(delete(RelationNode).where(RelationNode.file_md5 == file_md5))
            await db.flush()
            logger.info(f"关系索引为空（无可抽取边）: file={file_name}, file_md5={file_md5}")
            return {"nodes": 0, "edges": 0}

        await db.execute(delete(RelationEdge).where(RelationEdge.file_md5 == file_md5))
        await db.execute(delete(RelationNode).where(RelationNode.file_md5 == file_md5))
        await db.flush()

        node_map: Dict[str, RelationNode] = {}
        for edge in edges_raw:
            for node_name in (edge["src"], edge["dst"]):
                key = RelationSearchService._normalize_node_key(node_name)
                if not key:
                    continue
                if key not in node_map:
                    node_map[key] = RelationNode(
                        file_md5=file_md5,
                        node_key=key,
                        node_name=node_name[:255],
                        node_type="component",
                        page=int(edge.get("page") or 0) or None,
                        evidence_text=edge.get("evidence_text"),
                    )

        db.add_all(node_map.values())
        await db.flush()

        edge_models: List[RelationEdge] = []
        for edge in edges_raw:
            src_key = RelationSearchService._normalize_node_key(edge["src"])
            dst_key = RelationSearchService._normalize_node_key(edge["dst"])
            src_node = node_map.get(src_key)
            dst_node = node_map.get(dst_key)
            if not src_node or not dst_node:
                continue
            edge_models.append(
                RelationEdge(
                    file_md5=file_md5,
                    src_node_id=src_node.id,
                    dst_node_id=dst_node.id,
                    relation_type=edge["relation_type"][:64],
                    relation_text=(edge.get("relation_text") or "")[:255],
                    page=int(edge.get("page") or 0) or None,
                    evidence_text=edge.get("evidence_text"),
                )
            )

        if edge_models:
            db.add_all(edge_models)
            await db.flush()

        logger.info(
            f"关系索引构建完成: file={file_name}, file_md5={file_md5}, nodes={len(node_map)}, edges={len(edge_models)}"
        )
        return {"nodes": len(node_map), "edges": len(edge_models)}

    @staticmethod
    async def _get_accessible_file_md5_set(
        db: AsyncSession,
        user: User,
        kb_profile: Optional[str] = None,
    ) -> Set[str]:
        if user.role == UserRole.ADMIN:
            stmt = select(FileUpload.file_md5)
            if kb_profile:
                stmt = stmt.where(FileUpload.kb_profile == kb_profile)
            rows = await db.execute(stmt)
            return {x[0] for x in rows.all() if x and x[0]}

        accessible_tags = await permission_service.get_user_accessible_tags(db, user)
        conditions = permission_service.build_db_file_access_conditions(
            user=user,
            accessible_tags=accessible_tags,
        )

        stmt = select(FileUpload.file_md5).where(or_(*conditions))
        if kb_profile:
            stmt = stmt.where(FileUpload.kb_profile == kb_profile)
        rows = await db.execute(stmt)
        return {x[0] for x in rows.all() if x and x[0]}

    @staticmethod
    def _extract_query_terms(query: str) -> List[str]:
        raw_terms = re.split(r"[\s,，。！？\(\)（）\[\]【】\-_/\\:：;；]+", query or "")
        terms: List[str] = []
        for term in raw_terms:
            t = term.strip().lower()
            if not t:
                continue
            if t in RelationSearchService.STOP_TERMS:
                continue
            if any(h.lower() == t for h in RelationSearchService.RELATION_QUERY_HINTS):
                continue
            if len(t) == 1 and re.fullmatch(r"[a-z0-9]", t):
                continue
            terms.append(t)
        return terms

    @staticmethod
    def _bfs_find_path(
        start_id: int,
        target_id: int,
        adj: Dict[int, List[Tuple[int, RelationEdge]]],
        max_depth: int = 6,
    ) -> List[RelationEdge]:
        queue: deque[Tuple[int, List[RelationEdge]]] = deque()
        queue.append((start_id, []))
        visited = {start_id}

        while queue:
            node_id, path = queue.popleft()
            if len(path) >= max_depth:
                continue
            for nxt_id, edge in adj.get(node_id, []):
                if nxt_id in visited:
                    continue
                new_path = path + [edge]
                if nxt_id == target_id:
                    return new_path
                visited.add(nxt_id)
                queue.append((nxt_id, new_path))
        return []

    @staticmethod
    async def search_relations(
        db: AsyncSession,
        user: User,
        query_text: str,
        top_k: int = 6,
        kb_profile: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        流程类检索：
        - 优先尝试路径查询（至少识别到 2 个节点）
        - 次选单节点上下游
        - 再次选关系类型匹配
        """
        accessible_file_md5s = await RelationSearchService._get_accessible_file_md5_set(
            db,
            user,
            kb_profile=kb_profile,
        )
        if not accessible_file_md5s:
            return []

        terms = RelationSearchService._extract_query_terms(query_text)
        node_candidates: List[RelationNode] = []
        if terms:
            like_conditions = [RelationNode.node_name.ilike(f"%{t}%") for t in terms[:6]]
            node_rows = await db.execute(
                select(RelationNode).where(
                    RelationNode.file_md5.in_(accessible_file_md5s),
                    or_(*like_conditions),
                )
            )
            node_candidates = node_rows.scalars().all()

        file_rows = await db.execute(
            select(FileUpload.file_md5, FileUpload.file_name).where(FileUpload.file_md5.in_(accessible_file_md5s))
        )
        file_name_map = {row[0]: row[1] for row in file_rows.all()}

        by_file: Dict[str, List[RelationNode]] = {}
        for node in node_candidates:
            by_file.setdefault(node.file_md5, []).append(node)

        path_results: List[Dict[str, Any]] = []
        for file_md5, nodes in by_file.items():
            if len(nodes) < 2:
                continue
            edges_rows = await db.execute(select(RelationEdge).where(RelationEdge.file_md5 == file_md5))
            edges = edges_rows.scalars().all()
            if not edges:
                continue

            adj: Dict[int, List[Tuple[int, RelationEdge]]] = {}
            for edge in edges:
                adj.setdefault(edge.src_node_id, []).append((edge.dst_node_id, edge))

            node_name_map = {n.id: n.node_name for n in nodes}
            node_ids = set(node_name_map.keys())
            for edge in edges:
                if edge.src_node_id not in node_ids or edge.dst_node_id not in node_ids:
                    if edge.src_node_id not in node_name_map or edge.dst_node_id not in node_name_map:
                        pass
            if edges:
                ids_to_fill = {e.src_node_id for e in edges}.union({e.dst_node_id for e in edges})
                missing_ids = [nid for nid in ids_to_fill if nid not in node_name_map]
                if missing_ids:
                    node_rows = await db.execute(select(RelationNode.id, RelationNode.node_name).where(RelationNode.id.in_(missing_ids)))
                    for row in node_rows.all():
                        node_name_map[row[0]] = row[1]

            for i in range(len(nodes)):
                for j in range(i + 1, len(nodes)):
                    path = RelationSearchService._bfs_find_path(nodes[i].id, nodes[j].id, adj)
                    if not path:
                        path = RelationSearchService._bfs_find_path(nodes[j].id, nodes[i].id, adj)
                    if not path:
                        continue
                    chain = []
                    for e in path:
                        src_name = node_name_map.get(e.src_node_id, str(e.src_node_id))
                        dst_name = node_name_map.get(e.dst_node_id, str(e.dst_node_id))
                        chain.append(f"{src_name} --{e.relation_type}--> {dst_name}")
                    text = " ; ".join(chain)
                    path_results.append(
                        {
                            "file_md5": file_md5,
                            "chunk_id": path[0].id,
                            "text_content": f"[流程路径] {text}",
                            "score": round(2.0 + 1.0 / (len(path) + 1), 4),
                            "file_name": file_name_map.get(file_md5, "未知文件"),
                        }
                    )
                    if len(path_results) >= top_k:
                        return path_results

        if path_results:
            return path_results[:top_k]

        if node_candidates:
            node = node_candidates[0]
            edge_rows = await db.execute(
                select(RelationEdge).where(
                    RelationEdge.file_md5 == node.file_md5,
                    or_(RelationEdge.src_node_id == node.id, RelationEdge.dst_node_id == node.id),
                )
            )
            edges = edge_rows.scalars().all()
            if edges:
                node_rows = await db.execute(
                    select(RelationNode.id, RelationNode.node_name).where(
                        RelationNode.file_md5 == node.file_md5,
                        RelationNode.id.in_({e.src_node_id for e in edges}.union({e.dst_node_id for e in edges}))
                    )
                )
                node_name_map = {row[0]: row[1] for row in node_rows.all()}
                results: List[Dict[str, Any]] = []
                for edge in edges[:top_k]:
                    src_name = node_name_map.get(edge.src_node_id, str(edge.src_node_id))
                    dst_name = node_name_map.get(edge.dst_node_id, str(edge.dst_node_id))
                    results.append(
                        {
                            "file_md5": edge.file_md5,
                            "chunk_id": edge.id,
                            "text_content": f"[关系] {src_name} --{edge.relation_type}--> {dst_name}",
                            "score": 1.6,
                            "file_name": file_name_map.get(edge.file_md5, "未知文件"),
                        }
                    )
                return results

        rel_type_hit = RelationSearchService._detect_relation_type(query_text)
        if rel_type_hit:
            rows = await db.execute(
                select(RelationEdge).where(
                    RelationEdge.file_md5.in_(accessible_file_md5s),
                    RelationEdge.relation_type == rel_type_hit,
                )
            )
            edges = rows.scalars().all()
            node_rows = await db.execute(
                select(RelationNode.id, RelationNode.node_name).where(
                    RelationNode.id.in_({e.src_node_id for e in edges}.union({e.dst_node_id for e in edges}))
                )
            )
            node_name_map = {row[0]: row[1] for row in node_rows.all()}
            results: List[Dict[str, Any]] = []
            for edge in edges[:top_k]:
                src_name = node_name_map.get(edge.src_node_id, str(edge.src_node_id))
                dst_name = node_name_map.get(edge.dst_node_id, str(edge.dst_node_id))
                results.append(
                    {
                        "file_md5": edge.file_md5,
                        "chunk_id": edge.id,
                        "text_content": f"[关系] {src_name} --{edge.relation_type}--> {dst_name}",
                        "score": 1.3,
                        "file_name": file_name_map.get(edge.file_md5, "未知文件"),
                    }
                )
            if results:
                return results

        if RelationSearchService.is_relation_query(query_text):
            query_terms = RelationSearchService._extract_query_terms(query_text)
            if not query_terms:
                logger.info("关系兜底跳过：query_terms为空，避免返回泛化边。query=%s", (query_text or "")[:80])
                return []
            edge_rows = await db.execute(
                select(RelationEdge).where(RelationEdge.file_md5.in_(accessible_file_md5s))
            )
            edges = edge_rows.scalars().all()
            if edges:
                edges = sorted(edges, key=lambda e: (int(e.page or 0), int(e.id or 0)), reverse=True)
                node_ids = {e.src_node_id for e in edges[: max(top_k * 3, 20)]}.union(
                    {e.dst_node_id for e in edges[: max(top_k * 3, 20)]}
                )
                node_rows = await db.execute(
                    select(RelationNode.id, RelationNode.node_name).where(RelationNode.id.in_(node_ids))
                )
                node_name_map = {row[0]: row[1] for row in node_rows.all()}
                results: List[Dict[str, Any]] = []
                seen = set()
                for edge in edges:
                    src_name = node_name_map.get(edge.src_node_id, str(edge.src_node_id))
                    dst_name = node_name_map.get(edge.dst_node_id, str(edge.dst_node_id))
                    evidence = f"{src_name} {edge.relation_type} {dst_name} {file_name_map.get(edge.file_md5, '')}".lower()
                    matched_terms = sum(1 for t in query_terms if t and t in evidence)
                    if matched_terms <= 0:
                        continue
                    dedup_key = (
                        edge.file_md5,
                        RelationSearchService._normalize_node_key(src_name),
                        RelationSearchService._normalize_node_key(dst_name),
                        edge.relation_type,
                    )
                    if dedup_key in seen:
                        continue
                    seen.add(dedup_key)
                    results.append(
                        {
                            "file_md5": edge.file_md5,
                            "chunk_id": edge.id,
                            "text_content": f"[关系] {src_name} --{edge.relation_type}--> {dst_name}",
                            "score": round(1.0 + 0.04 * matched_terms, 4),
                            "file_name": file_name_map.get(edge.file_md5, "未知文件"),
                        }
                    )
                    if len(results) >= top_k:
                        break
                if results:
                    return results

        return []


relation_search_service = RelationSearchService()
