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
import uuid
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Query
from sqlalchemy import select, func

from app.core.response import ErrorCode, error, success
from app.database.connection import get_engine, get_sessionmaker
from app.database.models import Base, Equipment, EquipmentAlarm, MaintenancePlan

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/equipment", tags=["Equipment"])


# ---------------------------------------------------------------------------
# Helper: ensure tables exist
# ---------------------------------------------------------------------------

async def _ensure_tables():
    """Create equipment-related tables if they don't exist."""
    engine = get_engine()
    if engine is None:
        return
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("")
async def list_equipment(
    status: Optional[str] = Query(None, description="按状态过滤: 运行中/待机/维护中/故障"),
):
    """获取设备列表，可按状态过滤。"""
    sessionmaker = get_sessionmaker()
    if sessionmaker is None:
        return error(code=ErrorCode.SERVICE_UNAVAILABLE, message="数据库未配置")

    await _ensure_tables()

    async with sessionmaker() as session:
        stmt = select(Equipment)
        if status:
            stmt = stmt.where(Equipment.status == status)
        stmt = stmt.order_by(Equipment.created_at)
        result = await session.execute(stmt)
        items = result.scalars().all()
        return success(data=[e.to_dict() for e in items], message="设备列表获取成功")


@router.get("/stats/")
async def get_equipment_stats():
    """获取设备统计信息。"""
    sessionmaker = get_sessionmaker()
    if sessionmaker is None:
        return error(code=ErrorCode.SERVICE_UNAVAILABLE, message="数据库未配置")

    await _ensure_tables()

    async with sessionmaker() as session:
        total_q = await session.execute(select(func.count(Equipment.id)))
        total = total_q.scalar() or 0

        running_q = await session.execute(
            select(func.count(Equipment.id)).where(Equipment.status == "运行中")
        )
        running = running_q.scalar() or 0

        standby_q = await session.execute(
            select(func.count(Equipment.id)).where(Equipment.status == "待机")
        )
        standby = standby_q.scalar() or 0

        maintenance_q = await session.execute(
            select(func.count(Equipment.id)).where(Equipment.status == "维护中")
        )
        maintenance = maintenance_q.scalar() or 0

        fault_q = await session.execute(
            select(func.count(Equipment.id)).where(Equipment.status == "故障")
        )
        fault = fault_q.scalar() or 0

        return success(
            data={
                "total": total,
                "running": running,
                "standby": standby,
                "maintenance": maintenance,
                "fault": fault,
            },
            message="设备统计获取成功",
        )


@router.get("/{equipment_id}")
async def get_equipment(equipment_id: str):
    """获取单台设备详情及当前指标。"""
    sessionmaker = get_sessionmaker()
    if sessionmaker is None:
        return error(code=ErrorCode.SERVICE_UNAVAILABLE, message="数据库未配置")

    async with sessionmaker() as session:
        result = await session.execute(
            select(Equipment).where(Equipment.id == equipment_id)
        )
        equip = result.scalar_one_or_none()
        if not equip:
            return error(code=ErrorCode.NOT_FOUND, message=f"设备 '{equipment_id}' 未找到")

        return success(data=equip.to_dict(), message="设备详情获取成功")


@router.put("/{equipment_id}")
async def update_equipment(equipment_id: str, body: dict):
    """更新设备状态和指标。"""
    sessionmaker = get_sessionmaker()
    if sessionmaker is None:
        return error(code=ErrorCode.SERVICE_UNAVAILABLE, message="数据库未配置")

    async with sessionmaker() as session:
        result = await session.execute(
            select(Equipment).where(Equipment.id == equipment_id)
        )
        equip = result.scalar_one_or_none()
        if not equip:
            return error(code=ErrorCode.NOT_FOUND, message=f"设备 '{equipment_id}' 未找到")

        allowed_fields = {"status", "temperature", "vibration", "rpm", "power"}
        updated = []
        for key, value in body.items():
            if key in allowed_fields:
                setattr(equip, key, value)
                updated.append(key)

        if not updated:
            return error(code=ErrorCode.INVALID_REQUEST, message="没有有效的更新字段")

        equip.updated_at = datetime.utcnow()
        await session.commit()

        return success(data=equip.to_dict(), message=f"设备已更新: {', '.join(updated)}")


# ---------------------------------------------------------------------------
# Alarm endpoints
# ---------------------------------------------------------------------------

@router.get("/alarms/")
async def list_alarms(
    equipment_id: Optional[str] = Query(None, description="按设备ID过滤"),
    status: Optional[str] = Query(None, description="按状态过滤: 未处理/已确认/已解决"),
    severity: Optional[str] = Query(None, description="按严重程度过滤: 紧急/警告/提示"),
):
    """获取告警列表，支持多条件过滤。"""
    sessionmaker = get_sessionmaker()
    if sessionmaker is None:
        return error(code=ErrorCode.SERVICE_UNAVAILABLE, message="数据库未配置")

    await _ensure_tables()

    async with sessionmaker() as session:
        stmt = select(EquipmentAlarm).order_by(EquipmentAlarm.created_at.desc())
        if equipment_id:
            stmt = stmt.where(EquipmentAlarm.equipment_id == equipment_id)
        if status:
            stmt = stmt.where(EquipmentAlarm.status == status)
        if severity:
            stmt = stmt.where(EquipmentAlarm.severity == severity)
        result = await session.execute(stmt)
        items = result.scalars().all()
        return success(data=[a.to_dict() for a in items], message="告警列表获取成功")


