"""
速率限制工具
"""

from typing import Optional
from fastapi import Request, HTTPException, status
from app.clients.redis_client import redis_client
from app.core.config import settings


async def check_rate_limit(
    key: str, limit: int, window: int, error_msg: str = "请求过于频繁，请稍后再试"
) -> bool:
    """
    检查速率限制

    Args:
        key: Redis 键
        limit: 限制次数
        window: 时间窗口（秒）
        error_msg: 错误提示

    Returns:
        是否通过检查

    Raises:
        HTTPException: 超过限制时抛出
    """
    count = await redis_client.incr(key, window)

    if count > limit:
        ttl = await redis_client.ttl(key)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"{error_msg}，请在 {ttl} 秒后重试",
        )

    return True


async def get_client_ip(request: Request) -> str:
    """
    获取客户端 IP 地址

    Args:
        request: FastAPI Request 对象

    Returns:
        IP 地址
    """
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()

    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip

    return request.client.host if request.client else "unknown"


async def check_captcha_rate_limit(request: Request) -> bool:

    client_ip = await get_client_ip(request)
    key = f"rate_limit:captcha:{client_ip}"

    rate_config = settings.RATE_LIMITS["captcha"]

    return await check_rate_limit(
        key, rate_config["limit"], rate_config["window"], "图形验证码请求过于频繁"
    )


async def check_email_code_rate_limit(email: str) -> bool:

    key = f"rate_limit:email_code:{email}"

    rate_config = settings.RATE_LIMITS["email_code"]

    return await check_rate_limit(
        key, rate_config["limit"], rate_config["window"], "邮箱验证码请求过于频繁"
    )


async def check_register_rate_limit(request: Request) -> bool:

    client_ip = await get_client_ip(request)
    key = f"rate_limit:register:{client_ip}"

    rate_config = settings.RATE_LIMITS["register"]

    return await check_rate_limit(
        key, rate_config["limit"], rate_config["window"], "注册请求过于频繁"
    )
