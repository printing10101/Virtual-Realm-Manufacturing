"""Dataset API - 数据集 / 版本 / 血缘 REST 接口.

对应 ADR-005 阶段 2 / core-contracts-design.md 第 4 章。

端点总览：
    GET    /api/v1/datasets                          数据集列表（分页 + 过滤）
    POST   /api/v1/datasets                          创建数据集
    GET    /api/v1/datasets/{dataset_id}             数据集详情（含 schema + 版本概要）
    GET    /api/v1/datasets/{dataset_id}/versions    列出所有版本
    POST   /api/v1/datasets/{dataset_id}/commit      提交一个不可变版本
    GET    /api/v1/datasets/{dataset_id}/read        读取版本内容（流式 JSONL）
    POST   /api/v1/datasets/{dataset_id}/deprecate   废弃某版本
    POST   /api/v1/datasets/lineage                  记录血缘
    GET    /api/v1/datasets/lineage/{target_uri}     查询血缘图（上游/下游可视化）

权限模型：
    dataset:read    —— 查询 / 列表 / 读取
    dataset:write   —— 创建 / 提交版本 / 记录血缘
    dataset:manage  —— 废弃版本
"""

from __future__ import annotations

import json
import logging
from typing import Any, Optional
from urllib.parse import unquote

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.auth.permissions import require_permission
from app.core.response import ErrorCode, error, success
from app.contracts.dataset import DatasetSchema, DatasetStatus, LineageRecord
from app.data.dataset_store import get_dataset_store
from app.data.lineage_store import get_lineage_store, make_lineage_record

logger = logging.getLogger(__name__)


router = APIRouter(
    prefix="/api/v1/datasets",
    tags=["Dataset & Lineage"],
    dependencies=[Depends(require_permission("dataset:read"))],
)


# ---------------------------------------------------------------------------
# Pydantic 请求 / 响应模型
# ---------------------------------------------------------------------------


class SchemaFieldModel(BaseModel):
    type: str
    required: bool = False
    description: str = ""


class DatasetSchemaModel(BaseModel):
    """DatasetSchema 的 API 入参模型。"""

    fields: dict[str, SchemaFieldModel] = Field(default_factory=dict)
    primary_key: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class CreateDatasetRequest(BaseModel):
    """创建数据集请求体。"""

    name: str
    description: str = ""
    schema: DatasetSchemaModel
    owner_id: str


class CommitVersionRequest(BaseModel):
    """提交版本请求体。

    records 为空且 dataset_id 是 TrainingDataLake 适配器时，
    适配器会自动从 lake 加载当前全部 records。
    """

    records: list[dict[str, Any]] = Field(default_factory=list)
    version: Optional[str] = None  # None 自动递增 patch
    lineage: Optional["LineageModel"] = None


class LineageModel(BaseModel):
    """LineageRecord 的 API 入参模型。"""

    target: str
    source_type: str  # task / workflow / manual / external
    source_ref: str
    inputs: list[str] = Field(default_factory=list)
    outputs: list[str] = Field(default_factory=list)
    operation: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


# 解决前向引用
CommitVersionRequest.model_rebuild()


# ---------------------------------------------------------------------------
# 模型转换
# ---------------------------------------------------------------------------


def _schema_from_model(m: DatasetSchemaModel) -> DatasetSchema:
    return DatasetSchema(
        fields={
            name: {
                "type": f.type,
                "required": f.required,
                "description": f.description,
            }
            for name, f in m.fields.items()
        },
        primary_key=list(m.primary_key),
        metadata=dict(m.metadata),
    )


def _lineage_from_model(m: LineageModel) -> LineageRecord:
    return make_lineage_record(
        target=m.target,
        source_type=m.source_type,
        source_ref=m.source_ref,
        inputs=list(m.inputs),
        outputs=list(m.outputs),
        operation=m.operation,
        metadata=dict(m.metadata),
    )


