"""物料管理 API 路由。

提供制造物料的 CRUD 操作、统计汇总和种子数据初始化。
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
from app.database.models import Base, Material

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/materials", tags=["Materials"])


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------

class MaterialCreate(BaseModel):
    code: str = Field(..., min_length=1, max_length=64, description="物料编码")
    name: str = Field(..., min_length=1, max_length=128, description="名称")
    spec: str = Field("", max_length=256, description="规格")
    category: str = Field("原材料", max_length=32, description="分类: 原材料/半成品/成品")
    quantity: int = Field(0, ge=0, description="库存数量")
    safe_quantity: int = Field(0, ge=0, description="安全库存")
    status: str = Field("正常", max_length=16, description="状态: 正常/低库存/缺货")
    location: str = Field("", max_length=64, description="库位")
    unit: str = Field("", max_length=16, description="单位")
    supplier: str = Field("", max_length=128, description="供应商")


class MaterialUpdate(BaseModel):
    code: Optional[str] = Field(None, max_length=64, description="物料编码")
    name: Optional[str] = Field(None, max_length=128, description="名称")
    spec: Optional[str] = Field(None, max_length=256, description="规格")
    category: Optional[str] = Field(None, max_length=32, description="分类")
    quantity: Optional[int] = Field(None, ge=0, description="库存数量")
    safe_quantity: Optional[int] = Field(None, ge=0, description="安全库存")
    status: Optional[str] = Field(None, max_length=16, description="状态")
    location: Optional[str] = Field(None, max_length=64, description="库位")
    unit: Optional[str] = Field(None, max_length=16, description="单位")
    supplier: Optional[str] = Field(None, max_length=128, description="供应商")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _row_to_dict(m: Material) -> dict:
    return {
        "id": m.id,
        "code": m.code,
        "name": m.name,
        "spec": m.spec,
        "category": m.category,
        "quantity": m.quantity,
        "safe_quantity": m.safe_quantity,
        "status": m.status,
        "location": m.location,
        "unit": m.unit,
        "supplier": m.supplier,
        "created_at": m.created_at.isoformat() if m.created_at else None,
        "updated_at": m.updated_at.isoformat() if m.updated_at else None,
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
async def list_materials(
    category: Optional[str] = Query(None, description="按分类筛选"),
    status: Optional[str] = Query(None, description="按状态筛选"),
    keyword: Optional[str] = Query(None, description="搜索名称或编码"),
):
    """获取物料列表，支持分类、状态筛选和关键词搜索。"""
    sessionmaker = _get_session()
    async with sessionmaker() as session:
        stmt = select(Material).order_by(Material.code)
        if category:
            stmt = stmt.where(Material.category == category)
        if status:
            stmt = stmt.where(Material.status == status)
        if keyword:
            pattern = f"%{keyword}%"
            stmt = stmt.where(
                or_(
                    Material.name.ilike(pattern),
                    Material.code.ilike(pattern),
                )
            )
        result = await session.execute(stmt)
        materials = result.scalars().all()
        return success(data=[_row_to_dict(m) for m in materials])


@router.get("/stats/summary")
async def stats_summary():
    """获取物料统计汇总：总数、低库存数、缺货数。"""
    sessionmaker = _get_session()
    async with sessionmaker() as session:
        total = await session.execute(select(func.count(Material.id)))
        low_stock = await session.execute(
            select(func.count(Material.id)).where(Material.status == "低库存")
        )
        out_of_stock = await session.execute(
            select(func.count(Material.id)).where(Material.status == "缺货")
        )
        return success(data={
            "total": total.scalar() or 0,
            "low_stock": low_stock.scalar() or 0,
            "out_of_stock": out_of_stock.scalar() or 0,
        })


@router.get("/{material_id}")
async def get_material(material_id: str):
    """根据 ID 获取单个物料详情。"""
    sessionmaker = _get_session()
    async with sessionmaker() as session:
        result = await session.execute(
            select(Material).where(Material.id == material_id)
        )
        m = result.scalar_one_or_none()
        if m is None:
            return error(ErrorCode.NOT_FOUND, message=f"物料 {material_id} 不存在")
        return success(data=_row_to_dict(m))


@router.post("/")
async def create_material(body: MaterialCreate):
    """创建新物料。"""
    sessionmaker = _get_session()
    async with sessionmaker() as session:
        m = Material(
            code=body.code,
            name=body.name,
            spec=body.spec,
            category=body.category,
            quantity=body.quantity,
            safe_quantity=body.safe_quantity,
            status=body.status,
            location=body.location,
            unit=body.unit,
            supplier=body.supplier,
        )
        session.add(m)
        await session.flush()
        await session.commit()
        return success(data=_row_to_dict(m), message="物料创建成功")


@router.put("/{material_id}")
async def update_material(material_id: str, body: MaterialUpdate):
    """更新物料信息。"""
    sessionmaker = _get_session()
    async with sessionmaker() as session:
        result = await session.execute(
            select(Material).where(Material.id == material_id)
        )
        m = result.scalar_one_or_none()
        if m is None:
            return error(ErrorCode.NOT_FOUND, message=f"物料 {material_id} 不存在")

        update_data = body.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(m, key, value)
        m.updated_at = datetime.now(timezone.utc)

        await session.flush()
        await session.commit()
        return success(data=_row_to_dict(m), message="物料更新成功")


@router.delete("/{material_id}")
async def delete_material(material_id: str):
    """删除物料。"""
    sessionmaker = _get_session()
    async with sessionmaker() as session:
        result = await session.execute(
            select(Material).where(Material.id == material_id)
        )
        m = result.scalar_one_or_none()
        if m is None:
            return error(ErrorCode.NOT_FOUND, message=f"物料 {material_id} 不存在")

        await session.delete(m)
        await session.commit()
        return success(message="物料删除成功")


# ---------------------------------------------------------------------------
# Seed data
# ---------------------------------------------------------------------------

SEED_MATERIALS = [
    {
        "code": "MAT-001", "name": "45号钢", "spec": "φ50×200mm",
        "category": "原材料", "quantity": 1500, "safe_quantity": 200,
        "status": "正常", "location": "A-01-03", "unit": "根", "supplier": "宝钢集团",
    },
    {
        "code": "MAT-002", "name": "铝合金6061", "spec": "100×50×300mm",
        "category": "原材料", "quantity": 800, "safe_quantity": 300,
        "status": "正常", "location": "A-01-05", "unit": "根", "supplier": "忠旺集团",
    },
    {
        "code": "MAT-003", "name": "不锈钢304", "spec": "φ30×150mm",
        "category": "原材料", "quantity": 200, "safe_quantity": 150,
        "status": "低库存", "location": "A-02-01", "unit": "根", "supplier": "太钢集团",
    },
    {
        "code": "MAT-004", "name": "铜棒H59", "spec": "φ25×100mm",
        "category": "原材料", "quantity": 50, "safe_quantity": 100,
        "status": "缺货", "location": "A-02-03", "unit": "根", "supplier": "海亮股份",
    },
    {
        "code": "MAT-005", "name": "齿轮半成品", "spec": "GZ-50T",
        "category": "半成品", "quantity": 120, "safe_quantity": 50,
        "status": "正常", "location": "B-01-01", "unit": "件", "supplier": "自制",
    },
    {
        "code": "MAT-006", "name": "轴承座半成品", "spec": "ZC-30B",
        "category": "半成品", "quantity": 85, "safe_quantity": 30,
        "status": "正常", "location": "B-01-02", "unit": "件", "supplier": "自制",
    },
    {
        "code": "MAT-007", "name": "减速机总成", "spec": "JS-50W",
        "category": "成品", "quantity": 30, "safe_quantity": 20,
        "status": "正常", "location": "C-01-01", "unit": "台", "supplier": "自制",
    },
    {
        "code": "MAT-008", "name": "伺服电机", "spec": "SM-750W",
        "category": "成品", "quantity": 15, "safe_quantity": 10,
        "status": "低库存", "location": "C-01-02", "unit": "台", "supplier": "安川电机",
    },
    {
        "code": "MAT-009", "name": "数控刀具", "spec": "D10-200",
        "category": "原材料", "quantity": 45, "safe_quantity": 20,
        "status": "正常", "location": "A-03-01", "unit": "把", "supplier": "山特维克",
    },
    {
        "code": "MAT-010", "name": "润滑油", "spec": "HM-46",
        "category": "原材料", "quantity": 200, "safe_quantity": 50,
        "status": "正常", "location": "A-03-05", "unit": "升", "supplier": "壳牌",
    },
]


@router.post("/seed")
async def seed_materials():
    """初始化种子数据（仅在物料表为空时插入）。"""
    sessionmaker = _get_session()
    async with sessionmaker() as session:
        count_result = await session.execute(select(func.count(Material.id)))
        existing_count = count_result.scalar() or 0
        if existing_count > 0:
            return success(message=f"物料表已有 {existing_count} 条记录，跳过种子数据")

        for item in SEED_MATERIALS:
            m = Material(**item)
            session.add(m)
        await session.flush()
        await session.commit()

        logger.info("已插入 %d 条物料种子数据", len(SEED_MATERIALS))
        return success(message=f"成功插入 {len(SEED_MATERIALS)} 条物料种子数据")
