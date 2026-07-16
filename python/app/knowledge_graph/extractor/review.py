"""人工审核界面（M1.4）。

提供基础版 Web 界面，用于审核 LLM 抽取的实体和关系数据：
    - 展示待审核的抽取结果
    - 支持实体/关系的确认、修改和删除操作
    - 实现审核状态跟踪（未审核/已审核/需修改）

用法::

    # 启动审核服务
    python -m app.knowledge_graph.extractor.review

    # 或在代码中使用
    from app.knowledge_graph.extractor.review import ReviewManager
    manager = ReviewManager()
    manager.load_extraction_result(result)
"""

from __future__ import annotations

import json
import logging
import os
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 数据模型
# ---------------------------------------------------------------------------


class ReviewStatus:
    """审核状态常量。"""
    UNVERIFIED = "unverified"      # 未审核
    APPROVED = "approved"          # 已审核
    NEEDS_REVISION = "needs_revision"  # 需修改


class EntityReview(BaseModel):
    """实体审核数据模型。"""
    id: str
    entity_type: str
    name: str
    properties: dict[str, Any] = {}
    confidence: float = 50.0
    status: str = ReviewStatus.UNVERIFIED
    review_comment: str = ""
    reviewed_at: Optional[str] = None


class RelationReview(BaseModel):
    """关系审核数据模型。"""
    source_id: str
    target_id: str
    relation_type: str
    properties: dict[str, Any] = {}
    confidence: float = 50.0
    status: str = ReviewStatus.UNVERIFIED
    review_comment: str = ""
    reviewed_at: Optional[str] = None


class ExtractionReviewData(BaseModel):
    """抽取结果审核数据。"""
    id: str
    source_path: str
    extraction_method: str = ""
    total_pages: int = 0
    processed_pages: int = 0
    entities: list[EntityReview] = []
    relations: list[RelationReview] = []
    validation_report: Optional[dict[str, Any]] = None
    created_at: str = ""
    updated_at: str = ""
    overall_status: str = ReviewStatus.UNVERIFIED


# ---------------------------------------------------------------------------
# 审核管理器
# ---------------------------------------------------------------------------


