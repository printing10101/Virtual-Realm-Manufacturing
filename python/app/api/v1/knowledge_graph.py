"""知识图谱查询 REST API。

前缀：``/api/v1/knowledge-graph``

端点：
    - GET  /stats                       图规模统计
    - GET  /nodes/{node_id}             按 ID 取节点
    - GET  /nodes                       列出/搜索节点
    - GET  /edges                       列出/过滤关系
    - GET  /neighbors/{node_id}         N 跳邻居
    - POST /query                       统一查询入口
    - GET  /tools-for-material          业务快捷查询
    - GET  /materials-for-tool          业务快捷查询
    - GET  /process-chain/{feature_id}  业务快捷查询

设计要点：
    - **进程内单例 GraphStore**：避免每个请求都新建实例、重新加载数据库。
    - **懒加载 + 后台预热**：
        * 第一次访问时立即返回（空图也合法，stats 返回 0）。
        * 后台线程异步调用 ``load_from_repository()``，完成后自动替换图。
        * 这保证任何 API 请求都不会被数据库 I/O 阻塞。
    - **线程安全**：用 ``threading.Lock`` 保护单例创建与替换。
    - **统一异常包装**：所有端点用 try-except 把内部异常转为 503，
      避免堆栈信息泄露，与项目其他 API 风格一致。
"""
from __future__ import annotations

import logging
import threading
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.knowledge_graph.graph_store import GraphStore
from app.knowledge_graph.query_api import KnowledgeGraphQueryAPI

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/knowledge-graph", tags=["knowledge-graph"])


# ---------------------------------------------------------------------------
# 进程内单例（懒加载 + 后台预热）
# ---------------------------------------------------------------------------


_query_api_singleton: Optional[KnowledgeGraphQueryAPI] = None
_query_api_lock = threading.Lock()
_warmup_started = False
_warmup_lock = threading.Lock()


def _build_query_api() -> KnowledgeGraphQueryAPI:
    """构造一个 ``auto_load=False`` 的查询门面（绝不阻塞）。"""
    store = GraphStore(auto_load=False)
    return KnowledgeGraphQueryAPI(store)


def _warmup_graph_async() -> None:
    """后台线程：从持久化层加载已有节点/边，替换到单例中。

    关键不变量：即使预热失败或阻塞，请求路径也不会被影响——
    始终有 ``auto_load=False`` 的内存图可用，只是数据可能暂时为空。

    失败后会重置 ``_warmup_started``，下次请求可再次尝试预热，
    避免一次性失败导致图谱永久为空。
    """

    def _runner() -> None:
        global _warmup_started
        try:
            from app.knowledge_graph.repository import (
                get_sync_sessionmaker,
            )
            from app.knowledge_graph.persistence import GraphPersistence

            if get_sync_sessionmaker() is None:
                logger.info("KG warmup: no DB configured, skip")
                # 无 DB 也算正常完成，不需要重置标志
                return
            new_store = GraphStore(auto_load=False)
            persistence = GraphPersistence()
            persistence.load_from_repository(new_store, replace=False)
            # 替换单例：线程安全
            global _query_api_singleton
            with _query_api_lock:
                _query_api_singleton = KnowledgeGraphQueryAPI(new_store)
            n_nodes = new_store.graph().number_of_nodes()
            n_edges = new_store.graph().number_of_edges()
            logger.info(
                "KG warmup done: nodes=%d edges=%d", n_nodes, n_edges
            )
        except (ImportError, OSError, RuntimeError, ValueError, AttributeError) as exc:  # pragma: no cover - 后台线程兜底
            logger.warning("KG warmup failed (non-fatal): %s", exc, exc_info=True)
            # 失败时重置标志，允许下次请求再次尝试预热
            with _warmup_lock:
                _warmup_started = False

    global _warmup_started
    with _warmup_lock:
        if _warmup_started:
            return
        _warmup_started = True
    t = threading.Thread(
        target=_runner, name="kg-warmup", daemon=True
    )
    t.start()


