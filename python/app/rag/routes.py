import contextlib
import json
import logging
import os
import tempfile

from fastapi import APIRouter, File, Form, Query, UploadFile

from app.core.response import ErrorCode, error, success
from app.models.schemas import (
    KnowledgeAddRequest,
    KnowledgeDeleteRequest,
    KnowledgeQueryRequest,
)
from app.rag.document_importer import DocumentImportService
from app.rag.evaluation import RetrievalEvaluator
from app.rag.knowledge_base import get_knowledge_base
from app.rag.reranker import RerankerService

router = APIRouter(prefix="/api/knowledge", tags=["Knowledge"])

logger = logging.getLogger(__name__)

_reranker_service = None
_document_import_service = None
_evaluator = None


def get_reranker_service() -> RerankerService:
    global _reranker_service
    if _reranker_service is None:
        _reranker_service = RerankerService(enable_cross_encoder=False)
    return _reranker_service


def get_document_import_service() -> DocumentImportService:
    global _document_import_service
    if _document_import_service is None:
        kb = get_knowledge_base()
        _document_import_service = DocumentImportService(knowledge_base=kb)
    return _document_import_service


def get_evaluator() -> RetrievalEvaluator:
    global _evaluator
    if _evaluator is None:
        kb = get_knowledge_base()
        reranker = get_reranker_service()
        _evaluator = RetrievalEvaluator(knowledge_base=kb, reranker_service=reranker)
    return _evaluator


@router.get("/health")
async def knowledge_health():
    kb = get_knowledge_base()
    count = kb.count()
    return success(data={"status": "healthy", "count": count})


@router.post("/add")
async def add_knowledge(request: KnowledgeAddRequest):
    try:
        kb = get_knowledge_base()
        doc_id = kb.add_knowledge(
            document=request.document,
            metadata=request.metadata,
            doc_id=request.doc_id
        )
        return success(data={"doc_id": doc_id}, message="知识添加成功")
    except Exception as e:
        return error(code=ErrorCode.INTERNAL_ERROR, message=f"添加知识失败: {e!s}")


@router.post("/query")
async def query_knowledge(request: KnowledgeQueryRequest,
                         user_id: str | None = None,
                         enable_rerank: bool = True):
    try:
        kb = get_knowledge_base()
        results = kb.query(query_text=request.query_text, n_results=request.n_results * 2 if enable_rerank else request.n_results)

        if enable_rerank and results.get("documents"):
            reranker = get_reranker_service()

            formatted_results = []
            for i, doc in enumerate(results["documents"]):
                formatted_results.append({
                    "id": results["ids"][i],
                    "document": doc,
                    "metadata": results["metadatas"][i],
                    "distance": results["distances"][i]
                })

            reranked_results = reranker.rerank(
                query=request.query_text,
                results=formatted_results,
                user_id=user_id
            )

            return success(data={
                "results": reranked_results[:request.n_results],
                "reranked": True,
                "total_before_rerank": len(formatted_results),
                "total_after_rerank": len(reranked_results[:request.n_results])
            })

        return success(data=results)
    except Exception as e:
        return error(code=ErrorCode.INTERNAL_ERROR, message=f"查询知识失败: {e!s}")


@router.post("/delete")
async def delete_knowledge(request: KnowledgeDeleteRequest):
    try:
        kb = get_knowledge_base()
        kb.delete(doc_id=request.doc_id)
        return success(message="知识删除成功")
    except Exception as e:
        return error(code=ErrorCode.INTERNAL_ERROR, message=f"删除知识失败: {e!s}")


@router.get("/count")
async def knowledge_count():
    try:
        kb = get_knowledge_base()
        count = kb.count()
        return success(data={"count": count})
    except Exception as e:
        return error(code=ErrorCode.INTERNAL_ERROR, message=f"获取知识数量失败: {e!s}")


@router.post("/init")
async def init_default_knowledge():
    try:
        kb = get_knowledge_base()
        kb.load_default_knowledge()
        return success(data={"count": kb.count()}, message="默认知识库加载完成")
    except Exception as e:
        return error(code=ErrorCode.INTERNAL_ERROR, message=f"加载默认知识失败: {e!s}")