@dataclass
class ReviewManager:
    """审核结果管理器。

    负责存储和管理待审核的抽取结果。
    """

    reviews: dict[str, ExtractionReviewData] = field(default_factory=dict)
    storage_path: Path = Path("./data/reviews")

    def __post_init__(self):
        """初始化存储目录。"""
        self.storage_path.mkdir(parents=True, exist_ok=True)
        # 并发保护：ReviewManager 单例在多个 async 端点间共享，
        # reviews 字典的并发修改与 _save_to_disk 的文件写入均需加锁。
        # 使用 RLock 以允许 _save_to_disk 在已持锁的方法内部被调用时
        # 复用同一把锁，避免死锁。
        self._lock = threading.RLock()

    def load_extraction_result(
        self,
        result: dict[str, Any],
    ) -> str:
        """加载抽取结果到审核队列。

        Args:
            result: 抽取结果字典，包含 entities 和 relations。

        Returns:
            str: 审核记录 ID。
        """
        review_id = str(uuid.uuid4())[:8]
        now = datetime.now().isoformat()

        # 转换实体
        entities = []
        for ent in result.get("entities", []):
            entities.append(EntityReview(
                id=ent.get("id", ""),
                entity_type=ent.get("entity_type", ""),
                name=ent.get("name", ""),
                properties=ent.get("properties", {}),
                confidence=float(ent.get("confidence", 50)),
                status=ent.get("status", ReviewStatus.UNVERIFIED),
            ))

        # 转换关系
        relations = []
        for rel in result.get("relations", []):
            relations.append(RelationReview(
                source_id=rel.get("source_id", ""),
                target_id=rel.get("target_id", ""),
                relation_type=rel.get("relation_type", ""),
                properties=rel.get("properties", {}),
                confidence=float(rel.get("confidence", 50)),
                status=rel.get("status", ReviewStatus.UNVERIFIED),
            ))

        # 创建审核记录
        review = ExtractionReviewData(
            id=review_id,
            source_path=result.get("source_path", ""),
            extraction_method=result.get("extraction_method", ""),
            total_pages=result.get("total_pages", 0),
            processed_pages=result.get("processed_pages", 0),
            entities=entities,
            relations=relations,
            validation_report=result.get("validation_report"),
            created_at=now,
            updated_at=now,
            overall_status=ReviewStatus.UNVERIFIED,
        )

        with self._lock:
            self.reviews[review_id] = review
            self._save_to_disk(review)

        logger.info(
            "加载审核记录 %s: %d 个实体, %d 个关系",
            review_id,
            len(entities),
            len(relations),
        )

        return review_id

    def get_review(self, review_id: str) -> Optional[ExtractionReviewData]:
        """获取审核记录。"""
        with self._lock:
            return self.reviews.get(review_id)

    def list_reviews(self) -> list[dict[str, Any]]:
        """列出所有审核记录摘要。"""
        with self._lock:
            result = []
            for review_id, review in self.reviews.items():
                approved_entities = sum(
                    1 for e in review.entities if e.status == ReviewStatus.APPROVED
                )
                approved_relations = sum(
                    1 for r in review.relations if r.status == ReviewStatus.APPROVED
                )
                result.append({
                    "id": review_id,
                    "source_path": review.source_path,
                    "total_entities": len(review.entities),
                    "approved_entities": approved_entities,
                    "total_relations": len(review.relations),
                    "approved_relations": approved_relations,
                    "overall_status": review.overall_status,
                    "created_at": review.created_at,
                })
            return result

    def update_entity(
        self,
        review_id: str,
        entity_id: str,
        updates: dict[str, Any],
    ) -> bool:
        """更新实体审核状态。

        Args:
            review_id: 审核记录 ID。
            entity_id: 实体 ID。
            updates: 更新内容，可包含 status, review_comment 等。

        Returns:
            bool: 是否更新成功。
        """
        with self._lock:
            review = self.reviews.get(review_id)
            if not review:
                return False

            for entity in review.entities:
                if entity.id == entity_id:
                    if "status" in updates:
                        entity.status = updates["status"]
                        entity.reviewed_at = datetime.now().isoformat()
                    if "review_comment" in updates:
                        entity.review_comment = updates["review_comment"]
                    if "name" in updates:
                        entity.name = updates["name"]
                    if "properties" in updates:
                        entity.properties = updates["properties"]

                    review.updated_at = datetime.now().isoformat()
                    self._update_overall_status(review)
                    self._save_to_disk(review)
                    return True

            return False

    def update_relation(
        self,
        review_id: str,
        source_id: str,
        target_id: str,
        relation_type: str,
        updates: dict[str, Any],
    ) -> bool:
        """更新关系审核状态。

        Args:
            review_id: 审核记录 ID。
            source_id: 源实体 ID。
            target_id: 目标实体 ID。
            relation_type: 关系类型。
            updates: 更新内容。

        Returns:
            bool: 是否更新成功。
        """
        with self._lock:
            review = self.reviews.get(review_id)
            if not review:
                return False

            for relation in review.relations:
                if (
                    relation.source_id == source_id
                    and relation.target_id == target_id
                    and relation.relation_type == relation_type
                ):
                    if "status" in updates:
                        relation.status = updates["status"]
                        relation.reviewed_at = datetime.now().isoformat()
                    if "review_comment" in updates:
                        relation.review_comment = updates["review_comment"]
                    if "properties" in updates:
                        relation.properties = updates["properties"]

                    review.updated_at = datetime.now().isoformat()
                    self._update_overall_status(review)
                    self._save_to_disk(review)
                    return True

            return False

    def delete_entity(self, review_id: str, entity_id: str) -> bool:
        """删除实体（标记为删除状态）。"""
        with self._lock:
            review = self.reviews.get(review_id)
            if not review:
                return False

            for i, entity in enumerate(review.entities):
                if entity.id == entity_id:
                    entity.status = "deleted"
                    entity.reviewed_at = datetime.now().isoformat()
                    review.updated_at = datetime.now().isoformat()
                    self._update_overall_status(review)
                    self._save_to_disk(review)
                    return True

            return False

    def delete_relation(
        self,
        review_id: str,
        source_id: str,
        target_id: str,
        relation_type: str,
    ) -> bool:
        """删除关系（标记为删除状态）。"""
        with self._lock:
            review = self.reviews.get(review_id)
            if not review:
                return False

            for relation in review.relations:
                if (
                    relation.source_id == source_id
                    and relation.target_id == target_id
                    and relation.relation_type == relation_type
                ):
                    relation.status = "deleted"
                    relation.reviewed_at = datetime.now().isoformat()
                    review.updated_at = datetime.now().isoformat()
                    self._update_overall_status(review)
                    self._save_to_disk(review)
                    return True

            return False

    def approve_all(self, review_id: str) -> bool:
        """批量批准所有实体和关系。"""
        with self._lock:
            review = self.reviews.get(review_id)
            if not review:
                return False

            now = datetime.now().isoformat()
            for entity in review.entities:
                if entity.status == ReviewStatus.UNVERIFIED:
                    entity.status = ReviewStatus.APPROVED
                    entity.reviewed_at = now

            for relation in review.relations:
                if relation.status == ReviewStatus.UNVERIFIED:
                    relation.status = ReviewStatus.APPROVED
                    relation.reviewed_at = now

            review.overall_status = ReviewStatus.APPROVED
            review.updated_at = now
            self._save_to_disk(review)
            return True

    def get_approved_data(self, review_id: str) -> Optional[dict[str, Any]]:
        """获取已批准的数据，可用于写入图谱。

        Args:
            review_id: 审核记录 ID。

        Returns:
            dict: 包含已批准实体和关系的字典。
        """
        with self._lock:
            review = self.reviews.get(review_id)
            if not review:
                return None

            entities = [
                {
                    "entity_type": e.entity_type,
                    "id": e.id,
                    "name": e.name,
                    "properties": e.properties,
                    "confidence": e.confidence,
                }
                for e in review.entities
                if e.status == ReviewStatus.APPROVED
            ]

            relations = [
                {
                    "relation_type": r.relation_type,
                    "source_id": r.source_id,
                    "target_id": r.target_id,
                    "properties": r.properties,
                    "confidence": r.confidence,
                }
                for r in review.relations
                if r.status == ReviewStatus.APPROVED
            ]

            return {
                "entities": entities,
                "relations": relations,
                "source_path": review.source_path,
                "approved_at": datetime.now().isoformat(),
            }

    def _update_overall_status(self, review: ExtractionReviewData) -> None:
        """更新整体审核状态。"""
        all_items = list(review.entities) + list(review.relations)
        if not all_items:
            review.overall_status = ReviewStatus.APPROVED
            return

        statuses = [item.status for item in all_items if item.status != "deleted"]
        if not statuses:
            review.overall_status = ReviewStatus.APPROVED
        elif all(s == ReviewStatus.APPROVED for s in statuses):
            review.overall_status = ReviewStatus.APPROVED
        elif any(s == ReviewStatus.NEEDS_REVISION for s in statuses):
            review.overall_status = ReviewStatus.NEEDS_REVISION
        else:
            review.overall_status = ReviewStatus.UNVERIFIED

    def _save_to_disk(self, review: ExtractionReviewData) -> None:
        """保存审核记录到磁盘。

        使用 RLock 以允许在已持锁的公开方法内部被调用时复用锁，
        同时也可单独被调用而不影响正确性。
        """
        with self._lock:
            file_path = self.storage_path / f"{review.id}.json"
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(review.model_dump(), f, ensure_ascii=False, indent=2)

    def load_from_disk(self) -> None:
        """从磁盘加载所有审核记录。"""
        with self._lock:
            if not self.storage_path.exists():
                return

            for file_path in self.storage_path.glob("*.json"):
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    review = ExtractionReviewData(**data)
                    self.reviews[review.id] = review
                except (json.JSONDecodeError, OSError, ValueError, TypeError, KeyError) as exc:
                    logger.warning("加载审核记录失败 %s: %s", file_path, exc)


