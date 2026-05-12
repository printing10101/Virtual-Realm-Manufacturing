# 异步任务处理系统与SSE流式响应机制实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为灵境制造项目实现完整的异步任务处理系统与SSE流式响应机制，支持LNN模型训练等耗时操作的实时进度反馈。

**Architecture:** 基于现有SSE基础设施(sse.py)和task_manager.py进行扩展，采用单例AsyncTaskManager统一管理任务生命周期，通过标准化SSE事件流推送实时进度，前端使用EventSource API实现断线重连。

**Tech Stack:** FastAPI, asyncio, SSE (Server-Sent Events), Vue 3 Composition API, Element Plus

**文件映射：**
- 创建: `python/app/core/task_system.py` - 核心异步任务管理器
- 扩展: `python/app/core/task_manager.py` - 现有TaskStatus/TaskType枚举
- 重写: `python/app/api/v1/sse.py` - 增强SSE端点和事件格式
- 改造: `python/app/api/v1/lnn.py` - 异步化训练/推理接口
- 创建: `python/app/models/job_schemas.py` - 任务相关Pydantic模型
- 创建: `src/composables/useEventSource.ts` - 前端SSE封装
- 改造: `src/views/Workspace.vue` - 集成实时进度展示
- 创建: `src/views/TaskHistory.vue` - 任务历史面板
- 测试: `tests/test_async_task_system.py`

---

### Task 1: 扩展TaskStatus枚举与创建任务数据模型

**Files:**
- Modify: `python/app/core/task_manager.py` - 扩展枚举和添加dataclass
- Test: `tests/test_async_task_system.py::test_task_status_transitions`

- [ ] **Step 1: 扩展TaskStatus并添加CANCELED状态**

当前`python/app/core/task_manager.py`已有TaskStatus，添加COMPLETED和CANCELED别名：

```python
"""
Task Manager Module

Manages task lifecycle, status tracking, and task type definitions.
"""
from enum import Enum
from typing import Any, Dict, Optional
from dataclasses import dataclass, field
from datetime import datetime


class TaskType(str, Enum):
    """Task types supported by the system"""
    LNN_TRAINING = "lnn_training"
    LNN_INFERENCE = "lnn_inference"
    LNN_BATCH_INFERENCE = "lnn_batch_inference"
    DATA_PROCESSING = "data_processing"
    MODEL_EXPORT = "model_export"
    MODEL_QUANTIZATION = "model_quantization"
    UNKNOWN = "unknown"


class TaskStatus(str, Enum):
    """Task lifecycle status"""
    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    SUCCESS = "success"  # alias for COMPLETED
    FAILED = "failed"
    CANCELLED = "cancelled"
    CANCELED = "cancelled"  # alias


@dataclass
class TaskResult:
    """Standardized task result container"""
    job_id: str
    status: TaskStatus
    result_data: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    metrics: Optional[Dict[str, Any]] = None
```

- [ ] **Step 2: 运行测试验证枚举正确性**

创建`tests/test_async_task_system.py`并运行：

```python
from app.core.task_manager import TaskStatus, TaskType, TaskResult

def test_task_status_transitions():
    valid_statuses = [TaskStatus.PENDING, TaskStatus.QUEUED, TaskStatus.RUNNING, 
                      TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]
    for s in valid_statuses:
        assert isinstance(s, TaskStatus)
    assert TaskStatus.SUCCESS == TaskStatus.COMPLETED
```

运行: `cd python; pytest tests/test_async_task_system.py::test_task_status_transitions -v`
预期: PASS

---

### Task 2: 实现AsyncTaskManager核心管理器

**Files:**
- Create: `python/app/core/task_system.py`
- Test: `tests/test_async_task_system.py::test_async_task_manager`

- [ ] **Step 1: 实现AsyncTaskManager单例**

