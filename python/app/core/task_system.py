"""
Persistent Async Task System

PostgreSQL for task metadata + Redis for real-time progress + asyncio execution.
Supports task lifecycle management, SSE broadcasting, idempotency, and cancellation.
"""

import asyncio
import json
import logging
import time
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from threading import Lock
from typing import Any, Callable, Dict, List, Optional

from sqlalchemy import select, update, delete, func
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.core.task_manager import TaskStatus, TaskType
from app.database.models import TrainingTask, TaskStatusEnum
from app.database.connection import get_sessionmaker
from app.services.redis_client import (
    save_task_progress,
    get_task_progress,
    delete_task_progress,
    set_cancel_flag,
    clear_cancel_flag,
)

logger = logging.getLogger(__name__)

VALID_STATUS_TRANSITIONS = {
    TaskStatus.PENDING: {TaskStatus.QUEUED, TaskStatus.RUNNING, TaskStatus.CANCELLED},
    TaskStatus.QUEUED: {TaskStatus.RUNNING, TaskStatus.CANCELLED},
    TaskStatus.RUNNING: {TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED},
    TaskStatus.COMPLETED: set(),
    TaskStatus.FAILED: set(),
    TaskStatus.CANCELLED: set(),
}


@dataclass
class TaskRecord:
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

    @classmethod
    def from_db_model(cls, model: TrainingTask) -> "TaskRecord":
        return cls(
            job_id=model.id,
            task_type=TaskType(model.task_type) if model.task_type else TaskType.UNKNOWN,
            status=TaskStatus(model.status) if model.status else TaskStatus.PENDING,
            progress=float(model.progress or 0),
            result=model.result,
            error=model.error,
            params=model.params,
            owner_id=model.owner_id,
            idempotency_key=model.idempotency_key,
            created_at=model.created_at.timestamp() if model.created_at else time.time(),
            started_at=model.started_at.timestamp() if model.started_at else None,
            completed_at=model.completed_at.timestamp() if model.completed_at else None,
        )


