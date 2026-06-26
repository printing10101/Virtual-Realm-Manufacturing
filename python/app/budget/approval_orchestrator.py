"""审批工作流解耦层（Orchestrator）。

为什么要解耦？
    - 业务方（budget、agent_gateway、governance）不应该直接 import
      ``approval_workflow.ApprovalWorkflowEngine``：
        1. 后者跟 SQLite 持久化强耦合，单元测试要起 DB
        2. 它有自己的状态机、回调机制、紧急审批等复杂策略
        3. 不同业务场景对审批的需求差异很大
    - 解耦后：
        - 业务方 import ``approval_orchestrator``，调用稳定 API
        - 内部根据 strategy 决定走哪条路径（AUTO_EXECUTE 直接放行；
          EXECUTE_AFTER_RECORD 落审计日志；APPROVE_BEFORE_EXECUTE
          走 ApprovalWorkflowEngine；MULTI_APPROVAL 多签）
        - 换底层实现（迁移到专用审批服务 / 第三方 SaaS）不影响业务方

设计目标：
    - **零外部依赖**：orchestrator 本身只依赖标准库 + project models
    - **同步 API**：与 ``ApprovalWorkflowEngine`` 风格一致
    - **可降级**：当底层引擎不可用（DB 没配 / 模块未安装）时降级为
      内存版审批，不阻断业务流程
    - **审计落盘**：所有审批事件都写 jsonl，便于后期审计 / 影子分析
"""
from __future__ import annotations

import json
import logging
import os
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Optional

from app.utils.utils import get_output_dir

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 数据模型
# ---------------------------------------------------------------------------


class DecisionOutcome(str, Enum):
    """orchestrator 层的统一决策结果。"""

    AUTO_APPROVED = "auto_approved"
    RECORDED = "recorded"
    APPROVED = "approved"
    REJECTED = "rejected"
    NEEDS_REVIEW = "needs_review"
    ERROR = "error"


@dataclass
class ApprovalRequestLite:
    """业务方传入的轻量审批请求（orchestrator 入口格式）。"""

    task_id: str
    requester: str
    # 业务上下文：金额、风险分、敏感度、agent_role 等
    context: dict[str, Any] = field(default_factory=dict)
    # 显式指定策略（None 则自动根据 context 推断）
    strategy: Optional[str] = None  # AUTO_EXECUTE / EXECUTE_AFTER_RECORD / APPROVE_BEFORE_EXECUTE / MULTI_APPROVAL
    # 必填审批人数（仅 MULTI_APPROVAL）
    required_approvals: int = 1
    # 超时秒数
    timeout_sec: int = 86400  # 24h
    # 业务优先级
    priority: str = "normal"  # low / normal / high / emergency


@dataclass
class ApprovalDecisionLite:
    """orchestrator 返回的轻量决策。"""

    outcome: DecisionOutcome
    request_id: str
    reason: str = ""
    approvers: list[str] = field(default_factory=list)
    requires_human: bool = False
    fallback_to_full_engine: bool = False


# ---------------------------------------------------------------------------
# 策略推断
# ---------------------------------------------------------------------------


def infer_strategy(req: ApprovalRequestLite) -> str:
    """根据 context 推断审批策略。

    规则（可后续通过配置覆盖）：
        - 紧急 / 风险分 ≥ 0.8 / 敏感度=core → MULTI_APPROVAL
        - 风险分 ≥ 0.5 / 敏感度=confidential → APPROVE_BEFORE_EXECUTE
        - 一般业务 → EXECUTE_AFTER_RECORD
        - 风险分 < 0.1 且非敏感 → AUTO_EXECUTE
    """
    if req.strategy is not None:
        return req.strategy
    risk = float(req.context.get("risk_score", 0.0) or 0.0)
    sensitivity = req.context.get("sensitivity", "normal")
    if req.priority == "emergency" or risk >= 0.8 or sensitivity == "core":
        return "MULTI_APPROVAL"
    if risk >= 0.5 or sensitivity == "confidential":
        return "APPROVE_BEFORE_EXECUTE"
    if risk < 0.1 and sensitivity == "normal":
        return "AUTO_EXECUTE"
    return "EXECUTE_AFTER_RECORD"


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------


