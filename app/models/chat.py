"""
聊天相关模型
"""
from sqlalchemy import Column, String, DateTime, Text, ForeignKey, Index, Integer
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.models.base import Base, BIGINT_TYPE


class ConversationArchive(Base):
    
    __tablename__ = "conversation_archive"
    
    id = Column(BIGINT_TYPE, primary_key=True, autoincrement=True, comment='主键')
    conversation_id = Column(String(36), unique=True, nullable=False, index=True, comment='会话ID（UUID）')
    user_id = Column(BIGINT_TYPE, ForeignKey('users.id', ondelete='CASCADE'), nullable=False, comment='用户ID')
    archived_at = Column(DateTime, nullable=False, server_default=func.now(), comment='归档时间')
    
    user = relationship("User", backref="archived_conversations")
    messages = relationship("ConversationMessage", back_populates="conversation", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<ConversationArchive(id={self.id}, conversation_id={self.conversation_id}, user_id={self.user_id})>"
    
    __table_args__ = (
        Index('idx_user_archived', 'user_id', 'archived_at'),
    )


class ConversationMessage(Base):
    
    __tablename__ = "conversation_messages"
    
    id = Column(BIGINT_TYPE, primary_key=True, autoincrement=True, comment='主键')
    conversation_id = Column(String(36), ForeignKey('conversation_archive.conversation_id', ondelete='CASCADE'), nullable=False, comment='会话ID')
    role = Column(String(20), nullable=False, comment='角色: user 或 assistant')
    content = Column(Text, nullable=False, comment='消息内容')
    timestamp = Column(DateTime, nullable=False, comment='消息时间戳')
    created_at = Column(DateTime, nullable=False, server_default=func.now(), comment='创建时间')
    
    conversation = relationship("ConversationArchive", back_populates="messages")
    
    def __repr__(self):
        return f"<ConversationMessage(id={self.id}, conversation_id={self.conversation_id}, role={self.role})>"
    
    __table_args__ = (
        Index('idx_conversation_timestamp', 'conversation_id', 'timestamp'),
    )


class ChatUsageEvent(Base):

    __tablename__ = "chat_usage_events"

    id = Column(BIGINT_TYPE, primary_key=True, autoincrement=True, comment="主键")
    user_id = Column(BIGINT_TYPE, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, comment="用户ID")
    conversation_id = Column(String(36), nullable=False, index=True, comment="会话ID")
    question_text = Column(Text, nullable=False, comment="用户问题")
    answer_text = Column(Text, nullable=True, comment="系统回答")
    intent = Column(String(50), nullable=True, comment="识别意图")
    selected_profile = Column(String(32), nullable=True, comment="场景")
    retrieval_count = Column(Integer, nullable=False, default=0, comment="召回条数")
    source_count = Column(Integer, nullable=False, default=0, comment="来源条数")
    source_snapshot = Column(Text, nullable=True, comment="来源快照(JSON)")
    status = Column(String(20), nullable=False, default="success", comment="状态: success/no_evidence/error/archived")
    error_type = Column(String(64), nullable=True, comment="错误类型")
    error_message = Column(Text, nullable=True, comment="错误消息")
    latency_ms = Column(Integer, nullable=True, comment="处理耗时(毫秒)")
    created_at = Column(DateTime, nullable=False, server_default=func.now(), comment="创建时间")

    user = relationship("User", backref="chat_usage_events")

    __table_args__ = (
        Index("idx_chat_usage_user_time", "user_id", "created_at"),
        Index("idx_chat_usage_conv_time", "conversation_id", "created_at"),
        Index("idx_chat_usage_status_time", "status", "created_at"),
    )
