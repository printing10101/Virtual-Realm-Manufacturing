"""预算强制执行器.

从原 ``app/budget/budget_enforcer.py`` 拆分而来，聚焦于预算执行职责：
预执行原子检查、级联预算状态处理、周期性自动重置、告警生成与执行日志。

向后兼容：``app/budget/budget_enforcer.py`` 仍作为 re-export shim 暴露
本模块的全部公开符号。
"""
import json
import logging
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any, Callable, ClassVar, Dict, List, Optional

from app.budget.models import EnforcementAction, EnforcementResult
from app.models.budget import (
    BudgetAlert,
    BudgetCheckResult,
    BudgetLevel,
    BudgetPeriod,
    BudgetPolicy,
    BudgetStatus,
    DEFAULT_GLOBAL_BUDGETS,
    ResourceType,
)
from app.services._shared.service_base import BaseSingletonService
from app.utils.sqlite_pool import get_sqlite_manager
from app.utils.utils import get_output_dir

logger = logging.getLogger(__name__)


class BudgetEnforcer(BaseSingletonService):
    """预算强制执行器.

    单例管理由 ``BaseSingletonService`` 提供（``get_instance`` / ``reset_instance``）。
    需要「强制重新创建并指定 db_path」时使用 :meth:`init` 类方法。
    """

    # 类变量：``init(db_path)`` 写入此变量，``__init__`` 在无显式参数时读取它。
    # 这样既兼容 ``BaseSingletonService.get_instance()`` 的无参构造，又保留了
    # 原 ``init_budget_enforcer(db_path)`` 接口的「指定路径」能力。
    _db_path: ClassVar[Optional[str]] = None

    def __init__(self, db_path: Optional[str] = None):
        # 优先使用显式传入的 db_path，其次回退到类变量（由 init() 设置），
        # 最后回退到默认路径。保持与重构前 holder 行为一致。
        if db_path is not None:
            actual_path = db_path
        elif type(self)._db_path is not None:
            actual_path = type(self)._db_path
        else:
            actual_path = str(get_output_dir("data") / "budget_enforcer.db")

        db_dir = Path(actual_path).parent
        db_dir.mkdir(parents=True, exist_ok=True)

        self.db_path = actual_path
        # 使用统一的连接池管理器（传入 db_path 避免跨测试共享连接池死锁）
        self._manager = get_sqlite_manager()
        self._pool = self._manager.get_pool("budget_enforcer", db_path=self.db_path)
        self._conn = self._pool.get_connection()
        self._policies: Dict[str, BudgetPolicy] = {}
        self._alert_callbacks: List[Callable[[BudgetAlert], None]] = []
        self._task_canceller: Optional[Callable[[str], None]] = None
        self._agent_suspender: Optional[Callable[[str, str], None]] = None
        self._init_schema()
        self._load_policies()
        self._load_default_policies()

        logger.info("BudgetEnforcer initialized at %s", self.db_path)

    def close(self) -> None:
        """关闭执行器，归还连接到连接池"""
        if hasattr(self, "_conn") and self._conn:
            self._pool.return_connection(self._conn)
            self._conn = None
            logger.info("BudgetEnforcer closed")

    def _init_schema(self) -> None:
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS budget_policies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                level TEXT NOT NULL,
                scope_id TEXT NOT NULL DEFAULT 'default',
                resource_type TEXT NOT NULL,
                limit_value REAL NOT NULL DEFAULT 100.0,
                period TEXT NOT NULL DEFAULT 'daily',
                warning_threshold REAL NOT NULL DEFAULT 0.8,
                hard_stop INTEGER NOT NULL DEFAULT 1,
                auto_notify INTEGER NOT NULL DEFAULT 1,
                enabled INTEGER NOT NULL DEFAULT 1,
                current_usage REAL NOT NULL DEFAULT 0.0,
                last_reset_at REAL,
                created_at REAL,
                updated_at REAL,
                UNIQUE(level, scope_id, resource_type)
            );

            CREATE INDEX IF NOT EXISTS idx_policy_level ON budget_policies(level);
            CREATE INDEX IF NOT EXISTS idx_policy_scope ON budget_policies(scope_id);

            CREATE TABLE IF NOT EXISTS budget_alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                level TEXT NOT NULL,
                scope_id TEXT NOT NULL DEFAULT 'default',
                resource_type TEXT NOT NULL,
                status TEXT NOT NULL,
                current_usage REAL NOT NULL DEFAULT 0.0,
                limit_value REAL NOT NULL DEFAULT 0.0,
                usage_ratio REAL NOT NULL DEFAULT 0.0,
                message TEXT DEFAULT '',
                is_read INTEGER NOT NULL DEFAULT 0,
                created_at REAL
            );

            CREATE INDEX IF NOT EXISTS idx_alert_created ON budget_alerts(created_at);
            CREATE INDEX IF NOT EXISTS idx_alert_status ON budget_alerts(status);
            CREATE INDEX IF NOT EXISTS idx_alert_read ON budget_alerts(is_read);

            CREATE TABLE IF NOT EXISTS budget_reset_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                level TEXT NOT NULL,
                scope_id TEXT NOT NULL DEFAULT 'default',
                resource_type TEXT NOT NULL,
                period TEXT NOT NULL,
                usage_before_reset REAL NOT NULL DEFAULT 0.0,
                limit_at_reset REAL NOT NULL DEFAULT 0.0,
                reset_at REAL
            );

            CREATE TABLE IF NOT EXISTS enforcement_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                action TEXT NOT NULL,
                level TEXT NOT NULL,
                scope_id TEXT NOT NULL DEFAULT 'default',
                resource_type TEXT NOT NULL,
                details TEXT DEFAULT '{}',
                executed_at REAL
            );
        """)
        self._conn.commit()

    def _load_policies(self) -> None:
        rows = self._conn.execute(
            "SELECT * FROM budget_policies ORDER BY level, scope_id"
        ).fetchall()

        for row in rows:
            key = self._policy_key(row["level"], row["scope_id"], row["resource_type"])
            self._policies[key] = BudgetPolicy(
                level=BudgetLevel(row["level"]),
                scope_id=row["scope_id"],
                resource_type=ResourceType(row["resource_type"]),
                limit=row["limit_value"],
                period=BudgetPeriod(row["period"]),
                warning_threshold=row["warning_threshold"],
                hard_stop=bool(row["hard_stop"]),
                auto_notify=bool(row["auto_notify"]),
                enabled=bool(row["enabled"]),
                current_usage=row["current_usage"],
                last_reset_at=row["last_reset_at"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )

        logger.info("Loaded %d budget policies", len(self._policies))

    def _load_default_policies(self) -> None:
        for policy in DEFAULT_GLOBAL_BUDGETS:
            key = self._policy_key(
                policy.level.value, policy.scope_id, policy.resource_type.value
            )
            if key not in self._policies:
                self.set_policy(policy)

    @staticmethod
    def _policy_key(level: str, scope_id: str, resource_type: str) -> str:
        return f"{level}:{scope_id}:{resource_type}"

    def set_policy(self, policy: BudgetPolicy) -> None:
        now = time.time()
        if policy.created_at is None:
            policy.created_at = now
        policy.updated_at = now

        key = self._policy_key(
            policy.level.value, policy.scope_id, policy.resource_type.value
        )

        self._conn.execute(
            """INSERT OR REPLACE INTO budget_policies
               (level, scope_id, resource_type, limit_value, period,
                warning_threshold, hard_stop, auto_notify, enabled,
                current_usage, last_reset_at, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                policy.level.value,
                policy.scope_id,
                policy.resource_type.value,
                policy.limit,
                policy.period.value,
                policy.warning_threshold,
                int(policy.hard_stop),
                int(policy.auto_notify),
                int(policy.enabled),
                policy.current_usage,
                policy.last_reset_at,
                policy.created_at,
                policy.updated_at,
            ),
        )
        self._conn.commit()
        self._policies[key] = policy
        logger.info(
            "Budget policy set: %s limit=%.2f period=%s",
            key,
            policy.limit,
            policy.period.value,
        )

    def get_policy(
        self, level: BudgetLevel, scope_id: str, resource_type: ResourceType
    ) -> Optional[BudgetPolicy]:
        key = self._policy_key(level.value, scope_id, resource_type.value)
        return self._policies.get(key)

    def get_all_policies(
        self, level: Optional[BudgetLevel] = None, scope_id: Optional[str] = None
    ) -> List[BudgetPolicy]:
        result = []
        for policy in self._policies.values():
            if level and policy.level != level:
                continue
            if scope_id and policy.scope_id != scope_id:
                continue
            result.append(policy)
        return sorted(result, key=lambda p: (p.level.value, p.scope_id))

    def adjust_budget(
        self,
        level: BudgetLevel,
        scope_id: str,
        resource_type: ResourceType,
        new_limit: float,
        reason: str = "",
        adjusted_by: str = "admin",
    ) -> Optional[BudgetPolicy]:
        key = self._policy_key(level.value, scope_id, resource_type.value)
        old_policy = self._policies.get(key)

        old_limit = old_policy.limit if old_policy else 0.0

        if old_policy:
            old_policy.limit = new_limit
            old_policy._adjustment_reason = reason
            self.set_policy(old_policy)
        else:
            new_policy = BudgetPolicy(
                level=level,
                scope_id=scope_id,
                resource_type=resource_type,
                limit=new_limit,
            )
            self.set_policy(new_policy)

        if hasattr(self, "_cost_tracker_ref") and self._cost_tracker_ref:
            self._cost_tracker_ref.record_budget_adjustment(
                budget_level=level.value,
                scope_id=scope_id,
                resource_type=resource_type.value,
                old_limit=old_limit,
                new_limit=new_limit,
                reason=reason,
                adjusted_by=adjusted_by,
            )

        logger.info(
            "Budget adjusted: %s/%s/%s %.2f → %.2f by %s",
            level.value,
            scope_id,
            resource_type.value,
            old_limit,
            new_limit,
            adjusted_by,
        )
        return self._policies.get(key)

    def check_budget(
        self,
        level: BudgetLevel,
        scope_id: str,
        resource_type: ResourceType,
        planned_usage: float = 0.0,
    ) -> BudgetCheckResult:
        policy = self.get_policy(level, scope_id, resource_type)

        if policy is None:
            return BudgetCheckResult(
                passed=True,
                status=BudgetStatus.OK,
                usage_ratio=0.0,
                remaining=float("inf"),
                limit=0.0,
                checked_at=time.time(),
            )

        self._check_and_reset_period(policy)

        projected_usage = policy.current_usage + planned_usage
        projected_ratio = projected_usage / policy.limit if policy.limit > 0 else 0.0

        result = BudgetCheckResult(
            policy=policy,
            usage_ratio=projected_ratio,
            remaining=max(policy.limit - projected_usage, 0),
            limit=policy.limit,
            checked_at=time.time(),
        )

        if not policy.enabled:
            result.status = BudgetStatus.DISABLED
            result.passed = False
            result.block_reason = (
                f"Budget policy disabled: {scope_id}/{resource_type.value}"
            )
        elif projected_ratio >= 1.0:
            result.status = BudgetStatus.EXCEEDED
            if policy.hard_stop:
                result.passed = False
                result.block_reason = (
                    f"Budget EXCEEDED: {scope_id}/{resource_type.value} "
                    f"({projected_usage:.2f}/{policy.limit:.2f}, "
                    f"{projected_ratio:.1%})"
                )
            else:
                result.passed = True
                result.warnings.append(
                    f"Budget exceeded but hard_stop is disabled: "
                    f"{projected_usage:.2f}/{policy.limit:.2f}"
                )
        elif projected_ratio >= policy.warning_threshold:
            result.status = BudgetStatus.WARNING
            result.passed = True
            result.warnings.append(
                f"Budget WARNING: {scope_id}/{resource_type.value} "
                f"({projected_usage:.2f}/{policy.limit:.2f}, "
                f"{projected_ratio:.1%})"
            )
        else:
            result.status = BudgetStatus.OK
            result.passed = True

        return result

    def check_budget_cascade(
        self,
        agent_id: str,
        project_id: str = "default",
        resource_type: ResourceType = ResourceType.TOTAL_COST,
        planned_usage: float = 0.0,
    ) -> BudgetCheckResult:
        """级联预算检查：任务级 → 代理级 → 项目级 → 全局级"""
        cascade = [
            (BudgetLevel.TASK, agent_id),
            (BudgetLevel.AGENT, agent_id),
            (BudgetLevel.PROJECT, project_id),
            (BudgetLevel.GLOBAL, "default"),
        ]

        for level, scope_id in cascade:
            policy = self.get_policy(level, scope_id, resource_type)
            if policy is None:
                continue

            result = self.check_budget(level, scope_id, resource_type, planned_usage)
            if not result.passed:
                return result
            if result.warnings:
                return result

        return BudgetCheckResult(
            passed=True,
            status=BudgetStatus.OK,
            usage_ratio=0.0,
            remaining=float("inf"),
            limit=0.0,
            checked_at=time.time(),
        )

    def record_usage(
        self,
        level: BudgetLevel,
        scope_id: str,
        resource_type: ResourceType,
        usage: float,
    ) -> None:
        """记录资源用量并更新策略"""
        key = self._policy_key(level.value, scope_id, resource_type.value)
        policy = self._policies.get(key)

        if policy is None:
            return

        policy.current_usage += usage

        self._conn.execute(
            """UPDATE budget_policies SET current_usage = ?, updated_at = ?
               WHERE level = ? AND scope_id = ? AND resource_type = ?""",
            (
                policy.current_usage,
                time.time(),
                level.value,
                scope_id,
                resource_type.value,
            ),
        )
        self._conn.commit()

    def enforce(
        self,
        level: BudgetLevel,
        scope_id: str,
        resource_type: ResourceType,
        planned_usage: float = 0.0,
    ) -> EnforcementResult:
        """执行预算强制执行"""
        result = EnforcementResult()
        check = self.check_budget(level, scope_id, resource_type, planned_usage)
        result.check_result = check

        if check.status == BudgetStatus.DISABLED:
            result.actions_taken.append(EnforcementAction.BLOCK)
            return result

        if check.passed:
            result.actions_taken.append(EnforcementAction.ALLOW)
            if check.status == BudgetStatus.WARNING:
                result.actions_taken.append(EnforcementAction.WARN)

                alert = self._create_alert(
                    level, scope_id, resource_type, check, "warning"
                )
                result.alerts_generated.append(alert)
            return result

        result.actions_taken.append(EnforcementAction.BLOCK)

        alert = self._create_alert(level, scope_id, resource_type, check, "exceeded")
        result.alerts_generated.append(alert)

        policy = check.policy
        if policy and policy.hard_stop:
            result.actions_taken.append(EnforcementAction.CANCEL_PENDING)

            if self._task_canceller and policy:
                cancelled = self._cancel_pending_tasks(level, scope_id, resource_type)
                result.cancelled_tasks = cancelled

            if level == BudgetLevel.AGENT:
                result.actions_taken.append(EnforcementAction.SUSPEND_AGENT)
                result.suspended_agents.append(scope_id)

                if self._agent_suspender:
                    self._agent_suspender(
                        scope_id,
                        f"Budget exceeded: {resource_type.value} "
                        f"({check.usage_ratio:.1%})",
                    )

        if policy and policy.auto_notify:
            result.actions_taken.append(EnforcementAction.NOTIFY_ADMIN)
            result.notifications_sent = True

        self._log_enforcement(result, level, scope_id, resource_type)

        return result

    def enforce_cascade(
        self,
        agent_id: str,
        project_id: str = "default",
        resource_type: ResourceType = ResourceType.TOTAL_COST,
        planned_usage: float = 0.0,
    ) -> EnforcementResult:
        """级联预算强制执行"""
        cascade = [
            (BudgetLevel.TASK, agent_id),
            (BudgetLevel.AGENT, agent_id),
            (BudgetLevel.PROJECT, project_id),
            (BudgetLevel.GLOBAL, "default"),
        ]

        for level, scope_id in cascade:
            policy = self.get_policy(level, scope_id, resource_type)
            if policy is None:
                continue

            result = self.enforce(level, scope_id, resource_type, planned_usage)
            if EnforcementAction.BLOCK in result.actions_taken:
                return result

        return EnforcementResult(
            actions_taken=[EnforcementAction.ALLOW],
            check_result=BudgetCheckResult(
                passed=True, status=BudgetStatus.OK, checked_at=time.time()
            ),
        )

    def reset_period(
        self, level: BudgetLevel, scope_id: str, resource_type: ResourceType
    ) -> None:
        """手动重置预算周期"""
        policy = self.get_policy(level, scope_id, resource_type)
        if policy is None:
            return

        old_usage = policy.current_usage

        self._conn.execute(
            """INSERT INTO budget_reset_log
               (level, scope_id, resource_type, period, usage_before_reset,
                limit_at_reset, reset_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                level.value,
                scope_id,
                resource_type.value,
                policy.period.value,
                old_usage,
                policy.limit,
                time.time(),
            ),
        )

        policy.current_usage = 0.0
        policy.last_reset_at = time.time()

        self._conn.execute(
            """UPDATE budget_policies
               SET current_usage = 0.0, last_reset_at = ?, updated_at = ?
               WHERE level = ? AND scope_id = ? AND resource_type = ?""",
            (
                policy.last_reset_at,
                time.time(),
                level.value,
                scope_id,
                resource_type.value,
            ),
        )
        self._conn.commit()

        logger.info(
            "Budget reset: %s/%s/%s, previous usage: %.2f",
            level.value,
            scope_id,
            resource_type.value,
            old_usage,
        )

    def auto_reset_periods(self) -> int:
        """自动检查并重置所有到期周期，返回重置数量"""
        now = time.time()
        reset_count = 0

        for key, policy in list(self._policies.items()):
            if self._should_reset(policy, now):
                old_usage = policy.current_usage
                policy.current_usage = 0.0
                policy.last_reset_at = now

                self._conn.execute(
                    """UPDATE budget_policies
                       SET current_usage = 0.0, last_reset_at = ?, updated_at = ?
                       WHERE level = ? AND scope_id = ? AND resource_type = ?""",
                    (
                        now,
                        now,
                        policy.level.value,
                        policy.scope_id,
                        policy.resource_type.value,
                    ),
                )

                self._conn.execute(
                    """INSERT INTO budget_reset_log
                       (level, scope_id, resource_type, period,
                        usage_before_reset, limit_at_reset, reset_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (
                        policy.level.value,
                        policy.scope_id,
                        policy.resource_type.value,
                        policy.period.value,
                        old_usage,
                        policy.limit,
                        now,
                    ),
                )
                reset_count += 1

        if reset_count > 0:
            self._conn.commit()
            logger.info("Auto-reset %d budget periods", reset_count)

        return reset_count

    def _should_reset(self, policy: BudgetPolicy, now: float) -> bool:
        if policy.last_reset_at is None:
            return False

        import datetime

        last_dt = datetime.datetime.fromtimestamp(policy.last_reset_at)
        now_dt = datetime.datetime.fromtimestamp(now)

        if policy.period == BudgetPeriod.DAILY:
            return last_dt.date() < now_dt.date()
        elif policy.period == BudgetPeriod.WEEKLY:
            last_monday = last_dt - datetime.timedelta(days=last_dt.weekday())
            now_monday = now_dt - datetime.timedelta(days=now_dt.weekday())
            return last_monday.date() < now_monday.date()
        elif policy.period == BudgetPeriod.MONTHLY:
            return (last_dt.year, last_dt.month) < (now_dt.year, now_dt.month)

        return False

    def _check_and_reset_period(self, policy: BudgetPolicy) -> None:
        now = time.time()
        if policy.last_reset_at is None:
            policy.last_reset_at = now
            self._conn.execute(
                """UPDATE budget_policies SET last_reset_at = ?
                   WHERE level = ? AND scope_id = ? AND resource_type = ?""",
                (now, policy.level.value, policy.scope_id, policy.resource_type.value),
            )
            self._conn.commit()
            return

        if self._should_reset(policy, now):
            old_usage = policy.current_usage
            policy.current_usage = 0.0
            policy.last_reset_at = now

            self._conn.execute(
                """UPDATE budget_policies
                   SET current_usage = 0.0, last_reset_at = ?, updated_at = ?
                   WHERE level = ? AND scope_id = ? AND resource_type = ?""",
                (
                    now,
                    now,
                    policy.level.value,
                    policy.scope_id,
                    policy.resource_type.value,
                ),
            )
            self._conn.execute(
                """INSERT INTO budget_reset_log
                   (level, scope_id, resource_type, period,
                    usage_before_reset, limit_at_reset, reset_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    policy.level.value,
                    policy.scope_id,
                    policy.resource_type.value,
                    policy.period.value,
                    old_usage,
                    policy.limit,
                    now,
                ),
            )
            self._conn.commit()
            logger.info(
                "Period reset triggered: %s/%s/%s, previous: %.2f",
                policy.level.value,
                policy.scope_id,
                policy.resource_type.value,
                old_usage,
            )

    def _create_alert(
        self,
        level: BudgetLevel,
        scope_id: str,
        resource_type: ResourceType,
        check: BudgetCheckResult,
        alert_type: str,
    ) -> BudgetAlert:
        now = time.time()
        message = (
            f"[{alert_type.upper()}] {level.value}:{scope_id} "
            f"{resource_type.value}: {check.usage_ratio:.1%} used "
            f"(limit: {check.limit:.2f})"
        )

        alert = BudgetAlert(
            level=level,
            scope_id=scope_id,
            resource_type=resource_type,
            status=BudgetStatus.WARNING
            if alert_type == "warning"
            else BudgetStatus.EXCEEDED,
            current_usage=check.limit * check.usage_ratio,
            limit=check.limit,
            usage_ratio=check.usage_ratio,
            message=message,
            created_at=now,
        )

        self._conn.execute(
            """INSERT INTO budget_alerts
               (level, scope_id, resource_type, status, current_usage,
                limit_value, usage_ratio, message, is_read, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, ?)""",
            (
                level.value,
                scope_id,
                resource_type.value,
                alert.status.value,
                alert.current_usage,
                alert.limit,
                alert.usage_ratio,
                alert.message,
                now,
            ),
        )
        self._conn.commit()

        for callback in self._alert_callbacks:
            try:
                callback(alert)
            except (RuntimeError, ValueError, TypeError, AttributeError) as e:
                logger.error("Alert callback error", exc_info=True)

        return alert

    def get_alerts(
        self,
        status: Optional[str] = None,
        unread_only: bool = False,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        conditions = []
        params = []

        if status:
            conditions.append("status = ?")
            params.append(status)
        if unread_only:
            conditions.append("is_read = 0")

        where = " AND ".join(conditions) if conditions else "1=1"

        rows = self._conn.execute(
            f"""SELECT * FROM budget_alerts
                WHERE {where}
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?""",
            params + [limit, offset],
        ).fetchall()

        return [dict(row) for row in rows]

    def mark_alert_read(self, alert_id: int) -> None:
        self._conn.execute(
            "UPDATE budget_alerts SET is_read = 1 WHERE id = ?", (alert_id,)
        )
        self._conn.commit()

    def mark_all_alerts_read(self) -> None:
        self._conn.execute("UPDATE budget_alerts SET is_read = 1 WHERE is_read = 0")
        self._conn.commit()

    def delete_alert(self, alert_id: int) -> None:
        self._conn.execute("DELETE FROM budget_alerts WHERE id = ?", (alert_id,))
        self._conn.commit()

    def register_alert_callback(self, callback: Callable[[BudgetAlert], None]) -> None:
        self._alert_callbacks.append(callback)

    def set_task_canceller(self, canceller: Callable[[str], None]) -> None:
        self._task_canceller = canceller

    def set_agent_suspender(self, suspender: Callable[[str, str], None]) -> None:
        self._agent_suspender = suspender

    def set_cost_tracker(self, cost_tracker) -> None:
        self._cost_tracker_ref = cost_tracker

    def _cancel_pending_tasks(
        self, level: BudgetLevel, scope_id: str, resource_type: ResourceType
    ) -> List[str]:
        cancelled = []
        if self._task_canceller:
            try:
                if level == BudgetLevel.AGENT:
                    self._task_canceller(scope_id)
                    cancelled.append(scope_id)
                elif level == BudgetLevel.GLOBAL:
                    self._task_canceller("global")
                    cancelled.append("global")
            except (RuntimeError, ValueError, OSError) as e:
                logger.error("Task cancellation error", exc_info=True)
        return cancelled

    def _log_enforcement(
        self,
        result: EnforcementResult,
        level: BudgetLevel,
        scope_id: str,
        resource_type: ResourceType,
    ) -> None:
        details = json.dumps(
            {
                "actions": [a.value for a in result.actions_taken],
                "cancelled_tasks": result.cancelled_tasks,
                "suspended_agents": result.suspended_agents,
                "notifications_sent": result.notifications_sent,
            }
        )
        self._conn.execute(
            """INSERT INTO enforcement_log
               (action, level, scope_id, resource_type, details, executed_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                ",".join(a.value for a in result.actions_taken),
                level.value,
                scope_id,
                resource_type.value,
                details,
                time.time(),
            ),
        )
        self._conn.commit()

    def get_enforcement_log(self, limit: int = 100) -> List[Dict[str, Any]]:
        rows = self._conn.execute(
            "SELECT * FROM enforcement_log ORDER BY executed_at DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(row) for row in rows]

    def get_reset_log(self, limit: int = 100) -> List[Dict[str, Any]]:
        rows = self._conn.execute(
            "SELECT * FROM budget_reset_log ORDER BY reset_at DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(row) for row in rows]

    # H2 bug 修复：删除重复定义的 close 方法。
    # 原代码在第 83-88 行已定义 close（正确：归还连接到池），
    # 此处又定义了 close（错误：直接 close 连接，导致连接池泄漏）。
    # Python 类中后定义的方法会覆盖前者，使正确的版本永不生效。
    # 此处不再重复定义，由第 83 行的版本统一处理 close 逻辑。

    def __del__(self) -> None:
        try:
            self.close()
        except (sqlite3.ProgrammingError, AttributeError) as e:
            # 析构时数据库连接已关闭或对象处于无效状态属于正常 GC 路径
            logger.debug("Cleanup during deallocation skipped: %s", e)

    # ------------------------------------------------------------------
    # 单例生命周期扩展
    # ------------------------------------------------------------------

    @classmethod
    def init(cls, db_path: Optional[str] = None) -> "BudgetEnforcer":
        """强制重新创建单例实例（用于启动时指定 db_path 的场景）。

        与 :meth:`get_instance` 的「懒初始化」不同，``init`` 总是创建新实例并
        覆盖已有的单例。行为与重构前 ``_BudgetEnforcerHolder.init`` 一致。

        Parameters
        ----------
        db_path:
            SQLite 数据库路径。``None`` 表示使用默认路径
            (``<output>/data/budget_enforcer.db``)。
        """
        with cls._service_lock:
            cls._db_path = db_path
            cls._service_singleton = cls()
            return cls._service_singleton  # type: ignore[return-value]

    @classmethod
    def reset_instance(cls) -> None:
        """重置单例实例并清除缓存的 db_path。

        扩展了 ``BaseSingletonService.reset_instance``：同时清除 ``_db_path``，
        以保持与原 ``_BudgetEnforcerHolder.reset`` 的行为一致——即 reset 后再次
        ``get_instance`` 会使用默认路径，而非上次 ``init`` 设置的路径。
        """
        with cls._service_lock:
            cls._service_singleton = None
            cls._db_path = None


class _BudgetEnforcerHolder:
    """[Deprecated] 已被 :class:`BaseSingletonService` 单例机制取代.

    本类仅作为占位符保留，避免破坏 ``app/budget/budget_enforcer.py`` re-export
    shim 的导入。新代码应直接使用 :meth:`BudgetEnforcer.get_instance` /
    :meth:`BudgetEnforcer.init` / :meth:`BudgetEnforcer.reset_instance`。
    """

    def __init__(self) -> None:
        # 保留原属性名以兼容可能的外部反射访问
        self._lock = threading.Lock()
        self._instance: Optional[BudgetEnforcer] = None

    def get(self) -> BudgetEnforcer:
        return BudgetEnforcer.get_instance()  # type: ignore[return-value]

    def init(self, db_path: Optional[str] = None) -> BudgetEnforcer:
        return BudgetEnforcer.init(db_path)

    def reset(self) -> None:
        BudgetEnforcer.reset_instance()


_budget_holder = _BudgetEnforcerHolder()


def get_budget_enforcer() -> BudgetEnforcer:
    """获取共享的 :class:`BudgetEnforcer` 单例；首次访问时懒初始化。

    .. deprecated:: V3.0 (2026-08-02)
        本函数保留向后兼容。

    Returns:
        :class:`BudgetEnforcer` 实例（应用生命周期内同一实例）。

    Note:
        同时是 FastAPI 依赖工厂，可直接用于 ``Depends(get_budget_enforcer)``。
        实现是线程安全的，行为与重构前完全一致——内部委托给
        :meth:`BudgetEnforcer.get_instance`。
    """
    return BudgetEnforcer.get_instance()  # type: ignore[return-value]


def init_budget_enforcer(db_path: Optional[str] = None) -> BudgetEnforcer:
    """初始化预算执行器，行为与重构前完全一致。

    内部委托给 :meth:`BudgetEnforcer.init`：强制重新创建单例并指定 db_path。
    """
    return BudgetEnforcer.init(db_path)


__all__ = [
    "BudgetEnforcer",
    "_BudgetEnforcerHolder",
    "_budget_holder",
    "get_budget_enforcer",
    "init_budget_enforcer",
]
