"""
Budget Enforcement & Control Mechanism

Pre-execution atomic budget checks, hierarchical budget status handling,
periodic auto-reset, intelligent cost optimization suggestions.
"""
import logging
import time
import json
import sqlite3
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set
from pathlib import Path

from app.models.budget import (
    BudgetLevel,
    BudgetPeriod,
    BudgetStatus,
    ResourceType,
    BudgetPolicy,
    BudgetCheckResult,
    BudgetAdjustment,
    BudgetAlert,
    CostOptimizationSuggestion,
    DEFAULT_GLOBAL_BUDGETS,
)

logger = logging.getLogger(__name__)


class EnforcementAction(str, Enum):
    """强制执行动作"""
    ALLOW = "allow"
    WARN = "warn"
    BLOCK = "block"
    CANCEL_PENDING = "cancel_pending"
    SUSPEND_AGENT = "suspend_agent"
    NOTIFY_ADMIN = "notify_admin"


@dataclass
class EnforcementResult:
    """强制执行结果"""
    actions_taken: List[EnforcementAction] = field(default_factory=list)
    check_result: Optional[BudgetCheckResult] = None
    alerts_generated: List[BudgetAlert] = field(default_factory=list)
    cancelled_tasks: List[str] = field(default_factory=list)
    suspended_agents: List[str] = field(default_factory=list)
    notifications_sent: bool = False


