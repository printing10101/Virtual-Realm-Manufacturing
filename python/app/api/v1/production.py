"""
生产报表 API - 生产记录、工单管理及仪表盘。

提供生产记录查询、工单 CRUD、仪表盘 KPI、产线数据及演示数据填充功能。
"""

from __future__ import annotations

import uuid
import random
from datetime import datetime, date, timedelta
from typing import Optional

from fastapi import APIRouter, Query
from pydantic import BaseModel
from sqlalchemy import select, func, delete

from app.core.response import ErrorCode, error, success
from app.database.connection import get_sessionmaker
from app.database.models import Base, ProductionRecord, WorkOrder


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------

class WorkOrderUpdate(BaseModel):
    product_name: Optional[str] = None
    planned_qty: Optional[int] = None
    completed_qty: Optional[int] = None
    status: Optional[str] = None
    priority: Optional[str] = None
    start_date: Optional[str] = None
    due_date: Optional[str] = None


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

router = APIRouter(prefix="/api/v1/production", tags=["Production"])

LINES = ["产线A", "产线B", "产线C", "产线D", "产线E"]
SHIFTS = ["早班", "中班", "晚班"]


@router.get("/dashboard/")
async def get_dashboard():
    """仪表盘 KPI：今日产量、良品率、OEE、活跃告警数。"""
    sessionmaker = get_sessionmaker()
    if not sessionmaker:
        return error(code=ErrorCode.SERVICE_UNAVAILABLE, message="数据库未配置")

    today = date.today().isoformat()

    async with sessionmaker() as session:
        # 今日产量
        stmt_today = select(
            func.sum(ProductionRecord.actual_qty),
            func.sum(ProductionRecord.qualified_qty),
            func.sum(ProductionRecord.planned_qty),
            func.avg(ProductionRecord.equipment_utilization),
        ).where(ProductionRecord.date == today)
        row = (await session.execute(stmt_today)).one()

        today_output = int(row[0] or 0)
        today_qualified = int(row[1] or 0)
        today_planned = int(row[2] or 0)
        avg_util = round(float(row[3] or 0), 1)

        yield_rate = round(today_qualified / today_output * 100, 1) if today_output > 0 else 0.0
        oee = round(yield_rate * avg_util / 100, 1) if avg_util > 0 else 0.0

        # 活跃告警数（模拟）
        active_alarms = random.randint(2, 8)

    return success(data={
        "today_output": today_output,
        "today_planned": today_planned,
        "yield_rate": yield_rate,
        "oee": oee,
        "equipment_utilization": avg_util,
        "active_alarms": active_alarms,
    })


