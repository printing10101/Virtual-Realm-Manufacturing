"""Agent Gateway 共享状态与服务实例。

P3-2：将原 ``agent_gateway.py`` 中的模块级可变全局状态
（``_active_training``、``_training_sem``）封装为 :class:`TrainingCoordinator`，
消除"模块级可变全局"反模式，便于测试隔离与未来扩展为多实例场景。

本模块集中管理跨子模块共享的服务实例与常量，避免循环导入。
"""

from __future__ import annotations

import asyncio
import logging

from app.agent.orchestrator import AgentOrchestrator
from app.dependencies import get_model_registry_service

logger = logging.getLogger(__name__)

# 训练并发上限：与历史实现保持一致，不可随意上调（GPU 资源约束）
MAX_CONCURRENT_TRAINING = 3

# SSE 心跳超时（秒）：超过此时间无事件则发送 heartbeat 注释帧保持连接
SSE_HEARTBEAT_TIMEOUT = 30.0

# torch 相关模块：桌面版可能没有 torch，条件导入
TORCH_AVAILABLE = False
try:
    from app.ai.lnn.inference.predictor import LNNPredictor, PredictionResult
    TORCH_AVAILABLE = True
except ImportError:
    LNNPredictor = None  # type: ignore
    PredictionResult = None  # type: ignore


class TrainingCoordinator:
    """训练任务协调器（P3-2：封装模块级可变状态）。

    职责：
    - 管理活跃训练任务集合（替代原 ``_active_training: set[str]``）
    - 懒初始化 :class:`asyncio.Semaphore`（绑定到当前事件循环，[A-H16]）
    - 记录训练任务完成/失败/取消的回调（替代原 ``_handle_training_done``）

    设计目标：
    - 替代原模块级 ``_active_training`` / ``_training_sem`` / ``_get_training_sem`` /
      ``_handle_training_done`` 全局变量与函数
    - 单元测试可创建独立实例避免相互污染
    - 保留懒初始化语义（[A-H16]）
    """

    def __init__(self, max_concurrent: int = MAX_CONCURRENT_TRAINING) -> None:
        self._max_concurrent = max_concurrent
        self._active_training: set[str] = set()
        # [A-H16] 懒初始化 asyncio.Semaphore，避免模块导入时绑定到错误的事件循环
        self._training_sem: asyncio.Semaphore | None = None

    @property
    def max_concurrent(self) -> int:
        return self._max_concurrent

    def get_semaphore(self) -> asyncio.Semaphore:
        """[A-H16] 懒初始化 asyncio.Semaphore，绑定到当前运行的事件循环。"""
        if self._training_sem is None:
            self._training_sem = asyncio.Semaphore(self._max_concurrent)
        return self._training_sem

    def is_active(self, task_id: str) -> bool:
        return task_id in self._active_training

    def add_active(self, task_id: str) -> None:
        self._active_training.add(task_id)

    def discard_active(self, task_id: str) -> None:
        self._active_training.discard(task_id)

    def handle_task_done(self, task: asyncio.Task, task_id: str) -> None:
        """Callback to handle training task completion and log exceptions."""
        if task.cancelled():
            logger.info("Training task cancelled: %s", task_id)
        elif task.exception():
            logger.error(
                "Training task failed: %s - %s",
                task_id,
                task.exception(),
            )


# 单例：替代原模块级 _active_training / _training_sem / _get_training_sem /
# _handle_training_done，保持行为等价
training_coordinator = TrainingCoordinator(MAX_CONCURRENT_TRAINING)

# Use the unified service layer — do NOT instantiate LNNModelRegistry directly
registry_service = get_model_registry_service()
model_registry = registry_service.model_registry
agent_model_cache = registry_service.model_cache
training_tasks = registry_service.get_training_tasks()

# Agent Orchestrator for workflow pipeline execution
orchestrator = AgentOrchestrator()