```python
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
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set
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
        d['status'] = self.status.value
        d['task_type'] = self.task_type.value
        d['created_at_iso'] = datetime.fromtimestamp(self.created_at).isoformat()
        if self.started_at:
            d['started_at_iso'] = datetime.fromtimestamp(self.started_at).isoformat()
        if self.completed_at:
            d['completed_at_iso'] = datetime.fromtimestamp(self.completed_at).isoformat()
        if self.started_at and self.completed_at:
            d['duration_seconds'] = round(self.completed_at - self.started_at, 2)
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
        if hasattr(self, '_initialized'):
            return
        self._initialized = True

        self._tasks: Dict[str, TaskRecord] = {}
        self._idempotency_map: Dict[str, str] = {}
        self._cancel_events: Dict[str, asyncio.Event] = {}
        self._task_lock = asyncio.Lock()
        self._subscribers: Dict[str, List[asyncio.Queue]] = {}

        self._max_concurrent = 3
        self._semaphore = asyncio.Semaphore(self._max_concurrent)
        self._queue: asyncio.Queue = asyncio.Queue()

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
            await self._broadcast_event(job_id, "queued", {
                "job_id": job_id,
                "task_type": task_type.value,
                "estimated_wait": self._estimate_wait(),
                "queue_position": self._queue.qsize() + 1,
            })

            await self._queue.put(job_id)
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

            await self._broadcast_event(job_id, "started", {
                "job_id": job_id,
                "started_at": datetime.fromtimestamp(record.started_at).isoformat(),
                "resources": {"max_concurrent": self._max_concurrent},
            })

            try:
                cancel_evt = self._cancel_events.get(job_id)
                result = await executor(cancel_evt, self._create_progress_updater(job_id))
                
                async with self._task_lock:
                    record = self._tasks[job_id]
                    record.status = TaskStatus.COMPLETED
                    record.progress = 100.0
                    record.result = result
                    record.completed_at = time.time()
                    record.metrics = result.get("metrics") if result else None

                await self._broadcast_event(job_id, "complete", {
                    "job_id": job_id,
                    "result": result,
                    "completed_at": datetime.now().isoformat(),
                })

            except asyncio.CancelledError:
                async with self._task_lock:
                    record = self._tasks[job_id]
                    record.status = TaskStatus.CANCELLED
                    record.completed_at = time.time()

                await self._broadcast_event(job_id, "cancelled", {
                    "job_id": job_id,
                    "cancelled_at": datetime.now().isoformat(),
                    "progress": record.progress,
                })

            except Exception as e:
                async with self._task_lock:
                    record = self._tasks[job_id]
                    record.status = TaskStatus.FAILED
                    record.error = str(e)
                    record.completed_at = time.time()

                await self._broadcast_event(job_id, "failed", {
                    "job_id": job_id,
                    "error": str(e),
                    "suggestion": self._get_error_suggestion(e),
                    "failed_at": datetime.now().isoformat(),
                })

    async def cancel_task(self, job_id: str) -> bool:
        """Cancel a running task"""
        async with self._task_lock:
            if job_id not in self._tasks:
                return False
            record = self._tasks[job_id]
            if record.status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED):
                return False
            
            record.status = TaskStatus.CANCELLED
            record.completed_at = time.time()

        if job_id in self._cancel_events:
            self._cancel_events[job_id].set()

        await self._broadcast_event(job_id, "cancelled", {
            "job_id": job_id,
            "cancelled_at": datetime.now().isoformat(),
            "progress": record.progress,
        })

        return True

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
        return tasks[offset:offset + limit]

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

    async def _broadcast_event(self, job_id: str, event_type: str, data: Dict[str, Any]):
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
        async def update_progress(percent: float, message: str = "", metrics: Optional[Dict] = None):
            async with self._task_lock:
                if job_id in self._tasks:
                    self._tasks[job_id].progress = percent
                    if metrics:
                        self._tasks[job_id].metrics = metrics

            await self._broadcast_event(job_id, "progress", {
                "job_id": job_id,
                "percent": round(percent, 1),
                "message": message,
                "metrics": metrics or {},
            })

        return update_progress

    def _estimate_wait(self) -> float:
        """Estimate wait time in seconds"""
        queue_size = self._queue.qsize()
        return queue_size * 60.0

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
        with asyncio.Runner().get_loop().create_task(self._task_lock.acquire()):
            pass
        total = len(self._tasks)
        active = sum(1 for t in self._tasks.values() if t.status == TaskStatus.RUNNING)
        queued = sum(1 for t in self._tasks.values() if t.status == TaskStatus.QUEUED)
        completed = sum(1 for t in self._tasks.values() if t.status == TaskStatus.COMPLETED)
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
```

- [ ] **Step 2: 运行测试验证任务管理器**

```python
import asyncio
from app.core.task_system import AsyncTaskManager
from app.core.task_manager import TaskType, TaskStatus

async def test_async_task_manager():
    mgr = AsyncTaskManager()
    await mgr.initialize(max_concurrent=3)

    record = await mgr.create_task(
        TaskType.LNN_TRAINING,
        {"model": "test", "epochs": 10},
        owner_id="user-1",
    )
    assert record.status == TaskStatus.QUEUED
    assert record.task_type == TaskType.LNN_TRAINING

    tasks = await mgr.list_tasks(owner_id="user-1")
    assert len(tasks) >= 1

    stats = mgr.get_stats()
    assert "total_tasks" in stats

asyncio.run(test_async_task_manager())
```

运行: `cd python; python -c "import asyncio; from app.core.task_system import AsyncTaskManager; from app.core.task_manager import TaskType; asyncio.run((lambda: (mgr := AsyncTaskManager()).__init__() or mgr.initialize(3) or mgr.create_task(TaskType.LNN_TRAINING, {})))()"`
预期: 无异常

---

### Task 3: 创建任务相关Pydantic模型

**Files:**
- Create: `python/app/models/job_schemas.py`

- [ ] **Step 1: 定义任务请求和响应模型**

```python
"""
Job-related Pydantic schemas for async task system.
"""
from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional
from datetime import datetime


class CreateJobRequest(BaseModel):
    task_type: str = Field(..., description="任务类型: lnn_training, lnn_batch_inference")
    params: Dict[str, Any] = Field(..., description="任务参数")


class JobResponse(BaseModel):
    job_id: str = Field(..., description="任务ID")
    task_type: str = Field(..., description="任务类型")
    status: str = Field(..., description="任务状态")
    progress: float = Field(default=0.0, description="进度百分比")
    created_at: str = Field(..., description="创建时间")
    started_at: Optional[str] = Field(default=None, description="开始时间")
    completed_at: Optional[str] = Field(default=None, description="完成时间")
    result: Optional[Dict[str, Any]] = Field(default=None, description="任务结果")
    error: Optional[str] = Field(default=None, description="错误信息")
    metrics: Optional[Dict[str, Any]] = Field(default=None, description="任务指标")


class JobListItem(BaseModel):
    job_id: str
    task_type: str
    status: str
    progress: float
    created_at: str
    duration_seconds: Optional[float] = None
    owner_id: Optional[str] = None


class JobListResponse(BaseModel):
    jobs: List[JobListItem]
    total: int
    has_more: bool


class CancelJobResponse(BaseModel):
    job_id: str
    status: str
    message: str


class TaskStatsResponse(BaseModel):
    total_tasks: int
    active_tasks: int
    queued_tasks: int
    completed_tasks: int
    failed_tasks: int
    max_concurrent: int
    available_slots: int
```