@router.post("/init-extended")
async def init_extended_knowledge():
    try:
        kb = get_knowledge_base()
        from app.rag.extended_knowledge import get_extended_knowledge

        extended_knowledge = get_extended_knowledge()
        stats = {"total": len(extended_knowledge), "success": 0, "skipped": 0, "errors": 0}

        for item in extended_knowledge:
            try:
                kb.add_knowledge(
                    document=item["document"],
                    metadata=item["metadata"],
                    doc_id=item["id"]
                )
                stats["success"] += 1
            except Exception:
                stats["skipped"] += 1

        return success(
            data={
                "count": kb.count(),
                "stats": stats
            },
            message=f"扩展知识库加载完成: 成功 {stats['success']}, 跳过 {stats['skipped']}"
        )
    except Exception as e:
        return error(code=ErrorCode.INTERNAL_ERROR, message=f"加载扩展知识失败: {e!s}")


@router.post("/import-json")
async def import_rag_json():
    try:
        kb = get_knowledge_base()
        stats = kb.load_rag_json_knowledge()
        return success(
            data={
                "count": kb.count(),
                "stats": stats
            },
            message=f"RAG知识库导入完成: 成功 {stats['success']}, 跳过 {stats['skipped']}, 错误 {stats['errors']}"
        )
    except FileNotFoundError as e:
        return error(code=ErrorCode.NOT_FOUND, message=str(e))
    except Exception as e:
        return error(code=ErrorCode.INTERNAL_ERROR, message=f"导入RAG知识库失败: {e!s}")


@router.get("/list")
async def list_knowledge(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    category: str | None = Query(None, description="分类筛选"),
    keyword: str | None = Query(None, description="关键词搜索")
):
    try:
        kb = get_knowledge_base()

        all_docs = kb.collection.get(include=["documents", "metadatas"])

        filtered_docs = []
        for i, (doc, metadata) in enumerate(zip(all_docs["documents"], all_docs["metadatas"], strict=False)):
            doc_id = all_docs["ids"][i]

            if category and metadata.get("category") != category:
                continue

            if keyword and keyword.lower() not in doc.lower():
                doc_keywords = metadata.get("keywords", "")
                if keyword.lower() not in doc_keywords.lower():
                    continue

            filtered_docs.append({
                "doc_id": doc_id,
                "document": doc,
                "metadata": metadata
            })

        total = len(filtered_docs)
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        paginated_docs = filtered_docs[start_idx:end_idx]

        categories = {}
        for metadata in all_docs["metadatas"]:
            cat = metadata.get("category", "未分类")
            categories[cat] = categories.get(cat, 0) + 1

        return success(data={
            "documents": paginated_docs,
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total": total,
                "total_pages": (total + page_size - 1) // page_size
            },
            "categories": categories
        })
    except Exception as e:
        return error(code=ErrorCode.INTERNAL_ERROR, message=f"获取知识列表失败: {e!s}")


@router.get("/categories")
async def get_categories():
    try:
        kb = get_knowledge_base()

        all_docs = kb.collection.get(include=["metadatas"])

        categories = {}
        doc_types = {}

        for metadata in all_docs["metadatas"]:
            cat = metadata.get("category", "未分类")
            categories[cat] = categories.get(cat, 0) + 1

            doc_type = metadata.get("type", "未分类")
            doc_types[doc_type] = doc_types.get(doc_type, 0) + 1

        return success(data={
            "categories": categories,
            "doc_types": doc_types,
            "total": len(all_docs["ids"])
        })
    except Exception as e:
        return error(code=ErrorCode.INTERNAL_ERROR, message=f"获取分类统计失败: {e!s}")


@router.get("/get/{doc_id}")
async def get_knowledge(doc_id: str):
    try:
        kb = get_knowledge_base()

        result = kb.collection.get(ids=[doc_id], include=["documents", "metadatas"])

        if not result["documents"]:
            return error(code=ErrorCode.NOT_FOUND, message=f"知识不存在: {doc_id}")

        return success(data={
            "doc_id": doc_id,
            "document": result["documents"][0],
            "metadata": result["metadatas"][0]
        })
    except Exception as e:
        return error(code=ErrorCode.INTERNAL_ERROR, message=f"获取知识失败: {e!s}")


