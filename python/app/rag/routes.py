from fastapi import APIRouter

from app.core.response import success, error, ErrorCode
from app.models.schemas import KnowledgeAddRequest, KnowledgeQueryRequest, KnowledgeDeleteRequest
from app.rag.knowledge_base import get_knowledge_base

router = APIRouter(prefix="/api/knowledge", tags=["Knowledge"])


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
        return error(code=ErrorCode.INTERNAL_ERROR, message=f"添加知识失败: {str(e)}")


@router.post("/query")
async def query_knowledge(request: KnowledgeQueryRequest):
    try:
        kb = get_knowledge_base()
        results = kb.query(query_text=request.query_text, n_results=request.n_results)
        return success(data=results)
    except Exception as e:
        return error(code=ErrorCode.INTERNAL_ERROR, message=f"查询知识失败: {str(e)}")


@router.post("/delete")
async def delete_knowledge(request: KnowledgeDeleteRequest):
    try:
        kb = get_knowledge_base()
        kb.delete(doc_id=request.doc_id)
        return success(message="知识删除成功")
    except Exception as e:
        return error(code=ErrorCode.INTERNAL_ERROR, message=f"删除知识失败: {str(e)}")


@router.get("/count")
async def knowledge_count():
    try:
        kb = get_knowledge_base()
        count = kb.count()
        return success(data={"count": count})
    except Exception as e:
        return error(code=ErrorCode.INTERNAL_ERROR, message=f"获取知识数量失败: {str(e)}")


@router.post("/init")
async def init_default_knowledge():
    try:
        kb = get_knowledge_base()
        kb.load_default_knowledge()
        return success(data={"count": kb.count()}, message="默认知识库加载完成")
    except Exception as e:
        return error(code=ErrorCode.INTERNAL_ERROR, message=f"加载默认知识失败: {str(e)}")


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
        return error(code=ErrorCode.INTERNAL_ERROR, message=f"导入RAG知识库失败: {str(e)}")