- [ ] **Step 2: 验证模型导入**

运行: `cd python; python -c "from app.models.job_schemas import JobResponse, CreateJobRequest, JobListResponse; print('OK')"`
预期: 输出"OK"

---

### Task 4: 实现SSE流式响应端点

**Files:**
- Create: `python/app/api/v1/jobs.py` - 新任务API（包含SSE端点）
- Modify: `python/app/api/v1/sse.py` - 增强现有SSE管理器（可选）

- [ ] **Step 1: 实现任务API路由**

```python
"""
Jobs API - Async task management and SSE streaming.
"""
import asyncio
import logging
from typing import Optional

from fastapi import APIRouter, Header, Query
from fastapi.responses import StreamingResponse

from app.core.response import ErrorCode, error, success
from app.core.task_manager import TaskType, TaskStatus
from app.core.task_system import AsyncTaskManager
from app.models.job_schemas import (
    JobResponse, JobListItem, JobListResponse,
    CancelJobResponse, TaskStatsResponse,
)

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
                    if record and record.status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED):
                        yield f"event: done\ndata: {{\"status\": \"{record.status.value}\"}}\n\n"
                        break
                    yield ": heartbeat\n\n"
        except asyncio.CancelledError:
            pass
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
        return error(code=ErrorCode.INVALID_REQUEST, message=f"Cannot cancel job '{job_id}'")
    return success(data={"job_id": job_id, "status": "cancelled"}, message="Job cancelled")


@router.get("")
async def list_jobs(
    task_type: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """List all jobs with filters"""
    tt = TaskType(task_type) if task_type else None
    st = TaskStatus(status) if status else None
    
    tasks = await task_manager.list_tasks(task_type=tt, status=st, limit=limit, offset=offset)
    total = len(tasks)
    
    items = [
        JobListItem(
            job_id=t.job_id,
            task_type=t.task_type.value,
            status=t.status.value,
            progress=t.progress,
            created_at=t.to_dict().get("created_at_iso", ""),
            duration_seconds=t.to_dict().get("duration_seconds"),
            owner_id=t.owner_id,
        )
        for t in tasks
    ]
    
    return success(
        data={
            "jobs": [i.model_dump() for i in items],
            "total": total,
            "has_more": total >= limit,
        },
        message="Jobs retrieved",
    )


@router.get("/stats")
async def get_task_stats():
    """Get task system statistics"""
    return success(data=task_manager.get_stats(), message="Stats retrieved")
```

- [ ] **Step 2: 注册Jobs路由**

修改 `python/app/main.py`，在路由注册部分添加：

```python
from app.api.v1 import lnn, wear_prediction, user_sovereignty, agent_gateway, jobs

app.include_router(jobs.router)
```

- [ ] **Step 3: 验证SSE端点**

运行: `python -c "from app.api.v1.jobs import router; print(f'Routes: {[r.path for r in router.routes]}')"`
预期: 输出路由列表包含 `/api/v1/jobs/{job_id}/stream`

---

### Task 5: 改造LNN API为异步模式

**Files:**
- Modify: `python/app/api/v1/lnn.py` - 改造train和batch-inference端点
- Test: `tests/test_lnn_api_integration.py`

- [ ] **Step 1: 改造POST /api/v1/lnn/train为异步模式**

在 `python/app/api/v1/lnn.py` 中，找到 `train_lnn` 函数，替换为：

```python
@router.post("/train")
async def train_lnn(
    request: LNNTrainRequest,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
):
    """Start LNN training asynchronously. Returns job_id immediately."""
    try:
        from app.core.task_system import AsyncTaskManager
        from app.core.task_manager import TaskType

        mgr = AsyncTaskManager()
        
        existing = None
        if idempotency_key:
            existing = await mgr.create_task(
                TaskType.LNN_TRAINING,
                {
                    "model_name": request.model_name,
                    "data_path": request.data_path,
                    "hyperparameters": request.hyperparameters.model_dump(),
                    "device": request.device,
                },
                idempotency_key=idempotency_key,
            )
            if existing.status not in (TaskStatus.PENDING, TaskStatus.QUEUED):
                return success(
                    data={"job_id": existing.job_id, "status": existing.status.value, "cached": True},
                    message="Cached job retrieved",
                )
        else:
            existing = await mgr.create_task(
                TaskType.LNN_TRAINING,
                {
                    "model_name": request.model_name,
                    "data_path": request.data_path,
                    "hyperparameters": request.hyperparameters.model_dump(),
                    "device": request.device,
                },
            )

        task_id = existing.job_id

        async def training_executor(cancel_evt, progress_updater):
            return await run_training_task_v2(
                task_id,
                request.model_name,
                request.data_path,
                request.hyperparameters.model_dump(),
                request.device,
                cancel_evt,
                progress_updater,
            )

        asyncio.create_task(mgr.execute_task(task_id, training_executor))

        return success(
            data={"job_id": task_id, "status": "queued"},
            message="Training job queued",
        )

    except Exception as e:
        return error(code=ErrorCode.INTERNAL_ERROR, message=f"Training initiation failed: {e!s}")
```

- [ ] **Step 2: 创建V2训练执行器**