@router.put("/update/{doc_id}")
async def update_knowledge(doc_id: str, request: KnowledgeAddRequest):
    try:
        kb = get_knowledge_base()

        kb.delete(doc_id=doc_id)

        new_id = kb.add_knowledge(
            document=request.document,
            metadata=request.metadata,
            doc_id=doc_id
        )

        return success(data={"doc_id": new_id}, message="知识更新成功")
    except Exception as e:
        return error(code=ErrorCode.INTERNAL_ERROR, message=f"更新知识失败: {e!s}")


@router.post("/delete-batch")
async def delete_knowledge_batch(doc_ids: list[str]):
    try:
        kb = get_knowledge_base()

        deleted_count = 0
        for doc_id in doc_ids:
            try:
                kb.delete(doc_id=doc_id)
                deleted_count += 1
            except Exception:
                pass

        return success(
            data={"deleted_count": deleted_count},
            message=f"批量删除完成: 成功 {deleted_count}/{len(doc_ids)}"
        )
    except Exception as e:
        return error(code=ErrorCode.INTERNAL_ERROR, message=f"批量删除失败: {e!s}")


@router.post("/import-document")
async def import_document(
    file: UploadFile = File(...),
    category: str | None = Form(None),
    description: str | None = Form(None),
    tags: str | None = Form(None)
):
    try:
        suffix = os.path.splitext(file.filename)[1].lower()
        if suffix not in ['.pdf', '.doc', '.docx', '.md', '.markdown']:
            return error(code=ErrorCode.INVALID_REQUEST,
                        message=f"不支持的文件格式: {suffix}。支持: PDF, DOC, DOCX, MD")

        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp_file:
            content = await file.read()
            tmp_file.write(content)
            tmp_file_path = tmp_file.name

        try:
            import_service = get_document_import_service()

            additional_metadata = {}
            if category:
                additional_metadata["category"] = category
            if description:
                additional_metadata["description"] = description
            if tags:
                additional_metadata["tags"] = [t.strip() for t in tags.split(",")]

            result = import_service.import_document(
                tmp_file_path,
                additional_metadata=additional_metadata
            )

            return success(
                data=result,
                message=f"文档导入成功: {result['chunk_count']} 个知识块"
            )
        finally:
            with contextlib.suppress(Exception):
                os.unlink(tmp_file_path)
    except Exception as e:
        return error(code=ErrorCode.INTERNAL_ERROR, message=f"导入文档失败: {e!s}")


@router.get("/import-history")
async def get_import_history(limit: int = Query(50, ge=1, le=200)):
    try:
        import_service = get_document_import_service()
        history = import_service.get_import_history(limit=limit)
        return success(data={"history": history})
    except Exception as e:
        return error(code=ErrorCode.INTERNAL_ERROR, message=f"获取导入历史失败: {e!s}")


@router.get("/import-stats")
async def get_import_stats():
    try:
        import_service = get_document_import_service()
        stats = import_service.get_document_stats()
        return success(data=stats)
    except Exception as e:
        return error(code=ErrorCode.INTERNAL_ERROR, message=f"获取导入统计失败: {e!s}")


@router.get("/stats")
async def get_knowledge_stats():
    try:
        kb = get_knowledge_base()

        all_docs = kb.collection.get(include=["documents", "metadatas"])

        categories = {}
        doc_types = {}
        sources = {}

        total_doc_length = 0
        for doc, metadata in zip(all_docs["documents"], all_docs["metadatas"], strict=False):
            cat = metadata.get("category", "未分类")
            categories[cat] = categories.get(cat, 0) + 1

            doc_type = metadata.get("type", "未分类")
            doc_types[doc_type] = doc_types.get(doc_type, 0) + 1

            source = metadata.get("source", "unknown")
            sources[source] = sources.get(source, 0) + 1

            total_doc_length += len(doc)

        avg_doc_length = total_doc_length / len(all_docs["documents"]) if all_docs["documents"] else 0

        return success(data={
            "total_count": len(all_docs["ids"]),
            "categories": categories,
            "doc_types": doc_types,
            "sources": sources,
            "avg_document_length": round(avg_doc_length, 2)
        })
    except Exception as e:
        return error(code=ErrorCode.INTERNAL_ERROR, message=f"获取统计信息失败: {e!s}")


