"""RAG knowledge base API routes."""

from __future__ import annotations

import os
from typing import Any

from fastapi import APIRouter, HTTPException, Query, UploadFile, File, Form

from app.core.safe_errors import safe_error_message
from app.rag.knowledge_base import get_knowledge_base
from app.rag.vector_store import get_vector_store

router = APIRouter(prefix="/api/rag", tags=["RAG 知识库"])

kb = get_knowledge_base()


def _raise_internal(
    exc: BaseException,
    *,
    context: str,
    fallback: str,
    status_code: int = 500,
) -> None:
    """统一的 HTTPException 5xx 包装：避免将内部异常细节泄露给客户端。"""
    safe = safe_error_message(exc, context=context, fallback=fallback)
    headers = {"X-Error-ID": safe.get("error_id", "")}
    # debug 模式下保留 detail，便于本地排错
    detail: Any = safe.get("message")
    if "detail" in safe:
        detail = f"{safe['message']} ({safe['detail']})"
    raise HTTPException(status_code=status_code, detail=detail, headers=headers)


@router.get("/query")
async def query_knowledge(
    q: str = Query(..., description="查询文本"),
    n_results: int = Query(5, ge=1, le=50, description="返回结果数量"),
):
    try:
        result = kb.query(query_text=q, n_results=n_results)
        return {"query": q, "results": result}
    except Exception as e:
        # 兜底捕获：API 端点必须捕获所有未预期异常，避免 5xx 直接抛给客户端
        # 知识库查询涉及 embedding + 向量检索 + ChromaDB，异常族多源
        _raise_internal(e, context="rag.query", fallback="知识库查询失败")


@router.get("/stats")
async def get_stats():
    try:
        return kb.get_stats()
    except Exception as e:
        # 兜底捕获：API 端点统一收口所有未预期异常
        # 状态查询涉及 ChromaDB 内部计数，异常族多源
        _raise_internal(e, context="rag.stats", fallback="获取知识库状态失败")


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
        # 兜底捕获：API 端点统一收口所有未预期异常
        # 知识库写入涉及 embedding 推理 + ChromaDB 写入，异常族多源
        _raise_internal(e, context="rag.add", fallback="添加知识失败")


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
        # 兜底捕获：API 端点统一收口所有未预期异常
        _raise_internal(e, context="rag.delete", fallback="删除知识失败")


@router.get("/list")
async def list_documents(limit: int = Query(50, ge=1, le=500)):
    try:
        return {"documents": kb.list_documents(limit=limit)}
    except Exception as e:
        # 兜底捕获：API 端点统一收口所有未预期异常
        _raise_internal(e, context="rag.list", fallback="获取文档列表失败")


@router.post("/load/default")
async def load_default_knowledge():
    try:
        count = kb.load_default_knowledge()
        return {"loaded": count, "message": f"已加载 {count} 条默认知识"}
    except Exception as e:
        # 兜底捕获：API 端点统一收口所有未预期异常
        _raise_internal(e, context="rag.load_default", fallback="加载默认知识失败")


@router.post("/load/json")
async def load_rag_json():
    try:
        stats = kb.load_rag_json_knowledge()
        return {"stats": stats}
    except Exception as e:
        # 兜底捕获：API 端点统一收口所有未预期异常
        _raise_internal(e, context="rag.load_json", fallback="加载JSON知识失败")


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
        # 兜底捕获：API 端点统一收口所有未预期异常
        _raise_internal(e, context="rag.search", fallback="搜索失败")


@router.delete("/source/{source}")
async def delete_by_source(source: str):
    try:
        count = kb.delete_by_source(source)
        return {"deleted_count": count, "source": source}
    except Exception as e:
        # 兜底捕获：API 端点统一收口所有未预期异常
        _raise_internal(e, context="rag.delete_by_source", fallback="删除失败")


@router.post("/import/file")
async def import_document(
    file: UploadFile = File(...),
    chunk_size: int = Form(400),
    chunk_overlap: int = Form(60),
):
    try:
        from app.rag.document_importer import DocumentImportService

        import tempfile

        with tempfile.NamedTemporaryFile(
            delete=False, suffix=os.path.splitext(file.filename or "doc.txt")[1]
        ) as tmp:
            content = await file.read()
            tmp.write(content)
            tmp_path = tmp.name

        try:
            service = DocumentImportService(kb)
            result = service.import_document(
                tmp_path,
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
            )
            return result
        finally:
            os.unlink(tmp_path)
    except Exception as e:
        # 兜底捕获：API 端点统一收口所有未预期异常
        # 文档导入涉及临时文件 IO + 多种解析器 + embedding + 向量库
        _raise_internal(e, context="rag.import", fallback="文档导入失败")


@router.post("/backup/export")
async def export_backup(backup_dir: str = Query("./backups/rag")):
    try:
        vs = get_vector_store()
        path = vs.export_backup(backup_dir)
        return {"backup_path": path, "message": "备份导出成功"}
    except Exception as e:
        # 兜底捕获：API 端点统一收口所有未预期异常
        _raise_internal(e, context="rag.backup_export", fallback="备份导出失败")


@router.post("/backup/import")
async def import_backup(backup_dir: str = Query(..., description="备份目录路径")):
    try:
        vs = get_vector_store()
        success = vs.import_backup(backup_dir)
        if not success:
            raise HTTPException(status_code=400, detail="备份目录不存在或无效")
        return {"message": "备份导入成功", "document_count": vs.count()}
    except HTTPException:
        raise
    except Exception as e:
        # 兜底捕获：API 端点统一收口所有未预期异常
        _raise_internal(e, context="rag.backup_import", fallback="备份导入失败")


@router.post("/maintenance/optimize")
async def optimize_index():
    try:
        vs = get_vector_store()
        success = vs.optimize_index()
        return {"optimized": success, "document_count": vs.count()}
    except Exception as e:
        # 兜底捕获：API 端点统一收口所有未预期异常
        _raise_internal(e, context="rag.optimize", fallback="索引优化失败")


@router.post("/maintenance/cleanup")
async def cleanup_orphaned():
    try:
        vs = get_vector_store()
        before = vs.count()
        vs.optimize_index()
        after = vs.count()
        return {
            "before": before,
            "after": after,
            "removed": before - after,
        }
    except Exception as e:
        # 兜底捕获：API 端点统一收口所有未预期异常
        _raise_internal(e, context="rag.cleanup", fallback="清理失败")