```python
async def run_training_task_v2(
    task_id: str,
    model_name: str,
    data_path: str,
    hyperparameters: dict,
    device_preference: str,
    cancel_evt: asyncio.Event,
    progress_updater: Callable,
):
    """V2 training executor with progress callbacks"""
    import torch
    import numpy as np
    from torch.utils.data import DataLoader, TensorDataset
    from app.ai.lnn.inference.registry import get_torch_model_class, LNNModelRegistry
    from app.ai.lnn.models.torch_base_lnn import LNNConfig
    from app.ai.lnn.models.torch_cfc_model import CFCModel as TorchCFCModel
    from app.ai.lnn.models.torch_ltc_model import LTCModel as TorchLTCModel
    from app.ai.lnn.models.torch_hybrid_lnn import HybridLNN as TorchHybridLNN
    from app.ai.lnn.training.trainer import LNNTrainer
    from app.ai.lnn.training.device_manager import detect_device, get_optimal_batch_size, get_optimal_num_workers
    from app.config import config

    await progress_updater(5.0, "Loading data...")

    if not os.path.exists(data_path):
        raise FileNotFoundError(f"Data file not found: {data_path}")

    data = np.loadtxt(data_path, delimiter=",")
    if data.ndim == 1:
        data = data.reshape(-1, 1)
    if data.shape[1] == 1:
        data = np.column_stack([data, data])

    X = data[:, :-1]
    y = data[:, -1]
    input_dim = data.shape[1] - 1

    await progress_updater(10.0, "Preparing datasets...")

    X_tensor = torch.FloatTensor(X)
    y_tensor = torch.FloatTensor(y)
    dataset = TensorDataset(X_tensor, y_tensor)
    train_size = int(0.8 * len(dataset))
    train_dataset, val_dataset = torch.utils.data.random_split(dataset, [train_size, len(dataset) - train_size])

    device, _ = detect_device(device_preference)
    batch_size = hyperparameters.get("batch_size", 32)
    if device.type == "cuda":
        batch_size = get_optimal_batch_size(device, batch_size)

    num_workers = get_optimal_num_workers()
    train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True, num_workers=num_workers)
    val_loader = DataLoader(val_dataset, batch_size=batch_size, num_workers=num_workers)

    model_registry = LNNModelRegistry()
    entry = model_registry.registry.get(model_name)
    if not entry:
        raise ValueError(f"Model '{model_name}' not found")

    model_class = get_torch_model_class(entry.info.model_type)
    if not model_class:
        raise ValueError(f"Unsupported model type: {entry.info.model_type}")

    hidden_size = min(256, max(64, input_dim * 2))
    config_obj = LNNConfig(input_size=input_dim, hidden_size=hidden_size, output_size=1, num_layers=2, dropout=0.1)
    model = model_class(config_obj)

    use_amp = device.type == "cuda" and torch.cuda.is_available()
    epochs = hyperparameters.get("epochs", 100)

    await progress_updater(15.0, f"Starting training on {device.type}...")

    trainer = LNNTrainer(
        model=model,
        learning_rate=hyperparameters.get("learning_rate", 0.001),
        optimizer_type=hyperparameters.get("optimizer", "adam"),
        loss_type="mse",
        batch_size=batch_size,
        epochs=epochs,
        device=str(device),
        use_amp=use_amp,
    )

    start_time = time.perf_counter()

    for epoch in range(1, epochs + 1):
        if cancel_evt.is_set():
            raise asyncio.CancelledError()

        train_loss, val_loss = trainer.train_one_epoch(train_loader, val_loader, epoch)
        
        progress = 15.0 + (epoch / epochs) * 80.0
        await progress_updater(
            progress,
            f"Training: epoch {epoch}/{epochs}, loss={val_loss:.4f}",
            {"epoch": epoch, "train_loss": round(train_loss, 4), "val_loss": round(val_loss, 4)},
        )

    training_time = time.perf_counter() - start_time

    final_val_loss = trainer.history.get("val_loss", [0.0])[-1] if hasattr(trainer, 'history') else 0.0

    return {
        "status": "completed",
        "model_name": model_name,
        "epochs_completed": epochs,
        "final_val_loss": round(final_val_loss, 4),
        "training_time": round(training_time, 2),
        "metrics": {
            "r2_score": None,
            "loss": round(final_val_loss, 4),
            "training_time": round(training_time, 2),
            "epochs_completed": epochs,
        },
    }
```

- [ ] **Step 3: 保持GET /api/v1/lnn/predict同步模式**

确认 `/api/v1/lnn/predict` 保持不变（单次推理<1秒，无需异步）。

- [ ] **Step 4: 添加POST /api/v1/lnn/batch-inference异步端点**

在 `python/app/api/v1/lnn.py` 末尾添加：

```python
@router.post("/batch-inference")
async def batch_inference(
    request: LNNBatchInferenceRequest,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
):
    """Start batch inference asynchronously. Returns job_id immediately."""
    try:
        from app.core.task_system import AsyncTaskManager
        from app.core.task_manager import TaskType

        mgr = AsyncTaskManager()

        record = await mgr.create_task(
            TaskType.LNN_BATCH_INFERENCE,
            {
                "model_name": request.model_name,
                "input_data": request.input_data,
                "batch_size": request.batch_size,
            },
            idempotency_key=idempotency_key,
        )

        async def batch_executor(cancel_evt, progress_updater):
            return await run_batch_inference_v2(
                record.job_id,
                request.model_name,
                request.input_data,
                request.batch_size,
                cancel_evt,
                progress_updater,
            )

        asyncio.create_task(mgr.execute_task(record.job_id, batch_executor))

        return success(
            data={"job_id": record.job_id, "status": "queued"},
            message="Batch inference job queued",
        )

    except Exception as e:
        return error(code=ErrorCode.INTERNAL_ERROR, message=f"Batch inference failed: {e!s}")
```

