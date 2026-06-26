"""
Cost & Budget Management API Routes

Endpoints for cost tracking, budget enforcement, alerts, and optimization suggestions.
"""

from fastapi import APIRouter, Query, HTTPException
from typing import Optional

from app.budget.budget_enforcer import (
    get_budget_enforcer,
    get_cost_optimizer,
)
from app.budget.cost_tracker import (
    get_cost_tracker,
    CostDimension,
)
from app.models.budget import (
    BudgetLevel,
    BudgetPeriod,
    ResourceType,
    BudgetPolicy,
)

router = APIRouter(prefix="/api/v1/cost-budget", tags=["Cost & Budget"])


@router.get("/summary")
async def get_cost_summary(
    dimension: str = Query(
        "agent", description="汇总维度: agent/project/goal/task/provider/model"
    ),
    scope_id: str = Query("", description="范围ID"),
    start_time: Optional[float] = Query(None, description="起始Unix时间戳"),
    end_time: Optional[float] = Query(None, description="结束Unix时间戳"),
):
    try:
        dim = CostDimension(dimension)
    except ValueError:
        raise HTTPException(400, f"Invalid dimension: {dimension}")

    tracker = get_cost_tracker()

    if scope_id:
        summary = tracker.get_cost_summary(dim, scope_id, start_time, end_time)
        return {"ok": True, "data": summary.to_dict()}
    else:
        summaries = tracker.get_all_summaries(dim, start_time, end_time)
        return {"ok": True, "data": [s.to_dict() for s in summaries]}


@router.get("/task/{task_id}")
async def get_task_costs(task_id: str):
    tracker = get_cost_tracker()
    costs = tracker.get_task_costs(task_id)
    total = tracker.get_task_total_cost(task_id)
    return {
        "ok": True,
        "data": {
            "task_id": task_id,
            "total_cost": total,
            "events": costs,
        },
    }


@router.get("/trend")
async def get_cost_trend(
    days: int = Query(30, ge=1, le=365, description="查询天数"),
    interval_hours: int = Query(24, ge=1, le=168, description="数据间隔（小时）"),
):
    tracker = get_cost_tracker()
    trend = tracker.get_cost_trend(days, interval_hours)
    return {"ok": True, "data": trend}


@router.get("/unit-prices")
async def get_unit_prices():
    tracker = get_cost_tracker()
    return {"ok": True, "data": tracker.get_unit_prices()}


@router.post("/unit-prices")
async def set_unit_price(data: dict):
    key = data.get("key")
    value = data.get("value")

    if not key or value is None:
        raise HTTPException(400, "key and value are required")

    valid_keys = [
        "gpu_time_per_second",
        "gpu_memory_per_gb_second",
        "api_call_per_request",
        "data_transfer_per_mb",
    ]
    if key not in valid_keys:
        raise HTTPException(400, f"Invalid key. Must be one of: {valid_keys}")

    tracker = get_cost_tracker()
    tracker.set_unit_price(key, float(value))

    return {"ok": True, "data": tracker.get_unit_prices()}


@router.get("/policies")
async def get_budget_policies(
    level: Optional[str] = Query(None, description="预算层级"),
    scope_id: Optional[str] = Query(None, description="范围ID"),
):
    enforcer = get_budget_enforcer()

    query_level = BudgetLevel(level) if level else None
    policies = enforcer.get_all_policies(query_level, scope_id)

    return {"ok": True, "data": [p.to_dict() for p in policies]}


@router.post("/policies")
async def set_budget_policy(data: dict):
    enforcer = get_budget_enforcer()

    try:
        policy = BudgetPolicy(
            level=BudgetLevel(data.get("level", "global")),
            scope_id=data.get("scope_id", "default"),
            resource_type=ResourceType(data.get("resource_type", "total_cost")),
            limit=float(data.get("limit", 100.0)),
            period=BudgetPeriod(data.get("period", "daily")),
            warning_threshold=float(data.get("warning_threshold", 0.8)),
            hard_stop=bool(data.get("hard_stop", True)),
            auto_notify=bool(data.get("auto_notify", True)),
            enabled=bool(data.get("enabled", True)),
        )
    except (ValueError, KeyError):
        # 修复：参数验证失败时不应回显 e 给客户端（可能含键名/结构信息），
        # 仅返回通用提示，详细错误可由服务端日志分析。
        raise HTTPException(400, "Invalid policy data")

    enforcer.set_policy(policy)
    return {"ok": True, "data": policy.to_dict()}


@router.post("/adjust-budget")
async def adjust_budget(data: dict):
    enforcer = get_budget_enforcer()

    try:
        level = BudgetLevel(data["level"])
        scope_id = data.get("scope_id", "default")
        resource_type = ResourceType(data["resource_type"])
        new_limit = float(data["new_limit"])
        reason = data.get("reason", "")
        adjusted_by = data.get("adjusted_by", "admin")
    except (ValueError, KeyError):
        # 修复：不回显异常详情
        raise HTTPException(400, "Invalid adjustment data")

    updated = enforcer.adjust_budget(
        level, scope_id, resource_type, new_limit, reason, adjusted_by
    )
    return {"ok": True, "data": updated.to_dict() if updated else None}