@router.post("/export")
async def export_knowledge(
    category: str | None = Query(None, description="导出指定分类"),
    format: str = Query("json", description="导出格式: json或csv")
):
    try:
        kb = get_knowledge_base()

        all_docs = kb.collection.get(include=["documents", "metadatas"])

        export_data = []
        for i, (doc, metadata) in enumerate(zip(all_docs["documents"], all_docs["metadatas"], strict=False)):
            doc_id = all_docs["ids"][i]

            if category and metadata.get("category") != category:
                continue

            export_data.append({
                "doc_id": doc_id,
                "document": doc,
                "metadata": metadata
            })

        if format == "json":
            return success(data={
                "format": "json",
                "count": len(export_data),
                "data": export_data
            })
        else:
            return error(code=ErrorCode.INVALID_REQUEST,
                        message=f"不支持的导出格式: {format}")
    except Exception as e:
        return error(code=ErrorCode.INTERNAL_ERROR, message=f"导出知识失败: {e!s}")


@router.get("/reranker-info")
async def get_reranker_info():
    try:
        reranker = get_reranker_service()
        metrics = reranker.get_performance_metrics()
        return success(data=metrics)
    except Exception as e:
        return error(code=ErrorCode.INTERNAL_ERROR, message=f"获取重排序信息失败: {e!s}")


@router.get("/evaluation/dataset-stats")
async def get_dataset_stats():
    try:
        evaluator = get_evaluator()
        stats = evaluator.dataset.get_stats()
        return success(data=stats)
    except Exception as e:
        return error(code=ErrorCode.INTERNAL_ERROR, message=f"获取评估数据集统计失败: {e!s}")


@router.post("/evaluation/run")
async def run_evaluation(
    top_k: int = Query(3, ge=1, le=10, description="Top-K评估参数"),
    category: str | None = Query(None, description="按分类评估"),
    difficulty: str | None = Query(None, description="按难度评估")
):
    try:
        evaluator = get_evaluator()
        report = evaluator.evaluate_all(top_k=top_k, category=category, difficulty=difficulty)

        return success(
            data={
                "report_id": report.report_id,
                "evaluation_time": report.evaluation_time,
                "total_queries": report.total_queries,
                "top_k": report.top_k,
                "avg_precision": report.avg_precision,
                "avg_recall": report.avg_recall,
                "avg_f1_score": report.avg_f1_score,
                "avg_mrr": report.avg_mrr,
                "avg_ndcg": report.avg_ndcg,
                "top3_accuracy": report.top3_accuracy,
                "performance_target_met": report.performance_target_met,
                "target_accuracy": report.target_accuracy,
                "category_performance": report.category_performance
            },
            message=f"评估完成: Top-{top_k}准确率={report.top3_accuracy:.2%}"
        )
    except Exception as e:
        return error(code=ErrorCode.INTERNAL_ERROR, message=f"运行评估失败: {e!s}")


@router.post("/evaluation/generate-report")
async def generate_evaluation_report(
    top_k: int = Query(3, ge=1, le=10, description="Top-K评估参数"),
    output_path: str | None = Query(None, description="报告输出路径")
):
    try:
        evaluator = get_evaluator()
        report = evaluator.evaluate_all(top_k=top_k)

        if output_path:
            report_text = evaluator.generate_report(report, output_path=output_path)
            return success(
                data={"report_path": output_path},
                message=report_text
            )
        else:
            report_text = evaluator.generate_report(report)
            return success(data={"report": json.loads(report_text)})
    except Exception as e:
        return error(code=ErrorCode.INTERNAL_ERROR, message=f"生成评估报告失败: {e!s}")


@router.get("/evaluation/query/{query_id}")
async def get_evaluation_query(query_id: str):
    try:
        evaluator = get_evaluator()
        query = evaluator.dataset.get_query_by_id(query_id)

        if not query:
            return error(code=ErrorCode.NOT_FOUND, message=f"评估查询不存在: {query_id}")

        return success(data=query.to_dict())
    except Exception as e:
        return error(code=ErrorCode.INTERNAL_ERROR, message=f"获取评估查询失败: {e!s}")


@router.post("/bosch/build")
async def build_bosch_knowledge(data_dir: str = Form(default="python/data/datasets/bosch_cnc")):
    try:
        kb = get_knowledge_base()

        from app.rag.bosch_knowledge_builder import BoschKnowledgeBuilder

        builder = BoschKnowledgeBuilder(data_dir=data_dir, knowledge_base=kb)
        result = builder.build_all()

        return success(
            data={
                **result,
                "knowledge_base_count": kb.count(),
            },
            message=f"Bosch工艺知识构建完成：共 {result['total_entries']} 条知识条目"
        )
    except Exception as e:
        logger.exception("Failed to build Bosch knowledge")
        return error(
            code=ErrorCode.INTERNAL_ERROR,
            message=f"构建Bosch知识失败: {e!s}"
        )


@router.get("/bosch/stats")
async def get_bosch_knowledge_stats():
    try:
        kb = get_knowledge_base()
        all_data = kb.collection.get(include=["metadatas"])

        bosch_entries = []
        for i, meta in enumerate(all_data["metadatas"]):
            if meta.get("source") == "bosch_cnc":
                bosch_entries.append({
                    "id": all_data["ids"][i],
                    "type": meta.get("type", "unknown"),
                    "machine": meta.get("machine", ""),
                    "process": meta.get("process", ""),
                    "category": meta.get("category", "unknown"),
                })

        type_counts: dict[str, int] = {}
        machine_counts: dict[str, int] = {}
        for e in bosch_entries:
            t = e["type"]
            type_counts[t] = type_counts.get(t, 0) + 1
            m = e["machine"]
            if m:
                machine_counts[m] = machine_counts.get(m, 0) + 1

        return success(data={
            "bosch_total": len(bosch_entries),
            "by_type": type_counts,
            "by_machine": machine_counts,
            "entries": bosch_entries[:50],
        })
    except Exception as e:
        logger.exception("Failed to get Bosch stats")
        return error(code=ErrorCode.INTERNAL_ERROR, message=f"获取Bosch统计失败: {e!s}")


@router.delete("/bosch")
async def delete_bosch_knowledge():
    try:
        kb = get_knowledge_base()
        deleted = kb.delete_by_source("bosch_cnc")
        return success(
            data={"deleted_count": deleted, "remaining_total": kb.count()},
            message=f"已清除 {deleted} 条 Bosch 知识条目"
        )
    except Exception as e:
        logger.exception("Failed to delete Bosch knowledge")
        return error(code=ErrorCode.INTERNAL_ERROR, message=f"清除Bosch知识失败: {e!s}")


@router.post("/uniwear/build")
async def build_uniwear_knowledge(
    data_dir: str = Form(default="python/data/uniwear"),
):
    try:
        kb = get_knowledge_base()

        from app.rag.uniwear_knowledge_builder import UniwearKnowledgeBuilder

        builder = UniwearKnowledgeBuilder(knowledge_base=kb, data_dir=data_dir)
        result = builder.build_all()

        return success(
            data={
                **result,
                "knowledge_base_count": kb.count(),
            },
            message=f"Uniwear知识构建完成：共 {result['total_entries']} 条知识条目"
        )
    except ImportError:
        return error(code=ErrorCode.INTERNAL_ERROR, message="Uniwear知识构建模块未安装，请确保 pandas 可用")
    except Exception as e:
        logger.exception("Failed to build Uniwear knowledge")
        return error(code=ErrorCode.INTERNAL_ERROR, message=f"构建Uniwear知识失败: {e!s}")


