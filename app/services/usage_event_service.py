"""
在线使用事件记录服务
"""
import json
from typing import Any, Dict, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.chat import ChatUsageEvent
from app.utils.logger import get_logger

logger = get_logger(__name__)


class UsageEventService:

    @staticmethod
    def _safe_text(value: Any, limit: int = 4000) -> str:
        text = str(value or "").strip()
        if len(text) <= limit:
            return text
        return text[:limit]

    @staticmethod
    def _build_source_snapshot(sources: Optional[List[Dict[str, Any]]], max_items: int = 10) -> str:
        rows = []
        for s in (sources or [])[:max_items]:
            rows.append(
                {
                    "file_name": s.get("file_name"),
                    "file_md5": s.get("file_md5"),
                    "chunk_id": s.get("chunk_id"),
                    "page": s.get("page"),
                    "sheet": s.get("sheet"),
                    "score": s.get("score"),
                }
            )
        return json.dumps(rows, ensure_ascii=False)

    async def record(
        self,
        db: AsyncSession,
        *,
        user_id: int,
        conversation_id: str,
        question_text: str,
        answer_text: str = "",
        intent: str = "",
        selected_profile: str = "",
        retrieval_count: int = 0,
        sources: Optional[List[Dict[str, Any]]] = None,
        status: str = "success",
        error_type: Optional[str] = None,
        error_message: Optional[str] = None,
        latency_ms: Optional[int] = None,
    ) -> None:
        try:
            row = ChatUsageEvent(
                user_id=int(user_id),
                conversation_id=str(conversation_id or ""),
                question_text=self._safe_text(question_text, limit=8000),
                answer_text=self._safe_text(answer_text, limit=12000),
                intent=(str(intent or "").strip() or None),
                selected_profile=(str(selected_profile or "").strip() or None),
                retrieval_count=max(0, int(retrieval_count or 0)),
                source_count=len(sources or []),
                source_snapshot=self._build_source_snapshot(sources),
                status=(str(status or "success").strip() or "success"),
                error_type=(str(error_type or "").strip() or None),
                error_message=self._safe_text(error_message, limit=2000) if error_message else None,
                latency_ms=(max(0, int(latency_ms)) if latency_ms is not None else None),
            )
            db.add(row)
            await db.commit()
        except Exception as e:
            await db.rollback()
            logger.warning("chat usage event 持久化失败（忽略）: %s", e)


usage_event_service = UsageEventService()
