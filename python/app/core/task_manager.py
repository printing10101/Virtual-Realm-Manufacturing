import asyncio
import uuid
from enum import Enum
from typing import Optional, Callable, Any, Dict, List
from datetime import datetime
from dataclasses import dataclass, field


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskType(str, Enum):
    PROCESS_GENERATION = "process_generation"
    REPORT_GENERATION = "report_generation"
    SIMULATION_VALIDATION = "simulation_validation"
    CAD_GENERATION = "cad_generation"
    WORKFLOW_EXECUTION = "workflow_execution"


@dataclass
class Task:
    task_id: str
    task_type: TaskType
    status: TaskStatus = TaskStatus.PENDING
    progress: float = 0.0
    message: str = ""
    result: Optional[dict] = None
    error: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    params: Optional[dict] = None


class TaskManager:
    def __init__(self, default_timeout: float = 300.0):
        self._tasks: Dict[str, Task] = {}
        self._task_events: Dict[str, asyncio.Queue] = {}
        self._default_timeout = default_timeout
        self._task_timeout: Dict[str, float] = {}
        self._subscribers: Dict[str, List[asyncio.Queue]] = {}

    def create_task(self, task_type: TaskType, params: Optional[dict] = None) -> str:
        task_id = str(uuid.uuid4())
        task = Task(task_id=task_id, task_type=task_type, params=params)
        self._tasks[task_id] = task
        self._task_events[task_id] = asyncio.Queue()
        self._subscribers[task_id] = []
        self._task_timeout[task_id] = self._default_timeout
        return task_id

    async def update_progress(self, task_id: str, progress: float, message: str = ""):
        task = self._tasks.get(task_id)
        if not task:
            raise ValueError(f"Task {task_id} not found")
        
        task.progress = min(100.0, max(0.0, progress))
        task.message = message
        task.updated_at = datetime.now().isoformat()
        
        event = {
            "task_id": task_id,
            "event": "progress",
            "progress": task.progress,
            "message": task.message
        }
        await self._notify_subscribers(task_id, event)

    async def complete_task(self, task_id: str, result: Optional[dict] = None):
        task = self._tasks.get(task_id)
        if not task:
            raise ValueError(f"Task {task_id} not found")
        
        task.status = TaskStatus.SUCCESS
        task.progress = 100.0
        task.result = result
        task.updated_at = datetime.now().isoformat()
        
        event = {
            "task_id": task_id,
            "event": "result",
            "progress": 100.0,
            "result": result
        }
        await self._notify_subscribers(task_id, event)
        await self._cleanup_task(task_id)

    async def fail_task(self, task_id: str, error: str):
        task = self._tasks.get(task_id)
        if not task:
            raise ValueError(f"Task {task_id} not found")
        
        task.status = TaskStatus.FAILED
        task.error = error
        task.updated_at = datetime.now().isoformat()
        
        event = {
            "task_id": task_id,
            "event": "error",
            "error": error
        }
        await self._notify_subscribers(task_id, event)
        await self._cleanup_task(task_id)

    async def cancel_task(self, task_id: str):
        task = self._tasks.get(task_id)
        if not task:
            raise ValueError(f"Task {task_id} not found")
        
        if task.status in [TaskStatus.SUCCESS, TaskStatus.FAILED, TaskStatus.CANCELLED]:
            return
        
        task.status = TaskStatus.CANCELLED
        task.updated_at = datetime.now().isoformat()
        
        event = {
            "task_id": task_id,
            "event": "status_change",
            "status": TaskStatus.CANCELLED.value,
            "message": "Task cancelled by user"
        }
        await self._notify_subscribers(task_id, event)
        await self._cleanup_task(task_id)

    def get_task(self, task_id: str) -> Optional[Task]:
        return self._tasks.get(task_id)

    def list_tasks(self, status_filter: Optional[TaskStatus] = None, 
                   task_type_filter: Optional[TaskType] = None) -> List[Task]:
        tasks = list(self._tasks.values())
        
        if status_filter:
            tasks = [t for t in tasks if t.status == status_filter]
        
        if task_type_filter:
            tasks = [t for t in tasks if t.task_type == task_type_filter]
        
        return sorted(tasks, key=lambda x: x.created_at, reverse=True)

    def get_timeout(self, task_id: str) -> float:
        return self._task_timeout.get(task_id, self._default_timeout)

    def set_timeout(self, task_id: str, timeout: float):
        self._task_timeout[task_id] = timeout

    async def subscribe(self, task_id: str) -> asyncio.Queue:
        if task_id not in self._subscribers:
            self._subscribers[task_id] = []
        
        queue = asyncio.Queue()
        self._subscribers[task_id].append(queue)
        return queue

    def unsubscribe(self, task_id: str, queue: asyncio.Queue):
        if task_id in self._subscribers:
            try:
                self._subscribers[task_id].remove(queue)
            except ValueError:
                pass

    async def _notify_subscribers(self, task_id: str, event: dict):
        if task_id in self._subscribers:
            for queue in self._subscribers[task_id]:
                await queue.put(event)

    async def _cleanup_task(self, task_id: str):
        self._tasks.pop(task_id, None)
        self._task_events.pop(task_id, None)
        self._subscribers.pop(task_id, None)
        self._task_timeout.pop(task_id, None)

    async def run_with_timeout(self, task_id: str, coro):
        timeout = self.get_timeout(task_id)
        try:
            return await asyncio.wait_for(coro, timeout=timeout)
        except asyncio.TimeoutError:
            await self.fail_task(task_id, f"Task timed out after {timeout} seconds")
            raise


task_manager = TaskManager(default_timeout=300.0)
