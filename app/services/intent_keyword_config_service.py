"""
意图关键词配置服务（DB 持久化 + 运行时热更新）
"""
from __future__ import annotations

import json
from datetime import datetime
from typing import Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.system import SystemSetting
from app.services.intent_keywords import (
    KEYWORD_CATEGORY_ORDER,
    KEYWORD_LABELS,
    apply_runtime_keywords,
    export_runtime_keywords,
)


INTENT_KEYWORD_SETTING_KEY = "kb.intent_keywords.v1"


class IntentKeywordConfigService:
    @staticmethod
    def _normalize_categories(categories: Dict[str, List[str]]) -> Dict[str, List[str]]:
        payload: Dict[str, List[str]] = {}
        for key in KEYWORD_CATEGORY_ORDER:
            values = categories.get(key, [])
            normalized: List[str] = []
            seen = set()
            for raw in values:
                v = (raw or "").strip().lower()
                if not v or v in seen:
                    continue
                seen.add(v)
                normalized.append(v)
            payload[key] = normalized
        return payload

    @staticmethod
    def _shape_response(categories: Dict[str, List[str]], updated_at: Optional[datetime]) -> Dict[str, object]:
        return {
            "categories": [
                {
                    "key": key,
                    "label": KEYWORD_LABELS.get(key, key),
                    "keywords": categories.get(key, []),
                }
                for key in KEYWORD_CATEGORY_ORDER
            ],
            "updated_at": updated_at,
        }

    async def get_config(self, db: AsyncSession) -> Dict[str, object]:
        row = await db.execute(
            select(SystemSetting).where(SystemSetting.key == INTENT_KEYWORD_SETTING_KEY)
        )
        setting = row.scalar_one_or_none()
        if not setting:
            runtime_data = export_runtime_keywords()
            return self._shape_response(runtime_data, None)

        try:
            parsed = json.loads(setting.value or "{}")
            if not isinstance(parsed, dict):
                parsed = {}
        except Exception:
            parsed = {}

        normalized = self._normalize_categories(parsed) if parsed else export_runtime_keywords()
        runtime_data = apply_runtime_keywords(normalized)
        return self._shape_response(runtime_data, setting.updated_at)

    async def sync_runtime_from_db(self, db: AsyncSession) -> None:
        row = await db.execute(
            select(SystemSetting).where(SystemSetting.key == INTENT_KEYWORD_SETTING_KEY)
        )
        setting = row.scalar_one_or_none()
        if not setting:
            return
        try:
            parsed = json.loads(setting.value or "{}")
            if isinstance(parsed, dict):
                normalized = self._normalize_categories(parsed)
                apply_runtime_keywords(normalized)
        except Exception:
            return

    async def update_config(self, db: AsyncSession, categories: Dict[str, List[str]]) -> Dict[str, object]:
        normalized = self._normalize_categories(categories)
        runtime_data = apply_runtime_keywords(normalized)
        payload_str = json.dumps(runtime_data, ensure_ascii=False)

        row = await db.execute(
            select(SystemSetting).where(SystemSetting.key == INTENT_KEYWORD_SETTING_KEY)
        )
        setting = row.scalar_one_or_none()
        if setting:
            setting.value = payload_str
        else:
            db.add(SystemSetting(key=INTENT_KEYWORD_SETTING_KEY, value=payload_str))

        await db.commit()

        row2 = await db.execute(
            select(SystemSetting).where(SystemSetting.key == INTENT_KEYWORD_SETTING_KEY)
        )
        latest = row2.scalar_one_or_none()
        return self._shape_response(runtime_data, latest.updated_at if latest else None)


intent_keyword_config_service = IntentKeywordConfigService()
