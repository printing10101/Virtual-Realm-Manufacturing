"""
Execution and Recovery Module

Implements standardized task execution flow with adapter pattern for LNN inference,
training, and analysis tasks. Features structured logging, cost tracking,
session persistence, and orphaned task recovery.
"""

import asyncio
import logging
import time
import json
import os
import sqlite3
import traceback
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional
from pathlib import Path

from app.core.budget import get_budget_manager
from app.core.cost_tracker import get_cost_tracker
from app.core.skill_loader import get_skill_loader
from app.core.workspace import get_resolver

logger = logging.getLogger(__name__)


class ExecutionStatus(str, Enum):
    """执行状态"""

    PENDING = "pending"
    PREPARING = "preparing"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    RECOVERING = "recovering"
    CANCELLED = "cancelled"


class TaskCategory(str, Enum):
    """任务类别"""

    INFERENCE = "inference"
    TRAINING = "training"
    ANALYSIS = "analysis"


@dataclass
class ExecutionResult:
    """执行结果"""

    task_id: str
    status: ExecutionStatus
    start_time: float
    end_time: float
    duration_ms: float
    result_data: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    error_traceback: Optional[str] = None
    resource_usage: Dict[str, Any] = field(default_factory=dict)
    cost_events: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "status": self.status.value,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration_ms": self.duration_ms,
            "result_data": self.result_data,
            "error_message": self.error_message,
            "error_traceback": self.error_traceback,
            "resource_usage": self.resource_usage,
            "cost_events": self.cost_events,
        }


@dataclass
class ExecutionSession:
    """执行会话"""

    session_id: str
    task_id: str
    status: ExecutionStatus
    checkpoint_data: Optional[Dict[str, Any]] = None
    started_at: Optional[float] = None
    last_updated: Optional[float] = None
    retry_count: int = 0
    max_retries: int = 3

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "task_id": self.task_id,
            "status": self.status.value,
            "checkpoint_data": self.checkpoint_data,
            "started_at": self.started_at,
            "last_updated": self.last_updated,
            "retry_count": self.retry_count,
            "max_retries": self.max_retries,
        }


