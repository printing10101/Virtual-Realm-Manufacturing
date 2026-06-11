from __future__ import annotations

import logging
import threading
import time
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from app.tasks.execution_lock import (
    ExecutionLockStore,
    ExecutionLock,
    LockConflictError,
    LockNotFoundError,
    get_execution_lock_store,
    DEFAULT_LOCK_TIMEOUT_HOURS,
)

logger = logging.getLogger(__name__)

MAX_RETRY_COUNT = 5
BUDGET_RETRY_DELAY_MINUTES = 0
GPU_RETRY_DELAY_MINUTES = 5
CONFLICT_RETRY_DELAY_MINUTES = 1


class CheckoutStatus(str, Enum):
    SUCCESS = "success"
    FAILED = "failed"


class CheckoutFailureReason(str, Enum):
    ALREADY_CHECKED_OUT = "already_checked_out"
    TASK_COMPLETED = "task_completed"
    TASK_FAILED = "task_failed"
    ASSIGNED_TO_OTHER = "assigned_to_other"
    BUDGET_EXCEEDED = "budget_exceeded"
    GPU_UNAVAILABLE = "gpu_unavailable"
    AGENT_BUSY = "agent_busy"
    BLOCKERS_UNRESOLVED = "blockers_unresolved"
    LOCK_EXISTS = "lock_exists"


class TaskStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AgentMode(str, Enum):
    SINGLE = "single"
    BATCH = "batch"


class CheckoutPriority(int, Enum):
    CRITICAL = 1
    HIGH = 2
    NORMAL = 3
    LOW = 4


@dataclass
class CheckoutRequest:
    task_id: str
    agent_id: str
    agent_mode: AgentMode = AgentMode.SINGLE
    priority: CheckoutPriority = CheckoutPriority.NORMAL
    required_gpu_memory: float = 0.0
    timeout_hours: float = DEFAULT_LOCK_TIMEOUT_HOURS


@dataclass
class CheckoutResult:
    status: CheckoutStatus
    task_id: str
    agent_id: str
    message: str = ""
    failure_reason: Optional[CheckoutFailureReason] = None
    retry_recommended: bool = False
    retry_delay_minutes: int = 0
    lock: Optional[ExecutionLock] = None
    checked_out_at: Optional[str] = None
    expires_at: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "status": self.status.value,
            "task_id": self.task_id,
            "agent_id": self.agent_id,
            "message": self.message,
            "failure_reason": self.failure_reason.value
            if self.failure_reason
            else None,
            "retry_recommended": self.retry_recommended,
            "retry_delay_minutes": self.retry_delay_minutes,
            "checked_out_at": self.checked_out_at,
            "expires_at": self.expires_at,
            "lock": self.lock.to_dict() if self.lock else None,
        }


@dataclass
class CheckoutQueueEntry:
    task_id: str
    agent_id: str
    priority: CheckoutPriority
    created_at: float
    retry_count: int = 0
    last_failure: Optional[CheckoutFailureReason] = None
    next_retry_at: Optional[float] = None


@dataclass
class TaskRecord:
    id: str
    title: str = ""
    description: str = ""
    task_type: str = "execution"
    status: str = "pending"
    assigned_to: Optional[str] = None
    parent_goal_id: Optional[str] = None
    project_id: Optional[str] = None
    required_gpu_memory: float = 0.0
    blockers: List[str] = field(default_factory=list)
    priority: int = 3
    checked_out_at: Optional[str] = None
    checkout_expires_at: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    completed_at: Optional[str] = None
    failure_history: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "task_type": self.task_type,
            "status": self.status,
            "assigned_to": self.assigned_to,
            "parent_goal_id": self.parent_goal_id,
            "project_id": self.project_id,
            "required_gpu_memory": self.required_gpu_memory,
            "blockers": self.blockers,
            "priority": self.priority,
            "checked_out_at": self.checked_out_at,
            "checkout_expires_at": self.checkout_expires_at,
            "created_at": self.created_at,
            "completed_at": self.completed_at,
            "failure_history": self.failure_history,
        }


