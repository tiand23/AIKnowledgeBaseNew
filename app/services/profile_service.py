"""
知识库场景配置服务
"""
from dataclasses import dataclass
from typing import Dict, List, Optional

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.system import SystemSetting


PROFILE_SETTING_KEY = "kb.profile.selected"
LEGACY_PROFILE_MAP = {
    "resume": "general",
    "legal": "policy",
}


@dataclass(frozen=True)
class ProfileStrategy:
    profile_id: str
    name: str
    description: str
    chunk_size: int
    chunk_overlap: int
    enable_experience_index: bool
    enable_relation_index: bool
    enable_xlsx_image_extract: bool
    query_expand_terms: str
    enable_adaptive_ocr: bool = True
    ocr_min_chars_per_page: int = 80
    ocr_min_words_per_page: int = 20
    ocr_min_valid_ratio: float = 0.35
    ocr_doc_trigger_ratio: float = 0.40
    ocr_no_text_streak_trigger: int = 2
    ocr_max_pages: int = 20
    retrieval_weight_vector: float = 0.4
    retrieval_weight_bm25: float = 0.4
    retrieval_weight_relation: float = 0.2
    answer_style: str = "general"


class ProfileService:
    def __init__(self):
        self._profiles: Dict[str, ProfileStrategy] = {
            "general": ProfileStrategy(
                profile_id="general",
                name="汎用ドキュメント",
                description="マニュアル・議事録・社内資料向け。再現率と精度のバランス重視。",
                chunk_size=900,
                chunk_overlap=120,
                enable_experience_index=False,
                enable_relation_index=True,
                enable_xlsx_image_extract=False,
                query_expand_terms="",
                enable_adaptive_ocr=True,
                ocr_min_chars_per_page=70,
                ocr_min_words_per_page=15,
                ocr_min_valid_ratio=0.30,
                ocr_doc_trigger_ratio=0.50,
                ocr_no_text_streak_trigger=2,
                ocr_max_pages=12,
                retrieval_weight_vector=0.40,
                retrieval_weight_bm25=0.40,
                retrieval_weight_relation=0.20,
                answer_style="general",
            ),
            "design": ProfileStrategy(
                profile_id="design",
                name="設計書・アーキテクチャ",
                description="モジュール依存・業務フロー・IF連携・影響範囲分析を強化。",
                chunk_size=1100,
                chunk_overlap=150,
                enable_experience_index=False,
                enable_relation_index=True,
                enable_xlsx_image_extract=True,
                query_expand_terms="設計書 基本設計 詳細設計 IF インターフェース テーブル バッチ 依存 関係 フロー",
                enable_adaptive_ocr=True,
                ocr_min_chars_per_page=100,
                ocr_min_words_per_page=20,
                ocr_min_valid_ratio=0.35,
                ocr_doc_trigger_ratio=0.40,
                ocr_no_text_streak_trigger=2,
                ocr_max_pages=25,
                retrieval_weight_vector=0.30,
                retrieval_weight_bm25=0.25,
                retrieval_weight_relation=0.45,
                answer_style="design",
            ),
            "policy": ProfileStrategy(
                profile_id="policy",
                name="規程・業務プロセス",
                description="条項・施行日・適用範囲・承認経路の検索を強化。",
                chunk_size=950,
                chunk_overlap=140,
                enable_experience_index=False,
                enable_relation_index=False,
                enable_xlsx_image_extract=False,
                query_expand_terms="規程 規定 手順 承認 稟議 申請 施行 適用 範囲 例外",
                enable_adaptive_ocr=True,
                ocr_min_chars_per_page=80,
                ocr_min_words_per_page=18,
                ocr_min_valid_ratio=0.33,
                ocr_doc_trigger_ratio=0.45,
                ocr_no_text_streak_trigger=2,
                ocr_max_pages=15,
                retrieval_weight_vector=0.25,
                retrieval_weight_bm25=0.55,
                retrieval_weight_relation=0.20,
                answer_style="policy",
            ),
            "ops": ProfileStrategy(
                profile_id="ops",
                name="運用・障害対応",
                description="アラート・変更履歴・障害手順・ポストモーテム検索を強化。",
                chunk_size=900,
                chunk_overlap=120,
                enable_experience_index=False,
                enable_relation_index=True,
                enable_xlsx_image_extract=False,
                query_expand_terms="障害 アラート 監視 インシデント 復旧 原因 対応 手順 変更",
                enable_adaptive_ocr=True,
                ocr_min_chars_per_page=70,
                ocr_min_words_per_page=15,
                ocr_min_valid_ratio=0.30,
                ocr_doc_trigger_ratio=0.50,
                ocr_no_text_streak_trigger=2,
                ocr_max_pages=12,
                retrieval_weight_vector=0.30,
                retrieval_weight_bm25=0.35,
                retrieval_weight_relation=0.35,
                answer_style="ops",
            ),
        }

    def list_profile_options(self) -> List[Dict[str, str]]:
        return [
            {
                "profile_id": p.profile_id,
                "name": p.name,
                "description": p.description,
            }
            for p in self._profiles.values()
        ]

    def get_strategy(self, profile_id: Optional[str]) -> ProfileStrategy:
        if profile_id and profile_id in self._profiles:
            return self._profiles[profile_id]
        return self._profiles["general"]

    async def get_selected_profile(self, db: AsyncSession) -> Optional[str]:
        row = await db.execute(
            select(SystemSetting).where(SystemSetting.key == PROFILE_SETTING_KEY)
        )
        setting = row.scalar_one_or_none()
        if not setting:
            return None

        selected = (setting.value or "").strip()
        if selected in self._profiles:
            return selected

        migrated = LEGACY_PROFILE_MAP.get(selected, "general")
        setting.value = migrated
        await db.commit()
        return migrated

    async def ensure_profile_selected(self, db: AsyncSession) -> str:
        profile = await self.get_selected_profile(db)
        if not profile:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="先に初期シナリオ設定を完了してください",
            )
        return profile

    async def select_profile_once(self, db: AsyncSession, profile_id: str) -> str:
        profile_id = (profile_id or "").strip()
        if profile_id not in self._profiles:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="無効なシナリオです",
            )

        row = await db.execute(
            select(SystemSetting).where(SystemSetting.key == PROFILE_SETTING_KEY)
        )
        setting = row.scalar_one_or_none()
        if setting:
            if setting.value == profile_id:
                return setting.value
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="シナリオは固定されています。変更する場合はデータを初期化してください",
            )

        db.add(SystemSetting(key=PROFILE_SETTING_KEY, value=profile_id))
        await db.commit()
        return profile_id


profile_service = ProfileService()