def _version_to_dict(ver: Any) -> dict[str, Any]:
    """DatasetVersion dataclass → dict（用于响应序列化）."""
    return {
        "dataset_id": ver.dataset_id,
        "version": ver.version,
        "status": ver.status.value if isinstance(ver.status, DatasetStatus) else ver.status,
        "content_hash": ver.content_hash,
        "row_count": ver.row_count,
        "size_bytes": ver.size_bytes,
        "created_at": ver.created_at.isoformat() if ver.created_at else None,
        "created_by": ver.created_by,
        "storage_uri": ver.storage_uri,
        "lineage": ver.lineage,
    }


def _lineage_to_dict(rec: LineageRecord) -> dict[str, Any]:
    return {
        "record_id": rec.record_id,
        "target": rec.target,
        "source_type": rec.source_type,
        "source_ref": rec.source_ref,
        "inputs": list(rec.inputs),
        "outputs": list(rec.outputs),
        "operation": rec.operation,
        "timestamp": rec.timestamp.isoformat() if rec.timestamp else None,
        "metadata": dict(rec.metadata),
    }


# ---------------------------------------------------------------------------
# 端点实现
# ---------------------------------------------------------------------------


@router.get("")
async def list_datasets(
    owner_id: Optional[str] = Query(None, description="按 owner 过滤"),
    status: Optional[str] = Query(
        None, description="按状态过滤: draft/published/deprecated/archived"
    ),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
):
    """列出数据集（按 created_at 倒序）。"""
    store = get_dataset_store()
    status_enum: Optional[DatasetStatus] = None
    if status is not None:
        try:
            status_enum = DatasetStatus(status)
        except ValueError as e:
            return error(
                code=ErrorCode.INVALID_REQUEST,
                message=f"非法 status: {status}",
                detail=str(e),
            )
    try:
        items = await store.list_datasets(
            owner_id=owner_id, status=status_enum, limit=limit, offset=offset
        )
    except ValueError as e:
        return error(code=ErrorCode.INVALID_REQUEST, message=str(e))
    return success(data={"items": items, "limit": limit, "offset": offset})


@router.post(
    "",
    dependencies=[Depends(require_permission("dataset:write"))],
)
async def create_dataset(req: CreateDatasetRequest):
    """创建数据集（初始 DRAFT，无版本）。"""
    try:
        schema = _schema_from_model(req.schema)
    except ValueError as e:
        return error(code=ErrorCode.INVALID_REQUEST, message=f"Schema 构造失败: {e}")

    store = get_dataset_store()
    try:
        dataset_id = await store.create(
            name=req.name,
            schema=schema,
            owner_id=req.owner_id,
            description=req.description,
        )
    except ValueError as e:
        return error(code=ErrorCode.INVALID_REQUEST, message=str(e))

    return success(
        data={"dataset_id": dataset_id, "status": "draft"},
        message="数据集已创建",
    )


@router.get("/{dataset_id}")
async def get_dataset(dataset_id: str):
    """获取数据集详情（含 schema 与版本概要）。"""
    store = get_dataset_store()
    try:
        detail = await store.get_dataset(dataset_id)
    except ValueError as e:
        return error(code=ErrorCode.NOT_FOUND, message=str(e))
    return success(data=detail)


@router.get("/{dataset_id}/versions")
async def list_versions(dataset_id: str):
    """列出数据集的所有版本（按创建时间倒序）。"""
    store = get_dataset_store()
    try:
        versions = await store.list_versions(dataset_id)
    except ValueError as e:
        return error(code=ErrorCode.NOT_FOUND, message=str(e))
    return success(data={"items": [_version_to_dict(v) for v in versions]})


@router.post(
    "/{dataset_id}/commit",
    dependencies=[Depends(require_permission("dataset:write"))],
)
async def commit_version(dataset_id: str, req: CommitVersionRequest):
    """提交一个不可变版本。

    - records 为空且 dataset_id 为 lake 适配器时，自动从 lake 加载
    - version=None 自动递增 patch
    """
    store = get_dataset_store()
    lineage_rec: Optional[LineageRecord] = None
    if req.lineage is not None:
        try:
            lineage_rec = _lineage_from_model(req.lineage)
        except ValueError as e:
            return error(
                code=ErrorCode.INVALID_REQUEST,
                message=f"Lineage 构造失败: {e}",
            )

    try:
        version = await store.commit_version(
            dataset_id,
            req.records,
            version=req.version,
            lineage=lineage_rec,
        )
    except ValueError as e:
        return error(code=ErrorCode.INVALID_REQUEST, message=str(e))

    return success(
        data=_version_to_dict(version),
        message=f"版本 {version.version} 已提交",
    )


