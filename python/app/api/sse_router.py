import json
import asyncio
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from app.core.task_manager import task_manager, TaskStatus
from app.services.solver_progress_service import get_solver_progress_service

router = APIRouter(prefix="/api/v1/tasks", tags=["Tasks SSE"])


async def sse_event_generator(task_id: str):
    queue = await task_manager.subscribe(task_id)
    task = task_manager.get_task(task_id)
    
    if not task:
        yield f"data: {json.dumps({'error': 'Task not found'})}\n\n"
        return
    
    if task.status in [TaskStatus.SUCCESS, TaskStatus.FAILED, TaskStatus.CANCELLED]:
        event = {
            "task_id": task_id,
            "event": "status_change",
            "status": task.status.value,
            "progress": task.progress,
            "result": task.result,
            "error": task.error
        }
        yield f"data: {json.dumps(event)}\n\n"
        return
    
    try:
        while True:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=30.0)
                yield f"data: {json.dumps(event)}\n\n"
                
                if event.get("event") in ["result", "error", "status_change"]:
                    break
            except asyncio.TimeoutError:
                yield f": heartbeat\n\n"
    except asyncio.CancelledError:
        pass
    finally:
        task_manager.unsubscribe(task_id, queue)


async def solver_sse_event_generator(task_id: str):
    solver_service = get_solver_progress_service()
    queue = await solver_service.subscribe(task_id)
    
    try:
        while True:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=30.0)
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
                
                if event.get("event") in ["solver_completed", "solver_terminated"]:
                    break
            except asyncio.TimeoutError:
                yield f": heartbeat\n\n"
    except asyncio.CancelledError:
        pass
    finally:
        solver_service.unsubscribe(task_id, queue)


@router.get("/{task_id}/stream")
async def task_stream(task_id: str):
    return StreamingResponse(
        sse_event_generator(task_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@router.get("/{task_id}/solver-stream")
async def solver_progress_stream(task_id: str):
    return StreamingResponse(
        solver_sse_event_generator(task_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )
