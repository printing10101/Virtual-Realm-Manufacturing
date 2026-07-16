"""颤振预测接入模块 API 路由实现（阶段 5）。

数据流：阶段 4 ChatterParams JSON + material_id
    → ChatterPredictorAdapter 双路径预测：
        路径 A: Tlusty 解析法（compute_stability_limit，工程可用，默认路径）
        路径 B: LTC 神经网络（实验性，chatter_model.pt 不存在时自动回退到路径 A）
        路径 C: 兜底默认值（保守 limit_depth=1.0mm，confidence=0.3）
    → HRC52 材料 pending_calibration 时强制降低置信度（0.8 → 0.5）
    → 工程师审核每个特征的稳定性预测结果（confirmed / rejected / edited）
    → 导出 ChatterReport JSON（供阶段 6 G 代码生成使用）

工业硬约束（项目记忆）：
- 本模块输出 ChatterReport 仅供阶段 6 G 代码生成参考，不可直接用于机床
- 实际加工必须经 CAM 软件（NX/PowerMill/PyCAM）二次校验 + 持证操作员 + 导师签字
- 系统定位「工程师助手」，非「全自动颤振预测器」
- K_s（cutting_force_coeff）直接取自阶段 4，不二次拟合（项目记忆硬约束）
- SUCCEEDED 状态禁止删除（阶段 6 G 代码生成可能已引用其 ChatterReport）
- cam_validation_required 始终 True（项目记忆硬约束，不可关闭）
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from app.auth.permissions import require_permission
from app.config import config
from app.core.response import success, error, ErrorCode
from app.core.safe_errors import safe_error_message

from app.chatter_prediction import (
    ChatterPredictionPipeline,
    ChatterPredictionPipelineError,
    ChatterPredictionTask,
    ChatterPredictionTaskStatus,
    ChatterReviewError,
    ChatterReviewStatus,
    ChatterParamsLoadError,
    FeatureChatterResult,
    PredictionMethod,
    ReviewError,
    build_chatter_disclaimer,
    check_ltc_model_available,
    get_task_store,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/chatter_prediction",
    tags=["Chatter Prediction (Engineer-Assisted LTC Integration)"],
    dependencies=[Depends(require_permission("chatter_prediction:read"))],
)

# pipeline 单例（懒加载，避免模块导入期触发 LTC 模型探测）
_pipeline: ChatterPredictionPipeline | None = None


def _get_pipeline() -> ChatterPredictionPipeline:
    """获取 pipeline 单例。"""
    global _pipeline
    if _pipeline is None:
        _pipeline = ChatterPredictionPipeline(cfg=config.chatter_prediction)
    return _pipeline


def _disclaimer_dict(
    task: ChatterPredictionTask | None = None,
    chatter_report_ready: bool = False,
) -> dict[str, Any]:
    """构造精度告知字段。

    优先用 task 上下文构造（覆盖 mesh / 材料校准状态 / LTC 实际参与比例）；
    无 task 时返回通用默认值（用于 precision_info 端点）。
    """
    if task is not None:
        # HRC52 检测：material_id 命中 PENDING_CALIBRATION_MATERIALS 时强制 pending
        from app.chatter_prediction.predictor_adapter import (
            PENDING_CALIBRATION_MATERIALS,
        )
        material_id_lower = task.material_id.lower()
        material_calibration_status = (
            "pending_calibration"
            if material_id_lower in PENDING_CALIBRATION_MATERIALS
            else "calibrated"
        )

        # 根据 feature_results 统计预测方法分布 + LTC 实际参与比例
        if task.feature_results:
            analytical_count = sum(
                1 for r in task.feature_results
                if r.method == PredictionMethod.ANALYTICAL.value
            )
            nn_count = sum(
                1 for r in task.feature_results
                if r.method == PredictionMethod.NEURAL_NETWORK.value
            )
            fb_count = sum(
                1 for r in task.feature_results
                if r.method == PredictionMethod.FALLBACK.value
            )
            if fb_count > 0:
                prediction_method = "fallback"
            elif nn_count > 0 and analytical_count > 0:
                prediction_method = "mixed"
            elif nn_count > 0:
                prediction_method = "neural_network"
            else:
                prediction_method = "analytical"
            ltc_active_ratio = (
                sum(1 for r in task.feature_results if r.ltc_active)
                / len(task.feature_results)
            )
        else:
            prediction_method = "analytical"
            ltc_active_ratio = 0.0

        return build_chatter_disclaimer(
            mesh_calibrated=task.mesh_calibrated,
            chatter_params_source=task.chatter_params_path,
            material_id=task.material_id,
            material_calibration_status=material_calibration_status,
            precision_tier=task.precision_tier,
            machine_type=task.machine_type,
            prediction_method=prediction_method,
            ltc_model_available=task.ltc_model_available,
            ltc_active_ratio=ltc_active_ratio,
            chatter_report_ready=chatter_report_ready,
        ).to_dict()

    # 无 task 上下文（precision_info 端点默认值）
    ltc_available = check_ltc_model_available()
    return build_chatter_disclaimer(
        mesh_calibrated=config.chatter_prediction.default_mesh_calibrated,
        chatter_params_source="external_upload",
        material_id="unknown",
        material_calibration_status="pending_calibration",
        precision_tier=config.chatter_prediction.precision_tier,
        machine_type=config.chatter_prediction.default_machine_type,
        prediction_method="analytical" if not ltc_available else "mixed",
        ltc_model_available=ltc_available,
        ltc_active_ratio=0.0,
        chatter_report_ready=False,
    ).to_dict()


def _resolve_upstream_calibrated(
    source_cutting_parameters_task_id: str,
) -> tuple[bool, str, str]:
    """从上游阶段 4 任务追溯 mesh 标定状态 + ChatterParams 路径 + 材料 ID。

    精度继承链：阶段 1 image_to_3d → 阶段 2 feature_extraction
              → 阶段 3 parametric_geometry → 阶段 4 cutting_parameters
              → 阶段 5 chatter_prediction（本模块）
    本方法查询阶段 4 任务的 mesh_calibrated / chatter_params_path / material_id，
    避免精度信息断层。仅 SUCCEEDED 状态的阶段 4 任务才被认为是可信来源。

    Returns:
        (calibrated, chatter_params_path, material_id)
        - 上游任务存在且为 SUCCEEDED：(task.mesh_calibrated, chatter_params_path, material_id)
        - 上游任务不存在 / 未完成：(False, "", "")，并记日志
    """
    if not source_cutting_parameters_task_id:
        return False, "", ""

    try:
        from app.cutting_parameters import (
            get_task_store as get_cp_store,
            CuttingParametersTaskStatus,
        )
    except ImportError:
        logger.warning(
            "cutting_parameters 模块未启用，无法追溯上游 mesh_calibrated 状态 "
            "source_cp_task_id=%s，按未标定处理",
            source_cutting_parameters_task_id,
        )
        return False, "", ""

    try:
        cp_task = get_cp_store().get_task(source_cutting_parameters_task_id)
        if cp_task is None:
            logger.warning(
                "上游 cutting_parameters 任务不存在 task_id=%s，按未标定处理",
                source_cutting_parameters_task_id,
            )
            return False, "", ""

        if cp_task.status != CuttingParametersTaskStatus.SUCCEEDED.value:
            logger.warning(
                "上游 cutting_parameters 任务未 SUCCEEDED task_id=%s status=%s，"
                "按未标定处理",
                source_cutting_parameters_task_id,
                cp_task.status,
            )
            return False, "", ""

        return (
            bool(cp_task.mesh_calibrated),
            cp_task.chatter_params_path,
            cp_task.material_id,
        )

    except Exception as e:  # noqa: BLE001 - 上游 store 异常不应阻塞本模块
        safe = safe_error_message(
            e, context="chatter_prediction.resolve_upstream_calibrated"
        )
        logger.warning(
            "查询上游任务异常 source_cp_task_id=%s error_id=%s，按未标定处理",
            source_cutting_parameters_task_id,
            safe.get("error_id"),
        )
        return False, "", ""


# =============================================================================
# 请求 / 响应模型
# =============================================================================


class TaskCreateRequest(BaseModel):
    """创建颤振预测任务请求体。

    输入是阶段 4 任务 ID（追溯用）+ ChatterParams JSON 路径 + 材料 ID。
    若 source_cutting_parameters_task_id 存在且上游任务已 SUCCEEDED，
    本模块会自动从上游任务读取 chatter_params_path / material_id / mesh_calibrated，
    调用方可不显式提供这些字段。
    """

    source_cutting_parameters_task_id: str = Field(
        ...,
        description=(
            "阶段 4 cutting_parameters 任务 ID（用于追溯 ChatterParams 来源 "
            "及查询上游 mesh_calibrated / material_id 状态）。"
            "若上游任务不存在或未完成，必须显式提供 chatter_params_path + material_id。"
        ),
    )
    chatter_params_path: str = Field(
        default="",
        description=(
            "阶段 4 输出的 ChatterParams JSON 路径。"
            "为空时自动从 source_cutting_parameters_task_id 任务中读取。"
            "通常位于 output/cutting_parameters/{cp_task_id}/{cp_task_id}_chatter_params.json。"
        ),
    )
    material_id: str = Field(
        default="",
        description=(
            "材料 ID：al_6061 / ti_tc4 / steel_hrc52 等。"
            "为空时自动从阶段 4 任务中读取。HRC52 触发 pending_calibration 强制降低置信度。"
        ),
    )
    precision_tier: str = Field(
        default="standard",
        description="精度档位（继承自阶段 1/2/3/4）：coarse / standard / high。",
    )
    mesh_calibrated: bool | None = Field(
        default=None,
        description=(
            "上游 mesh 是否已做尺度归一化。"
            "None 时通过 source_cutting_parameters_task_id 自动查询阶段 4 任务。"
        ),
    )
    machine_type: str = Field(
        default="vmc_850",
        description="机床类型标识（仅供追溯，不直接影响预测算法）。",
    )


class TaskCreateResponse(BaseModel):
    task_id: str
    status: str
    source_cutting_parameters_task_id: str
    chatter_params_path: str
    material_id: str
    precision_tier: str
    mesh_calibrated: bool
    machine_type: str
    ltc_model_available: bool
    chatter_disclaimer: dict[str, Any]


class TaskStatusResponse(BaseModel):
    """任务状态响应（含审核进度 + 预测方法分布）。"""

    task_id: str
    status: str
    source_cutting_parameters_task_id: str
    chatter_params_path: str
    material_id: str
    precision_tier: str
    mesh_calibrated: bool
    machine_type: str
    feature_count: int
    predicted_count: int
    analytical_count: int
    neural_network_count: int
    fallback_count: int
    ltc_model_available: bool
    pending_count: int
    confirmed_count: int
    rejected_count: int
    edited_count: int
    cam_validation_required: bool
    chatter_report_path: str
    error_message: str
    created_at: float
    started_at: float
    completed_at: float
    chatter_disclaimer: dict[str, Any]


class TaskListResponse(BaseModel):
    tasks: list[dict[str, Any]]
    total: int


class FeatureChatterResultResponse(BaseModel):
    """单条颤振预测结果的响应。"""

    feature_id: str
    feature_type: str
    material_id: str
    spindle_rpm: float
    axial_depth_mm: float
    limit_depth_mm: float
    stable: bool
    stability_margin: float
    method: str
    ltc_active: bool
    confidence: float
    inference_time_ms: float
    warnings: list[str]
    material_calibration_status: str
    review_status: str
    edited_params: dict[str, Any]
    effective_params: dict[str, Any]
    reviewed_by: str
    reviewed_at: float
    engineer_notes: str
    source_cutting_params_task_id: str
    machine_id: str
    tool_id: str
    cutting_force_coeff: float


class TaskResultResponse(BaseModel):
    """颤振预测任务结果摘要（含全部特征预测结果列表）。"""

    task_id: str
    status: str
    source_cutting_parameters_task_id: str
    material_id: str
    precision_tier: str
    mesh_calibrated: bool
    feature_count: int
    predicted_count: int
    analytical_count: int
    neural_network_count: int
    fallback_count: int
    ltc_model_available: bool
    cam_validation_required: bool
    chatter_report_path: str
    error_message: str | None
    feature_results: list[FeatureChatterResultResponse]
    chatter_disclaimer: dict[str, Any]


class ReviewRequest(BaseModel):
    """工程师审核请求体。"""

    action: str = Field(
        ...,
        description=(
            "审核动作：confirmed（确认预测结果无误）/ "
            "rejected（拒绝该特征，不进入最终 ChatterReport）/ "
            "edited（参数需修正，需同时提供 edited_params）"
        ),
    )
    edited_params: dict[str, Any] | None = Field(
        default=None,
        description=(
            "工程师编辑后的参数。仅 action=edited 时必须提供。"
            "字段可为 limit_depth_mm / axial_depth_mm / stable（0/1）的子集。"
        ),
    )
    engineer_notes: str = Field(
        default="",
        description="工程师备注（可选，便于审计追溯）。",
    )
    reviewed_by: str = Field(
        default="engineer",
        description="审核人标识。",
    )


class ReviewResponse(BaseModel):
    """审核结果响应。"""

    task_id: str
    feature_id: str
    feature_type: str
    review_status: str
    effective_params: dict[str, Any]
    all_reviewed: bool
    task_status: str
    chatter_disclaimer: dict[str, Any]


class ExportChatterReportResponse(BaseModel):
    """导出 ChatterReport 响应（阶段 6 输入）。"""

    task_id: str
    status: str
    source_cutting_parameters_task_id: str
    material_id: str
    feature_count: int
    chatter_report_path: str
    download_url: str
    chatter_report_ready: bool
    chatter_disclaimer: dict[str, Any]


# =============================================================================
# 端点实现
# =============================================================================


@router.get("/precision_info")
async def get_precision_info() -> dict[str, Any]:
    """查询当前精度档位信息、LTC 模型可用性与工业硬门槛（不创建任务）。

    前端在用户进入颤振预测页面前应先调用此端点，向用户展示：
    - 当前精度档位（继承自上游 image_to_3d mesh + feature_extraction + parametric_geometry + cutting_parameters）
    - LTC 神经网络模型可用性（chatter_model.pt 是否存在）
    - 预测方法说明（解析法工程可用，LTC 实验性）
    - 工业生产硬门槛
    - 工程师审核流程说明
    """
    ltc_available = check_ltc_model_available()

    return success(
        data={
            "current_tier": config.chatter_prediction.precision_tier,
            "available_tiers": {
                "coarse": "粗加工档位，大切深 + 低精度，常配合 roughing 使用",
                "standard": "标准档位，平衡切深与精度（默认）",
                "high": "精加工档位，小切深 + 高精度，常配合 finishing 使用",
            },
            "module_parameters": {
                "default_machine_type": config.chatter_prediction.default_machine_type,
                "default_mesh_calibrated": config.chatter_prediction.default_mesh_calibrated,
                "force_analytical": config.chatter_prediction.force_analytical,
                "allow_delete_succeeded": config.chatter_prediction.allow_delete_succeeded,
                "cam_validation_required": config.chatter_prediction.cam_validation_required,
            },
            "ltc_model_available": ltc_available,
            "ltc_model_path": "simulation/chatter/checkpoints/chatter_model.pt",
            "prediction_methods": {
                "analytical": "Tlusty 解析法（compute_stability_limit，工程可用，默认路径）",
                "neural_network": "LTC 神经网络（实验性，chatter_model.pt 存在时启用）",
                "mixed": "解析法 + 神经网络混合（按特征分别走对应路径）",
                "fallback": "兜底默认值（解析法与神经网络均失败，保守 limit_depth=1.0mm）",
            },
            "industrial_hard_gates": [
                "颤振预测基于 Tlusty 解析法 + LTC 神经网络（实验性），稳定性判断必须经工程师审核",
                "良品率要求 0 缺陷容忍，极限切深为理论值，实际加工必须留 20% 安全裕度",
                "工业级配合面公差 0.01mm，颤振预测无法直接达到，需精加工工序",
                "CNC 机床操作需持证操作员，本系统输出的预测结果仅供工艺参考",
                "实际加工需导师签字 + 保险，大一独立项目不可独立完成机床执行环节",
                "CAM 二次校验强制：生成的切削参数必须经 NX/PowerMill/PyCAM 校验后才允许上机床",
                "系统定位「工程师助手」，非「全自动颤振预测器」，最终决策权在工程师",
                "LTC 神经网络路径为实验性，chatter_model.pt 不存在时自动回退到 Tlusty 解析法",
            ],
            "chatter_disclaimer": _disclaimer_dict(),
            "workflow_summary": {
                "step_1": "POST /tasks 创建任务（输入阶段 4 任务 ID + ChatterParams 路径 + 材料 ID）",
                "step_2": "POST /tasks/{task_id}/run 异步触发双路径预测",
                "step_3": "GET /tasks/{task_id} 轮询状态（PENDING → RUNNING → PREDICTED）",
                "step_4": "POST /tasks/{task_id}/review?feature_id=... 工程师逐条审核",
                "step_5": "POST /tasks/{task_id}/export 导出 ChatterReport JSON（→ SUCCEEDED）",
                "step_6": "GET /tasks/{task_id}/chatter_report/download 下载 ChatterReport 供阶段 6 使用",
            },
        },
    )


@router.post(
    "/tasks",
    response_model=TaskCreateResponse,
    summary="创建颤振预测任务",
)
async def create_task(body: TaskCreateRequest) -> dict[str, Any]:
    """创建颤振预测任务。

    创建后状态为 PENDING，需调用 POST /tasks/{task_id}/run 触发执行。

    输入解析优先级：
    1. 若 source_cutting_parameters_task_id 对应的阶段 4 任务已 SUCCEEDED，
       自动读取 chatter_params_path / material_id / mesh_calibrated。
    2. 若上游任务不存在或未完成，必须显式提供 chatter_params_path + material_id。
    3. mesh_calibrated 显式提供时优先采用，否则从上游任务读取（读不到默认 False）。
    """
    # 从上游阶段 4 任务追溯
    (
        upstream_calibrated,
        upstream_chatter_params_path,
        upstream_material_id,
    ) = _resolve_upstream_calibrated(body.source_cutting_parameters_task_id)

    # 解析 chatter_params_path（显式 > 上游 > 报错）
    chatter_params_path = body.chatter_params_path or upstream_chatter_params_path
    if not chatter_params_path:
        return error(
            code=ErrorCode.INVALID_REQUEST,
            message=(
                "chatter_params_path 为空且无法从上游阶段 4 任务读取 "
                f"source_cutting_parameters_task_id={body.source_cutting_parameters_task_id}"
            ),
            suggestion=(
                "请显式提供 chatter_params_path，或确认上游阶段 4 任务已 SUCCEEDED "
                "且已导出 ChatterParams JSON。"
            ),
        )

    # 校验 ChatterParams JSON 文件存在
    if not Path(chatter_params_path).exists():
        return error(
            code=ErrorCode.NOT_FOUND,
            message=f"阶段 4 ChatterParams JSON 不存在 path={chatter_params_path}",
            suggestion="请先在阶段 4 完成审核并导出 ChatterParams JSON。",
        )

    # 解析 material_id（显式 > 上游 > 报错）
    material_id = body.material_id or upstream_material_id
    if not material_id:
        return error(
            code=ErrorCode.INVALID_REQUEST,
            message=(
                "material_id 为空且无法从上游阶段 4 任务读取 "
                f"source_cutting_parameters_task_id={body.source_cutting_parameters_task_id}"
            ),
            suggestion="请显式提供 material_id。",
        )

    # 解析 mesh_calibrated（显式 > 上游 > 默认 False）
    if body.mesh_calibrated is not None:
        mesh_calibrated = bool(body.mesh_calibrated)
    else:
        mesh_calibrated = upstream_calibrated

    try:
        pipeline = _get_pipeline()
        task = pipeline.create_task(
            source_cutting_parameters_task_id=body.source_cutting_parameters_task_id,
            chatter_params_path=chatter_params_path,
            material_id=material_id,
            precision_tier=body.precision_tier,
            mesh_calibrated=mesh_calibrated,
            machine_type=body.machine_type,
        )
    except Exception as e:
        safe = safe_error_message(e, context="chatter_prediction.create_task")
        logger.error(
            "创建任务失败 source_cp_task_id=%s | error_id=%s | exc=%s",
            body.source_cutting_parameters_task_id,
            safe.get("error_id"),
            e,
            exc_info=True,
        )
        return error(
            code=ErrorCode.INTERNAL_ERROR,
            message=safe["message"],
        )

    return success(
        data={
            "task_id": task.task_id,
            "status": task.status,
            "source_cutting_parameters_task_id": task.source_cutting_parameters_task_id,
            "chatter_params_path": task.chatter_params_path,
            "material_id": task.material_id,
            "precision_tier": task.precision_tier,
            "mesh_calibrated": task.mesh_calibrated,
            "machine_type": task.machine_type,
            "ltc_model_available": task.ltc_model_available,
            "chatter_disclaimer": _disclaimer_dict(task=task),
        },
        message=(
            f"任务已创建 task_id={task.task_id}，"
            f"请调用 POST /tasks/{task.task_id}/run 触发执行"
        ),
    )


@router.post(
    "/tasks/{task_id}/run",
    summary="异步触发颤振预测流水线执行",
)
async def run_task(task_id: str) -> dict[str, Any]:
    """异步触发颤振预测流水线执行。

    执行流程：
    1. 加载阶段 4 ChatterParams JSON → 特征列表
    2. ChatterPredictorAdapter.predict_feature() 对每个特征执行双路径预测：
       - 默认走 Tlusty 解析法（工程可用）
       - LTC 神经网络路径仅在 chatter_model.pt 存在时尝试（实验性）
       - HRC52 材料 pending_calibration 时强制降低置信度
    3. 状态置为 PREDICTED（等待工程师审核）

    仅 PENDING / FAILED 状态可触发执行（FAILED 允许重试）。
    """
    store = get_task_store()
    task = store.get_task(task_id)
    if task is None:
        return error(
            code=ErrorCode.NOT_FOUND,
            message=f"任务不存在 task_id={task_id}",
        )

    if task.status not in (
        ChatterPredictionTaskStatus.PENDING.value,
        ChatterPredictionTaskStatus.FAILED.value,
    ):
        return error(
            code=ErrorCode.INVALID_REQUEST,
            message=(
                f"任务状态不允许执行当前操作 status={task.status}。"
                "仅 PENDING / FAILED 状态可触发执行。"
            ),
        )

    # 重试场景：清空错误信息
    if task.status == ChatterPredictionTaskStatus.FAILED.value:
        task.error_message = ""
        store.update_task(task)

    pipeline = _get_pipeline()
    asyncio.create_task(pipeline.run_pipeline(task_id))

    return success(
        data={
            "task_id": task_id,
            "status": ChatterPredictionTaskStatus.RUNNING.value,
            "message": (
                "任务已开始执行，请轮询 GET /tasks/{task_id} 获取状态。"
                "执行完成后状态将变为 PREDICTED，等待工程师审核颤振预测结果。"
            ),
        },
        message="任务已开始执行",
    )


@router.get(
    "/tasks/{task_id}",
    response_model=TaskStatusResponse,
    summary="查询任务状态",
)
async def get_task_status(task_id: str) -> dict[str, Any]:
    """查询任务当前状态、审核进度、ChatterReport 路径、精度告知字段。"""
    store = get_task_store()
    task = store.get_task(task_id)
    if task is None:
        return error(
            code=ErrorCode.NOT_FOUND,
            message=f"任务不存在 task_id={task_id}",
        )

    # 统计审核进度
    pending_count = sum(
        1 for r in task.feature_results
        if r.review_status == ChatterReviewStatus.PENDING.value
    )
    confirmed_count = sum(
        1 for r in task.feature_results
        if r.review_status == ChatterReviewStatus.CONFIRMED.value
    )
    rejected_count = sum(
        1 for r in task.feature_results
        if r.review_status == ChatterReviewStatus.REJECTED.value
    )
    edited_count = sum(
        1 for r in task.feature_results
        if r.review_status == ChatterReviewStatus.EDITED.value
    )

    chatter_report_ready = bool(task.chatter_report_path)

    return success(
        data={
            "task_id": task.task_id,
            "status": task.status,
            "source_cutting_parameters_task_id": task.source_cutting_parameters_task_id,
            "chatter_params_path": task.chatter_params_path,
            "material_id": task.material_id,
            "precision_tier": task.precision_tier,
            "mesh_calibrated": task.mesh_calibrated,
            "machine_type": task.machine_type,
            "feature_count": len(task.feature_results),
            "predicted_count": len(task.feature_results),
            "analytical_count": task.analytical_count,
            "neural_network_count": task.neural_network_count,
            "fallback_count": task.fallback_count,
            "ltc_model_available": task.ltc_model_available,
            "pending_count": pending_count,
            "confirmed_count": confirmed_count,
            "rejected_count": rejected_count,
            "edited_count": edited_count,
            "cam_validation_required": task.cam_validation_required,
            "chatter_report_path": task.chatter_report_path,
            "error_message": task.error_message,
            "created_at": task.created_at,
            "started_at": task.started_at,
            "completed_at": task.completed_at,
            "chatter_disclaimer": _disclaimer_dict(
                task=task, chatter_report_ready=chatter_report_ready
            ),
        },
    )


@router.get(
    "/tasks",
    response_model=TaskListResponse,
    summary="列出最近任务",
)
async def list_tasks(limit: int = 20) -> dict[str, Any]:
    """列出最近的颤振预测任务（按创建时间倒序）。"""
    if limit < 1 or limit > 100:
        limit = max(1, min(100, limit))

    store = get_task_store()
    tasks = store.list_tasks(limit=limit)
    return success(
        data={
            "tasks": [
                {
                    "task_id": t.task_id,
                    "status": t.status,
                    "source_cutting_parameters_task_id": t.source_cutting_parameters_task_id,
                    "material_id": t.material_id,
                    "feature_count": len(t.feature_results),
                    "predicted_count": len(t.feature_results),
                    "analytical_count": t.analytical_count,
                    "neural_network_count": t.neural_network_count,
                    "fallback_count": t.fallback_count,
                    "ltc_model_available": t.ltc_model_available,
                    "precision_tier": t.precision_tier,
                    "mesh_calibrated": t.mesh_calibrated,
                    "machine_type": t.machine_type,
                    "chatter_report_path": t.chatter_report_path,
                    "created_at": t.created_at,
                    "completed_at": t.completed_at,
                }
                for t in tasks
            ],
            "total": len(tasks),
        },
    )


@router.get(
    "/tasks/{task_id}/result",
    response_model=TaskResultResponse,
    summary="获取颤振预测结果列表 + 审核状态",
)
async def get_task_result(task_id: str) -> dict[str, Any]:
    """获取任务结果摘要与完整预测结果列表（含审核状态）。

    仅当任务状态为 PREDICTED / REVIEWED / SUCCEEDED 时可调用。
    返回的每条预测结果包含：
    - feature_id / feature_type / material_id
    - spindle_rpm / axial_depth_mm / limit_depth_mm / stable / stability_margin
    - method（analytical / neural_network / fallback）/ ltc_active / confidence
    - review_status（pending / confirmed / rejected / edited）
    - effective_params（合并 edited_params 后的生效参数）
    - warnings（预测时生成的告警，如 HRC52 pending_calibration / 切深超极限）
    """
    store = get_task_store()
    task = store.get_task(task_id)
    if task is None:
        return error(
            code=ErrorCode.NOT_FOUND,
            message=f"任务不存在 task_id={task_id}",
        )

    allowed_states = {
        ChatterPredictionTaskStatus.PREDICTED.value,
        ChatterPredictionTaskStatus.REVIEWED.value,
        ChatterPredictionTaskStatus.SUCCEEDED.value,
    }
    if task.status not in allowed_states:
        return error(
            code=ErrorCode.INVALID_REQUEST,
            message=(
                f"任务状态 {task.status} 不允许获取结果，"
                f"仅 {sorted(allowed_states)} 状态可获取。"
            ),
            suggestion="请等待状态变为 predicted 后再调用此端点",
        )

    chatter_report_ready = bool(task.chatter_report_path)

    feature_results_data = [
        {
            "feature_id": r.feature_id,
            "feature_type": r.feature_type,
            "material_id": r.material_id,
            "spindle_rpm": r.spindle_rpm,
            "axial_depth_mm": r.axial_depth_mm,
            "limit_depth_mm": r.limit_depth_mm,
            "stable": r.stable,
            "stability_margin": r.stability_margin,
            "method": r.method,
            "ltc_active": r.ltc_active,
            "confidence": r.confidence,
            "inference_time_ms": r.inference_time_ms,
            "warnings": list(r.warnings),
            "material_calibration_status": r.material_calibration_status,
            "review_status": r.review_status,
            "edited_params": dict(r.edited_params),
            "effective_params": r.effective_result(),
            "reviewed_by": r.reviewed_by,
            "reviewed_at": r.reviewed_at,
            "engineer_notes": r.engineer_notes,
            "source_cutting_params_task_id": r.source_cutting_params_task_id,
            "machine_id": r.machine_id,
            "tool_id": r.tool_id,
            "cutting_force_coeff": r.cutting_force_coeff,
        }
        for r in task.feature_results
    ]

    return success(
        data={
            "task_id": task.task_id,
            "status": task.status,
            "source_cutting_parameters_task_id": task.source_cutting_parameters_task_id,
            "material_id": task.material_id,
            "precision_tier": task.precision_tier,
            "mesh_calibrated": task.mesh_calibrated,
            "feature_count": len(task.feature_results),
            "predicted_count": len(task.feature_results),
            "analytical_count": task.analytical_count,
            "neural_network_count": task.neural_network_count,
            "fallback_count": task.fallback_count,
            "ltc_model_available": task.ltc_model_available,
            "cam_validation_required": task.cam_validation_required,
            "chatter_report_path": task.chatter_report_path,
            "error_message": task.error_message or None,
            "feature_results": feature_results_data,
            "chatter_disclaimer": _disclaimer_dict(
                task=task, chatter_report_ready=chatter_report_ready
            ),
        },
    )


@router.post(
    "/tasks/{task_id}/review",
    response_model=ReviewResponse,
    summary="工程师审核单个特征的颤振预测结果",
)
async def review_result(
    task_id: str,
    feature_id: str,
    body: ReviewRequest,
) -> dict[str, Any]:
    """工程师审核单个特征的颤振预测结果。

    本端点是 human-in-the-loop 的核心入口（项目记忆硬约束：
    系统定位「工程师助手」，非「全自动颤振预测器」）。

    审核动作：
    - ``confirmed``: 预测结果（稳定性判断 + 极限切深）无误
    - ``rejected``:  拒绝该特征（不进入最终 ChatterReport）
    - ``edited``:    参数需修正，需同时提供 ``edited_params``
        可编辑字段：limit_depth_mm / axial_depth_mm / stable（0/1）

    当所有特征都被审核（confirmed / rejected / edited）后，
    任务状态自动从 PREDICTED 转为 REVIEWED，
    随后可调用 POST /tasks/{task_id}/export 导出 ChatterReport。

    请求体中 ``feature_id`` 作为查询参数传入，便于 RESTful 路径表达。
    """
    store = get_task_store()
    task = store.get_task(task_id)
    if task is None:
        return error(
            code=ErrorCode.NOT_FOUND,
            message=f"任务不存在 task_id={task_id}",
        )

    if task.status != ChatterPredictionTaskStatus.PREDICTED.value:
        return error(
            code=ErrorCode.INVALID_REQUEST,
            message=(
                f"任务状态 {task.status} 不允许审核，"
                f"仅 {ChatterPredictionTaskStatus.PREDICTED.value} 状态可审核"
            ),
            suggestion="请等待流水线执行完成（状态变为 predicted）后再审核",
        )

    # 校验 action
    valid_actions = {
        ChatterReviewStatus.CONFIRMED.value,
        ChatterReviewStatus.REJECTED.value,
        ChatterReviewStatus.EDITED.value,
    }
    if body.action not in valid_actions:
        return error(
            code=ErrorCode.INVALID_REQUEST,
            message=f"非法 action: {body.action}，应为 {sorted(valid_actions)}",
        )

    # edited 动作必须提供 edited_params
    if body.action == ChatterReviewStatus.EDITED.value and not body.edited_params:
        return error(
            code=ErrorCode.INVALID_REQUEST,
            message="action=edited 时必须提供 edited_params",
            suggestion=(
                "请提供编辑后的参数（字段可为 limit_depth_mm / axial_depth_mm "
                "/ stable（0/1）的子集）"
            ),
        )

    try:
        pipeline = _get_pipeline()
        reviewed_result = pipeline.review_result(
            task_id=task_id,
            feature_id=feature_id,
            review_status=body.action,
            reviewed_by=body.reviewed_by,
            edited_params=body.edited_params,
            engineer_notes=body.engineer_notes,
        )
    except ChatterReviewError as e:
        return error(
            code=ErrorCode.INVALID_REQUEST,
            message=str(e),
        )
    except Exception as e:
        safe = safe_error_message(
            e, context="chatter_prediction.review_result"
        )
        logger.error(
            "审核特征失败 task_id=%s feature_id=%s | error_id=%s | exc=%s",
            task_id,
            feature_id,
            safe.get("error_id"),
            e,
            exc_info=True,
        )
        return error(
            code=ErrorCode.INTERNAL_ERROR,
            message=safe["message"],
        )

    # 重新查询任务状态（review_result 内部可能已将状态置为 REVIEWED）
    task_after = store.get_task(task_id)
    if task_after is None:
        return error(
            code=ErrorCode.INTERNAL_ERROR,
            message="审核后任务丢失，请检查任务存储",
        )

    all_reviewed = all(
        r.review_status != ChatterReviewStatus.PENDING.value
        for r in task_after.feature_results
    )

    return success(
        data={
            "task_id": task_id,
            "feature_id": reviewed_result.feature_id,
            "feature_type": reviewed_result.feature_type,
            "review_status": reviewed_result.review_status,
            "effective_params": reviewed_result.effective_result(),
            "all_reviewed": all_reviewed,
            "task_status": task_after.status,
            "chatter_disclaimer": _disclaimer_dict(task=task_after),
        },
        message=(
            f"特征 {feature_id} 已审核（action={body.action}）。"
            + (
                " 全部特征已审核完毕，可调用 POST /tasks/{task_id}/export "
                "导出 ChatterReport JSON。"
                if all_reviewed
                else " 仍有特征待审核。"
            )
        ),
    )


@router.post(
    "/tasks/{task_id}/export",
    response_model=ExportChatterReportResponse,
    summary="导出 ChatterReport JSON（供阶段 6 G 代码生成）",
)
async def export_chatter_report(task_id: str) -> dict[str, Any]:
    """导出 ChatterReport JSON 文件供阶段 6 G 代码生成使用。

    本端点在所有特征审核完毕（状态 REVIEWED）后调用：
    - 仅导出 confirmed + edited 的特征预测结果（rejected 排除）
    - 写入 {task_id}_chatter_report.json
    - 状态置为 SUCCEEDED

    导出后，可通过 GET /tasks/{task_id}/chatter_report/download 下载 JSON 文件。

    工业硬约束（项目记忆）：
    - 导出的 ChatterReport 仅供阶段 6 G 代码生成参考，不可直接用于机床
    - 实际加工必须经 CAM 软件（NX/PowerMill/PyCAM）二次校验 + 持证操作员 + 导师签字
    - 极限切深为理论值，实际加工必须留 20% 安全裕度
    - cam_validation_required 始终 True（项目记忆硬约束，不可关闭）
    """
    store = get_task_store()
    task = store.get_task(task_id)
    if task is None:
        return error(
            code=ErrorCode.NOT_FOUND,
            message=f"任务不存在 task_id={task_id}",
        )

    if task.status != ChatterPredictionTaskStatus.REVIEWED.value:
        return error(
            code=ErrorCode.INVALID_REQUEST,
            message=(
                f"任务状态 {task.status} 不允许导出，"
                f"仅 {ChatterPredictionTaskStatus.REVIEWED.value} 状态可导出"
            ),
            suggestion="请先完成所有特征的审核（状态变为 reviewed）后再导出",
        )

    try:
        pipeline = _get_pipeline()
        chatter_report_path = pipeline.export_chatter_report(task_id)
    except ChatterPredictionPipelineError as e:
        return error(
            code=ErrorCode.INVALID_REQUEST,
            message=str(e),
        )
    except Exception as e:
        safe = safe_error_message(
            e, context="chatter_prediction.export_chatter_report"
        )
        logger.error(
            "导出 ChatterReport 失败 task_id=%s | error_id=%s | exc=%s",
            task_id,
            safe.get("error_id"),
            e,
            exc_info=True,
        )
        return error(
            code=ErrorCode.INTERNAL_ERROR,
            message=safe["message"],
        )

    # 重新查询任务获取最新状态
    task_after = store.get_task(task_id)
    if task_after is None:
        return error(
            code=ErrorCode.INTERNAL_ERROR,
            message="导出后任务丢失，请检查任务存储",
        )

    download_url = (
        f"/api/v1/chatter_prediction/tasks/{task_id}/chatter_report/download"
    )

    return success(
        data={
            "task_id": task_after.task_id,
            "status": task_after.status,
            "source_cutting_parameters_task_id": task_after.source_cutting_parameters_task_id,
            "material_id": task_after.material_id,
            "feature_count": len(task_after.feature_results),
            "chatter_report_path": chatter_report_path,
            "download_url": download_url,
            "chatter_report_ready": True,
            "chatter_disclaimer": _disclaimer_dict(
                task=task_after, chatter_report_ready=True
            ),
        },
        message=(
            f"ChatterReport 已导出 path={chatter_report_path}。"
            "可通过 download_url 下载，并供阶段 6 G 代码生成使用。"
            "注意：实际加工必须经 CAM 软件二次校验后才允许上机床。"
        ),
    )


@router.get(
    "/tasks/{task_id}/chatter_report/download",
    summary="下载 ChatterReport JSON 文件",
)
async def download_chatter_report(task_id: str) -> FileResponse:
    """下载 ChatterReport JSON 文件（供阶段 6 G 代码生成读取）。

    仅 SUCCEEDED 状态可下载。

    文件结构：
    - task_id / source_cutting_parameters_task_id / material_id
    - cam_validation_required: 始终 True（项目记忆硬约束）
    - method_statistics: {analytical, neural_network, fallback}
    - feature_results: list[dict]
      每条含 feature_id / feature_type / spindle_rpm / axial_depth_mm / limit_depth_mm
      / stable / stability_margin / method / ltc_active / confidence / review_status
      / effective_params / source_cutting_params_task_id / cutting_force_coeff
    - industrial_hard_gates_note: 强制告知工业硬约束
    """
    store = get_task_store()
    task = store.get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail=f"任务不存在 task_id={task_id}")

    if task.status != ChatterPredictionTaskStatus.SUCCEEDED.value:
        raise HTTPException(
            status_code=400,
            detail=(
                f"任务未 SUCCEEDED status={task.status}，无法下载 ChatterReport。"
                "请先完成审核并调用 POST /tasks/{task_id}/export。"
            ),
        )

    if not task.chatter_report_path:
        raise HTTPException(
            status_code=404,
            detail="任务 ChatterReport 路径为空",
        )

    output_path = Path(task.chatter_report_path)
    if not output_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"ChatterReport 文件不存在 path={output_path}",
        )

    return FileResponse(
        path=str(output_path),
        media_type="application/json",
        filename=f"{task_id}_chatter_report.json",
    )


@router.delete(
    "/tasks/{task_id}",
    summary="取消/删除任务",
)
async def delete_task(task_id: str) -> dict[str, Any]:
    """取消或删除颤振预测任务。

    - 非终态任务：将状态置为 CANCELLED 后删除任务元信息
    - 终态任务（FAILED / CANCELLED）：直接删除任务元信息
    - SUCCEEDED 状态任务禁止删除（项目记忆硬约束：阶段 6 G 代码生成可能已引用其 ChatterReport）

    注意：ChatterReport JSON 文件与 workspace 目录不会被自动删除，
    避免误删下游链路已引用的资源。
    """
    store = get_task_store()
    task = store.get_task(task_id)
    if task is None:
        return error(
            code=ErrorCode.NOT_FOUND,
            message=f"任务不存在 task_id={task_id}",
        )

    # SUCCEEDED 状态的任务禁止删除（避免误删阶段 6 已引用的 ChatterReport）
    if task.status == ChatterPredictionTaskStatus.SUCCEEDED.value:
        return error(
            code=ErrorCode.INVALID_REQUEST,
            message=(
                f"任务 {task_id} 已 SUCCEEDED，禁止删除。"
                "ChatterReport 可能已被阶段 6 G 代码生成引用。"
            ),
            suggestion="如确需删除，请先手动清理下游引用，再删除任务",
        )

    # 非终态任务先取消（修改状态后持久化）
    terminal_states = {
        ChatterPredictionTaskStatus.FAILED.value,
        ChatterPredictionTaskStatus.CANCELLED.value,
    }
    if task.status not in terminal_states:
        task.status = ChatterPredictionTaskStatus.CANCELLED.value
        try:
            store.update_task(task)
        except Exception as e:
            safe = safe_error_message(
                e, context="chatter_prediction.delete_task.cancel"
            )
            logger.error(
                "取消任务失败 task_id=%s | error_id=%s | exc=%s",
                task_id,
                safe.get("error_id"),
                e,
                exc_info=True,
            )
            return error(
                code=ErrorCode.INTERNAL_ERROR,
                message=safe["message"],
            )

    # 删除任务
    try:
        deleted = store.delete_task(task_id)
    except ReviewError as e:
        # SUCCEEDED 禁删硬约束在 store 层兜底（API 层已先检查）
        return error(
            code=ErrorCode.INVALID_REQUEST,
            message=str(e),
        )
    except Exception as e:
        safe = safe_error_message(
            e, context="chatter_prediction.delete_task"
        )
        logger.error(
            "删除任务失败 task_id=%s | error_id=%s | exc=%s",
            task_id,
            safe.get("error_id"),
            e,
            exc_info=True,
        )
        return error(
            code=ErrorCode.INTERNAL_ERROR,
            message=safe["message"],
        )

    if not deleted:
        return error(
            code=ErrorCode.NOT_FOUND,
            message=f"任务 {task_id} 删除失败（可能已被并发删除）",
        )

    return success(
        data={
            "task_id": task_id,
            "deleted": True,
            "note": (
                "任务元信息已删除，ChatterReport JSON 文件与 workspace 目录未自动清理，"
                "避免误删下游链路已引用的资源。"
            ),
        },
        message=f"任务 {task_id} 已删除",
    )
