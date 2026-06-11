"""
Task Checkout API Routes

Endpoints for atomic task checkout, execution lock management,
task board, and checkout queue processing.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Query

from app.core.response import ErrorCode, error, success
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
        return error(code=ErrorCode.NOT_FOUND, message=str(e))
    except LockError as e:
        return error(code=ErrorCode.INVALID_REQUEST, message=str(e))


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
    task_id: str, admin_id: str = Query("admin", description="Administrator ID")
):
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