class StructuredLogger:
    """结构化日志生成系统"""

    def __init__(self, log_dir: Optional[str] = None):
        """
        初始化结构化日志器

        Args:
            log_dir: 日志目录
        """
        if log_dir is None:
            from app.config import PROJECT_ROOT

            log_dir = str(Path(PROJECT_ROOT) / "logs" / "execution")

        self.log_dir = log_dir
        os.makedirs(log_dir, exist_ok=True)
        logger.info("StructuredLogger initialized at %s", log_dir)

    def log_execution_start(
        self, task_id: str, task_type: str, metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """记录执行开始"""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "event": "execution_start",
            "task_id": task_id,
            "task_type": task_type,
            "metadata": metadata or {},
        }
        self._write_log(task_id, entry)
        logger.info("[EXECUTION_START] task=%s type=%s", task_id, task_type)

    def log_execution_end(
        self,
        task_id: str,
        status: ExecutionStatus,
        duration_ms: float,
        result_summary: Optional[str] = None,
    ) -> None:
        """记录执行结束"""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "event": "execution_end",
            "task_id": task_id,
            "status": status.value,
            "duration_ms": duration_ms,
            "result_summary": result_summary,
        }
        self._write_log(task_id, entry)
        logger.info(
            "[EXECUTION_END] task=%s status=%s duration=%.2fms",
            task_id,
            status.value,
            duration_ms,
        )

    def log_resource_usage(self, task_id: str, resource_usage: Dict[str, Any]) -> None:
        """记录资源使用情况"""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "event": "resource_usage",
            "task_id": task_id,
            "resources": resource_usage,
        }
        self._write_log(task_id, entry)
        logger.debug("[RESOURCE_USAGE] task=%s %s", task_id, resource_usage)

    def log_error(
        self, task_id: str, error: Exception, traceback_str: Optional[str] = None
    ) -> None:
        """记录错误信息"""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "event": "error",
            "task_id": task_id,
            "error_type": type(error).__name__,
            "error_message": str(error),
            "traceback": traceback_str or traceback.format_exc(),
        }
        self._write_log(task_id, entry)
        logger.error(
            "[ERROR] task=%s type=%s msg=%s", task_id, type(error).__name__, error
        )

    def log_cost_event(self, task_id: str, cost_event: Dict[str, Any]) -> None:
        """记录成本事件"""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "event": "cost",
            "task_id": task_id,
            "cost": cost_event,
        }
        self._write_log(task_id, entry)

    def _write_log(self, task_id: str, entry: Dict[str, Any]) -> None:
        """写入日志条目"""
        log_file = os.path.join(self.log_dir, f"{task_id}.jsonl")

        try:
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception as e:
            logger.warning("Failed to write log entry: %s", e)

    def get_task_logs(self, task_id: str) -> List[Dict[str, Any]]:
        """获取任务日志"""
        log_file = os.path.join(self.log_dir, f"{task_id}.jsonl")

        if not os.path.exists(log_file):
            return []

        logs = []
        try:
            with open(log_file, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        logs.append(json.loads(line))
        except Exception as e:
            logger.warning("Failed to read task logs: %s", e)

        return logs


class SessionManager:
    """会话状态管理器"""

    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            from app.config import PROJECT_ROOT

            db_path = str(Path(PROJECT_ROOT) / "data" / "sessions.db")

        db_dir = Path(db_path).parent
        db_dir.mkdir(parents=True, exist_ok=True)

        self.db_path = db_path
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS execution_sessions (
                session_id TEXT PRIMARY KEY,
                task_id TEXT NOT NULL,
                status TEXT NOT NULL,
                checkpoint_data TEXT,
                started_at REAL,
                last_updated REAL,
                retry_count INTEGER DEFAULT 0,
                max_retries INTEGER DEFAULT 3,
                created_at REAL DEFAULT (strftime('%s', 'now'))
            );

            CREATE INDEX IF NOT EXISTS idx_session_task ON execution_sessions(task_id);
            CREATE INDEX IF NOT EXISTS idx_session_status ON execution_sessions(status);
        """)
        self._conn.commit()

    def create_session(self, session: ExecutionSession) -> None:
        """创建执行会话"""
        self._conn.execute(
            """INSERT OR REPLACE INTO execution_sessions
               (session_id, task_id, status, checkpoint_data, started_at,
                last_updated, retry_count, max_retries)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                session.session_id,
                session.task_id,
                session.status.value,
                json.dumps(session.checkpoint_data)
                if session.checkpoint_data
                else None,
                session.started_at,
                session.last_updated,
                session.retry_count,
                session.max_retries,
            ),
        )
        self._conn.commit()

    def update_session(
        self,
        session_id: str,
        status: ExecutionStatus,
        checkpoint_data: Optional[Dict[str, Any]] = None,
    ) -> None:
        """更新会话状态"""
        updates = {
            "status": status.value,
            "last_updated": time.time(),
        }

        if checkpoint_data is not None:
            updates["checkpoint_data"] = json.dumps(checkpoint_data)

        set_clause = ", ".join(f"{k} = ?" for k in updates.keys())
        values = list(updates.values()) + [session_id]

        self._conn.execute(
            f"UPDATE execution_sessions SET {set_clause} WHERE session_id = ?", values
        )
        self._conn.commit()

    def get_session(self, session_id: str) -> Optional[ExecutionSession]:
        """获取会话"""
        row = self._conn.execute(
            "SELECT * FROM execution_sessions WHERE session_id = ?", (session_id,)
        ).fetchone()

        if row is None:
            return None

        return ExecutionSession(
            session_id=row["session_id"],
            task_id=row["task_id"],
            status=ExecutionStatus(row["status"]),
            checkpoint_data=json.loads(row["checkpoint_data"])
            if row["checkpoint_data"]
            else None,
            started_at=row["started_at"],
            last_updated=row["last_updated"],
            retry_count=row["retry_count"],
            max_retries=row["max_retries"],
        )

    def get_sessions_by_task(self, task_id: str) -> List[ExecutionSession]:
        """获取任务的所有会话"""
        rows = self._conn.execute(
            "SELECT * FROM execution_sessions WHERE task_id = ? ORDER BY started_at DESC",
            (task_id,),
        ).fetchall()

        sessions = []
        for row in rows:
            sessions.append(
                ExecutionSession(
                    session_id=row["session_id"],
                    task_id=row["task_id"],
                    status=ExecutionStatus(row["status"]),
                    checkpoint_data=json.loads(row["checkpoint_data"])
                    if row["checkpoint_data"]
                    else None,
                    started_at=row["started_at"],
                    last_updated=row["last_updated"],
                    retry_count=row["retry_count"],
                    max_retries=row["max_retries"],
                )
            )

        return sessions

    def get_orphaned_sessions(
        self, timeout_seconds: float = 3600
    ) -> List[ExecutionSession]:
        """
        获取孤立会话（超时未更新的运行中会话）

        Args:
            timeout_seconds: 超时阈值（秒）

        Returns:
            孤立会话列表
        """
        cutoff = time.time() - timeout_seconds

        rows = self._conn.execute(
            """SELECT * FROM execution_sessions
               WHERE status IN ('running', 'preparing') AND last_updated < ?""",
            (cutoff,),
        ).fetchall()

        sessions = []
        for row in rows:
            sessions.append(
                ExecutionSession(
                    session_id=row["session_id"],
                    task_id=row["task_id"],
                    status=ExecutionStatus(row["status"]),
                    checkpoint_data=json.loads(row["checkpoint_data"])
                    if row["checkpoint_data"]
                    else None,
                    started_at=row["started_at"],
                    last_updated=row["last_updated"],
                    retry_count=row["retry_count"],
                    max_retries=row["max_retries"],
                )
            )

        if sessions:
            logger.warning("Found %d orphaned sessions", len(sessions))

        return sessions

    def close(self) -> None:
        if self._conn:
            self._conn.close()


