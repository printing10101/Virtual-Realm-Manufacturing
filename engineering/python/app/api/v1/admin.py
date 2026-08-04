"""管理员端点（优雅关闭等）。"""

import asyncio
import logging

from fastapi import APIRouter

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/admin", tags=["Admin"])


@router.post("/shutdown")
async def admin_shutdown():
    """触发后端优雅关闭（由 Tauri Rust 端调用）。"""
    logger.info("[shutdown] received graceful shutdown request from sidecar host")
    from app.main import _async_shutdown, _IDLE_AUTO_SHUTDOWN_ENABLED

    if _IDLE_AUTO_SHUTDOWN_ENABLED:
        return {"status": "skipped", "reason": "idle auto shutdown is active"}

    shutdown_task = asyncio.create_task(_async_shutdown())
    shutdown_task.add_done_callback(lambda t: logger.info("[shutdown] backend shutdown completed"))
    return {"status": "shutting_down"}