class TaskCheckoutManager:
    def __init__(
        self, lock_store: ExecutionLockStore, db_path: str = "task_checkout.db"
    ):
        self._lock_store = lock_store
        self._db_path = db_path
        self._queue_lock = threading.Lock()
        self._checkout_lock = threading.Lock()
        self._conn: Optional[sqlite3.Connection] = None
        self._budget_checker: Optional[Callable[[str, Optional[str]], bool]] = None
        self._gpu_checker: Optional[Callable[[float], bool]] = None
        self._ensure_tables()

    def set_budget_checker(self, checker: Callable[[str, Optional[str]], bool]):
        self._budget_checker = checker

    def set_gpu_checker(self, checker: Callable[[float], bool]):
        self._gpu_checker = checker

    def _get_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA busy_timeout=5000")
        return self._conn

    def _ensure_tables(self):
        conn = self._get_conn()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS checkout_tasks (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL DEFAULT '',
                description TEXT NOT NULL DEFAULT '',
                task_type TEXT NOT NULL DEFAULT 'execution',
                status TEXT NOT NULL DEFAULT 'pending',
                assigned_to TEXT,
                parent_goal_id TEXT,
                project_id TEXT,
                required_gpu_memory REAL NOT NULL DEFAULT 0.0,
                blockers TEXT NOT NULL DEFAULT '[]',
                priority INTEGER NOT NULL DEFAULT 3,
                checked_out_at TEXT,
                checkout_expires_at TEXT,
                created_at TEXT NOT NULL,
                completed_at TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS checkout_failure_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id TEXT NOT NULL,
                agent_id TEXT NOT NULL,
                reason TEXT NOT NULL,
                message TEXT,
                timestamp TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS checkout_queue (
                task_id TEXT NOT NULL,
                agent_id TEXT NOT NULL,
                priority INTEGER NOT NULL DEFAULT 3,
                retry_count INTEGER NOT NULL DEFAULT 0,
                last_failure TEXT,
                next_retry_at REAL,
                created_at REAL NOT NULL,
                PRIMARY KEY (task_id, agent_id)
            )
        """)
        conn.commit()

    def register_task(self, task: TaskRecord):
        conn = self._get_conn()
        conn.execute(
            """INSERT OR REPLACE INTO checkout_tasks
               (id, title, description, task_type, status, assigned_to, parent_goal_id,
                project_id, required_gpu_memory, blockers, priority,
                checked_out_at, checkout_expires_at, created_at, completed_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                task.id,
                task.title,
                task.description,
                task.task_type,
                task.status,
                task.assigned_to,
                task.parent_goal_id,
                task.project_id,
                task.required_gpu_memory,
                self._serialize_blockers(task.blockers),
                task.priority,
                task.checked_out_at,
                task.checkout_expires_at,
                task.created_at,
                task.completed_at,
            ),
        )
        conn.commit()

    def get_task(self, task_id: str) -> Optional[TaskRecord]:
        conn = self._get_conn()
        row = conn.execute(
            "SELECT * FROM checkout_tasks WHERE id = ?", (task_id,)
        ).fetchone()
        if row is None:
            return None
        return self._row_to_task(row)

    def _row_to_task(self, row) -> TaskRecord:
        import json

        blockers = []
        try:
            blockers = json.loads(row["blockers"] or "[]")
        except (json.JSONDecodeError, TypeError):
            blockers = []

        return TaskRecord(
            id=row["id"],
            title=row["title"],
            description=row["description"],
            task_type=row["task_type"],
            status=row["status"],
            assigned_to=row["assigned_to"],
            parent_goal_id=row["parent_goal_id"],
            project_id=row["project_id"],
            required_gpu_memory=row["required_gpu_memory"] or 0.0,
            blockers=blockers,
            priority=row["priority"] or 3,
            checked_out_at=row["checked_out_at"],
            checkout_expires_at=row["checkout_expires_at"],
            created_at=row["created_at"],
            completed_at=row["completed_at"],
        )

    @staticmethod
    def _serialize_blockers(blockers: List[str]) -> str:
        import json

        return json.dumps(blockers, ensure_ascii=False)

    def checkout_task(self, request: CheckoutRequest) -> CheckoutResult:
        with self._checkout_lock:
            return self._perform_checkout(request)

    def _perform_checkout(self, request: CheckoutRequest) -> CheckoutResult:
        task = self.get_task(request.task_id)
        if task is None:
            return self._checkout_fail(
                request,
                CheckoutFailureReason.ALREADY_CHECKED_OUT,
                f"Task '{request.task_id}' not found",
                retry=False,
            )

        if task.status == TaskStatus.COMPLETED.value:
            return self._checkout_fail(
                request,
                CheckoutFailureReason.TASK_COMPLETED,
                f"Task '{request.task_id}' is already completed",
                retry=False,
            )

        if task.status == TaskStatus.FAILED.value:
            return self._checkout_fail(
                request,
                CheckoutFailureReason.TASK_FAILED,
                f"Task '{request.task_id}' has failed",
                retry=False,
            )

        if task.status == TaskStatus.CANCELLED.value:
            return self._checkout_fail(
                request,
                CheckoutFailureReason.ALREADY_CHECKED_OUT,
                f"Task '{request.task_id}' is cancelled",
                retry=False,
            )

        if (
            task.status == TaskStatus.IN_PROGRESS.value
            and task.assigned_to != request.agent_id
        ):
            return self._checkout_fail(
                request,
                CheckoutFailureReason.ASSIGNED_TO_OTHER,
                f"Task is assigned to {task.assigned_to}",
                retry=False,
            )

        if task.assigned_to and task.assigned_to != request.agent_id:
            return self._checkout_fail(
                request,
                CheckoutFailureReason.ASSIGNED_TO_OTHER,
                f"Task assigned to {task.assigned_to}",
                retry=True,
                retry_delay=CONFLICT_RETRY_DELAY_MINUTES,
            )

        if task.blockers:
            unresolved = self._get_unresolved_blockers(task.blockers)
            if unresolved:
                return self._checkout_fail(
                    request,
                    CheckoutFailureReason.BLOCKERS_UNRESOLVED,
                    f"Unresolved blockers: {unresolved}",
                    retry=True,
                    retry_delay=CONFLICT_RETRY_DELAY_MINUTES,
                )

        if request.agent_mode == AgentMode.SINGLE:
            active_lock = self._lock_store.get_active_lock_by_agent(request.agent_id)
            if active_lock and active_lock.task_id != request.task_id:
                return self._checkout_fail(
                    request,
                    CheckoutFailureReason.AGENT_BUSY,
                    f"Agent '{request.agent_id}' is holding lock on task '{active_lock.task_id}'",
                    retry=False,
                )

        if self._budget_checker:
            project_id = task.project_id
            if not self._budget_checker(request.agent_id, project_id):
                self._record_failure(
                    request.task_id,
                    request.agent_id,
                    CheckoutFailureReason.BUDGET_EXCEEDED,
                    "Budget exceeded for agent/project",
                )
                return self._checkout_fail(
                    request,
                    CheckoutFailureReason.BUDGET_EXCEEDED,
                    "Budget exceeded",
                    retry=False,
                )

        if request.required_gpu_memory > 0 and self._gpu_checker:
            if not self._gpu_checker(request.required_gpu_memory):
                self._record_failure(
                    request.task_id,
                    request.agent_id,
                    CheckoutFailureReason.GPU_UNAVAILABLE,
                    f"GPU memory {request.required_gpu_memory}GB unavailable",
                )
                return self._checkout_fail(
                    request,
                    CheckoutFailureReason.GPU_UNAVAILABLE,
                    f"GPU resources unavailable (need {request.required_gpu_memory}GB)",
                    retry=True,
                    retry_delay=GPU_RETRY_DELAY_MINUTES,
                )

        try:
            lock = self._lock_store.create_lock(
                task_id=request.task_id,
                agent_id=request.agent_id,
                timeout_hours=request.timeout_hours,
            )
        except LockConflictError as e:
            return self._checkout_fail(
                request,
                CheckoutFailureReason.LOCK_EXISTS,
                str(e),
                retry=True,
                retry_delay=CONFLICT_RETRY_DELAY_MINUTES,
            )

        now_iso = datetime.now().isoformat()
        expires_iso = (
            datetime.now() + timedelta(hours=request.timeout_hours)
        ).isoformat()

        conn = self._get_conn()
        conn.execute(
            """UPDATE checkout_tasks
               SET status = ?, assigned_to = ?, checked_out_at = ?, checkout_expires_at = ?
               WHERE id = ?""",
            (
                TaskStatus.IN_PROGRESS.value,
                request.agent_id,
                now_iso,
                expires_iso,
                request.task_id,
            ),
        )
        conn.commit()

        logger.info(
            "Task checked out: task=%s agent=%s expires=%s",
            request.task_id,
            request.agent_id,
            expires_iso,
        )
        return CheckoutResult(
            status=CheckoutStatus.SUCCESS,
            task_id=request.task_id,
            agent_id=request.agent_id,
            message="Task checked out successfully",
            lock=lock,
            checked_out_at=now_iso,
            expires_at=expires_iso,
        )

    def complete_task(self, task_id: str, agent_id: str) -> CheckoutResult:
        task = self.get_task(task_id)
        if task is None:
            return CheckoutResult(
                status=CheckoutStatus.FAILED,
                task_id=task_id,
                agent_id=agent_id,
                message=f"Task '{task_id}' not found",
                failure_reason=CheckoutFailureReason.ALREADY_CHECKED_OUT,
            )

        if task.status != TaskStatus.IN_PROGRESS.value:
            return CheckoutResult(
                status=CheckoutStatus.FAILED,
                task_id=task_id,
                agent_id=agent_id,
                message=f"Task is not in progress (current: {task.status})",
                failure_reason=CheckoutFailureReason.ALREADY_CHECKED_OUT,
            )

        if task.assigned_to != agent_id:
            return CheckoutResult(
                status=CheckoutStatus.FAILED,
                task_id=task_id,
                agent_id=agent_id,
                message=f"Task is assigned to {task.assigned_to}, not {agent_id}",
                failure_reason=CheckoutFailureReason.ASSIGNED_TO_OTHER,
            )

        try:
            self._lock_store.release_lock(task_id, agent_id, "task completed")
        except (LockNotFoundError, LockConflictError) as lock_err:
            # 任务完成时锁可能已过期/被回收，不影响主流程
            logger.debug(
                "Lock release on task complete skipped for %s: %s",
                task_id,
                lock_err,
                exc_info=True,
            )

        now_iso = datetime.now().isoformat()
        conn = self._get_conn()
        conn.execute(
            "UPDATE checkout_tasks SET status = ?, completed_at = ? WHERE id = ?",
            (TaskStatus.COMPLETED.value, now_iso, task_id),
        )
        conn.commit()

        logger.info("Task completed: task=%s agent=%s", task_id, agent_id)
        return CheckoutResult(
            status=CheckoutStatus.SUCCESS,
            task_id=task_id,
            agent_id=agent_id,
            message="Task completed successfully",
        )

    def fail_task(
        self, task_id: str, agent_id: str, reason: str = ""
    ) -> CheckoutResult:
        task = self.get_task(task_id)
        if task is None:
            return CheckoutResult(
                status=CheckoutStatus.FAILED,
                task_id=task_id,
                agent_id=agent_id,
                message=f"Task '{task_id}' not found",
                failure_reason=CheckoutFailureReason.ALREADY_CHECKED_OUT,
            )

        try:
            self._lock_store.release_lock(task_id, agent_id, f"task failed: {reason}")
        except (LockNotFoundError, LockConflictError) as lock_err:
            # 任务失败时锁可能已被其他流程释放，记录以便排查
            logger.debug(
                "Lock release on task failed skipped for %s: %s",
                task_id,
                lock_err,
                exc_info=True,
            )

        datetime.now().isoformat()
        conn = self._get_conn()
        conn.execute(
            "UPDATE checkout_tasks SET status = ?, assigned_to = NULL WHERE id = ?",
            (TaskStatus.FAILED.value, task_id),
        )
        conn.commit()

        self._record_failure(
            task_id, agent_id, CheckoutFailureReason.TASK_FAILED, reason
        )

        logger.warning(
            "Task failed: task=%s agent=%s reason=%s", task_id, agent_id, reason
        )
        return CheckoutResult(
            status=CheckoutStatus.SUCCESS,
            task_id=task_id,
            agent_id=agent_id,
            message=f"Task marked as failed: {reason}",
        )

    def abandon_task(self, task_id: str, agent_id: str) -> CheckoutResult:
        task = self.get_task(task_id)
        if task is None:
            return CheckoutResult(
                status=CheckoutStatus.FAILED,
                task_id=task_id,
                agent_id=agent_id,
                message=f"Task '{task_id}' not found",
                failure_reason=CheckoutFailureReason.ALREADY_CHECKED_OUT,
            )

        try:
            self._lock_store.release_lock(task_id, agent_id, "task abandoned")
        except (LockNotFoundError, LockConflictError) as lock_err:
            # 任务放弃时锁可能已被自动回收，记录以便排查
            logger.debug(
                "Lock release on task abandoned skipped for %s: %s",
                task_id,
                lock_err,
                exc_info=True,
            )

        conn = self._get_conn()
        conn.execute(
            "UPDATE checkout_tasks SET status = ?, assigned_to = NULL, "
            "checked_out_at = NULL, checkout_expires_at = NULL WHERE id = ?",
            (TaskStatus.PENDING.value, task_id),
        )
        conn.commit()

        logger.info("Task abandoned: task=%s agent=%s", task_id, agent_id)
        return CheckoutResult(
            status=CheckoutStatus.SUCCESS,
            task_id=task_id,
            agent_id=agent_id,
            message="Task abandoned, returned to pending",
        )

    def get_task_board(self) -> Dict[str, List[dict]]:
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT * FROM checkout_tasks ORDER BY priority ASC, created_at ASC"
        ).fetchall()

        board: Dict[str, List[dict]] = {
            "pending": [],
            "in_progress": [],
            "completed": [],
            "failed": [],
            "cancelled": [],
        }

        for row in rows:
            task = self._row_to_task(row)
            task_dict = task.to_dict()

            active_lock = self._lock_store.get_lock(task.id)
            if active_lock and active_lock.status.value == "active":
                task_dict["lock_info"] = active_lock.to_dict()
            else:
                task_dict["lock_info"] = None

            status = task.status
            if status in board:
                board[status].append(task_dict)
            else:
                board["pending"].append(task_dict)

        return board

    def get_task_checkout_history(self, task_id: str) -> Dict[str, Any]:
        task = self.get_task(task_id)
        if task is None:
            return {"task": None, "lock_history": [], "failure_history": []}

        lock_history = self._lock_store.get_lock_history(task_id)

        conn = self._get_conn()
        failure_rows = conn.execute(
            "SELECT * FROM checkout_failure_history WHERE task_id = ? ORDER BY timestamp DESC",
            (task_id,),
        ).fetchall()

        failure_history = [
            {
                "task_id": row["task_id"],
                "agent_id": row["agent_id"],
                "reason": row["reason"],
                "message": row["message"],
                "timestamp": row["timestamp"],
            }
            for row in failure_rows
        ]

        return {
            "task": task.to_dict(),
            "lock_history": lock_history,
            "failure_history": failure_history,
        }

    def get_agent_status(self, agent_id: str) -> Dict[str, Any]:
        active_lock = self._lock_store.get_active_lock_by_agent(agent_id)
        pending_count = self._count_tasks_by_agent(agent_id, TaskStatus.PENDING.value)
        in_progress_count = self._count_tasks_by_agent(
            agent_id, TaskStatus.IN_PROGRESS.value
        )
        completed_count = self._count_tasks_by_agent(
            agent_id, TaskStatus.COMPLETED.value
        )

        return {
            "agent_id": agent_id,
            "active_lock": active_lock.to_dict() if active_lock else None,
            "has_active_task": active_lock is not None,
            "pending_tasks": pending_count,
            "in_progress_tasks": in_progress_count,
            "completed_tasks": completed_count,
        }

    def _count_tasks_by_agent(self, agent_id: str, status: str) -> int:
        conn = self._get_conn()
        row = conn.execute(
            "SELECT COUNT(*) as cnt FROM checkout_tasks WHERE assigned_to = ? AND status = ?",
            (agent_id, status),
        ).fetchone()
        return row["cnt"] if row else 0

    def get_all_locks(self) -> List[dict]:
        return [lock.to_dict() for lock in self._lock_store.list_all_locks()]

    def force_release_lock(
        self, task_id: str, admin_id: str = "admin"
    ) -> CheckoutResult:
        try:
            lock = self._lock_store.force_release(task_id, admin_id)

            conn = self._get_conn()
            conn.execute(
                "UPDATE checkout_tasks SET status = ?, assigned_to = NULL, "
                "checked_out_at = NULL, checkout_expires_at = NULL WHERE id = ?",
                (TaskStatus.PENDING.value, task_id),
            )
            conn.commit()

            self._record_failure(
                task_id,
                lock.agent_id,
                "force_released",
                f"Lock force-released by {admin_id}",
            )

            logger.warning(
                "Lock force-released and task reset: task=%s agent=%s by=%s",
                task_id,
                lock.agent_id,
                admin_id,
            )
            return CheckoutResult(
                status=CheckoutStatus.SUCCESS,
                task_id=task_id,
                agent_id=lock.agent_id,
                message=f"Lock force-released by {admin_id}, task returned to pending",
            )
        except LockNotFoundError as e:
            return CheckoutResult(
                status=CheckoutStatus.FAILED,
                task_id=task_id,
                agent_id="",
                message=str(e),
                failure_reason=CheckoutFailureReason.LOCK_EXISTS,
            )

    def cleanup_expired_locks(self) -> List[dict]:
        expired = self._lock_store.cleanup_expired_locks()

        for lock in expired:
            task = self.get_task(lock.task_id)
            if task and task.status == TaskStatus.IN_PROGRESS.value:
                conn = self._get_conn()
                conn.execute(
                    "UPDATE checkout_tasks SET status = ?, assigned_to = NULL, "
                    "checked_out_at = NULL, checkout_expires_at = NULL WHERE id = ?",
                    (TaskStatus.PENDING.value, lock.task_id),
                )
                conn.commit()
                self._record_failure(
                    lock.task_id,
                    lock.agent_id,
                    "lock_expired",
                    "Task returned to pending due to lock timeout",
                )
                logger.warning(
                    "Task returned to pending due to expired lock: task=%s agent=%s",
                    lock.task_id,
                    lock.agent_id,
                )

        return [e.to_dict() for e in expired]

    def enqueue_checkout(self, request: CheckoutRequest) -> CheckoutQueueEntry:
        with self._queue_lock:
            conn = self._get_conn()
            now = time.time()
            conn.execute(
                """INSERT OR REPLACE INTO checkout_queue
                   (task_id, agent_id, priority, retry_count, last_failure, next_retry_at, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    request.task_id,
                    request.agent_id,
                    request.priority.value,
                    0,
                    None,
                    now,
                    now,
                ),
            )
            conn.commit()

        logger.debug(
            "Checkout enqueued: task=%s agent=%s priority=%s",
            request.task_id,
            request.agent_id,
            request.priority.name,
        )
        return CheckoutQueueEntry(
            task_id=request.task_id,
            agent_id=request.agent_id,
            priority=request.priority,
            created_at=now,
        )

    def process_queue(self, max_batch: int = 10) -> List[CheckoutResult]:
        with self._queue_lock:
            conn = self._get_conn()
            now = time.time()
            rows = conn.execute(
                """SELECT * FROM checkout_queue
                   WHERE next_retry_at IS NULL OR next_retry_at <= ?
                   ORDER BY priority ASC, created_at ASC
                   LIMIT ?""",
                (now, max_batch),
            ).fetchall()

            results: List[CheckoutResult] = []
            for row in rows:
                entry = CheckoutQueueEntry(
                    task_id=row["task_id"],
                    agent_id=row["agent_id"],
                    priority=CheckoutPriority(row["priority"]),
                    created_at=row["created_at"],
                    retry_count=row["retry_count"],
                    last_failure=CheckoutFailureReason(row["last_failure"])
                    if row["last_failure"]
                    else None,
                    next_retry_at=row["next_retry_at"],
                )

                task = self.get_task(entry.task_id)
                required_gpu = task.required_gpu_memory if task else 0.0

                request = CheckoutRequest(
                    task_id=entry.task_id,
                    agent_id=entry.agent_id,
                    priority=entry.priority,
                    required_gpu_memory=required_gpu,
                )

                result = self.checkout_task(request)

                if result.status == CheckoutStatus.SUCCESS:
                    conn.execute(
                        "DELETE FROM checkout_queue WHERE task_id = ? AND agent_id = ?",
                        (entry.task_id, entry.agent_id),
                    )
                else:
                    new_retry_count = entry.retry_count + 1
                    if new_retry_count >= MAX_RETRY_COUNT:
                        conn.execute(
                            "DELETE FROM checkout_queue WHERE task_id = ? AND agent_id = ?",
                            (entry.task_id, entry.agent_id),
                        )
                        self.fail_task(
                            entry.task_id,
                            entry.agent_id,
                            f"Max retries ({MAX_RETRY_COUNT}) exceeded: {result.failure_reason}",
                        )
                    else:
                        next_retry = now + result.retry_delay_minutes * 60
                        conn.execute(
                            """UPDATE checkout_queue
                               SET retry_count = ?, last_failure = ?, next_retry_at = ?
                               WHERE task_id = ? AND agent_id = ?""",
                            (
                                new_retry_count,
                                result.failure_reason.value
                                if result.failure_reason
                                else None,
                                next_retry,
                                entry.task_id,
                                entry.agent_id,
                            ),
                        )

                results.append(result)

            conn.commit()
            return results

    def get_queue_status(self) -> List[dict]:
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT * FROM checkout_queue ORDER BY priority ASC, created_at ASC"
        ).fetchall()
        return [
            {
                "task_id": row["task_id"],
                "agent_id": row["agent_id"],
                "priority": row["priority"],
                "retry_count": row["retry_count"],
                "last_failure": row["last_failure"],
                "next_retry_at": datetime.fromtimestamp(
                    row["next_retry_at"]
                ).isoformat()
                if row["next_retry_at"]
                else None,
                "created_at": datetime.fromtimestamp(row["created_at"]).isoformat(),
            }
            for row in rows
        ]

    def _get_unresolved_blockers(self, blockers: List[str]) -> List[str]:
        unresolved = []
        for blocker_id in blockers:
            blocker_task = self.get_task(blocker_id)
            if (
                blocker_task is None
                or blocker_task.status != TaskStatus.COMPLETED.value
            ):
                unresolved.append(blocker_id)
        return unresolved

    def _record_failure(self, task_id: str, agent_id: str, reason, message: str = ""):
        reason_str = (
            reason.value if isinstance(reason, CheckoutFailureReason) else reason
        )
        conn = self._get_conn()
        conn.execute(
            """INSERT INTO checkout_failure_history (task_id, agent_id, reason, message, timestamp)
               VALUES (?, ?, ?, ?, ?)""",
            (task_id, agent_id, reason_str, message, datetime.now().isoformat()),
        )
        conn.commit()

    def _checkout_fail(
        self,
        request: CheckoutRequest,
        reason: CheckoutFailureReason,
        message: str,
        retry: bool = False,
        retry_delay: int = 0,
    ) -> CheckoutResult:
        self._record_failure(request.task_id, request.agent_id, reason, message)

        logger.warning(
            "Checkout failed: task=%s agent=%s reason=%s message=%s retry=%s",
            request.task_id,
            request.agent_id,
            reason.value,
            message,
            retry,
        )

        return CheckoutResult(
            status=CheckoutStatus.FAILED,
            task_id=request.task_id,
            agent_id=request.agent_id,
            message=message,
            failure_reason=reason,
            retry_recommended=retry,
            retry_delay_minutes=retry_delay,
        )

    def close(self):
        if self._conn:
            self._conn.close()
            self._conn = None


class _CheckoutManagerHolder:
    """Thread-safe lazy holder for the :class:`TaskCheckoutManager` singleton."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._instance: Optional[TaskCheckoutManager] = None

    def get(self) -> TaskCheckoutManager:
        # 快速路径：已存在则直接返回，避免持锁开销
        if self._instance is not None:
            return self._instance
        with self._lock:
            if self._instance is None:
                self._instance = TaskCheckoutManager(
                    lock_store=get_execution_lock_store(),
                    db_path="task_checkout.db",
                )
            return self._instance

    def init(self, db_path: str = "task_checkout.db") -> TaskCheckoutManager:
        """强制重新创建实例（用于启动时指定 db_path 的场景）。"""
        with self._lock:
            self._instance = TaskCheckoutManager(
                lock_store=get_execution_lock_store(),
                db_path=db_path,
            )
            return self._instance

    def reset(self) -> None:
        """Reset the cached instance (mainly for tests)."""
        with self._lock:
            self._instance = None


_holder = _CheckoutManagerHolder()


def get_checkout_manager() -> TaskCheckoutManager:
    """获取共享的 :class:`TaskCheckoutManager` 单例；首次访问时懒初始化。

    Returns:
        :class:`TaskCheckoutManager` 实例（应用生命周期内同一实例）。

    Note:
        同时也是 FastAPI 依赖工厂，可直接用于 ``Depends(get_checkout_manager)``。
        实现是线程安全的，行为与重构前完全一致。
    """
    return _holder.get()


def init_checkout_manager(db_path: str = "task_checkout.db") -> TaskCheckoutManager:
    """初始化任务签出管理器，行为与重构前完全一致。"""
    return _holder.init(db_path)