class TaskExecutor:
    """任务执行器 - 适配器模式"""

    def __init__(self):
        self._executors: Dict[str, Callable] = {}
        self._register_default_executors()

    def _register_default_executors(self) -> None:
        """注册默认执行器"""
        self._executors["lnn_inference"] = self._execute_lnn_inference
        self._executors["lnn_training"] = self._execute_lnn_training
        self._executors["lnn_analysis"] = self._execute_lnn_analysis

    def register_executor(self, task_type: str, executor: Callable) -> None:
        """注册自定义执行器"""
        self._executors[task_type] = executor

    async def execute(
        self,
        task_type: str,
        workspace_context: Any,
        params: Optional[Dict[str, Any]] = None,
    ) -> ExecutionResult:
        """
        执行任务

        Args:
            task_type: 任务类型
            workspace_context: 工作空间上下文
            params: 任务参数

        Returns:
            执行结果
        """
        executor = self._executors.get(task_type)

        if executor is None:
            raise ValueError(f"No executor registered for task type: {task_type}")

        start_time = time.time()

        try:
            result = executor(workspace_context, params or {})

            duration_ms = (time.time() - start_time) * 1000

            return ExecutionResult(
                task_id=workspace_context.task_id,
                status=ExecutionStatus.COMPLETED,
                start_time=start_time,
                end_time=time.time(),
                duration_ms=duration_ms,
                result_data=result if isinstance(result, dict) else {"output": result},
            )
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000

            return ExecutionResult(
                task_id=workspace_context.task_id,
                status=ExecutionStatus.FAILED,
                start_time=start_time,
                end_time=time.time(),
                duration_ms=duration_ms,
                error_message=str(e),
                error_traceback=traceback.format_exc(),
            )

    def _execute_lnn_inference(
        self, workspace_context: Any, params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """执行LNN推理任务"""
        from app.ai.lnn.inference.predictor import LNNPredictor
        import numpy as np

        logger.info("Executing LNN inference for task %s", workspace_context.task_id)

        if workspace_context.model_path is None:
            raise RuntimeError("No model path available for inference")

        input_data = params.get("input_data")
        if input_data is None:
            raise ValueError("Missing input_data for inference")

        input_array = np.array(input_data)
        if input_array.ndim == 1:
            input_array = input_array.reshape(1, -1)

        predictor = LNNPredictor.from_registry(
            registry={},
            model_name=workspace_context.model_path,
        )

        result = predictor.predict(input_array, return_confidence=True)

        return {
            "prediction": result.value.tolist()
            if hasattr(result.value, "tolist")
            else result.value,
            "confidence": result.confidence,
            "inference_time": result.inference_time,
        }

    def _execute_lnn_training(
        self, workspace_context: Any, params: Dict[str, Any]
    ) -> Dict[str, Any]:
        from app.ai.lnn.training.trainer import LNNTrainer

        logger.info("Executing LNN training for task %s", workspace_context.task_id)

        if not workspace_context.dataset_path:
            raise RuntimeError(
                "LNN训练任务缺少数据集路径。请指定训练数据集的文件路径。"
            )

        trainer = LNNTrainer(
            model_name=workspace_context.model_name,
            dataset_path=workspace_context.dataset_path,
            output_dir=workspace_context.model_path,
        )
        trainer.train(params)

        return {
            "status": "training_completed",
            "model_path": workspace_context.model_path,
            "dataset_path": workspace_context.dataset_path,
            "metrics": trainer.get_metrics(),
        }

    def _execute_lnn_analysis(
        self, workspace_context: Any, params: Dict[str, Any]
    ) -> Dict[str, Any]:
        from app.ai.lnn.inference.predictor import LNNPredictor
        import numpy as np

        logger.info("Executing LNN analysis for task %s", workspace_context.task_id)

        input_data = params.get("input_data")
        if input_data is None:
            raise ValueError("分析任务缺少输入数据。请在params中提供input_data。")

        input_array = np.array(input_data)
        if input_array.ndim == 1:
            input_array = input_array.reshape(1, -1)

        predictor = LNNPredictor.from_registry(
            registry={},
            model_name=workspace_context.model_path or "default",
        )
        result = predictor.predict(input_array, return_confidence=True)

        return {
            "status": "analysis_completed",
            "workspace": workspace_context.workspace_dir,
            "prediction": result.value.tolist()
            if hasattr(result.value, "tolist")
            else result.value,
            "confidence": result.confidence,
        }


class ExecutionEngine:
    """
    执行引擎 - 整合所有模块

    实现原子性操作流程：
    任务检出 → 预算检查 → 环境准备 → 技能加载 → 任务执行 → 结果记录 → 资源释放
    """

    def __init__(self):

        self.structured_logger = StructuredLogger()
        self.session_manager = SessionManager()
        self.executor = TaskExecutor()

        self._retry_delays = [600, 1800, 3600]

    async def execute_task(self, task: Any) -> ExecutionResult:
        """
        执行任务的完整原子性流程

        Args:
            task: ScheduledTask实例

        Returns:
            执行结果
        """
        from app.core.heartbeat import get_scheduler, ScheduleStatus

        scheduler = get_scheduler()
        budget_manager = get_budget_manager()
        workspace_resolver = get_resolver()
        skill_loader = get_skill_loader()

        task_id = task.task_id
        agent_id = task.agent_id
        task_type = task.task_type

        session_id = f"{task_id}_{int(time.time())}"
        session = ExecutionSession(
            session_id=session_id,
            task_id=task_id,
            status=ExecutionStatus.PENDING,
            started_at=time.time(),
            last_updated=time.time(),
            retry_count=task.retry_count,
            max_retries=task.max_retries,
        )

        try:
            self.structured_logger.log_execution_start(task_id, task_type, task.params)
            self.session_manager.create_session(session)

            self.session_manager.update_session(session_id, ExecutionStatus.PREPARING)

            budget_result = budget_manager.check_budget(agent_id)

            if not budget_result.passed:
                error_msg = (
                    f"Budget check failed: {'; '.join(budget_result.blocked_reasons)}"
                )
                logger.error("[%s] %s", task_id, error_msg)

                self.structured_logger.log_error(task_id, RuntimeError(error_msg))
                self.session_manager.update_session(session_id, ExecutionStatus.FAILED)

                scheduler.wakeup_queue.update_task_status(
                    task_id, ScheduleStatus.FAILED
                )
                scheduler.wakeup_queue.log_execution(
                    task_id, "failed", error_message=error_msg
                )

                budget_manager.suspend_agent_tasks(agent_id, error_msg)

                return ExecutionResult(
                    task_id=task_id,
                    status=ExecutionStatus.FAILED,
                    start_time=time.time(),
                    end_time=time.time(),
                    duration_ms=0,
                    error_message=error_msg,
                )

            workspace = workspace_resolver.resolve(task_id, task_type, task.metadata)

            project_id = getattr(task, "project_id", None)
            skill_context = await skill_loader.inject_skills(
                task_type=task_type,
                project_id=project_id,
                agent_id=agent_id,
                available_context=set(workspace.to_dict().keys()),
            )
            if skill_context:
                task.params["_skill_context"] = skill_context
            skill_loader.inject_context(workspace.to_dict())

            self.session_manager.update_session(session_id, ExecutionStatus.RUNNING)

            result = await self.executor.execute(task_type, workspace, task.params)

            self._record_resource_usage(task_id, agent_id, result)

            self.structured_logger.log_execution_end(
                task_id, result.status, result.duration_ms
            )

            if result.status == ExecutionStatus.COMPLETED:
                scheduler.wakeup_queue.update_task_status(
                    task_id, ScheduleStatus.COMPLETED, last_run=time.time()
                )
                scheduler.wakeup_queue.log_execution(
                    task_id,
                    "completed",
                    duration_ms=result.duration_ms,
                    result_summary=json.dumps(result.result_data)[:500]
                    if result.result_data
                    else None,
                )
                self.session_manager.update_session(
                    session_id, ExecutionStatus.COMPLETED
                )
            else:
                await self._handle_failure(task, session, result)

            self._cleanup_resources(task_id)

            return result

        except Exception as e:
            logger.error("Task execution failed %s: %s", task_id, e, exc_info=True)

            self.structured_logger.log_error(task_id, e)
            self.session_manager.update_session(session_id, ExecutionStatus.FAILED)

            scheduler.wakeup_queue.update_task_status(task_id, ScheduleStatus.FAILED)
            scheduler.wakeup_queue.log_execution(
                task_id, "failed", error_message=str(e)
            )

            self._cleanup_resources(task_id)

            return ExecutionResult(
                task_id=task_id,
                status=ExecutionStatus.FAILED,
                start_time=time.time(),
                end_time=time.time(),
                duration_ms=0,
                error_message=str(e),
                error_traceback=traceback.format_exc(),
            )

    async def _handle_failure(
        self, task: Any, session: ExecutionSession, result: ExecutionResult
    ) -> None:
        """处理任务失败，实现重试机制"""
        from app.core.heartbeat import get_scheduler, ScheduleStatus

        scheduler = get_scheduler()

        if task.retry_count < task.max_retries:
            retry_delay = self._retry_delays[task.retry_count]

            logger.info(
                "Task %s failed, scheduling retry %d/%d in %d seconds",
                task.task_id,
                task.retry_count + 1,
                task.max_retries,
                retry_delay,
            )

            task.retry_count += 1
            task.next_run = time.time() + retry_delay
            task.status = ScheduleStatus.PENDING

            scheduler.wakeup_queue.add_task(task)
            scheduler.wakeup_queue.log_execution(
                task.task_id,
                "retry_scheduled",
                error_message=result.error_message,
                result_summary=f"Retry {task.retry_count}/{task.max_retries} in {retry_delay}s",
            )

            self.session_manager.update_session(
                session.session_id,
                ExecutionStatus.PENDING,
                checkpoint_data={
                    "retry_count": task.retry_count,
                    "next_run": task.next_run,
                },
            )
        else:
            logger.error(
                "Task %s failed after %d retries, marking as permanently failed",
                task.task_id,
                task.max_retries,
            )

            scheduler.wakeup_queue.update_task_status(
                task.task_id, ScheduleStatus.FAILED
            )
            scheduler.wakeup_queue.log_execution(
                task.task_id,
                "permanently_failed",
                error_message=result.error_message,
                result_summary=f"Failed after {task.max_retries} retries",
            )

            self.session_manager.update_session(
                session.session_id, ExecutionStatus.FAILED
            )

    def _record_resource_usage(
        self, task_id: str, agent_id: str, result: ExecutionResult
    ) -> None:
        """记录资源使用"""
        gpu_hours = result.duration_ms / (1000 * 3600) if result.duration_ms else 0

        if gpu_hours > 0:
            get_cost_tracker().record_gpu_usage(task_id, gpu_hours, agent_id)

        get_cost_tracker().record_memory_usage(
            task_id, result.resource_usage.get("memory_mb", 0), agent_id
        )

    def _cleanup_resources(self, task_id: str) -> None:
        """清理任务资源"""
        try:
            from app.core.workspace import get_resolver

            resolver = get_resolver()
            resolver.cleanup_workspace(task_id, keep_outputs=True)
            logger.info("Resources cleaned up for task %s", task_id)
        except Exception as e:
            logger.warning("Failed to cleanup resources for task %s: %s", task_id, e)

    async def recover_orphaned_tasks(self) -> int:
        """
        检测并恢复孤立任务

        Returns:
            恢复的任务数量
        """
        from app.core.heartbeat import get_scheduler, ScheduleStatus

        scheduler = get_scheduler()

        orphaned_sessions = self.session_manager.get_orphaned_sessions(
            timeout_seconds=3600
        )

        recovered_count = 0

        for session in orphaned_sessions:
            if session.retry_count < session.max_retries:
                task = scheduler.wakeup_queue.get_task(session.task_id)

                if task:
                    task.retry_count = session.retry_count
                    task.next_run = (
                        time.time() + self._retry_delays[session.retry_count]
                    )
                    task.status = ScheduleStatus.PENDING

                    scheduler.wakeup_queue.add_task(task)

                    self.session_manager.update_session(
                        session.session_id, ExecutionStatus.RECOVERING
                    )

                    recovered_count += 1

                    logger.info(
                        "Recovered orphaned task %s (session=%s)",
                        session.task_id,
                        session.session_id,
                    )

        if recovered_count > 0:
            logger.info("Recovered %d orphaned tasks", recovered_count)

        return recovered_count

    async def start_recovery_loop(
        self, check_interval: float = 60.0, max_interval: float = 600.0
    ) -> None:
        """启动孤立任务检测循环（含指数退避）

        Args:
            check_interval: 基础检测间隔（秒）
            max_interval: 最大检测间隔（秒）
        """
        backoff = check_interval
        while True:
            try:
                recovered = await self.recover_orphaned_tasks()
                if recovered > 0:
                    logger.info("Recovery loop: recovered %d tasks", recovered)
                    backoff = check_interval
                else:
                    backoff = min(backoff * 2, max_interval)
            except Exception as e:
                logger.error("Recovery loop error: %s", e)
                backoff = min(backoff * 2, max_interval)

            await asyncio.sleep(backoff)

    def close(self) -> None:
        """关闭所有资源"""
        self.session_manager.close()


_engine: Optional[ExecutionEngine] = None


def get_engine() -> ExecutionEngine:
    """获取全局执行引擎单例"""
    global _engine
    if _engine is None:
        _engine = ExecutionEngine()
    return _engine


def init_execution_engine() -> ExecutionEngine:
    """初始化全局执行引擎"""
    global _engine
    _engine = ExecutionEngine()
    return _engine
