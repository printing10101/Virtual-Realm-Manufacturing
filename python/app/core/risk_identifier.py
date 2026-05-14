"""
High-Risk Operation Identification System

Automatic identification of operations requiring approval:
- T-type operations: Process parameter dispatch to production machines
- Model operations: Training new models and overwriting existing models
- C-type operations: System configuration modifications
- Sensitive data access: Historical process data access
- Budget threshold exceedance

Multi-factor risk scoring algorithm for approval strategy application.
"""
from __future__ import annotations
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from app.models.governance import (
    AgentRole,
    ApprovalPriority,
    ApprovalStrategy,
    ResourceSensitivity,
    TaskType,
)

logger = logging.getLogger(__name__)


class OperationCategory(str, Enum):
    """操作分类"""
    T_TYPE = "T"
    C_TYPE = "C"
    M_TYPE = "M"
    D_TYPE = "D"
    B_TYPE = "B"


@dataclass
class RiskFactor:
    """风险因子"""
    name: str
    weight: float
    score: float
    description: str = ""


@dataclass
class RiskAssessment:
    """风险评估结果"""
    operation_id: str = ""
    operation_type: str = ""
    operation_category: Optional[OperationCategory] = None
    risk_score: float = 0.0
    risk_level: str = "low"
    risk_factors: List[RiskFactor] = field(default_factory=list)
    requires_approval: bool = False
    suggested_strategy: ApprovalStrategy = ApprovalStrategy.AUTO_EXECUTE
    suggested_priority: ApprovalPriority = ApprovalPriority.LOW
    suggested_approvers: List[str] = field(default_factory=list)
    resource_sensitivity: ResourceSensitivity = ResourceSensitivity.NORMAL
    assessment_time: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "operation_id": self.operation_id,
            "operation_type": self.operation_type,
            "operation_category": self.operation_category.value if self.operation_category else None,
            "risk_score": round(self.risk_score, 2),
            "risk_level": self.risk_level,
            "risk_factors": [
                {"name": f.name, "weight": f.weight, "score": f.score, "description": f.description}
                for f in self.risk_factors
            ],
            "requires_approval": self.requires_approval,
            "suggested_strategy": self.suggested_strategy.value,
            "suggested_priority": self.suggested_priority.value,
            "suggested_approvers": self.suggested_approvers,
            "resource_sensitivity": self.resource_sensitivity.value,
            "assessment_time": self.assessment_time,
        }


class RiskScorer:
    """风险评分算法"""

    OPERATION_BASE_SCORES = {
        OperationCategory.T_TYPE: 0.6,
        OperationCategory.C_TYPE: 0.5,
        OperationCategory.M_TYPE: 0.4,
        OperationCategory.D_TYPE: 0.3,
        OperationCategory.B_TYPE: 0.2,
    }

    SENSITIVITY_MULTIPLIERS = {
        ResourceSensitivity.NORMAL: 1.0,
        ResourceSensitivity.CONFIDENTIAL: 1.5,
        ResourceSensitivity.CORE: 2.0,
    }

    ROLE_RISK_FACTORS = {
        AgentRole.ENGINEER: {"error_rate_weight": 1.0, "base_trust": 0.8},
        AgentRole.ANALYST: {"error_rate_weight": 1.2, "base_trust": 0.7},
        AgentRole.OPERATOR: {"error_rate_weight": 1.5, "base_trust": 0.6},
    }

    def __init__(self):
        self._error_rates: Dict[str, float] = {}
        self._error_count: Dict[str, int] = {}
        self._total_operations: Dict[str, int] = {}

    def set_error_rate(self, user_or_agent_id: str, error_rate: float) -> None:
        self._error_rates[user_or_agent_id] = min(error_rate, 1.0)

    def record_error(self, user_or_agent_id: str) -> None:
        self._error_count[user_or_agent_id] = self._error_count.get(user_or_agent_id, 0) + 1

    def record_operation(self, user_or_agent_id: str) -> None:
        self._total_operations[user_or_agent_id] = self._total_operations.get(user_or_agent_id, 0) + 1

    def get_error_rate(self, user_or_agent_id: str) -> float:
        if user_or_agent_id in self._error_rates:
            return self._error_rates[user_or_agent_id]
        total = self._total_operations.get(user_or_agent_id, 0)
        if total == 0:
            return 0.0
        errors = self._error_count.get(user_or_agent_id, 0)
        return errors / total

    def compute_risk_score(
        self,
        operation_category: OperationCategory,
        sensitivity: ResourceSensitivity = ResourceSensitivity.NORMAL,
        agent_role: AgentRole = AgentRole.ENGINEER,
        error_rate: Optional[float] = None,
        budget_amount: float = 0.0,
        budget_threshold: float = 1000.0,
        additional_factors: Optional[List[RiskFactor]] = None,
    ) -> float:
        base_score = self.OPERATION_BASE_SCORES.get(operation_category, 0.2)
        sensitivity_mult = self.SENSITIVITY_MULTIPLIERS.get(sensitivity, 1.0)

        if error_rate is None:
            error_rate = 0.0
        error_factor = 1.0 + (error_rate * 2.0)

        budget_factor = 1.0
        if budget_threshold > 0 and budget_amount > 0:
            budget_ratio = budget_amount / budget_threshold
            if budget_ratio > 1.0:
                budget_factor = 1.0 + (budget_ratio - 1.0) * 0.5
            elif budget_ratio > 0.8:
                budget_factor = 1.0 + budget_ratio * 0.2

        role_info = self.ROLE_RISK_FACTORS.get(agent_role, {"error_rate_weight": 1.0, "base_trust": 0.8})
        role_factor = 2.0 - role_info["base_trust"]

        score = base_score * sensitivity_mult * error_factor * budget_factor * role_factor
        score = min(score, 1.0)

        if additional_factors:
            for factor in additional_factors:
                score += factor.weight * factor.score
            score = min(score, 1.0)

        return round(score, 4)


