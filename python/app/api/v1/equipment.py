"""
设备监控 API - Equipment monitoring, alarms, and maintenance plans.

Endpoints:
    - GET  /                      List all equipment (optional status filter)
    - GET  /{equipment_id}        Get single equipment with current metrics
    - PUT  /{equipment_id}        Update equipment (status, metrics)
    - GET  /alarms/               List all alarms (filter by equipment_id, status, severity)
    - PUT  /alarms/{alarm_id}/status  Update alarm status
    - GET  /maintenance/          List all maintenance plans
    - PUT  /maintenance/{plan_id} Update maintenance plan
    - GET  /stats/                Get equipment stats (total, running, standby, fault)
    - POST /seed                  Seed initial demo data
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, Query

from app.auth.permissions import require_permission, require_role
from app.core.response import ErrorCode, error, success
from app.service import equipment_service

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/equipment",
    tags=["Equipment"],
    dependencies=[Depends(require_permission("equipment:read"))],
)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("")
async def list_equipment(
    status: Optional[str] = Query(None, description="按状态过滤: 运行中/待机/维护中/故障"),
    page: int = Query(1, ge=1, description="页码（从 1 开始）"),
    page_size: int = Query(50, ge=1, le=500, description="每页条数（最大 500）"),
):
    """获取设备列表，可按状态过滤并分页。"""
    try:
        data = await equipment_service.list_equipment(
            status=status, page=page, page_size=page_size
        )
    except RuntimeError:
        return error(code=ErrorCode.SERVICE_UNAVAILABLE, message="数据库未配置")

    return success(data=data, message="设备列表获取成功")


@router.get("/stats/")
async def get_equipment_stats():
    """获取设备统计信息。"""
    try:
        data = await equipment_service.get_equipment_stats()
    except RuntimeError:
        return error(code=ErrorCode.SERVICE_UNAVAILABLE, message="数据库未配置")

    return success(data=data, message="设备统计获取成功")


@router.get("/{equipment_id}")
async def get_equipment(equipment_id: str):
    """获取单台设备详情及当前指标。"""
    try:
        data = await equipment_service.get_equipment(equipment_id)
    except RuntimeError:
        return error(code=ErrorCode.SERVICE_UNAVAILABLE, message="数据库未配置")

    if data is None:
        return error(code=ErrorCode.NOT_FOUND, message=f"设备 '{equipment_id}' 未找到")

    return success(data=data, message="设备详情获取成功")


@router.put("/{equipment_id}")
async def update_equipment(equipment_id: str, body: dict):
    """更新设备状态和指标。"""
    try:
        data = await equipment_service.update_equipment(equipment_id, body)
    except RuntimeError:
        return error(code=ErrorCode.SERVICE_UNAVAILABLE, message="数据库未配置")
    except ValueError as exc:
        return error(code=ErrorCode.INVALID_REQUEST, message=str(exc))

    if data is None:
        return error(code=ErrorCode.NOT_FOUND, message=f"设备 '{equipment_id}' 未找到")

    # data 自带更新后的字段；这里需要重新计算 updated 列表以保持原消息格式
    # （service 已返回完整 dict，但消息中的字段列表需另传，这里从 body 推导）
    allowed_fields = {"status", "temperature", "vibration", "rpm", "power"}
    updated = [k for k in body.keys() if k in allowed_fields]
    return success(data=data, message=f"设备已更新: {', '.join(updated)}")


# ---------------------------------------------------------------------------
# Alarm endpoints
# ---------------------------------------------------------------------------

@router.get("/alarms/")
async def list_alarms(
    equipment_id: Optional[str] = Query(None, description="按设备ID过滤"),
    status: Optional[str] = Query(None, description="按状态过滤: 未处理/已确认/已解决"),
    severity: Optional[str] = Query(None, description="按严重程度过滤: 紧急/警告/提示"),
    page: int = Query(1, ge=1, description="页码（从 1 开始）"),
    page_size: int = Query(50, ge=1, le=500, description="每页条数（最大 500）"),
):
    """获取告警列表，支持多条件过滤和分页。"""
    try:
        data = await equipment_service.list_alarms(
            equipment_id=equipment_id,
            status=status,
            severity=severity,
            page=page,
            page_size=page_size,
        )
    except RuntimeError:
        return error(code=ErrorCode.SERVICE_UNAVAILABLE, message="数据库未配置")

    return success(data=data, message="告警列表获取成功")


@router.put("/alarms/{alarm_id}/status")
async def update_alarm_status(alarm_id: str, body: dict):
    """更新告警状态。"""
    try:
        data = await equipment_service.update_alarm_status(alarm_id, body)
    except RuntimeError:
        return error(code=ErrorCode.SERVICE_UNAVAILABLE, message="数据库未配置")
    except ValueError as exc:
        return error(code=ErrorCode.INVALID_REQUEST, message=str(exc))

    if data is None:
        return error(code=ErrorCode.NOT_FOUND, message=f"告警 '{alarm_id}' 未找到")

    return success(data=data, message="告警状态已更新")


# ---------------------------------------------------------------------------
# Maintenance endpoints
# ---------------------------------------------------------------------------

@router.get("/maintenance/")
async def list_maintenance_plans(
    equipment_id: Optional[str] = Query(None, description="按设备ID过滤"),
    status: Optional[str] = Query(None, description="按状态过滤"),
    page: int = Query(1, ge=1, description="页码（从 1 开始）"),
    page_size: int = Query(50, ge=1, le=500, description="每页条数（最大 500）"),
):
    """获取维护计划列表，支持过滤和分页。"""
    try:
        data = await equipment_service.list_maintenance_plans(
            equipment_id=equipment_id,
            status=status,
            page=page,
            page_size=page_size,
        )
    except RuntimeError:
        return error(code=ErrorCode.SERVICE_UNAVAILABLE, message="数据库未配置")

    return success(data=data, message="维护计划列表获取成功")


@router.put("/maintenance/{plan_id}")
async def update_maintenance_plan(plan_id: str, body: dict):
    """更新维护计划。"""
    try:
        data = await equipment_service.update_maintenance_plan(plan_id, body)
    except RuntimeError:
        return error(code=ErrorCode.SERVICE_UNAVAILABLE, message="数据库未配置")
    except ValueError as exc:
        return error(code=ErrorCode.INVALID_REQUEST, message=str(exc))

    if data is None:
        return error(code=ErrorCode.NOT_FOUND, message=f"维护计划 '{plan_id}' 未找到")

    allowed_fields = {"title", "type", "frequency", "last_date", "next_date", "status"}
    updated = [k for k in body.keys() if k in allowed_fields]
    return success(data=data, message=f"维护计划已更新: {', '.join(updated)}")


# ---------------------------------------------------------------------------
# Seed endpoint
# ---------------------------------------------------------------------------

@router.post("/seed", dependencies=[Depends(require_role("admin"))])
async def seed_equipment_data():
    """初始化设备监控演示数据（6台设备、6条告警、6条维护计划）。"""
    try:
        result = await equipment_service.seed_equipment_data()
    except RuntimeError:
        return error(code=ErrorCode.SERVICE_UNAVAILABLE, message="数据库未配置")

    if result["already_exists"]:
        return success(message="演示数据已存在，跳过初始化")

    return success(
        data=result["counts"],
        message="设备监控演示数据初始化成功",
    )