@router.get("/uniwear/stats")
async def get_uniwear_knowledge_stats():
    try:
        kb = get_knowledge_base()
        all_data = kb.collection.get(include=["metadatas"])

        uniwear_sources = [
            "uniwear", "uniwear-nuaa", "uniwear-phm2010", "cross_source"
        ]
        uniwear_entries = []
        for i, meta in enumerate(all_data["metadatas"]):
            if meta.get("source") in uniwear_sources:
                uniwear_entries.append({
                    "id": all_data["ids"][i],
                    "type": meta.get("type", "unknown"),
                    "source": meta.get("source", "unknown"),
                    "material": meta.get("material", ""),
                    "experiment": meta.get("experiment", ""),
                    "category": meta.get("category", "unknown"),
                })

        source_counts: dict[str, int] = {}
        material_counts: dict[str, int] = {}
        for e in uniwear_entries:
            s = e["source"]
            source_counts[s] = source_counts.get(s, 0) + 1
            m = e["material"]
            if m:
                material_counts[m] = material_counts.get(m, 0) + 1

        return success(data={
            "uniwear_total": len(uniwear_entries),
            "by_source": source_counts,
            "by_material": material_counts,
            "entries": uniwear_entries[:50],
        })
    except Exception as e:
        logger.exception("Failed to get Uniwear stats")
        return error(code=ErrorCode.INTERNAL_ERROR, message=f"获取Uniwear统计失败: {e!s}")


@router.post("/uniwear/retrieval")
async def uniwear_retrieval(
    query: str = Form(..., description="检索查询文本"),
    material: str | None = Form(default=None, description="材料筛选：TC4 或 HRC52"),
    signal_type: str | None = Form(default=None, description="信号类型筛选：vibration, force, acoustic_emission"),
    n_results: int = Form(default=5, ge=1, le=20),
):
    try:
        kb = get_knowledge_base()
        from app.rag.rag_retrieval import RagRetrievalEngine

        engine = RagRetrievalEngine(knowledge_base=kb)

        if material:
            result = engine.retrieve_by_material(
                material=material, query=query, n_results=n_results
            )
        elif signal_type:
            result = engine.retrieve_by_signal_type(
                signal_type=signal_type, query=query, n_results=n_results
            )
        else:
            result = engine.retrieve(query=query, n_results=n_results)

        return success(data=result, message=f"检索完成：命中 {result['results_returned']} 条")
    except Exception as e:
        logger.exception("Uniwear retrieval failed")
        return error(code=ErrorCode.INTERNAL_ERROR, message=f"Uniwear检索失败: {e!s}")


@router.post("/uniwear/cross-source")
async def cross_source_retrieval(
    query: str = Form(..., description="检索查询文本"),
    sources: str | None = Form(default=None, description="数据源列表，逗号分隔"),
    n_results: int = Form(default=10, ge=1, le=20),
):
    try:
        kb = get_knowledge_base()
        from app.rag.rag_retrieval import RagRetrievalEngine

        engine = RagRetrievalEngine(knowledge_base=kb)

        source_list = None
        if sources:
            source_list = [s.strip() for s in sources.split(",")]

        result = engine.retrieve_cross_source(
            query=query, sources=source_list, n_results=n_results
        )

        return success(data=result, message=f"跨源检索完成：搜索 {len(result['sources_queried'])} 个数据源，命中 {result['results_returned']} 条")
    except Exception as e:
        logger.exception("Cross-source retrieval failed")
        return error(code=ErrorCode.INTERNAL_ERROR, message=f"跨源检索失败: {e!s}")


@router.delete("/uniwear")
async def delete_uniwear_knowledge():
    try:
        kb = get_knowledge_base()
        total_deleted = 0
        for source in ["uniwear", "uniwear-nuaa", "uniwear-phm2010", "cross_source"]:
            deleted = kb.delete_by_source(source)
            total_deleted += deleted
        return success(
            data={"deleted_count": total_deleted, "remaining_total": kb.count()},
            message=f"已清除 {total_deleted} 条 Uniwear 知识条目"
        )
    except Exception as e:
        logger.exception("Failed to delete Uniwear knowledge")
        return error(code=ErrorCode.INTERNAL_ERROR, message=f"清除Uniwear知识失败: {e!s}")
