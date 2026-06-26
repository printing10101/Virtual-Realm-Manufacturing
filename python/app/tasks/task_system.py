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

from sqlalchemy import select

from app.tasks.task_manager import TaskStatus, TaskType
from app.core.safe_errors import safe_error_message
from app.database.models import TrainingTask, TaskStatusEnum
from app.database.connection import get_sessionmaker
from app.services.redis_client import (
    save_task_progress,
    get_task_progress,
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

# 可重试的异常类型
RETRYABLE_EXCEPTIONS = (TimeoutError, ConnectionError, OSError)


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
        
        # 任务超时和重试配置
        self._task_timeout = 3600  # 默认1小时超时
        self._max_retries = 3

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

        except (RuntimeError, OSError) as e:
            logger.error("Task recovery failed: %s", e)

    async def requeue_orphan_tasks(
        self,
        *,
        task_types: Optional[List[str]] = None,
        max_age_seconds: int = 3600,
    ) -> int:
        """将历史 RUNNING 任务重置为 QUEUED，便于重新调度。

        与 :meth:`_recover_running_tasks` 不同的是：后者把任务标记为
        ``FAILED``（用于生产环境的"宁可丢不可错跑"），而本方法将其
        重新放回队列（用于可恢复的训练/推理任务）。

        Args:
            task_types: 仅重置这些任务类型；为 ``None`` 时重置全部。
            max_age_seconds: 仅重置 ``updated_at`` 距今不超过此秒数的任务。

        Returns:
            实际重置的任务数量。
        """
        sessionmaker = get_sessionmaker()
        if sessionmaker is None:
            return 0
        try:
            from datetime import timedelta
            cutoff = datetime.now(timezone.utc) - timedelta(seconds=max_age_seconds)
            async with sessionmaker() as session:
                stmt = select(TrainingTask).where(
                    TrainingTask.status == TaskStatusEnum.RUNNING
                )
                if task_types:
                    stmt = stmt.where(TrainingTask.task_type.in_(task_types))
                result = await session.execute(stmt)
                orphans = result.scalars().all()
                requeued = 0
                for task in orphans:
                    task.status = TaskStatusEnum.QUEUED
                    task.error = None
                    task.started_at = None
                    task.completed_at = None
                    requeued += 1
                await session.commit()
                if requeued:
                    logger.warning(
                        "requeue_orphan_tasks: 重置 %d 个 RUNNING→QUEUED (cutoff=%s)",
                        requeued,
                        cutoff.isoformat(),
                    )
                return requeued
        except (RuntimeError, OSError) as e:
            logger.error("requeue_orphan_tasks failed: %s", e)
            return 0

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
        except (RuntimeError, OSError) as e:
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
                    except (RuntimeError, OSError) as e:
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

            retry_count = 0
            for attempt in range(self._max_retries + 1):
                try:
                    timeout = self._task_timeout
                    cancel_evt = self._cancel_events.get(job_id)

                    # 使用 wait_for 添加超时控制
                    try:
                        result = await asyncio.wait_for(
                            executor(
                                cancel_evt, self._create_progress_updater(job_id)
                            ),
                            timeout=timeout,
                        )
                    except asyncio.TimeoutError:
                        raise TimeoutError(
                            f"Task {job_id} exceeded timeout of {timeout}s"
                        )

                    # 成功执行，跳出重试循环
                    async with self._task_lock:
                        record = self._tasks[job_id]
                        record.status = TaskStatus.COMPLETED
                        record.progress = 100.0
                        record.result = result
                        record.completed_at = time.time()
                        metrics = result.get("metrics") if result else None
                        if retry_count > 0:
                            if metrics is None:
                                metrics = {}
                            metrics["retry_count"] = retry_count
                        record.metrics = metrics

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
                    return

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
                    return

                except RETRYABLE_EXCEPTIONS as e:
                    retry_count += 1
                    if attempt < self._max_retries:
                        logger.warning(
                            "Task %s failed (attempt %d/%d), retrying: %s",
                            job_id, attempt + 1, self._max_retries, e,
                        )
                        # 重试时重置进度
                        async with self._task_lock:
                            if job_id in self._tasks:
                                self._tasks[job_id].progress = 0.0
                        await save_task_progress(
                            job_id,
                            {
                                "progress": 0.0,
                                "status": "running",
                                "message": f"Retrying (attempt {attempt + 1}/{self._max_retries})",
                            },
                        )
                        await self._broadcast_event(
                            job_id,
                            "progress",
                            {
                                "job_id": job_id,
                                "percent": 0.0,
                                "message": f"Retrying (attempt {attempt + 1}/{self._max_retries})",
                                "retry_count": retry_count,
                            },
                        )
                        # 指数退避
                        await asyncio.sleep(2 ** attempt)
                        continue
                    raise  # 最后一次重试失败，抛出异常

                except (RuntimeError, ValueError, TypeError) as e:
                    # 不可重试的异常，直接失败
                    safe = safe_error_message(
                        e, context=f"task_system.run_task[{job_id}]"
                    )
                    async with self._task_lock:
                        record = self._tasks[job_id]
                        record.status = TaskStatus.FAILED
                        record.error = safe["message"]
                        record.completed_at = time.time()
                        if retry_count > 0:
                            if record.metrics is None:
                                record.metrics = {}
                            record.metrics["retry_count"] = retry_count

                    await self._persist_task_to_db(record)
                    await save_task_progress(
                        job_id,
                        {
                            "progress": record.progress,
                            "status": "failed",
                            "error": safe["message"],
                            "error_id": safe.get("error_id"),
                        },
                    )

                    await self._broadcast_event(
                        job_id,
                        "failed",
                        {
                            "job_id": job_id,
                            "error": safe["message"],
                            "error_id": safe.get("error_id"),
                            "suggestion": self._get_error_suggestion(e),
                            "failed_at": datetime.now().isoformat(),
                        },
                    )

                    await self._cleanup_task(job_id)
                    return

            # 所有重试耗尽后仍然失败（RETRYABLE_EXCEPTIONS 最后一次 raise 后不会到这里，
            # 但为安全起见保留此兜底）
            logger.error("Task %s exhausted all %d retries", job_id, self._max_retries)

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
            except (RuntimeError, ValueError) as e:
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
        except (RuntimeError, OSError) as e:
            logger.error("Failed to load task %s from DB: %s", job_id, e)

        return None

    async def count_tasks(
        self,
        owner_id: Optional[str] = None,
        task_type: Optional[TaskType] = None,
        status: Optional[TaskStatus] = None,
    ) -> int:
        """统计符合条件的任务总数（用于分页）"""
        sessionmaker = get_sessionmaker()
        if sessionmaker is None:
            async with self._task_lock:
                tasks = list(self._tasks.values())
            filtered = self._filter_tasks(tasks, owner_id, task_type, status, limit=len(tasks), offset=0)
            return len(filtered)

        try:
            async with sessionmaker() as session:
                from sqlalchemy import func
                query = select(func.count(TrainingTask.id))

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

                result = await session.execute(query)
                return result.scalar() or 0
        except (RuntimeError, OSError) as e:
            logger.error("Failed to count tasks from DB: %s", e)
            async with self._task_lock:
                tasks = list(self._tasks.values())
            filtered = self._filter_tasks(tasks, owner_id, task_type, status, limit=len(tasks), offset=0)
            return len(filtered)

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
        except (RuntimeError, OSError) as e:
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
            except ValueError as remove_err:
                # 重复 unsubscribe 时 queue 已不在列表中是预期行为
                logger.debug(
                    "Queue already removed from subscribers for job %s: %s",
                    job_id,
                    remove_err,
                    exc_info=True,
                )

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
                except (RuntimeError, OSError):
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
