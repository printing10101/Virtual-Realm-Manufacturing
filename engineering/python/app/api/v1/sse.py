"""
SSE (Server-Sent Events) training status push system.

Provides real-time training status updates to multiple clients,
replacing polling mechanism with event-driven push.
"""

import asyncio
import json
import logging
import time
from typing import Any, Dict, Optional
from dataclasses import dataclass
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


@dataclass
class SSEClient:
    """Represents a single SSE client connection."""

    queue: asyncio.Queue
    connected_at: float
    last_activity: float
    client_id: str


class SSEConnectionManager:
    """
    Manages SSE connections for training tasks.

    Supports multiple clients per task, event broadcasting,
    and connection lifecycle management.
    """

    def __init__(self, timeout_seconds: int = 1800):
        self._clients: Dict[str, Dict[str, SSEClient]] = {}
        self._timeout = timeout_seconds
        # [H4] asyncio.Lock 懒初始化：模块级 sse_manager 实例化时创建 Lock 会
        # 绑定到导入时的事件循环，多事件循环场景下抛 RuntimeError。
        self._lock: Optional[asyncio.Lock] = None
        self._cancel_events: Dict[str, asyncio.Event] = {}

    def _get_lock(self) -> asyncio.Lock:
        """懒初始化 SSE 管理器锁，绑定到首次调用的事件循环。"""
        if self._lock is None:
            self._lock = asyncio.Lock()
        return self._lock

    async def subscribe(self, task_id: str, client_id: str) -> SSEClient:
        """Subscribe a client to a training task's SSE events."""
        async with self._get_lock():
            if task_id not in self._clients:
                self._clients[task_id] = {}
                self._cancel_events[task_id] = asyncio.Event()

            client = SSEClient(
                queue=asyncio.Queue(maxsize=100),
                connected_at=time.time(),
                last_activity=time.time(),
                client_id=client_id,
            )
            self._clients[task_id][client_id] = client
            logger.info("Client %s subscribed to task %s", client_id, task_id)
            return client

    async def unsubscribe(self, task_id: str, client_id: str):
        """Unsubscribe a client from a training task."""
        async with self._get_lock():
            if task_id in self._clients and client_id in self._clients[task_id]:
                del self._clients[task_id][client_id]
                logger.info("Client %s unsubscribed from task %s", client_id, task_id)

                if not self._clients[task_id]:
                    del self._clients[task_id]
                    if task_id in self._cancel_events:
                        del self._cancel_events[task_id]

    async def broadcast(self, task_id: str, event_type: str, data: dict[str, Any]):
        """Broadcast an event to all clients subscribed to a task."""
        async with self._get_lock():
            if task_id not in self._clients:
                return

            event = self._format_event(event_type, data)
            clients_to_remove = []

            for client_id, client in self._clients[task_id].items():
                try:
                    await client.queue.put(event)
                    client.last_activity = time.time()
                except (asyncio.QueueFull, RuntimeError, AttributeError) as e:
                    # 队列满或客户端异常时标记为待移除，记录日志以便排查
                    logger.warning("Failed to send SSE event to client %s: %s", client_id, e)
                    clients_to_remove.append(client_id)

            for cid in clients_to_remove:
                self._clients[task_id].pop(cid, None)

    async def send_to_client(
        self, task_id: str, client_id: str, event_type: str, data: dict[str, Any]
    ):
        """Send an event to a specific client."""
        async with self._get_lock():
            if task_id not in self._clients or client_id not in self._clients[task_id]:
                return

            client = self._clients[task_id][client_id]
            event = self._format_event(event_type, data)
            # [A-H18] 使用 put_nowait 并捕获 QueueFull，避免队列满时持锁阻塞导致死锁
            try:
                client.queue.put_nowait(event)
                client.last_activity = time.time()
            except asyncio.QueueFull:
                logger.warning(
                    "SSE queue full for client %s on task %s, event dropped",
                    client_id,
                    task_id,
                )

    def _format_event(self, event_type: str, data: dict[str, Any]) -> str:
        """Format data as SSE event string."""
        return f"event: {event_type}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"

    async def signal_cancel(self, task_id: str):
        """Signal cancellation for a training task."""
        async with self._get_lock():
            if task_id in self._cancel_events:
                self._cancel_events[task_id].set()
                logger.info("Cancel signal sent for task %s", task_id)

    def get_cancel_event(self, task_id: str) -> Optional[asyncio.Event]:
        """Get the cancellation event for a task."""
        return self._cancel_events.get(task_id)

    async def cleanup_timeout_clients(self):
        """Remove clients that have timed out."""
        async with self._get_lock():
            now = time.time()
            for task_id in list(self._clients.keys()):
                for client_id in list(self._clients[task_id].keys()):
                    client = self._clients[task_id][client_id]
                    if now - client.last_activity > self._timeout:
                        del self._clients[task_id][client_id]
                        logger.info("Client %s timed out for task %s", client_id, task_id)

                if not self._clients[task_id]:
                    del self._clients[task_id]
                    if task_id in self._cancel_events:
                        del self._cancel_events[task_id]

    def get_active_clients_count(self, task_id: str) -> int:
        """Get number of active clients for a task."""
        if task_id not in self._clients:
            return 0
        return len(self._clients[task_id])

    def get_total_clients_count(self) -> int:
        """Get total number of active SSE clients."""
        return sum(len(clients) for clients in self._clients.values())


class TrainingProgressCallback:
    """
    Callback handler for training progress events.

    Bridges training loop with SSE broadcast system.
    """

    def __init__(self, manager: SSEConnectionManager, task_id: str, total_epochs: int):
        self._manager = manager
        self._task_id = task_id
        self._total_epochs = total_epochs
        self._start_time = time.time()

    def __call__(
        self, epoch: int, loss: float, metrics: Optional[dict] = None, **kwargs
    ):
        """Called after each training epoch."""
        progress = (
            round((epoch / self._total_epochs) * 100, 1)
            if self._total_epochs > 0
            else 0.0
        )

        data = {
            "epoch": epoch,
            "total_epochs": self._total_epochs,
            "loss": round(loss, 4),
            "progress": progress,
            "metrics": metrics or {},
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        # 修复：保存任务引用防止 GC 提前回收，并添加异常处理
        broadcast_task = asyncio.create_task(
            self._manager.broadcast(self._task_id, "progress", data)
        )
        broadcast_task.add_done_callback(self._handle_broadcast_done)

    def _handle_broadcast_done(self, task: asyncio.Task) -> None:
        """记录广播任务完成状态"""
        if task.cancelled():
            logger.debug("Broadcast task cancelled for %s", self._task_id)
        elif task.exception():
            logger.error(
                "Broadcast task failed for %s: %s",
                self._task_id,
                task.exception(),
            )

    async def send_complete(
        self, status: str, final_loss: float, training_time: Optional[float] = None
    ):
        """Send training completion event."""
        if training_time is None:
            training_time = time.time() - self._start_time

        data = {
            "status": status,
            "final_loss": round(final_loss, 4),
            "training_time": int(training_time),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        await self._manager.broadcast(self._task_id, "complete", data)

    async def send_error(self, code: str, message: str, details: Optional[dict] = None):
        """Send training error event."""
        data = {
            "code": code,
            "message": message,
            "details": details or {},
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        await self._manager.broadcast(self._task_id, "error", data)


sse_manager = SSEConnectionManager()


def create_progress_callback(
    task_id: str, total_epochs: int
) -> TrainingProgressCallback:
    """Factory function to create a progress callback for a training task."""
    return TrainingProgressCallback(sse_manager, task_id, total_epochs)
