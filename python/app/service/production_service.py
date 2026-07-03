"""生产报表 Service 层。

封装生产记录、工单管理及仪表盘的业务逻辑与数据库操作，供
``app.api.v1.production`` 路由调用。
所有函数返回原始数据（dict / None），不构造 HTTP 响应。
"""

from __future__ import annotations

import logging
import random
from datetime import date, timedelta
from typing import Optional

from sqlalchemy import select, func

from app.database.connection import get_sessionmaker
from app.database.models import ProductionRecord, WorkOrder, EquipmentAlarm

logger = logging.getLogger(__name__)


# 产线与班次常量（与原路由保持一致）
LINES = ["产线A", "产线B", "产线C", "产线D", "产线E"]
SHIFTS = ["早班", "中班", "晚班"]


def _get_session():
    """获取异步 sessionmaker，若数据库未配置则抛出 RuntimeError。"""
    sessionmaker = get_sessionmaker()
    if sessionmaker is None:
        raise RuntimeError("数据库未配置")
    return sessionmaker


async def get_dashboard() -> dict:
    """仪表盘 KPI：今日产量、良品率、OEE、活跃告警数。

    Returns:
        {"today_output": int, "today_planned": int, "yield_rate": float,
         "oee": float, "equipment_utilization": float, "active_alarms": int}
    """
    sessionmaker = _get_session()
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

        # 活跃告警数：查询真实未处理告警数量（替代原 random.randint 模拟值）
        try:
            alarm_stmt = select(func.count()).select_from(EquipmentAlarm).where(
                EquipmentAlarm.status == "未处理"
            )
            active_alarms = (await session.execute(alarm_stmt)).scalar() or 0
        except Exception as e:
            # 表不存在或查询失败时返回 0，避免随机数误导
            logger.warning("查询活跃告警数失败，降级为 0: %s", e, exc_info=True)
            active_alarms = 0

    return {
        "today_output": today_output,
        "today_planned": today_planned,
        "yield_rate": yield_rate,
        "oee": oee,
        "equipment_utilization": avg_util,
        "active_alarms": active_alarms,
    }


async def list_production_records(
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    line_name: Optional[str] = None,
    shift: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> dict:
    """获取生产记录列表，支持按日期范围、产线、班次筛选。

    Returns:
        {"records": [...], "total": int, "limit": int, "offset": int}
    """
    sessionmaker = _get_session()
    async with sessionmaker() as session:
        stmt = select(ProductionRecord).order_by(
            ProductionRecord.date.desc(), ProductionRecord.line_name
        )
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

    return {
        "records": [r.to_dict() for r in rows],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


async def list_work_orders(
    status: Optional[str] = None,
    priority: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> dict:
    """获取工单列表，支持按状态、优先级筛选。

    Returns:
        {"work_orders": [...], "total": int, "limit": int, "offset": int}
    """
    sessionmaker = _get_session()
    async with sessionmaker() as session:
        stmt = select(WorkOrder).order_by(WorkOrder.created_at.desc())
        if status:
            stmt = stmt.where(WorkOrder.status == status)
        if priority:
            stmt = stmt.where(WorkOrder.priority == priority)

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = (await session.execute(count_stmt)).scalar() or 0

        stmt = stmt.offset(offset).limit(limit)
        rows = (await session.execute(stmt)).scalars().all()

    return {
        "work_orders": [w.to_dict() for w in rows],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


async def get_work_order(wo_id: str) -> Optional[dict]:
    """获取单个工单详情。

    Returns:
        工单 dict；若未找到返回 None。
    """
    sessionmaker = _get_session()
    async with sessionmaker() as session:
        stmt = select(WorkOrder).where(WorkOrder.id == wo_id)
        row = (await session.execute(stmt)).scalar_one_or_none()

    if not row:
        return None
    return row.to_dict()


async def update_work_order(wo_id: str, update_data: dict) -> Optional[dict]:
    """更新工单信息。

    Args:
        wo_id: 工单 ID
        update_data: 待更新字段 dict（已 exclude_unset）

    Returns:
        更新后的工单 dict；若未找到返回 None。
    """
    sessionmaker = _get_session()
    async with sessionmaker() as session:
        stmt = select(WorkOrder).where(WorkOrder.id == wo_id)
        row = (await session.execute(stmt)).scalar_one_or_none()
        if not row:
            return None

        for key, value in update_data.items():
            setattr(row, key, value)

        await session.flush()
        await session.commit()

    return row.to_dict()


async def get_production_lines() -> dict:
    """获取产线列表及各班次数据。

    Returns:
        {"lines": [{"line_name": str, "shifts": {...}}, ...]}
    """
    sessionmaker = _get_session()
    today = date.today().isoformat()

    async with sessionmaker() as session:
        # 单次查询获取今天所有产线的记录，替代 N 次（LINES 长度）独立查询。
        # 将 N+1 查询模式降为 1 次查询 + 内存分组。
        stmt = select(ProductionRecord).where(
            ProductionRecord.date == today,
            ProductionRecord.line_name.in_(LINES),
        )
        all_rows = (await session.execute(stmt)).scalars().all()

    # 按产线名称分组
    rows_by_line: dict[str, list] = {}
    for r in all_rows:
        rows_by_line.setdefault(r.line_name, []).append(r)

    lines_data = []
    for line in LINES:
        rows = rows_by_line.get(line, [])
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

    return {"lines": lines_data}


async def get_monthly_summary() -> dict:
    """月度汇总 KPI。"""
    sessionmaker = _get_session()
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

    return {
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
    }


async def seed_production_data() -> dict:
    """填充生产演示数据：14天 x 5产线 x 3班次 + 8个工单。

    Returns:
        {"already_exists": bool, "record_count": int, "work_order_count": int}
    """
    sessionmaker = _get_session()
    async with sessionmaker() as session:
        existing = (await session.execute(select(func.count()).select_from(ProductionRecord))).scalar()
        if existing and existing > 0:
            return {"already_exists": True, "record_count": 0, "work_order_count": 0}

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

    return {
        "already_exists": False,
        "record_count": record_count,
        "work_order_count": len(work_orders_data),
    }
