"""
LangGraph-based lightweight QA orchestrator.

Pipeline:
Planner -> Retriever -> Reasoner -> Critic -> Answer

This orchestrator is intentionally minimal and delegates heavy logic
(retrieval, evidence formatting, grounding checks) to caller-provided callbacks.
"""

from __future__ import annotations

import time
from typing import Any, Awaitable, Callable, Dict, List, Optional, TypedDict

from app.utils.logger import get_logger

logger = get_logger(__name__)


class QAState(TypedDict, total=False):
    message: str
    selected_profile: str

    # planner outputs
    intent: str
    search_query: str
    query_entities: List[str]
    must_terms: List[str]
    strict_entity_filter: bool
    top_k: int
    include_relation: bool

    # retriever outputs
    search_results: List[Dict[str, Any]]
    context: str
    sources: List[Dict[str, Any]]

    # reasoner/critic outputs
    reasoning_notes: str
    critic_passed: bool
    no_evidence: bool
    critic_reason_code: str
    critic_reason_message: str
    answer_text: str

    # observability outputs
    node_metrics_ms: Dict[str, int]
    orchestration_total_ms: int
    orchestration_mode: str


RetrieverFn = Callable[[QAState], Awaitable[List[Dict[str, Any]]]]
FormatterFn = Callable[[List[Dict[str, Any]]], tuple[str, List[Dict[str, Any]]]]
GroundingFn = Callable[[str, List[Dict[str, Any]], Optional[str]], bool]
NoEvidenceFn = Callable[[], str]


