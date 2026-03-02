"""
安全相关工具函数（仅保留密码哈希与通用 UUID）。
"""
from passlib.context import CryptContext
import uuid

pwd_context = CryptContext(
    schemes=["pbkdf2_sha256", "bcrypt"],
    deprecated="auto"
)


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def generate_uuid() -> str:
    return str(uuid.uuid4())
