"""
主数据初始化服务（幂等）
"""
from __future__ import annotations

from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.organization import OrganizationTag
from app.models.user import User, UserRole
from app.utils.logger import get_logger

logger = get_logger(__name__)


class MasterDataService:
    DEFAULT_ORG_TAG_ID = "DEFAULT"
    DEFAULT_ORG_TAG_NAME = "全体公開"
    DEFAULT_ORG_TAG_DESC = "全ユーザーが参照可能なデフォルト組織タグ"

    async def ensure_default_org_tag(
        self,
        db: AsyncSession,
        creator_user_id: Optional[int] = None,
    ) -> bool:
        """
        确保 DEFAULT 组织标签存在（幂等）。
        返回值：True=本次新建，False=已存在或无法创建。
        """
        row = await db.execute(
            select(OrganizationTag).where(OrganizationTag.tag_id == self.DEFAULT_ORG_TAG_ID)
        )
        existing = row.scalar_one_or_none()
        if existing:
            return False

        creator_id = creator_user_id
        if not creator_id:
            admin_row = await db.execute(
                select(User.id).where(User.role == UserRole.ADMIN).order_by(User.id.asc()).limit(1)
            )
            creator_id = admin_row.scalar_one_or_none()
        if not creator_id:
            user_row = await db.execute(
                select(User.id).order_by(User.id.asc()).limit(1)
            )
            creator_id = user_row.scalar_one_or_none()

        if not creator_id:
            logger.info("跳过 DEFAULT 组织标签初始化：当前无可用创建者用户")
            return False

        db.add(
            OrganizationTag(
                tag_id=self.DEFAULT_ORG_TAG_ID,
                name=self.DEFAULT_ORG_TAG_NAME,
                description=self.DEFAULT_ORG_TAG_DESC,
                parent_tag=None,
                created_by=int(creator_id),
            )
        )
        await db.flush()
        logger.info("已初始化主数据组织标签: %s", self.DEFAULT_ORG_TAG_ID)
        return True


master_data_service = MasterDataService()
