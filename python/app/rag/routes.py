"""RAG knowledge base API routes."""

from __future__ import annotations

import json
import logging
import os
from typing import Any

from fastapi import APIRouter, HTTPException, Query, UploadFile, File, Form

from app.core.safe_errors import safe_error_message
from app.rag.knowledge_base import get_knowledge_base
from app.rag.vector_store import get_vector_store

logger = logging.getLogger(__name__)

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
    except (ValueError, TypeError, KeyError, RuntimeError, OSError) as e:
        # 捕获 RAG 查询相关异常：embedding 生成、向量检索、ChromaDB 操作
        _raise_internal(e, context="rag.query", fallback="知识库查询失败")


@router.get("/stats")
async def get_stats():
    try:
        return kb.get_stats()
    except (ValueError, TypeError, RuntimeError, OSError) as e:
        # 捕获知识库状态查询异常：ChromaDB 计数、集合访问
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
    except (ValueError, TypeError, RuntimeError, OSError) as e:
        # 捕获知识库写入异常：embedding 推理、ChromaDB 写入
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
    except (ValueError, TypeError, RuntimeError, OSError) as e:
        # 捕获知识库删除异常：ChromaDB 删除操作、文档查找
        _raise_internal(e, context="rag.delete", fallback="删除知识失败")


@router.get("/list")
async def list_documents(limit: int = Query(50, ge=1, le=500)):
    try:
        return {"documents": kb.list_documents(limit=limit)}
    except (ValueError, TypeError, KeyError, RuntimeError, OSError) as e:
        # 捕获知识库列表查询异常：ChromaDB 集合访问、文档计数
        logger.exception("Failed to list documents")
        _raise_internal(e, context="rag.list", fallback="获取文档列表失败")


@router.post("/load/default")
async def load_default_knowledge():
    try:
        count = kb.load_default_knowledge()
        return {"loaded": count, "message": f"已加载 {count} 条默认知识"}
    except (OSError, ValueError, RuntimeError) as e:
        # 捕获默认知识加载异常：文件读取、JSON 解析、ChromaDB 写入
        logger.exception("Failed to load default knowledge")
        _raise_internal(e, context="rag.load_default", fallback="加载默认知识失败")


@router.post("/load/json")
async def load_rag_json():
    try:
        stats = kb.load_rag_json_knowledge()
        return {"stats": stats}
    except (json.JSONDecodeError, OSError, ValueError, RuntimeError) as e:
        # 捕获 JSON 知识加载异常：JSON 解析、文件读取、ChromaDB 写入
        logger.exception("Failed to load RAG JSON knowledge")
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
    except (ValueError, TypeError, KeyError, RuntimeError, OSError) as e:
        # 捕获按来源搜索异常：ChromaDB where 过滤、embedding 推理
        logger.exception("Failed to search by source")
        _raise_internal(e, context="rag.search", fallback="搜索失败")


@router.delete("/source/{source}")
async def delete_by_source(source: str):
    try:
        count = kb.delete_by_source(source)
        return {"deleted_count": count, "source": source}
    except (ValueError, TypeError, KeyError, RuntimeError, OSError) as e:
        # 捕获按来源删除异常：ChromaDB where 过滤、批量删除
        logger.exception("Failed to delete by source")
        _raise_internal(e, context="rag.delete_by_source", fallback="删除失败")


@router.post("/import/file")
async def import_document(
    file: UploadFile = File(...),
    chunk_size: int = Form(400, ge=100, le=10000),
    chunk_overlap: int = Form(60, ge=0, le=1000),
):
    try:
        from app.rag.document_importer import DocumentImportService
        from app.utils.utils import validate_file_upload, UploadValidationError

        import tempfile

        # 读取内容后统一校验（类型、大小、文件名）
        content = await file.read()
        _ALLOWED_RAG_EXTENSIONS = {
            ".txt", ".pdf", ".docx", ".doc", ".md",
            ".json", ".csv", ".html", ".xml", ".rtf",
        }
        try:
            validate_file_upload(
                file.filename, len(content), _ALLOWED_RAG_EXTENSIONS,
                max_size_bytes=50 * 1024 * 1024,
            )
        except UploadValidationError as ve:
            raise HTTPException(status_code=400, detail=str(ve))

        with tempfile.NamedTemporaryFile(
            delete=False, suffix=os.path.splitext(file.filename or "doc.txt")[1]
        ) as tmp:
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
    except (OSError, ValueError, UnicodeDecodeError, RuntimeError) as e:
        # 捕获文档导入异常：临时文件 IO、文本解析、embedding 推理、ChromaDB 写入
        logger.exception("Failed to import document")
        _raise_internal(e, context="rag.import", fallback="文档导入失败")


@router.post("/backup/export")
async def export_backup(backup_dir: str = Query("./backups/rag")):
    try:
        vs = get_vector_store()
        path = vs.export_backup(backup_dir)
        return {"backup_path": path, "message": "备份导出成功"}
    except (OSError, RuntimeError) as e:
        # 捕获备份导出异常：目录创建、文件写入、ChromaDB 导出
        logger.exception("Failed to export backup")
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
    except (OSError, ValueError, RuntimeError) as e:
        # 捕获备份导入异常：目录读取、文件解析、ChromaDB 恢复
        logger.exception("Failed to import backup")
        _raise_internal(e, context="rag.backup_import", fallback="备份导入失败")


@router.post("/maintenance/optimize")
async def optimize_index():
    try:
        vs = get_vector_store()
        success = vs.optimize_index()
        return {"optimized": success, "document_count": vs.count()}
    except (RuntimeError, OSError) as e:
        # 捕获索引优化异常：ChromaDB compaction、磁盘 IO
        logger.exception("Failed to optimize index")
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
    except (RuntimeError, OSError) as e:
        # 捕获清理异常：ChromaDB compaction、计数操作
        logger.exception("Failed to cleanup orphaned documents")
        _raise_internal(e, context="rag.cleanup", fallback="清理失败")
