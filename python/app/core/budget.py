"""
Budget Check Pre-execution Module

Implements resource budget verification before task execution, including GPU memory
availability, inference quota validation, and multi-dimensional resource tracking.
"""

import logging
import threading
import time
import sqlite3
import psutil
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from pathlib import Path

from app.models.budget import BudgetLevel, BudgetStatus, ResourceType

logger = logging.getLogger(__name__)


@dataclass
class BudgetLimit:
    """预算限制配置"""

    resource_type: ResourceType
    limit_value: float
    warning_threshold: float = 0.8
    hard_stop_threshold: float = 1.0
    budget_level: BudgetLevel = BudgetLevel.GLOBAL
    scope_id: str = "default"
    reset_interval: str = "daily"
    created_at: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "resource_type": self.resource_type.value,
            "limit_value": self.limit_value,
            "warning_threshold": self.warning_threshold,
            "hard_stop_threshold": self.hard_stop_threshold,
            "budget_level": self.budget_level.value,
            "scope_id": self.scope_id,
            "reset_interval": self.reset_interval,
        }


@dataclass
class BudgetUsage:
    """资源使用量"""

    resource_type: ResourceType
    current_usage: float
    limit: float
    usage_ratio: float
    status: BudgetStatus
    budget_level: BudgetLevel
    scope_id: str
    last_updated: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "resource_type": self.resource_type.value,
            "current_usage": self.current_usage,
            "limit": self.limit,
            "usage_ratio": self.usage_ratio,
            "status": self.status.value,
            "budget_level": self.budget_level.value,
            "scope_id": self.scope_id,
            "last_updated": self.last_updated,
        }


@dataclass
class BudgetCheckResult:
    """预算检查结果"""

    passed: bool
    status: BudgetStatus
    usages: List[BudgetUsage] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    blocked_reasons: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "passed": self.passed,
            "status": self.status.value,
            "usages": [u.to_dict() for u in self.usages],
            "warnings": self.warnings,
            "blocked_reasons": self.blocked_reasons,
        }


class ResourceTracker:
    """多维度资源追踪系统"""

    def __init__(self):
        self._gpu_memory_mb = 0.0
        self._gpu_hours_today = 0.0
        self._inference_count_today = 0
        self._memory_peak_mb = 0.0
        self._api_calls_today = 0
        self._last_reset = time.time()
        self._update_current_metrics()

    def _update_current_metrics(self) -> None:
        """更新当前资源使用指标"""
        try:
            process = psutil.Process()
            mem_info = process.memory_info()
            self._memory_peak_mb = max(
                self._memory_peak_mb, mem_info.rss / (1024 * 1024)
            )
        except Exception as e:
            logger.warning("Failed to update memory metrics: %s", e)

    def get_gpu_memory_available(self) -> float:
        """获取GPU显存可用量（MB）"""
        try:
            import torch

            if torch.cuda.is_available():
                total = torch.cuda.get_device_properties(0).total_memory / (1024**2)
                allocated = torch.cuda.memory_allocated(0) / (1024**2)
                return total - allocated
            return 0.0
        except ImportError:
            return 0.0

    def get_gpu_memory_total(self) -> float:
        """获取GPU显存总量（MB）"""
        try:
            import torch

            if torch.cuda.is_available():
                return torch.cuda.get_device_properties(0).total_memory / (1024**2)
            return 0.0
        except ImportError:
            return 0.0

    def increment_inference_count(self) -> None:
        """增加推理次数计数"""
        self._inference_count_today += 1

    def increment_gpu_hours(self, hours: float) -> None:
        """增加GPU使用小时数"""
        self._gpu_hours_today += hours

    def increment_api_calls(self) -> None:
        """增加API调用次数"""
        self._api_calls_today += 1

    def get_current_usage(self, resource_type: ResourceType) -> float:
        """获取当前资源使用量"""
        self._update_current_metrics()

        if resource_type == ResourceType.GPU_MEMORY:
            return self.get_gpu_memory_total() - self.get_gpu_memory_available()
        elif resource_type == ResourceType.GPU_HOURS:
            return self._gpu_hours_today
        elif resource_type == ResourceType.INFERENCE_COUNT:
            return self._inference_count_today
        elif resource_type == ResourceType.MEMORY_PEAK:
            return self._memory_peak_mb
        elif resource_type == ResourceType.API_CALLS:
            return self._api_calls_today
        else:
            raise ValueError(f"Unknown resource type: {resource_type}")

    def reset_daily(self) -> None:
        """重置每日计数"""
        now = time.time()
        elapsed = now - self._last_reset

        if elapsed >= 86400:
            self._inference_count_today = 0
            self._gpu_hours_today = 0.0
            self._api_calls_today = 0
            self._last_reset = now
            logger.info("Daily resource counters reset")


