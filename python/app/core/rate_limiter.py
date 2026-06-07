"""Shared rate limiter instance for the whole application.

Uses slowapi with in-memory storage (no Redis required).
Imported by main.py, auth.py, and lnn.py to apply consistent rate limits.
"""

from __future__ import annotations

import logging
import re

from fastapi import Request
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.core.request_id import get_request_id

logger = logging.getLogger(__name__)

# Shared rate limiter instance (in-memory, keyed by client IP)
limiter = Limiter(key_func=get_remote_address)


async def rate_limit_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    """自定义速率限制错误处理器，返回中文友好提示消息。

    根据不同的速率限制窗口（秒/分钟/小时）动态生成提示文本。
    返回429状态码，并携带 Retry-After 响应头。
    """
    detail = str(exc.detail) if exc.detail else ""

    # 从 slowapi 的 detail 信息中提取限制窗口大小（如 "5 per 1 minute"）
    retry_window_seconds = 60  # 默认回退值
    match = re.search(r"per\s+(\d+)\s+(second|minute|hour)", detail, re.IGNORECASE)
    if match:
        amount = int(match.group(1))
        unit = match.group(2).lower()
        unit_map = {"second": 1, "minute": 60, "hour": 3600}
        retry_window_seconds = amount * unit_map.get(unit, 60)

    # 生成中文友好提示
    if retry_window_seconds >= 3600:
        hours = retry_window_seconds // 3600
        message = f"请求过于频繁，请在{hours}小时后重试"
    elif retry_window_seconds >= 60:
        minutes = retry_window_seconds // 60
        message = f"请求过于频繁，请在{minutes}分钟后重试"
    else:
        message = f"请求过于频繁，请在{retry_window_seconds}秒后重试"

    logger.warning(
        "Rate limit exceeded: path=%s client=%s window=%ds detail=%s",
        request.url.path,
        request.client.host if request.client else "unknown",
        retry_window_seconds,
        detail,
    )

    return JSONResponse(
        status_code=429,
        content={
            "code": 1007,
            "message": message,
            "request_id": get_request_id(),
        },
        headers={"Retry-After": str(retry_window_seconds)},
    )