class HighRiskOperationIdentifier:
    """高风险操作识别器"""

    T_TYPE_OPERATIONS = {
        "machine_param_dispatch",
        "cnc_program_download",
        "process_parameter_apply",
        "machine_execute",
        "production_start",
    }

    C_TYPE_OPERATIONS = {
        "system_config_modify",
        "api_key_manage",
        "permission_change",
        "security_policy_update",
        "user_management",
    }

    M_TYPE_OPERATIONS = {
        "model_train",
        "model_overwrite",
        "model_deploy",
        "model_delete",
        "model_export",
    }

    D_TYPE_OPERATIONS = {
        "historical_data_access",
        "sensitive_data_export",
        "process_data_download",
        "customer_data_access",
    }

    B_TYPE_OPERATIONS = {
        "budget_exceed",
        "resource_request_high",
        "cost_anomaly",
    }

    def __init__(self, risk_scorer: Optional[RiskScorer] = None):
        self._risk_scorer = risk_scorer or RiskScorer()
        self._budget_threshold = 1000.0
        self._sensitive_data_patterns: List[str] = []

    def set_budget_threshold(self, threshold: float) -> None:
        self._budget_threshold = threshold

    def identify_operation_category(self, operation_type: str) -> Optional[OperationCategory]:
        if operation_type in self.T_TYPE_OPERATIONS:
            return OperationCategory.T_TYPE
        if operation_type in self.C_TYPE_OPERATIONS:
            return OperationCategory.C_TYPE
        if operation_type in self.M_TYPE_OPERATIONS:
            return OperationCategory.M_TYPE
        if operation_type in self.D_TYPE_OPERATIONS:
            return OperationCategory.D_TYPE
        if operation_type in self.B_TYPE_OPERATIONS:
            return OperationCategory.B_TYPE

        if "machine" in operation_type or "dispatch" in operation_type or "execute" in operation_type:
            return OperationCategory.T_TYPE
        if "config" in operation_type or "setting" in operation_type or "permission" in operation_type:
            return OperationCategory.C_TYPE
        if "model" in operation_type or "train" in operation_type or "deploy" in operation_type:
            return OperationCategory.M_TYPE
        if "data" in operation_type or "access" in operation_type or "export" in operation_type:
            return OperationCategory.D_TYPE
        if "budget" in operation_type or "cost" in operation_type:
            return OperationCategory.B_TYPE

        return None

    def assess_risk(
        self,
        operation_id: str,
        operation_type: str,
        context: Dict[str, Any],
        requester_role: AgentRole = AgentRole.ENGINEER,
        budget_amount: float = 0.0,
    ) -> RiskAssessment:
        category = self.identify_operation_category(operation_type)
        if category is None:
            category = OperationCategory.D_TYPE

        sensitivity = self._determine_sensitivity(context, category)
        error_rate = self._risk_scorer.get_error_rate(context.get("requester_id", ""))

        risk_factors = []

        factor_op_type = RiskFactor(
            name="operation_type",
            weight=0.3,
            score=self._risk_scorer.OPERATION_BASE_SCORES.get(category, 0.2),
            description=f"Operation category: {category.value}",
        )
        risk_factors.append(factor_op_type)

        factor_sensitivity = RiskFactor(
            name="resource_sensitivity",
            weight=0.25,
            score=self._risk_scorer.SENSITIVITY_MULTIPLIERS.get(sensitivity, 1.0) / 2.0,
            description=f"Resource sensitivity: {sensitivity.value}",
        )
        risk_factors.append(factor_sensitivity)

        factor_error = RiskFactor(
            name="error_history",
            weight=0.2,
            score=error_rate,
            description=f"Historical error rate: {error_rate:.2%}",
        )
        risk_factors.append(factor_error)

        if budget_amount > 0:
            budget_ratio = budget_amount / self._budget_threshold if self._budget_threshold > 0 else 0
            factor_budget = RiskFactor(
                name="budget_threshold",
                weight=0.15,
                score=min(budget_ratio, 1.0),
                description=f"Budget ratio: {budget_ratio:.2%}",
            )
            risk_factors.append(factor_budget)

        risk_score = self._risk_scorer.compute_risk_score(
            operation_category=category,
            sensitivity=sensitivity,
            agent_role=requester_role,
            error_rate=error_rate,
            budget_amount=budget_amount,
            budget_threshold=self._budget_threshold,
            additional_factors=risk_factors,
        )

        risk_level = self._classify_risk_level(risk_score)
        requires_approval, strategy, priority = self._determine_approval_strategy(
            category, sensitivity, risk_score
        )

        suggested_approvers = self._suggest_approvers(category, sensitivity, requester_role)

        assessment = RiskAssessment(
            operation_id=operation_id,
            operation_type=operation_type,
            operation_category=category,
            risk_score=risk_score,
            risk_level=risk_level,
            risk_factors=risk_factors,
            requires_approval=requires_approval,
            suggested_strategy=strategy,
            suggested_priority=priority,
            suggested_approvers=suggested_approvers,
            resource_sensitivity=sensitivity,
            assessment_time=time.time(),
        )

        logger.info(
            "Risk assessment: op=%s category=%s risk=%.2f level=%s requires_approval=%s",
            operation_id, category.value, risk_score, risk_level, requires_approval
        )
        return assessment

    def _determine_sensitivity(
        self,
        context: Dict[str, Any],
        category: OperationCategory,
    ) -> ResourceSensitivity:
        explicit_sensitivity = context.get("resource_sensitivity")
        if explicit_sensitivity:
            try:
                return ResourceSensitivity(explicit_sensitivity)
            except ValueError:
                pass

        if category == OperationCategory.T_TYPE:
            return ResourceSensitivity.CONFIDENTIAL
        if category == OperationCategory.C_TYPE:
            return ResourceSensitivity.CORE
        if category == OperationCategory.M_TYPE:
            return ResourceSensitivity.CONFIDENTIAL
        if category == OperationCategory.D_TYPE:
            data_type = context.get("data_type", "")
            if "historical" in data_type or "process" in data_type:
                return ResourceSensitivity.CONFIDENTIAL
            return ResourceSensitivity.NORMAL
        if category == OperationCategory.B_TYPE:
            return ResourceSensitivity.NORMAL

        return ResourceSensitivity.NORMAL

    def _classify_risk_level(self, risk_score: float) -> str:
        if risk_score >= 0.8:
            return "critical"
        if risk_score >= 0.6:
            return "high"
        if risk_score >= 0.4:
            return "medium"
        if risk_score >= 0.2:
            return "low"
        return "minimal"

    def _determine_approval_strategy(
        self,
        category: OperationCategory,
        sensitivity: ResourceSensitivity,
        risk_score: float,
    ) -> tuple[bool, ApprovalStrategy, ApprovalPriority]:
        if sensitivity == ResourceSensitivity.CORE or risk_score >= 0.8:
            return True, ApprovalStrategy.MULTI_APPROVAL, ApprovalPriority.CRITICAL
        if sensitivity == ResourceSensitivity.CONFIDENTIAL or risk_score >= 0.6:
            return True, ApprovalStrategy.APPROVE_BEFORE_EXECUTE, ApprovalPriority.HIGH
        if category == OperationCategory.T_TYPE:
            return True, ApprovalStrategy.APPROVE_BEFORE_EXECUTE, ApprovalPriority.HIGH
        if category == OperationCategory.C_TYPE:
            return True, ApprovalStrategy.APPROVE_BEFORE_EXECUTE, ApprovalPriority.HIGH
        if category == OperationCategory.M_TYPE:
            return True, ApprovalStrategy.EXECUTE_AFTER_RECORD, ApprovalPriority.MEDIUM
        if risk_score >= 0.4:
            return True, ApprovalStrategy.EXECUTE_AFTER_RECORD, ApprovalPriority.MEDIUM
        return False, ApprovalStrategy.AUTO_EXECUTE, ApprovalPriority.LOW

    def _suggest_approvers(
        self,
        category: OperationCategory,
        sensitivity: ResourceSensitivity,
        requester_role: AgentRole,
    ) -> List[str]:
        approvers = []

        if category == OperationCategory.T_TYPE:
            approvers.append("process_engineer")
        if category == OperationCategory.C_TYPE:
            approvers.append("security_officer")
            approvers.append("system_admin")
        if category == OperationCategory.M_TYPE:
            approvers.append("ml_engineer")
        if sensitivity == ResourceSensitivity.CORE:
            approvers.append("project_manager")
            approvers.append("quality_assurance")
        if sensitivity == ResourceSensitivity.CONFIDENTIAL:
            approvers.append("data_steward")

        if not approvers:
            approvers.append("default_approver")

        return approvers


_global_identifier: Optional[HighRiskOperationIdentifier] = None


def get_risk_identifier() -> HighRiskOperationIdentifier:
    global _global_identifier
    if _global_identifier is None:
        _global_identifier = HighRiskOperationIdentifier()
    return _global_identifier


def init_risk_identifier() -> HighRiskOperationIdentifier:
    global _global_identifier
    _global_identifier = HighRiskOperationIdentifier()
    return _global_identifier