class ApprovalOrchestrator:
    """审批工作流解耦层（单例）。

    用法::

        orch = ApprovalOrchestrator.get_instance()
        req = ApprovalRequestLite(task_id="t-1", requester="alice",
                                   context={"risk_score": 0.3})
        decision = orch.submit(req)
        if decision.outcome == DecisionOutcome.NEEDS_REVIEW:
            ...  # 业务方等待审批回调
    """

    _instance: Optional["ApprovalOrchestrator"] = None
    _lock = threading.Lock()

    def __init__(self, audit_log_path: Optional[str] = None):
        if audit_log_path is None:
            audit_log_path = str(
                get_output_dir("budget") / "approval_audit.jsonl"
            )
        self._audit_path = Path(audit_log_path)
        self._audit_path.parent.mkdir(parents=True, exist_ok=True)
        # 内存中跟踪 in-flight 的请求（业务方需要时 query）
        self._pending: dict[str, ApprovalRequestLite] = {}
        self._engine = None  # 懒加载完整引擎
        self._engine_load_failed = False

    @classmethod
    def get_instance(cls) -> "ApprovalOrchestrator":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    # ============================================================== 内部

    def _try_get_full_engine(self):
        """懒加载 ApprovalWorkflowEngine；失败则降级。"""
        if self._engine is not None or self._engine_load_failed:
            return self._engine
        try:
            from app.budget.approval_workflow import (
                ApprovalWorkflowEngine,
            )

            self._engine = ApprovalWorkflowEngine()
        except (ImportError, ModuleNotFoundError, RuntimeError) as e:  # noqa: BLE001
            logger.warning("ApprovalWorkflowEngine 加载失败，降级", exc_info=True)
            self._engine_load_failed = True
        return self._engine

    def _audit(self, record: dict[str, Any]) -> None:
        """落审计 jsonl。"""
        try:
            with open(self._audit_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False, default=str))
                f.write("\n")
        except (OSError, IOError, PermissionError) as e:  # noqa: BLE001
            logger.debug("audit log write failed", exc_info=True)

    # ============================================================== 入口

    def submit(self, req: ApprovalRequestLite) -> ApprovalDecisionLite:
        """提交审批请求并立即返回决策。"""
        strategy = infer_strategy(req)
        request_id = f"apr-{uuid.uuid4().hex[:12]}"
        # 落审计
        self._audit(
            {
                "event": "approval.submit",
                "request_id": request_id,
                "task_id": req.task_id,
                "requester": req.requester,
                "strategy": strategy,
                "priority": req.priority,
                "context": req.context,
                "ts": time.time(),
            }
        )

        # 策略分支
        if strategy == "AUTO_EXECUTE":
            return ApprovalDecisionLite(
                outcome=DecisionOutcome.AUTO_APPROVED,
                request_id=request_id,
                reason="low risk + normal sensitivity, auto approved",
                approvers=[],
            )
        if strategy == "EXECUTE_AFTER_RECORD":
            return ApprovalDecisionLite(
                outcome=DecisionOutcome.RECORDED,
                request_id=request_id,
                reason="recorded for later review",
                approvers=[],
            )
        if strategy in ("APPROVE_BEFORE_EXECUTE", "MULTI_APPROVAL"):
            # 走完整引擎
            engine = self._try_get_full_engine()
            if engine is None:
                # 降级：标 NEEDS_REVIEW，让上层处理
                self._pending[request_id] = req
                return ApprovalDecisionLite(
                    outcome=DecisionOutcome.NEEDS_REVIEW,
                    request_id=request_id,
                    reason=(
                        "full engine unavailable, marked as pending; "
                        "manual review required"
                    ),
                    requires_human=True,
                )
            try:
                from app.models.governance import ApprovalPriority

                priority_enum = {
                    "low": ApprovalPriority.LOW,
                    "normal": ApprovalPriority.MEDIUM,
                    "high": ApprovalPriority.HIGH,
                    "emergency": ApprovalPriority.CRITICAL,
                }.get(req.priority, ApprovalPriority.MEDIUM)
                engine.create_approval_request(
                    task_id=req.task_id,
                    requester=req.requester,
                    context=req.context,
                    priority=priority_enum,
                    required_approvals=req.required_approvals,
                )
                self._pending[request_id] = req
                return ApprovalDecisionLite(
                    outcome=DecisionOutcome.NEEDS_REVIEW,
                    request_id=request_id,
                    reason=(
                        f"submitted to ApprovalWorkflowEngine, strategy={strategy}"
                    ),
                    requires_human=True,
                    fallback_to_full_engine=True,
                )
            except (RuntimeError, ValueError, TypeError, AttributeError) as e:  # noqa: BLE001
                logger.warning("full engine submit failed", exc_info=True)
                self._pending[request_id] = req
                return ApprovalDecisionLite(
                    outcome=DecisionOutcome.NEEDS_REVIEW,
                    request_id=request_id,
                    reason=f"engine error, fallback to manual review: {e}",
                    requires_human=True,
                )
        # 未知策略
        return ApprovalDecisionLite(
            outcome=DecisionOutcome.ERROR,
            request_id=request_id,
            reason=f"unknown strategy: {strategy}",
        )

    def query(self, request_id: str) -> Optional[ApprovalRequestLite]:
        """查询 in-flight 请求（仅看 orchestrator 内存中的）。"""
        return self._pending.get(request_id)

    def list_pending(self) -> list[dict[str, Any]]:
        """列出所有待审批请求（orchestrator 视角）。"""
        out = []
        for rid, req in self._pending.items():
            out.append(
                {
                    "request_id": rid,
                    "task_id": req.task_id,
                    "requester": req.requester,
                    "strategy": infer_strategy(req),
                    "priority": req.priority,
                }
            )
        return out

    def decide(
        self,
        request_id: str,
        approver: str,
        approve: bool,
        reason: str = "",
    ) -> ApprovalDecisionLite:
        """人工在 orchestrator 层完成决策（仅适用于 in-memory 路径）。"""
        req = self._pending.get(request_id)
        if req is None:
            return ApprovalDecisionLite(
                outcome=DecisionOutcome.ERROR,
                request_id=request_id,
                reason="request not found in orchestrator pending list",
            )
        outcome = (
            DecisionOutcome.APPROVED if approve else DecisionOutcome.REJECTED
        )
        self._audit(
            {
                "event": "approval.decide",
                "request_id": request_id,
                "approver": approver,
                "approve": approve,
                "reason": reason,
                "ts": time.time(),
            }
        )
        if approve:
            del self._pending[request_id]
        # 拒绝也清理
        if not approve and request_id in self._pending:
            del self._pending[request_id]
        return ApprovalDecisionLite(
            outcome=outcome,
            request_id=request_id,
            reason=reason or f"decided by {approver}",
            approvers=[approver],
        )

    def summary(self) -> dict[str, Any]:
        """orchestrator 自身状态摘要。"""
        return {
            "pending_count": len(self._pending),
            "engine_loaded": self._engine is not None,
            "engine_load_failed": self._engine_load_failed,
            "audit_path": str(self._audit_path),
        }


__all__ = [
    "ApprovalOrchestrator",
    "ApprovalRequestLite",
    "ApprovalDecisionLite",
    "DecisionOutcome",
    "infer_strategy",
]
