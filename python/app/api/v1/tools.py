"""刀具库管理 API 路由。

提供刀具的 CRUD 操作、磨损跟踪、寿命预测集成和种子数据初始化。
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field
from sqlalchemy import select, func, or_

from app.core.response import success, error, ErrorCode
from app.database.connection import get_sessionmaker
from app.database.models.tool import Tool

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/tools", tags=["Tools"])


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------

class ToolCreate(BaseModel):
    code: str = Field(..., min_length=1, max_length=32, description="刀具编码 (T01, T02, ...)")
    name: str = Field(..., min_length=1, max_length=128, description="刀具名称")
    type: str = Field(
        ..., max_length=32,
        description="刀具类型: end_mill/ball_mill/drill/reamer/tap/insert/grooving/threading",
    )
    diameter: float = Field(..., gt=0, description="刀具直径 (mm)")
    length: Optional[float] = Field(None, gt=0, description="刀具长度 (mm)")
    flute_count: Optional[int] = Field(2, ge=1, description="刃数")
    material: Optional[str] = Field(None, max_length=32, description="刀具材料: carbide/hss/ceramic/cbn/diamond")
    coating: Optional[str] = Field(None, max_length=32, description="涂层类型: TiN/TiAlN/AlCrN/DLC/None")
    max_rpm: Optional[float] = Field(None, gt=0, description="最大允许转速 (RPM)")
    max_feed: Optional[float] = Field(None, gt=0, description="最大允许进给 (mm/min)")
    vendor: Optional[str] = Field(None, max_length=128, description="供应商")
    cost: Optional[float] = Field(None, ge=0, description="采购成本")
    notes: Optional[str] = Field(None, description="备注")


class ToolUpdate(BaseModel):
    code: Optional[str] = Field(None, max_length=32, description="刀具编码")
    name: Optional[str] = Field(None, max_length=128, description="刀具名称")
    type: Optional[str] = Field(None, max_length=32, description="刀具类型")
    diameter: Optional[float] = Field(None, gt=0, description="刀具直径 (mm)")
    length: Optional[float] = Field(None, gt=0, description="刀具长度 (mm)")
    flute_count: Optional[int] = Field(None, ge=1, description="刃数")
    material: Optional[str] = Field(None, max_length=32, description="刀具材料")
    coating: Optional[str] = Field(None, max_length=32, description="涂层类型")
    max_rpm: Optional[float] = Field(None, gt=0, description="最大允许转速 (RPM)")
    max_feed: Optional[float] = Field(None, gt=0, description="最大允许进给 (mm/min)")
    usage_time: Optional[float] = Field(None, ge=0, description="累计使用时间 (分钟)")
    wear_amount: Optional[float] = Field(None, ge=0, description="磨损量 (mm)")
    status: Optional[str] = Field(None, max_length=16, description="刀具状态: active/worn/broken/maintenance")
    vendor: Optional[str] = Field(None, max_length=128, description="供应商")
    cost: Optional[float] = Field(None, ge=0, description="采购成本")
    notes: Optional[str] = Field(None, description="备注")


class ToolWearUpdate(BaseModel):
    """刀具磨损更新请求。"""
    additional_usage_time: float = Field(0.0, ge=0, description="新增使用时间 (分钟)")
    additional_wear: float = Field(0.0, ge=0, description="新增磨损量 (mm)")
    sharpened: bool = Field(False, description="是否进行了刃磨")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _row_to_dict(t: Tool) -> dict:
    return {
        **t.to_dict(),
        "wear_percentage": t.wear_percentage,
        "is_worn": t.is_worn,
        "tool_life_remaining": t.tool_life_remaining,
    }


def _get_session():
    """获取异步 sessionmaker 工厂。"""
    sessionmaker = get_sessionmaker()
    if sessionmaker is None:
        raise RuntimeError("数据库未配置，请设置 DB_URL 环境变量")
    return sessionmaker


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/")
async def list_tools(
    type: Optional[str] = Query(None, description="按刀具类型筛选"),
    status: Optional[str] = Query(None, description="按状态筛选"),
    keyword: Optional[str] = Query(None, description="搜索名称或编码"),
):
    """获取刀具列表，支持类型、状态筛选和关键词搜索。"""
    sessionmaker = _get_session()
    async with sessionmaker() as session:
        stmt = select(Tool).order_by(Tool.code)
        if type:
            stmt = stmt.where(Tool.type == type)
        if status:
            stmt = stmt.where(Tool.status == status)
        if keyword:
            pattern = f"%{keyword}%"
            stmt = stmt.where(
                or_(
                    Tool.name.ilike(pattern),
                    Tool.code.ilike(pattern),
                )
            )
        result = await session.execute(stmt)
        tools = result.scalars().all()
        return success(data=[_row_to_dict(t) for t in tools])


@router.get("/stats/summary")
async def stats_summary():
    """获取刀具统计汇总：总数、磨损数、报废数、平均寿命剩余。"""
    sessionmaker = _get_session()
    async with sessionmaker() as session:
        total = await session.execute(select(func.count(Tool.id)))
        worn = await session.execute(
            select(func.count(Tool.id)).where(Tool.status == "worn")
        )
        broken = await session.execute(
            select(func.count(Tool.id)).where(Tool.status == "broken")
        )
        active = await session.execute(
            select(func.count(Tool.id)).where(Tool.status == "active")
        )
        return success(data={
            "total": total.scalar() or 0,
            "active": active.scalar() or 0,
            "worn": worn.scalar() or 0,
            "broken": broken.scalar() or 0,
        })


@router.get("/{tool_id}")
async def get_tool(tool_id: str):
    """根据 ID 获取单个刀具详情。"""
    sessionmaker = _get_session()
    async with sessionmaker() as session:
        result = await session.execute(
            select(Tool).where(Tool.id == tool_id)
        )
        t = result.scalar_one_or_none()
        if t is None:
            return error(ErrorCode.NOT_FOUND, message=f"刀具 {tool_id} 不存在")
        return success(data=_row_to_dict(t))


@router.post("/")
async def create_tool(body: ToolCreate):
    """创建新刀具。"""
    sessionmaker = _get_session()
    async with sessionmaker() as session:
        # 检查编码唯一性
        existing = await session.execute(
            select(Tool).where(Tool.code == body.code)
        )
        if existing.scalar_one_or_none() is not None:
            return error(
                ErrorCode.VALIDATION_ERROR,
                message=f"刀具编码 '{body.code}' 已存在",
            )

        t = Tool(
            code=body.code,
            name=body.name,
            type=body.type,
            diameter=body.diameter,
            length=body.length,
            flute_count=body.flute_count,
            material=body.material,
            coating=body.coating,
            max_rpm=body.max_rpm,
            max_feed=body.max_feed,
            vendor=body.vendor,
            cost=body.cost,
            notes=body.notes,
        )
        session.add(t)
        await session.flush()
        await session.commit()
        return success(data=_row_to_dict(t), message="刀具创建成功")


@router.put("/{tool_id}")
async def update_tool(tool_id: str, body: ToolUpdate):
    """更新刀具信息。"""
    sessionmaker = _get_session()
    async with sessionmaker() as session:
        result = await session.execute(
            select(Tool).where(Tool.id == tool_id)
        )
        t = result.scalar_one_or_none()
        if t is None:
            return error(ErrorCode.NOT_FOUND, message=f"刀具 {tool_id} 不存在")

        update_data = body.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(t, key, value)
        t.updated_at = datetime.now(timezone.utc)

        await session.flush()
        await session.commit()
        return success(data=_row_to_dict(t), message="刀具更新成功")


@router.delete("/{tool_id}")
async def delete_tool(tool_id: str):
    """删除刀具。"""
    sessionmaker = _get_session()
    async with sessionmaker() as session:
        result = await session.execute(
            select(Tool).where(Tool.id == tool_id)
        )
        t = result.scalar_one_or_none()
        if t is None:
            return error(ErrorCode.NOT_FOUND, message=f"刀具 {tool_id} 不存在")

        await session.delete(t)
        await session.commit()
        return success(message="刀具删除成功")


@router.post("/{tool_id}/wear")
async def update_tool_wear(tool_id: str, body: ToolWearUpdate):
    """更新刀具磨损信息。

    累加使用时间和磨损量，如果进行了刃磨则重置磨损量并记录刃磨时间。
    """
    sessionmaker = _get_session()
    async with sessionmaker() as session:
        result = await session.execute(
            select(Tool).where(Tool.id == tool_id)
        )
        t = result.scalar_one_or_none()
        if t is None:
            return error(ErrorCode.NOT_FOUND, message=f"刀具 {tool_id} 不存在")

        if body.sharpened:
            # 刃磨：重置磨损量，记录刃磨时间
            t.wear_amount = 0.0
            t.last_sharpened = datetime.now(timezone.utc)
            t.status = "active"
            logger.info("刀具 %s 已刃磨，磨损量重置为0", t.code)
        else:
            # 正常磨损累加
            t.usage_time += body.additional_usage_time
            t.wear_amount += body.additional_wear

            # 自动更新状态
            if t.wear_percentage > 80.0:
                t.status = "worn"
                logger.warning("刀具 %s 磨损超过80%%，状态更新为worn", t.code)

        t.updated_at = datetime.now(timezone.utc)
        await session.flush()
        await session.commit()
        return success(data=_row_to_dict(t), message="刀具磨损信息更新成功")


@router.get("/{tool_id}/life-prediction")
async def tool_life_prediction(tool_id: str):
    """获取刀具寿命预测信息。

    基于使用时间和磨损量估算剩余寿命。
    """
    sessionmaker = _get_session()
    async with sessionmaker() as session:
        result = await session.execute(
            select(Tool).where(Tool.id == tool_id)
        )
        t = result.scalar_one_or_none()
        if t is None:
            return error(ErrorCode.NOT_FOUND, message=f"刀具 {tool_id} 不存在")

        return success(data={
            "tool_id": tool_id,
            "tool_code": t.code,
            "tool_name": t.name,
            "status": t.status,
            "usage_time_min": t.usage_time,
            "wear_amount_mm": t.wear_amount,
            "wear_percentage": t.wear_percentage,
            "tool_life_remaining_pct": t.tool_life_remaining,
            "is_worn": t.is_worn,
            "last_sharpened": t.last_sharpened.isoformat() if t.last_sharpened else None,
            "recommendation": _get_recommendation(t),
        })


def _get_recommendation(t: Tool) -> str:
    """根据刀具状态给出使用建议。"""
    if t.status == "broken":
        return "刀具已报废，请立即更换"
    if t.wear_percentage > 90:
        return "刀具磨损严重，建议立即更换或刃磨"
    if t.wear_percentage > 70:
        return "刀具磨损较多，建议安排刃磨计划"
    if t.wear_percentage > 50:
        return "刀具磨损中等，可降低进给率延长寿命"
    if t.tool_life_remaining < 20:
        return "剩余寿命不足20%，建议准备替换刀具"
    return "刀具状态良好，可正常使用"


# ---------------------------------------------------------------------------
# Seed data
# ---------------------------------------------------------------------------

SEED_TOOLS = [
    {
        "code": "T01", "name": "D10立铣刀", "type": "end_mill",
        "diameter": 10.0, "length": 75.0, "flute_count": 4,
        "material": "carbide", "coating": "TiAlN",
        "max_rpm": 12000, "max_feed": 3000,
        "vendor": "山特维克", "cost": 280.0,
    },
    {
        "code": "T02", "name": "D6球头铣刀", "type": "ball_mill",
        "diameter": 6.0, "length": 60.0, "flute_count": 2,
        "material": "carbide", "coating": "AlCrN",
        "max_rpm": 15000, "max_feed": 2000,
        "vendor": "肯纳金属", "cost": 320.0,
    },
    {
        "code": "T03", "name": "D8.5钻头", "type": "drill",
        "diameter": 8.5, "length": 100.0, "flute_count": 2,
        "material": "hss", "coating": "TiN",
        "max_rpm": 5000, "max_feed": 500,
        "vendor": "OSG", "cost": 45.0,
    },
    {
        "code": "T04", "name": "D10铰刀", "type": "reamer",
        "diameter": 10.0, "length": 90.0, "flute_count": 6,
        "material": "hss", "coating": "TiN",
        "max_rpm": 3000, "max_feed": 200,
        "vendor": "OSG", "cost": 120.0,
    },
    {
        "code": "T05", "name": "M6丝锥", "type": "tap",
        "diameter": 6.0, "length": 70.0, "flute_count": 4,
        "material": "hss", "coating": "TiN",
        "max_rpm": 1500, "max_feed": 100,
        "vendor": "YAMAWA", "cost": 35.0,
    },
    {
        "code": "T06", "name": "D16立铣刀", "type": "end_mill",
        "diameter": 16.0, "length": 90.0, "flute_count": 4,
        "material": "carbide", "coating": "TiAlN",
        "max_rpm": 10000, "max_feed": 4000,
        "vendor": "山特维克", "cost": 420.0,
    },
    {
        "code": "T07", "name": "D4立铣刀", "type": "end_mill",
        "diameter": 4.0, "length": 50.0, "flute_count": 4,
        "material": "carbide", "coating": "DLC",
        "max_rpm": 20000, "max_feed": 1500,
        "vendor": "三菱综合材料", "cost": 180.0,
    },
    {
        "code": "T08", "name": "切槽刀 3mm", "type": "grooving",
        "diameter": 3.0, "length": 40.0, "flute_count": 1,
        "material": "carbide", "coating": None,
        "max_rpm": 3000, "max_feed": 100,
        "vendor": "伊斯卡", "cost": 150.0,
    },
]


@router.post("/seed")
async def seed_tools():
    """初始化种子数据（仅在刀具表为空时插入）。"""
    sessionmaker = _get_session()
    async with sessionmaker() as session:
        count_result = await session.execute(select(func.count(Tool.id)))
        existing_count = count_result.scalar() or 0
        if existing_count > 0:
            return success(message=f"刀具表已有 {existing_count} 条记录，跳过种子数据")

        for item in SEED_TOOLS:
            t = Tool(**item)
            session.add(t)
        await session.flush()
        await session.commit()

        logger.info("已插入 %d 条刀具种子数据", len(SEED_TOOLS))
        return success(message=f"成功插入 {len(SEED_TOOLS)} 条刀具种子数据")
