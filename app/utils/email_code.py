"""
邮箱验证码工具
"""
import random
from app.core.config import settings


def generate_email_code() -> str:
    return ''.join(random.choices('0123456789', k=settings.EMAIL_CODE_LENGTH))