@router.put("/alarms/{alarm_id}/status")
async def update_alarm_status(alarm_id: str, body: dict):
    """更新告警状态。"""
    sessionmaker = get_sessionmaker()
    if sessionmaker is None:
        return error(code=ErrorCode.SERVICE_UNAVAILABLE, message="数据库未配置")

    async with sessionmaker() as session:
        result = await session.execute(
            select(EquipmentAlarm).where(EquipmentAlarm.id == alarm_id)
        )
        alarm = result.scalar_one_or_none()
        if not alarm:
            return error(code=ErrorCode.NOT_FOUND, message=f"告警 '{alarm_id}' 未找到")

        new_status = body.get("status")
        valid_statuses = ["未处理", "已确认", "已解决"]
        if not new_status or new_status not in valid_statuses:
            return error(
                code=ErrorCode.INVALID_REQUEST,
                message=f"无效状态，可选值: {valid_statuses}",
            )

        alarm.status = new_status
        await session.commit()

        return success(data=alarm.to_dict(), message="告警状态已更新")


# ---------------------------------------------------------------------------
# Maintenance endpoints
# ---------------------------------------------------------------------------

@router.get("/maintenance/")
async def list_maintenance_plans(
    equipment_id: Optional[str] = Query(None, description="按设备ID过滤"),
    status: Optional[str] = Query(None, description="按状态过滤"),
):
    """获取维护计划列表。"""
    sessionmaker = get_sessionmaker()
    if sessionmaker is None:
        return error(code=ErrorCode.SERVICE_UNAVAILABLE, message="数据库未配置")

    await _ensure_tables()

    async with sessionmaker() as session:
        stmt = select(MaintenancePlan).order_by(MaintenancePlan.created_at)
        if equipment_id:
            stmt = stmt.where(MaintenancePlan.equipment_id == equipment_id)
        if status:
            stmt = stmt.where(MaintenancePlan.status == status)
        result = await session.execute(stmt)
        items = result.scalars().all()
        return success(data=[p.to_dict() for p in items], message="维护计划列表获取成功")


@router.put("/maintenance/{plan_id}")
async def update_maintenance_plan(plan_id: str, body: dict):
    """更新维护计划。"""
    sessionmaker = get_sessionmaker()
    if sessionmaker is None:
        return error(code=ErrorCode.SERVICE_UNAVAILABLE, message="数据库未配置")

    async with sessionmaker() as session:
        result = await session.execute(
            select(MaintenancePlan).where(MaintenancePlan.id == plan_id)
        )
        plan = result.scalar_one_or_none()
        if not plan:
            return error(code=ErrorCode.NOT_FOUND, message=f"维护计划 '{plan_id}' 未找到")

        allowed_fields = {"title", "type", "frequency", "last_date", "next_date", "status"}
        updated = []
        for key, value in body.items():
            if key in allowed_fields:
                if key in ("last_date", "next_date") and isinstance(value, str):
                    value = datetime.fromisoformat(value)
                setattr(plan, key, value)
                updated.append(key)

        if not updated:
            return error(code=ErrorCode.INVALID_REQUEST, message="没有有效的更新字段")

        await session.commit()

        return success(data=plan.to_dict(), message=f"维护计划已更新: {', '.join(updated)}")


# ---------------------------------------------------------------------------
# Seed endpoint
# ---------------------------------------------------------------------------

