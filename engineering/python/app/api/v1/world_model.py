"""World Model API - 世界模型 REST 接口.

对应 ADR-017（世界模型与 RL 模块）第 8 节：世界模型 REST API 端点。

端点总览（prefix: ``/api/v1/world-model``）：
    GET    /versions              列出世界模型版本（分页 + active_only 过滤）
    GET    /versions/{version}    查询版本详情
    POST   /predict               直接预测（不走工作流，调用 WorldModelService.predict）

权限模型：
    world_model:read   —— 列出版本 / 查询版本详情
    world_model:write  —— 直接预测（触发模型推理，消耗资源）

设计说明
--------
    - ``GET /versions`` 返回分页结构 ``{items, total, limit, offset}``
    - ``POST /predict`` 不持久化预测结果（按需生成，避免大数组膨胀数据库），
      前端如需保存轨迹可走工作流 ``wm_predict_state`` 任务类型
    - 预测端点为同步执行（horizon ≤ 100，单次 < 2s）
    - 服务层异常通过 ``_handle_service_exception`` 统一映射为 API 错误响应
"""
from __future__ import annotations

import logging
from typing import Any, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from app.auth.permissions import require_permission
from app.core.response import ErrorCode, error, success
from app.dependencies import get_world_model_service
from app.contracts.world_model import (
    DEFAULT_HORIZON,
    InvalidStateError,
    MAX_HORIZON,
    MIN_HORIZON,
    ModelNotFoundError,
    PredictionError,
    WorldModelError,
)

logger = logging.getLogger(__name__)

# 骨架修复（2026-08-03 任务B）：原文件缺失 router/logger/域符号导入。
# 补齐骨架但保持未接入（main/router_registry 未引用本文件）。
router = APIRouter(prefix="/api/v1/world-model", tags=["World Model"])




# ---------------------------------------------------------------------------
# Pydantic 请求模型
# ---------------------------------------------------------------------------


class WorldModelPredictRequest(BaseModel):
    """世界模型预测请求体.

    与 ``app.contracts.world_model.WorldModelPredictRequest`` 对齐，
    但使用 Pydantic 以获得自动校验和 OpenAPI 文档。
    """

    current_state: dict[str, float] = Field(
        default_factory=dict,
        description=(
            "当前加工状态（字段名见 StateField，至少包含全部 8 个状态字段）。"
            "融合模式下可为空（由 unified_state 提供状态信息）"
        ),
    )
    candidate_action: dict[str, float] = Field(
        ...,
        description="候选切削参数调整量（字段名见 ActionField，4 个 delta 字段）",
    )
    horizon: int = Field(
        default=DEFAULT_HORIZON,
        ge=MIN_HORIZON,
        le=MAX_HORIZON,
        description=f"预测步长（{MIN_HORIZON}~{MAX_HORIZON}，默认 {DEFAULT_HORIZON}）",
    )
    model_uri: str = Field(
        default="model://world_model/1.0.0",
        min_length=1,
        max_length=256,
        description="世界模型 URI",
    )
    unified_state: Optional[dict[str, Any]] = Field(
        default=None,
        description=(
            "ADR-020 思路 1 融合模式可选输入。包含几何特征（ADR-007）与"
            "动力学状态（ADR-013）的统一状态字典。提供时走融合路径"
            "（GeometryEncoder/DynamicsEncoder/FusionLayer）。"
            "为 None 时走原始 state_dim 字段拼接路径（向后兼容）。"
            "需配合环境变量 WORLD_MODEL_USE_FUSION=true 使用"
        ),
    )


# ---------------------------------------------------------------------------
# 辅助函数
# ---------------------------------------------------------------------------