class AsyncTaskManager:
    """
    Persistent singleton async task manager.

    Storage Architecture:
        PostgreSQL: task metadata (status, params, result, timestamps)
        Redis: real-time progress (Hash: task:{id}:progress), cancel flags

    State Machine: PENDING -> QUEUED -> RUNNING -> COMPLETED/FAILED/CANCELLED
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
        self._cancel_hooks: Dict[str, Callable] = {}

        self._max_concurrent = 3
        self._semaphore = asyncio.Semaphore(self._max_concurrent)
        self._started = False

    async def initialize(self, max_concurrent: int = 3):
        self._max_concurrent = max_concurrent
        self._semaphore = asyncio.Semaphore(max_concurrent)

        await self._recover_running_tasks()

        self._started = True
        logger.info("AsyncTaskManager initialized: max_concurrent=%d", max_concurrent)

    async def shutdown(self):
        self._started = False
        logger.info("AsyncTaskManager shut down")

    async def _recover_running_tasks(self):
        sessionmaker = get_sessionmaker()
        if sessionmaker is None:
            return

        try:
            async with sessionmaker() as session:
                result = await session.execute(
                    select(TrainingTask).where(
                        TrainingTask.status == TaskStatusEnum.RUNNING
                    )
                )
                running_tasks = result.scalars().all()

            if not running_tasks:
                return

            logger.warning(
                "Found %d RUNNING tasks from previous session, marking as FAILED",
                len(running_tasks),
            )

            async with sessionmaker() as session:
                now = datetime.now(timezone.utc)
                for task in running_tasks:
                    task.status = TaskStatusEnum.FAILED
                    task.error = "Service restarted: task was running before shutdown"
                    task.completed_at = now
                    task.progress = task.progress or 0
                await session.commit()

        except Exception as e:
            logger.error("Task recovery failed: %s", e)

    async def _persist_task_to_db(self, record: TaskRecord):
        sessionmaker = get_sessionmaker()
        if sessionmaker is None:
            return

        try:
            async with sessionmaker() as session:
                existing = await session.get(TrainingTask, record.job_id)
                if existing:
                    existing.status = record.status.value
                    existing.progress = int(record.progress)
                    existing.result = record.result
                    existing.error = record.error
                    existing.params = record.params
                    if record.started_at:
                        existing.started_at = datetime.fromtimestamp(
                            record.started_at, tz=timezone.utc
                        )
                    if record.completed_at:
                        existing.completed_at = datetime.fromtimestamp(
                            record.completed_at, tz=timezone.utc
                        )
                else:
                    task_model = TrainingTask(
                        id=record.job_id,
                        task_type=record.task_type.value,
                        status=record.status.value,
                        progress=int(record.progress),
                        params=record.params,
                        result=record.result,
                        error=record.error,
                        owner_id=record.owner_id,
                        idempotency_key=record.idempotency_key,
                        created_at=datetime.fromtimestamp(
                            record.created_at, tz=timezone.utc
                        ),
                        started_at=datetime.fromtimestamp(
                            record.started_at, tz=timezone.utc
                        )
                        if record.started_at
                        else None,
                        completed_at=datetime.fromtimestamp(
                            record.completed_at, tz=timezone.utc
                        )
                        if record.completed_at
                        else None,
                    )
                    session.add(task_model)
                await session.commit()
        except Exception as e:
            logger.error("Failed to persist task %s to DB: %s", record.job_id, e)

    async def create_task(
        self,
        task_type: TaskType,
        params: Dict[str, Any],
        owner_id: Optional[str] = None,
        idempotency_key: Optional[str] = None,
    ) -> TaskRecord:
        async with self._task_lock:
            if idempotency_key and idempotency_key in self._idempotency_map:
                return self._tasks[self._idempotency_map[idempotency_key]]

            if idempotency_key:
                sessionmaker = get_sessionmaker()
                if sessionmaker:
                    try:
                        async with sessionmaker() as session:
                            result = await session.execute(
                                select(TrainingTask).where(
                                    TrainingTask.idempotency_key == idempotency_key
                                )
                            )
                            existing_db = result.scalar_one_or_none()
                            if existing_db:
                                record = TaskRecord.from_db_model(existing_db)
                                self._tasks[record.job_id] = record
                                self._idempotency_map[idempotency_key] = record.job_id
                                return record
                    except Exception as e:
                        logger.warning("Idempotency check failed: %s", e)

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
            await self._persist_task_to_db(record)

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

            logger.info("Task %s created and queued", job_id)
            return record

    async def execute_task(self, job_id: str, executor: Callable):
        async with self._semaphore:
            async with self._task_lock:
                if job_id not in self._tasks:
                    return
                record = self._tasks[job_id]
                if record.status == TaskStatus.CANCELLED:
                    return
                record.status = TaskStatus.RUNNING
                record.started_at = time.time()

            await self._persist_task_to_db(record)

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

                await self._persist_task_to_db(record)
                await save_task_progress(
                    job_id,
                    {"progress": 100.0, "status": "completed", "message": "Done"},
                )

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

                await self._persist_task_to_db(record)
                await save_task_progress(
                    job_id,
                    {"progress": record.progress, "status": "cancelled"},
                )

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

                await self._persist_task_to_db(record)
                await save_task_progress(
                    job_id,
                    {
                        "progress": record.progress,
                        "status": "failed",
                        "error": str(e),
                    },
                )

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

        await set_cancel_flag(job_id)

        if job_id in self._cancel_hooks:
            try:
                hook = self._cancel_hooks.pop(job_id)
                if callable(hook):
                    hook()
            except Exception as e:
                logger.warning("Cancel hook for task %s failed: %s", job_id, e)

        await self._persist_task_to_db(record)

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
        async with self._task_lock:
            self._subscribers.pop(job_id, None)
            self._cancel_events.pop(job_id, None)
            self._cancel_hooks.pop(job_id, None)

            record = self._tasks.get(job_id)
            if record and record.idempotency_key:
                self._idempotency_map.pop(record.idempotency_key, None)

            self._tasks.pop(job_id, None)
            await clear_cancel_flag(job_id)

        logger.debug("Task %s resources cleaned up", job_id)

    async def get_task(self, job_id: str) -> Optional[TaskRecord]:
        async with self._task_lock:
            if job_id in self._tasks:
                return self._tasks[job_id]

        sessionmaker = get_sessionmaker()
        if sessionmaker is None:
            return None

        try:
            async with sessionmaker() as session:
                result = await session.execute(
                    select(TrainingTask).where(TrainingTask.id == job_id)
                )
                db_task = result.scalar_one_or_none()
                if db_task:
                    record = TaskRecord.from_db_model(db_task)
                    async with self._task_lock:
                        self._tasks[job_id] = record
                    return record
        except Exception as e:
            logger.error("Failed to load task %s from DB: %s", job_id, e)

        return None

    async def list_tasks(
        self,
        owner_id: Optional[str] = None,
        task_type: Optional[TaskType] = None,
        status: Optional[TaskStatus] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[TaskRecord]:
        sessionmaker = get_sessionmaker()
        if sessionmaker is None:
            async with self._task_lock:
                tasks = list(self._tasks.values())
            return self._filter_tasks(tasks, owner_id, task_type, status, limit, offset)

        try:
            async with sessionmaker() as session:
                query = select(TrainingTask)

                filters = []
                if owner_id:
                    filters.append(TrainingTask.owner_id == owner_id)
                if task_type:
                    filters.append(TrainingTask.task_type == task_type.value)
                if status:
                    filters.append(TrainingTask.status == status.value)

                if filters:
                    from sqlalchemy import and_
                    query = query.where(and_(*filters))

                query = query.order_by(TrainingTask.created_at.desc())
                query = query.offset(offset).limit(limit)

                result = await session.execute(query)
                db_tasks = result.scalars().all()

                records = []
                for db_task in db_tasks:
                    record = TaskRecord.from_db_model(db_task)
                    records.append(record)
                    async with self._task_lock:
                        if record.job_id not in self._tasks:
                            self._tasks[record.job_id] = record

                return records
        except Exception as e:
            logger.error("Failed to list tasks from DB: %s", e)
            async with self._task_lock:
                tasks = list(self._tasks.values())
            return self._filter_tasks(tasks, owner_id, task_type, status, limit, offset)

    def _filter_tasks(
        self,
        tasks: List[TaskRecord],
        owner_id: Optional[str],
        task_type: Optional[TaskType],
        status: Optional[TaskStatus],
        limit: int,
        offset: int,
    ) -> List[TaskRecord]:
        if owner_id:
            tasks = [t for t in tasks if t.owner_id == owner_id]
        if task_type:
            tasks = [t for t in tasks if t.task_type == task_type]
        if status:
            tasks = [t for t in tasks if t.status == status]
        tasks.sort(key=lambda t: t.created_at, reverse=True)
        return tasks[offset : offset + limit]

    def subscribe(self, job_id: str) -> asyncio.Queue:
        q = asyncio.Queue(maxsize=100)
        if job_id in self._subscribers:
            self._subscribers[job_id].append(q)
        return q

    def unsubscribe(self, job_id: str, queue: asyncio.Queue):
        if job_id in self._subscribers:
            try:
                self._subscribers[job_id].remove(queue)
            except ValueError:
                pass

    def register_cancel_hook(self, job_id: str, hook: Callable):
        self._cancel_hooks[job_id] = hook

    async def _broadcast_event(
        self, job_id: str, event_type: str, data: Dict[str, Any]
    ):
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
        async def update_progress(
            percent: float, message: str = "", metrics: Optional[Dict] = None
        ):
            async with self._task_lock:
                if job_id in self._tasks:
                    self._tasks[job_id].progress = percent
                    if metrics:
                        self._tasks[job_id].metrics = metrics

            await save_task_progress(
                job_id,
                {
                    "progress": round(percent, 1),
                    "message": message,
                    "status": "running",
                    "metrics": json.dumps(metrics) if metrics else "{}",
                },
            )

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
        queued_count = sum(
            1 for t in self._tasks.values() if t.status == TaskStatus.QUEUED
        )
        return queued_count * 60.0

    def _queue_size(self) -> int:
        return sum(1 for t in self._tasks.values() if t.status == TaskStatus.QUEUED)

    def _get_error_suggestion(self, error: Exception) -> str:
        err_msg = str(error).lower()
        if "memory" in err_msg:
            return "减小 batch_size 或使用 CPU 模式"
        if "cuda" in err_msg:
            return "检查GPU驱动或切换到CPU模式"
        if "file" in err_msg or "path" in err_msg:
            return "检查文件路径是否正确"
        return "检查输入参数后重试"

    def get_stats(self) -> Dict[str, Any]:
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

    async def get_task_progress_from_redis(self, job_id: str) -> Dict[str, Any]:
        return await get_task_progress(job_id)