# ---------------------------------------------------------------------------
# FastAPI 路由
# ---------------------------------------------------------------------------


router = APIRouter(prefix="/review", tags=["review"])
review_manager = ReviewManager()


@router.on_event("startup")
async def startup_event():
    """启动时加载审核记录。"""
    review_manager.load_from_disk()


@router.get("/", response_class=HTMLResponse)
async def review_page():
    """审核界面首页。"""
    return REVIEW_HTML_TEMPLATE


@router.get("/api/reviews")
async def list_reviews():
    """列出所有审核记录。"""
    return {"reviews": review_manager.list_reviews()}


@router.get("/api/reviews/{review_id}")
async def get_review(review_id: str):
    """获取审核记录详情。"""
    review = review_manager.get_review(review_id)
    if not review:
        raise HTTPException(status_code=404, detail="审核记录不存在")
    return review.model_dump()


@router.patch("/api/reviews/{review_id}/entities/{entity_id}")
async def update_entity(review_id: str, entity_id: str, request: Request):
    """更新实体。"""
    updates = await request.json()
    success = review_manager.update_entity(review_id, entity_id, updates)
    if not success:
        raise HTTPException(status_code=404, detail="实体不存在")
    return {"success": True}


@router.delete("/api/reviews/{review_id}/entities/{entity_id}")
async def delete_entity(review_id: str, entity_id: str):
    """删除实体。"""
    success = review_manager.delete_entity(review_id, entity_id)
    if not success:
        raise HTTPException(status_code=404, detail="实体不存在")
    return {"success": True}