@router.post("/seed")
async def seed_equipment_data():
    """初始化设备监控演示数据（6台设备、6条告警、6条维护计划）。"""
    sessionmaker = get_sessionmaker()
    if sessionmaker is None:
        return error(code=ErrorCode.SERVICE_UNAVAILABLE, message="数据库未配置")

    await _ensure_tables()

    now = datetime.utcnow()

    equipment_data = [
        {
            "id": str(uuid.uuid4()),
            "name": "CNC-001 五轴加工中心",
            "model": "DMG MORI DMU 50",
            "location": "A区-01号",
            "status": "运行中",
            "temperature": 45.2,
            "vibration": 0.12,
            "rpm": 12000.0,
            "power": 35.5,
        },
        {
            "id": str(uuid.uuid4()),
            "name": "CNC-002 三轴加工中心",
            "model": "FANUC α-D21MiB5",
            "location": "A区-02号",
            "status": "运行中",
            "temperature": 42.8,
            "vibration": 0.08,
            "rpm": 8000.0,
            "power": 28.3,
        },
        {
            "id": str(uuid.uuid4()),
            "name": "WEDM-001 线切割机",
            "model": "SODICK VZ300L",
            "location": "B区-01号",
            "status": "待机",
            "temperature": 25.1,
            "vibration": 0.02,
            "rpm": 0.0,
            "power": 2.1,
        },
        {
            "id": str(uuid.uuid4()),
            "name": "GRIND-001 数控磨床",
            "model": "STUDER S33",
            "location": "B区-02号",
            "status": "运行中",
            "temperature": 38.5,
            "vibration": 0.15,
            "rpm": 4500.0,
            "power": 22.7,
        },
        {
            "id": str(uuid.uuid4()),
            "name": "ROBOT-001 焊接机器人",
            "model": "FANUC R-2000iC",
            "location": "C区-01号",
            "status": "维护中",
            "temperature": 22.3,
            "vibration": 0.01,
            "rpm": 0.0,
            "power": 0.5,
        },
        {
            "id": str(uuid.uuid4()),
            "name": "CMM-001 三坐标测量机",
            "model": "ZEISS CONTURA",
            "location": "D区-01号",
            "status": "运行中",
            "temperature": 23.8,
            "vibration": 0.03,
            "rpm": 0.0,
            "power": 5.2,
        },
    ]

    async with sessionmaker() as session:
        # 检查是否已有数据
        existing = await session.execute(select(func.count(Equipment.id)))
        if existing.scalar() > 0:
            return success(message="演示数据已存在，跳过初始化")

        # 创建设备
        equip_map = {}
        for ed in equipment_data:
            equip = Equipment(**ed)
            session.add(equip)
            equip_map[ed["id"]] = equip
        await session.flush()

        # 创建告警
        alarm_data = [
            {
                "equipment_id": equipment_data[0]["id"],
                "alarm_type": "温度异常",
                "severity": "警告",
                "message": "CNC-001 主轴温度偏高 (45.2°C)，接近阈值上限",
                "status": "未处理",
            },
            {
                "equipment_id": equipment_data[3]["id"],
                "alarm_type": "振动异常",
                "severity": "警告",
                "message": "GRIND-001 振动值偏高 (0.15mm/s)，建议检查砂轮平衡",
                "status": "未处理",
            },
            {
                "equipment_id": equipment_data[4]["id"],
                "alarm_type": "维护提醒",
                "severity": "提示",
                "message": "ROBOT-001 焊接机器人已进入计划维护周期",
                "status": "已确认",
            },
            {
                "equipment_id": equipment_data[1]["id"],
                "alarm_type": "功率异常",
                "severity": "紧急",
                "message": "CNC-002 功率波动异常，瞬时峰值超过额定功率15%",
                "status": "未处理",
            },
            {
                "equipment_id": equipment_data[2]["id"],
                "alarm_type": "维护提醒",
                "severity": "提示",
                "message": "WEDM-001 线切割机电极丝寿命即将到期，建议更换",
                "status": "已解决",
            },
            {
                "equipment_id": equipment_data[5]["id"],
                "alarm_type": "温度异常",
                "severity": "警告",
                "message": "CMM-001 测量环境温度波动超出允许范围",
                "status": "未处理",
            },
        ]

        for ad in alarm_data:
            alarm = EquipmentAlarm(**ad)
            session.add(alarm)
        await session.flush()

        # 创建维护计划
        maintenance_data = [
            {
                "equipment_id": equipment_data[0]["id"],
                "title": "主轴润滑保养",
                "type": "定期保养",
                "frequency": "每周",
                "last_date": now - timedelta(days=3),
                "next_date": now + timedelta(days=4),
                "status": "待执行",
            },
            {
                "equipment_id": equipment_data[1]["id"],
                "title": "刀具磨损检查",
                "type": "预防性维护",
                "frequency": "每日",
                "last_date": now - timedelta(hours=8),
                "next_date": now + timedelta(hours=16),
                "status": "待执行",
            },
            {
                "equipment_id": equipment_data[2]["id"],
                "title": "电极丝更换",
                "type": "定期保养",
                "frequency": "每月",
                "last_date": now - timedelta(days=25),
                "next_date": now + timedelta(days=5),
                "status": "待执行",
            },
            {
                "equipment_id": equipment_data[3]["id"],
                "title": "砂轮修整与校准",
                "type": "定期保养",
                "frequency": "每季度",
                "last_date": now - timedelta(days=60),
                "next_date": now + timedelta(days=30),
                "status": "待执行",
            },
            {
                "equipment_id": equipment_data[4]["id"],
                "title": "机械臂关节润滑与校准",
                "type": "故障维修",
                "frequency": "每月",
                "last_date": now - timedelta(days=10),
                "next_date": now - timedelta(days=3),
                "status": "进行中",
            },
            {
                "equipment_id": equipment_data[5]["id"],
                "title": "测量探头校准",
                "type": "预防性维护",
                "frequency": "每周",
                "last_date": now - timedelta(days=6),
                "next_date": now + timedelta(days=1),
                "status": "待执行",
            },
        ]

        for md in maintenance_data:
            plan = MaintenancePlan(**md)
            session.add(plan)

        await session.commit()

        return success(
            data={
                "equipment_count": len(equipment_data),
                "alarm_count": len(alarm_data),
                "maintenance_count": len(maintenance_data),
            },
            message="设备监控演示数据初始化成功",
        )
