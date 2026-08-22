"""Cutting Experience 采集 API（P2-3）。

数据飞轮采集端点：
- POST /capture      单条采集（手工录入 / 现场实测）
- POST /batch        批量采集（MTConnect 管道落库）
- GET  /             分页查询（多条件筛选）
- GET  /stats        聚合统计（仪表盘）
- GET  /{id}         单条详情
- DELETE /{id}       删除（管理用途）

权限：
- 写操作 require_permission("experience:write")
- 读操作 require_permission("experience:read")
"""

from __future__ import annotations

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query

from app.auth.permissions import require_permission
from app.contracts.cutting_experience import (
    CuttingExperience,
    ExperienceQuery,
    MachiningResult,
    MachiningType,
)
from app.services.domain.cutting_experience_repository import (
    aggregate_experience_stats,
    create_cutting_experience,
    create_many_cutting_experiences,
    delete_cutting_experience,
    get_cutting_experience,
    list_cutting_experiences,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/experience", tags=["cutting-experience"])


@router.post("/capture", status_code=201)
async def capture_experience(
    payload: CuttingExperience,
    _: None = Depends(require_permission("experience:write")),
) -> dict:
    """单条切削实测采集。"""
    try:
        return await create_cutting_experience(payload)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/batch", status_code=201)
async def batch_capture_experiences(
    payloads: list[CuttingExperience],
    _: None = Depends(require_permission("experience:write")),
) -> dict:
    """批量采集（MTConnect 管道 / CSV 导入）。

    请求体为 CuttingExperience 数组，全部校验通过后一次性落库。
    """
    if len(payloads) > 1000:
        raise HTTPException(status_code=422, detail="单次批量上限 1000 条")
    try:
        count = await create_many_cutting_experiences(payloads)
        return {"inserted": count, "requested": len(payloads)}
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("")
async def query_experiences(
    machine_id: str | None = Query(default=None, max_length=64),
    tool_id: str | None = Query(default=None, max_length=64),
    material: str | None = Query(default=None, max_length=64),
    machining_type: MachiningType | None = Query(default=None),
    result: MachiningResult | None = Query(default=None),
    has_anomaly: bool | None = Query(default=None),
    start_time: str | None = Query(default=None, description="ISO8601 起始时间"),
    end_time: str | None = Query(default=None, description="ISO8601 结束时间"),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    _: None = Depends(require_permission("experience:read")),
) -> dict:
    """分页查询切削实测记录。"""
    from datetime import datetime

    def _parse_dt(value: str | None) -> object:
        if not value:
            return None
        try:
            return datetime.fromisoformat(value)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=f"非法时间格式: {value}") from exc

    query = ExperienceQuery(
        machine_id=machine_id,
        tool_id=tool_id,
        material=material,
        machining_type=machining_type,
        result=result,
        has_anomaly=has_anomaly,
        start_time=_parse_dt(start_time),  # type: ignore[arg-type]
        end_time=_parse_dt(end_time),  # type: ignore[arg-type]
        limit=limit,
        offset=offset,
    )
    try:
        return await list_cutting_experiences(query)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/stats")
async def experience_stats(
    machine_id: str | None = Query(default=None, max_length=64),
    tool_id: str | None = Query(default=None, max_length=64),
    _: None = Depends(require_permission("experience:read")),
) -> dict:
    """聚合统计（节拍/粗糙度/磨损均值、合格率、异常率）。"""
    query = ExperienceQuery(machine_id=machine_id, tool_id=tool_id, limit=1)
    try:
        stats = await aggregate_experience_stats(query)
        return stats.model_dump()
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/{record_id}")
async def experience_detail(
    record_id: UUID,
    _: None = Depends(require_permission("experience:read")),
) -> dict:
    """单条详情。"""
    try:
        record = await get_cutting_experience(record_id)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    if record is None:
        raise HTTPException(status_code=404, detail=f"记录不存在: {record_id}")
    return record


@router.delete("/{record_id}")
async def remove_experience(
    record_id: UUID,
    _: None = Depends(require_permission("experience:write")),
) -> dict:
    """删除记录（管理用途）。"""
    try:
        deleted = await delete_cutting_experience(record_id)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    if not deleted:
        raise HTTPException(status_code=404, detail=f"记录不存在: {record_id}")
    return {"deleted": True, "id": str(record_id)}
