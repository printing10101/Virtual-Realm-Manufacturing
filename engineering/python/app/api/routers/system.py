"""系统域路由注册：健康检查 / 状态 / SSE.

注册端点：
- GET  /api/v1/health          - 主健康检查
- GET  /api/v1/health/ping     - 轻量级存活探测（Docker HEALTHCHECK 使用）
- GET  /api/v1/status          - 系统状态
- SSE  推送端点（由 sse_manager 管理）

设计约束：
- 健康检查端点必须在 unified_auth.PUBLIC_PATHS 中登记为公开路径
- 不应用任何认证装饰器或中间件
- 旧路径 /health 已彻底移除
"""
from __future__ import annotations

from fastapi import FastAPI

from app.api.v1 import health, status


def register(app: FastAPI) -> None:
    """注册系统域路由."""
    app.include_router(health.router)
    # 标准化健康检查端点（公开访问，无认证）:
    #   - GET /api/health       — 主健康检查
    #   - GET /api/health/ping  — 轻量级存活探测（Docker HEALTHCHECK 使用）
    # 两个端点均已在 unified_auth.PUBLIC_PATHS 中登记为公开路径，
    # 不应用任何认证装饰器或中间件。旧路径 /health 已彻底移除。
    app.include_router(health.simple_health_router)
    app.include_router(status.router)