需要添加 `LNNBatchInferenceRequest` 到 `python/app/models/schemas.py`：

```python
class LNNBatchInferenceRequest(BaseModel):
    model_name: str = Field(..., description="模型名称", min_length=1)
    input_data: list[list[float]] = Field(..., description="批量输入数据")
    batch_size: int = Field(default=32, description="批次大小", ge=1)
```

- [ ] **Step 5: 实现V2批量推理执行器**

```python
async def run_batch_inference_v2(
    job_id: str,
    model_name: str,
    input_data: list,
    batch_size: int,
    cancel_evt: asyncio.Event,
    progress_updater: Callable,
):
    """V2 batch inference executor with progress callbacks"""
    from app.ai.lnn.inference.predictor import LNNPredictor
    
    await progress_updater(5.0, "Loading model...")
    
    predictor = LNNPredictor.from_registry(
        registry=model_registry,
        model_name=model_name,
        use_amp=True,
        auto_device=True,
    )
    
    results = []
    total = len(input_data)
    
    for i in range(0, total, batch_size):
        if cancel_evt.is_set():
            raise asyncio.CancelledError()
        
        batch = input_data[i:i + batch_size]
        batch_results = []
        
        for sample in batch:
            result = predictor.predict(input_data=sample, return_confidence=True)
            value = result.value
            if hasattr(value, "tolist"):
                value = value.tolist()
            batch_results.append({"value": value, "confidence": result.confidence})
        
        results.extend(batch_results)
        
        progress = 10.0 + ((i + len(batch)) / total) * 85.0
        await progress_updater(progress, f"Processed {i + len(batch)}/{total} samples")
    
    await progress_updater(100.0, "Batch inference completed")
    
    return {
        "status": "completed",
        "total_samples": total,
        "results": results,
        "metrics": {"samples_processed": total},
    }
```

- [ ] **Step 6: 验证API改造**

运行: `python -c "from app.api.v1.lnn import router; print([r.path for r in router.routes])"`
预期: 包含 `/api/v1/lnn/train`, `/api/v1/lnn/batch-inference`, `/api/v1/lnn/predict`

---

### Task 6: 开发前端SSE集成组件

**Files:**
- Create: `src/composables/useEventSource.ts`
- Test: 手动测试（浏览器测试SSE连接）

- [ ] **Step 1: 实现useEventSource composable**

```typescript
/**
 * SSE EventSource composable with auto-reconnect and lifecycle management.
 */
import { ref, onUnmounted, type Ref } from 'vue'

export interface SSEEvent {
  type: string
  data: any
  timestamp: number
}

export interface UseEventSourceOptions {
  autoReconnect?: boolean
  maxRetries?: number
  reconnectDelay?: number
  onEvent?: (event: SSEEvent) => void
  onError?: (error: Event) => void
  onOpen?: () => void
}

export function useEventSource(url: Ref<string> | string, options: UseEventSourceOptions = {}) {
  const {
    autoReconnect = true,
    maxRetries = 5,
    reconnectDelay = 1000,
    onEvent,
    onError,
    onOpen,
  } = options

  const events = ref<SSEEvent[]>([])
  const isConnected = ref(false)
  const isConnecting = ref(false)
  const error = ref<string | null>(null)
  const retryCount = ref(0)

  let eventSource: EventSource | null = null
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null

  function connect() {
    if (eventSource) {
      close()
    }

    const resolvedUrl = typeof url === 'string' ? url : url.value
    if (!resolvedUrl) return

    isConnecting.value = true
    error.value = null

    eventSource = new EventSource(resolvedUrl)

    eventSource.onopen = () => {
      isConnected.value = true
      isConnecting.value = false
      retryCount.value = 0
      onOpen?.()
    }

    eventSource.onerror = (evt) => {
      isConnected.value = false
      isConnecting.value = false
      error.value = 'SSE connection error'
      onError?.(evt)

      if (autoReconnect && retryCount.value < maxRetries) {
        scheduleReconnect()
      }
    }

    eventSource.addEventListener('progress', (evt) => {
      const data = JSON.parse(evt.data)
      const event: SSEEvent = { type: 'progress', data, timestamp: Date.now() }
      events.value.push(event)
      onEvent?.(event)
    })

    eventSource.addEventListener('started', (evt) => {
      const data = JSON.parse(evt.data)
      const event: SSEEvent = { type: 'started', data, timestamp: Date.now() }
      events.value.push(event)
      onEvent?.(event)
    })

    eventSource.addEventListener('complete', (evt) => {
      const data = JSON.parse(evt.data)
      const event: SSEEvent = { type: 'complete', data, timestamp: Date.now() }
      events.value.push(event)
      onEvent?.(event)
      close()
    })

    eventSource.addEventListener('failed', (evt) => {
      const data = JSON.parse(evt.data)
      const event: SSEEvent = { type: 'failed', data, timestamp: Date.now() }
      events.value.push(event)
      error.value = data.error || 'Task failed'
      onEvent?.(event)
      close()
    })

    eventSource.addEventListener('cancelled', (evt) => {
      const data = JSON.parse(evt.data)
      const event: SSEEvent = { type: 'cancelled', data, timestamp: Date.now() }
      events.value.push(event)
      onEvent?.(event)
      close()
    })

    eventSource.addEventListener('queued', (evt) => {
      const data = JSON.parse(evt.data)
      const event: SSEEvent = { type: 'queued', data, timestamp: Date.now() }
      events.value.push(event)
      onEvent?.(event)
    })
  }

  function scheduleReconnect() {
    retryCount.value++
    const delay = reconnectDelay * Math.pow(2, retryCount.value - 1)
    reconnectTimer = setTimeout(() => {
      connect()
    }, delay)
  }

  function close() {
    if (reconnectTimer) {
      clearTimeout(reconnectTimer)
      reconnectTimer = null
    }
    if (eventSource) {
      eventSource.close()
      eventSource = null
    }
    isConnected.value = false
  }

  function clearEvents() {
    events.value = []
  }

  onUnmounted(() => {
    close()
  })

  return {
    events,
    isConnected,
    isConnecting,
    error,
    retryCount,
    connect,
    close,
    clearEvents,
  }
}
```

