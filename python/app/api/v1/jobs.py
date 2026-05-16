"""
Jobs API - Async task management and SSE streaming.
"""

import asyncio
import logging
from typing import Optional

from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse

from app.core.response import ErrorCode, error, success
from app.core.task_manager import TaskType, TaskStatus
from app.core.task_system import AsyncTaskManager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/jobs", tags=["Async Jobs"])
task_manager = AsyncTaskManager()


@router.get("/{job_id}")
async def get_job(job_id: str):
    """Get job status and details"""
    record = await task_manager.get_task(job_id)
    if not record:
        return error(code=ErrorCode.NOT_FOUND, message=f"Job '{job_id}' not found")
    return success(data=record.to_dict(), message="Job retrieved")


@router.get("/{job_id}/stream")
async def stream_job_events(job_id: str):
    """SSE endpoint for real-time job event streaming"""
    record = await task_manager.get_task(job_id)
    if not record:
        return error(code=ErrorCode.NOT_FOUND, message=f"Job '{job_id}' not found")

    queue = task_manager.subscribe(job_id)

    async def event_generator():
        try:
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=30.0)
                    yield event
                except asyncio.TimeoutError:
                    record = await task_manager.get_task(job_id)
                    if record and record.status in (
                        TaskStatus.COMPLETED,
                        TaskStatus.FAILED,
                        TaskStatus.CANCELLED,
                    ):
                        yield f'event: done\ndata: {{"status": "{record.status.value}"}}\n\n'
                        break
                    yield ": heartbeat\n\n"
        except asyncio.CancelledError:
            logger.info(f"SSE stream cancelled for job {job_id}")
        finally:
            task_manager.unsubscribe(job_id, queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/{job_id}/cancel")
async def cancel_job(job_id: str):
    """Cancel a running job"""
    result = await task_manager.cancel_task(job_id)
    if not result:
        return error(
            code=ErrorCode.INVALID_REQUEST, message=f"Cannot cancel job '{job_id}'"
        )
    return success(
        data={"job_id": job_id, "status": "cancelled"}, message="Job cancelled"
    )


@router.delete("/{job_id}")
async def delete_job(job_id: str):
    """Cancel a running job (RESTful DELETE alias)"""
    result = await task_manager.cancel_task(job_id)
    if not result:
        return error(
            code=ErrorCode.INVALID_REQUEST, message=f"Cannot cancel job '{job_id}'"
        )
    return success(
        data={"job_id": job_id, "status": "cancelled"}, message="Job cancelled"
    )


@router.get("")
async def list_jobs(
    task_type: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """List all jobs with filters"""
    try:
        tt = TaskType(task_type) if task_type else None
    except ValueError:
        valid_types = [t.value for t in TaskType]
        return error(
            code=ErrorCode.INVALID_REQUEST,
            message=f"Invalid task_type '{task_type}'. Valid values: {valid_types}",
        )

    try:
        st = TaskStatus(status) if status else None
    except ValueError:
        valid_statuses = [s.value for s in TaskStatus]
        return error(
            code=ErrorCode.INVALID_REQUEST,
            message=f"Invalid status '{status}'. Valid values: {valid_statuses}",
        )

    tasks = await task_manager.list_tasks(
        task_type=tt, status=st, limit=limit, offset=offset
    )
    total = len(tasks)

    items = []
    for t in tasks:
        td = t.to_dict()
        items.append(
            {
                "job_id": t.job_id,
                "task_type": t.task_type.value,
                "status": t.status.value,
                "progress": t.progress,
                "created_at": td.get("created_at_iso", ""),
                "duration_seconds": td.get("duration_seconds"),
                "owner_id": t.owner_id,
            }
        )

    return success(
        data={
            "jobs": items,
            "total": total,
            "has_more": total >= limit,
        },
        message="Jobs retrieved",
    )


@router.get("/stats")
async def get_task_stats():
    """Get task system statistics"""
    return success(data=task_manager.get_stats(), message="Stats retrieved")
