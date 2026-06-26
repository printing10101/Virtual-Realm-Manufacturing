"""
质量检验 API - 质量记录与异常管理。

提供质量检验记录的 CRUD、统计汇总、异常管理及演示数据填充功能。
"""

from __future__ import annotations

import uuid
from datetime import datetime, date
from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select, func, delete

from app.core.response import ErrorCode, error, success
from app.database.connection import get_sessionmaker
from app.database.models import Base, QualityRecord, QualityAnomaly
from app.auth.permissions import require_role

class QualityRecordCreate(BaseModel):
    batch_no: str
    inspection_type: str
    result: str
    inspector: str
    notes: Optional[str] = None


class QualityAnomalyCreate(BaseModel):
    record_id: str
    anomaly_type: str
    description: Optional[str] = None
    severity: str


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

router = APIRouter(prefix="/api/v1/quality", tags=["Quality"])


@router.get("/")
async def list_quality_records(
    inspection_type: Optional[str] = Query(None, description="检验类型"),
    result: Optional[str] = Query(None, description="检验结果"),
    date_from: Optional[str] = Query(None, description="起始日期 YYYY-MM-DD"),
    date_to: Optional[str] = Query(None, description="结束日期 YYYY-MM-DD"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """获取质量检验记录列表，支持按类型、结果、日期范围筛选。"""
    sessionmaker = get_sessionmaker()
    if not sessionmaker:
        return error(code=ErrorCode.SERVICE_UNAVAILABLE, message="数据库未配置")

    async with sessionmaker() as session:
        stmt = select(QualityRecord).order_by(QualityRecord.created_at.desc())
        if inspection_type:
            stmt = stmt.where(QualityRecord.inspection_type == inspection_type)
        if result:
            stmt = stmt.where(QualityRecord.result == result)
        if date_from:
            try:
                dt_from = datetime.strptime(date_from, "%Y-%m-%d")
                stmt = stmt.where(QualityRecord.created_at >= dt_from)
            except ValueError:
                return error(
                    code=ErrorCode.INVALID_PARAMETER,
                    message=f"日期格式错误: date_from 应为 YYYY-MM-DD，收到 '{date_from}'"
                )
        if date_to:
            try:
                dt_to = datetime.strptime(date_to, "%Y-%m-%d").replace(hour=23, minute=59, second=59)
                stmt = stmt.where(QualityRecord.created_at <= dt_to)
            except ValueError:
                return error(
                    code=ErrorCode.INVALID_PARAMETER,
                    message=f"日期格式错误: date_to 应为 YYYY-MM-DD，收到 '{date_to}'"
                )

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


@router.post("/")
async def create_quality_record(body: QualityRecordCreate):
    """创建质量检验记录。"""
    sessionmaker = get_sessionmaker()
    if not sessionmaker:
        return error(code=ErrorCode.SERVICE_UNAVAILABLE, message="数据库未配置")

    today = date.today().strftime("%Y%m%d")
    async with sessionmaker() as session:
        # 生成检验编号 - 使用微秒时间戳避免并发冲突
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S%f")
        inspection_no = f"QC-{timestamp}"

        record = QualityRecord(
            inspection_no=inspection_no,
            batch_no=body.batch_no,
            inspection_type=body.inspection_type,
            result=body.result,
            inspector=body.inspector,
            notes=body.notes,
        )
        session.add(record)
        await session.flush()
        await session.commit()

    return success(data=record.to_dict(), message="质量记录创建成功")


@router.get("/stats/")
async def get_quality_stats():
    """获取质量统计：今日检验数、合格率、异常数、异常类型分布。"""
    sessionmaker = get_sessionmaker()
    if not sessionmaker:
        return error(code=ErrorCode.SERVICE_UNAVAILABLE, message="数据库未配置")

    async with sessionmaker() as session:
        today_start = datetime.combine(date.today(), datetime.min.time())

        # 今日检验数
        today_count_stmt = select(func.count()).select_from(QualityRecord).where(
            QualityRecord.created_at >= today_start
        )
        today_count = (await session.execute(today_count_stmt)).scalar() or 0

        # 合格率
        total_stmt = select(func.count()).select_from(QualityRecord)
        total = (await session.execute(total_stmt)).scalar() or 0
        pass_stmt = select(func.count()).select_from(QualityRecord).where(
            QualityRecord.result == "合格"
        )
        pass_count = (await session.execute(pass_stmt)).scalar() or 0
        pass_rate = round(pass_count / total * 100, 1) if total > 0 else 0.0

        # 异常数
        anomaly_count_stmt = select(func.count()).select_from(QualityAnomaly)
        anomaly_count = (await session.execute(anomaly_count_stmt)).scalar() or 0

        # 异常类型分布
        dist_stmt = (
            select(QualityAnomaly.anomaly_type, func.count().label("cnt"))
            .group_by(QualityAnomaly.anomaly_type)
        )
        dist_rows = (await session.execute(dist_stmt)).all()
        anomaly_distribution = {row.anomaly_type: row.cnt for row in dist_rows}

    return success(data={
        "today_count": today_count,
        "pass_rate": pass_rate,
        "anomaly_count": anomaly_count,
        "anomaly_distribution": anomaly_distribution,
    })


@router.get("/anomalies/")
async def list_anomalies(
    anomaly_type: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """获取质量异常列表。"""
    sessionmaker = get_sessionmaker()
    if not sessionmaker:
        return error(code=ErrorCode.SERVICE_UNAVAILABLE, message="数据库未配置")

    async with sessionmaker() as session:
        stmt = select(QualityAnomaly).order_by(QualityAnomaly.created_at.desc())
        if anomaly_type:
            stmt = stmt.where(QualityAnomaly.anomaly_type == anomaly_type)
        if status:
            stmt = stmt.where(QualityAnomaly.status == status)

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = (await session.execute(count_stmt)).scalar() or 0

        stmt = stmt.offset(offset).limit(limit)
        rows = (await session.execute(stmt)).scalars().all()

    return success(data={
        "anomalies": [a.to_dict() for a in rows],
        "total": total,
        "limit": limit,
        "offset": offset,
    })


@router.post("/seed", dependencies=[Depends(require_role("admin"))])
async def seed_quality_data():
    """填充质量检验演示数据。"""
    sessionmaker = get_sessionmaker()
    if not sessionmaker:
        return error(code=ErrorCode.SERVICE_UNAVAILABLE, message="数据库未配置")

    async with sessionmaker() as session:
        # 检查是否已有数据
        existing = (await session.execute(select(func.count()).select_from(QualityRecord))).scalar()
        if existing and existing > 0:
            return success(message="质量数据已存在，跳过填充")

        # 10 条质量记录
        records_data = [
            {"inspection_no": "QC-20260623-001", "batch_no": "B20260623-A01", "inspection_type": "进料检验", "result": "合格", "inspector": "张伟", "notes": "原材料检验合格"},
            {"inspection_no": "QC-20260623-002", "batch_no": "B20260623-A02", "inspection_type": "过程检验", "result": "合格", "inspector": "李明", "notes": "加工过程参数正常"},
            {"inspection_no": "QC-20260623-003", "batch_no": "B20260623-B01", "inspection_type": "成品检验", "result": "不合格", "inspector": "王芳", "notes": "表面粗糙度超标"},
            {"inspection_no": "QC-20260623-004", "batch_no": "B20260623-A03", "inspection_type": "进料检验", "result": "合格", "inspector": "张伟", "notes": "材料成分符合标准"},
            {"inspection_no": "QC-20260623-005", "batch_no": "B20260623-C01", "inspection_type": "过程检验", "result": "待判定", "inspector": "赵强", "notes": "需进一步检测"},
            {"inspection_no": "QC-20260623-006", "batch_no": "B20260623-B02", "inspection_type": "成品检验", "result": "合格", "inspector": "李明", "notes": "成品各项指标合格"},
            {"inspection_no": "QC-20260623-007", "batch_no": "B20260623-A04", "inspection_type": "进料检验", "result": "不合格", "inspector": "王芳", "notes": "材料硬度不达标"},
            {"inspection_no": "QC-20260623-008", "batch_no": "B20260623-D01", "inspection_type": "过程检验", "result": "合格", "inspector": "张伟", "notes": "加工精度满足要求"},
            {"inspection_no": "QC-20260623-009", "batch_no": "B20260623-C02", "inspection_type": "成品检验", "result": "合格", "inspector": "赵强", "notes": "成品外观及尺寸合格"},
            {"inspection_no": "QC-20260623-010", "batch_no": "B20260623-B03", "inspection_type": "过程检验", "result": "合格", "inspector": "李明", "notes": "工序参数稳定"},
        ]

        record_map = {}  # inspection_no -> id
        for rd in records_data:
            rec = QualityRecord(**rd)
            session.add(rec)
            await session.flush()
            record_map[rd["inspection_no"]] = rec.id

        # 8 条异常记录: 3 尺寸偏差, 2 表面缺陷, 2 材料问题, 1 其他
        anomalies_data = [
            {"record_id": record_map["QC-20260623-003"], "anomaly_type": "表面缺陷", "description": "成品表面粗糙度Ra值超标", "severity": "一般", "status": "处理中"},
            {"record_id": record_map["QC-20260623-005"], "anomaly_type": "尺寸偏差", "description": "轴径尺寸偏大0.02mm", "severity": "严重", "status": "待处理"},
            {"record_id": record_map["QC-20260623-007"], "anomaly_type": "材料问题", "description": "材料硬度低于标准值HRC58", "severity": "严重", "status": "待处理"},
            {"record_id": record_map["QC-20260623-003"], "anomaly_type": "尺寸偏差", "description": "孔径公差超出允许范围", "severity": "一般", "status": "已解决"},
            {"record_id": record_map["QC-20260623-005"], "anomaly_type": "尺寸偏差", "description": "长度方向尺寸偏差0.05mm", "severity": "一般", "status": "处理中"},
            {"record_id": record_map["QC-20260623-007"], "anomaly_type": "材料问题", "description": "材料成分中Cr含量偏低", "severity": "严重", "status": "待处理"},
            {"record_id": record_map["QC-20260623-003"], "anomaly_type": "表面缺陷", "description": "表面有明显划痕", "severity": "一般", "status": "已解决"},
            {"record_id": record_map["QC-20260623-005"], "anomaly_type": "其他", "description": "标签信息不完整", "severity": "轻微", "status": "已解决"},
        ]

        for ad in anomalies_data:
            session.add(QualityAnomaly(**ad))

        await session.commit()

    return success(message="质量演示数据填充成功", data={
        "records": len(records_data),
        "anomalies": len(anomalies_data),
    })
