"""
质量检验 API - 质量记录与异常管理。

提供质量检验记录的 CRUD、统计汇总、异常管理及演示数据填充功能。
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from app.core.response import ErrorCode, error, success
from app.service import quality_service
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
    # 日期解析保留在路由层：原实现在此处返回 ErrorCode.INVALID_PARAMETER，
    # 该枚举值为预存不一致（response.py 未定义），按"API 行为完全不变"约束保持原样。
    dt_from: Optional[datetime] = None
    dt_to: Optional[datetime] = None
    if date_from:
        try:
            dt_from = datetime.strptime(date_from, "%Y-%m-%d")
        except ValueError:
            return error(
                code=ErrorCode.INVALID_PARAMETER,
                message=f"日期格式错误: date_from 应为 YYYY-MM-DD，收到 '{date_from}'"
            )
    if date_to:
        try:
            dt_to = datetime.strptime(date_to, "%Y-%m-%d").replace(hour=23, minute=59, second=59)
        except ValueError:
            return error(
                code=ErrorCode.INVALID_PARAMETER,
                message=f"日期格式错误: date_to 应为 YYYY-MM-DD，收到 '{date_to}'"
            )

    try:
        data = await quality_service.list_quality_records(
            inspection_type=inspection_type,
            result=result,
            dt_from=dt_from,
            dt_to=dt_to,
            limit=limit,
            offset=offset,
        )
    except RuntimeError:
        return error(code=ErrorCode.SERVICE_UNAVAILABLE, message="数据库未配置")

    return success(data=data)


@router.post("/")
async def create_quality_record(body: QualityRecordCreate):
    """创建质量检验记录。"""
    try:
        data = await quality_service.create_quality_record(
            batch_no=body.batch_no,
            inspection_type=body.inspection_type,
            result=body.result,
            inspector=body.inspector,
            notes=body.notes,
        )
    except RuntimeError:
        return error(code=ErrorCode.SERVICE_UNAVAILABLE, message="数据库未配置")

    return success(data=data, message="质量记录创建成功")


@router.get("/stats/")
async def get_quality_stats():
    """获取质量统计：今日检验数、合格率、异常数、异常类型分布。"""
    try:
        data = await quality_service.get_quality_stats()
    except RuntimeError:
        return error(code=ErrorCode.SERVICE_UNAVAILABLE, message="数据库未配置")

    return success(data=data)


@router.get("/anomalies/")
async def list_anomalies(
    anomaly_type: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """获取质量异常列表。"""
    try:
        data = await quality_service.list_anomalies(
            anomaly_type=anomaly_type,
            status=status,
            limit=limit,
            offset=offset,
        )
    except RuntimeError:
        return error(code=ErrorCode.SERVICE_UNAVAILABLE, message="数据库未配置")

    return success(data=data)


@router.post("/seed", dependencies=[Depends(require_role("admin"))])
async def seed_quality_data():
    """填充质量检验演示数据。"""
    try:
        result = await quality_service.seed_quality_data()
    except RuntimeError:
        return error(code=ErrorCode.SERVICE_UNAVAILABLE, message="数据库未配置")

    if result["already_exists"]:
        return success(message="质量数据已存在，跳过填充")

    return success(message="质量演示数据填充成功", data={
        "records": result["records_count"],
        "anomalies": result["anomalies_count"],
    })
