"""
Task Checkout API Routes

Endpoints for atomic task checkout, execution lock management,
task board, and checkout queue processing.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Query, Request

from app.auth.permissions import require_permission
from app.core.response import ErrorCode, error, success
from app.core.safe_errors import safe_error_message
from app.tasks.task_checkout import (
    get_checkout_manager,
    TaskCheckoutManager,
    CheckoutRequest,
    CheckoutStatus,
    CheckoutPriority,
    AgentMode,
    TaskRecord,
)
from app.tasks.execution_lock import (
    LockError,
    LockNotFoundError,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/task-checkout", tags=["Task Checkout"])


def _get_manager() -> TaskCheckoutManager:
    return get_checkout_manager()


@router.post("/tasks")
async def register_task(data: dict):
    manager = _get_manager()

    task_id = data.get("id")
    if not task_id:
        return error(code=ErrorCode.INVALID_REQUEST, message="Task id is required")

    try:
        import json

        blockers = data.get("blockers", [])
        if isinstance(blockers, str):
            blockers = json.loads(blockers)
    except (json.JSONDecodeError, TypeError):
        blockers = []

    task = TaskRecord(
        id=task_id,
        title=data.get("title", ""),
        description=data.get("description", ""),
        task_type=data.get("task_type", "execution"),
        status=data.get("status", "pending"),
        assigned_to=data.get("assigned_to"),
        parent_goal_id=data.get("parent_goal_id"),
        project_id=data.get("project_id"),
        required_gpu_memory=float(data.get("required_gpu_memory", 0.0)),
        blockers=blockers,
        priority=int(data.get("priority", 3)),
    )

    manager.register_task(task)
    return success(data=task.to_dict(), message="Task registered")


@router.post("/checkout")
async def checkout_task(data: dict):
    manager = _get_manager()

    task_id = data.get("task_id")
    agent_id = data.get("agent_id")

    if not task_id or not agent_id:
        return error(
            code=ErrorCode.INVALID_REQUEST, message="task_id and agent_id are required"
        )

    try:
        agent_mode = AgentMode(data.get("agent_mode", "single"))
    except ValueError:
        valid = [m.value for m in AgentMode]
        return error(
            code=ErrorCode.INVALID_REQUEST,
            message=f"Invalid agent_mode. Must be one of: {valid}",
        )

    try:
        priority = CheckoutPriority(int(data.get("priority", 3)))
    except (ValueError, TypeError):
        valid = [f"{p.value}({p.name})" for p in CheckoutPriority]
        return error(
            code=ErrorCode.INVALID_REQUEST,
            message=f"Invalid priority. Must be one of: {valid}",
        )

    request = CheckoutRequest(
        task_id=task_id,
        agent_id=agent_id,
        agent_mode=agent_mode,
        priority=priority,
        required_gpu_memory=float(data.get("required_gpu_memory", 0.0)),
        timeout_hours=float(data.get("timeout_hours", 4.0)),
    )

    result = manager.checkout_task(request)

    if result.status == CheckoutStatus.SUCCESS:
        return success(data=result.to_dict(), message=result.message)
    else:
        return error(
            code=ErrorCode.INVALID_REQUEST,
            message=result.message,
            detail={
                "failure_reason": result.failure_reason.value
                if result.failure_reason
                else None,
                "retry_recommended": result.retry_recommended,
                "retry_delay_minutes": result.retry_delay_minutes,
            },
        )


@router.post("/tasks/{task_id}/heartbeat")
async def heartbeat(task_id: str, data: dict):
    manager = _get_manager()
    agent_id = data.get("agent_id")

    if not agent_id:
        return error(code=ErrorCode.INVALID_REQUEST, message="agent_id is required")

    try:
        lock_store = manager._lock_store
        lock = lock_store.heartbeat(task_id, agent_id)
        return success(data=lock.to_dict(), message="Heartbeat received, lock renewed")
    except LockNotFoundError as e:
        # 修复 [B26]：避免 str(e) 直接进入响应，泄露内部异常详情（如锁ID、内部状态）
        safe = safe_error_message(e, context="task_checkout.heartbeat", fallback="任务心跳失败：锁不存在或已过期")
        logger.error("[task_checkout.heartbeat] error_id=%s: %s", safe["error_id"], e, exc_info=True)
        return error(code=ErrorCode.NOT_FOUND, message=safe["message"], detail={"error_id": safe["error_id"]})
    except LockError as e:
        # 修复 [B26]：避免 str(e) 直接进入响应，泄露内部异常详情
        safe = safe_error_message(e, context="task_checkout.heartbeat", fallback="任务心跳失败，请稍后重试")
        logger.error("[task_checkout.heartbeat] error_id=%s: %s", safe["error_id"], e, exc_info=True)
        return error(code=ErrorCode.INVALID_REQUEST, message=safe["message"], detail={"error_id": safe["error_id"]})


@router.post("/tasks/{task_id}/complete")
async def complete_task(task_id: str, data: dict):
    manager = _get_manager()
    agent_id = data.get("agent_id")

    if not agent_id:
        return error(code=ErrorCode.INVALID_REQUEST, message="agent_id is required")

    result = manager.complete_task(task_id, agent_id)

    if result.status == CheckoutStatus.SUCCESS:
        return success(data=result.to_dict(), message=result.message)
    else:
        return error(
            code=ErrorCode.INVALID_REQUEST,
            message=result.message,
            detail={
                "failure_reason": result.failure_reason.value
                if result.failure_reason
                else None
            },
        )


@router.post("/tasks/{task_id}/fail")
async def fail_task(task_id: str, data: dict):
    manager = _get_manager()
    agent_id = data.get("agent_id")
    reason = data.get("reason", "")

    if not agent_id:
        return error(code=ErrorCode.INVALID_REQUEST, message="agent_id is required")

    result = manager.fail_task(task_id, agent_id, reason)

    if result.status == CheckoutStatus.SUCCESS:
        return success(data=result.to_dict(), message=result.message)
    else:
        return error(
            code=ErrorCode.INVALID_REQUEST,
            message=result.message,
            detail={
                "failure_reason": result.failure_reason.value
                if result.failure_reason
                else None
            },
        )


@router.post("/tasks/{task_id}/abandon")
async def abandon_task(task_id: str, data: dict):
    manager = _get_manager()
    agent_id = data.get("agent_id")

    if not agent_id:
        return error(code=ErrorCode.INVALID_REQUEST, message="agent_id is required")

    result = manager.abandon_task(task_id, agent_id)

    if result.status == CheckoutStatus.SUCCESS:
        return success(data=result.to_dict(), message=result.message)
    else:
        return error(
            code=ErrorCode.INVALID_REQUEST,
            message=result.message,
            detail={
                "failure_reason": result.failure_reason.value
                if result.failure_reason
                else None
            },
        )


@router.get("/board")
async def get_task_board():
    manager = _get_manager()
    board = manager.get_task_board()
    return success(data=board, message="Task board retrieved")


@router.get("/locks")
async def list_locks():
    manager = _get_manager()
    locks = manager.get_all_locks()
    return success(data=locks, message="Locks retrieved")


@router.delete("/locks/{task_id}")
async def force_release_lock(
    task_id: str,
    request: Request,
    _perm: None = Depends(require_permission("task:lock:release")),
):
    """强制释放任务执行锁。

    修复 [B11]：
        1. 移除原 ``admin_id: str = Query("admin", ...)`` 的默认值 "admin"，
           该默认值允许任何未认证调用方以 "admin" 身份释放锁；
        2. 通过 ``Depends(require_permission("task:lock:release"))`` 强制认证，
           未登录调用方将得到 401，权限不足将得到 403；
        3. 操作者身份从认证上下文 ``request.state.username`` 获取，
           并记录到审计链路，确保强制释放操作可追溯。
    """
    # 从认证上下文获取操作者身份，避免使用不可信的客户端默认值
    admin_id = getattr(request.state, "username", None)
    if not admin_id:
        # require_permission 已拦截未认证请求，此处仅为防御性兜底
        return error(
            code=ErrorCode.INVALID_REQUEST,
            message="无法获取操作者身份，请先认证",
        )

    manager = _get_manager()
    result = manager.force_release_lock(task_id, admin_id)

    if result.status == CheckoutStatus.SUCCESS:
        return success(data=result.to_dict(), message=result.message)
    else:
        return error(
            code=ErrorCode.NOT_FOUND,
            message=result.message,
            detail={
                "failure_reason": result.failure_reason.value
                if result.failure_reason
                else None
            },
        )


@router.get("/tasks/{task_id}/history")
async def get_checkout_history(task_id: str):
    manager = _get_manager()
    history = manager.get_task_checkout_history(task_id)

    if history["task"] is None:
        return error(code=ErrorCode.NOT_FOUND, message=f"Task '{task_id}' not found")

    return success(data=history, message="Checkout history retrieved")


@router.get("/agents/{agent_id}/status")
async def get_agent_status(agent_id: str):
    manager = _get_manager()
    status = manager.get_agent_status(agent_id)
    return success(data=status, message="Agent status retrieved")


@router.post("/queue/enqueue")
async def enqueue_checkout(data: dict):
    manager = _get_manager()

    task_id = data.get("task_id")
    agent_id = data.get("agent_id")

    if not task_id or not agent_id:
        return error(
            code=ErrorCode.INVALID_REQUEST, message="task_id and agent_id are required"
        )

    try:
        priority = CheckoutPriority(int(data.get("priority", 3)))
    except (ValueError, TypeError):
        valid = [f"{p.value}({p.name})" for p in CheckoutPriority]
        return error(
            code=ErrorCode.INVALID_REQUEST,
            message=f"Invalid priority. Must be one of: {valid}",
        )

    try:
        agent_mode = AgentMode(data.get("agent_mode", "single"))
    except ValueError:
        agent_mode = AgentMode.SINGLE

    request = CheckoutRequest(
        task_id=task_id,
        agent_id=agent_id,
        agent_mode=agent_mode,
        priority=priority,
        required_gpu_memory=float(data.get("required_gpu_memory", 0.0)),
        timeout_hours=float(data.get("timeout_hours", 4.0)),
    )

    entry = manager.enqueue_checkout(request)
    return success(
        data={
            "task_id": entry.task_id,
            "agent_id": entry.agent_id,
            "priority": entry.priority.name,
            "retry_count": entry.retry_count,
            "created_at": entry.created_at,
        },
        message="Checkout enqueued",
    )


@router.post("/queue/process")
async def process_queue(max_batch: int = Query(10, ge=1, le=100)):
    manager = _get_manager()
    results = manager.process_queue(max_batch)
    return success(
        data=[
            {
                "task_id": r.task_id,
                "agent_id": r.agent_id,
                "success": r.status == CheckoutStatus.SUCCESS,
                "message": r.message,
                "failure_reason": r.failure_reason.value if r.failure_reason else None,
            }
            for r in results
        ],
        message=f"Processed {len(results)} queue entries",
    )


@router.get("/queue")
async def get_queue_status():
    manager = _get_manager()
    queue = manager.get_queue_status()
    return success(data=queue, message="Queue status retrieved")


@router.post("/cleanup")
async def cleanup_expired():
    manager = _get_manager()
    expired = manager.cleanup_expired_locks()
    return success(
        data={
            "expired_locks": expired,
            "count": len(expired),
        },
        message=f"Cleaned up {len(expired)} expired locks",
    )