@router.patch("/api/reviews/{review_id}/relations")
async def update_relation(review_id: str, request: Request):
    """更新关系。"""
    data = await request.json()
    success = review_manager.update_relation(
        review_id,
        data["source_id"],
        data["target_id"],
        data["relation_type"],
        data.get("updates", {}),
    )
    if not success:
        raise HTTPException(status_code=404, detail="关系不存在")
    return {"success": True}


@router.delete("/api/reviews/{review_id}/relations")
async def delete_relation(review_id: str, request: Request):
    """删除关系。"""
    data = await request.json()
    success = review_manager.delete_relation(
        review_id,
        data["source_id"],
        data["target_id"],
        data["relation_type"],
    )
    if not success:
        raise HTTPException(status_code=404, detail="关系不存在")
    return {"success": True}


@router.post("/api/reviews/{review_id}/approve-all")
async def approve_all(review_id: str):
    """批量批准所有项目。"""
    success = review_manager.approve_all(review_id)
    if not success:
        raise HTTPException(status_code=404, detail="审核记录不存在")
    return {"success": True}


@router.get("/api/reviews/{review_id}/approved")
async def get_approved_data(review_id: str):
    """获取已批准的数据。"""
    data = review_manager.get_approved_data(review_id)
    if data is None:
        raise HTTPException(status_code=404, detail="审核记录不存在")
    return data


@router.post("/api/load")
async def load_extraction_result(request: Request):
    """加载抽取结果到审核队列。"""
    data = await request.json()
    review_id = review_manager.load_extraction_result(data)
    return {"review_id": review_id}


# ---------------------------------------------------------------------------
# HTML 模板
# ---------------------------------------------------------------------------