def _get_query_api() -> KnowledgeGraphQueryAPI:
    """延迟实例化，每次请求拿新门面（GraphStore 是单例进程内）。

    第一次访问会立即创建一个空图（不阻塞），并触发后台预热线程
    从数据库加载真实数据；后续请求直接复用已预热的单例。

    使用双检锁模式：先无锁读，命中则直接返回；未命中再加锁二次检查，
    避免每次请求都争抢锁。预热完成后单例会被替换，无锁读也能拿到最新值。
    """
    global _query_api_singleton
    # 第一次无锁读（命中即返回，性能优先）
    if _query_api_singleton is not None:
        return _query_api_singleton
    # 未命中，加锁二次检查
    with _query_api_lock:
        if _query_api_singleton is None:
            _query_api_singleton = _build_query_api()
            _warmup_graph_async()
        return _query_api_singleton


# ---------------------------------------------------------------------------
# Pydantic 请求模型
# ---------------------------------------------------------------------------


class GraphQueryRequest(BaseModel):
    """``POST /query`` 请求体模型。

    用 Pydantic 验证替代原始 dict，避免 ``**params`` 解包触发 TypeError。
    """

    query_type: str = Field(..., description="查询类型，如 search_nodes")
    params: dict[str, Any] = Field(
        default_factory=dict, description="查询参数键值对"
    )


# ---------------------------------------------------------------------------
# 端点
# ---------------------------------------------------------------------------


@router.get("/stats")
def get_stats() -> dict[str, Any]:
    """图规模统计。"""
    try:
        return _get_query_api().stats()
    except (ValueError, KeyError, TypeError, OSError, RuntimeError, AttributeError) as exc:
        logger.exception("KG /stats failed")
        raise HTTPException(
            status_code=503,
            detail="knowledge graph temporarily unavailable",
        ) from exc


@router.get("/nodes/{node_id}")
def get_node(node_id: str) -> dict[str, Any]:
    """按 ID 取节点。"""
    try:
        node = _get_query_api().node(node_id)
    except (ValueError, KeyError, TypeError, OSError, RuntimeError, AttributeError) as exc:
        logger.exception("KG /nodes/{node_id} failed: %s", node_id)
        raise HTTPException(
            status_code=503,
            detail="knowledge graph temporarily unavailable",
        ) from exc
    if node is None:
        raise HTTPException(status_code=404, detail=f"node not found: {node_id}")
    return node


@router.get("/nodes")
def list_nodes(
    type: Optional[str] = Query(None, description="节点类型，如 material / tool"),
    pattern: Optional[str] = Query(None, description="ID 通配符（%/_)"),
    limit: int = Query(200, ge=1, le=2000),
) -> dict[str, Any]:
    """列出/搜索节点。"""
    try:
        api = _get_query_api()
        if pattern is not None:
            nodes = api.search_nodes(
                id_pattern=pattern, node_type=type, limit=limit
            )
        else:
            nodes = api.nodes_by_type(type or "", limit=limit)
    except (ValueError, KeyError, TypeError, OSError, RuntimeError, AttributeError) as exc:
        logger.exception("KG /nodes failed")
        raise HTTPException(
            status_code=503,
            detail="knowledge graph temporarily unavailable",
        ) from exc
    return {"count": len(nodes), "nodes": nodes}


@router.get("/edges")
def list_edges(
    edge_type: Optional[str] = Query(None, description="关系类型，如 SUITABLE_FOR"),
    source_id: Optional[str] = Query(None, description="源节点 ID"),
    target_id: Optional[str] = Query(None, description="目标节点 ID"),
    min_confidence: float = Query(0.0, ge=0.0, le=1.0),
    max_confidence: float = Query(1.0, ge=0.0, le=1.0),
    limit: int = Query(200, ge=1, le=5000),
) -> dict[str, Any]:
    """列出/过滤关系。"""
    try:
        edges = _get_query_api().edges(
            edge_type=edge_type,
            source_id=source_id,
            target_id=target_id,
            min_confidence=min_confidence,
            max_confidence=max_confidence,
            limit=limit,
        )
    except (ValueError, KeyError, TypeError, OSError, RuntimeError, AttributeError) as exc:
        logger.exception("KG /edges failed")
        raise HTTPException(
            status_code=503,
            detail="knowledge graph temporarily unavailable",
        ) from exc
    return {"count": len(edges), "edges": edges}