def _handle_service_exception(e: Exception, *, action: str):
    """统一处理服务层异常 → API 错误响应.

    风格与 explainability.py 对齐。

    Args:
        e: 服务层抛出的异常
        action: 当前操作描述（用于日志）

    Returns:
        error() 响应对象
    """
    if isinstance(e, ModelNotFoundError):
        return error(
            code=ErrorCode.NOT_FOUND,
            message=str(e),
            suggestion="请确认版本号正确，或通过 GET /versions 查看可用版本",
        )
    if isinstance(e, InvalidStateError):
        return error(
            code=ErrorCode.INVALID_REQUEST,
            message=str(e),
            suggestion="请检查 current_state / candidate_action 字段是否完整且为合法数值",
        )
    if isinstance(e, PredictionError):
        return error(
            code=ErrorCode.INTERNAL_ERROR,
            message=str(e),
            suggestion="预测失败：模型权重可能未加载或维度不匹配，请检查 model_uri",
        )
    if isinstance(e, ValueError):
        return error(code=ErrorCode.INVALID_REQUEST, message=str(e))
    if isinstance(e, WorldModelError):
        logger.error("WorldModel error during %s: %s", action, e, exc_info=True)
        return error(code=ErrorCode.INTERNAL_ERROR, message=str(e))
    # 兜底：未识别的异常
    logger.error("Unexpected error during %s: %s", action, e, exc_info=True)
    return error(
        code=ErrorCode.INTERNAL_ERROR,
        message=f"{action} 失败",
        detail=str(e),
    )


# ---------------------------------------------------------------------------
# 端点 1: GET /versions —— 列出世界模型版本
# ---------------------------------------------------------------------------


@router.get("/versions")
async def list_versions(
    active_only: bool = Query(
        False, description="为 true 时仅返回当前激活版本"
    ),
    limit: int = Query(
        50, ge=1, le=500, description="每页数量（1-500，默认 50）"
    ),
    offset: int = Query(0, ge=0, description="偏移量"),
):
    """分页列出世界模型版本.

    返回字段：
        - items: list[dict]（每个版本记录的 to_dict()）
        - total / limit / offset

    权限：``world_model:read``
    """
    service = get_world_model_service()
    try:
        versions, total = await service.list_versions(
            active_only=active_only,
            limit=limit,
            offset=offset,
        )
    except Exception as e:
        return _handle_service_exception(e, action="列出世界模型版本")

    items = [v.to_dict() for v in versions]
    return success(
        data={
            "items": items,
            "total": total,
            "limit": limit,
            "offset": offset,
        },
        message=f"世界模型版本列表已获取（{len(items)} 条）",
    )


# ---------------------------------------------------------------------------
# 端点 2: GET /versions/{version} —— 查询版本详情
# ---------------------------------------------------------------------------


@router.get("/versions/{version}")
async def get_version(version: str):
    """查询世界模型版本详情.

    权限：``world_model:read``
    """
    service = get_world_model_service()
    try:
        version_record = await service.get_version(version)
    except Exception as e:
        return _handle_service_exception(e, action="查询世界模型版本详情")

    return success(
        data=version_record.to_dict(),
        message="世界模型版本详情已获取",
    )


# ---------------------------------------------------------------------------
# 端点 3: POST /predict —— 直接预测（不走工作流）
# ---------------------------------------------------------------------------


@router.post(
    "/predict",
    dependencies=[Depends(require_permission("world_model:write"))],
)
async def predict(request: WorldModelPredictRequest):
    """执行世界模型轨迹预测（不走工作流，直接调用服务层）.

    流程：
        1. Pydantic 自动校验 horizon 范围 / 字段非空
        2. 调用 ``WorldModelService.predict()`` 执行轨迹预测
        3. 返回结构化响应（含 predicted_trajectory / trajectory_metrics / model_info）

    权限：``world_model:write``（触发模型推理，消耗资源）
    """
    service = get_world_model_service()

    # 构造契约层 dataclass（再次校验，与 Pydantic 互补）
    from app.contracts.world_model import WorldModelPredictRequest as _ContractReq

    try:
        contract_req = _ContractReq(
            current_state=request.current_state,
            candidate_action=request.candidate_action,
            horizon=request.horizon,
            model_uri=request.model_uri,
            unified_state=request.unified_state,
        )
    except ValueError as e:
        return error(
            code=ErrorCode.INVALID_REQUEST,
            message=str(e),
            suggestion="请检查 current_state / candidate_action / unified_state 字段",
        )

    try:
        response = await service.predict(contract_req)
    except Exception as e:
        return _handle_service_exception(e, action="世界模型预测")

    payload = response.to_dict()
    return success(
        data=payload,
        message=(
            f"世界模型预测完成: horizon={request.horizon}，"
            f"轨迹步数={len(payload.get('predicted_trajectory', []))}"
        ),
    )


__all__ = ["router"]
