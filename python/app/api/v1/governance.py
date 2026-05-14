"""
Governance & Approval Management API Routes

Endpoints for approval workflow, risk assessment, emergency override, and governance reports.
"""
from fastapi import APIRouter, Query, HTTPException
from typing import Optional
import time

from app.core.approval_workflow import (
    get_approval_engine,
    ApprovalWorkflowEngine,
)
from app.core.risk_identifier import (
    get_risk_identifier,
    HighRiskOperationIdentifier,
)
from app.models.governance import (
    ApprovalPolicy,
    ApprovalPriority,
    ApprovalRequest,
    ApprovalStatus,
    ApprovalStrategy,
    ApprovalMode,
    TaskType,
    AgentRole,
    ResourceSensitivity,
)

router = APIRouter(prefix="/api/v1/governance", tags=["Governance & Approval"])


@router.get("/approval-requests")
async def list_approval_requests(
    status: Optional[str] = Query(None, description="筛选状态: pending/under_review/approved/rejected/escalated"),
    requester: Optional[str] = Query(None, description="请求人"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    engine = get_approval_engine()

    if status:
        try:
            status_enum = ApprovalStatus(status)
            requests = engine.get_requests_by_status(status_enum, limit, offset)
        except ValueError:
            raise HTTPException(400, f"Invalid status: {status}")
    elif requester:
        requests = engine.get_requests_by_requester(requester, limit, offset)
    else:
        requests = engine.get_requests_by_status(ApprovalStatus.PENDING, limit, offset)

    return {"ok": True, "data": [r.to_dict() for r in requests]}


@router.get("/approval-requests/{request_id}")
async def get_approval_request(request_id: str):
    engine = get_approval_engine()
    request = engine.get_request(request_id)
    if request is None:
        raise HTTPException(404, f"Approval request not found: {request_id}")
    return {"ok": True, "data": request.to_dict()}


@router.post("/approval-requests")
async def create_approval_request(data: dict):
    engine = get_approval_engine()
    risk_identifier = get_risk_identifier()

    try:
        task_id = data["task_id"]
        requester = data["requester"]
        context = data.get("context", {})
        operation_type = context.get("operation_type", "unknown")
        budget_amount = float(data.get("budget_amount", 0))
        agent_role = AgentRole(data.get("agent_role", "engineer"))

        assessment = risk_identifier.assess_risk(
            operation_id=f"OP-{int(time.time())}",
            operation_type=operation_type,
            context=context,
            requester_role=agent_role,
            budget_amount=budget_amount,
        )

        priority = assessment.suggested_priority
        approvers = assessment.suggested_approvers
        required_approvals = 1
        expires_at = time.time() + 24 * 3600

        request = engine.create_approval_request(
            task_id=task_id,
            requester=requester,
            context={**context, "risk_assessment": assessment.to_dict()},
            priority=priority,
            approvers=approvers,
            required_approvals=required_approvals,
            risk_score=assessment.risk_score,
            risk_factors=[f.name for f in assessment.risk_factors],
            suggested_decision=assessment.suggested_strategy.value,
            expires_at=expires_at,
        )

        return {"ok": True, "data": request.to_dict(), "risk_assessment": assessment.to_dict()}
    except (ValueError, KeyError) as e:
        raise HTTPException(400, f"Invalid request data: {e}")


@router.post("/approval-requests/{request_id}/assign")
async def assign_approver(request_id: str, data: dict):
    engine = get_approval_engine()
    approver_id = data.get("approver_id")
    if not approver_id:
        raise HTTPException(400, "approver_id is required")

    request = engine.assign_approver(request_id, approver_id)
    if request is None:
        raise HTTPException(404, f"Approval request not found: {request_id}")
    return {"ok": True, "data": request.to_dict()}


@router.post("/approval-requests/{request_id}/decide")
async def make_decision(request_id: str, data: dict):
    engine = get_approval_engine()

    try:
        approver_id = data["approver_id"]
        decision = data["decision"]
        if decision not in ("approved", "rejected", "escalated", "request_info"):
            raise HTTPException(400, "Invalid decision. Must be: approved/rejected/escalated/request_info")

        comment = data.get("comment", "")
        request = engine.make_decision(request_id, approver_id, decision, comment)
        if request is None:
            raise HTTPException(404, f"Approval request not found: {request_id}")

        return {"ok": True, "data": request.to_dict()}
    except (ValueError, KeyError) as e:
        raise HTTPException(400, f"Invalid decision data: {e}")


@router.post("/approval-requests/{request_id}/escalate")
async def escalate_request(request_id: str, data: dict):
    engine = get_approval_engine()
    escalator_id = data.get("escalator_id", "system")
    reason = data.get("reason", "")

    request = engine.escalate_request(request_id, escalator_id, reason)
    if request is None:
        raise HTTPException(404, f"Approval request not found: {request_id}")
    return {"ok": True, "data": request.to_dict()}


@router.post("/approval-timeout-handler")
async def handle_approval_timeout():
    engine = get_approval_engine()
    handled_count = engine.handle_timeout()
    return {"ok": True, "data": {"handled_count": handled_count}}


@router.get("/approval-requests/my")
async def get_my_approval_requests(
    approver_id: str = Query(..., description="审批人ID"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    engine = get_approval_engine()
    requests = engine.get_requests_by_approver(approver_id, limit, offset)
    return {"ok": True, "data": [r.to_dict() for r in requests]}


@router.get("/approval-dashboard")
async def get_approval_dashboard():
    engine = get_approval_engine()

    pending = engine.get_requests_by_status(ApprovalStatus.PENDING, 100)
    under_review = engine.get_requests_by_status(ApprovalStatus.UNDER_REVIEW, 100)
    approved = engine.get_requests_by_status(ApprovalStatus.APPROVED, 50)
    rejected = engine.get_requests_by_status(ApprovalStatus.REJECTED, 50)

    return {
        "ok": True,
        "data": {
            "pending": [r.to_dict() for r in pending],
            "under_review": [r.to_dict() for r in under_review],
            "approved": [r.to_dict() for r in approved],
            "rejected": [r.to_dict() for r in rejected],
            "counts": {
                "pending": len(pending),
                "under_review": len(under_review),
                "approved": len(approved),
                "rejected": len(rejected),
            }
        }
    }


@router.post("/risk-assess")
async def assess_operation_risk(data: dict):
    risk_identifier = get_risk_identifier()

    try:
        operation_id = data.get("operation_id", f"OP-{int(time.time())}")
        operation_type = data["operation_type"]
        context = data.get("context", {})
        requester_role = AgentRole(data.get("requester_role", "engineer"))
        budget_amount = float(data.get("budget_amount", 0))

        assessment = risk_identifier.assess_risk(
            operation_id=operation_id,
            operation_type=operation_type,
            context=context,
            requester_role=requester_role,
            budget_amount=budget_amount,
        )

        return {"ok": True, "data": assessment.to_dict()}
    except (ValueError, KeyError) as e:
        raise HTTPException(400, f"Invalid assessment data: {e}")


@router.get("/risk-categories")
async def get_risk_categories():
    risk_identifier = get_risk_identifier()
    return {
        "ok": True,
        "data": {
            "T_TYPE": list(risk_identifier.T_TYPE_OPERATIONS),
            "C_TYPE": list(risk_identifier.C_TYPE_OPERATIONS),
            "M_TYPE": list(risk_identifier.M_TYPE_OPERATIONS),
            "D_TYPE": list(risk_identifier.D_TYPE_OPERATIONS),
            "B_TYPE": list(risk_identifier.B_TYPE_OPERATIONS),
        }
    }


@router.post("/emergency-override")
async def emergency_override(data: dict):
    engine = get_approval_engine()

    try:
        request_id = data["request_id"]
        task_id = data["task_id"]
        operator_id = data["operator_id"]
        reason = data["reason"]
        emergency_type = data.get("emergency_type", "production_halt")

        result = engine.record_emergency_operation(
            request_id=request_id,
            task_id=task_id,
            operator_id=operator_id,
            reason=reason,
            emergency_type=emergency_type,
        )

        return {"ok": True, "data": result}
    except (ValueError, KeyError) as e:
        raise HTTPException(400, f"Invalid emergency override data: {e}")


@router.post("/emergency-retroactive-approval")
async def complete_retroactive_approval(data: dict):
    engine = get_approval_engine()
    emergency_id = data.get("emergency_id")
    if not emergency_id:
        raise HTTPException(400, "emergency_id is required")

    success = engine.complete_retroactive_approval(emergency_id)
    if not success:
        raise HTTPException(404, f"Emergency operation not found: {emergency_id}")
    return {"ok": True, "message": "Retroactive approval completed"}


@router.get("/delegations")
async def get_delegations(user_id: str = Query(..., description="用户ID")):
    engine = get_approval_engine()
    active_delegation = engine.get_active_delegation(user_id)
    delegates_for = engine.get_delegates_for_user(user_id)

    return {
        "ok": True,
        "data": {
            "active_delegation": active_delegation.to_dict() if active_delegation else None,
            "delegates_for": delegates_for,
        }
    }


@router.post("/delegations")
async def create_delegation(data: dict):
    engine = get_approval_engine()

    try:
        delegator_id = data["delegator_id"]
        delegate_id = data["delegate_id"]
        start_time = float(data["start_time"])
        end_time = float(data["end_time"])
        reason = data.get("reason", "")

        delegation = engine.delegate_approval(
            delegator_id=delegator_id,
            delegate_id=delegate_id,
            start_time=start_time,
            end_time=end_time,
            reason=reason,
        )

        return {"ok": True, "data": delegation.to_dict()}
    except (ValueError, KeyError) as e:
        raise HTTPException(400, f"Invalid delegation data: {e}")


@router.get("/reports/governance")
async def get_governance_report(
    days: int = Query(30, ge=1, le=365, description="报告天数"),
):
    engine = get_approval_engine()
    now = time.time()
    period_start = now - days * 24 * 3600

    report = engine.generate_governance_report(period_start=period_start, period_end=now)
    return {"ok": True, "data": report.to_dict()}


@router.get("/audit-log/export")
async def export_audit_log(
    format: str = Query("json", description="导出格式: json/csv"),
    start_time: Optional[float] = Query(None, description="起始时间"),
    end_time: Optional[float] = Query(None, description="结束时间"),
):
    engine = get_approval_engine()

    try:
        log_data = engine.export_audit_log(start_time, end_time, format)
        return {"ok": True, "data": log_data, "format": format}
    except ValueError as e:
        raise HTTPException(400, str(e))
