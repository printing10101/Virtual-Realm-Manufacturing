"""
Async Task System

Provides unified async task management with lifecycle control,
SSE event broadcasting, and concurrency management.
"""

import asyncio
import json
import logging
import time
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional
from threading import Lock

from app.core.task_manager import TaskStatus, TaskType

logger = logging.getLogger(__name__)


@dataclass
class TaskRecord:
    """Complete task record with lifecycle tracking"""

    job_id: str
    task_type: TaskType
    status: TaskStatus
    progress: float = 0.0
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    params: Optional[Dict[str, Any]] = None
    owner_id: Optional[str] = None
    idempotency_key: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    metrics: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["status"] = self.status.value
        d["task_type"] = self.task_type.value
        d["created_at_iso"] = datetime.fromtimestamp(self.created_at).isoformat()
        if self.started_at:
            d["started_at_iso"] = datetime.fromtimestamp(self.started_at).isoformat()
        if self.completed_at:
            d["completed_at_iso"] = datetime.fromtimestamp(
                self.completed_at
            ).isoformat()
        if self.started_at and self.completed_at:
            d["duration_seconds"] = round(self.completed_at - self.started_at, 2)
        return d


class AsyncTaskManager:
    """
    Singleton async task manager with lifecycle control.

    Features:
    - Task creation, scheduling, execution tracking
    - State machine: PENDING -> QUEUED -> RUNNING -> COMPLETED/FAILED/CANCELLED
    - Concurrency control with configurable limits
    - SSE event broadcasting
    - Idempotency support
    """

    _instance = None
    _lock = Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, "_initialized"):
            return
        self._initialized = True

        self._tasks: Dict[str, TaskRecord] = {}
        self._idempotency_map: Dict[str, str] = {}
        self._cancel_events: Dict[str, asyncio.Event] = {}
        self._task_lock = asyncio.Lock()
        self._subscribers: Dict[str, List[asyncio.Queue]] = {}

        self._max_concurrent = 3
        self._semaphore = asyncio.Semaphore(self._max_concurrent)

        self._cancel_hooks: Dict[str, Callable] = {}

    def register_cancel_hook(self, job_id: str, hook: Callable):
        """Register a cancel hook for a specific task.

        Args:
            job_id: The task ID to register the hook for
            hook: A callable that will be invoked when the task is cancelled
        """
        self._cancel_hooks[job_id] = hook

    async def initialize(self, max_concurrent: int = 3):
        """Initialize with configuration"""
        self._max_concurrent = max_concurrent
        self._semaphore = asyncio.Semaphore(max_concurrent)

    async def create_task(
        self,
        task_type: TaskType,
        params: Dict[str, Any],
        owner_id: Optional[str] = None,
        idempotency_key: Optional[str] = None,
    ) -> TaskRecord:
        """Create a new task and enqueue it"""
        async with self._task_lock:
            if idempotency_key and idempotency_key in self._idempotency_map:
                existing_id = self._idempotency_map[idempotency_key]
                return self._tasks[existing_id]

            job_id = f"{task_type.value}-{uuid.uuid4().hex[:12]}"

            record = TaskRecord(
                job_id=job_id,
                task_type=task_type,
                status=TaskStatus.PENDING,
                params=params,
                owner_id=owner_id,
                idempotency_key=idempotency_key,
            )

            self._tasks[job_id] = record
            self._cancel_events[job_id] = asyncio.Event()
            self._subscribers[job_id] = []

            if idempotency_key:
                self._idempotency_map[idempotency_key] = job_id

            record.status = TaskStatus.QUEUED
            await self._broadcast_event(
                job_id,
                "queued",
                {
                    "job_id": job_id,
                    "task_type": task_type.value,
                    "estimated_wait": self._estimate_wait(),
                    "queue_position": self._queue_size() + 1,
                },
            )

            logger.info(f"Task {job_id} created and queued")

            return record

    async def execute_task(self, job_id: str, executor: Callable):
        """Execute a task with concurrency control"""
        async with self._semaphore:
            async with self._task_lock:
                if job_id not in self._tasks:
                    return
                record = self._tasks[job_id]
                if record.status == TaskStatus.CANCELLED:
                    return
                record.status = TaskStatus.RUNNING
                record.started_at = time.time()

            await self._broadcast_event(
                job_id,
                "started",
                {
                    "job_id": job_id,
                    "started_at": datetime.fromtimestamp(record.started_at).isoformat(),
                    "resources": {"max_concurrent": self._max_concurrent},
                },
            )

            try:
                cancel_evt = self._cancel_events.get(job_id)
                result = await executor(
                    cancel_evt, self._create_progress_updater(job_id)
                )

                async with self._task_lock:
                    record = self._tasks[job_id]
                    record.status = TaskStatus.COMPLETED
                    record.progress = 100.0
                    record.result = result
                    record.completed_at = time.time()
                    record.metrics = result.get("metrics") if result else None

                await self._broadcast_event(
                    job_id,
                    "complete",
                    {
                        "job_id": job_id,
                        "result": result,
                        "completed_at": datetime.now().isoformat(),
                    },
                )

                await self._cleanup_task(job_id)

            except asyncio.CancelledError:
                async with self._task_lock:
                    record = self._tasks[job_id]
                    record.status = TaskStatus.CANCELLED
                    record.completed_at = time.time()

                await self._broadcast_event(
                    job_id,
                    "cancelled",
                    {
                        "job_id": job_id,
                        "cancelled_at": datetime.now().isoformat(),
                        "progress": record.progress,
                    },
                )

                await self._cleanup_task(job_id)

            except Exception as e:
                async with self._task_lock:
                    record = self._tasks[job_id]
                    record.status = TaskStatus.FAILED
                    record.error = str(e)
                    record.completed_at = time.time()

                await self._broadcast_event(
                    job_id,
                    "failed",
                    {
                        "job_id": job_id,
                        "error": str(e),
                        "suggestion": self._get_error_suggestion(e),
                        "failed_at": datetime.now().isoformat(),
                    },
                )

                await self._cleanup_task(job_id)

    async def cancel_task(self, job_id: str) -> bool:
        """Cancel a running task"""
        async with self._task_lock:
            if job_id not in self._tasks:
                return False
            record = self._tasks[job_id]
            if record.status in (
                TaskStatus.COMPLETED,
                TaskStatus.FAILED,
                TaskStatus.CANCELLED,
            ):
                return False

            record.status = TaskStatus.CANCELLED
            record.completed_at = time.time()

        if job_id in self._cancel_events:
            self._cancel_events[job_id].set()

        if job_id in self._cancel_hooks:
            try:
                hook = self._cancel_hooks.pop(job_id)
                if callable(hook):
                    hook()
            except Exception as e:
                logger.warning(f"Cancel hook for task {job_id} failed: {e}")

        await self._broadcast_event(
            job_id,
            "cancelled",
            {
                "job_id": job_id,
                "cancelled_at": datetime.now().isoformat(),
                "progress": record.progress,
            },
        )

        await self._cleanup_task(job_id)

        return True

    async def _cleanup_task(self, job_id: str):
        """Clean up all resources associated with a completed task"""
        MAX_TASK_RECORDS = 1000

        async with self._task_lock:
            self._subscribers.pop(job_id, None)
            self._cancel_events.pop(job_id, None)
            self._cancel_hooks.pop(job_id, None)
            # 移除指向该job_id的幂等映射（O(1)操作）
            record = self._tasks.get(job_id)
            if record and record.idempotency_key:
                self._idempotency_map.pop(record.idempotency_key, None)

            self._tasks.pop(job_id, None)

            if len(self._tasks) > MAX_TASK_RECORDS:
                sorted_tasks = sorted(
                    self._tasks.items(), key=lambda x: x[1].created_at
                )
                excess_count = len(self._tasks) - MAX_TASK_RECORDS
                for old_job_id, old_record in sorted_tasks[:excess_count]:
                    del self._tasks[old_job_id]
                    self._subscribers.pop(old_job_id, None)
                    self._cancel_events.pop(old_job_id, None)
                    if old_record.idempotency_key:
                        self._idempotency_map.pop(old_record.idempotency_key, None)

        logger.debug(f"Task {job_id} resources cleaned up")

    async def get_task(self, job_id: str) -> Optional[TaskRecord]:
        """Get task by ID"""
        async with self._task_lock:
            return self._tasks.get(job_id)

    async def list_tasks(
        self,
        owner_id: Optional[str] = None,
        task_type: Optional[TaskType] = None,
        status: Optional[TaskStatus] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[TaskRecord]:
        """List tasks with filters"""
        async with self._task_lock:
            tasks = list(self._tasks.values())

        if owner_id:
            tasks = [t for t in tasks if t.owner_id == owner_id]
        if task_type:
            tasks = [t for t in tasks if t.task_type == task_type]
        if status:
            tasks = [t for t in tasks if t.status == status]

        tasks.sort(key=lambda t: t.created_at, reverse=True)
        return tasks[offset : offset + limit]

    def subscribe(self, job_id: str) -> asyncio.Queue:
        """Subscribe to task events"""
        q = asyncio.Queue(maxsize=100)
        if job_id in self._subscribers:
            self._subscribers[job_id].append(q)
        return q

    def unsubscribe(self, job_id: str, queue: asyncio.Queue):
        """Unsubscribe from task events"""
        if job_id in self._subscribers:
            try:
                self._subscribers[job_id].remove(queue)
            except ValueError:
                pass

    async def _broadcast_event(
        self, job_id: str, event_type: str, data: Dict[str, Any]
    ):
        """Broadcast event to all subscribers"""
        event = f"event: {event_type}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"

        if job_id in self._subscribers:
            dead_queues = []
            for q in self._subscribers[job_id]:
                try:
                    await q.put(event)
                except Exception:
                    dead_queues.append(q)
            for q in dead_queues:
                self._subscribers[job_id].remove(q)

    def _create_progress_updater(self, job_id: str) -> Callable:
        """Create a progress update callback"""

        async def update_progress(
            percent: float, message: str = "", metrics: Optional[Dict] = None
        ):
            async with self._task_lock:
                if job_id in self._tasks:
                    self._tasks[job_id].progress = percent
                    if metrics:
                        self._tasks[job_id].metrics = metrics

            await self._broadcast_event(
                job_id,
                "progress",
                {
                    "job_id": job_id,
                    "percent": round(percent, 1),
                    "message": message,
                    "metrics": metrics or {},
                },
            )

        return update_progress

    def _estimate_wait(self) -> float:
        """Estimate wait time in seconds"""
        queued_count = sum(
            1 for t in self._tasks.values() if t.status == TaskStatus.QUEUED
        )
        return queued_count * 60.0

    def _queue_size(self) -> int:
        """Get number of queued tasks"""
        return sum(1 for t in self._tasks.values() if t.status == TaskStatus.QUEUED)

    def _get_error_suggestion(self, error: Exception) -> str:
        """Get user-friendly error suggestion"""
        err_msg = str(error).lower()
        if "memory" in err_msg:
            return "减小 batch_size 或使用 CPU 模式"
        if "cuda" in err_msg:
            return "检查GPU驱动或切换到CPU模式"
        if "file" in err_msg or "path" in err_msg:
            return "检查文件路径是否正确"
        return "检查输入参数后重试"

    def get_stats(self) -> Dict[str, Any]:
        """Get task system statistics"""
        total = len(self._tasks)
        active = sum(1 for t in self._tasks.values() if t.status == TaskStatus.RUNNING)
        queued = sum(1 for t in self._tasks.values() if t.status == TaskStatus.QUEUED)
        completed = sum(
            1 for t in self._tasks.values() if t.status == TaskStatus.COMPLETED
        )
        failed = sum(1 for t in self._tasks.values() if t.status == TaskStatus.FAILED)

        return {
            "total_tasks": total,
            "active_tasks": active,
            "queued_tasks": queued,
            "completed_tasks": completed,
            "failed_tasks": failed,
            "max_concurrent": self._max_concurrent,
            "available_slots": self._max_concurrent - active,
        }
