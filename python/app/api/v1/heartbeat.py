"""
Heartbeat Scheduling API Routes

Provides RESTful interfaces for task scheduling, budget management,
and execution monitoring.
"""

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/heartbeat", tags=["heartbeat"])


class CreateScheduledTaskRequest(BaseModel):
    """创建调度任务请求"""

    task_id: str = Field(..., description="任务唯一标识符", min_length=1)
    agent_id: str = Field(..., description="执行代理ID", min_length=1)
    schedule: str = Field(
        ..., description="Cron表达式（分 时 日 月 星期）", min_length=1
    )
    task_type: str = Field(
        ...,
        description="任务类型（lnn_inference/lnn_training/lnn_analysis）",
        min_length=1,
    )
    params: Dict[str, Any] = Field(default={}, description="任务参数")
    metadata: Dict[str, Any] = Field(default={}, description="任务元数据")
    max_retries: int = Field(default=3, description="最大重试次数", ge=0, le=10)


class TaskResponse(BaseModel):
    """任务响应"""

    task_id: str
    agent_id: str
    schedule: str
    task_type: str
    status: str
    last_run: Optional[float] = None
    next_run: Optional[float] = None
    retry_count: int = 0
    max_retries: int = 3
    params: Dict[str, Any] = {}
    metadata: Dict[str, Any] = {}


class BudgetCheckResponse(BaseModel):
    """预算检查响应"""

    passed: bool
    status: str
    usages: List[Dict[str, Any]] = []
    warnings: List[str] = []
    blocked_reasons: List[str] = []


class ExecutionResultResponse(BaseModel):
    """执行结果响应"""

    task_id: str
    status: str
    duration_ms: float
    result_data: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    resource_usage: Dict[str, Any] = {}


@router.post("/tasks", response_model=TaskResponse)
async def create_scheduled_task(request: CreateScheduledTaskRequest):
    """创建调度任务"""
    from app.heartbeat.heartbeat import get_scheduler, ScheduledTask, ScheduleStatus

    scheduler = get_scheduler()

    existing = scheduler.wakeup_queue.get_task(request.task_id)
    if existing:
        raise HTTPException(
            status_code=409, detail=f"Task already exists: {request.task_id}"
        )

    task = ScheduledTask(
        task_id=request.task_id,
        agent_id=request.agent_id,
        schedule=request.schedule,
        task_type=request.task_type,
        params=request.params,
        status=ScheduleStatus.PENDING,
        max_retries=request.max_retries,
        metadata=request.metadata,
    )

    created = scheduler.schedule_task(task)

    return TaskResponse(
        task_id=created.task_id,
        agent_id=created.agent_id,
        schedule=created.schedule,
        task_type=created.task_type,
        status=created.status.value,
        last_run=created.last_run,
        next_run=created.next_run,
        retry_count=created.retry_count,
        max_retries=created.max_retries,
        params=created.params,
        metadata=created.metadata,
    )


@router.get("/tasks/{task_id}", response_model=TaskResponse)
async def get_scheduled_task(task_id: str):
    """获取调度任务详情"""
    from app.heartbeat.heartbeat import get_scheduler

    scheduler = get_scheduler()
    task = scheduler.wakeup_queue.get_task(task_id)

    if task is None:
        raise HTTPException(status_code=404, detail=f"Task not found: {task_id}")

    return TaskResponse(
        task_id=task.task_id,
        agent_id=task.agent_id,
        schedule=task.schedule,
        task_type=task.task_type,
        status=task.status.value,
        last_run=task.last_run,
        next_run=task.next_run,
        retry_count=task.retry_count,
        max_retries=task.max_retries,
        params=task.params,
        metadata=task.metadata,
    )


