from typing import Optional
from fastapi import APIRouter, Query

from app.core.response import success, error, ErrorCode
from app.core.container import container
from app.models.schemas import CreateTaskRequest, TaskType, TaskStatus

router = APIRouter(prefix="/api/v1/tasks", tags=["Task Management"])


@router.post("")
async def create_task(request: CreateTaskRequest):
    task_manager = container.get_service("task_manager")
    
    task_id = task_manager.create_task(task_type=request.task_type, params=request.params)
    
    if request.timeout:
        task_manager.set_timeout(task_id, request.timeout)
    
    task = task_manager.get_task(task_id)
    return success(data={
        "task_id": task.task_id,
        "task_type": task.task_type.value,
        "status": task.status.value,
        "progress": task.progress,
        "created_at": task.created_at
    }, message="Task created successfully")


@router.get("/{task_id}")
async def get_task(task_id: str):
    task_manager = container.get_service("task_manager")
    
    task = task_manager.get_task(task_id)
    if not task:
        return error(code=ErrorCode.NOT_FOUND, message=f"Task {task_id} not found")
    
    return success(data={
        "task_id": task.task_id,
        "task_type": task.task_type.value,
        "status": task.status.value,
        "progress": task.progress,
        "message": task.message,
        "result": task.result,
        "error": task.error,
        "params": task.params,
        "created_at": task.created_at,
        "updated_at": task.updated_at
    })


@router.get("")
async def list_tasks(
    status: Optional[TaskStatus] = Query(default=None, description="Filter by status"),
    task_type: Optional[TaskType] = Query(default=None, description="Filter by task type"),
    page: int = Query(default=1, ge=1, description="Page number"),
    page_size: int = Query(default=20, ge=1, le=100, description="Page size")
):
    task_manager = container.get_service("task_manager")
    
    tasks = task_manager.list_tasks(status_filter=status, task_type_filter=task_type)
    
    start = (page - 1) * page_size
    end = start + page_size
    paginated_tasks = tasks[start:end]
    
    task_list = []
    for task in paginated_tasks:
        task_list.append({
            "task_id": task.task_id,
            "task_type": task.task_type.value,
            "status": task.status.value,
            "progress": task.progress,
            "message": task.message,
            "created_at": task.created_at,
            "updated_at": task.updated_at
        })
    
    return success(data={
        "tasks": task_list,
        "total": len(tasks),
        "page": page,
        "page_size": page_size
    })


@router.delete("/{task_id}")
async def cancel_task(task_id: str):
    task_manager = container.get_service("task_manager")
    
    task = task_manager.get_task(task_id)
    if not task:
        return error(code=ErrorCode.NOT_FOUND, message=f"Task {task_id} not found")
    
    if task.status in [TaskStatus.SUCCESS, TaskStatus.FAILED, TaskStatus.CANCELLED]:
        return success(data={
            "task_id": task_id,
            "status": task.status.value
        }, message="Task is already in terminal state")
    
    await task_manager.cancel_task(task_id)
    return success(message="Task cancelled successfully")
