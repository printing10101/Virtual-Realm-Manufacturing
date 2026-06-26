"""
知识库文档 API - 文档管理。

提供文档的 CRUD、分类统计、关键词搜索及演示数据填充功能。
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Query
from pydantic import BaseModel
from sqlalchemy import select, func, delete, or_

from app.core.response import ErrorCode, error, success
from app.database.connection import get_sessionmaker
from app.database.models import Base, Document


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------

class DocumentCreate(BaseModel):
    title: str
    category: str
    version: str = "v1.0"
    author: str
    content: Optional[str] = None
    tags: list[str] = []
    status: str = "待审核"


class DocumentUpdate(BaseModel):
    title: Optional[str] = None
    category: Optional[str] = None
    version: Optional[str] = None
    author: Optional[str] = None
    content: Optional[str] = None
    tags: Optional[list[str]] = None
    status: Optional[str] = None


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

router = APIRouter(prefix="/api/v1/documents", tags=["Documents"])

VALID_CATEGORIES = ["工艺规范", "SOP标准", "设备手册", "质量标准", "材料参数"]


@router.get("/")
async def list_documents(
    category: Optional[str] = Query(None, description="分类筛选"),
    status: Optional[str] = Query(None, description="状态筛选"),
    keyword: Optional[str] = Query(None, description="关键词搜索"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """获取文档列表，支持按分类、状态、关键词筛选。"""
    sessionmaker = get_sessionmaker()
    if not sessionmaker:
        return error(code=ErrorCode.SERVICE_UNAVAILABLE, message="数据库未配置")

    async with sessionmaker() as session:
        stmt = select(Document).order_by(Document.created_at.desc())
        if category:
            stmt = stmt.where(Document.category == category)
        if status:
            stmt = stmt.where(Document.status == status)
        if keyword:
            stmt = stmt.where(
                or_(
                    Document.title.ilike(f"%{keyword}%"),
                    Document.content.ilike(f"%{keyword}%"),
                    Document.author.ilike(f"%{keyword}%"),
                )
            )

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = (await session.execute(count_stmt)).scalar() or 0

        stmt = stmt.offset(offset).limit(limit)
        rows = (await session.execute(stmt)).scalars().all()

    return success(data={
        "documents": [d.to_dict() for d in rows],
        "total": total,
        "limit": limit,
        "offset": offset,
    })


@router.get("/categories/")
async def list_categories():
    """获取所有分类及其文档数量。"""
    sessionmaker = get_sessionmaker()
    if not sessionmaker:
        return error(code=ErrorCode.SERVICE_UNAVAILABLE, message="数据库未配置")

    async with sessionmaker() as session:
        stmt = (
            select(Document.category, func.count().label("count"))
            .group_by(Document.category)
            .order_by(func.count().desc())
        )
        rows = (await session.execute(stmt)).all()

        # 确保所有分类都有返回，即使数量为0
        cat_map = {row.category: row.count for row in rows}
        categories = [
            {"name": cat, "count": cat_map.get(cat, 0)}
            for cat in VALID_CATEGORIES
        ]

    return success(data={"categories": categories})


@router.get("/{doc_id}")
async def get_document(doc_id: str):
    """获取单个文档详情（浏览量+1）。"""
    sessionmaker = get_sessionmaker()
    if not sessionmaker:
        return error(code=ErrorCode.SERVICE_UNAVAILABLE, message="数据库未配置")

    async with sessionmaker() as session:
        stmt = select(Document).where(Document.id == doc_id)
        doc = (await session.execute(stmt)).scalar_one_or_none()
        if not doc:
            return error(code=ErrorCode.NOT_FOUND, message=f"文档 '{doc_id}' 未找到")

        # 增加浏览量
        doc.view_count = (doc.view_count or 0) + 1
        await session.flush()
        await session.commit()

    return success(data=doc.to_dict())


@router.post("/")
async def create_document(body: DocumentCreate):
    """创建文档。"""
    sessionmaker = get_sessionmaker()
    if not sessionmaker:
        return error(code=ErrorCode.SERVICE_UNAVAILABLE, message="数据库未配置")

    async with sessionmaker() as session:
        doc = Document(
            title=body.title,
            category=body.category,
            version=body.version,
            author=body.author,
            content=body.content,
            tags=body.tags,
            status=body.status,
        )
        session.add(doc)
        await session.flush()
        await session.commit()

    return success(data=doc.to_dict(), message="文档创建成功")


@router.put("/{doc_id}")
async def update_document(doc_id: str, body: DocumentUpdate):
    """更新文档。"""
    sessionmaker = get_sessionmaker()
    if not sessionmaker:
        return error(code=ErrorCode.SERVICE_UNAVAILABLE, message="数据库未配置")

    async with sessionmaker() as session:
        stmt = select(Document).where(Document.id == doc_id)
        doc = (await session.execute(stmt)).scalar_one_or_none()
        if not doc:
            return error(code=ErrorCode.NOT_FOUND, message=f"文档 '{doc_id}' 未找到")

        update_data = body.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(doc, key, value)

        await session.flush()
        await session.commit()

    return success(data=doc.to_dict(), message="文档更新成功")


@router.delete("/{doc_id}")
async def delete_document(doc_id: str):
    """删除文档。"""
    sessionmaker = get_sessionmaker()
    if not sessionmaker:
        return error(code=ErrorCode.SERVICE_UNAVAILABLE, message="数据库未配置")

    async with sessionmaker() as session:
        stmt = select(Document).where(Document.id == doc_id)
        doc = (await session.execute(stmt)).scalar_one_or_none()
        if not doc:
            return error(code=ErrorCode.NOT_FOUND, message=f"文档 '{doc_id}' 未找到")

        del_stmt = delete(Document).where(Document.id == doc_id)
        await session.execute(del_stmt)
        await session.commit()

    return success(message="文档删除成功")


@router.post("/seed")
async def seed_documents():
    """填充知识库文档演示数据。"""
    sessionmaker = get_sessionmaker()
    if not sessionmaker:
        return error(code=ErrorCode.SERVICE_UNAVAILABLE, message="数据库未配置")

    async with sessionmaker() as session:
        existing = (await session.execute(select(func.count()).select_from(Document))).scalar()
        if existing and existing > 0:
            return success(message="文档数据已存在，跳过填充")

        docs_seed = [
            {
                "title": "五轴加工中心操作规范",
                "category": "工艺规范",
                "version": "v2.1",
                "author": "工艺部-张工",
                "content": "本规范规定了五轴联动加工中心的操作流程、安全要求及加工参数设置标准，适用于DMG MORI DMU 50系列设备的日常操作。",
                "tags": ["五轴加工", "操作规范", "DMG MORI", "数控"],
                "status": "已发布",
                "view_count": 156,
            },
            {
                "title": "CNC日常维护SOP",
                "category": "SOP标准",
                "version": "v1.0",
                "author": "设备部-李工",
                "content": "本SOP规定了CNC数控机床的日常维护保养流程，包括每日点检、每周保养、月度检查及年度大修的具体操作步骤和标准。",
                "tags": ["CNC", "维护保养", "SOP", "设备管理"],
                "status": "已发布",
                "view_count": 203,
            },
            {
                "title": "DMG MORI DMU 50 设备手册",
                "category": "设备手册",
                "version": "v3.2",
                "author": "DMG MORI技术支持",
                "content": "DMG MORI DMU 50 五轴万能铣削中心完整技术手册，包含设备规格、操作界面说明、报警代码及故障排除指南。",
                "tags": ["DMG MORI", "DMU 50", "设备手册", "五轴"],
                "status": "已发布",
                "view_count": 89,
            },
            {
                "title": "ISO 9001质量检验标准",
                "category": "质量标准",
                "version": "v4.0",
                "author": "质量部-王工",
                "content": "基于ISO 9001:2015标准制定的质量检验规范，涵盖进料检验、过程检验、成品检验的抽样方案、判定标准及记录要求。",
                "tags": ["ISO 9001", "质量标准", "检验规范"],
                "status": "已发布",
                "view_count": 134,
            },
            {
                "title": "45号钢材料参数手册",
                "category": "材料参数",
                "version": "v1.5",
                "author": "技术部-赵工",
                "content": "45号钢（45#）完整材料参数手册，包含化学成分、力学性能、热处理工艺参数及切削加工推荐参数。",
                "tags": ["45号钢", "材料参数", "热处理", "切削参数"],
                "status": "已发布",
                "view_count": 178,
            },
            {
                "title": "铝合金加工工艺指南",
                "category": "工艺规范",
                "version": "v2.0",
                "author": "工艺部-陈工",
                "content": "铝合金（6061-T6/7075-T6）精密加工工艺指南，涵盖刀具选择、切削参数、冷却方案及变形控制措施。",
                "tags": ["铝合金", "加工工艺", "6061", "7075"],
                "status": "待审核",
                "view_count": 45,
            },
            {
                "title": "三坐标测量操作流程",
                "category": "SOP标准",
                "version": "v1.0",
                "author": "质检部-孙工",
                "content": "三坐标测量机（CMM）标准操作流程，包括测头校准、坐标系建立、测量程序编制及测量报告生成。",
                "tags": ["三坐标", "CMM", "测量", "SOP"],
                "status": "已发布",
                "view_count": 112,
            },
            {
                "title": "刀具寿命管理规范",
                "category": "工艺规范",
                "version": "v1.2",
                "author": "工艺部-周工",
                "content": "数控加工刀具寿命管理规范，规定了各类刀具的寿命标准、监测方法、更换流程及寿命数据分析方法。",
                "tags": ["刀具管理", "寿命管理", "加工工艺"],
                "status": "待审核",
                "view_count": 67,
            },
        ]

        for dd in docs_seed:
            session.add(Document(**dd))

        await session.commit()

    return success(message="文档演示数据填充成功", data={
        "documents": len(docs_seed),
    })