REVIEW_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>知识图谱抽取结果审核</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            background: #f5f7fa;
            color: #333;
            line-height: 1.6;
        }
        .container {
            max-width: 1400px;
            margin: 0 auto;
            padding: 20px;
        }
        header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            border-radius: 12px;
            margin-bottom: 30px;
            box-shadow: 0 4px 20px rgba(102, 126, 234, 0.3);
        }
        header h1 {
            font-size: 28px;
            margin-bottom: 10px;
        }
        header p {
            opacity: 0.9;
            font-size: 14px;
        }
        .stats {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }
        .stat-card {
            background: white;
            padding: 20px;
            border-radius: 12px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.05);
            text-align: center;
        }
        .stat-card .value {
            font-size: 36px;
            font-weight: bold;
            color: #667eea;
        }
        .stat-card .label {
            color: #666;
            font-size: 14px;
            margin-top: 5px;
        }
        .review-list {
            background: white;
            border-radius: 12px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.05);
            overflow: hidden;
        }
        .review-item {
            padding: 20px;
            border-bottom: 1px solid #eee;
            cursor: pointer;
            transition: background 0.2s;
        }
        .review-item:hover {
            background: #f8f9fa;
        }
        .review-item:last-child {
            border-bottom: none;
        }
        .review-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 10px;
        }
        .review-title {
            font-weight: 600;
            color: #333;
        }
        .status-badge {
            padding: 4px 12px;
            border-radius: 20px;
            font-size: 12px;
            font-weight: 500;
        }
        .status-unverified {
            background: #fff3cd;
            color: #856404;
        }
        .status-approved {
            background: #d4edda;
            color: #155724;
        }
        .status-needs-revision {
            background: #f8d7da;
            color: #721c24;
        }
        .review-meta {
            display: flex;
            gap: 20px;
            font-size: 13px;
            color: #666;
        }
        .empty-state {
            text-align: center;
            padding: 60px 20px;
            color: #666;
        }
        .empty-state svg {
            width: 80px;
            height: 80px;
            margin-bottom: 20px;
            opacity: 0.5;
        }
        .btn {
            padding: 10px 20px;
            border: none;
            border-radius: 8px;
            cursor: pointer;
            font-size: 14px;
            font-weight: 500;
            transition: all 0.2s;
        }
        .btn-primary {
            background: #667eea;
            color: white;
        }
        .btn-primary:hover {
            background: #5a6fd6;
        }
        .btn-success {
            background: #28a745;
            color: white;
        }
        .btn-success:hover {
            background: #218838;
        }
        .btn-danger {
            background: #dc3545;
            color: white;
        }
        .btn-danger:hover {
            background: #c82333;
        }
        .actions {
            display: flex;
            gap: 10px;
            margin-top: 15px;
        }
        /* Modal */
        .modal {
            display: none;
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0,0,0,0.5);
            z-index: 1000;
            overflow-y: auto;
        }
        .modal.active {
            display: flex;
            align-items: flex-start;
            justify-content: center;
            padding: 40px 20px;
        }
        .modal-content {
            background: white;
            border-radius: 16px;
            width: 100%;
            max-width: 1000px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
        }
        .modal-header {
            padding: 20px 30px;
            border-bottom: 1px solid #eee;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .modal-header h2 {
            font-size: 20px;
        }
        .modal-close {
            background: none;
            border: none;
            font-size: 24px;
            cursor: pointer;
            color: #666;
        }
        .modal-body {
            padding: 30px;
            max-height: 70vh;
            overflow-y: auto;
        }
        .section {
            margin-bottom: 30px;
        }
        .section-title {
            font-size: 16px;
            font-weight: 600;
            margin-bottom: 15px;
            color: #333;
            display: flex;
            align-items: center;
            gap: 10px;
        }
        .section-title .count {
            background: #667eea;
            color: white;
            padding: 2px 10px;
            border-radius: 12px;
            font-size: 12px;
        }
        .entity-card, .relation-card {
            background: #f8f9fa;
            border: 1px solid #e9ecef;
            border-radius: 8px;
            padding: 15px;
            margin-bottom: 10px;
        }
        .entity-card.approved, .relation-card.approved {
            border-color: #28a745;
            background: #f8fff8;
        }
        .entity-card.needs-revision, .relation-card.needs-revision {
            border-color: #ffc107;
            background: #fffbf0;
        }
        .entity-card.deleted, .relation-card.deleted {
            opacity: 0.5;
            text-decoration: line-through;
        }
        .item-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 10px;
        }
        .item-type {
            font-size: 11px;
            padding: 2px 8px;
            border-radius: 4px;
            background: #667eea;
            color: white;
            text-transform: uppercase;
        }
        .item-name {
            font-weight: 600;
            font-size: 15px;
        }
        .item-id {
            font-size: 12px;
            color: #666;
            font-family: monospace;
        }
        .item-properties {
            font-size: 13px;
            color: #555;
            margin-top: 8px;
        }
        .item-actions {
            display: flex;
            gap: 8px;
            margin-top: 10px;
        }
        .item-actions button {
            padding: 6px 12px;
            font-size: 12px;
        }
        .confidence {
            font-size: 12px;
            color: #666;
        }
        .confidence.high { color: #28a745; }
        .confidence.medium { color: #ffc107; }
        .confidence.low { color: #dc3545; }
        .relation-arrow {
            color: #667eea;
            font-weight: bold;
            margin: 0 8px;
        }
        .loading {
            text-align: center;
            padding: 40px;
            color: #666;
        }
        .loading::after {
            content: '';
            display: inline-block;
            width: 20px;
            height: 20px;
            border: 3px solid #667eea;
            border-top-color: transparent;
            border-radius: 50%;
            animation: spin 1s linear infinite;
            margin-left: 10px;
        }
        @keyframes spin {
            to { transform: rotate(360deg); }
        }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>知识图谱抽取结果审核</h1>
            <p>审核 LLM 从工艺文档中抽取的实体和关系数据</p>
        </header>

        <div class="stats">
            <div class="stat-card">
                <div class="value" id="total-reviews">0</div>
                <div class="label">待审核记录</div>
            </div>
            <div class="stat-card">
                <div class="value" id="total-entities">0</div>
                <div class="label">实体总数</div>
            </div>
            <div class="stat-card">
                <div class="value" id="total-relations">0</div>
                <div class="label">关系总数</div>
            </div>
            <div class="stat-card">
                <div class="value" id="approved-count">0</div>
                <div class="label">已批准</div>
            </div>
        </div>

        <div class="review-list" id="review-list">
            <div class="loading">加载中</div>
        </div>
    </div>

    <!-- 审核详情模态框 -->
    <div class="modal" id="review-modal">
        <div class="modal-content">
            <div class="modal-header">
                <h2 id="modal-title">审核详情</h2>
                <button class="modal-close" onclick="closeModal()">&times;</button>
            </div>
            <div class="modal-body" id="modal-body">
                <!-- 动态内容 -->
            </div>
        </div>
    </div>

    <script>
        let currentReviewId = null;

        // 加载审核列表
        async function loadReviews() {
            try {
                const response = await fetch('/review/api/reviews');
                const data = await response.json();
                renderReviewList(data.reviews);
                updateStats(data.reviews);
            } catch (error) {
                console.error('加载审核列表失败:', error);
                document.getElementById('review-list').innerHTML = `
                    <div class="empty-state">
                        <p>加载失败，请刷新页面重试</p>
                    </div>
                `;
            }
        }

        // 渲染审核列表
        function renderReviewList(reviews) {
            const container = document.getElementById('review-list');
            
            if (reviews.length === 0) {
                container.innerHTML = `
                    <div class="empty-state">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
                            <path d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                        </svg>
                        <p>暂无待审核记录</p>
                        <p style="font-size: 13px; margin-top: 10px;">请先运行抽取命令生成审核数据</p>
                    </div>
                `;
                return;
            }

            container.innerHTML = reviews.map(review => `
                <div class="review-item" onclick="openReview('${review.id}')">
                    <div class="review-header">
                        <span class="review-title">${review.source_path || '未命名文档'}</span>
                        <span class="status-badge status-${review.overall_status}">
                            ${getStatusText(review.overall_status)}
                        </span>
                    </div>
                    <div class="review-meta">
                        <span>实体: ${review.approved_entities}/${review.total_entities}</span>
                        <span>关系: ${review.approved_relations}/${review.total_relations}</span>
                        <span>创建: ${new Date(review.created_at).toLocaleString()}</span>
                    </div>
                </div>
            `).join('');
        }

        // 更新统计
        function updateStats(reviews) {
            const totalEntities = reviews.reduce((sum, r) => sum + r.total_entities, 0);
            const totalRelations = reviews.reduce((sum, r) => sum + r.total_relations, 0);
            const approvedEntities = reviews.reduce((sum, r) => sum + r.approved_entities, 0);
            const approvedRelations = reviews.reduce((sum, r) => sum + r.approved_relations, 0);

            document.getElementById('total-reviews').textContent = reviews.length;
            document.getElementById('total-entities').textContent = totalEntities;
            document.getElementById('total-relations').textContent = totalRelations;
            document.getElementById('approved-count').textContent = approvedEntities + approvedRelations;
        }

        // 打开审核详情
        async function openReview(reviewId) {
            currentReviewId = reviewId;
            const modal = document.getElementById('review-modal');
            const body = document.getElementById('modal-body');
            
            modal.classList.add('active');
            body.innerHTML = '<div class="loading">加载中</div>';

            try {
                const response = await fetch(`/review/api/reviews/${reviewId}`);
                const data = await response.json();
                renderReviewDetail(data);
            } catch (error) {
                body.innerHTML = '<p>加载失败</p>';
            }
        }

        // 渲染审核详情
        function renderReviewDetail(data) {
            const body = document.getElementById('modal-body');
            document.getElementById('modal-title').textContent = data.source_path || '审核详情';

            const entitiesHtml = data.entities.map(entity => `
                <div class="entity-card ${entity.status}" id="entity-${entity.id}">
                    <div class="item-header">
                        <div>
                            <span class="item-type">${entity.entity_type}</span>
                            <span class="item-name">${entity.name}</span>
                        </div>
                        <span class="item-id">${entity.id}</span>
                    </div>
                    <div class="item-properties">
                        ${Object.entries(entity.properties).map(([k, v]) => `${k}: ${v}`).join(' | ') || '无属性'}
                    </div>
                    <div class="item-actions">
                        <span class="confidence ${getConfidenceClass(entity.confidence)}">
                            置信度: ${entity.confidence}%
                        </span>
                        <button class="btn btn-success" onclick="approveEntity('${entity.id}')">
                            ${entity.status === 'approved' ? '已批准' : '批准'}
                        </button>
                        <button class="btn btn-primary" onclick="requestRevision('entity', '${entity.id}')">
                            需修改
                        </button>
                        <button class="btn btn-danger" onclick="deleteEntity('${entity.id}')">
                            删除
                        </button>
                    </div>
                </div>
            `).join('');

            const relationsHtml = data.relations.map((rel, idx) => `
                <div class="relation-card ${rel.status}" id="relation-${idx}">
                    <div class="item-header">
                        <div>
                            <span class="item-type">${rel.relation_type}</span>
                            <span>
                                <span class="item-id">${rel.source_id}</span>
                                <span class="relation-arrow">→</span>
                                <span class="item-id">${rel.target_id}</span>
                            </span>
                        </div>
                    </div>
                    <div class="item-actions">
                        <span class="confidence ${getConfidenceClass(rel.confidence)}">
                            置信度: ${rel.confidence}%
                        </span>
                        <button class="btn btn-success" onclick="approveRelation(${idx})">
                            ${rel.status === 'approved' ? '已批准' : '批准'}
                        </button>
                        <button class="btn btn-primary" onclick="requestRevisionRelation(${idx})">
                            需修改
                        </button>
                        <button class="btn btn-danger" onclick="deleteRelation(${idx})">
                            删除
                        </button>
                    </div>
                </div>
            `).join('');

            body.innerHTML = `
                <div class="section">
                    <div class="section-title">
                        实体列表
                        <span class="count">${data.entities.length}</span>
                    </div>
                    ${entitiesHtml || '<p style="color: #666;">无实体数据</p>'}
                </div>
                <div class="section">
                    <div class="section-title">
                        关系列表
                        <span class="count">${data.relations.length}</span>
                    </div>
                    ${relationsHtml || '<p style="color: #666;">无关系数据</p>'}
                </div>
                <div class="actions">
                    <button class="btn btn-success" onclick="approveAll()">
                        全部批准
                    </button>
                    <button class="btn btn-primary" onclick="exportApproved()">
                        导出已批准数据
                    </button>
                </div>
            `;
        }

        // 关闭模态框
        function closeModal() {
            document.getElementById('review-modal').classList.remove('active');
            currentReviewId = null;
            loadReviews();
        }

        // 批准实体
        async function approveEntity(entityId) {
            await fetch(`/review/api/reviews/${currentReviewId}/entities/${entityId}`, {
                method: 'PATCH',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ status: 'approved' })
            });
            document.getElementById(`entity-${entityId}`).classList.add('approved');
        }

        // 请求修改实体
        async function requestRevision(type, entityId) {
            await fetch(`/review/api/reviews/${currentReviewId}/entities/${entityId}`, {
                method: 'PATCH',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ status: 'needs_revision' })
            });
            document.getElementById(`entity-${entityId}`).classList.add('needs-revision');
        }

        // 删除实体
        async function deleteEntity(entityId) {
            if (!confirm('确定要删除此实体吗？')) return;
            await fetch(`/review/api/reviews/${currentReviewId}/entities/${entityId}`, {
                method: 'DELETE'
            });
            document.getElementById(`entity-${entityId}`).classList.add('deleted');
        }

        // 批准关系
        async function approveRelation(idx) {
            const modal = document.getElementById('modal-body');
            const relCard = document.getElementById(`relation-${idx}`);
            const relType = relCard.querySelector('.item-type').textContent;
            const ids = relCard.querySelectorAll('.item-id');
            
            await fetch(`/review/api/reviews/${currentReviewId}/relations`, {
                method: 'PATCH',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    source_id: ids[0].textContent,
                    target_id: ids[1].textContent,
                    relation_type: relType,
                    updates: { status: 'approved' }
                })
            });
            relCard.classList.add('approved');
        }

        // 请求修改关系
        async function requestRevisionRelation(idx) {
            const relCard = document.getElementById(`relation-${idx}`);
            const relType = relCard.querySelector('.item-type').textContent;
            const ids = relCard.querySelectorAll('.item-id');
            
            await fetch(`/review/api/reviews/${currentReviewId}/relations`, {
                method: 'PATCH',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    source_id: ids[0].textContent,
                    target_id: ids[1].textContent,
                    relation_type: relType,
                    updates: { status: 'needs_revision' }
                })
            });
            relCard.classList.add('needs-revision');
        }

        // 删除关系
        async function deleteRelation(idx) {
            if (!confirm('确定要删除此关系吗？')) return;
            const relCard = document.getElementById(`relation-${idx}`);
            const relType = relCard.querySelector('.item-type').textContent;
            const ids = relCard.querySelectorAll('.item-id');
            
            await fetch(`/review/api/reviews/${currentReviewId}/relations`, {
                method: 'DELETE',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    source_id: ids[0].textContent,
                    target_id: ids[1].textContent,
                    relation_type: relType
                })
            });
            relCard.classList.add('deleted');
        }

        // 全部批准
        async function approveAll() {
            if (!confirm('确定要批准所有未审核项目吗？')) return;
            await fetch(`/review/api/reviews/${currentReviewId}/approve-all`, {
                method: 'POST'
            });
            openReview(currentReviewId);
        }

        // 导出已批准数据
        async function exportApproved() {
            const response = await fetch(`/review/api/reviews/${currentReviewId}/approved`);
            const data = await response.json();
            const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `approved-${currentReviewId}.json`;
            a.click();
            URL.revokeObjectURL(url);
        }

        // 辅助函数
        function getStatusText(status) {
            const map = {
                'unverified': '待审核',
                'approved': '已批准',
                'needs_revision': '需修改'
            };
            return map[status] || status;
        }

        function getConfidenceClass(confidence) {
            if (confidence >= 80) return 'high';
            if (confidence >= 60) return 'medium';
            return 'low';
        }

        // 初始化
        loadReviews();
    </script>
</body>
</html>"""


# ---------------------------------------------------------------------------
# 独立运行
# ---------------------------------------------------------------------------


def create_review_app() -> FastAPI:
    """创建审核应用实例。"""
    app = FastAPI(title="知识图谱抽取结果审核", version="1.0.0")
    app.include_router(router)
    return app


def main():  # pragma: no cover
    """独立运行审核服务。"""
    import uvicorn

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    app = create_review_app()
    # 默认仅监听本机回环，避免暴露到外网；如需远程访问可通过 env 显式指定绑定地址。
    host = os.environ.get("KG_REVIEW_HOST", "127.0.0.1")
    port = int(os.environ.get("KG_REVIEW_PORT", "8001"))
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":  # pragma: no cover
    main()