@router.get("/neighbors/{node_id}")
def get_neighbors(
    node_id: str,
    max_hops: int = Query(1, ge=1, le=5),
    limit: int = Query(200, ge=1, le=2000),
) -> dict[str, Any]:
    """N 跳邻居。"""
    try:
        api = _get_query_api()
        if not api.node(node_id):
            raise HTTPException(
                status_code=404, detail=f"node not found: {node_id}"
            )
        neighbors = api.neighbors(
            node_id, max_hops=max_hops, limit=limit
        )
    except HTTPException:
        raise
    except (ValueError, KeyError, TypeError, OSError, RuntimeError, AttributeError) as exc:
        logger.exception("KG /neighbors/{node_id} failed: %s", node_id)
        raise HTTPException(
            status_code=503,
            detail="knowledge graph temporarily unavailable",
        ) from exc
    return {"count": len(neighbors), "neighbors": neighbors}


@router.post("/query")
def post_query(payload: GraphQueryRequest) -> dict[str, Any]:
    """统一查询入口。

    Body::

        {
          "query_type": "search_nodes",
          "params": {"id_pattern": "tool-%", "node_type": "tool"}
        }
    """
    qt = payload.query_type
    if not qt:
        raise HTTPException(status_code=400, detail="query_type is required")
    params = payload.params or {}
    try:
        return _get_query_api().query(qt, **params)
    except TypeError as exc:
        # 参数不匹配：返回 400 而非 500
        raise HTTPException(
            status_code=400,
            detail=f"invalid query params for '{qt}': {exc}",
        ) from exc
    except (ValueError, KeyError, TypeError, OSError, RuntimeError, AttributeError) as exc:
        logger.exception("KG /query failed: %s", qt)
        raise HTTPException(
            status_code=503,
            detail="knowledge graph temporarily unavailable",
        ) from exc


@router.get("/tools-for-material")
def get_tools_for_material(
    material_id: str = Query(..., description="材料节点 ID"),
    min_confidence: float = Query(0.0, ge=0.0, le=1.0),
    limit: int = Query(50, ge=1, le=500),
) -> dict[str, Any]:
    """某材料适配的所有刀具。"""
    try:
        items = _get_query_api().tools_for_material(
            material_id, min_confidence=min_confidence, limit=limit
        )
    except (ValueError, KeyError, TypeError, OSError, RuntimeError, AttributeError) as exc:
        logger.exception("KG /tools-for-material failed: %s", material_id)
        raise HTTPException(
            status_code=503,
            detail="knowledge graph temporarily unavailable",
        ) from exc
    return {"count": len(items), "items": items}


@router.get("/materials-for-tool")
def get_materials_for_tool(
    tool_id: str = Query(..., description="刀具节点 ID"),
    min_confidence: float = Query(0.0, ge=0.0, le=1.0),
    limit: int = Query(50, ge=1, le=500),
) -> dict[str, Any]:
    """某刀具能加工的所有材料。"""
    try:
        items = _get_query_api().materials_for_tool(
            tool_id, min_confidence=min_confidence, limit=limit
        )
    except (ValueError, KeyError, TypeError, OSError, RuntimeError, AttributeError) as exc:
        logger.exception("KG /materials-for-tool failed: %s", tool_id)
        raise HTTPException(
            status_code=503,
            detail="knowledge graph temporarily unavailable",
        ) from exc
    return {"count": len(items), "items": items}


@router.get("/process-chain/{feature_id}")
def get_process_chain(
    feature_id: str,
    max_hops: int = Query(3, ge=1, le=5),
) -> dict[str, Any]:
    """某 feature 的工艺链。"""
    try:
        api = _get_query_api()
        if not api.node(feature_id):
            raise HTTPException(
                status_code=404, detail=f"node not found: {feature_id}"
            )
        chain = api.process_chain(feature_id, max_hops=max_hops)
    except HTTPException:
        raise
    except (ValueError, KeyError, TypeError, OSError, RuntimeError, AttributeError) as exc:
        logger.exception("KG /process-chain/{feature_id} failed: %s", feature_id)
        raise HTTPException(
            status_code=503,
            detail="knowledge graph temporarily unavailable",
        ) from exc
    return {"count": len(chain), "chain": chain}


__all__ = ["router"]
