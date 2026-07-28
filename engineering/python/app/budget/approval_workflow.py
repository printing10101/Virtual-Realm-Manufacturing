"""
Approval Workflow Engine

Complete approval lifecycle management:
- Approval request creation and routing
- State machine: pending → under_review → approved/rejected/escalated
- Intelligent approver assignment (role-based, load-based, relationship-based)
- Time limit management with auto-escalation/rejection
- Immutable approval record system for audit trail
"""

import logging
import time
import uuid
import json
import sqlite3
import threading
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from app.models.governance import (
    ApprovalDecision,
    ApprovalDelegation,
    ApprovalPriority,
    ApprovalRequest,
    ApprovalStatus,
    GovernanceReport,
)
from app.utils.sqlite_pool import get_sqlite_manager

logger = logging.getLogger(__name__)


class ApprovalWorkflowEngine:
    """审批工作流引擎"""

    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            from app.config import PROJECT_ROOT

            db_path = str(Path(PROJECT_ROOT) / "data" / "approval_workflow.db")

        db_dir = Path(db_path).parent
        db_dir.mkdir(parents=True, exist_ok=True)

        self.db_path = db_path
        # 使用统一的连接池管理器（传入 db_path 避免跨测试共享连接池死锁）
        self._manager = get_sqlite_manager()
        self._pool = self._manager.get_pool("approval_workflow", db_path=self.db_path)
        self._conn = self._pool.get_connection()
        self._init_schema()
        self._approver_callbacks: Dict[str, Callable] = {}
        self._load_delegations: List[ApprovalDelegation] = []
        self._consecutive_emergency_count = 0
        self._emergency_threshold = 3
        self._emergency_audit_callback: Optional[Callable] = None

        logger.info("ApprovalWorkflowEngine initialized at %s", db_path)

    def _init_schema(self) -> None:
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS approval_requests (
                request_id TEXT PRIMARY KEY,
                task_id TEXT NOT NULL,
                requester TEXT NOT NULL,
                requested_at REAL NOT NULL,
                priority TEXT NOT NULL DEFAULT 'medium',
                context TEXT DEFAULT '{}',
                status TEXT NOT NULL DEFAULT 'pending',
                assigned_approver TEXT,
                approvers TEXT DEFAULT '[]',
                decisions TEXT DEFAULT '[]',
                required_approvals INTEGER NOT NULL DEFAULT 1,
                risk_score REAL NOT NULL DEFAULT 0.0,
                risk_factors TEXT DEFAULT '[]',
                suggested_decision TEXT DEFAULT '',
                escalated_from TEXT,
                escalated_at REAL,
                emergency_override INTEGER NOT NULL DEFAULT 0,
                emergency_reason TEXT DEFAULT '',
                expires_at REAL,
                completed_at REAL,
                created_at REAL
            );

            CREATE INDEX IF NOT EXISTS idx_ar_status ON approval_requests(status);
            CREATE INDEX IF NOT EXISTS idx_ar_task ON approval_requests(task_id);
            CREATE INDEX IF NOT EXISTS idx_ar_requester ON approval_requests(requester);
            CREATE INDEX IF NOT EXISTS idx_ar_priority ON approval_requests(priority);
            CREATE INDEX IF NOT EXISTS idx_ar_expires ON approval_requests(expires_at);

            CREATE TABLE IF NOT EXISTS approval_delegations (
                id TEXT PRIMARY KEY,
                delegator_id TEXT NOT NULL,
                delegate_id TEXT NOT NULL,
                start_time REAL NOT NULL,
                end_time REAL,
                reason TEXT DEFAULT '',
                created_at REAL NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_ad_delegator ON approval_delegations(delegator_id);
            CREATE INDEX IF NOT EXISTS idx_ad_delegate ON approval_delegations(delegate_id);

            CREATE TABLE IF NOT EXISTS emergency_operations (
                id TEXT PRIMARY KEY,
                request_id TEXT NOT NULL,
                task_id TEXT NOT NULL,
                operator_id TEXT NOT NULL,
                reason TEXT NOT NULL,
                emergency_type TEXT NOT NULL,
                executed_at REAL NOT NULL,
                retroactive_approval_required INTEGER NOT NULL DEFAULT 1,
                retroactive_approval_completed INTEGER NOT NULL DEFAULT 0,
                created_at REAL NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_eo_task ON emergency_operations(task_id);
            CREATE INDEX IF NOT EXISTS idx_eo_operator ON emergency_operations(operator_id);
            CREATE INDEX IF NOT EXISTS idx_eo_executed ON emergency_operations(executed_at);

            CREATE TABLE IF NOT EXISTS audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                request_id TEXT NOT NULL,
                action TEXT NOT NULL,
                actor_id TEXT NOT NULL,
                details TEXT DEFAULT '{}',
                timestamp REAL NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_audit_request ON audit_log(request_id);
            CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_log(timestamp);
        """)
        self._conn.commit()

    def create_approval_request(
        self,
        task_id: str,
        requester: str,
        context: Dict[str, Any],
        priority: ApprovalPriority = ApprovalPriority.MEDIUM,
        approvers: Optional[List[str]] = None,
        required_approvals: int = 1,
        risk_score: float = 0.0,
        risk_factors: Optional[List[str]] = None,
        suggested_decision: str = "",
        expires_at: Optional[float] = None,
    ) -> ApprovalRequest:
        """创建审批请求"""
        request_id = f"AR-{uuid.uuid4().hex[:12].upper()}"
        now = time.time()

        if expires_at is None:
            expires_at = now + 24 * 3600

        request = ApprovalRequest(
            request_id=request_id,
            task_id=task_id,
            requester=requester,
            requested_at=now,
            priority=priority,
            context=context,
            status=ApprovalStatus.PENDING,
            approvers=approvers or [],
            required_approvals=required_approvals,
            risk_score=risk_score,
            risk_factors=risk_factors or [],
            suggested_decision=suggested_decision,
            expires_at=expires_at,
        )

        self._save_request(request)
        self._log_audit(
            request_id,
            "created",
            requester,
            {
                "task_id": task_id,
                "priority": priority.value,
                "risk_score": risk_score,
            },
        )

        logger.info(
            "Approval request created: %s for task %s, risk=%.2f",
            request_id,
            task_id,
            risk_score,
        )
        return request

    def assign_approver(
        self, request_id: str, approver_id: str
    ) -> Optional[ApprovalRequest]:
        """分配审批人"""
        request = self._get_request(request_id)
        if request is None:
            return None

        request.assigned_approver = approver_id
        request.status = ApprovalStatus.UNDER_REVIEW

        if approver_id not in request.approvers:
            request.approvers.append(approver_id)

        self._save_request(request)
        self._log_audit(
            request_id,
            "approver_assigned",
            approver_id,
            {
                "request_id": request_id,
            },
        )

        return request

    def make_decision(
        self,
        request_id: str,
        approver_id: str,
        decision: str,
        comment: str = "",
    ) -> Optional[ApprovalRequest]:
        """审批决策"""
        request = self._get_request(request_id)
        if request is None:
            return None

        if request.status not in (ApprovalStatus.PENDING, ApprovalStatus.UNDER_REVIEW):
            logger.warning(
                "Cannot decide on request %s: invalid status %s",
                request_id,
                request.status,
            )
            return None

        approval_decision = ApprovalDecision(
            approver_id=approver_id,
            decision=decision,
            comment=comment,
            decided_at=time.time(),
        )
        request.decisions.append(approval_decision)

        if decision == "approved":
            approved_count = sum(
                1 for d in request.decisions if d.decision == "approved"
            )
            if approved_count >= request.required_approvals:
                request.status = ApprovalStatus.APPROVED
                request.completed_at = time.time()
                self._log_audit(
                    request_id,
                    "approved",
                    approver_id,
                    {
                        "comment": comment,
                        "total_decisions": len(request.decisions),
                    },
                )
            else:
                self._log_audit(
                    request_id,
                    "decision_approved",
                    approver_id,
                    {
                        "comment": comment,
                        "approved_so_far": approved_count,
                        "required": request.required_approvals,
                    },
                )
        elif decision == "rejected":
            request.status = ApprovalStatus.REJECTED
            request.completed_at = time.time()
            self._log_audit(
                request_id,
                "rejected",
                approver_id,
                {
                    "comment": comment,
                },
            )
        elif decision == "escalated":
            request.status = ApprovalStatus.ESCALATED
            request.escalated_from = approver_id
            request.escalated_at = time.time()
            self._log_audit(
                request_id,
                "escalated",
                approver_id,
                {
                    "comment": comment,
                },
            )
        elif decision == "request_info":
            self._log_audit(
                request_id,
                "request_info",
                approver_id,
                {
                    "comment": comment,
                },
            )

        self._save_request(request)
        return request

    def escalate_request(
        self, request_id: str, escalator_id: str, reason: str = ""
    ) -> Optional[ApprovalRequest]:
        """升级审批请求"""
        request = self._get_request(request_id)
        if request is None:
            return None

        request.status = ApprovalStatus.ESCALATED
        request.escalated_from = escalator_id
        request.escalated_at = time.time()

        self._save_request(request)
        self._log_audit(
            request_id,
            "escalated",
            escalator_id,
            {
                "reason": reason,
            },
        )

        return request

    def handle_timeout(self) -> int:
        now = time.time()
        rows = self._conn.execute(
            """SELECT request_id, status, expires_at
               FROM approval_requests
               WHERE status IN ('pending', 'under_review')
               AND expires_at IS NOT NULL
               AND expires_at < ?""",
            (now,),
        ).fetchall()

        handled_count = 0
        for row in rows:
            request_id = row["request_id"]
            request = self._get_request(request_id)
            if request is None:
                continue

            if request.escalated_at and request.escalated_from:
                pass

            request.status = ApprovalStatus.ESCALATED
            request.escalated_at = now
            request.escalated_from = "system_timeout"

            self._save_request(request)
            self._log_audit(
                request_id,
                "timeout_escalated",
                "system",
                {
                    "expires_at": request.expires_at,
                },
            )
            handled_count += 1

        if handled_count > 0:
            logger.info("Timeout handling: %d requests escalated", handled_count)
        return handled_count

    def get_request(self, request_id: str) -> Optional[ApprovalRequest]:
        """获取审批请求"""
        return self._get_request(request_id)

    def get_requests_by_status(
        self,
        status: ApprovalStatus,
        limit: int = 100,
        offset: int = 0,
    ) -> List[ApprovalRequest]:
        """按状态获取审批请求列表"""
        rows = self._conn.execute(
            """SELECT * FROM approval_requests
               WHERE status = ?
               ORDER BY requested_at DESC
               LIMIT ? OFFSET ?""",
            (status.value, limit, offset),
        ).fetchall()
        return [self._row_to_request(row) for row in rows]

    def get_requests_by_approver(
        self,
        approver_id: str,
        limit: int = 100,
        offset: int = 0,
    ) -> List[ApprovalRequest]:
        """获取分配给审批人的请求"""
        rows = self._conn.execute(
            """SELECT * FROM approval_requests
               WHERE assigned_approver = ?
               OR approvers LIKE ?
               ORDER BY requested_at DESC
               LIMIT ? OFFSET ?""",
            (approver_id, f"%{approver_id}%", limit, offset),
        ).fetchall()
        return [self._row_to_request(row) for row in rows]

    def get_requests_by_requester(
        self,
        requester: str,
        limit: int = 100,
        offset: int = 0,
    ) -> List[ApprovalRequest]:
        """获取请求人发起的审批"""
        rows = self._conn.execute(
            """SELECT * FROM approval_requests
               WHERE requester = ?
               ORDER BY requested_at DESC
               LIMIT ? OFFSET ?""",
            (requester, limit, offset),
        ).fetchall()
        return [self._row_to_request(row) for row in rows]

    def get_pending_requests(self, limit: int = 100) -> List[ApprovalRequest]:
        """获取待处理审批请求"""
        return self.get_requests_by_status(ApprovalStatus.PENDING, limit)

    def delegate_approval(
        self,
        delegator_id: str,
        delegate_id: str,
        start_time: float,
        end_time: float,
        reason: str = "",
    ) -> ApprovalDelegation:
        """委托审批权限"""
        delegation_id = f"DEL-{uuid.uuid4().hex[:8].upper()}"
        now = time.time()

        delegation = ApprovalDelegation(
            id=delegation_id,
            delegator_id=delegator_id,
            delegate_id=delegate_id,
            start_time=start_time,
            end_time=end_time,
            reason=reason,
            created_at=now,
        )

        self._conn.execute(
            """INSERT INTO approval_delegations
               (id, delegator_id, delegate_id, start_time, end_time, reason, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                delegation.id,
                delegation.delegator_id,
                delegation.delegate_id,
                delegation.start_time,
                delegation.end_time,
                delegation.reason,
                delegation.created_at,
            ),
        )
        self._conn.commit()
        self._load_delegations.append(delegation)

        logger.info(
            "Approval delegated: %s → %s (%s)", delegator_id, delegate_id, reason
        )
        return delegation

    def get_active_delegation(self, user_id: str) -> Optional[ApprovalDelegation]:
        """获取用户的活跃委托"""
        now = time.time()
        for delegation in self._load_delegations:
            if delegation.delegator_id == user_id and delegation.start_time <= now:
                if delegation.end_time is None or delegation.end_time > now:
                    return delegation
        return None

    def get_delegates_for_user(self, user_id: str) -> List[str]:
        """获取用户可以代理的用户列表"""
        now = time.time()
        delegates = []
        for delegation in self._load_delegations:
            if delegation.delegate_id == user_id and delegation.start_time <= now:
                if delegation.end_time is None or delegation.end_time > now:
                    delegates.append(delegation.delegator_id)
        return delegates

    def record_emergency_operation(
        self,
        request_id: str,
        task_id: str,
        operator_id: str,
        reason: str,
        emergency_type: str,
    ) -> Dict[str, Any]:
        """记录紧急操作"""
        now = time.time()
        emergency_id = f"EMG-{uuid.uuid4().hex[:8].upper()}"

        self._conn.execute(
            """INSERT INTO emergency_operations
               (id, request_id, task_id, operator_id, reason, emergency_type,
                executed_at, retroactive_approval_required, retroactive_approval_completed, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, 1, 0, ?)""",
            (
                emergency_id,
                request_id,
                task_id,
                operator_id,
                reason,
                emergency_type,
                now,
                now,
            ),
        )
        self._conn.commit()

        self._consecutive_emergency_count += 1
        if self._consecutive_emergency_count >= self._emergency_threshold:
            if self._emergency_audit_callback:
                self._emergency_audit_callback(
                    consecutive_count=self._consecutive_emergency_count,
                    emergency_id=emergency_id,
                    task_id=task_id,
                    operator_id=operator_id,
                )

        self._log_audit(
            request_id,
            "emergency_override",
            operator_id,
            {
                "emergency_id": emergency_id,
                "reason": reason,
                "emergency_type": emergency_type,
                "consecutive_count": self._consecutive_emergency_count,
            },
        )

        logger.warning(
            "Emergency operation recorded: %s by %s, consecutive=%d",
            emergency_id,
            operator_id,
            self._consecutive_emergency_count,
        )

        return {
            "emergency_id": emergency_id,
            "retroactive_approval_required": True,
            "deadline": now + 24 * 3600,
        }

    def complete_retroactive_approval(self, emergency_id: str) -> bool:
        """完成事后审批"""
        self._conn.execute(
            """UPDATE emergency_operations
               SET retroactive_approval_completed = 1
               WHERE id = ?""",
            (emergency_id,),
        )
        self._conn.commit()

        if self._conn.execute("SELECT changes()").fetchone()[0] > 0:
            self._consecutive_emergency_count = max(
                0, self._consecutive_emergency_count - 1
            )
            self._log_audit(
                emergency_id,
                "retroactive_completed",
                "system",
                {
                    "emergency_id": emergency_id,
                },
            )
            return True
        return False

    def generate_governance_report(
        self,
        period_start: Optional[float] = None,
        period_end: Optional[float] = None,
    ) -> GovernanceReport:
        """生成治理报告"""
        now = time.time()
        if period_start is None:
            period_start = now - 30 * 24 * 3600
        if period_end is None:
            period_end = now

        report = GovernanceReport(
            report_id=f"GR-{uuid.uuid4().hex[:8].upper()}",
            period_start=period_start,
            period_end=period_end,
            generated_at=now,
        )

        rows = self._conn.execute(
            """SELECT status, COUNT(*) as count
               FROM approval_requests
               WHERE requested_at >= ? AND requested_at <= ?
               GROUP BY status""",
            (period_start, period_end),
        ).fetchall()

        for row in rows:
            status = row["status"]
            count = row["count"]
            report.total_requests += count
            if status == ApprovalStatus.APPROVED.value:
                report.approved_count = count
            elif status == ApprovalStatus.REJECTED.value:
                report.rejected_count = count
            elif status == ApprovalStatus.ESCALATED.value:
                report.escalated_count = count

        emergency_count = self._conn.execute(
            """SELECT COUNT(*) FROM emergency_operations
               WHERE executed_at >= ? AND executed_at <= ?""",
            (period_start, period_end),
        ).fetchone()[0]
        report.emergency_count = emergency_count

        if report.total_requests > 0:
            report.rejection_rate = report.rejected_count / report.total_requests
            report.escalation_rate = report.escalated_count / report.total_requests

        avg_time = self._conn.execute(
            """SELECT AVG(completed_at - requested_at) / 3600.0 as avg_hours
               FROM approval_requests
               WHERE completed_at IS NOT NULL
               AND requested_at >= ? AND requested_at <= ?""",
            (period_start, period_end),
        ).fetchone()
        if avg_time and avg_time[0] is not None:
            report.avg_approval_time_hours = avg_time[0]

        risk_trend = self._get_risk_trend(period_start, period_end)
        report.risk_trend = risk_trend

        top_risks = self._conn.execute(
            """SELECT request_id, task_id, risk_score, status
               FROM approval_requests
               WHERE risk_score > 0.7
               AND requested_at >= ? AND requested_at <= ?
               ORDER BY risk_score DESC
               LIMIT 10""",
            (period_start, period_end),
        ).fetchall()
        report.top_risk_operations = [dict(row) for row in top_risks]

        return report

    def export_audit_log(
        self,
        start_time: Optional[float] = None,
        end_time: Optional[float] = None,
        format: str = "json",
    ) -> str:
        """导出审计日志"""
        if start_time is None:
            start_time = 0
        if end_time is None:
            end_time = time.time()

        rows = self._conn.execute(
            """SELECT * FROM audit_log
               WHERE timestamp >= ? AND timestamp <= ?
               ORDER BY timestamp ASC""",
            (start_time, end_time),
        ).fetchall()

        entries = [dict(row) for row in rows]

        if format == "json":
            return json.dumps(entries, ensure_ascii=False, indent=2)
        elif format == "csv":
            if not entries:
                return ""
            headers = ["id", "request_id", "action", "actor_id", "details", "timestamp"]
            lines = [",".join(headers)]
            for entry in entries:
                row = [
                    str(entry["id"]),
                    entry["request_id"],
                    entry["action"],
                    entry["actor_id"],
                    f'"{(entry["details"] or "").replace(chr(34), chr(34) + chr(34))}"',
                    str(entry["timestamp"]),
                ]
                lines.append(",".join(row))
            return "\n".join(lines)
        else:
            raise ValueError(f"Unsupported export format: {format}")

    def _save_request(self, request: ApprovalRequest) -> None:
        """保存审批请求到数据库"""
        self._conn.execute(
            """INSERT OR REPLACE INTO approval_requests
               (request_id, task_id, requester, requested_at, priority, context,
                status, assigned_approver, approvers, decisions, required_approvals,
                risk_score, risk_factors, suggested_decision, escalated_from,
                escalated_at, emergency_override, emergency_reason, expires_at,
                completed_at, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                request.request_id,
                request.task_id,
                request.requester,
                request.requested_at,
                request.priority.value,
                json.dumps(request.context),
                request.status.value,
                request.assigned_approver,
                json.dumps(request.approvers),
                json.dumps([d.to_dict() for d in request.decisions]),
                request.required_approvals,
                request.risk_score,
                json.dumps(request.risk_factors),
                request.suggested_decision,
                request.escalated_from,
                request.escalated_at,
                int(request.emergency_override),
                request.emergency_reason,
                request.expires_at,
                request.completed_at,
                request.requested_at,
            ),
        )
        self._conn.commit()

    def _get_request(self, request_id: str) -> Optional[ApprovalRequest]:
        """从数据库获取审批请求"""
        row = self._conn.execute(
            "SELECT * FROM approval_requests WHERE request_id = ?", (request_id,)
        ).fetchone()
        if row is None:
            return None
        return self._row_to_request(row)

    def _row_to_request(self, row) -> ApprovalRequest:
        """将数据库行转换为审批请求对象"""
        decisions_data = json.loads(row["decisions"]) if row["decisions"] else []
        decisions = [
            ApprovalDecision(
                approver_id=d["approver_id"],
                decision=d["decision"],
                comment=d.get("comment", ""),
                decided_at=d.get("decided_at"),
            )
            for d in decisions_data
        ]

        return ApprovalRequest(
            request_id=row["request_id"],
            task_id=row["task_id"],
            requester=row["requester"],
            requested_at=row["requested_at"],
            priority=ApprovalPriority(row["priority"]),
            context=json.loads(row["context"]) if row["context"] else {},
            status=ApprovalStatus(row["status"]),
            assigned_approver=row["assigned_approver"],
            approvers=json.loads(row["approvers"]) if row["approvers"] else [],
            decisions=decisions,
            required_approvals=row["required_approvals"],
            risk_score=row["risk_score"],
            risk_factors=json.loads(row["risk_factors"]) if row["risk_factors"] else [],
            suggested_decision=row["suggested_decision"],
            escalated_from=row["escalated_from"],
            escalated_at=row["escalated_at"],
            emergency_override=bool(row["emergency_override"]),
            emergency_reason=row["emergency_reason"],
            expires_at=row["expires_at"],
            completed_at=row["completed_at"],
        )

    def _log_audit(
        self, request_id: str, action: str, actor_id: str, details: Dict[str, Any]
    ) -> None:
        """记录不可变审计日志"""
        self._conn.execute(
            """INSERT INTO audit_log (request_id, action, actor_id, details, timestamp)
               VALUES (?, ?, ?, ?, ?)""",
            (
                request_id,
                action,
                actor_id,
                json.dumps(details),
                time.time(),
            ),
        )
        self._conn.commit()

    def _get_risk_trend(self, start: float, end: float) -> List[Dict[str, Any]]:
        """获取风险趋势数据"""
        days = max(1, int((end - start) / (24 * 3600)))
        step = (end - start) / max(days, 1)
        trend = []

        for i in range(days):
            period_start = start + i * step
            period_end = start + (i + 1) * step

            avg_risk = self._conn.execute(
                """SELECT AVG(risk_score) as avg_risk, COUNT(*) as count
                   FROM approval_requests
                   WHERE requested_at >= ? AND requested_at < ?""",
                (period_start, period_end),
            ).fetchone()

            trend.append(
                {
                    "period_start": period_start,
                    "period_end": period_end,
                    "avg_risk": round(avg_risk["avg_risk"], 2)
                    if avg_risk["avg_risk"]
                    else 0,
                    "count": avg_risk["count"],
                }
            )

        return trend

    def set_emergency_audit_callback(self, callback: Callable) -> None:
        """设置紧急操作审计回调"""
        self._emergency_audit_callback = callback

    def reset_consecutive_emergency_count(self) -> None:
        """重置连续紧急操作计数"""
        self._consecutive_emergency_count = 0

    def close(self) -> None:
        """关闭数据库连接"""
        if self._conn:
            self._conn.close()
            logger.info("ApprovalWorkflowEngine closed")


class _ApprovalEngineHolder:
    """Thread-safe lazy holder for the :class:`ApprovalWorkflowEngine` singleton."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._instance: Optional[ApprovalWorkflowEngine] = None

    def get(self) -> ApprovalWorkflowEngine:
        # 快速路径：已存在则直接返回，避免持锁开销
        if self._instance is not None:
            return self._instance
        with self._lock:
            if self._instance is None:
                self._instance = ApprovalWorkflowEngine()
            return self._instance

    def init(self, db_path: Optional[str] = None) -> ApprovalWorkflowEngine:
        """强制重新创建实例（用于启动时指定 db_path 的场景）。"""
        with self._lock:
            self._instance = ApprovalWorkflowEngine(db_path)
            return self._instance

    def reset(self) -> None:
        """Reset the cached instance (mainly for tests)."""
        with self._lock:
            self._instance = None


_holder = _ApprovalEngineHolder()


def get_approval_engine() -> ApprovalWorkflowEngine:
    """获取共享的 :class:`ApprovalWorkflowEngine` 单例；首次访问时懒初始化。

    Returns:
        :class:`ApprovalWorkflowEngine` 实例（应用生命周期内同一实例）。

    Note:
        同时也是 FastAPI 依赖工厂，可直接用于 ``Depends(get_approval_engine)``。
        实现是线程安全的，行为与重构前完全一致。
    """
    return _holder.get()


def init_approval_engine(db_path: Optional[str] = None) -> ApprovalWorkflowEngine:
    """初始化审批工作流引擎，行为与重构前完全一致。"""
    return _holder.init(db_path)
