"""
用户模型
"""
from sqlalchemy import Column, String, Boolean, DateTime, Enum
from sqlalchemy.sql import func
from app.models.base import Base, BIGINT_TYPE
import enum


class UserRole(enum.Enum):
    USER = "USER"
    ADMIN = "ADMIN"


class User(Base):
    
    __tablename__ = "users"
    
    id = Column(BIGINT_TYPE, primary_key=True, autoincrement=True, comment='用户唯一标识')
    username = Column(String(255), unique=True, nullable=False, index=True, comment='用户名，唯一')
    email = Column(String(255), unique=True, nullable=False, index=True, comment='邮箱，唯一')
    password = Column(String(255), nullable=False, comment='加密后的密码')
    # Use non-native enum for cross-DB compatibility and to avoid PG enum-type creation races.
    role = Column(
        Enum(
            UserRole,
            native_enum=False,
            validate_strings=True,
            create_constraint=False,
            length=20,
        ),
        nullable=False,
        default=UserRole.USER,
        comment='用户角色',
    )
    org_tags = Column(String(255), nullable=True, comment='用户所属组织标签，多个用逗号分隔')
    primary_org = Column(String(50), nullable=True, comment='用户主组织标签')
    created_at = Column(DateTime, server_default=func.now(), comment='创建时间')
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment='更新时间')
    
    def __repr__(self):
        return f"<User(id={self.id}, username={self.username}, role={self.role.value})>"
