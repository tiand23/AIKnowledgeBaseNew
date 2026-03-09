"""
聊天服务 - 整合知识检索和LLM生成回答
"""
import re
import json
import asyncio
import time
from typing import List, Dict, Optional, AsyncIterator, Any, Tuple, Callable, Awaitable
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_
from app.models.user import User
from app.models.user import UserRole
from app.models.file import TableRow, FileUpload, ChunkSource
from app.services.experience_service import experience_service
from app.services.intent_keywords import (
    get_flow_query_keys,
    get_layout_query_keys,
    get_relation_presentation_keys,
    get_strict_relation_keys,
    get_text_explanation_keys,
    get_visual_diagram_request_keys,
)
from app.services.intent_router_service import intent_router_service
from app.services.profile_service import profile_service
from app.services.search_service import search_service
from app.services.relation_search_service import relation_search_service
from app.services.prompt_service import prompt_service
from app.services.conversation_service import conversation_service
from app.services.query_understanding_service import query_understanding_service
from app.services.usage_event_service import usage_event_service
from app.services.langgraph_qa_orchestrator import LangGraphQAOrchestrator, QAState
from app.clients.openai_chat_client import openai_chat_client
from app.utils.logger import get_logger

logger = get_logger(__name__)


class ChatService:
    _MEMORY_WINDOW_TURNS = 4
    
    def __init__(self):
        self.search_service = search_service
        self.experience_service = experience_service
        self.intent_router_service = intent_router_service
        self.relation_search_service = relation_search_service
        self.prompt_service = prompt_service
        self.chat_client = openai_chat_client
        self.conversation_service = conversation_service
        self.query_understanding_service = query_understanding_service
    
    def _format_search_results(self, results: List[Dict]) -> tuple[str, List[Dict]]:
        """
        格式化检索结果为上下文和来源信息
        
        Args:
            results: 检索结果列表
            
        Returns:
            (context_str, sources_list): 上下文字符串和来源列表
        """
        if not results:
            return "関連する参照情報は見つかりませんでした。", []
        
        context_parts = []
        sources = []
        
        for i, result in enumerate(results, 1):
            text_content = result.get('text_content', '')
            if len(text_content) > 1400:
                text_content = text_content[:1400] + "..."
            
            context_parts.append(
                f"[文書{i}]\n"
                f"ファイル: {result.get('file_name', '不明なファイル')}\n"
                f"チャンク: {result.get('chunk_id', '-')}\n"
                f"ページ: {result.get('page', '-')}\n"
                f"シート: {result.get('sheet', '-')}\n"
                f"内容: {text_content}\n"
            )
            
            sources.append({
                "index": i,
                "file_name": result.get('file_name', '不明なファイル'),
                "file_md5": result.get('file_md5'),
                "chunk_id": result.get('chunk_id'),
                "page": result.get('page'),
                "sheet": result.get('sheet'),
                "score": result.get('score', 0.0)
            })
        
        context_str = "\n".join(context_parts)
        return context_str, sources

    async def _record_usage_event(
        self,
        db: AsyncSession,
        *,
        user: User,
        conversation_id: str,
        message: str,
        answer_text: str,
        intent: str,
        selected_profile: str,
        search_results: List[Dict[str, Any]],
        sources: List[Dict[str, Any]],
        status: str,
        started_at: float,
        error_type: str = "",
        error_message: str = "",
    ) -> None:
        latency_ms = max(0, int((time.perf_counter() - started_at) * 1000))
        await usage_event_service.record(
            db=db,
            user_id=int(user.id),
            conversation_id=conversation_id,
            question_text=message,
            answer_text=answer_text,
            intent=intent,
            selected_profile=selected_profile,
            retrieval_count=len(search_results or []),
            sources=sources,
            status=status,
            error_type=error_type or None,
            error_message=error_message or None,
            latency_ms=latency_ms,
        )

    @staticmethod
    def _profile_fusion_weights(selected_profile: str) -> Dict[str, float]:
        strategy = profile_service.get_strategy(selected_profile)
        hybrid_weight = max(
            0.0,
            float(strategy.retrieval_weight_vector) + float(strategy.retrieval_weight_bm25),
        )
        relation_weight = max(0.0, float(strategy.retrieval_weight_relation))
        total = hybrid_weight + relation_weight
        if total <= 0:
            return {"hybrid": 0.8, "relation": 0.2}
        return {"hybrid": hybrid_weight / total, "relation": relation_weight / total}

    @staticmethod
    def _relation_enabled_for_profile(selected_profile: str) -> bool:
        strategy = profile_service.get_strategy(selected_profile)
        return bool(strategy.enable_relation_index)

    @staticmethod
    def _profile_system_instruction(selected_profile: str) -> str:
        base = "あなたは社内ナレッジベースに接続されたアシスタントです。提供された根拠に基づいて日本語で回答してください。"
        if selected_profile == "design":
            return (
                base
                + " 回答はまず構成/関係/入出力を箇条書きで示し、その後に補足説明を短く記載してください。"
                + " 影響範囲質問では依存先・影響対象を明示してください。"
            )
        if selected_profile == "policy":
            return (
                base
                + " 回答は原文根拠を優先し、条項/適用範囲/例外/施行日を明確に分けて示してください。"
                + " 根拠不十分な場合は推測せず不足点を明示してください。"
            )
        if selected_profile == "ops":
            return (
                base
                + " 回答は『現象』『原因候補』『対応手順』『検証』『ロールバック』の順で整理してください。"
                + " 手順は番号付きで簡潔に示してください。"
            )
        return base

    @staticmethod
    def _enforce_answer_style(answer: str, selected_profile: str) -> str:
        text = (answer or "").strip()
        if not text:
            return text
        if selected_profile == "policy":
            must_headers = ("条項", "適用範囲", "例外", "施行日")
            if any(h in text for h in must_headers):
                return text
            return (
                "条項:\n"
                "- 根拠文書の該当箇所を確認してください。\n"
                "適用範囲:\n"
                "- 質問対象の範囲を明確化してください。\n"
                "例外:\n"
                "- 例外条件は根拠不足のため断定しません。\n"
                "施行日:\n"
                "- 施行日情報は根拠から確認してください。\n\n"
                f"{text}"
            )
        if selected_profile == "ops":
            must_headers = ("現象", "原因候補", "対応手順", "検証", "ロールバック")
            if any(h in text for h in must_headers):
                return text
            return (
                "現象:\n- 問い合わせ内容に基づく事象を確認。\n"
                "原因候補:\n- 根拠不足のため候補は限定。\n"
                "対応手順:\n1. 根拠文書の該当手順を確認\n"
                "2. 手順実施\n"
                "検証:\n- 期待結果を確認\n"
                "ロールバック:\n- 失敗時は事前状態へ戻す\n\n"
                f"{text}"
            )
        if selected_profile == "design":
            if "構成/連携関係" in text or "入出力" in text:
                return text
            return f"構成/連携関係:\n- 根拠に基づき要点を整理\n\n補足:\n{text}"
        return text

    @staticmethod
    def _build_audit_citation_block(sources: List[Dict], max_items: int = 5) -> str:
        """
        生成固定格式的可审计引用，避免只依赖 LLM 自由发挥的 [文書X]。
        """
        if not sources:
            return ""
        lines: List[str] = []
        seen = set()
        for s in sources:
            idx = s.get("index", "-")
            file_name = s.get("file_name", "不明なファイル")
            chunk_id = s.get("chunk_id", "-")
            file_md5 = s.get("file_md5", "")
            page = s.get("page")
            sheet = s.get("sheet")
            dedup_key = (str(file_md5), str(chunk_id or ""), str(page or ""), str(sheet or ""))
            if dedup_key in seen:
                continue
            seen.add(dedup_key)
            lines.append(
                f"[[SRC|{idx}|{file_name}|{file_md5}|{chunk_id}|{page if page is not None else ''}|{sheet if sheet else ''}]]"
            )
            if len(lines) >= max_items:
                break
        return ("\n" + "\n".join(lines) + "\n") if lines else ""

    def _append_audit_citations(self, answer: str, sources: List[Dict]) -> str:
        block = self._build_audit_citation_block(sources=sources)
        if not block:
            return answer
        base = (answer or "").rstrip()
        return f"{base}\n{block}\n"

    @staticmethod
    def _build_timeline_answer(results: List[Dict], top_n: int = 3) -> str:
        """
        为 timeline_query 生成确定性回答，避免 LLM 在有结构化结果时编造。
        仅使用 [时间线] 结构化结果字段。
        """
        timeline_rows = []
        for item in results:
            text = str(item.get("text_content") or "")
            if not text.startswith("[时间线]"):
                continue
            m = re.search(
                r"项目:\s*(?P<project>.*?)\s*;\s*期间:\s*(?P<period>.*?)\s*;\s*角色:\s*(?P<role>.*?)(?:\s*;\s*距今天约:\s*(?P<distance>\d+)\s*个月)?$",
                text,
            )
            if not m:
                continue
            timeline_rows.append(
                {
                    "project": (m.group("project") or "").strip(),
                    "period": (m.group("period") or "").strip(),
                    "role": (m.group("role") or "").strip(),
                    "distance": (m.group("distance") or "").strip(),
                    "file_name": str(item.get("file_name") or "不明なファイル"),
                }
            )

        if not timeline_rows:
            return "直近の案件情報は見つかりませんでした。"

        lines = [f"直近の{min(top_n, len(timeline_rows))}件は以下の通りです。"]
        for idx, row in enumerate(timeline_rows[:top_n], 1):
            source = f"[文書{idx}]"
            body = (
                f"{idx}. {row['project']}\n"
                f"   - 期間: {row['period']}\n"
                f"   - 役割: {row['role']}"
            )
            if row["distance"]:
                body += f"\n   - 現在から: 約{row['distance']}か月前"
            body += f"\n   - 根拠: {source} {row['file_name']}"
            lines.append(body)
        return "\n".join(lines)

    @classmethod
    def _build_compare_answer(cls, query_text: str, results: List[Dict], top_k: int = 3) -> str:
        """
        通用比较回答（确定性）：
        - 从问题提取强锚点（实体）
        - 对每个实体给出命中情况与证据片段
        """
        anchors = cls._extract_strong_anchors(query_text)
        if len(anchors) < 2:
            return "比較対象を2つ以上特定できませんでした。比較したい対象を明確に指定してください。"

        lines: List[str] = ["比較結果（根拠ベース）:"]
        for idx, anchor in enumerate(anchors[:4], 1):
            variants = cls._anchor_variants(anchor)
            matched = []
            for item in results:
                text = str(item.get("text_content") or "")
                norm = cls._normalize_match_text(text)
                if any(v and v in norm for v in variants):
                    matched.append(item)
            if not matched:
                lines.append(f"{idx}. {anchor}: 根拠となる文書断片が見つかりませんでした。")
                continue

            lines.append(f"{idx}. {anchor}: {len(matched)}件の根拠が見つかりました。")
            for j, m in enumerate(matched[:top_k], 1):
                snippet = str(m.get("text_content") or "").replace("\n", " ").strip()[:120]
                lines.append(
                    f"   - 根拠{j}: [文書{j}] {m.get('file_name', '不明なファイル')} / {snippet}"
                )
        return "\n".join(lines)

    @staticmethod
    def _build_statistics_answer(results: List[Dict]) -> str:
        """
        通用统计回答（确定性）：
        - 命中文档数
        - 命中片段数
        - 命中最多文档
        """
        if not results:
            return "集計対象となる根拠が見つかりませんでした。"

        file_count: Dict[str, int] = {}
        file_name_map: Dict[str, str] = {}
        for row in results:
            md5 = str(row.get("file_md5") or "")
            if not md5:
                continue
            file_count[md5] = file_count.get(md5, 0) + 1
            file_name_map[md5] = str(row.get("file_name") or "不明なファイル")

        if not file_count:
            return "集計対象となる根拠が見つかりませんでした。"

        top_md5 = max(file_count.keys(), key=lambda x: file_count[x])
        return (
            "集計結果（根拠ベース）:\n"
            f"- 命中文書数: {len(file_count)}\n"
            f"- 命中断片数: {len(results)}\n"
            f"- 最多命中文書: {file_name_map.get(top_md5, '不明なファイル')} ({file_count[top_md5]}件)"
        )

    @staticmethod
    def _safe_no_evidence_answer() -> str:
        return "参照可能な根拠が不足しているため、現時点では断定できません。対象名や条件を具体化して再質問してください。"

    @staticmethod
    def _extract_constraint_from_text(text: str) -> str:
        q = (text or "").strip()
        if not q:
            return ""
        constraint_map = [
            ("期間", ("期間", "工期", "いつから", "いつまで", "開始", "終了", "何月", "何日", "什么时候", "何時")),
            ("比較", ("比較", "違い", "差分", "vs", "比", "对比", "比較して")),
            ("件数", ("件数", "合計", "総数", "count", "何件", "いくつ")),
            ("担当", ("担当", "役割", "ポジション", "職位", "职责")),
        ]
        for label, keys in constraint_map:
            if any(k in q for k in keys):
                return label
        return ""

    @staticmethod
    def _extract_scope_from_text(text: str) -> str:
        q = (text or "").strip()
        if not q:
            return ""
        m_sheet = re.search(r"(?:シート|sheet)\s*[「\"']?([\w\u3040-\u30ff\u3400-\u9fff\-]{1,48})", q, re.IGNORECASE)
        if m_sheet:
            return f"シート:{(m_sheet.group(1) or '').strip()}"
        if "スケジュール" in q:
            return "スケジュール"
        if "履歴書" in q or "経歴書" in q:
            return "履歴書"
        return ""

    @staticmethod
    def _extract_subject_from_text(text: str) -> str:
        q = (text or "").strip()
        if not q:
            return ""
        patterns = [
            r"([\u3040-\u30ff\u3400-\u9fffA-Za-z0-9_/\-]{2,40})の(?:期間|工期|スケジュール|比較|件数|担当|役割)",
            r"([\u3040-\u30ff\u3400-\u9fffA-Za-z0-9_/\-]{2,40})(?:は|って|が|を|に|で)(?:いつから|いつまで|期間|工期|比較|担当|役割)",
            r"(?:について|関して)\s*([\u3040-\u30ff\u3400-\u9fffA-Za-z0-9_/\-]{2,40})",
        ]
        for p in patterns:
            m = re.search(p, q)
            if m:
                cand = (m.group(1) or "").strip()
                if cand:
                    return cand
        m = re.search(r"^([\u3040-\u30ff\u3400-\u9fffA-Za-z0-9_/\-]{2,24})(?:は|って)\??$", q)
        return (m.group(1) or "").strip() if m else ""

    @classmethod
    def _build_memory_slot_from_history(cls, history: List[Dict[str, str]]) -> Dict[str, str]:
        slot = {"subject": "", "constraint": "", "scope": ""}
        user_msgs = [m for m in (history or []) if m.get("role") == "user"]
        for msg in reversed(user_msgs[-cls._MEMORY_WINDOW_TURNS:]):
            content = msg.get("content") or ""
            if not slot["subject"]:
                slot["subject"] = cls._extract_subject_from_text(content)
            if not slot["constraint"]:
                slot["constraint"] = cls._extract_constraint_from_text(content)
            if not slot["scope"]:
                slot["scope"] = cls._extract_scope_from_text(content)
            if all(slot.values()):
                break
        return slot

    @classmethod
    def _is_probable_followup(
        cls,
        message: str,
        entities: List[str],
        current_subject: str,
    ) -> bool:
        text = (message or "").strip()
        if not text:
            return False
        if current_subject:
            return False
        if entities:
            return False
        short_len = len(text) <= 24
        followup_cues = (
            "それ", "その", "この", "あれ", "哪个", "这个", "那个", "那", "つづき",
            "いつから", "いつまで", "什么时候", "どれくらい", "何件", "何月", "何日",
        )
        has_cue = any(k in text for k in followup_cues)
        return short_len or has_cue

    @classmethod
    def _inject_followup_memory(
        cls,
        message: str,
        history: List[Dict[str, str]],
        entities: List[str],
    ) -> str:
        current_subject = cls._extract_subject_from_text(message)
        if not cls._is_probable_followup(message, entities, current_subject):
            return message

        slot = cls._build_memory_slot_from_history(history)
        subject = current_subject or slot.get("subject", "")
        constraint = cls._extract_constraint_from_text(message) or slot.get("constraint", "")
        scope = cls._extract_scope_from_text(message) or slot.get("scope", "")
        if not subject and not constraint and not scope:
            return message

        header_parts: List[str] = []
        if scope:
            header_parts.append(scope)
        if subject and constraint:
            header_parts.append(f"{subject}の{constraint}")
        elif subject:
            header_parts.append(subject)
        elif constraint:
            header_parts.append(constraint)
        if not header_parts:
            return message
        return f"{' / '.join(header_parts)} について: {message}"

    @staticmethod
    def _parse_period_labels(period_text: str) -> Tuple[str, str]:
        t = (period_text or "").strip()
        if not t:
            return "", ""
        sep = "->" if "->" in t else ("～" if "～" in t else ("~" if "~" in t else ("至" if "至" in t else "")))
        if sep:
            parts = [p.strip() for p in t.split(sep) if p.strip()]
            if len(parts) >= 2:
                return parts[0], parts[-1]
        return t, t

    @staticmethod
    def _period_duration_text(start: str, end: str) -> str:
        def ym(value: str) -> Optional[Tuple[int, int]]:
            m = re.search(r"(\d{4})\D+(\d{1,2})", value or "")
            if not m:
                return None
            return int(m.group(1)), int(m.group(2))

        start_ym = ym(start)
        end_ym = ym(end)
        if start_ym and end_ym:
            months = (end_ym[0] - start_ym[0]) * 12 + (end_ym[1] - start_ym[1]) + 1
            if months >= 1:
                return f"{months}か月"
        if start and end and start != end:
            return f"{start} ～ {end}"
        if start:
            return "不明"
        return "不明"

    @staticmethod
    def _build_schedule_answer(
        query_text: str,
        results: List[Dict],
        top_n: int = 3,
    ) -> Tuple[Optional[str], float]:
        """
        日程/期間系質問の确定性回答（优先使用 [schedule] 结构化片段）。
        """
        rows: List[Dict[str, Any]] = []
        for item in results:
            text = str(item.get("text_content") or "")
            if not text.startswith("[schedule]"):
                continue
            m = re.search(
                r"sheet=(?P<sheet>.*?)\s*;\s*task=(?P<task>.*?)\s*;\s*period=(?P<period>.*?)(?:\s*;\s*detail=(?P<detail>.*?))?(?:\s*;\s*confidence=(?P<confidence>[0-9.]+))?$",
                text,
            )
            if not m:
                continue
            rows.append(
                {
                    "sheet": (m.group("sheet") or "").strip(),
                    "task": (m.group("task") or "").strip(),
                    "period": (m.group("period") or "").strip(),
                    "detail": (m.group("detail") or "").strip(),
                    "confidence": float(m.group("confidence") or 0.0),
                    "file_name": str(item.get("file_name") or "不明なファイル"),
                }
            )

        if not rows:
            return None, 0.0

        q = (query_text or "").strip().lower()
        filtered = [r for r in rows if r["task"] and r["task"].lower() in q]
        candidates = filtered if filtered else rows
        top_confidence = max((float(r.get("confidence") or 0.0) for r in candidates), default=0.0)

        lines: List[str] = []
        head = candidates[0]
        if filtered:
            start_text, end_text = ChatService._parse_period_labels(head["period"])
            duration_text = ChatService._period_duration_text(start_text, end_text)
            lines.append(
                f"{head['task']} の期間は次の通りです。"
            )
            lines.append(f"- 開始: {start_text or '不明'}")
            lines.append(f"- 終了: {end_text or '不明'}")
            lines.append(f"- 期間: {duration_text}")
            lines.append(f"根拠: シート「{head['sheet']}」 / {head['file_name']}")
            if head["detail"]:
                lines.append(f"補足: {head['detail'][:120]}")
            return "\n".join(lines), top_confidence

        lines.append("抽出済みスケジュールから確認できる期間は以下です。")
        for idx, row in enumerate(candidates[:max(1, top_n)], 1):
            start_text, end_text = ChatService._parse_period_labels(row["period"])
            duration_text = ChatService._period_duration_text(start_text, end_text)
            lines.append(
                f"{idx}. {row['task']}\n"
                f"   - 開始: {start_text or '不明'}\n"
                f"   - 終了: {end_text or '不明'}\n"
                f"   - 期間: {duration_text}\n"
                f"   - 根拠: シート「{row['sheet']}」 / {row['file_name']}"
            )
        return "\n".join(lines), top_confidence

    @staticmethod
    def _extract_schedule_keywords(query_text: str) -> List[str]:
        q = (query_text or "").strip()
        if not q:
            return []
        tokens: List[str] = []
        tokens.extend(re.findall(r"[\u3040-\u30ff\u3400-\u9fff]{2,24}", q))
        tokens.extend(re.findall(r"[A-Za-z][A-Za-z0-9_-]{1,32}", q))
        stop = {
            "スケジュール", "期間", "開始", "終了", "工期", "進捗", "工程",
            "いつ", "いつから", "いつまで", "教えて", "ください", "ですか",
        }
        out: List[str] = []
        seen = set()
        for t in tokens:
            x = t.strip()
            if not x or x in stop or x in seen:
                continue
            seen.add(x)
            out.append(x)
        return out[:8]

    @staticmethod
    def _build_schedule_answer_from_rows(query_text: str, rows: List[Dict[str, Any]]) -> Optional[str]:
        if not rows:
            return None
        query = (query_text or "").lower()
        preferred = [r for r in rows if str(r.get("task") or "").lower() in query]
        candidates = preferred if preferred else rows
        head = candidates[0]
        period_start = str(head.get("period_start") or "").strip()
        period_end = str(head.get("period_end") or "").strip()
        duration = ChatService._period_duration_text(period_start, period_end)
        lines = [
            f"{head.get('task', '対象タスク')} の期間は次の通りです。",
            f"- 開始: {period_start or '不明'}",
            f"- 終了: {period_end or '不明'}",
            f"- 期間: {duration}",
            f"根拠: シート「{head.get('sheet', '-') }」 行 {head.get('row_no', '-') } / {head.get('file_name', '不明なファイル')}",
        ]
        detail = str(head.get("task_detail") or "").strip()
        if detail:
            lines.append(f"補足: {detail[:120]}")
        return "\n".join(lines)

    @staticmethod
    def _should_use_relation_search(intent: str, selected_profile: str, message: str) -> bool:
        text = (message or "").lower()
        strict_relation_keys = get_strict_relation_keys()
        if intent == "flow_query":
            return any(kw in text for kw in strict_relation_keys)

        hit_count = sum(1 for kw in strict_relation_keys if kw in text)
        if selected_profile in {"design", "ops"}:
            return hit_count >= 2
        return hit_count >= 2

    @staticmethod
    def _is_relation_presentation_query(message: str) -> bool:
        text = (message or "").lower()
        return any(k in text for k in get_relation_presentation_keys())

    @staticmethod
    def _is_visual_diagram_request(message: str) -> bool:
        text = (message or "").lower()
        return any(k in text for k in get_visual_diagram_request_keys())

    @staticmethod
    def _build_relation_answer(results: List[Dict]) -> Optional[str]:
        """
        将关系检索结果确定性格式化为 A -> B 列表，避免只输出节点清单。
        """
        def _clean_relation_text(value: str) -> str:
            v = (value or "").strip()
            v = re.sub(r"\[(diagram_node|diagram_edge|diagram_summary)\]\s*", "", v, flags=re.IGNORECASE)
            v = re.sub(r"(diagram_node|diagram_edge|diagram_summary)\]\s*", "", v, flags=re.IGNORECASE)
            v = re.sub(r"\s+", " ", v).strip()
            return v

        relation_lines: List[str] = []
        for row in results:
            text = str(row.get("text_content") or "").strip()
            if not text:
                continue
            if text.startswith("[流程路径]"):
                payload = text.replace("[流程路径]", "", 1).strip()
                for seg in [x.strip() for x in payload.split(";") if x.strip()]:
                    clean_seg = _clean_relation_text(seg)
                    if clean_seg:
                        relation_lines.append(clean_seg)
                continue
            if text.startswith("[关系]"):
                payload = text.replace("[关系]", "", 1).strip()
                clean_payload = _clean_relation_text(payload)
                if clean_payload:
                    relation_lines.append(clean_payload)

        if not relation_lines:
            return None

        uniq: List[str] = []
        seen = set()
        for ln in relation_lines:
            k = re.sub(r"\s+", "", ln)
            if not k or k in seen:
                continue
            seen.add(k)
            uniq.append(ln)

        if not uniq:
            return None

        lines = ["構成/連携関係は次の通りです。"]
        for i, ln in enumerate(uniq[:15], 1):
            display = ln.replace("--", "").replace("-->", "->")
            lines.append(f"{i}. {display}")
        return "\n".join(lines)

    @staticmethod
    def _should_force_relation_answer(results: List[Dict], query_text: str = "") -> bool:
        """
        仅在关系证据足够时才强制用“关系列表”回答，避免劣质边污染主答案。
        """
        rel_lines = 0
        for row in results:
            t = str(row.get("text_content") or "")
            if not (t.startswith("[关系]") or t.startswith("[流程路径]")):
                continue
            clean = re.sub(r"\[(diagram_node|diagram_edge|diagram_summary)\]\s*", "", t, flags=re.IGNORECASE)
            if ("->" in clean) or ("入力>" in clean) or ("输出>" in clean) or ("出力>" in clean):
                rel_lines += 1
        q = (query_text or "").lower()
        explicit_relation_ask = any(k in q for k in get_relation_presentation_keys())
        ask_list_style = any(k in q for k in ("一覧", "列出", "list", "show all", "全部"))
        threshold = 2 if ask_list_style else (3 if explicit_relation_ask else 5)
        return rel_lines >= threshold

    @classmethod
    def _has_anchor_grounding(
        cls,
        query_text: str,
        results: List[Dict],
        selected_profile: Optional[str] = None,
    ) -> bool:
        """
        通用证据约束：
        - 若用户问题包含强锚点（人名/系统名）
        - 检索结果必须至少命中一个锚点
        """
        strong_anchors = cls._extract_strong_anchors(query_text, selected_profile=selected_profile)
        if not strong_anchors:
            return True

        variants = []
        for a in strong_anchors:
            variants.extend(cls._anchor_variants(a))
        variants = [v for v in variants if v]
        if not variants:
            return True

        for row in results:
            text = cls._normalize_match_text(
                f"{row.get('file_name', '')} {row.get('text_content', '')}"
            )
            if any(v in text for v in variants):
                return True
        return False

    @staticmethod
    def _rewrite_query_for_resume(message: str, profile_terms: str = "") -> str:
        """
        履歴書/経歴系質問の軽量クエリ拡張（日本語優先、多言語フォールバック）。
        """
        q = (message or "").strip()
        lower_q = q.lower()
        has_profile_intent = any(
            k in q for k in (
                "履歴書", "経歴書", "職歴", "経歴", "業務経歴書",
                "プロジェクト", "案件", "役割", "担当", "ポジション",
                "経験", "会社", "在籍",
                # fallback
                "简历", "经历", "项目", "职位",
            )
        )
        has_time_order_intent = any(
            k in lower_q for k in (
                "直近", "最近", "最新", "latest", "recent", "top3", "3件", "3個",
                # fallback
                "近3", "前三", "3个", "三个",
            )
        )

        if has_profile_intent or has_time_order_intent:
            enrich = profile_terms or (
                " 履歴書 経歴書 業務経歴書 職歴 経歴 担当 役割 ポジション"
                " プロジェクト 案件 期間 会社 業務内容 最新 直近"
            )
            if enrich.strip() not in q:
                return f"{q}{enrich}"
        return q

    @staticmethod
    def _looks_like_db_identifier(token: str) -> bool:
        t = (token or "").strip()
        if not t:
            return False
        patterns = (
            r"^[A-Za-z][A-Za-z0-9_]{2,63}$",
            r"^[A-Za-z][A-Za-z0-9_]{1,63}(?:\.[A-Za-z][A-Za-z0-9_]{1,63}){1,2}$",
            r"^[A-Z]{2,}[0-9]{2,}$",
            r"^(?:IF|API)[-_][A-Za-z0-9_]{2,}$",
            r"^[A-Za-z][A-Za-z0-9_]{2,}_(?:id|cd|code|no|num|key)$",
            r"^(?:tbl|t)_[A-Za-z0-9_]{2,}$",
        )
        return any(re.fullmatch(p, t) for p in patterns)

    @classmethod
    def _extract_anchor_tokens(cls, query: str, selected_profile: Optional[str] = None) -> List[str]:
        """
        クエリからアンカー語を抽出（日本語優先）。
        """
        raw_text = (query or "").strip()
        text = raw_text.lower()
        if not text:
            return []

        text = re.sub(r"[、。,.!?！？:：;；()\[\]{}<>「」『』\"'`]+", " ", text)
        tokens: List[str] = []
        tokens.extend(re.findall(r"[A-Za-z][A-Za-z0-9_]{1,63}(?:\.[A-Za-z][A-Za-z0-9_]{1,63}){1,2}", raw_text))
        tokens.extend(re.findall(r"[A-Za-z][A-Za-z0-9_-]{1,31}", text))
        tokens.extend(re.findall(r"[\u3040-\u30ff\u3400-\u9fff]{2,24}", text))

        stop_words = {
            "なに", "何", "どれ", "どの", "どう", "について", "教えて", "ください",
            "最近", "最新", "直近", "ですか", "ますか",
            "什么", "哪些", "怎么", "如何", "这个", "那个", "一下",
            "what", "which", "how", "latest", "recent",
            "project", "projects", "role", "roles",
        }
        if selected_profile == "design":
            stop_words = stop_words.union(
                {
                    "db", "database", "データベース", "テーブル", "カラム", "項目",
                    "主キー", "外部キー", "インデックス", "制約",
                    "参照", "結合", "join", "正規化", "er図",
                    "追加", "変更", "削除", "影響範囲", "api", "if",
                    "設計書", "基本設計", "詳細設計", "内部設計", "外部設計",
                    "要件", "仕様", "画面", "帳票",
                }
            )
        uniq: List[str] = []
        seen = set()
        for t in tokens:
            tok = t.strip()
            if not tok:
                continue
            if selected_profile == "design" and cls._looks_like_db_identifier(tok):
                pass
            elif tok in stop_words:
                continue
            if tok in seen:
                continue
            seen.add(tok)
            uniq.append(tok)
        return uniq[:8]

    @staticmethod
    def _normalize_match_text(text: str) -> str:
        t = (text or "").lower()
        t = re.sub(r"[\s\-_|\u3000]+", "", t)
        return t

    @staticmethod
    def _anchor_variants(token: str) -> List[str]:
        """
        生成锚点变体（通用最小集）：
        - 原词
        - 去空白
        - 常见简繁字对（用于姓名/专有名词）
        """
        tok = (token or "").strip()
        if not tok:
            return []

        s2t = {
            "婵": "嬋",
            "莲": "蓮",
            "华": "華",
            "伟": "偉",
            "杰": "傑",
            "丽": "麗",
            "国": "國",
            "东": "東",
            "龙": "龍",
            "叶": "葉",
            "陈": "陳",
            "刘": "劉",
            "张": "張",
            "杨": "楊",
            "黄": "黃",
        }
        t2s = {v: k for k, v in s2t.items()}

        def convert(text: str, mapping: Dict[str, str]) -> str:
            return "".join(mapping.get(ch, ch) for ch in text)

        candidates = {
            tok,
            ChatService._normalize_match_text(tok),
            convert(tok, s2t),
            convert(tok, t2s),
            ChatService._normalize_match_text(convert(tok, s2t)),
            ChatService._normalize_match_text(convert(tok, t2s)),
        }
        return [c for c in candidates if c]

    @classmethod
    def _extract_strong_anchors(cls, query_text: str, selected_profile: Optional[str] = None) -> List[str]:
        anchors = cls._extract_anchor_tokens(query_text, selected_profile=selected_profile)

        raw = (query_text or "").strip()
        ja_name_candidates = re.findall(
            r"([\u3400-\u9fff]{2,12})(?:さん|氏|様|ちゃん|くん)?(?:の|は|が|を|に|で|と|について|に関して)",
            raw,
        )
        for cand in ja_name_candidates:
            if cand and cand not in anchors:
                anchors.insert(0, cand)
        suffix_patterns = [
            r"(ですか|ますか|でしょうか|について|とは|って)$",
            r"(何ですか|なに|何|どれ|どのくらい|どんな|教えて)$",
            r"(擅长什么|擅長什麼|是什么|是什麼|有哪些|有哪一些|怎么|如何|多少|最近|最新)$",
            r"(ね|よ|かな|か|呢|吗|嗎|嘛|呀|啊)$",
        ]

        def normalize_anchor(a: str) -> str:
            token = (a or "").strip()
            if not token:
                return ""
            token = re.sub(r"(さん|氏|様|ちゃん|くん)$", "", token)
            token = re.sub(r"(の|は|が|を|に|で|と).*$", "", token)
            for p in suffix_patterns:
                token = re.sub(p, "", token)
            token = token.strip()
            return token

        stop_words = {
            "履歴書", "経歴書", "職歴", "経歴", "プロジェクト", "案件", "役割", "担当", "ポジション",
            "最近", "最新", "直近", "強み", "スキル", "能力", "経験", "紹介", "説明",
            "構成図", "システム図", "システム構成図", "構成", "アーキテクチャ", "フロー", "関係図", "連携図", "システム",
            "定義", "確認", "画面", "レイアウト", "画面レイアウト",
            "なに", "何", "どれ", "どう",
            "简历", "项目", "职位", "擅长", "技能", "能力", "经验", "什么", "哪些", "怎么", "如何",
            "please", "what", "which", "how",
            "いつから", "いつまで", "いつからいつまで", "いつ", "何月", "何日",
        }
        if selected_profile == "design":
            stop_words = stop_words.union(
                {
                    "db", "database", "データベース", "テーブル", "カラム", "項目",
                    "主キー", "外部キー", "インデックス", "制約",
                    "参照", "結合", "join", "正規化", "er図",
                    "追加", "変更", "削除", "影響範囲", "api", "if",
                    "設計書", "基本設計", "詳細設計", "内部設計", "外部設計",
                    "要件", "仕様", "画面", "帳票",
                }
            )

        def looks_like_question_phrase(token: str) -> bool:
            t = (token or "").strip()
            if not t:
                return True
            question_fragments = (
                "ですか", "ますか", "でしょう", "吗", "嗎", "呢", "？", "?", "一下",
                "比较", "對比", "比一下", "何件", "いくつ", "どれ", "なに", "何",
                "いつ", "いつから", "いつまで", "什么时候",
            )
            if any(k in t for k in question_fragments):
                return True
            if re.match(r"^(何|哪|どの|どれ|なに|いつ)", t):
                return True
            return False

        strong = []
        for a in anchors:
            normalized = normalize_anchor(a)
            if not normalized:
                continue
            if selected_profile == "design" and cls._looks_like_db_identifier(normalized):
                strong.append(normalized)
                continue
            if normalized in stop_words:
                continue
            if looks_like_question_phrase(normalized):
                continue
            if re.fullmatch(r"[\u3040-\u309f]{2,24}", normalized):
                continue
            if re.fullmatch(r"[\u3040-\u30ff\u3400-\u9fff]{2,12}", normalized) or re.fullmatch(r"[A-Za-z0-9_-]{3,32}", normalized):
                strong.append(normalized)
        return strong[:4]

    @classmethod
    def _apply_document_focus(
        cls,
        results: List[Dict],
        query_text: str,
        top_k: int = 8,
        strict_entity_filter: bool = False,
        selected_profile: Optional[str] = None,
    ) -> List[Dict]:
        """
        通用文档聚焦：
        - 按 file 计算主题强度（max_score + 命中数加权）
        - 同时用查询锚点词计算文档词面命中强度（file_name + chunk 文本）
        - 当头部文件显著领先时，只保留该文件块，避免跨文档污染
        该策略对简历、设计书、流程图都适用。
        """
        if not results:
            return results
        anchors = cls._extract_anchor_tokens(query_text, selected_profile=selected_profile)
        strong_anchors = cls._extract_strong_anchors(query_text, selected_profile=selected_profile)
        strong_anchor_variants = {a: cls._anchor_variants(a) for a in strong_anchors}

        file_stats: Dict[str, Dict[str, float]] = {}
        for item in results:
            file_md5 = str(item.get("file_md5") or "")
            if not file_md5:
                continue
            score = float(item.get("score") or 0.0)
            content = cls._normalize_match_text(f"{item.get('file_name', '')} {item.get('text_content', '')}")
            anchor_hits = sum(1.0 for a in anchors if a and a in content)
            strong_hits = 0.0
            for variants in strong_anchor_variants.values():
                if any(v and v in content for v in variants):
                    strong_hits += 1.0
            if file_md5 not in file_stats:
                file_stats[file_md5] = {"max": score, "cnt": 1.0, "anchor_hits": anchor_hits, "strong_hits": strong_hits}
            else:
                file_stats[file_md5]["max"] = max(file_stats[file_md5]["max"], score)
                file_stats[file_md5]["cnt"] += 1.0
                file_stats[file_md5]["anchor_hits"] += anchor_hits
                file_stats[file_md5]["strong_hits"] += strong_hits

        if len(file_stats) <= 1:
            return results[:top_k]

        is_layout_query = any(k in (query_text or "").lower() for k in get_layout_query_keys())
        if strict_entity_filter and strong_anchor_variants and (not is_layout_query):
            strong_ranked = sorted(file_stats.items(), key=lambda kv: kv[1]["strong_hits"], reverse=True)
            best_hits = strong_ranked[0][1]["strong_hits"]
            if best_hits > 0:
                allowed = {fid for fid, st in strong_ranked if st["strong_hits"] == best_hits}
                focused = [x for x in results if str(x.get("file_md5") or "") in allowed]
                if focused:
                    logger.info("实体强约束命中: anchors=%s, file_ids=%s", list(strong_anchor_variants.keys()), list(allowed))
                    return focused[:top_k]
            else:
                logger.info("实体强约束未命中，改为软惩罚: anchors=%s", list(strong_anchor_variants.keys()))
                penalty = 0.82
                for item in results:
                    try:
                        item["score"] = float(item.get("score") or 0.0) * penalty
                    except Exception:
                        item["score"] = 0.0
        elif strict_entity_filter and strong_anchor_variants and is_layout_query:
            logger.info("layout查询跳过强锚点硬过滤: anchors=%s", list(strong_anchor_variants.keys()))

        ranked_files = sorted(
            file_stats.items(),
            key=lambda kv: (kv[1]["max"] + 0.08 * kv[1]["cnt"] + 0.25 * kv[1]["anchor_hits"] + 0.5 * kv[1]["strong_hits"]),
            reverse=True,
        )
        top_file, top_stat = ranked_files[0]
        second_stat = ranked_files[1][1]
        top_strength = top_stat["max"] + 0.08 * top_stat["cnt"] + 0.25 * top_stat["anchor_hits"]
        second_strength = second_stat["max"] + 0.08 * second_stat["cnt"] + 0.25 * second_stat["anchor_hits"]

        if top_strength >= second_strength * 1.12 or (top_strength - second_strength) >= 0.25:
            focused = [x for x in results if str(x.get("file_md5") or "") == top_file]
            if focused:
                return focused[:top_k]
        return results[:top_k]

    @staticmethod
    def _is_relation_evidence_row(row: Dict[str, Any]) -> bool:
        text = str(row.get("text_content") or "")
        if text.startswith("[关系]") or text.startswith("[流程路径]"):
            return True
        low = text.lower()
        if ("-->" in low) or ("入力>" in text) or ("出力>" in text) or ("输出>" in text):
            return True
        return False

    async def _promote_layout_image_evidence(
        self,
        db: AsyncSession,
        results: List[Dict[str, Any]],
        top_k: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        layout 查询优先“可溯源到图片”的 chunk，避免回答命中纯表格文本而证据面板无图。
        """
        if not results:
            return results

        ranked: List[Tuple[float, int, Dict[str, Any]]] = []
        for idx, row in enumerate(results):
            text = str(row.get("text_content") or "")
            score = float(row.get("score") or 0.0)
            bonus = 0.0
            if "[diagram_page]" in text:
                bonus += 0.35
            if "[diagram_summary]" in text:
                bonus += 0.25
            if "[图片]" in text:
                bonus += 0.22
            if "画面id" in text.lower() or "画面名" in text:
                bonus += 0.10

            file_md5 = str(row.get("file_md5") or "")
            chunk_id = row.get("chunk_id")
            has_image = False
            if file_md5 and chunk_id is not None:
                try:
                    stmt = (
                        select(ChunkSource.id)
                        .where(
                            ChunkSource.file_md5 == file_md5,
                            ChunkSource.chunk_id == int(chunk_id),
                            ChunkSource.image_path.is_not(None),
                            ChunkSource.image_path != "",
                        )
                        .limit(1)
                    )
                    hit = (await db.execute(stmt)).first()
                    has_image = bool(hit)
                except Exception:
                    has_image = False
            if has_image:
                bonus += 0.55
            ranked.append((score + bonus, idx, row))

        ranked.sort(key=lambda x: (x[0], -x[1]), reverse=True)
        return [x[2] for x in ranked[: max(1, top_k)]]

    def _apply_evidence_guardrails(
        self,
        message: str,
        selected_profile: str,
        results: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        证据硬约束：
        - policy 模式下禁用关系证据
        - relation 问题若无关系证据则返回空（上层走安全降级）
        - text 问题若仅关系证据则优先剔除关系
        """
        rows = list(results or [])
        if not rows:
            return rows

        preference = self._evidence_preference(message)
        if selected_profile == "policy":
            rows = [r for r in rows if not self._is_relation_evidence_row(r)]
            if not rows:
                return []

        relation_rows = [r for r in rows if self._is_relation_evidence_row(r)]
        text_rows = [r for r in rows if not self._is_relation_evidence_row(r)]

        if preference == "relation":
            if relation_rows:
                return relation_rows
            if self._is_visual_diagram_request(message):
                return text_rows
            return []
        if preference == "text":
            return text_rows if text_rows else []
        if preference == "mixed":
            mixed = relation_rows[:4] + text_rows[:4]
            return mixed if mixed else rows
        return rows

    @staticmethod
    def _evidence_preference(query_text: str) -> str:
        text = (query_text or "").lower()
        layout_keys = get_layout_query_keys()
        strict_relation_keys = get_strict_relation_keys()
        flow_keys = get_flow_query_keys()
        explanation_keys = get_text_explanation_keys()
        if any(k in text for k in layout_keys):
            return "text"
        rel_hit = sum(1 for k in strict_relation_keys.union(flow_keys) if k in text)
        txt_hit = sum(1 for k in explanation_keys if k in text)
        if rel_hit > 0 and txt_hit > 0:
            return "mixed"
        if rel_hit > 0:
            return "relation"
        return "text"

    @classmethod
    def _fuse_parallel_results(
        cls,
        query_text: str,
        hybrid_results: List[Dict[str, Any]],
        relation_results: List[Dict[str, Any]],
        selected_profile: str,
        top_k: int = 8,
    ) -> List[Dict[str, Any]]:
        """
        并行三路中的“hybrid + relation”融合（RRF + 证据类型偏置）。
        """
        preference = cls._evidence_preference(query_text)
        weights = cls._profile_fusion_weights(selected_profile)
        rank_map: Dict[str, Dict[str, Any]] = {}
        k = 60.0

        def row_key(row: Dict[str, Any], fallback_prefix: str, idx: int) -> str:
            file_md5 = str(row.get("file_md5") or "")
            chunk_id = row.get("chunk_id")
            if file_md5 and chunk_id is not None:
                return f"{file_md5}_{chunk_id}"
            sig = re.sub(r"\s+", "", str(row.get("text_content") or ""))[:120]
            return f"{fallback_prefix}_{idx}_{file_md5}_{sig}"

        for idx, row in enumerate(hybrid_results or [], 1):
            key = row_key(row, "h", idx)
            current = rank_map.setdefault(
                key,
                {
                    **row,
                    "rrf_score": 0.0,
                    "hybrid_rank": idx,
                    "relation_rank": None,
                    "is_relation_evidence": cls._is_relation_evidence_row(row),
                },
            )
            current["rrf_score"] += float(weights.get("hybrid", 0.8)) * (1.0 / (k + float(idx)))

        for idx, row in enumerate(relation_results or [], 1):
            key = row_key(row, "r", idx)
            current = rank_map.setdefault(
                key,
                {
                    **row,
                    "rrf_score": 0.0,
                    "hybrid_rank": None,
                    "relation_rank": idx,
                    "is_relation_evidence": cls._is_relation_evidence_row(row),
                },
            )
            current["rrf_score"] += float(weights.get("relation", 0.2)) * (1.0 / (k + float(idx)))
            current["relation_rank"] = idx

        fused = list(rank_map.values())
        for row in fused:
            bonus = 0.0
            is_rel = bool(row.get("is_relation_evidence"))
            if preference == "relation":
                bonus += 0.25 if is_rel else 0.0
            elif preference == "text":
                bonus += 0.10 if not is_rel else 0.0
            else:  # mixed
                bonus += 0.12 if is_rel else 0.06

            if selected_profile in {"design", "ops"} and is_rel:
                bonus += 0.08
            if selected_profile == "policy" and is_rel:
                bonus -= 0.05

            row["final_score"] = float(row.get("rrf_score") or 0.0) + bonus

        fused.sort(key=lambda x: float(x.get("final_score") or 0.0), reverse=True)
        return fused[:top_k]

    async def _parallel_retrieve(
        self,
        db: AsyncSession,
        user: User,
        message: str,
        search_query: str,
        selected_profile: str,
        entities: List[str],
        top_k: int = 8,
        include_relation: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        并行检索：
        - hybrid（向量 + BM25）
        - relation（图/关系）
        然后统一融合重排。
        """
        enable_relation = bool(include_relation) and self._relation_enabled_for_profile(selected_profile)
        hybrid_task = self.search_service.hybrid_search(
            db=db,
            user=user,
            query_text=search_query,
            top_k=max(top_k, 8),
            entities=entities,
            selected_profile=selected_profile,
        )
        relation_task = (
            self.relation_search_service.search_relations(
                db=db,
                user=user,
                query_text=search_query,
                top_k=max(6, top_k),
                kb_profile=None,
            )
            if enable_relation
            else None
        )

        if relation_task is not None:
            hybrid_results, relation_results = await asyncio.gather(hybrid_task, relation_task)
        else:
            hybrid_results = await hybrid_task
            relation_results = []

        fused = self._fuse_parallel_results(
            query_text=message,
            hybrid_results=hybrid_results or [],
            relation_results=relation_results or [],
            selected_profile=selected_profile,
            top_k=top_k,
        )
        return self._apply_evidence_guardrails(
            message=message,
            selected_profile=selected_profile,
            results=fused,
        )

    async def _handle_timeline_intent(
        self,
        db: AsyncSession,
        user: User,
        message: str,
        search_query: str,
        selected_profile: str,
        strict_entity_filter: bool,
        entities: List[str],
        route: Dict[str, Any],
    ) -> Tuple[Optional[str], List[Dict]]:
        top_n = int(route.get("top_n") or 3)
        ask_distance = bool(route.get("ask_distance"))
        timeline_results = await self.experience_service.query_recent_items(
            db=db,
            user=user,
            top_n=max(1, min(top_n, 20)),
            ask_distance=ask_distance,
            kb_profile=None,
        )
        if timeline_results:
            return self._build_timeline_answer(timeline_results, top_n=top_n), []

        logger.info("時系列の構造化結果が空のため、並行三路検索へフォールバック")
        search_results = await self._parallel_retrieve(
            db=db,
            user=user,
            message=message,
            search_query=search_query,
            selected_profile=selected_profile,
            entities=entities,
            top_k=8,
            include_relation=True,
        )
        search_results = self._apply_document_focus(
            search_results,
            query_text=message,
            top_k=8,
            strict_entity_filter=strict_entity_filter,
            selected_profile=selected_profile,
        )
        return None, search_results

    async def _handle_compare_intent(
        self,
        db: AsyncSession,
        user: User,
        message: str,
        search_query: str,
        selected_profile: str,
        entities: List[str],
    ) -> Tuple[str, List[Dict]]:
        search_results = await self._parallel_retrieve(
            db=db,
            user=user,
            message=message,
            search_query=search_query,
            selected_profile=selected_profile,
            entities=entities,
            top_k=10,
            include_relation=True,
        )
        search_results = self._apply_document_focus(
            search_results,
            query_text=message,
            top_k=10,
            strict_entity_filter=False,
            selected_profile=selected_profile,
        )
        return self._build_compare_answer(message, search_results, top_k=3), search_results

    async def _handle_statistics_intent(
        self,
        db: AsyncSession,
        user: User,
        message: str,
        search_query: str,
        selected_profile: str,
        entities: List[str],
    ) -> Tuple[str, List[Dict]]:
        search_results = await self._parallel_retrieve(
            db=db,
            user=user,
            message=message,
            search_query=search_query,
            selected_profile=selected_profile,
            entities=entities,
            top_k=12,
            include_relation=True,
        )
        return self._build_statistics_answer(search_results), search_results

    async def _handle_schedule_intent(
        self,
        db: AsyncSession,
        user: User,
        message: str,
        search_query: str,
        selected_profile: str,
        entities: List[str],
    ) -> Tuple[Optional[str], List[Dict]]:
        ask_strict_period = any(k in (message or "") for k in ("いつから", "いつまで", "開始", "終了", "何月", "何日"))
        search_results = await self._parallel_retrieve(
            db=db,
            user=user,
            message=message,
            search_query=search_query,
            selected_profile=selected_profile,
            entities=entities,
            top_k=12,
            include_relation=True,
        )
        search_results = self._apply_document_focus(
            search_results,
            query_text=message,
            top_k=12,
            strict_entity_filter=False,
            selected_profile=selected_profile,
        )
        deterministic, confidence = self._build_schedule_answer(message, search_results, top_n=3)
        if deterministic and confidence >= 0.62:
            return deterministic, search_results

        fallback_answer = await self._schedule_structured_fallback(
            db=db,
            user=user,
            message=message,
            selected_profile=selected_profile,
        )
        if fallback_answer:
            return fallback_answer, search_results
        if ask_strict_period:
            return self._safe_no_evidence_answer(), search_results
        return deterministic, search_results

    async def _handle_flow_intent(
        self,
        db: AsyncSession,
        user: User,
        message: str,
        search_query: str,
        selected_profile: str,
        strict_entity_filter: bool,
        entities: List[str],
    ) -> List[Dict]:
        logger.info("フロー/関係質問を検出。並行三路（hybrid + relation）で検索")
        search_results = await self._parallel_retrieve(
            db=db,
            user=user,
            message=message,
            search_query=search_query,
            selected_profile=selected_profile,
            entities=entities,
            top_k=8,
            include_relation=True,
        )
        search_results = self._apply_document_focus(
            search_results,
            query_text=message,
            top_k=8,
            strict_entity_filter=strict_entity_filter,
            selected_profile=selected_profile,
        )
        return search_results

    async def _schedule_structured_fallback(
        self,
        db: AsyncSession,
        user: User,
        message: str,
        selected_profile: str,
    ) -> Optional[str]:
        """
        低置信补强：直接查询 table_rows（source_parser=xlsx_schedule）。
        """
        file_map = await self.search_service._load_accessible_file_metadata(db, user)
        file_md5s = [k for k in file_map.keys() if k]
        if not file_md5s:
            return None

        stmt = (
            select(
                TableRow.file_md5,
                TableRow.sheet,
                TableRow.row_no,
                TableRow.row_json,
                TableRow.raw_text,
                TableRow.source_parser,
                FileUpload.file_name,
                FileUpload.kb_profile,
            )
            .join(FileUpload, FileUpload.file_md5 == TableRow.file_md5)
            .where(TableRow.file_md5.in_(file_md5s))
            .where(TableRow.source_parser == "xlsx_schedule")
            .order_by(TableRow.id.asc())
            .limit(300)
        )
        rows = (await db.execute(stmt)).all()
        if not rows:
            return None

        kw = self._extract_schedule_keywords(message)
        matched: List[Dict[str, Any]] = []
        for row in rows:
            file_md5, sheet, row_no, row_json, raw_text, _src, file_name, kb_profile = row
            profile_bonus = 1 if kb_profile == selected_profile else 0
            raw = str(raw_text or "")
            parsed: Dict[str, Any] = {}
            try:
                parsed = json.loads(row_json) if isinstance(row_json, str) else (row_json or {})
            except Exception:
                parsed = {}

            task = str(parsed.get("task") or "")
            period_start = str(parsed.get("period_start") or "")
            period_end = str(parsed.get("period_end") or "")
            detail = str(parsed.get("task_detail") or "")
            confidence = float(parsed.get("confidence") or 0.0)
            haystack = f"{sheet or ''} {task} {detail} {raw}".lower()
            hit = sum(1 for k in kw if k.lower() in haystack)

            if kw and hit == 0:
                continue
            score = hit + profile_bonus + confidence
            matched.append(
                {
                    "score": score,
                    "sheet": sheet,
                    "row_no": row_no,
                    "task": task or raw[:40],
                    "period_start": period_start,
                    "period_end": period_end,
                    "task_detail": detail,
                    "file_name": file_name,
                    "file_md5": file_md5,
                }
            )

        if not matched:
            return None
        matched.sort(key=lambda x: x.get("score", 0.0), reverse=True)
        return self._build_schedule_answer_from_rows(message, matched[:10])

    async def _retrieve_with_intent_plan(
        self,
        db: AsyncSession,
        user: User,
        *,
        intent: str,
        message: str,
        search_query: str,
        selected_profile: str,
        strict_entity_filter: bool,
        query_entities: List[str],
        top_k: int,
        include_relation: bool,
    ) -> List[Dict[str, Any]]:
        if intent == "layout_query":
            search_results = await self._parallel_retrieve(
                db=db,
                user=user,
                message=message,
                search_query=search_query,
                selected_profile=selected_profile,
                entities=query_entities,
                top_k=max(10, top_k),
                include_relation=False,
            )
            search_results = self._apply_document_focus(
                search_results,
                query_text=message,
                top_k=max(10, top_k),
                strict_entity_filter=strict_entity_filter,
                selected_profile=selected_profile,
            )
            search_results = await self._promote_layout_image_evidence(
                db=db,
                results=search_results,
                top_k=max(10, top_k),
            )
        elif self._should_use_relation_search(intent, selected_profile, message):
            search_results = await self._handle_flow_intent(
                db=db,
                user=user,
                message=message,
                search_query=search_query,
                selected_profile=selected_profile,
                strict_entity_filter=strict_entity_filter,
                entities=query_entities,
            )
        else:
            search_results = await self._parallel_retrieve(
                db=db,
                user=user,
                message=message,
                search_query=search_query,
                selected_profile=selected_profile,
                entities=query_entities,
                top_k=max(8, top_k),
                include_relation=include_relation,
            )
            search_results = self._apply_document_focus(
                search_results,
                query_text=message,
                top_k=max(8, top_k),
                strict_entity_filter=strict_entity_filter,
                selected_profile=selected_profile,
            )

        if (not search_results) and self._is_visual_diagram_request(message):
            visual_terms = " ".join(sorted(get_visual_diagram_request_keys()))
            visual_query = f"{visual_terms} {search_query} [diagram_page] [diagram_summary]"
            fallback_visual = await self.search_service.keyword_fallback_search(
                db=db,
                user=user,
                query_text=visual_query,
                kb_profile=None,
                top_k=12,
            )
            search_results = self._apply_document_focus(
                fallback_visual,
                query_text=message,
                top_k=10,
                strict_entity_filter=False,
                selected_profile=selected_profile,
            )
            search_results = await self._promote_layout_image_evidence(
                db=db,
                results=search_results,
                top_k=10,
            )

        if strict_entity_filter and not search_results:
            fallback_results = await self.search_service.keyword_fallback_search(
                db=db,
                user=user,
                query_text=message,
                kb_profile=None,
                top_k=8,
            )
            search_results = self._apply_document_focus(
                fallback_results,
                query_text=message,
                top_k=8,
                strict_entity_filter=True,
                selected_profile=selected_profile,
            )

        if strict_entity_filter and search_results:
            file_ids = {str(x.get("file_md5") or "") for x in search_results if x.get("file_md5")}
            if len(file_ids) == 1 and len(search_results) < 5:
                file_md5 = next(iter(file_ids))
                supplement = await self.search_service.get_file_chunks(
                    db=db,
                    file_md5=file_md5,
                    limit=8,
                )
                merged = {f"{r.get('file_md5')}_{r.get('chunk_id')}": r for r in search_results}
                for row in supplement:
                    key = f"{row.get('file_md5')}_{row.get('chunk_id')}"
                    if key not in merged:
                        merged[key] = row
                search_results = list(merged.values())[:8]

        return search_results

    async def process_message(
        self,
        db: AsyncSession,
        user: User,
        message: str,
        conversation_id: Optional[str] = None,
        status_callback: Optional[Callable[[Dict[str, Any]], Awaitable[None]]] = None,
    ) -> AsyncIterator[str]:
        """
        处理用户消息，返回流式响应
        
        Args:
            db: 数据库会话
            user: 当前用户
            message: 用户消息
            conversation_id: 会话ID（可选，如果不提供则自动获取或创建）
            
        Yields:
            str: 响应内容块
        """
        started_at = time.perf_counter()
        intent = "unknown"
        selected_profile = ""
        search_results: List[Dict] = []
        sources: List[Dict] = []
        assistant_content = ""
        async def emit_status(stage: str, text: str, **extra: Any) -> None:
            if not status_callback:
                return
            try:
                payload = {
                    "type": "status",
                    "stage": stage,
                    "message": text,
                    "timestamp": int(time.time() * 1000),
                }
                payload.update(extra)
                await status_callback(payload)
            except Exception:
                pass
        try:
            await emit_status("planner", "質問の意図を分析しています...")
            if not conversation_id:
                conversation_id = await self.conversation_service.get_or_create_conversation(user.id)
            
            is_archived = await self.conversation_service.is_archived(conversation_id, db)
            if is_archived:
                assistant_content = "この会話はアーカイブ済みのため続行できません。新しい会話を作成してください。"
                await self._record_usage_event(
                    db=db,
                    user=user,
                    conversation_id=conversation_id,
                    message=message,
                    answer_text=assistant_content,
                    intent=intent,
                    selected_profile=selected_profile,
                    search_results=search_results,
                    sources=sources,
                    status="archived",
                    started_at=started_at,
                )
                yield assistant_content
                return
            
            logger.info(f"处理用户消息: user_id={user.id}, conversation_id={conversation_id}")
            selected_profile = await profile_service.get_selected_profile(db)
            if not selected_profile:
                assistant_content = "ナレッジベースのシナリオが未初期化です。先に「シナリオ初期化」を実行してください。"
                await self._record_usage_event(
                    db=db,
                    user=user,
                    conversation_id=conversation_id,
                    message=message,
                    answer_text=assistant_content,
                    intent=intent,
                    selected_profile=selected_profile,
                    search_results=search_results,
                    sources=sources,
                    status="error",
                    started_at=started_at,
                    error_type="profile_not_selected",
                )
                yield assistant_content
                return
            profile_strategy = profile_service.get_strategy(selected_profile)
            history_for_understanding = await self.conversation_service.get_conversation_history(
                conversation_id, db=db
            )
            tentative_entities = self._extract_strong_anchors(message, selected_profile=selected_profile)
            understood_input = self._inject_followup_memory(
                message=message,
                history=history_for_understanding,
                entities=tentative_entities,
            )
            if understood_input != message:
                logger.info("追问补全生效: raw='%s' => normalized='%s'", message[:80], understood_input[:120])
            
            understood = self.query_understanding_service.understand(
                query=understood_input,
                profile_terms=profile_strategy.query_expand_terms,
            )
            route = self.intent_router_service.parse(understood_input)
            intent = str(understood.get("intent") or route.get("intent") or "fact_lookup")
            query_entities = list(understood.get("entities") or [])
            must_terms = list(understood.get("must_terms") or [])
            strict_entity_filter = bool(must_terms) and intent not in {"layout_query"}
            search_query = str(understood.get("rewritten_query") or understood_input)
            logger.info(
                "开始知识库检索: intent=%s, entities=%s, must_terms=%s, strict_entity_filter=%s, raw='%s...', normalized='%s...', query='%s...'",
                intent,
                query_entities[:4],
                must_terms[:4],
                strict_entity_filter,
                message[:50],
                understood_input[:80],
                search_query[:80],
            )
            search_results: List[Dict] = []
            await emit_status("retriever", "根拠を検索しています...")

            deterministic_answer: Optional[str] = None
            graph_state: Optional[QAState] = None
            intent_handlers = {
                "timeline_query": self._handle_timeline_intent,
                "compare_query": self._handle_compare_intent,
                "statistics_query": self._handle_statistics_intent,
                "schedule_query": self._handle_schedule_intent,
            }

            if intent in intent_handlers:
                if intent == "timeline_query":
                    deterministic_answer, search_results = await self._handle_timeline_intent(
                        db=db,
                        user=user,
                        message=message,
                        search_query=search_query,
                        selected_profile=selected_profile,
                        strict_entity_filter=strict_entity_filter,
                        entities=query_entities,
                        route=route,
                    )
                elif intent == "compare_query":
                    deterministic_answer, search_results = await self._handle_compare_intent(
                        db=db,
                        user=user,
                        message=message,
                        search_query=search_query,
                        selected_profile=selected_profile,
                        entities=query_entities,
                    )
                elif intent == "statistics_query":
                    deterministic_answer, search_results = await self._handle_statistics_intent(
                        db=db,
                        user=user,
                        message=message,
                        search_query=search_query,
                        selected_profile=selected_profile,
                        entities=query_entities,
                    )
                elif intent == "schedule_query":
                    deterministic_answer, search_results = await self._handle_schedule_intent(
                        db=db,
                        user=user,
                        message=message,
                        search_query=search_query,
                        selected_profile=selected_profile,
                        entities=query_entities,
                    )

                if deterministic_answer:
                    await emit_status("reasoner", "根拠を整理しています...")
                    _ctx, det_sources = self._format_search_results(search_results or [])
                    sources = det_sources
                    deterministic_answer = self._append_audit_citations(
                        self._enforce_answer_style(deterministic_answer, selected_profile),
                        det_sources,
                    )
                    await self.conversation_service.save_message(
                        conversation_id, "user", message, db=db
                    )
                    await self.conversation_service.save_message(
                        conversation_id, "assistant", deterministic_answer, db=db
                    )
                    assistant_content = deterministic_answer
                    await self._record_usage_event(
                        db=db,
                        user=user,
                        conversation_id=conversation_id,
                        message=message,
                        answer_text=assistant_content,
                        intent=intent,
                        selected_profile=selected_profile,
                        search_results=search_results,
                        sources=sources,
                        status="success",
                        started_at=started_at,
                    )
                    yield deterministic_answer
                    return
            else:
                async def _graph_retriever(state: QAState) -> List[Dict[str, Any]]:
                    return await self._retrieve_with_intent_plan(
                        db=db,
                        user=user,
                        intent=str(state.get("intent") or intent),
                        message=message,
                        search_query=str(state.get("search_query") or search_query),
                        selected_profile=selected_profile,
                        strict_entity_filter=bool(state.get("strict_entity_filter", strict_entity_filter)),
                        query_entities=list(state.get("query_entities") or query_entities),
                        top_k=int(state.get("top_k") or 8),
                        include_relation=bool(state.get("include_relation", True)),
                    )

                orchestrator = LangGraphQAOrchestrator(
                    retriever_fn=_graph_retriever,
                    formatter_fn=self._format_search_results,
                    grounding_fn=self._has_anchor_grounding,
                    no_evidence_fn=self._safe_no_evidence_answer,
                )
                graph_state = await orchestrator.run(
                    QAState(
                        message=message,
                        selected_profile=selected_profile,
                        intent=intent,
                        search_query=search_query,
                        query_entities=query_entities,
                        must_terms=must_terms,
                        strict_entity_filter=strict_entity_filter,
                        top_k=10 if intent == "layout_query" else 8,
                        include_relation=(intent != "layout_query"),
                    )
                )
                search_results = list(graph_state.get("search_results") or [])
                await emit_status("reasoner", "関連する根拠を整理しています...")
                logger.info(
                    "[qa_orchestration] mode=%s total_ms=%s node_ms=%s intent=%s hits=%s critic_passed=%s no_evidence=%s reason=%s",
                    graph_state.get("orchestration_mode"),
                    graph_state.get("orchestration_total_ms"),
                    graph_state.get("node_metrics_ms", {}),
                    intent,
                    len(search_results),
                    graph_state.get("critic_passed"),
                    graph_state.get("no_evidence"),
                    graph_state.get("critic_reason_code"),
                )

            if (
                self._relation_enabled_for_profile(selected_profile)
                and self._is_relation_presentation_query(message)
                and self._should_force_relation_answer(search_results, query_text=message)
            ):
                relation_answer = self._build_relation_answer(search_results)
                if not relation_answer:
                    logger.info("関係表示質問の一次結果が空。原文クエリで関係索引を再検索します。")
                    direct_relation_results = await self.relation_search_service.search_relations(
                        db=db,
                        user=user,
                        query_text=message,
                        top_k=8,
                        kb_profile=None,
                    )
                    if direct_relation_results:
                        search_results = direct_relation_results
                        relation_answer = self._build_relation_answer(search_results)
                if relation_answer:
                    _ctx, rel_sources = self._format_search_results(search_results)
                    sources = rel_sources
                    relation_answer = self._append_audit_citations(
                        self._enforce_answer_style(relation_answer, selected_profile),
                        rel_sources,
                    )
                    await self.conversation_service.save_message(
                        conversation_id, "user", message, db=db
                    )
                    await self.conversation_service.save_message(
                        conversation_id, "assistant", relation_answer, db=db
                    )
                    assistant_content = relation_answer
                    await self._record_usage_event(
                        db=db,
                        user=user,
                        conversation_id=conversation_id,
                        message=message,
                        answer_text=assistant_content,
                        intent=intent,
                        selected_profile=selected_profile,
                        search_results=search_results,
                        sources=sources,
                        status="success",
                        started_at=started_at,
                    )
                    yield relation_answer
                    return

            logger.info(f"检索完成，找到 {len(search_results)} 个相关文档")
            await emit_status("critic", "回答の妥当性を確認しています...")

            if graph_state and graph_state.get("no_evidence"):
                no_evidence_answer = str(graph_state.get("answer_text") or self._safe_no_evidence_answer())
                reason_code = str(graph_state.get("critic_reason_code") or "NO_EVIDENCE")
                reason_message = str(graph_state.get("critic_reason_message") or "根拠不足")
                await emit_status("critic", f"回答保留: {reason_message}", reason_code=reason_code, reason_message=reason_message)
                await self.conversation_service.save_message(
                    conversation_id, "user", message, db=db
                )
                await self.conversation_service.save_message(
                    conversation_id, "assistant", no_evidence_answer, db=db
                )
                assistant_content = no_evidence_answer
                await self._record_usage_event(
                    db=db,
                    user=user,
                    conversation_id=conversation_id,
                    message=message,
                    answer_text=assistant_content,
                    intent=intent,
                    selected_profile=selected_profile,
                    search_results=search_results,
                    sources=sources,
                    status="no_evidence",
                    started_at=started_at,
                    error_type=reason_code,
                    error_message=reason_message,
                )
                yield no_evidence_answer
                return
            if (not graph_state) and (not self._is_relation_presentation_query(message)) and (
                not self._has_anchor_grounding(message, search_results, selected_profile=selected_profile)
            ):
                no_evidence_answer = self._safe_no_evidence_answer()
                await self.conversation_service.save_message(
                    conversation_id, "user", message, db=db
                )
                await self.conversation_service.save_message(
                    conversation_id, "assistant", no_evidence_answer, db=db
                )
                assistant_content = no_evidence_answer
                await self._record_usage_event(
                    db=db,
                    user=user,
                    conversation_id=conversation_id,
                    message=message,
                    answer_text=assistant_content,
                    intent=intent,
                    selected_profile=selected_profile,
                    search_results=search_results,
                    sources=sources,
                    status="no_evidence",
                    started_at=started_at,
                )
                yield no_evidence_answer
                return

            if not search_results:
                no_evidence_answer = self._safe_no_evidence_answer()
                await self.conversation_service.save_message(
                    conversation_id, "user", message, db=db
                )
                await self.conversation_service.save_message(
                    conversation_id, "assistant", no_evidence_answer, db=db
                )
                assistant_content = no_evidence_answer
                await self._record_usage_event(
                    db=db,
                    user=user,
                    conversation_id=conversation_id,
                    message=message,
                    answer_text=assistant_content,
                    intent=intent,
                    selected_profile=selected_profile,
                    search_results=search_results,
                    sources=sources,
                    status="no_evidence",
                    started_at=started_at,
                )
                yield no_evidence_answer
                return
            
            await emit_status("answer", "回答を生成しています...")
            if graph_state:
                context = str(graph_state.get("context") or "")
                sources = list(graph_state.get("sources") or [])
                if (not context) or (not sources):
                    context, sources = self._format_search_results(search_results)
            else:
                context, sources = self._format_search_results(search_results)
            
            history = await self.conversation_service.get_conversation_history(conversation_id, db=db)
            
            prompt = self.prompt_service.build_rag_prompt(
                context=context,
                history=history,
                query=message,
                sources=sources
            )
            
            messages = [
                {"role": "system", "content": self._profile_system_instruction(selected_profile)},
                {"role": "user", "content": prompt}
            ]
            
            await self.conversation_service.save_message(
                conversation_id, "user", message, db=db
            )
            
            logger.info("开始调用OpenAI Chat API（流式）")
            chunk_count = 0
            llm_status = "success"
            llm_error_type = ""
            llm_error_detail = ""
            
            try:
                async for chunk in self.chat_client.stream_chat(messages):
                    assistant_content += chunk
                    chunk_count += 1
                    yield chunk
                
                logger.info(f"OpenAI响应完成，共 {chunk_count} 个chunk，总长度 {len(assistant_content)}")
                audit_block = self._build_audit_citation_block(sources)
                if audit_block:
                    assistant_content = f"{assistant_content.rstrip()}\n{audit_block}\n"
                    yield f"\n{audit_block}\n"
                assistant_content = self._enforce_answer_style(assistant_content, selected_profile)
                
            except Exception as e:
                error_type = type(e).__name__
                error_detail = str(e)
                llm_status = "error"
                llm_error_type = error_type
                llm_error_detail = error_detail
                logger.error(f"OpenAI API调用失败: {error_type}: {error_detail}", exc_info=True)
                
                if "rate_limit" in error_detail.lower() or "RateLimitError" in error_type:
                    error_msg = "AIサービスのリクエストが多すぎます。しばらくしてから再試行してください。"
                elif "authentication" in error_detail.lower() or "AuthenticationError" in error_type:
                    error_msg = "AIサービス認証に失敗しました。管理者に連絡してください。"
                elif "timeout" in error_detail.lower() or "Timeout" in error_type:
                    error_msg = "AIサービスの応答がタイムアウトしました。"
                elif "connection" in error_detail.lower() or "Connection" in error_type:
                    error_msg = "AIサービスに接続できません。ネットワークを確認してください。"
                else:
                    error_msg = f"AIサービスは一時的に利用できません: {error_detail[:100]} (type: {error_type})"
                
                yield error_msg
                assistant_content = error_msg
            
            if assistant_content:
                await self.conversation_service.save_message(
                    conversation_id, "assistant", assistant_content, db=db
                )
                await self._record_usage_event(
                    db=db,
                    user=user,
                    conversation_id=conversation_id,
                    message=message,
                    answer_text=assistant_content,
                    intent=intent,
                    selected_profile=selected_profile,
                    search_results=search_results,
                    sources=sources,
                    status=llm_status,
                    started_at=started_at,
                    error_type=llm_error_type or None,
                    error_message=llm_error_detail or None,
                )
            
        except Exception as e:
            error_type = type(e).__name__
            error_detail = str(e)
            logger.error(f"处理用户消息失败: {error_type}: {error_detail}", exc_info=True)
            try:
                if conversation_id:
                    await self._record_usage_event(
                        db=db,
                        user=user,
                        conversation_id=conversation_id,
                        message=message,
                        answer_text=assistant_content,
                        intent=intent,
                        selected_profile=selected_profile,
                        search_results=search_results,
                        sources=sources,
                        status="error",
                        started_at=started_at,
                        error_type=error_type,
                        error_message=error_detail,
                    )
            except Exception:
                pass
            
            if "archived" in error_detail.lower():
                yield "この会話はアーカイブ済みのため続行できません。新しい会話を作成してください。"
            elif "database" in error_detail.lower() or "Database" in error_type:
                yield "データベース処理に失敗しました。しばらくしてから再試行してください。"
            elif "embedding" in error_detail.lower() or "Embedding" in error_type:
                yield "埋め込み生成に失敗しました。再試行するか管理者に連絡してください。"
            elif "search" in error_detail.lower() or "Search" in error_type:
                yield "ナレッジ検索に失敗しました。しばらくしてから再試行してください。"
            else:
                yield f"メッセージ処理中にエラーが発生しました: {error_detail[:100]} (type: {error_type})"
    
    async def get_conversation_history(
        self,
        user_id: int,
        conversation_id: Optional[str] = None
    ) -> List[Dict[str, str]]:
        """
        获取对话历史
        
        Args:
            user_id: 用户ID
            conversation_id: 会话ID（可选，如果不提供则使用当前会话）
            
        Returns:
            对话历史列表
        """
        if not conversation_id:
            conversation_id = await self.conversation_service.get_current_conversation(user_id)
        
        if not conversation_id:
            return []
        
        return await self.conversation_service.get_conversation_history(conversation_id)
    
    async def create_new_conversation(self, user_id: int) -> str:
        """
        创建新会话
        
        Args:
            user_id: 用户ID
            
        Returns:
            新会话ID
        """
        return await self.conversation_service.create_conversation(user_id)
    
    async def clear_conversation(self, conversation_id: str) -> bool:
        """
        清空对话历史
        
        Args:
            conversation_id: 会话ID
            
        Returns:
            是否成功
        """
        return await self.conversation_service.clear_conversation(conversation_id)


chat_service = ChatService()
