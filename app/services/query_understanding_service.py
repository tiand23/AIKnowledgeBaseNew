"""
查询理解服务（语义归一）

输出统一结构：
- intent: 问题意图
- rewritten_query: 归一化检索查询
- entities: 实体候选（人名/系统名等）
- must_terms: 强约束词（当前与 entities 同步）
"""
from __future__ import annotations

import re
from typing import Dict, List, Any, Tuple

from app.services.intent_keywords import (
    get_generic_topic_terms,
    get_layout_query_keys,
)
from app.services.intent_router_service import intent_router_service


class QueryUnderstandingService:

    _HONORIFICS_RE = re.compile(r"(さん|様|氏|ちゃん|くん)$")
    _PARTICLE_TAIL_RE = re.compile(r"(の|は|が|を|に|で|と|って).*$")

    def understand(self, query: str, profile_terms: str = "") -> Dict[str, object]:
        text = (query or "").strip()
        route = intent_router_service.parse(text)
        intent = route.get("intent", "fact_lookup")

        normalized = self._normalize_query(text)
        entity_signals = self._extract_entity_signals(text)
        entities = [str(x["term"]) for x in entity_signals][:8]
        must_terms = [
            str(x["term"])
            for x in entity_signals
            if str(x.get("entity_type") or "") == "named"
            and float(x.get("confidence") or 0.0) >= 0.70
        ][:4]

        rewritten = normalized
        if profile_terms and profile_terms.strip() and profile_terms.strip() not in rewritten:
            rewritten = f"{rewritten} {profile_terms.strip()}"
        if intent == "schedule_query":
            schedule_terms = " スケジュール 工程 期間 開始 終了 工期 日程 進捗"
            if schedule_terms.strip() not in rewritten:
                rewritten = f"{rewritten}{schedule_terms}"
        if intent == "layout_query":
            layout_terms = " " + " ".join(sorted(get_layout_query_keys()))
            if layout_terms.strip() not in rewritten:
                rewritten = f"{rewritten}{layout_terms}"

        return {
            "intent": intent,
            "rewritten_query": rewritten.strip(),
            "entities": entities,
            "must_terms": must_terms,
            "entity_signals": entity_signals,
            "top_n": route.get("top_n"),
            "ask_distance": route.get("ask_distance", False),
        }

    def _normalize_query(self, query: str) -> str:
        t = (query or "").strip()
        t = re.sub(r"[、。,.!?！？:：;；\[\]{}<>\"'`]+", " ", t)
        t = re.sub(r"\s+", " ", t)
        return t

    def _extract_entity_signals(self, query: str) -> List[Dict[str, Any]]:
        text = (query or "").strip()
        candidates: List[Tuple[str, str]] = []

        ja = re.findall(r"([\u3400-\u9fff]{2,16})(?:さん|様|氏|ちゃん|くん)?(?:の|は|が|を|に|で|と|って)", text)
        candidates.extend([(x, "ja_pattern") for x in ja])

        en = re.findall(r"[A-Za-z][A-Za-z0-9_-]{2,32}", text)
        candidates.extend([(x, "latin_token") for x in en])

        uniq: List[Dict[str, Any]] = []
        seen = set()
        for raw, source in candidates:
            token = self._normalize_entity(raw)
            if not token:
                continue
            key = token.lower()
            if key in seen:
                continue
            seen.add(key)
            etype, conf = self._classify_entity(token, source=source)
            uniq.append(
                {
                    "term": token,
                    "entity_type": etype,  # named | topic
                    "confidence": round(conf, 3),
                    "source": source,
                }
            )
        uniq.sort(key=lambda x: float(x.get("confidence") or 0.0), reverse=True)
        return uniq[:10]

    def _classify_entity(self, token: str, source: str) -> Tuple[str, float]:
        t = (token or "").strip()
        generic_terms = set(get_generic_topic_terms())
        if not t:
            return ("topic", 0.0)
        if t in generic_terms:
            return ("topic", 0.2)
        lower = t.lower()
        if lower in {x.lower() for x in generic_terms}:
            return ("topic", 0.2)

        is_named = False
        if re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{2,32}", t):
            is_named = True
        elif re.fullmatch(r"[A-Z]{2,}[0-9_-]{1,16}", t):
            is_named = True
        elif re.fullmatch(r"[\u3400-\u9fff]{2,16}", t):
            is_named = True

        if is_named:
            base = 0.74 if source == "ja_pattern" else 0.68
            return ("named", base)
        return ("topic", 0.45)

    def _normalize_entity(self, token: str) -> str:
        t = (token or "").strip()
        if not t:
            return ""
        t = self._HONORIFICS_RE.sub("", t)
        t = self._PARTICLE_TAIL_RE.sub("", t)
        t = re.sub(r"[\s\-_|\u3000]+", "", t)
        return t.strip()


query_understanding_service = QueryUnderstandingService()
