"""
通用意图路由服务

目标：不依赖具体人名或固定问句，基于问题语义识别检索策略。
"""
from __future__ import annotations

import re
from typing import Dict, Any

from app.services.intent_keywords import (
    get_compare_query_keys,
    get_flow_query_keys,
    get_layout_query_keys,
    get_schedule_query_keys,
    get_statistics_query_keys,
    get_timeline_query_keys,
)


class IntentRouterService:

    def parse(self, query: str) -> Dict[str, Any]:
        text = (query or "").strip()
        lower = text.lower()

        top_n = self._extract_top_n(lower)
        ask_distance = any(k in lower for k in ("距离今天", "距今", "多久", "多少月", "how long"))
        compare_keys = get_compare_query_keys()
        statistics_keys = get_statistics_query_keys()
        timeline_keys = get_timeline_query_keys()
        schedule_keys = get_schedule_query_keys()
        flow_keys = get_flow_query_keys()
        layout_keys = get_layout_query_keys()

        ask_compare = any(k in lower for k in compare_keys)
        ask_statistics = any(k in lower for k in statistics_keys)
        is_timeline = any(k in lower for k in timeline_keys)
        is_schedule = any(k in lower for k in schedule_keys)
        is_flow = any(k in lower for k in flow_keys)
        layout_hits = sum(1 for k in layout_keys if k in lower)
        flow_hits = sum(1 for k in flow_keys if k in lower)
        is_layout = layout_hits > 0 and layout_hits >= flow_hits

        if ask_compare:
            intent = "compare_query"
        elif ask_statistics:
            intent = "statistics_query"
        elif is_schedule:
            intent = "schedule_query"
        elif is_timeline:
            intent = "timeline_query"
        elif is_layout:
            intent = "layout_query"
        elif is_flow:
            intent = "flow_query"
        else:
            intent = "fact_lookup"

        return {
            "intent": intent,
            "top_n": top_n,
            "ask_distance": ask_distance,
        }

    @staticmethod
    def _extract_top_n(text: str) -> int:
        m = re.search(r"(?:top|近|最近|latest|recent)?\s*([1-9]\d?)\s*(?:个|條|条|件|項|项|つ)?", text)
        if m:
            n = int(m.group(1))
            return min(max(n, 1), 20)
        if "三个" in text or "三個" in text:
            return 3
        if "两个" in text or "兩個" in text:
            return 2
        if "一个" in text or "一個" in text:
            return 1
        return 3


intent_router_service = IntentRouterService()