@router.get("/tasks", response_model=List[TaskResponse])
async def list_scheduled_tasks(
    agent_id: Optional[str] = None, status: Optional[str] = None
):
    """列出所有调度任务"""
    from app.heartbeat.heartbeat import get_scheduler, ScheduleStatus

    scheduler = get_scheduler()

    status_enum = ScheduleStatus(status) if status else None
    tasks = scheduler.wakeup_queue.list_tasks(agent_id=agent_id, status=status_enum)

    return [
        TaskResponse(
            task_id=t.task_id,
            agent_id=t.agent_id,
            schedule=t.schedule,
            task_type=t.task_type,
            status=t.status.value,
            last_run=t.last_run,
            next_run=t.next_run,
            retry_count=t.retry_count,
            max_retries=t.max_retries,
            params=t.params,
            metadata=t.metadata,
        )
        for t in tasks
    ]


@router.post("/tasks/{task_id}/trigger")
async def trigger_task_now(task_id: str):
    """立即触发任务执行"""
    from app.heartbeat.heartbeat import get_scheduler

    scheduler = get_scheduler()

    try:
        scheduler.trigger_now(task_id)
        return {"status": "triggered", "task_id": task_id}
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Task not found: {task_id}")


@router.post("/tasks/{task_id}/pause")
async def pause_task(task_id: str):
    """暂停任务"""
    from app.heartbeat.heartbeat import get_scheduler

    scheduler = get_scheduler()
    task = scheduler.wakeup_queue.get_task(task_id)

    if task is None:
        raise HTTPException(status_code=404, detail=f"Task not found: {task_id}")

    scheduler.pause_task(task_id)
    return {"status": "paused", "task_id": task_id}


@router.post("/tasks/{task_id}/resume")
async def resume_task(task_id: str):
    """恢复任务"""
    from app.heartbeat.heartbeat import get_scheduler

    scheduler = get_scheduler()

    try:
        scheduler.resume_task(task_id)
        return {"status": "resumed", "task_id": task_id}
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Task not found: {task_id}")


@router.delete("/tasks/{task_id}")
async def delete_task(task_id: str):
    """删除任务"""
    from app.heartbeat.heartbeat import get_scheduler

    scheduler = get_scheduler()
    deleted = scheduler.wakeup_queue.delete_task(task_id)

    if not deleted:
        raise HTTPException(status_code=404, detail=f"Task not found: {task_id}")

    return {"status": "deleted", "task_id": task_id}


@router.get("/tasks/{task_id}/history")
async def get_task_history(task_id: str, limit: int = 50):
    """获取任务执行历史"""
    from app.heartbeat.heartbeat import get_scheduler

    scheduler = get_scheduler()
    task = scheduler.wakeup_queue.get_task(task_id)

    if task is None:
        raise HTTPException(status_code=404, detail=f"Task not found: {task_id}")

    history = scheduler.wakeup_queue.get_task_history(task_id, limit)
    return {"task_id": task_id, "history": history}


@router.get("/budget/{agent_id}", response_model=BudgetCheckResponse)
async def check_budget(agent_id: str):
    """检查代理预算状态"""
    from app.budget.budget import get_budget_manager

    budget_manager = get_budget_manager()
    result = budget_manager.check_budget(agent_id)

    return BudgetCheckResponse(
        passed=result.passed,
        status=result.status.value,
        usages=[u.to_dict() for u in result.usages],
        warnings=result.warnings,
        blocked_reasons=result.blocked_reasons,
    )


@router.get("/budget/notifications")
async def get_budget_notifications(agent_id: Optional[str] = None, limit: int = 50):
    """获取预算通知"""
    from app.budget.budget import get_budget_manager

    budget_manager = get_budget_manager()
    notifications = budget_manager.get_notifications(agent_id, limit)

    return {"notifications": notifications}


@router.get("/stats")
async def get_scheduler_stats():
    """获取调度器统计信息"""
    from app.heartbeat.heartbeat import get_scheduler
    from app.tasks.execution import get_engine

    scheduler = get_scheduler()
    engine = get_engine()

    return {
        "scheduler": scheduler.get_stats(),
        "engine": {
            "orphaned_sessions": len(engine.session_manager.get_orphaned_sessions()),
        },
    }


@router.post("/recovery/orphaned")
async def recover_orphaned_tasks():
    """手动触发孤立任务恢复"""
    from app.tasks.execution import get_engine

    engine = get_engine()
    recovered = await engine.recover_orphaned_tasks()

    return {"status": "completed", "recovered_count": recovered}