@router.get("/adjustment-history")
async def get_adjustment_history(limit: int = Query(50, ge=1, le=200)):
    tracker = get_cost_tracker()
    history = tracker.get_budget_adjustments(limit)
    return {"ok": True, "data": history}


@router.post("/check")
async def check_budget(data: dict):
    enforcer = get_budget_enforcer()

    try:
        level = BudgetLevel(data.get("level", "global"))
        scope_id = data.get("scope_id", "default")
        resource_type = ResourceType(data.get("resource_type", "total_cost"))
        planned_usage = float(data.get("planned_usage", 0.0))
    except (ValueError, KeyError):
        # 修复：不回显异常详情
        raise HTTPException(400, "Invalid check data")

    result = enforcer.check_budget(level, scope_id, resource_type, planned_usage)
    return {"ok": True, "data": result.to_dict()}


@router.post("/check-cascade")
async def check_budget_cascade(data: dict):
    enforcer = get_budget_enforcer()

    agent_id = data.get("agent_id", "")
    project_id = data.get("project_id", "default")
    resource_type_str = data.get("resource_type", "total_cost")
    planned_usage = float(data.get("planned_usage", 0.0))

    try:
        resource_type = ResourceType(resource_type_str)
    except ValueError:
        raise HTTPException(400, f"Invalid resource_type: {resource_type_str}")

    result = enforcer.check_budget_cascade(
        agent_id, project_id, resource_type, planned_usage
    )
    return {"ok": True, "data": result.to_dict()}


@router.post("/enforce")
async def enforce_budget(data: dict):
    enforcer = get_budget_enforcer()

    try:
        level = BudgetLevel(data.get("level", "global"))
        scope_id = data.get("scope_id", "default")
        resource_type = ResourceType(data.get("resource_type", "total_cost"))
        planned_usage = float(data.get("planned_usage", 0.0))
    except (ValueError, KeyError):
        # 修复：不回显异常详情
        raise HTTPException(400, "Invalid enforce data")

    result = enforcer.enforce(level, scope_id, resource_type, planned_usage)
    return {
        "ok": True,
        "data": {
            "actions": [a.value for a in result.actions_taken],
            "passed": result.check_result.passed if result.check_result else False,
            "status": result.check_result.status.value
            if result.check_result
            else "unknown",
            "alerts": [a.to_dict() for a in result.alerts_generated],
        },
    }


@router.post("/reset")
async def reset_budget_period(data: dict):
    enforcer = get_budget_enforcer()

    try:
        level = BudgetLevel(data["level"])
        scope_id = data.get("scope_id", "default")
        resource_type = ResourceType(data["resource_type"])
    except (ValueError, KeyError):
        # 修复：不回显异常详情
        raise HTTPException(400, "Invalid reset data")

    enforcer.reset_period(level, scope_id, resource_type)
    return {
        "ok": True,
        "message": f"Reset completed: {level.value}/{scope_id}/{resource_type.value}",
    }


@router.get("/alerts")
async def get_budget_alerts(
    status: Optional[str] = Query(None, description="筛选状态: warning/exceeded"),
    unread_only: bool = Query(False, description="仅未读"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0, le=10000),
):
    enforcer = get_budget_enforcer()
    alerts = enforcer.get_alerts(status, unread_only, limit, offset)
    return {"ok": True, "data": alerts}


@router.post("/alerts/{alert_id}/read")
async def mark_alert_read(alert_id: int):
    enforcer = get_budget_enforcer()
    enforcer.mark_alert_read(alert_id)
    return {"ok": True, "message": "Alert marked as read"}


@router.post("/alerts/read-all")
async def mark_all_alerts_read():
    enforcer = get_budget_enforcer()
    enforcer.mark_all_alerts_read()
    return {"ok": True, "message": "All alerts marked as read"}


@router.delete("/alerts/{alert_id}")
async def delete_alert(alert_id: int):
    enforcer = get_budget_enforcer()
    enforcer.delete_alert(alert_id)
    return {"ok": True, "message": "Alert deleted"}


@router.get("/suggestions")
async def get_optimization_suggestions():
    optimizer = get_cost_optimizer()
    tracker = get_cost_tracker()
    optimizer.set_cost_tracker(tracker)

    suggestions = optimizer.generate_all_suggestions()
    return {"ok": True, "data": [s.to_dict() for s in suggestions]}


@router.get("/enforcement-log")
async def get_enforcement_log(limit: int = Query(100, ge=1, le=500)):
    enforcer = get_budget_enforcer()
    log_entries = enforcer.get_enforcement_log(limit)
    return {"ok": True, "data": log_entries}


@router.get("/reset-log")
async def get_reset_log(limit: int = Query(100, ge=1, le=500)):
    enforcer = get_budget_enforcer()
    log_entries = enforcer.get_reset_log(limit)
    return {"ok": True, "data": log_entries}