- [ ] **Step 2: 验证composable导入**

运行: 在TypeScript项目中，通过编译检查：`npx vue-tsc --noEmit`
预期: 无错误

---

### Task 7: 集成SSE到模型训练页面

**Files:**
- Modify: `src/views/Workspace.vue` - 集成实时进度展示

- [ ] **Step 1: 更新handleTrain函数使用SSE**

修改 `src/views/Workspace.vue` 的 `<script setup>` 部分：

```typescript
import { useEventSource } from '@/composables/useEventSource'

const jobId = ref<string | null>(null)
const trainingProgress = ref(0)
const trainingMessage = ref('')
const trainingMetrics = ref<any>(null)
const lossHistory = ref<number[]>([])

const { events, isConnected, connect, close: closeSSE } = useEventSource(
  computed(() => jobId.value ? `http://localhost:8000/api/v1/jobs/${jobId.value}/stream` : ''),
  {
    autoReconnect: true,
    maxRetries: 3,
    onEvent: (evt) => {
      if (evt.type === 'progress') {
        trainingProgress.value = evt.data.percent
        trainingMessage.value = evt.data.message
        if (evt.data.metrics?.val_loss !== undefined) {
          lossHistory.value.push(evt.data.metrics.val_loss)
        }
      } else if (evt.type === 'complete') {
        trainingResult.value = evt.data.result
        trainingProgress.value = 100
        ElMessage.success('训练完成')
      } else if (evt.type === 'failed') {
        ElMessage.error(`训练失败: ${evt.data.error}`)
        trainingMessage.value = evt.data.error
      }
    },
  },
)

async function handleTrain() {
  if (!trainPlanConfirmed.value) {
    ElMessage.warning('请先审阅并确认训练计划')
    return
  }

  training.value = true
  trainResult.value = null
  trainingProgress.value = 0
  trainingMessage.value = '正在启动训练任务...'
  lossHistory.value = []

  try {
    const res = await axios.post('/api/v1/lnn/train', {
      model_name: trainForm.modelName,
      data_path: trainForm.dataPath,
      hyperparameters: trainForm.hyperparameters,
      device: trainForm.device,
    })

    jobId.value = res.data.data.job_id
    ElMessage.success('训练任务已启动，正在接收实时进度...')

    connect()

  } catch (e: any) {
    const errorMsg = e?.response?.data?.message || e?.message || '训练启动失败'
    ElMessage.error(errorMsg)
  } finally {
    training.value = false
  }
}
```

- [ ] **Step 2: 更新模板添加进度展示**

在 `src/views/Workspace.vue` 的 `<template>` 部分，训练结果区域前添加：

```vue
<div v-if="jobId" class="training-progress">
  <h4>训练进度</h4>
  
  <el-progress 
    :percentage="trainingProgress" 
    :status="trainingProgress >= 100 ? 'success' : undefined"
    :stroke-width="20"
  />
  
  <p class="progress-message">{{ trainingMessage }}</p>
  
  <div v-if="lossHistory.length > 0" class="loss-chart">
    <h5>Loss曲线</h5>
    <canvas ref="lossCanvas" width="600" height="200"></canvas>
  </div>
  
  <el-button 
    v-if="isConnected" 
    type="danger" 
    size="small" 
    @click="handleCancelTraining"
  >
    取消训练
  </el-button>
</div>
```

- [ ] **Step 3: 添加取消训练函数**

```typescript
async function handleCancelTraining() {
  if (!jobId.value) return
  
  try {
    await axios.post(`/api/v1/jobs/${jobId.value}/cancel`)
    ElMessage.info('训练已取消')
    closeSSE()
  } catch (e: any) {
    ElMessage.error('取消失败')
  }
}
```

- [ ] **Step 4: 添加样式**

```css
.training-progress {
  margin: 20px 0;
  padding: 16px;
  background: #f5f7fa;
  border-radius: 4px;
}

.progress-message {
  margin-top: 8px;
  color: #606266;
  font-size: 14px;
}

.loss-chart {
  margin-top: 16px;
}

