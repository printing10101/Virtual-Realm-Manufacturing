"""RAG knowledge base API routes."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Query

from app.rag.knowledge_base import get_knowledge_base

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/rag", tags=["RAG 知识库"])

kb = get_knowledge_base()


@router.get("/query")
async def query_knowledge(
    q: str = Query(..., description="查询文本"),
    n_results: int = Query(5, ge=1, le=50, description="返回结果数量"),
):
    try:
        result = kb.query(query_text=q, n_results=n_results)
        return {"query": q, "results": result}
    except Exception as e:
        logger.exception("RAG query failed: %s", e)
        raise HTTPException(status_code=500, detail=f"知识库查询失败: {e}")


@router.get("/stats")
async def get_stats():
    try:
        return kb.get_stats()
    except Exception as e:
        logger.exception("Failed to get RAG stats: %s", e)
        raise HTTPException(status_code=500, detail=f"获取知识库状态失败: {e}")


@router.post("/add")
async def add_knowledge(request: dict[str, Any]):
    try:
        document = request.get("document", "")
        metadata = request.get("metadata")
        if not document:
            raise HTTPException(status_code=400, detail="文档内容不能为空")
        result = kb.add_knowledge(document=document, metadata=metadata)
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to add knowledge: %s", e)
        raise HTTPException(status_code=500, detail=f"添加知识失败: {e}")


@router.delete("/{doc_id}")
async def delete_knowledge(doc_id: str):
    try:
        deleted = kb.delete(doc_id)
        if not deleted:
            raise HTTPException(status_code=404, detail=f"文档不存在: {doc_id}")
        return {"deleted": True, "doc_id": doc_id}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to delete knowledge: %s", e)
        raise HTTPException(status_code=500, detail=f"删除知识失败: {e}")


@router.get("/list")
async def list_documents(limit: int = Query(50, ge=1, le=500)):
    try:
        return {"documents": kb.list_documents(limit=limit)}
    except Exception as e:
        logger.exception("Failed to list documents: %s", e)
        raise HTTPException(status_code=500, detail=f"获取文档列表失败: {e}")


@router.post("/load/default")
async def load_default_knowledge():
    try:
        count = kb.load_default_knowledge()
        return {"loaded": count, "message": f"已加载 {count} 条默认知识"}
    except Exception as e:
        logger.exception("Failed to load default knowledge: %s", e)
        raise HTTPException(status_code=500, detail=f"加载默认知识失败: {e}")


@router.post("/load/json")
async def load_rag_json():
    try:
        stats = kb.load_rag_json_knowledge()
        return {"stats": stats}
    except Exception as e:
        logger.exception("Failed to load JSON knowledge: %s", e)
        raise HTTPException(status_code=500, detail=f"加载JSON知识失败: {e}")


@router.get("/search")
async def search_by_source(
    source: str = Query(..., description="知识来源"),
    query: str = Query("", description="可选搜索查询"),
    n_results: int = Query(5, ge=1, le=50),
):
    try:
        result = kb.query_by_source(source=source, query=query, n_results=n_results)
        return {"source": source, "results": result}
    except Exception as e:
        logger.exception("Source search failed: %s", e)
        raise HTTPException(status_code=500, detail=f"搜索失败: {e}")


@router.delete("/source/{source}")
async def delete_by_source(source: str):
    try:
        count = kb.delete_by_source(source)
        return {"deleted_count": count, "source": source}
    except Exception as e:
        logger.exception("Failed to delete by source: %s", e)
        raise HTTPException(status_code=500, detail=f"删除失败: {e}")
