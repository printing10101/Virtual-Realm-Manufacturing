"""
灵境制造 - API 版本管理中间件
为每个响应添加版本信息和弃用警告
"""
from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

CURRENT_API_VERSION = "v1"
API_VERSIONS = {
    "v1": {
        "status": "current",
        "release_date": "2026-01-01",
        "sunset_date": None,
        "description": "当前版本"
    },
    "v2": {
        "status": "planned",
        "release_date": None,
        "sunset_date": None,
        "description": "计划中"
    }
}

DEPRECATED_VERSIONS = {"v1"}


class APIVersionMiddleware(BaseHTTPMiddleware):
    """API 版本管理中间件"""

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Any]
    ) -> Response:
        path: str = request.url.path

        # 跳过非 API 路径
        if not path.startswith("/api/"):
            return await call_next(request)

        # 提取版本
        version: str | None = None
        for v in API_VERSIONS:
            if f"/api/{v}/" in path:
                version = v
                break

        response: Response = await call_next(request)

        # 添加版本响应头
        if version:
            response.headers["X-API-Version"] = version

            # 添加弃用警告
            if version in DEPRECATED_VERSIONS:
                v_info = API_VERSIONS[version]
                response.headers["X-API-Deprecated"] = "true"
                response.headers["X-API-Deprecation-Notice"] = (
                    f"API {version} 已弃用，请升级到最新版本"
                )
                if v_info.get("sunset_date"):
                    response.headers["Sunset"] = v_info["sunset_date"]

            # 添加当前版本信息
            if version == CURRENT_API_VERSION:
                response.headers["X-API-Latest-Version"] = CURRENT_API_VERSION

        return response