@router.get("/{dataset_id}/read")
async def read_dataset(
    dataset_id: str,
    version: Optional[str] = Query(None, description="版本号，None 取最新"),
    batch_size: int = Query(1000, ge=1, le=10000),
):
    """读取数据集版本内容（流式 JSONL）.

    返回 ``StreamingResponse``，每行一个 JSON 对象，每 batch 之间 flush。
    """
    store = get_dataset_store()

    async def _stream():
        try:
            async for batch in store.read(
                dataset_id, version, batch_size=batch_size
            ):
                for record in batch:
                    yield json.dumps(record, ensure_ascii=False, default=str) + "\n"
        except ValueError as e:
            # 流式响应中错误以 JSON 行形式给出
            yield json.dumps(
                {"error": "INVALID_REQUEST", "message": str(e)}, ensure_ascii=False
            ) + "\n"
        except FileNotFoundError as e:
            yield json.dumps(
                {"error": "FILE_NOT_FOUND", "message": str(e)}, ensure_ascii=False
            ) + "\n"

    return StreamingResponse(
        _stream(),
        media_type="application/x-ndjson",
        headers={"Cache-Control": "no-cache"},
    )


@router.post(
    "/{dataset_id}/deprecate",
    dependencies=[Depends(require_permission("dataset:manage"))],
)
async def deprecate_version(
    dataset_id: str, version: str = Query(..., description="要废弃的版本号")
):
    """废弃某版本（不可逆，但内容仍可读）。"""
    store = get_dataset_store()
    try:
        await store.deprecate(dataset_id, version)
    except ValueError as e:
        return error(code=ErrorCode.INVALID_REQUEST, message=str(e))
    return success(
        data={"dataset_id": dataset_id, "version": version, "status": "deprecated"},
        message=f"版本 {version} 已废弃",
    )


# ---------------------------------------------------------------------------
# 血缘端点（路径独立，避免与 /datasets/{id} 冲突）
# ---------------------------------------------------------------------------


@router.post(
    "/lineage",
    dependencies=[Depends(require_permission("dataset:write"))],
)
async def record_lineage(req: LineageModel):
    """记录一条血缘。"""
    try:
        rec = _lineage_from_model(req)
    except ValueError as e:
        return error(code=ErrorCode.INVALID_REQUEST, message=str(e))

    lineage_store = get_lineage_store()
    record_id = await lineage_store.record(rec)
    return success(
        data={"record_id": record_id},
        message="血缘已记录",
    )


@router.get("/lineage/{target_uri:path}")
async def get_lineage(
    target_uri: str,
    direction: str = Query("upstream", description="upstream 或 downstream"),
    depth: int = Query(10, ge=1, le=50),
):
    """查询血缘图（target_uri 通过 path 参数传入，自动 URL 解码）。

    返回可视化数据：nodes / edges / records。
    """
    target = unquote(target_uri)
    if direction not in {"upstream", "downstream", "visualize"}:
        return error(
            code=ErrorCode.INVALID_REQUEST,
            message=f"direction 必须为 upstream/downstream/visualize: {direction}",
        )

    lineage_store = get_lineage_store()
    try:
        if direction == "upstream":
            records = await lineage_store.get_upstream(target, depth=depth)
            return success(
                data={
                    "target": target,
                    "direction": "upstream",
                    "records": [_lineage_to_dict(r) for r in records],
                }
            )
        if direction == "downstream":
            records = await lineage_store.get_downstream(target, depth=depth)
            return success(
                data={
                    "target": target,
                    "direction": "downstream",
                    "records": [_lineage_to_dict(r) for r in records],
                }
            )
        # visualize
        graph = await lineage_store.visualize(target)
        return success(data={"target": target, "graph": graph})
    except ValueError as e:
        return error(code=ErrorCode.INVALID_REQUEST, message=str(e))


__all__ = ["router"]