@router.get("/records/")
async def list_production_records(
    date_from: Optional[str] = Query(None, description="起始日期"),
    date_to: Optional[str] = Query(None, description="结束日期"),
    line_name: Optional[str] = Query(None, description="产线名称"),
    shift: Optional[str] = Query(None, description="班次"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    """获取生产记录列表，支持按日期范围、产线、班次筛选。"""
    sessionmaker = get_sessionmaker()
    if not sessionmaker:
        return error(code=ErrorCode.SERVICE_UNAVAILABLE, message="数据库未配置")

    async with sessionmaker() as session:
        stmt = select(ProductionRecord).order_by(ProductionRecord.date.desc(), ProductionRecord.line_name)
        if date_from:
            stmt = stmt.where(ProductionRecord.date >= date_from)
        if date_to:
            stmt = stmt.where(ProductionRecord.date <= date_to)
        if line_name:
            stmt = stmt.where(ProductionRecord.line_name == line_name)
        if shift:
            stmt = stmt.where(ProductionRecord.shift == shift)

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = (await session.execute(count_stmt)).scalar() or 0

        stmt = stmt.offset(offset).limit(limit)
        rows = (await session.execute(stmt)).scalars().all()

    return success(data={
        "records": [r.to_dict() for r in rows],
        "total": total,
        "limit": limit,
        "offset": offset,
    })


@router.get("/work-orders/")
async def list_work_orders(
    status: Optional[str] = Query(None),
    priority: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """获取工单列表，支持按状态、优先级筛选。"""
    sessionmaker = get_sessionmaker()
    if not sessionmaker:
        return error(code=ErrorCode.SERVICE_UNAVAILABLE, message="数据库未配置")

    async with sessionmaker() as session:
        stmt = select(WorkOrder).order_by(
            WorkOrder.created_at.desc()
        )
        if status:
            stmt = stmt.where(WorkOrder.status == status)
        if priority:
            stmt = stmt.where(WorkOrder.priority == priority)

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = (await session.execute(count_stmt)).scalar() or 0

        stmt = stmt.offset(offset).limit(limit)
        rows = (await session.execute(stmt)).scalars().all()

    return success(data={
        "work_orders": [w.to_dict() for w in rows],
        "total": total,
        "limit": limit,
        "offset": offset,
    })


@router.get("/work-orders/{wo_id}")
async def get_work_order(wo_id: str):
    """获取单个工单详情。"""
    sessionmaker = get_sessionmaker()
    if not sessionmaker:
        return error(code=ErrorCode.SERVICE_UNAVAILABLE, message="数据库未配置")

    async with sessionmaker() as session:
        stmt = select(WorkOrder).where(WorkOrder.id == wo_id)
        row = (await session.execute(stmt)).scalar_one_or_none()

    if not row:
        return error(code=ErrorCode.NOT_FOUND, message=f"工单 '{wo_id}' 未找到")
    return success(data=row.to_dict())


@router.put("/work-orders/{wo_id}")
async def update_work_order(wo_id: str, body: WorkOrderUpdate):
    """更新工单信息。"""
    sessionmaker = get_sessionmaker()
    if not sessionmaker:
        return error(code=ErrorCode.SERVICE_UNAVAILABLE, message="数据库未配置")

    async with sessionmaker() as session:
        stmt = select(WorkOrder).where(WorkOrder.id == wo_id)
        row = (await session.execute(stmt)).scalar_one_or_none()
        if not row:
            return error(code=ErrorCode.NOT_FOUND, message=f"工单 '{wo_id}' 未找到")

        update_data = body.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(row, key, value)

        await session.flush()
        await session.commit()

    return success(data=row.to_dict(), message="工单更新成功")


@router.get("/lines/")
async def get_production_lines():
    """获取产线列表及各班次数据。"""
    sessionmaker = get_sessionmaker()
    if not sessionmaker:
        return error(code=ErrorCode.SERVICE_UNAVAILABLE, message="数据库未配置")

    today = date.today().isoformat()

    async with sessionmaker() as session:
        lines_data = []
        for line in LINES:
            stmt = select(ProductionRecord).where(
                ProductionRecord.date == today,
                ProductionRecord.line_name == line,
            )
            rows = (await session.execute(stmt)).scalars().all()

            shifts = {}
            for r in rows:
                shifts[r.shift] = {
                    "planned_qty": r.planned_qty,
                    "actual_qty": r.actual_qty,
                    "qualified_qty": r.qualified_qty,
                    "defect_qty": r.defect_qty,
                    "equipment_utilization": r.equipment_utilization,
                    "energy_consumption": r.energy_consumption,
                }

            lines_data.append({
                "line_name": line,
                "shifts": shifts,
            })

    return success(data={"lines": lines_data})


@router.get("/stats/summary")
async def get_monthly_summary():
    """月度汇总 KPI。"""
    sessionmaker = get_sessionmaker()
    if not sessionmaker:
        return error(code=ErrorCode.SERVICE_UNAVAILABLE, message="数据库未配置")

    today = date.today()
    month_start = today.replace(day=1).isoformat()

    async with sessionmaker() as session:
        stmt = select(
            func.sum(ProductionRecord.actual_qty),
            func.sum(ProductionRecord.qualified_qty),
            func.sum(ProductionRecord.planned_qty),
            func.sum(ProductionRecord.defect_qty),
            func.avg(ProductionRecord.equipment_utilization),
            func.sum(ProductionRecord.energy_consumption),
            func.count(ProductionRecord.id),
        ).where(ProductionRecord.date >= month_start)
        row = (await session.execute(stmt)).one()

        total_output = int(row[0] or 0)
        total_qualified = int(row[1] or 0)
        total_planned = int(row[2] or 0)
        total_defect = int(row[3] or 0)
        avg_util = round(float(row[4] or 0), 1)
        total_energy = round(float(row[5] or 0), 1)
        record_count = int(row[6] or 0)

        yield_rate = round(total_qualified / total_output * 100, 1) if total_output > 0 else 0.0
        completion_rate = round(total_output / total_planned * 100, 1) if total_planned > 0 else 0.0

    return success(data={
        "month": today.strftime("%Y-%m"),
        "total_output": total_output,
        "total_planned": total_planned,
        "total_qualified": total_qualified,
        "total_defect": total_defect,
        "yield_rate": yield_rate,
        "completion_rate": completion_rate,
        "avg_equipment_utilization": avg_util,
        "total_energy_consumption": total_energy,
        "record_count": record_count,
    })


@router.post("/seed")
async def seed_production_data():
    """填充生产演示数据：14天 x 5产线 x 3班次 + 8个工单。"""
    sessionmaker = get_sessionmaker()
    if not sessionmaker:
        return error(code=ErrorCode.SERVICE_UNAVAILABLE, message="数据库未配置")

    async with sessionmaker() as session:
        existing = (await session.execute(select(func.count()).select_from(ProductionRecord))).scalar()
        if existing and existing > 0:
            return success(message="生产数据已存在，跳过填充")

        today = date.today()
        record_count = 0

        for day_offset in range(14):
            d = today - timedelta(days=day_offset)
            d_str = d.isoformat()

            for line in LINES:
                for shift in SHIFTS:
                    planned = random.randint(80, 120)
                    actual = random.randint(int(planned * 0.85), planned)
                    qualified = int(actual * random.uniform(0.92, 0.99))
                    defect = actual - qualified
                    util = round(random.uniform(75, 98), 1)
                    energy = round(random.uniform(200, 500), 1)

                    rec = ProductionRecord(
                        date=d_str,
                        line_name=line,
                        planned_qty=planned,
                        actual_qty=actual,
                        qualified_qty=qualified,
                        defect_qty=defect,
                        equipment_utilization=util,
                        energy_consumption=energy,
                        shift=shift,
                    )
                    session.add(rec)
                    record_count += 1

        # 8 个工单
        work_orders_data = [
            {"order_no": "WO-20260623-001", "product_name": "精密轴类零件-A型", "planned_qty": 500, "completed_qty": 320, "status": "进行中", "priority": "紧急", "start_date": "2026-06-20", "due_date": "2026-06-28"},
            {"order_no": "WO-20260623-002", "product_name": "齿轮组件-B型", "planned_qty": 300, "completed_qty": 300, "status": "已完成", "priority": "高", "start_date": "2026-06-15", "due_date": "2026-06-22"},
            {"order_no": "WO-20260623-003", "product_name": "箱体铸件-C型", "planned_qty": 100, "completed_qty": 45, "status": "进行中", "priority": "中", "start_date": "2026-06-21", "due_date": "2026-07-05"},
            {"order_no": "WO-20260623-004", "product_name": "模具核心-D型", "planned_qty": 50, "completed_qty": 0, "status": "待开始", "priority": "高", "start_date": "2026-06-25", "due_date": "2026-07-10"},
            {"order_no": "WO-20260623-005", "product_name": "焊接支架-E型", "planned_qty": 200, "completed_qty": 180, "status": "进行中", "priority": "中", "start_date": "2026-06-18", "due_date": "2026-06-26"},
            {"order_no": "WO-20260623-006", "product_name": "精密轴承座-F型", "planned_qty": 150, "completed_qty": 150, "status": "已完成", "priority": "低", "start_date": "2026-06-10", "due_date": "2026-06-20"},
            {"order_no": "WO-20260623-007", "product_name": "涡轮叶片-G型", "planned_qty": 80, "completed_qty": 20, "status": "已延期", "priority": "紧急", "start_date": "2026-06-12", "due_date": "2026-06-22"},
            {"order_no": "WO-20260623-008", "product_name": "液压缸体-H型", "planned_qty": 120, "completed_qty": 0, "status": "待开始", "priority": "中", "start_date": "2026-06-28", "due_date": "2026-07-15"},
        ]

        for wod in work_orders_data:
            session.add(WorkOrder(**wod))

        await session.commit()

    return success(message="生产演示数据填充成功", data={
        "production_records": record_count,
        "work_orders": len(work_orders_data),
    })