class BudgetEnforcer:
    """预算强制执行器"""

    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            from app.config import PROJECT_ROOT
            db_path = str(Path(PROJECT_ROOT) / "data" / "budget_enforcer.db")

        db_dir = Path(db_path).parent
        db_dir.mkdir(parents=True, exist_ok=True)

        self.db_path = db_path
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._policies: Dict[str, BudgetPolicy] = {}
        self._alert_callbacks: List[Callable[[BudgetAlert], None]] = []
        self._task_canceller: Optional[Callable[[str], None]] = None
        self._agent_suspender: Optional[Callable[[str, str], None]] = None
        self._init_schema()
        self._load_policies()
        self._load_default_policies()

        logger.info("BudgetEnforcer initialized at %s", db_path)

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
            )
        )
        self._conn.commit()
        self._policies[key] = policy
        logger.info(
            "Budget policy set: %s limit=%.2f period=%s",
            key, policy.limit, policy.period.value
        )

    def get_policy(self, level: BudgetLevel, scope_id: str,
                   resource_type: ResourceType) -> Optional[BudgetPolicy]:
        key = self._policy_key(level.value, scope_id, resource_type.value)
        return self._policies.get(key)

    def get_all_policies(self,
                         level: Optional[BudgetLevel] = None,
                         scope_id: Optional[str] = None) -> List[BudgetPolicy]:
        result = []
        for policy in self._policies.values():
            if level and policy.level != level:
                continue
            if scope_id and policy.scope_id != scope_id:
                continue
            result.append(policy)
        return sorted(result, key=lambda p: (p.level.value, p.scope_id))

    def adjust_budget(self, level: BudgetLevel, scope_id: str,
                      resource_type: ResourceType, new_limit: float,
                      reason: str = "", adjusted_by: str = "admin") -> Optional[BudgetPolicy]:
        key = self._policy_key(level.value, scope_id, resource_type.value)
        old_policy = self._policies.get(key)

        old_limit = old_policy.limit if old_policy else 0.0

        if old_policy:
            old_policy.limit = new_limit
            old_policy._adjustment_reason = reason
            self.set_policy(old_policy)
        else:
            new_policy = BudgetPolicy(
                level=level, scope_id=scope_id, resource_type=resource_type,
                limit=new_limit,
            )
            self.set_policy(new_policy)

        if hasattr(self, '_cost_tracker_ref') and self._cost_tracker_ref:
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
            level.value, scope_id, resource_type.value, old_limit, new_limit, adjusted_by
        )
        return self._policies.get(key)

    def check_budget(self, level: BudgetLevel, scope_id: str,
                     resource_type: ResourceType,
                     planned_usage: float = 0.0) -> BudgetCheckResult:
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
            result.block_reason = f"Budget policy disabled: {scope_id}/{resource_type.value}"
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

    def check_budget_cascade(self, agent_id: str, project_id: str = "default",
                             resource_type: ResourceType = ResourceType.TOTAL_COST,
                             planned_usage: float = 0.0) -> BudgetCheckResult:
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

    def record_usage(self, level: BudgetLevel, scope_id: str,
                     resource_type: ResourceType, usage: float) -> None:
        """记录资源用量并更新策略"""
        key = self._policy_key(level.value, scope_id, resource_type.value)
        policy = self._policies.get(key)

        if policy is None:
            return

        policy.current_usage += usage

        self._conn.execute(
            """UPDATE budget_policies SET current_usage = ?, updated_at = ?
               WHERE level = ? AND scope_id = ? AND resource_type = ?""",
            (policy.current_usage, time.time(),
             level.value, scope_id, resource_type.value)
        )
        self._conn.commit()

    def enforce(self, level: BudgetLevel, scope_id: str,
                resource_type: ResourceType,
                planned_usage: float = 0.0) -> EnforcementResult:
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

        alert = self._create_alert(
            level, scope_id, resource_type, check, "exceeded"
        )
        result.alerts_generated.append(alert)

        policy = check.policy
        if policy and policy.hard_stop:
            result.actions_taken.append(EnforcementAction.CANCEL_PENDING)

            if self._task_canceller and policy:
                cancelled = self._cancel_pending_tasks(
                    level, scope_id, resource_type
                )
                result.cancelled_tasks = cancelled

            if level == BudgetLevel.AGENT:
                result.actions_taken.append(EnforcementAction.SUSPEND_AGENT)
                result.suspended_agents.append(scope_id)

                if self._agent_suspender:
                    self._agent_suspender(
                        scope_id,
                        f"Budget exceeded: {resource_type.value} "
                        f"({check.usage_ratio:.1%})"
                    )

        if policy and policy.auto_notify:
            result.actions_taken.append(EnforcementAction.NOTIFY_ADMIN)
            result.notifications_sent = True

        self._log_enforcement(result, level, scope_id, resource_type)

        return result

    def enforce_cascade(self, agent_id: str, project_id: str = "default",
                        resource_type: ResourceType = ResourceType.TOTAL_COST,
                        planned_usage: float = 0.0) -> EnforcementResult:
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

    def reset_period(self, level: BudgetLevel, scope_id: str,
                     resource_type: ResourceType) -> None:
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
                level.value, scope_id, resource_type.value,
                policy.period.value, old_usage, policy.limit, time.time()
            )
        )

        policy.current_usage = 0.0
        policy.last_reset_at = time.time()

        self._conn.execute(
            """UPDATE budget_policies 
               SET current_usage = 0.0, last_reset_at = ?, updated_at = ?
               WHERE level = ? AND scope_id = ? AND resource_type = ?""",
            (policy.last_reset_at, time.time(),
             level.value, scope_id, resource_type.value)
        )
        self._conn.commit()

        logger.info(
            "Budget reset: %s/%s/%s, previous usage: %.2f",
            level.value, scope_id, resource_type.value, old_usage
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
                    (now, now,
                     policy.level.value, policy.scope_id, policy.resource_type.value)
                )

                self._conn.execute(
                    """INSERT INTO budget_reset_log 
                       (level, scope_id, resource_type, period, 
                        usage_before_reset, limit_at_reset, reset_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (
                        policy.level.value, policy.scope_id,
                        policy.resource_type.value, policy.period.value,
                        old_usage, policy.limit, now
                    )
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
                (now, policy.level.value, policy.scope_id, policy.resource_type.value)
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
                (now, now,
                 policy.level.value, policy.scope_id, policy.resource_type.value)
            )
            self._conn.execute(
                """INSERT INTO budget_reset_log 
                   (level, scope_id, resource_type, period, 
                    usage_before_reset, limit_at_reset, reset_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    policy.level.value, policy.scope_id,
                    policy.resource_type.value, policy.period.value,
                    old_usage, policy.limit, now
                )
            )
            self._conn.commit()
            logger.info(
                "Period reset triggered: %s/%s/%s, previous: %.2f",
                policy.level.value, policy.scope_id,
                policy.resource_type.value, old_usage
            )

    def _create_alert(self, level: BudgetLevel, scope_id: str,
                      resource_type: ResourceType,
                      check: BudgetCheckResult,
                      alert_type: str) -> BudgetAlert:
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
            status=BudgetStatus.WARNING if alert_type == "warning" else BudgetStatus.EXCEEDED,
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
                level.value, scope_id, resource_type.value,
                alert.status.value, alert.current_usage,
                alert.limit, alert.usage_ratio, alert.message, now
            )
        )
        self._conn.commit()

        for callback in self._alert_callbacks:
            try:
                callback(alert)
            except Exception as e:
                logger.error("Alert callback error: %s", e)

        return alert

    def get_alerts(self, status: Optional[str] = None,
                   unread_only: bool = False,
                   limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
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
            params + [limit, offset]
        ).fetchall()

        return [dict(row) for row in rows]

    def mark_alert_read(self, alert_id: int) -> None:
        self._conn.execute(
            "UPDATE budget_alerts SET is_read = 1 WHERE id = ?",
            (alert_id,)
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

    def _cancel_pending_tasks(self, level: BudgetLevel,
                              scope_id: str,
                              resource_type: ResourceType) -> List[str]:
        cancelled = []
        if self._task_canceller:
            try:
                if level == BudgetLevel.AGENT:
                    self._task_canceller(scope_id)
                    cancelled.append(scope_id)
                elif level == BudgetLevel.GLOBAL:
                    self._task_canceller("global")
                    cancelled.append("global")
            except Exception as e:
                logger.error("Task cancellation error: %s", e)
        return cancelled

    def _log_enforcement(self, result: EnforcementResult,
                         level: BudgetLevel, scope_id: str,
                         resource_type: ResourceType) -> None:
        details = json.dumps({
            "actions": [a.value for a in result.actions_taken],
            "cancelled_tasks": result.cancelled_tasks,
            "suspended_agents": result.suspended_agents,
            "notifications_sent": result.notifications_sent,
        })
        self._conn.execute(
            """INSERT INTO enforcement_log 
               (action, level, scope_id, resource_type, details, executed_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                ",".join(a.value for a in result.actions_taken),
                level.value, scope_id, resource_type.value,
                details, time.time()
            )
        )
        self._conn.commit()

    def get_enforcement_log(self, limit: int = 100) -> List[Dict[str, Any]]:
        rows = self._conn.execute(
            "SELECT * FROM enforcement_log ORDER BY executed_at DESC LIMIT ?",
            (limit,)
        ).fetchall()
        return [dict(row) for row in rows]

    def get_reset_log(self, limit: int = 100) -> List[Dict[str, Any]]:
        rows = self._conn.execute(
            "SELECT * FROM budget_reset_log ORDER BY reset_at DESC LIMIT ?",
            (limit,)
        ).fetchall()
        return [dict(row) for row in rows]

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            logger.info("BudgetEnforcer closed")


class CostOptimizer:
    """智能成本优化建议系统"""

    from app.core.cost_tracker import ModelType as CTModelType

    MODEL_ALTERNATIVES = {
        CTModelType.CFC.value: [
            {"model": "LTC", "cost_factor": 0.7, "performance_note": "相近精度，低30%成本"},
            {"model": "Custom", "cost_factor": 0.5, "performance_note": "精简模型，适用于简单任务"},
        ],
        CTModelType.LTC.value: [
            {"model": "CFC", "cost_factor": 1.2, "performance_note": "更高精度但成本较高"},
            {"model": "Custom", "cost_factor": 0.6, "performance_note": "精简模型，适用于推理任务"},
        ],
        CTModelType.HYBRID_LNN.value: [
            {"model": "LTC", "cost_factor": 0.5, "performance_note": "单模型方案，低成本替代"},
            {"model": "CFC", "cost_factor": 0.8, "performance_note": "简化架构，适中成本"},
        ],
        CTModelType.TRANSFORMER.value: [
            {"model": "HybridLNN", "cost_factor": 0.3, "performance_note": "LNN架构，显著降本"},
            {"model": "Custom", "cost_factor": 0.4, "performance_note": "轻量模型替代"},
        ],
        CTModelType.CUSTOM.value: [
            {"model": "LTC", "cost_factor": 1.5, "performance_note": "更高性能标准模型"},
            {"model": "CFC", "cost_factor": 2.0, "performance_note": "最高精度专业模型"},
        ],
    }

    def __init__(self, cost_tracker=None):
        self._cost_tracker = cost_tracker

    def set_cost_tracker(self, cost_tracker) -> None:
        self._cost_tracker = cost_tracker

    def analyze_model_cost(self) -> List[CostOptimizationSuggestion]:
        from app.core.cost_tracker import CostDimension, ModelType as CTModelType

        suggestions = []

        if self._cost_tracker is None:
            return suggestions

        summaries = self._cost_tracker.get_all_summaries(CostDimension.MODEL)

        for summary in summaries:
            model_name = summary.scope_id

            alternatives = self.MODEL_ALTERNATIVES.get(model_name)
            if not alternatives:
                alternatives = self.MODEL_ALTERNATIVES.get(CTModelType.CUSTOM.value, [])

            for alt in alternatives:
                alt_cost = summary.total_cost * alt["cost_factor"]
                savings = summary.total_cost - alt_cost

                if savings > 0:
                    suggestion = CostOptimizationSuggestion(
                        suggestion_id=f"model_{model_name}_{alt['model']}_{int(time.time())}",
                        category="model_optimization",
                        title=f"模型替代建议: {model_name} → {alt['model']}",
                        description=(
                            f"当前模型 {model_name} 总成本为 {summary.total_cost:.6f}，"
                            f"使用 {alt['model']} 预估成本 {alt_cost:.6f}。"
                            f"{alt['performance_note']}。"
                        ),
                        current_cost=summary.total_cost,
                        estimated_savings=savings,
                        savings_percentage=(savings / summary.total_cost * 100) if summary.total_cost > 0 else 0,
                        priority="high" if savings > summary.total_cost * 0.3 else "medium",
                        recommendation=f"建议将 {model_name} 相关任务迁移至 {alt['model']} 模型",
                        metrics={
                            "current_model": model_name,
                            "suggested_model": alt["model"],
                            "task_count": summary.task_count,
                            "gpu_time_cost": summary.gpu_time_cost,
                        },
                        generated_at=time.time(),
                    )
                    suggestions.append(suggestion)

        return suggestions

    def analyze_gpu_utilization(self, gpu_utilization_threshold: float = 0.5) -> List[CostOptimizationSuggestion]:
        suggestions = []

        if self._cost_tracker is None:
            return suggestions

        from app.core.cost_tracker import CostDimension

        gpu_summary = self._cost_tracker.get_all_summaries(CostDimension.TASK)
        low_util_tasks = [
            s for s in gpu_summary
            if s.total_gpu_seconds > 0 and (s.total_gpu_memory_gb_seconds / s.total_gpu_seconds if s.total_gpu_seconds > 0 else 1.0) < gpu_utilization_threshold
        ]

        if low_util_tasks:
            suggestion = CostOptimizationSuggestion(
                suggestion_id=f"gpu_util_{int(time.time())}",
                category="resource_optimization",
                title="GPU利用率优化建议",
                description=(
                    f"检测到 {len(low_util_tasks)} 个任务的GPU利用率低于{gpu_utilization_threshold*100:.0f}%。"
                    f"建议采用批量推理策略，将多个低利用率任务合并执行。"
                ),
                current_cost=sum(t.total_cost for t in low_util_tasks),
                estimated_savings=sum(t.total_cost for t in low_util_tasks) * 0.3,
                savings_percentage=30.0,
                priority="medium",
                recommendation="启用批量推理模式，合并GPU低利用率任务以提升资源效率",
                metrics={
                    "low_utilization_task_count": len(low_util_tasks),
                    "threshold": gpu_utilization_threshold,
                },
                generated_at=time.time(),
            )
            suggestions.append(suggestion)

        return suggestions

    def analyze_training_efficiency(self) -> List[CostOptimizationSuggestion]:
        suggestions = []

        if self._cost_tracker is None:
            return suggestions

        from app.core.cost_tracker import CostDimension

        model_summaries = self._cost_tracker.get_all_summaries(CostDimension.MODEL)

        for summary in model_summaries:
            if summary.task_count > 5 and summary.total_gpu_seconds > 3600:
                suggestion = CostOptimizationSuggestion(
                    suggestion_id=f"training_reuse_{summary.scope_id}_{int(time.time())}",
                    category="training_efficiency",
                    title=f"训练复用建议: {summary.scope_id}",
                    description=(
                        f"模型 {summary.scope_id} 已执行 {summary.task_count} 次训练任务，"
                        f"累计GPU时间 {summary.total_gpu_seconds:.0f}秒。"
                        f"检测到重复训练模式，建议启用模型复用机制。"
                    ),
                    current_cost=summary.total_cost,
                    estimated_savings=summary.total_cost * 0.4,
                    savings_percentage=40.0,
                    priority="high",
                    recommendation=(
                        f"为 {summary.scope_id} 启用预训练模型缓存，"
                        f"对相似任务复用已有模型权重，减少冗余训练"
                    ),
                    metrics={
                        "model": summary.scope_id,
                        "task_count": summary.task_count,
                        "total_gpu_seconds": summary.total_gpu_seconds,
                    },
                    generated_at=time.time(),
                )
                suggestions.append(suggestion)

        return suggestions

    def generate_all_suggestions(self) -> List[CostOptimizationSuggestion]:
        all_suggestions = []
        all_suggestions.extend(self.analyze_model_cost())
        all_suggestions.extend(self.analyze_gpu_utilization())
        all_suggestions.extend(self.analyze_training_efficiency())
        return sorted(all_suggestions, key=lambda s: s.estimated_savings, reverse=True)


_budget_enforcer: Optional[BudgetEnforcer] = None
_cost_optimizer: Optional[CostOptimizer] = None


def get_budget_enforcer() -> BudgetEnforcer:
    global _budget_enforcer
    if _budget_enforcer is None:
        _budget_enforcer = BudgetEnforcer()
    return _budget_enforcer


def init_budget_enforcer(db_path: Optional[str] = None) -> BudgetEnforcer:
    global _budget_enforcer
    _budget_enforcer = BudgetEnforcer(db_path)
    return _budget_enforcer


def get_cost_optimizer() -> CostOptimizer:
    global _cost_optimizer
    if _cost_optimizer is None:
        _cost_optimizer = CostOptimizer()
    return _cost_optimizer


def init_cost_optimizer() -> CostOptimizer:
    global _cost_optimizer
    _cost_optimizer = CostOptimizer()
    return _cost_optimizer
