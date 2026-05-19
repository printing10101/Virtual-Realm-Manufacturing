from __future__ import annotations

import logging
from typing import Optional

from fastapi import Request, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.core.security import decode_token_strict, get_token_ban_list

logger = logging.getLogger(__name__)

AUTH_PUBLIC_PATHS = {
    "/api/v1/auth/register",
    "/api/v1/auth/login",
    "/api/v1/auth/refresh",
    "/api/health",
    "/api/health/ping",
    "/api/metrics",
    "/api/docs",
    "/api/redoc",
    "/api/openapi.json",
    "/health",
}

AUTH_PUBLIC_PREFIXES = [
    "/api/docs",
    "/api/redoc",
    "/api/openapi",
]


class JwtAuthMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, enabled: bool = True):
        super().__init__(app)
        self.enabled = enabled

    def _is_public(self, path: str) -> bool:
        if path in AUTH_PUBLIC_PATHS:
            return True
        for prefix in AUTH_PUBLIC_PREFIXES:
            if path.startswith(prefix):
                return True
        return False

    async def dispatch(self, request: Request, call_next):
        if not self.enabled:
            return await call_next(request)

        path = request.url.path

        if self._is_public(path):
            return await call_next(request)

        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={
                    "code": 401,
                    "message": "未提供认证Token",
                    "detail": "请在Authorization头中提供Bearer Token",
                },
            )

        token = auth_header[7:]
        if not token:
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={
                    "code": 401,
                    "message": "Token为空",
                },
            )

        ban_list = get_token_ban_list()
        if ban_list.is_banned(token):
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={
                    "code": 401,
                    "message": "Token已被撤销，请重新登录",
                },
            )

        payload = decode_token_strict(token, expected_type="access")
        if payload is None:
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={
                    "code": 401,
                    "message": "Token无效或已过期",
                },
            )

        request.state.username = payload.get("sub")
        request.state.user_role = payload.get("role", "user")

        return await call_next(request)


async def get_current_username_role(request: Request = None) -> tuple[str | None, str]:
    if request is not None and hasattr(request.state, "username"):
        return (request.state.username, request.state.user_role)

    try:
        from fastapi import Request as FastAPIRequest
        return ("", "user")
    except ImportError:
        return ("", "user")