class LangGraphQAOrchestrator:
    """Minimal orchestration layer for QA flow with LangGraph."""

    def __init__(
        self,
        retriever_fn: RetrieverFn,
        formatter_fn: FormatterFn,
        grounding_fn: GroundingFn,
        no_evidence_fn: NoEvidenceFn,
    ) -> None:
        self._retriever_fn = retriever_fn
        self._formatter_fn = formatter_fn
        self._grounding_fn = grounding_fn
        self._no_evidence_fn = no_evidence_fn
        self._graph = self._build_graph()

    def _build_graph(self):
        try:
            from langgraph.graph import END, StateGraph
        except Exception as e:
            logger.warning("LangGraph import failed, fallback to sequential mode: %s", e)
            return None

        graph = StateGraph(QAState)
        graph.add_node("planner", self._planner_node_timed)
        graph.add_node("retriever", self._retriever_node_timed)
        graph.add_node("reasoner", self._reasoner_node_timed)
        graph.add_node("critic", self._critic_node_timed)
        graph.add_node("answer", self._answer_node_timed)

        graph.set_entry_point("planner")
        graph.add_edge("planner", "retriever")
        graph.add_edge("retriever", "reasoner")
        graph.add_edge("reasoner", "critic")
        graph.add_edge("critic", "answer")
        graph.add_edge("answer", END)
        return graph.compile()

    async def run(self, init_state: QAState) -> QAState:
        started_at = time.perf_counter()
        if self._graph is None:
            # Sequential fallback when LangGraph is not available.
            state = dict(init_state)
            state["orchestration_mode"] = "sequential_fallback"
            state = await self._planner_node_timed(state)
            state = await self._retriever_node_timed(state)
            state = await self._reasoner_node_timed(state)
            state = await self._critic_node_timed(state)
            state = await self._answer_node_timed(state)
            state["orchestration_total_ms"] = int((time.perf_counter() - started_at) * 1000)
            logger.info(
                "[langgraph] mode=%s total_ms=%s node_ms=%s critic_passed=%s no_evidence=%s reason=%s",
                state.get("orchestration_mode"),
                state.get("orchestration_total_ms"),
                state.get("node_metrics_ms", {}),
                state.get("critic_passed"),
                state.get("no_evidence"),
                state.get("critic_reason_code"),
            )
            return state
        graph_state = await self._graph.ainvoke(init_state)
        graph_state["orchestration_mode"] = "langgraph"
        graph_state["orchestration_total_ms"] = int((time.perf_counter() - started_at) * 1000)
        logger.info(
            "[langgraph] mode=%s total_ms=%s node_ms=%s critic_passed=%s no_evidence=%s reason=%s",
            graph_state.get("orchestration_mode"),
            graph_state.get("orchestration_total_ms"),
            graph_state.get("node_metrics_ms", {}),
            graph_state.get("critic_passed"),
            graph_state.get("no_evidence"),
            graph_state.get("critic_reason_code"),
        )
        return graph_state

    async def _timed_node(
        self,
        state: QAState,
        node_name: str,
        func: Callable[[QAState], Awaitable[QAState]],
    ) -> QAState:
        started_at = time.perf_counter()
        next_state = await func(state)
        node_metrics = dict(next_state.get("node_metrics_ms") or {})
        node_metrics[node_name] = int((time.perf_counter() - started_at) * 1000)
        next_state["node_metrics_ms"] = node_metrics
        return next_state

    async def _planner_node_timed(self, state: QAState) -> QAState:
        return await self._timed_node(state, "planner", self._planner_node)

    async def _retriever_node_timed(self, state: QAState) -> QAState:
        return await self._timed_node(state, "retriever", self._retriever_node)

    async def _reasoner_node_timed(self, state: QAState) -> QAState:
        return await self._timed_node(state, "reasoner", self._reasoner_node)

    async def _critic_node_timed(self, state: QAState) -> QAState:
        return await self._timed_node(state, "critic", self._critic_node)

    async def _answer_node_timed(self, state: QAState) -> QAState:
        return await self._timed_node(state, "answer", self._answer_node)

    async def _planner_node(self, state: QAState) -> QAState:
        intent = str(state.get("intent") or "fact_lookup")
        include_relation = bool(state.get("include_relation", True))
        top_k = int(state.get("top_k") or 8)

        # Lightweight planning: adjust retrieval plan by intent.
        if intent == "layout_query":
            include_relation = False
            top_k = 10
        elif intent in {"flow_query", "relation_query"}:
            include_relation = True
            top_k = max(top_k, 8)

        state["include_relation"] = include_relation
        state["top_k"] = top_k
        return state

    async def _retriever_node(self, state: QAState) -> QAState:
        results = await self._retriever_fn(state)
        state["search_results"] = results or []
        context, sources = self._formatter_fn(state["search_results"])
        state["context"] = context
        state["sources"] = sources
        return state

    async def _reasoner_node(self, state: QAState) -> QAState:
        results = state.get("search_results") or []
        if not results:
            state["reasoning_notes"] = "No retrieval evidence found."
            return state

        top = results[:3]
        lines = []
        for row in top:
            lines.append(
                f"{row.get('file_name', 'unknown')}#chunk={row.get('chunk_id', '-')};"
                f" score={float(row.get('score') or 0.0):.4f}"
            )
        state["reasoning_notes"] = "Top evidence: " + " | ".join(lines)
        return state

    async def _critic_node(self, state: QAState) -> QAState:
        message = str(state.get("message") or "")
        selected_profile = str(state.get("selected_profile") or "")
        results = state.get("search_results") or []

        if not results:
            state["critic_passed"] = False
            state["no_evidence"] = True
            state["critic_reason_code"] = "EVIDENCE_EMPTY"
            state["critic_reason_message"] = "根拠が見つかりませんでした。"
            return state

        scores = [float(x.get("score") or 0.0) for x in results]
        top_score = max(scores) if scores else 0.0
        unique_sources = {
            f"{x.get('file_md5','')}::{x.get('chunk_id','')}::{x.get('page','')}::{x.get('sheet','')}"
            for x in results
        }

        grounded = self._grounding_fn(message, results, selected_profile)
        if not grounded:
            state["critic_passed"] = False
            state["no_evidence"] = True
            state["critic_reason_code"] = "ANCHOR_MISMATCH"
            state["critic_reason_message"] = "質問の対象語と一致する根拠を確認できませんでした。"
            return state

        if len(unique_sources) < 1 or top_score < 0.18:
            state["critic_passed"] = False
            state["no_evidence"] = True
            state["critic_reason_code"] = "EVIDENCE_WEAK"
            state["critic_reason_message"] = "根拠の信頼度が不足しています。条件を具体化して再質問してください。"
            return state

        state["critic_passed"] = True
        state["no_evidence"] = False
        state["critic_reason_code"] = "PASS"
        state["critic_reason_message"] = "根拠整合性チェックを通過しました。"
        return state

    async def _answer_node(self, state: QAState) -> QAState:
        if state.get("no_evidence"):
            state["answer_text"] = self._no_evidence_fn()
        return state