class BudgetManager:
    """预算管理器"""

    def __init__(self, db_path: Optional[str] = None):
        """
        初始化预算管理器

        Args:
            db_path: SQLite数据库路径
        """
        if db_path is None:
            db_path = str(Path(__file__).parent.parent.parent / "data" / "budget.db")

        db_dir = Path(db_path).parent
        db_dir.mkdir(parents=True, exist_ok=True)

        self.db_path = db_path
        self.tracker = ResourceTracker()
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._lock = threading.RLock()
        self._init_schema()
        self._load_default_budgets()

        logger.info("BudgetManager initialized at %s", db_path)

    def _init_schema(self) -> None:
        """初始化数据库模式"""
        with self._lock:
            self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS budget_limits (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                resource_type TEXT NOT NULL,
                limit_value REAL NOT NULL,
                warning_threshold REAL DEFAULT 0.8,
                hard_stop_threshold REAL DEFAULT 1.0,
                budget_level TEXT DEFAULT 'global',
                scope_id TEXT DEFAULT 'default',
                reset_interval TEXT DEFAULT 'daily',
                created_at REAL DEFAULT (strftime('%s', 'now')),
                UNIQUE(resource_type, budget_level, scope_id)
            );
            
            CREATE TABLE IF NOT EXISTS budget_usage_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                agent_id TEXT NOT NULL,
                resource_type TEXT NOT NULL,
                usage_value REAL NOT NULL,
                limit_value REAL NOT NULL,
                usage_ratio REAL NOT NULL,
                status TEXT NOT NULL,
                recorded_at REAL DEFAULT (strftime('%s', 'now'))
            );
            
            CREATE TABLE IF NOT EXISTS budget_notifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                agent_id TEXT NOT NULL,
                notification_type TEXT NOT NULL,
                message TEXT NOT NULL,
                resource_type TEXT,
                usage_ratio REAL,
                created_at REAL DEFAULT (strftime('%s', 'now'))
            );
        """)
            self._conn.commit()

    def _load_default_budgets(self) -> None:
        """加载默认预算配置"""
        defaults = [
            BudgetLimit(
                resource_type=ResourceType.INFERENCE_COUNT,
                limit_value=10000,
                budget_level=BudgetLevel.GLOBAL,
            ),
            BudgetLimit(
                resource_type=ResourceType.GPU_HOURS,
                limit_value=24.0,
                budget_level=BudgetLevel.GLOBAL,
            ),
            BudgetLimit(
                resource_type=ResourceType.MEMORY_PEAK,
                limit_value=16384,
                budget_level=BudgetLevel.GLOBAL,
            ),
            BudgetLimit(
                resource_type=ResourceType.API_CALLS,
                limit_value=50000,
                budget_level=BudgetLevel.GLOBAL,
            ),
        ]

        with self._lock:
            for budget in defaults:
                try:
                    self._conn.execute(
                        """INSERT OR IGNORE INTO budget_limits 
                           (resource_type, limit_value, warning_threshold, hard_stop_threshold, 
                            budget_level, scope_id, reset_interval)
                           VALUES (?, ?, ?, ?, ?, ?, ?)""",
                        (
                            budget.resource_type.value,
                            budget.limit_value,
                            budget.warning_threshold,
                            budget.hard_stop_threshold,
                            budget.budget_level.value,
                            budget.scope_id,
                            budget.reset_interval,
                        ),
                    )
                except Exception:
                    pass

            self._conn.commit()

    def set_budget_limit(self, budget: BudgetLimit) -> None:
        """设置预算限制"""
        with self._lock:
            self._conn.execute(
                """INSERT OR REPLACE INTO budget_limits 
                   (resource_type, limit_value, warning_threshold, hard_stop_threshold, 
                    budget_level, scope_id, reset_interval)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    budget.resource_type.value,
                    budget.limit_value,
                    budget.warning_threshold,
                    budget.hard_stop_threshold,
                    budget.budget_level.value,
                    budget.scope_id,
                    budget.reset_interval,
                ),
            )
            self._conn.commit()

        logger.info(
            "Budget limit set: %s for %s (level=%s, limit=%.2f)",
            budget.resource_type.value,
            budget.scope_id,
            budget.budget_level.value,
            budget.limit_value,
        )

    def check_budget(
        self, agent_id: str, resource_types: Optional[List[ResourceType]] = None
    ) -> BudgetCheckResult:
        """
        执行预算检查

        Args:
            agent_id: 代理ID
            resource_types: 要检查的资源类型列表（默认检查所有）

        Returns:
            预算检查结果
        """
        self.tracker.reset_daily()
        self.tracker._update_current_metrics()

        if resource_types is None:
            resource_types = list(ResourceType)

        usages = []
        warnings = []
        blocked_reasons = []
        overall_status = BudgetStatus.OK
        passed = True

        for res_type in resource_types:
            current_usage = self.tracker.get_current_usage(res_type)
            budget_limit = self._get_budget_limit(res_type, agent_id)

            if budget_limit is None:
                continue

            usage_ratio = (
                current_usage / budget_limit.limit_value
                if budget_limit.limit_value > 0
                else 0.0
            )

            if usage_ratio >= budget_limit.hard_stop_threshold:
                status = BudgetStatus.EXCEEDED
                passed = False
                blocked_reasons.append(
                    f"Resource {res_type.value} exceeded hard stop threshold: "
                    f"{current_usage:.2f}/{budget_limit.limit_value:.2f} ({usage_ratio * 100:.1f}%)"
                )
                overall_status = BudgetStatus.EXCEEDED

                self._record_notification(
                    agent_id,
                    "hard_stop",
                    blocked_reasons[-1],
                    res_type.value,
                    usage_ratio,
                )
            elif usage_ratio >= budget_limit.warning_threshold:
                status = BudgetStatus.WARNING
                warnings.append(
                    f"Resource {res_type.value} approaching limit: "
                    f"{current_usage:.2f}/{budget_limit.limit_value:.2f} ({usage_ratio * 100:.1f}%)"
                )
                if overall_status == BudgetStatus.OK:
                    overall_status = BudgetStatus.WARNING

                self._record_notification(
                    agent_id, "warning", warnings[-1], res_type.value, usage_ratio
                )
            else:
                status = BudgetStatus.OK

            usage = BudgetUsage(
                resource_type=res_type,
                current_usage=current_usage,
                limit=budget_limit.limit_value,
                usage_ratio=usage_ratio,
                status=status,
                budget_level=budget_limit.budget_level,
                scope_id=budget_limit.scope_id,
                last_updated=time.time(),
            )
            usages.append(usage)

            self._log_usage(
                agent_id,
                res_type,
                current_usage,
                budget_limit.limit_value,
                usage_ratio,
                status,
            )

        if warnings:
            logger.warning(
                "Budget warnings for agent %s: %s", agent_id, "; ".join(warnings)
            )

        if blocked_reasons:
            logger.error(
                "Budget exceeded for agent %s: %s", agent_id, "; ".join(blocked_reasons)
            )

        return BudgetCheckResult(
            passed=passed,
            status=overall_status,
            usages=usages,
            warnings=warnings,
            blocked_reasons=blocked_reasons,
        )

    def _get_budget_limit(
        self, resource_type: ResourceType, agent_id: str
    ) -> Optional[BudgetLimit]:
        """获取预算限制（按代理级、项目级、全局级优先级）"""
        with self._lock:
            for level, scope in [
                (BudgetLevel.AGENT.value, agent_id),
                (BudgetLevel.PROJECT.value, "default"),
                (BudgetLevel.GLOBAL.value, "default"),
            ]:
                row = self._conn.execute(
                    """SELECT * FROM budget_limits 
                       WHERE resource_type = ? AND budget_level = ? AND scope_id = ?""",
                    (resource_type.value, level, scope),
                ).fetchone()

                if row:
                    return BudgetLimit(
                        resource_type=resource_type,
                        limit_value=row["limit_value"],
                        warning_threshold=row["warning_threshold"],
                        hard_stop_threshold=row["hard_stop_threshold"],
                        budget_level=BudgetLevel(row["budget_level"]),
                        scope_id=row["scope_id"],
                        reset_interval=row["reset_interval"],
                    )

            return None

    def _log_usage(
        self,
        agent_id: str,
        resource_type: ResourceType,
        usage: float,
        limit: float,
        ratio: float,
        status: BudgetStatus,
    ) -> None:
        """记录使用量日志"""
        try:
            with self._lock:
                self._conn.execute(
                    """INSERT INTO budget_usage_log 
                       (agent_id, resource_type, usage_value, limit_value, usage_ratio, status)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (agent_id, resource_type.value, usage, limit, ratio, status.value),
                )
                self._conn.commit()
        except Exception as e:
            logger.warning("Failed to log budget usage: %s", e)

    def _record_notification(
        self,
        agent_id: str,
        notification_type: str,
        message: str,
        resource_type: Optional[str] = None,
        usage_ratio: Optional[float] = None,
    ) -> None:
        """记录预算通知"""
        try:
            with self._lock:
                self._conn.execute(
                    """INSERT INTO budget_notifications 
                       (agent_id, notification_type, message, resource_type, usage_ratio)
                       VALUES (?, ?, ?, ?, ?)""",
                    (agent_id, notification_type, message, resource_type, usage_ratio),
                )
                self._conn.commit()
        except Exception as e:
            logger.warning("Failed to record budget notification: %s", e)

    def get_agent_budget_status(self, agent_id: str) -> Dict[str, Any]:
        """获取代理预算状态概览"""
        result = self.check_budget(agent_id)
        return result.to_dict()

    def suspend_agent_tasks(self, agent_id: str, reason: str) -> None:
        """
        暂停代理的所有任务（当预算超出时调用）

        Args:
            agent_id: 代理ID
            reason: 暂停原因
        """
        from app.core.heartbeat import get_scheduler

        try:
            scheduler = get_scheduler()
            tasks = scheduler.wakeup_queue.list_tasks(agent_id=agent_id)

            for task in tasks:
                if task.status.value not in ("completed", "failed"):
                    scheduler.pause_task(task.task_id)
                    logger.info(
                        "Task %s paused for agent %s: budget exceeded",
                        task.task_id,
                        agent_id,
                    )

            self._record_notification(agent_id, "suspended", reason)
        except Exception as e:
            logger.error("Failed to suspend agent tasks: %s", e)

    def get_notifications(
        self, agent_id: Optional[str] = None, limit: int = 50
    ) -> List[Dict[str, Any]]:
        """获取预算通知列表"""
        with self._lock:
            if agent_id:
                rows = self._conn.execute(
                    """SELECT * FROM budget_notifications 
                       WHERE agent_id = ? ORDER BY created_at DESC LIMIT ?""",
                    (agent_id, limit),
                ).fetchall()
            else:
                rows = self._conn.execute(
                    """SELECT * FROM budget_notifications 
                       ORDER BY created_at DESC LIMIT ?""",
                    (limit,),
                ).fetchall()

        return [dict(row) for row in rows]

    def close(self) -> None:
        """关闭数据库连接"""
        if self._conn:
            self._conn.close()
            self._conn = None

    def __del__(self) -> None:
        try:
            self.close()
        except Exception:
            pass


_budget_manager: Optional[BudgetManager] = None


def get_budget_manager() -> BudgetManager:
    """获取全局预算管理器单例"""
    global _budget_manager
    if _budget_manager is None:
        _budget_manager = BudgetManager()
    return _budget_manager


def init_budget_manager(db_path: Optional[str] = None) -> BudgetManager:
    """初始化全局预算管理器"""
    global _budget_manager
    _budget_manager = BudgetManager(db_path)
    return _budget_manager
