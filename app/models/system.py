"""
系统配置模型
"""
from sqlalchemy import Column, String, Text, DateTime, Index
from sqlalchemy.sql import func

from app.models.base import Base


class SystemSetting(Base):

    __tablename__ = "system_settings"

    key = Column(String(64), primary_key=True, comment="配置键")
    value = Column(Text, nullable=False, comment="配置值")
    created_at = Column(DateTime, nullable=False, server_default=func.now(), comment="创建时间")
    updated_at = Column(
        DateTime,
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
        comment="更新时间",
    )

    __table_args__ = (
        Index("idx_system_settings_updated_at", "updated_at"),
    )