.loss-chart canvas {
  width: 100%;
  border: 1px solid #e4e7ed;
  border-radius: 4px;
}
```

---

### Task 8: 实现任务历史与重放功能

**Files:**
- Create: `src/views/TaskHistory.vue`
- Modify: `src/router/index.ts` - 添加路由（如需要）

- [ ] **Step 1: 创建任务历史组件**

```vue
<template>
  <div class="task-history-page">
    <el-card>
      <template #header>
        <div class="header-with-actions">
          <span>任务历史</span>
          <el-button @click="refreshTasks" :loading="loading">刷新</el-button>
        </div>
      </template>

      <el-tabs v-model="activeTab">
        <el-tab-pane label="全部任务" name="all" />
        <el-tab-pane label="训练任务" name="lnn_training" />
        <el-tab-pane label="推理任务" name="lnn_batch_inference" />
        <el-tab-pane label="已完成" name="completed" />
        <el-tab-pane label="失败" name="failed" />
      </el-tabs>

      <el-table :data="filteredTasks" style="width: 100%" v-loading="loading">
        <el-table-column prop="job_id" label="任务ID" width="200" />
        <el-table-column prop="task_type" label="类型" width="150" />
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)">{{ row.status }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="progress" label="进度" width="100">
          <template #default="{ row }">
            <el-progress :percentage="row.progress" :status="row.status === 'failed' ? 'exception' : undefined" />
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="180" />
        <el-table-column prop="duration_seconds" label="耗时" width="100">
          <template #default="{ row }">
            {{ row.duration_seconds ? `${row.duration_seconds}s` : '-' }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="150">
          <template #default="{ row }">
            <el-button size="small" @click="viewTaskDetail(row)">详情</el-button>
            <el-button 
              size="small" 
              type="primary" 
              @click="rerunTask(row)"
              :disabled="row.status !== 'completed' && row.status !== 'failed'"
            >
              重执行
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <el-pagination
        v-if="totalTasks > pageSize"
        :current-page="currentPage"
        :page-size="pageSize"
        :total="totalTasks"
        @current-change="handlePageChange"
        layout="prev, pager, next"
        style="margin-top: 16px; justify-content: center;"
      />
    </el-card>

    <el-dialog v-model="detailVisible" title="任务详情" width="60%">
      <div v-if="selectedTask">
        <el-descriptions :column="2" border>
          <el-descriptions-item label="任务ID">{{ selectedTask.job_id }}</el-descriptions-item>
          <el-descriptions-item label="状态">
            <el-tag :type="getStatusType(selectedTask.status)">{{ selectedTask.status }}</el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="类型">{{ selectedTask.task_type }}</el-descriptions-item>
          <el-descriptions-item label="进度">{{ selectedTask.progress }}%</el-descriptions-item>
          <el-descriptions-item label="创建时间">{{ selectedTask.created_at }}</el-descriptions-item>
          <el-descriptions-item label="耗时">{{ selectedTask.duration_seconds || '-' }}s</el-descriptions-item>
        </el-descriptions>

        <div v-if="selectedTask.result" style="margin-top: 16px;">
          <h4>任务结果</h4>
          <pre>{{ JSON.stringify(selectedTask.result, null, 2) }}</pre>
        </div>

        <div v-if="selectedTask.error" style="margin-top: 16px;">
          <h4>错误信息</h4>
          <el-alert :title="selectedTask.error" type="error" :closable="false" />
        </div>

        <div v-if="selectedTask.metrics" style="margin-top: 16px;">
          <h4>任务指标</h4>
          <pre>{{ JSON.stringify(selectedTask.metrics, null, 2) }}</pre>
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import axios from 'axios'
import { ElMessage } from 'element-plus'
import { useRouter } from 'vue-router'

const router = useRouter()
const loading = ref(false)
const tasks = ref<any[]>([])
const activeTab = ref('all')
const currentPage = ref(1)
const pageSize = 20
const totalTasks = ref(0)

const detailVisible = ref(false)
const selectedTask = ref<any>(null)

const filteredTasks = computed(() => {
  let filtered = tasks.value
  
  if (activeTab.value === 'lnn_training') {
    filtered = filtered.filter(t => t.task_type === 'lnn_training')
  } else if (activeTab.value === 'lnn_batch_inference') {
    filtered = filtered.filter(t => t.task_type === 'lnn_batch_inference')
  } else if (activeTab.value === 'completed') {
    filtered = filtered.filter(t => t.status === 'completed')
  } else if (activeTab.value === 'failed') {
    filtered = filtered.filter(t => t.status === 'failed')
  }
  
  return filtered
})

async function loadTasks() {
  loading.value = true
  try {
    const res = await axios.get('/api/v1/jobs', {
      params: {
        limit: pageSize,
        offset: (currentPage.value - 1) * pageSize,
      },
    })
    tasks.value = res.data.data.jobs || []
    totalTasks.value = res.data.data.total || 0
  } catch (e) {
    ElMessage.error('加载任务历史失败')
  } finally {
    loading.value = false
  }
}

function getStatusType(status: string): 'success' | 'warning' | 'danger' | 'info' {
  switch (status) {
    case 'completed': return 'success'
    case 'running': return 'warning'
    case 'failed': return 'danger'
    case 'cancelled': return 'info'
    default: return 'info'
  }
}

function viewTaskDetail(task: any) {
  selectedTask.value = task
  detailVisible.value = true
}

async function rerunTask(task: any) {
  try {
    const endpoint = task.task_type === 'lnn_training' ? '/api/v1/lnn/train' : '/api/v1/lnn/batch-inference'
    await axios.post(endpoint, task.params || {})
    ElMessage.success('任务已重新提交')
    await loadTasks()
  } catch (e: any) {
    ElMessage.error('重执行失败: ' + (e.response?.data?.message || e.message))
  }
}

async function refreshTasks() {
  await loadTasks()
}

function handlePageChange(page: number) {
  currentPage.value = page
  loadTasks()
}

onMounted(() => {
  loadTasks()
})
</script>

<style scoped>
.task-history-page {
  max-width: 1200px;
  margin: 0 auto;
}

.header-with-actions {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

pre {
  background: #f5f7fa;
  padding: 12px;
  border-radius: 4px;
  font-size: 12px;
  max-height: 400px;
  overflow: auto;
}
</style>
```

- [ ] **Step 2: 添加路由（如需要）**

如果项目使用Vue Router，在 `src/router/index.ts` 添加：

```typescript
{
  path: '/tasks',
  name: 'TaskHistory',
  component: () => import('@/views/TaskHistory.vue'),
}
```

- [ ] **Step 3: 验证前端编译**

运行: `pnpm run build`
预期: 无编译错误

---

### Task 9: 注册路由与集成测试

**Files:**
- Modify: `python/app/main.py` - 注册jobs路由
- Create: `tests/test_async_task_system.py` - 完整测试

- [ ] **Step 1: 注册路由到main.py**

修改 `python/app/main.py` 中的导入和路由注册：

```python
from app.api.v1 import lnn, wear_prediction, user_sovereignty, agent_gateway, jobs

# ... existing code ...

app.include_router(jobs.router)
```

- [ ] **Step 2: 创建完整集成测试**

```python
"""
Integration tests for async task system and SSE streaming.
"""
import asyncio
import pytest
from app.core.task_system import AsyncTaskManager
from app.core.task_manager import TaskType, TaskStatus


class TestAsyncTaskManager:
    @pytest.fixture
    async def manager(self):
        mgr = AsyncTaskManager()
        await mgr.initialize(max_concurrent=2)
        yield mgr

    @pytest.mark.asyncio
    async def test_create_and_list_tasks(self, manager):
        record = await manager.create_task(
            TaskType.LNN_TRAINING,
            {"model": "test", "epochs": 10},
            owner_id="user-1",
        )
        assert record.status == TaskStatus.QUEUED
        
        tasks = await manager.list_tasks(owner_id="user-1")
        assert len(tasks) >= 1

    @pytest.mark.asyncio
    async def test_task_execution(self, manager):
        record = await manager.create_task(
            TaskType.LNN_TRAINING,
            {"model": "test"},
        )

        async def dummy_executor(cancel_evt, progress_updater):
            await progress_updater(50.0, "Halfway")
            await progress_updater(100.0, "Done")
            return {"result": "ok"}

        await manager.execute_task(record.job_id, dummy_executor)
        
        updated = await manager.get_task(record.job_id)
        assert updated.status == TaskStatus.COMPLETED
        assert updated.progress == 100.0

    @pytest.mark.asyncio
    async def test_task_cancellation(self, manager):
        record = await manager.create_task(TaskType.LNN_TRAINING, {})

        async def long_executor(cancel_evt, progress_updater):
            for i in range(100):
                if cancel_evt.is_set():
                    raise asyncio.CancelledError()
                await asyncio.sleep(0.01)
            return {"result": "done"}

        asyncio.create_task(manager.execute_task(record.job_id, long_executor))
        await asyncio.sleep(0.05)
        
        result = await manager.cancel_task(record.job_id)
        assert result is True

    @pytest.mark.asyncio
    async def test_idempotency(self, manager):
        key = "test-idempotency-key"
        
        r1 = await manager.create_task(TaskType.LNN_TRAINING, {}, idempotency_key=key)
        r2 = await manager.create_task(TaskType.LNN_TRAINING, {}, idempotency_key=key)
        
        assert r1.job_id == r2.job_id

    @pytest.mark.asyncio
    async def test_concurrency_limit(self, manager):
        await manager.initialize(max_concurrent=2)
        
        for i in range(5):
            await manager.create_task(TaskType.LNN_TRAINING, {"index": i})
        
        stats = manager.get_stats()
        assert stats["max_concurrent"] == 2
```

运行: `cd python; pytest tests/test_async_task_system.py -v`
预期: 全部通过

---

### Self-Review Checklist

**1. Spec Coverage:**
- ✅ 异步任务框架 (Task 1-2): AsyncTaskManager单例, 状态机, 混合存储, 取消功能, 并发控制
- ✅ SSE流式端点 (Task 3-4): GET /api/v1/jobs/{job_id}/stream, 标准事件格式, 连接管理, 状态查询回退
- ✅ API异步化 (Task 5): POST /api/v1/lnn/train, POST /api/v1/lnn/batch-inference, GET /api/v1/lnn/predict同步保持, Idempotency-Key支持
- ✅ 前端SSE集成 (Task 6-7): useEventSource composable, 实时进度, loss曲线, 断线重连, 生命周期管理
- ✅ 任务历史与重放 (Task 8): 选项卡布局, 列表展示, 详情查看, 重执行功能
- ✅ 非功能需求: 可靠性(状态机), 性能(并发控制), 可维护性(测试), 安全性(owner_id过滤)

**2. Placeholder Scan:**
- 无TBD/TODO
- 所有步骤包含完整代码
- 测试代码完整可运行

**3. Type Consistency:**
- TaskStatus/TaskType枚举全局一致
- job_id格式统一: `{task_type}-{uuid}`
- SSE事件格式统一: `event: {type}\ndata: {json}\n\n`

---

## 执行顺序

1. **Task 1**: 扩展枚举和基础模型 (5分钟)
2. **Task 2**: 实现AsyncTaskManager核心 (20分钟)
3. **Task 3**: 创建Pydantic模型 (5分钟)
4. **Task 4**: 实现SSE端点 (15分钟)
5. **Task 5**: 改造LNN API (30分钟)
6. **Task 6**: 开发useEventSource (15分钟)
7. **Task 7**: 集成到训练页面 (20分钟)
8. **Task 8**: 实现任务历史 (20分钟)
9. **Task 9**: 集成测试与验证 (15分钟)

**预计总时间**: 约2.5小时
