"""RAG knowledge base API routes."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import threading
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Form

from app.auth.permissions import require_permission
from app.core.safe_errors import safe_error_message
from app.rag.knowledge_base import get_knowledge_base
from app.rag.vector_store import get_vector_store

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/rag", tags=["RAG 知识库"])

kb = get_knowledge_base()


# ---------------------------------------------------------------------------
# v2 增强：懒加载单例（避免在导入时初始化重型组件）
# ---------------------------------------------------------------------------

_rag_engine_instance = None
_rag_engine_lock = threading.Lock()


def _get_rag_engine():
    """懒加载 RagRetrievalEngine 单例。

    RAG engine 依赖 knowledge_base，且其增强模块（reranker / hybrid_search /
    query_rewriter）在首次调用 ``_load_enhancements`` 时才会触发模型加载，
    避免在服务启动时阻塞。
    """
    global _rag_engine_instance
    if _rag_engine_instance is not None:
        return _rag_engine_instance
    with _rag_engine_lock:
        if _rag_engine_instance is not None:
            return _rag_engine_instance
        from app.rag.rag_retrieval import RagRetrievalEngine

        _rag_engine_instance = RagRetrievalEngine(knowledge_base=kb)
        logger.info("RagRetrievalEngine singleton initialized")
    return _rag_engine_instance


def _get_evaluator(use_rag_engine: bool = False):
    """构建 RetrievalEvaluator 实例。

    Args:
        use_rag_engine: True 时注入 RAG engine，启用完整 pipeline 评估
    """
    from app.rag.evaluation import RetrievalEvaluator

    reranker = None
    try:
        from app.rag.reranker import get_reranker_service

        reranker = get_reranker_service()
    except (ImportError, RuntimeError) as e:
        logger.debug("Reranker service unavailable: %s", e)

    rag_engine = _get_rag_engine() if use_rag_engine else None
    return RetrievalEvaluator(
        knowledge_base=kb,
        reranker_service=reranker,
        rag_engine=rag_engine,
    )


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
    intent: str | None = Query(
        None,
        description="查询意图（material_wear/cutting_params/vibration_wear/"
        "material_compare/cross_source/general），不传则自动检测",
    ),
    use_enhanced: bool = Query(
        True,
        description="True 启用完整增强 pipeline（reranker/hybrid_search/"
        "query_rewrite），False 仅使用 baseline 向量检索",
    ),
):
    """RAG 知识库查询（v2 增强）。

    启用完整 pipeline：查询改写 → HyDE → 意图检测 → 多源并行检索 →
    混合检索融合（RRF）→ Cross-Encoder 重排序 → 关键词 boost。

    Args:
        q: 查询文本
        n_results: 返回结果数量
        intent: 可选查询意图，不传则自动检测
        use_enhanced: 是否启用增强 pipeline（默认 True）

    Returns:
        增强检索结果，包含 results / detected_intent / enhancements 等字段
    """
    try:
        if use_enhanced:
            # 使用增强 pipeline（RagRetrievalEngine）
            engine = _get_rag_engine()

            # 解析 intent 字符串到 QueryIntent 枚举
            intent_enum = None
            if intent:
                from app.rag.rag_retrieval import QueryIntent

                try:
                    intent_enum = QueryIntent(intent)
                except ValueError:
                    valid_intents = [i.value for i in QueryIntent]
                    raise HTTPException(
                        status_code=400,
                        detail=f"无效的 intent: {intent}，可选值: {valid_intents}",
                    )

            # ChromaDB 同步调用通过线程池执行，避免阻塞事件循环
            result = await asyncio.to_thread(
                engine.retrieve,
                q,
                intent_enum,
                n_results,
                None,  # override_source
            )
            return {
                "query": q,
                "results": result,
                "pipeline": "enhanced",
                "n_results": n_results,
            }
        else:
            # baseline 模式：直接使用 kb.query()
            result = kb.query(query_text=q, n_results=n_results)
            return {
                "query": q,
                "results": result,
                "pipeline": "baseline",
                "n_results": n_results,
            }
    except HTTPException:
        raise
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


@router.post("/backup/export", dependencies=[Depends(require_permission("backup:export"))])
async def export_backup(backup_dir: str = Query("./backups/rag")):
    try:
        vs = get_vector_store()
        path = vs.export_backup(backup_dir)
        return {"backup_path": path, "message": "备份导出成功"}
    except (OSError, RuntimeError) as e:
        # 捕获备份导出异常：目录创建、文件写入、ChromaDB 导出
        logger.exception("Failed to export backup")
        _raise_internal(e, context="rag.backup_export", fallback="备份导出失败")


@router.post("/backup/import", dependencies=[Depends(require_permission("backup:import"))])
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


# ===========================================================================
# v2 增强 API 端点
# ===========================================================================
# 以下端点暴露 RAG pipeline 的诊断、评估与 ablation study 能力，
# 便于运维与研发团队量化各增强模块的贡献度。
# ---------------------------------------------------------------------------


@router.get("/v2/enhancement/status")
async def get_enhancement_status():
    """获取 RAG 增强模块的实时状态与性能指标。

    返回各模块（parallel_retrieval / hybrid_search / reranker /
    query_rewrite / hyde / result_cache）的启用状态与统计信息，
    用于运维诊断与灰度发布验证。
    """
    try:
        engine = _get_rag_engine()
        return engine.get_enhancement_status()
    except (RuntimeError, OSError, ValueError, AttributeError) as e:
        logger.exception("Failed to get enhancement status")
        _raise_internal(
            e, context="rag.v2.enhancement_status", fallback="获取增强状态失败"
        )


@router.get("/v2/cache/stats")
async def get_cache_stats():
    """获取检索结果 LRU 缓存的命中统计。

    用于判断缓存效果与容量是否需要调整。
    """
    try:
        engine = _get_rag_engine()
        return engine._cache.stats()
    except (RuntimeError, AttributeError) as e:
        logger.exception("Failed to get cache stats")
        _raise_internal(e, context="rag.v2.cache_stats", fallback="获取缓存统计失败")


@router.delete("/v2/cache")
async def clear_cache():
    """清空检索结果 LRU 缓存。

    在知识库内容更新后调用，避免返回过期的缓存结果。
    """
    try:
        engine = _get_rag_engine()
        engine.clear_cache()
        return {"cleared": True, "message": "检索结果缓存已清空"}
    except (RuntimeError, AttributeError) as e:
        logger.exception("Failed to clear cache")
        _raise_internal(e, context="rag.v2.cache_clear", fallback="清空缓存失败")


@router.post("/v2/evaluation")
def run_evaluation(
    top_k: int = Query(3, ge=1, le=10, description="每条查询返回的文档数"),
    category: str | None = Query(None, description="仅评估指定类别"),
    difficulty: str | None = Query(None, description="仅评估指定难度"),
    use_rag_engine: bool = Query(
        False,
        description="True 使用完整 RAG pipeline，False 使用 baseline",
    ),
):
    """运行检索质量评估。

    评估 60 条标准查询的 precision / recall / F1 / MRR / nDCG /
    top3 / top5 准确率，并按类别汇总性能。

    注意：此端点为同步阻塞操作（底层 ChromaDB 调用非异步），
    FastAPI 会自动将普通 ``def`` 路由放到线程池执行，不会阻塞事件循环。
    60 条查询的 baseline 评估约耗时 5-15 秒，启用 RAG engine 后可能
    因 reranker 推理增加 30-90 秒。
    """
    try:
        evaluator = _get_evaluator(use_rag_engine=use_rag_engine)
        report = evaluator.evaluate_all(
            top_k=top_k, category=category, difficulty=difficulty
        )
        return report.to_dict()
    except (RuntimeError, OSError, ValueError) as e:
        logger.exception("Evaluation failed")
        _raise_internal(e, context="rag.v2.evaluation", fallback="评估运行失败")


@router.post("/v2/ablation")
def run_ablation_study(
    top_k: int = Query(3, ge=1, le=10, description="每条查询返回的文档数"),
    category: str | None = Query(None, description="仅评估指定类别"),
    difficulty: str | None = Query(None, description="仅评估指定难度"),
):
    """运行 ablation study，逐项关闭增强模块，量化各模块贡献。

    实验配置（6 组）：
    1. baseline            - 所有增强关闭
    2. reranker_only       - 仅 Cross-Encoder 重排序
    3. hybrid_only         - 仅混合检索（BM25+Vector RRF）
    4. rewrite_only        - 仅查询改写
    5. parallel_cache_only - 仅并行检索+缓存（性能优化）
    6. full_pipeline       - 全部增强开启

    返回各组配置下的评估指标，用于判断各模块的边际贡献。

    注意：此端点非常耗时（6 组 × 60 条查询），可能需要 5-15 分钟。
    建议在低峰期或离线场景调用。
    """
    try:
        evaluator = _get_evaluator(use_rag_engine=True)
        results = evaluator.run_ablation_study(
            top_k=top_k, category=category, difficulty=difficulty
        )
        return {
            "total_configs": len(results),
            "results": [r.to_dict() for r in results],
        }
    except (RuntimeError, OSError, ValueError) as e:
        logger.exception("Ablation study failed")
        _raise_internal(e, context="rag.v2.ablation", fallback="消融研究运行失败")


@router.post("/v2/comparison")
def generate_comparison_report(
    top_k: int = Query(3, ge=1, le=10, description="每条查询返回的文档数"),
    category: str | None = Query(None, description="仅评估指定类别"),
    difficulty: str | None = Query(None, description="仅评估指定难度"),
    run_ablation: bool = Query(
        True, description="是否运行 ablation study（更全面但更耗时）"
    ),
):
    """生成 baseline vs enhanced A/B 对比报告。

    同时运行 baseline（纯向量检索）与 enhanced（完整 RAG pipeline）评估，
    计算各指标的提升幅度，并可选运行 ablation study 量化各模块贡献。

    返回 ComparisonReport，包含：
    - baseline / enhanced 的完整评估报告
    - 各指标的提升百分比
    - ablation study 结果（可选）
    - 自动生成的结论

    注意：启用 ablation 时总耗时可能超过 10 分钟。
    """
    try:
        evaluator = _get_evaluator(use_rag_engine=True)
        comparison = evaluator.generate_comparison_report(
            top_k=top_k,
            category=category,
            difficulty=difficulty,
            run_ablation=run_ablation,
        )
        return comparison.to_dict()
    except (RuntimeError, OSError, ValueError) as e:
        logger.exception("Comparison report generation failed")
        _raise_internal(
            e, context="rag.v2.comparison", fallback="对比报告生成失败"
        )
