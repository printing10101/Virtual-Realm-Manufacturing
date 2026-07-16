"""LNN API 路由定义。"""

import os
import uuid
import asyncio
import logging
import threading
from typing import Optional
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import torch  # /device/info、/device/status、/device/clear-cache 端点需要

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.responses import StreamingResponse

from app.core.response import ErrorCode, error, success
from app.core.safe_errors import safe_error_message
from app.auth.permissions import require_permission
from app.api.v1.auth import get_current_user
from app.core.api_response import api_response
from app.audit.audit_log import AIModule, UserDecision, OperationStatus
from app.utils.ring_buffer import get_ring_log_buffer
from app.utils.utils import validate_user_path
from app.middleware.rate_limiter import limiter
from app.models.schemas import (
    LNNPredictRequest,
    LNNTrainRequest,
    LNNModelInfo,
    LNNQuantizeRequest,
    LNNModelSizeResponse,
    LNNTrainDryRunRequest,
    LNNTrainDryRunResponse,
    TrainingPlanSummary,
    LNNBatchInferenceRequest,
    LNNStreamPredictRequest,
    LNNWindowedPredictRequest,
    LNNStreamingConfig,
)
from app.tasks.task_manager import TaskType, TaskStatus
from app.ai.lnn.inference.predictor import LNNPredictor, PredictionResult
from app.ai.lnn.inference.registry import (
    is_quantized_model,
    get_quantized_model_name,
)
from app.ai.lnn.training.device_manager import (
    detect_device,
    get_available_devices,
    get_device_status,
    clear_gpu_memory,
)
from app.api.v1.sse import sse_manager

from app.api.v1.lnn.dependencies import (
    model_registry,
    pytorch_registry,
    model_cache,
    training_tasks,
    audit_log,
    task_manager,
    MAX_CONCURRENT_TRAINING_TASKS,
    _active_training_tasks,
)
from app.api.v1.lnn.services import (
    _generate_prediction_reasoning,
    _generate_alternatives,
    _broadcast_error,
    _run_training_task_async,
    _broadcast_training_events,
    _run_quantization_task_v2,
    _format_size,
    run_batch_inference_v2,
    sse_event_generator,
)

logger = logging.getLogger(__name__)

# 修复 [B10] /train/dry_run 路径遍历：允许的数据文件根目录白名单。
# 1. python/data/ —— 项目内置训练/校准数据目录（含 uniwear/、training_data/ 等）；
# 2. 项目根目录 —— 兼容从仓库内 fixtures 目录加载数据；
# 3. 环境变量 LNN_DATA_BASE_DIRS 注入的额外目录（多路径用 os.pathsep 分隔）。
# 任意 data_path 在 resolve() 后必须位于以下根目录之一，否则视为路径遍历攻击。
_ALLOWED_DATA_BASE_DIRS: list[Path] = [
    Path(os.getenv("LNN_DATA_DIR", Path(__file__).resolve().parents[3] / "data")).resolve(),
    Path(__file__).resolve().parents[4],  # python/ 项目根
]
_extra_data_dirs = os.getenv("LNN_DATA_BASE_DIRS", "")
if _extra_data_dirs:
    for _d in _extra_data_dirs.split(os.pathsep):
        _d = _d.strip()
        if _d:
            _ALLOWED_DATA_BASE_DIRS.append(Path(_d).resolve())


def _validate_data_path(user_path: str) -> Path:
    """校验 /train/dry_run 接收的数据文件路径，防止路径遍历攻击。

    修复 [B10]：原端点直接将 ``request.data_path`` 透传给 ``np.loadtxt()``，
    攻击者可构造 ``/etc/passwd``、``../../../app.db`` 等任意路径读取服务器文件。
    本函数委托给统一的 ``app.utils.utils.validate_user_path``，在 ``resolve()``
    后强制校验绝对路径必须位于 ``_ALLOWED_DATA_BASE_DIRS`` 之一之下，并要求
    扩展名为常见数据文件类型，从而将可读取范围严格限制在数据目录内。

    Args:
        user_path: 用户提交的数据文件路径（相对或绝对）

    Returns:
        校验通过后的 Path 对象

    Raises:
        HTTPException: 400 当路径为空、扩展名不允许或解析后超出允许目录范围
    """
    # 允许的数据文件扩展名白名单（避免读取 .py、.db 等敏感文件）
    _allowed_exts = {".csv", ".txt", ".tsv", ".dat", ".json", ".jsonl", ".npy"}
    try:
        return validate_user_path(
            user_path=user_path,
            allowed_base_dirs=_ALLOWED_DATA_BASE_DIRS,
            allowed_extensions=_allowed_exts,
            project_root=_ALLOWED_DATA_BASE_DIRS[1],
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=safe_error_message(exc, fallback="请求参数无效", context="lnn.routes")) from exc


router = APIRouter(
    prefix="/api/v1/lnn",
    tags=["LNN Models"],
    dependencies=[Depends(require_permission("lnn:read"))],
)

# 训练队列(模块级状态) —— 修复 P0-10：添加 TTL 清理与线程安全锁
# job_id -> {"cancel": asyncio.Event, "progress": asyncio.Queue, "created_at": datetime}
_TRAINING_QUEUES: dict = {}
_TRAINING_QUEUES_LOCK = threading.Lock()
_TRAINING_QUEUE_TTL = timedelta(hours=1)


def _cleanup_training_queues() -> None:
    """清理超过 TTL 的训练队列，防止内存泄漏。

    在添加新队列时顺便调用，惰性清理策略避免引入后台定时任务。
    """
    now = datetime.utcnow()
    expired = [
        job_id
        for job_id, info in _TRAINING_QUEUES.items()
        if now - info.get("created_at", now) > _TRAINING_QUEUE_TTL
    ]
    for job_id in expired:
        _TRAINING_QUEUES.pop(job_id, None)
        logger.info("清理过期训练队列: %s", job_id)


def _log_task_exception(task: asyncio.Task, context: str) -> None:
    """记录后台任务未捕获异常，避免静默失败。"""
    if task.cancelled():
        logger.debug("Task %s cancelled", context)
    elif task.exception():
        logger.error(
            "Task %s failed: %s",
            context,
            task.exception(),
        )


@router.post("/predict", dependencies=[Depends(require_permission("lnn:write"))])
@limiter.limit("60/minute")
async def predict_lnn(request: Request, body: LNNPredictRequest):
    try:
        entry = model_registry.registry.get(body.model_name)
        if not entry:
            return error(
                code=ErrorCode.NOT_FOUND,
                message=f"Model '{body.model_name}' not found",
            )

        model_info = entry.info

        if not body.input_data:
            return error(
                code=ErrorCode.INVALID_REQUEST,
                message="输入数据必须为非空列表",
            )

        if any(not isinstance(x, (int, float)) for x in body.input_data):
            return error(
                code=ErrorCode.INVALID_REQUEST,
                message="输入数据必须为数值类型",
            )

        expected_dim = (
            len(model_info.input_features) if model_info.input_features else None
        )
        if expected_dim:
            input_len = len(body.input_data)
            if input_len != expected_dim and input_len % expected_dim != 0:
                return error(
                    code=ErrorCode.INVALID_REQUEST,
                    message=f"输入维度不匹配: 期望{expected_dim}维或其倍数,实际{input_len}维",
                )

        predictor = model_cache.get(body.model_name)
        if predictor is None:
            predictor = LNNPredictor.from_registry(
                registry=model_registry,
                model_name=body.model_name,
                use_amp=True,
                auto_device=True,
            )
            model_cache.put(body.model_name, predictor)

        try:
            result = predictor.predict(
                input_data=body.input_data,
                return_confidence=body.return_confidence,
            )
        except (ValueError, KeyError, TypeError, AttributeError, RuntimeError, OSError) as model_err:
            safe = safe_error_message(
                model_err,
                context=f"lnn.predict_inference[{body.model_name}]",
            )
            logger.error(
                "Model inference error | model=%s | error_id=%s | exc=%s",
                body.model_name,
                safe.get("error_id"),
                model_err,
                exc_info=True,
            )
            get_ring_log_buffer().append(
                "ai_inference",
                level="ERROR",
                message=f"Model '{body.model_name}' inference failed",
                data={
                    "error_id": safe.get("error_id"),
                    "model": body.model_name,
                },
            )
            return error(
                code=ErrorCode.INTERNAL_ERROR,
                message=safe["message"],
                detail=safe.get("detail"),
            )

        if not isinstance(result, PredictionResult):
            result = PredictionResult(
                value=result,
                confidence=0.0,
                inference_time=0.0,
            )

        value = result.value
        if hasattr(value, "tolist"):
            value = value.tolist()
        if isinstance(value, list) and len(value) == 1:
            value = value[0]
        confidence = result.confidence if body.return_confidence else None
        inference_time = result.inference_time

        reasoning = _generate_prediction_reasoning(
            model_name=body.model_name,
            input_data=body.input_data,
            prediction=value,
            confidence=confidence,
            inference_time=inference_time,
        )

        alternatives = _generate_alternatives(
            model_name=body.model_name,
            input_data=body.input_data,
            primary_value=value,
            primary_confidence=confidence if confidence else 0.0,
        )

        model_info_response = LNNModelInfo(
            name=model_info.name,
            version=model_info.version,
            last_updated=datetime.now().isoformat(),
        )

        response_data = {
            "value": value,
            "inference_time": inference_time,
            "model_info": model_info_response.model_dump(),
            "reasoning": reasoning,
            "alternatives": [alt.model_dump() for alt in alternatives],
        }
        if confidence is not None:
            response_data["confidence"] = confidence

        audit_log.log_decision(
            ai_module=AIModule.LNN_PREDICT,
            ai_recommendation={
                "model_name": body.model_name,
                "prediction": value,
                "confidence": confidence,
                "alternatives": [alt.model_dump() for alt in alternatives],
            },
            user_decision=UserDecision.AUTO_EXECUTED,
            final_execution={"prediction": value},
            operation_status=OperationStatus.SUCCESS,
            input_parameters={
                "model_name": body.model_name,
                "input_data": body.input_data,
                "return_confidence": body.return_confidence,
            },
            confidence=confidence,
            reasoning=reasoning,
        )

        get_ring_log_buffer().append(
            "ai_inference",
            level="INFO",
            message=f"Model '{body.model_name}' prediction completed",
            data={
                "model": body.model_name,
                "inference_time_ms": inference_time,
                "input_size": len(body.input_data)
                if isinstance(body.input_data, list)
                else 1,
            },
        )

        return success(data=response_data, message="Prediction completed successfully")

    except KeyError:
        get_ring_log_buffer().append(
            "ai_inference",
            level="WARN",
            message=f"Model '{body.model_name}' not found",
            data={"model": body.model_name},
        )
        return error(
            code=ErrorCode.NOT_FOUND,
            message=f"Model '{body.model_name}' not found in registry",
        )
    except (ValueError, TypeError, OSError, RuntimeError, AttributeError) as e:
        get_ring_log_buffer().append(
            "ai_inference",
            level="ERROR",
            message=f"Model '{body.model_name}' unexpected error",
            data={"model": body.model_name, "error_id": None},
        )
        safe = safe_error_message(
            e,
            context=f"lnn.predict[{body.model_name}]",
        )
        get_ring_log_buffer().append(
            "ai_inference",
            level="ERROR",
            message=f"safe_error_id={safe.get('error_id')}",
            data={"model": body.model_name},
        )
        return error(
            code=ErrorCode.INTERNAL_ERROR,
            message=safe["message"],
            detail=safe.get("detail"),
        )


@router.post("/train/dry_run", dependencies=[Depends(require_permission("lnn:train"))])
async def dry_run_training(request: LNNTrainDryRunRequest):
    try:
        # 修复 [B10]：对 data_path 做路径遍历校验，限制在允许的数据目录内
        validated_data_path = _validate_data_path(request.data_path)
        max_size = 100 * 1024 * 1024

        def _load_data_sync():
            """同步读取文件大小并加载 CSV（在线程池中执行避免阻塞事件循环）。"""
            with open(str(validated_data_path), 'rb') as f:
                f.seek(0, 2)
                file_size = f.tell()
                if file_size > max_size:
                    raise ValueError(
                        f"File too large ({file_size / 1024 / 1024:.1f} MB), "
                        f"max {max_size / 1024 / 1024:.0f} MB"
                    )
                f.seek(0)
                return np.loadtxt(f, delimiter=",")

        try:
            # 修复 P2：用 asyncio.to_thread 包装同步文件 IO + np.loadtxt，避免阻塞事件循环
            data = await asyncio.to_thread(_load_data_sync)
        except FileNotFoundError:
            return error(
                code=ErrorCode.NOT_FOUND,
                message=f"Data file not found: {request.data_path}",
            )
        except IsADirectoryError:
            return error(
                code=ErrorCode.INVALID_REQUEST,
                message=f"Not a regular file: {request.data_path}",
            )
        except PermissionError:
            return error(
                code=ErrorCode.INVALID_REQUEST,
                message=f"Permission denied: {request.data_path}",
            )
        except ValueError as e:
            if "File too large" in str(e):
                # 包装异常消息，避免直接回显内部错误细节
                safe = safe_error_message(
                    e, context="lnn.upload_data[file_too_large]", fallback="数据文件过大"
                )
                return error(
                    code=ErrorCode.INVALID_REQUEST,
                    message=safe["message"],
                    detail={"error_id": safe["error_id"]},
                )
            raise
        if data.ndim == 1:
            data = data.reshape(-1, 1)

        if data.size == 0:
            return error(
                code=ErrorCode.INVALID_REQUEST,
                message="Data file is empty",
            )

        if data.shape[0] < 2:
            return error(
                code=ErrorCode.INVALID_REQUEST,
                message=f"Need at least 2 samples for train/val split, got {data.shape[0]}",
            )

        if not np.isfinite(data).all():
            return error(
                code=ErrorCode.INVALID_REQUEST,
                message="Data contains NaN or Inf values",
            )

        entry = model_registry.registry.get(request.model_name)
        if not entry:
            return error(
                code=ErrorCode.NOT_FOUND,
                message=f"Model '{request.model_name}' not found",
            )

        dataset_samples = data.shape[0]
        train_size = int(0.8 * dataset_samples)
        val_size = dataset_samples - train_size

        device, device_info = detect_device(request.device)

        estimated_memory_mb = (data.nbytes / (1024 * 1024)) * 3
        estimated_gpu_memory_mb = None
        if device.type == "cuda":
            estimated_gpu_memory_mb = estimated_memory_mb * 2

        epochs = request.hyperparameters.epochs
        batch_size = request.hyperparameters.batch_size
        samples_per_epoch = dataset_samples
        estimated_duration_minutes = (epochs * samples_per_epoch / batch_size) * 0.001

        potential_risks = []
        recommendations = []

        if dataset_samples < 100:
            potential_risks.append("数据集样本较少(<100),可能导致模型过拟合")
            recommendations.append("建议增加训练数据量以提升模型泛化能力")

        if epochs > 500:
            potential_risks.append("训练轮数较多(>500),训练时间可能较长")
            recommendations.append("可考虑使用早停策略(early stopping)避免过拟合")

        if request.hyperparameters.learning_rate > 0.01:
            potential_risks.append("学习率较高(>0.01),可能导致训练不稳定")
            recommendations.append("建议从较低学习率(0.001-0.005)开始训练")

        if device.type == "cpu":
            recommendations.append("当前使用CPU训练,如需加速可考虑使用GPU")

        training_plan = TrainingPlanSummary(
            estimated_duration_minutes=round(estimated_duration_minutes, 2),
            estimated_memory_mb=round(estimated_memory_mb, 2),
            estimated_gpu_memory_mb=round(estimated_gpu_memory_mb, 2)
            if estimated_gpu_memory_mb
            else None,
            dataset_samples=dataset_samples,
            train_val_split={
                "train": train_size,
                "validation": val_size,
                "ratio": "80/20",
            },
            potential_risks=potential_risks,
            recommendations=recommendations,
        )

        confidence = 0.85
        if len(potential_risks) > 2:
            confidence = 0.6
        elif len(potential_risks) > 0:
            confidence = 0.75

        reasoning = (
            f"基于数据集规模({dataset_samples} 样本)和超参数配置,"
            f"预计训练时间约为 {estimated_duration_minutes:.2f} 分钟。"
            f"{'检测到以下风险:' + '、'.join(potential_risks) if potential_risks else '未发现重大风险。'}"
            f"建议使用推荐配置开始训练。"
        )

        dry_run_response = LNNTrainDryRunResponse(
            is_dry_run=True,
            training_plan=training_plan,
            confidence=confidence,
            reasoning=reasoning,
        )

        return success(
            data=dry_run_response.model_dump(),
            message="Dry run completed: training plan generated for review",
        )

    except (ValueError, TypeError, OSError, RuntimeError) as e:
        safe = safe_error_message(e, context="lnn.dry_run_training")
        logger.warning("Dry run training failed: %s", e)
        return error(
            code=ErrorCode.INTERNAL_ERROR,
            message=safe["message"],
            detail=safe.get("detail"),
        )


@router.post("/train", dependencies=[Depends(require_permission("lnn:train"))])
@limiter.limit("5/hour")
async def train_lnn(
    request: Request,
    body: LNNTrainRequest,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
):
    """异步启动 LNN 训练,立即返回 job_id。"""
    try:
        existing = await task_manager.create_task(
            TaskType.LNN_TRAINING,
            {
                "model_name": body.model_name,
                "data_path": body.data_path,
                "hyperparameters": body.hyperparameters.model_dump(),
                "device": body.device,
            },
            idempotency_key=idempotency_key,
        )

        if idempotency_key and existing.status not in (
            TaskStatus.PENDING,
            TaskStatus.QUEUED,
        ):
            return success(
                data={
                    "job_id": existing.job_id,
                    "status": existing.status.value,
                    "cached": True,
                },
                message="Cached job retrieved",
            )

        task_id = existing.job_id

        progress_q: asyncio.Queue = asyncio.Queue(maxsize=1024)
        cancel_evt = asyncio.Event()
        with _TRAINING_QUEUES_LOCK:
            _cleanup_training_queues()  # 惰性清理过期队列
            _TRAINING_QUEUES[task_id] = {
                "cancel": cancel_evt,
                "progress": progress_q,
                "created_at": datetime.utcnow(),
            }

        # 同步到 task_manager 的内部队列引用
        if not hasattr(task_manager, "_training_queues"):
            task_manager._training_queues = {}
        task_manager._training_queues[task_id] = _TRAINING_QUEUES[task_id]

        def cancel_training_hook():
            cancel_evt.set()

        task_manager.register_cancel_hook(task_id, cancel_training_hook)

        # 修复：保存任务引用防止 GC 提前回收，并添加异常处理
        training_task = asyncio.create_task(
            _run_training_task_async(
                task_id,
                body.model_name,
                body.data_path,
                body.hyperparameters.model_dump(),
                body.device,
            )
        )
        training_task.add_done_callback(
            lambda t: _log_task_exception(t, f"training-{task_id}")
        )
        broadcast_task = asyncio.create_task(_broadcast_training_events(task_id))
        broadcast_task.add_done_callback(
            lambda t: _log_task_exception(t, f"broadcast-{task_id}")
        )

        return success(
            data={"job_id": task_id, "status": "queued"},
            message="Training job queued",
        )

    except (ValueError, TypeError, OSError, RuntimeError) as e:
        safe = safe_error_message(e, context=f"lnn.train_init[{body.model_name}]")
        logger.warning("Training init failed: %s", e)
        return error(
            code=ErrorCode.INTERNAL_ERROR,
            message=safe["message"],
            detail=safe.get("detail"),
        )


@router.get("/models")
@api_response
async def list_lnn_models():
    models = model_registry.list_models(return_objects=True)

    models_list = []
    for model_info in models:
        models_list.append(
            {
                "name": model_info.name,
                "model_type": model_info.model_type,
                "version": model_info.version,
                "input_features": model_info.input_features,
                "output_features": model_info.output_features,
            }
        )

    return success(
        data={"models": models_list, "total": len(models_list)},
        message="Models retrieved successfully",
    )


@router.get("/models/{model_name}/info")
@api_response
async def get_model_info(model_name: str):
    entry = model_registry.registry.get(model_name)
    if not entry:
        return error(
            code=ErrorCode.NOT_FOUND,
            message=f"Model '{model_name}' not found",
        )

    model_info = entry.info

    validation_result = model_registry.validate_model(model_name)

    info_data = {
        "name": model_info.name,
        "model_type": model_info.model_type,
        "model_path": model_info.model_path,
        "input_features": model_info.input_features,
        "output_features": model_info.output_features,
        "version": model_info.version,
        "is_loaded": entry.is_loaded,
        "access_count": entry.access_count,
        "validation": validation_result,
    }

    return success(data=info_data, message="Model info retrieved successfully")


@router.post("/models/{model_name}/validate", dependencies=[Depends(require_permission("lnn:write"))])
async def validate_model(model_name: str):
    try:
        entry = model_registry.registry.get(model_name)
        if not entry:
            return error(
                code=ErrorCode.NOT_FOUND,
                message=f"Model '{model_name}' not found",
            )

        validation_result = model_registry.validate_model(model_name)

        if not validation_result["valid"]:
            return success(
                data={
                    "model_name": model_name,
                    "valid": False,
                    "validation_details": validation_result,
                    "message": "Model validation failed",
                },
                message="Model validation completed with errors",
            )

        model_info = entry.info
        info_data = {
            "model_name": model_name,
            "valid": True,
            "validation_details": validation_result,
            "model_type": model_info.model_type,
            "version": model_info.version,
            "input_dimensions": len(model_info.input_features),
            "output_dimensions": len(model_info.output_features),
        }

        return success(
            data=info_data, message="Model validation completed successfully"
        )

    except (ValueError, KeyError, TypeError, OSError, RuntimeError) as e:
        safe = safe_error_message(e, context=f"lnn.validate_model[{model_name}]")
        logger.warning("Model validation failed: %s", e)
        return error(
            code=ErrorCode.INTERNAL_ERROR,
            message=safe["message"],
            detail=safe.get("detail"),
        )


@router.get("/health")
@api_response
async def health_check():
    """LNN 系统健康检查(包含持久层状态)"""
    model_count = len(model_registry.registry)
    active_tasks = len(_active_training_tasks)
    total_slots = MAX_CONCURRENT_TRAINING_TASKS

    from app.database.connection import check_db_health
    from app.services.redis_client import check_redis_health

    db_health = await check_db_health()
    redis_health = await check_redis_health()

    health_status = {
        "status": "healthy" if model_count > 0 else "degraded",
        "models_registered": model_count,
        "active_training_tasks": active_tasks,
        "available_training_slots": total_slots - active_tasks,
        "max_concurrent_tasks": total_slots,
        "persistence": {
            "postgres": db_health,
            "redis": redis_health,
        },
    }

    return success(data=health_status, message="Health check completed")


@router.get("/tasks")
@api_response
async def list_training_tasks():
    """列出所有训练任务"""
    tasks = await task_manager.list_tasks(
        task_type=TaskType.LNN_TRAINING, limit=200, offset=0
    )

    tasks_list = []
    for t in tasks:
        td = t.to_dict()
        tasks_list.append(
            {
                "task_id": t.job_id,
                "status": t.status.value,
                "progress": t.progress,
                "message": td.get("error", ""),
                "metrics": td.get("metrics"),
                "created_at": td.get("created_at_iso", ""),
                "duration_seconds": td.get("duration_seconds"),
            }
        )

    return success(
        data={"tasks": tasks_list, "total": len(tasks_list)},
        message="Training tasks retrieved",
    )


@router.get("/cache/stats")
@api_response
async def get_cache_stats():
    """获取模型缓存统计信息"""
    stats = model_cache.get_stats()

    return success(
        data={
            "cached_models": stats["cached_models"],
            "model_details": stats["model_details"],
            "total_cache_size_bytes": stats["total_cache_size_bytes"],
            "total_cache_size_mb": stats["total_cache_size_mb"],
            "hit_rate": stats["hit_rate"],
            "cache_hits": stats["cache_hits"],
            "cache_misses": stats["cache_misses"],
            "total_requests": stats["total_requests"],
            "max_size": stats["max_size"],
        },
        message="Cache statistics retrieved successfully",
    )


@router.delete("/cache/clear", dependencies=[Depends(require_permission("lnn:write"))])
@api_response
async def clear_cache():
    """清空所有模型缓存"""
    count, memory_freed = model_cache.clear()

    return success(
        data={
            "models_cleared": count,
            "memory_freed_bytes": memory_freed,
            "memory_freed_mb": round(memory_freed / (1024 * 1024), 2),
        },
        message=f"Cache cleared successfully: {count} models removed",
    )


@router.get("/performance")
@api_response
async def get_performance(model: str | None = None):
    candidate_models: list[str] = []
    if model:
        candidate_models = [model]
    else:
        candidate_models = list(model_registry.registry.keys())

    results: list[dict] = []
    for m_name in candidate_models:
        cached_predictor = model_cache.get(m_name)
        if cached_predictor is None:
            continue
        try:
            entry = model_registry.registry.get(m_name)
            base_model = entry.model if entry else cached_predictor
            if not isinstance(base_model, LNNPredictor) and base_model is not None:
                from app.ai.lnn.inference.predictor import LNNPredictor as P

                if isinstance(base_model, P):
                    perf = base_model.get_performance()
                    results.append(perf)
                    continue
        except (KeyError, AttributeError, RuntimeError, ValueError) as e:
            logger.debug(
                f"Failed to collect performance for {m_name}: {e}",
                exc_info=True,
            )

        if isinstance(cached_predictor, LNNPredictor):
            perf = cached_predictor.get_performance()
            results.append(perf)

    summary = {
        "total_models_tracked": len(results),
        "models": results,
    }
    return success(data=summary, message="Performance stats retrieved")


@router.get("/device/info")
@api_response
async def get_device_info():
    """返回系统中可用的计算设备信息"""
    devices = get_available_devices()

    current_device, current_info = detect_device("auto")

    response_data = {
        "current_device": {
            "type": current_info.device_type,
            "index": current_info.device_index,
            "name": current_info.device_name,
            "total_memory_mb": current_info.total_memory_mb,
            "available_memory_mb": current_info.available_memory_mb,
            "cuda_version": current_info.cuda_version,
            "compute_capability": current_info.compute_capability,
            "gpu_count": current_info.gpu_count,
        },
        "available_devices": [d.to_dict() for d in devices],
        "torch_cuda_available": torch.cuda.is_available(),
        "torch_version": torch.__version__,
        "cuda_version": torch.version.cuda if torch.cuda.is_available() else None,
        "cudnn_version": torch.backends.cudnn.version()
        if torch.cuda.is_available()
        else None,
    }

    return success(data=response_data, message="Device info retrieved successfully")


@router.get("/device/status")
@api_response
async def get_device_status_endpoint():
    """返回当前设备利用率和温度等信息"""
    device, device_info = detect_device("auto")

    status = get_device_status(device)

    response_data = {
        "active_device": str(device),
        "device_info": device_info.to_dict(),
        "status": status,
    }

    if device.type == "cuda":
        gpu_index = device.index if device.index is not None else 0
        response_data["gpu_status"] = {
            "total_memory_mb": round(
                torch.cuda.get_device_properties(gpu_index).total_memory
                / (1024**2),
                2,
            ),
            "allocated_memory_mb": round(
                torch.cuda.memory_allocated(gpu_index) / (1024**2), 2
            ),
            "reserved_memory_mb": round(
                torch.cuda.memory_reserved(gpu_index) / (1024**2), 2
            ),
            "max_memory_mb": round(
                torch.cuda.max_memory_allocated(gpu_index) / (1024**2), 2
            ),
        }

    return success(
        data=response_data, message="Device status retrieved successfully"
    )


@router.post("/device/clear-cache", dependencies=[Depends(require_permission("lnn:write"))])
@api_response
async def clear_device_cache():
    """清空GPU缓存"""
    if not torch.cuda.is_available():
        return error(
            code=ErrorCode.INVALID_REQUEST,
            message="No CUDA device available",
        )

    clear_gpu_memory(torch.device("cuda"))

    return success(
        data={"message": "GPU cache cleared successfully"},
        message="Device cache cleared",
    )


@router.get("/train/{task_id}/stream", dependencies=[Depends(get_current_user)])
async def stream_training_status(task_id: str):
    """SSE 端点,用于实时训练状态更新。"""
    record = await task_manager.get_task(task_id)
    if not record:
        return error(
            code=ErrorCode.NOT_FOUND,
            message=f"Training task '{task_id}' not found",
        )

    client_id = f"client_{uuid.uuid4().hex[:8]}"
    logger.info("Client %s connecting to SSE stream for task %s", client_id, task_id)

    return StreamingResponse(
        sse_event_generator(task_id, client_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/train/{task_id}/cancel", dependencies=[Depends(require_permission("lnn:train"))])
async def cancel_training_task(task_id: str):
    """取消正在运行的训练任务。"""
    record = await task_manager.get_task(task_id)
    if not record:
        return error(
            code=ErrorCode.NOT_FOUND,
            message=f"Training task '{task_id}' not found",
        )

    if record.status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED):
        return error(
            code=ErrorCode.INVALID_REQUEST,
            message=f"Training task '{task_id}' is already {record.status.value}",
        )

    await sse_manager.signal_cancel(task_id)

    if task_id in training_tasks:
        training_tasks[task_id]["status"] = "cancelling"
        training_tasks[task_id]["message"] = "Training cancellation requested"

    result = await task_manager.cancel_task(task_id)

    return success(
        data={"task_id": task_id, "status": "cancelled" if result else "cancelling"},
        message="Training cancellation processed",
    )


@router.post("/models/{model_name}/quantize", dependencies=[Depends(require_permission("lnn:write"))])
@limiter.limit("10/hour")
async def quantize_model(request: Request, model_name: str, body: LNNQuantizeRequest):
    """异步启动 INT8 量化任务,立即返回 job_id。"""
    try:
        entry = model_registry.registry.get(model_name)
        if not entry:
            return error(
                code=ErrorCode.NOT_FOUND,
                message=f"Model '{model_name}' not found",
            )

        if is_quantized_model(model_name):
            return error(
                code=ErrorCode.INVALID_REQUEST,
                message=f"Model '{model_name}' is already quantized",
            )

        if body.quantization_type == "static" and not body.calibration_data_path:
            return error(
                code=ErrorCode.INVALID_REQUEST,
                message="Calibration data path is required for static quantization",
            )

        record = await task_manager.create_task(
            TaskType.MODEL_QUANTIZATION,
            {
                "model_name": model_name,
                "quantization_type": body.quantization_type,
                "calibration_data_path": body.calibration_data_path,
            },
        )
        task_id = record.job_id

        async def quantization_executor(cancel_evt, progress_updater):
            return await _run_quantization_task_v2(
                task_id,
                model_name,
                body.quantization_type,
                body.calibration_data_path,
                cancel_evt,
                progress_updater,
            )

        # 修复：保存任务引用防止 GC 提前回收，并添加异常处理
        quantize_task = asyncio.create_task(
            task_manager.execute_task(task_id, quantization_executor)
        )
        quantize_task.add_done_callback(
            lambda t: _log_task_exception(t, f"quantize-{task_id}")
        )

        return success(
            data={"task_id": task_id, "status": "queued"},
            message="Quantization job queued",
        )

    except (ValueError, KeyError, TypeError, OSError, RuntimeError) as e:
        safe = safe_error_message(e, context=f"lnn.quantize[{model_name}]")
        logger.warning("Quantization init failed: %s", e)
        return error(
            code=ErrorCode.INTERNAL_ERROR,
            message=safe["message"],
            detail=safe.get("detail"),
        )


@router.get("/quantize/{task_id}/status")
@api_response
async def get_quantization_status(task_id: str):
    """查询异步量化任务的状态与结果。"""
    record = await task_manager.get_task(task_id)
    if not record or record.task_type != TaskType.MODEL_QUANTIZATION:
        return error(
            code=ErrorCode.NOT_FOUND,
            message=f"Quantization task '{task_id}' not found",
        )

    payload: dict = {
        "task_id": task_id,
        "status": record.status.value,
        "progress": getattr(record, "progress", 0.0),
    }
    if record.status == TaskStatus.COMPLETED and record.result:
        payload["result"] = record.result
    if record.status == TaskStatus.FAILED and record.error:
        payload["error"] = record.error
    return success(data=payload, message="Quantization status retrieved")


@router.post("/quantize/{task_id}/cancel", dependencies=[Depends(require_permission("lnn:write"))])
@api_response
async def cancel_quantization_task(task_id: str):
    """取消进行中的量化任务。"""
    record = await task_manager.get_task(task_id)
    if not record or record.task_type != TaskType.MODEL_QUANTIZATION:
        return error(
            code=ErrorCode.NOT_FOUND,
            message=f"Quantization task '{task_id}' not found",
        )

    if record.status in (
        TaskStatus.COMPLETED,
        TaskStatus.FAILED,
        TaskStatus.CANCELLED,
    ):
        return error(
            code=ErrorCode.INVALID_REQUEST,
            message=f"Quantization task '{task_id}' is already {record.status.value}",
        )

    cancelled = await task_manager.cancel_task(task_id)
    return success(
        data={
            "task_id": task_id,
            "status": "cancelled" if cancelled else "cancelling",
        },
        message="Quantization cancellation processed",
    )


@router.get("/models/{model_name}/size")
async def get_model_size(model_name: str):
    """获取模型及其量化版本的大小信息。"""
    try:
        entry = model_registry.registry.get(model_name)
        if not entry:
            return error(
                code=ErrorCode.NOT_FOUND,
                message=f"Model '{model_name}' not found",
            )

        original_path = entry.info.model_path
        original_size = (
            os.path.getsize(original_path) if os.path.exists(original_path) else 0
        )

        quantized_model_name = get_quantized_model_name(model_name)
        quantized_entry = model_registry.registry.get(quantized_model_name)
        quantized_size = None
        quantized_path = None

        if quantized_entry:
            quantized_path = quantized_entry.info.model_path
            if os.path.exists(quantized_path):
                quantized_size = os.path.getsize(quantized_path)

        response = LNNModelSizeResponse(
            original_size_bytes=original_size,
            quantized_size_bytes=quantized_size,
            original_size_human=_format_size(original_size),
            quantized_size_human=_format_size(quantized_size)
            if quantized_size
            else None,
            size_reduction_bytes=original_size - quantized_size
            if quantized_size
            else None,
            size_reduction_percent=round(
                (1.0 - quantized_size / original_size) * 100, 2
            )
            if quantized_size and original_size > 0
            else None,
        )

        return success(
            data=response.model_dump(), message="Model size retrieved successfully"
        )

    except (OSError, ValueError, KeyError, TypeError, RuntimeError) as e:
        safe = safe_error_message(e, context=f"lnn.get_model_size[{model_name}]")
        logger.warning("Get model size failed: %s", e)
        return error(
            code=ErrorCode.INTERNAL_ERROR,
            message=safe["message"],
            detail=safe.get("detail"),
        )


@router.post("/batch-inference", dependencies=[Depends(require_permission("lnn:write"))])
# P2-4-4 修复：批量推理消耗大量计算资源，需速率限制防止 DoS。
# 限制为 10/hour（比单次 predict 的 60/minute 更严格，因批量任务资源消耗高）。
@limiter.limit("10/hour")
async def batch_inference(
    request: Request,
    body: LNNBatchInferenceRequest,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
):
    """异步启动批量推理,立即返回 job_id。"""
    try:
        record = await task_manager.create_task(
            TaskType.LNN_BATCH_INFERENCE,
            {
                "model_name": body.model_name,
                "input_data": body.input_data,
                "batch_size": body.batch_size,
            },
            idempotency_key=idempotency_key,
        )

        async def batch_executor(cancel_evt, progress_updater):
            return await run_batch_inference_v2(
                record.job_id,
                body.model_name,
                body.input_data,
                body.batch_size,
                cancel_evt,
                progress_updater,
            )

        # 修复：保存任务引用防止 GC 提前回收，并添加异常处理
        batch_task = asyncio.create_task(
            task_manager.execute_task(record.job_id, batch_executor)
        )
        batch_task.add_done_callback(
            lambda t: _log_task_exception(t, f"batch-{record.job_id}")
        )

        return success(
            data={"job_id": record.job_id, "status": "queued"},
            message="Batch inference job queued",
        )

    except (ValueError, TypeError, OSError, RuntimeError) as e:
        safe = safe_error_message(
            e, context=f"lnn.batch_inference_init[{body.model_name}]"
        )
        logger.warning("Batch inference init failed: %s", e)
        return error(
            code=ErrorCode.INTERNAL_ERROR,
            message=safe["message"],
            detail=safe.get("detail"),
        )


# ============================================================
# 流式长时序推理（借鉴 lingbot-map GCT 五项核心思想）
# ============================================================
#
# 本节暴露 HybridInferenceEngine 的 infer_stream / infer_windowed 能力为
# HTTP 端点，使前端/外部服务可消费流式推理结果。引擎与 StreamingPredictor
# 的实现在 app.ai.lnn.engine / app.ai.lnn.inference.streaming 中，本节仅
# 做 HTTP 编排、输入校验、审计日志与错误安全。
#
# 设计要点：
# 1. HybridInferenceEngine 作为模块级惰性单例，避免每次请求重建路由表；
#    使用双重检查锁保证线程安全。
# 2. StreamingPredictor 每次请求新建（内部隐状态缓存、锚点、轨迹记忆
#    随请求隔离，避免跨请求状态污染）。
# 3. 流式端点返回 NDJSON（application/x-ndjson），每行一帧结果，便于
#    客户端增量消费；窗口化端点返回一次性 JSON 数组。
# 4. 速率限制：流式 20/minute（单帧轻量），窗口化 10/hour（批量重负载）。

_hybrid_engine: Optional[object] = None
_hybrid_engine_lock = threading.Lock()


def _get_hybrid_engine():
    """惰性获取 HybridInferenceEngine 模块级单例。

    使用双重检查锁（double-checked locking）保证线程安全。引擎以
    ``enable_fusion=False`` 初始化，因为流式推理路径为单模型，无需
    Dempster-Shafer 融合开销；融合能力保留给多模型 infer() 路径。

    Returns:
        HybridInferenceEngine 实例。

    Raises:
        ImportError: 当 app.ai.lnn.engine 不可导入时（torch 依赖缺失等）。
    """
    global _hybrid_engine
    if _hybrid_engine is not None:
        return _hybrid_engine
    with _hybrid_engine_lock:
        if _hybrid_engine is None:
            # 惰性导入：避免在模块加载阶段触发 torch 导入链
            from app.ai.lnn.engine import HybridInferenceEngine

            _hybrid_engine = HybridInferenceEngine(enable_fusion=False)
            logger.info("HybridInferenceEngine 流式推理单例已初始化")
    return _hybrid_engine


def _build_streaming_predictor(
    model_name: str,
    config: Optional[LNNStreamingConfig],
):
    """从 model_cache 获取 LNNPredictor 并构建 StreamingPredictor。

    复用 /predict 端点的 model_cache 模式，使单次推理与流式推理共享同一份
    模型权重与预处理器。StreamingPredictor 每次新建，保证隐状态隔离。

    Args:
        model_name: 已在 model_registry 注册的模型名称。
        config: 来自请求体的流式配置，None 时使用 StreamingConfig 默认值。

    Returns:
        StreamingPredictor 实例。

    Raises:
        ValueError: 当模型未注册或配置无效时。
        ImportError: 当 streaming 模块依赖缺失时。
    """
    from app.ai.lnn.inference.streaming import StreamingConfig, StreamingPredictor

    predictor = model_cache.get(model_name)
    if predictor is None:
        predictor = LNNPredictor.from_registry(
            registry=model_registry,
            model_name=model_name,
            use_amp=True,
            auto_device=True,
        )
        model_cache.put(model_name, predictor)

    streaming_config_kwargs = config.model_dump() if config is not None else {}
    streaming_config = StreamingConfig(**streaming_config_kwargs)
    return StreamingPredictor(predictor=predictor, config=streaming_config)


def _inference_result_to_dict(result) -> dict:
    """将 InferenceResult 序列化为 JSON 兼容的 dict。

    处理 numpy 标量/数组、EngineType 枚举、以及 prediction 单元素列表
    的展平（与 /predict 端点的响应格式保持一致）。

    Args:
        result: app.ai.lnn.core.InferenceResult 实例。

    Returns:
        JSON 可序列化的 dict。
    """
    prediction = result.prediction
    if prediction is not None and hasattr(prediction, "tolist"):
        prediction = prediction.tolist()
    if isinstance(prediction, list) and len(prediction) == 1:
        prediction = prediction[0]

    engine_used = result.engine_used
    if hasattr(engine_used, "value"):
        engine_used = engine_used.value

    return {
        "prediction": prediction,
        "confidence": result.confidence,
        "engine_used": engine_used,
        "model_used": result.model_used,
        "processing_time_ms": result.processing_time_ms,
        "metadata": result.metadata or {},
        "evidence": result.evidence or [],
        "uncertainty": result.uncertainty or {},
    }


def _validate_streaming_frames(frames: list) -> Optional[str]:
    """校验流式推理的帧序列数据，返回错误消息或 None。

    Args:
        frames: 请求体中的 frames 字段（list[list[float]]）。

    Returns:
        校验失败时返回错误消息字符串，成功时返回 None。
    """
    if not frames:
        return "frames 必须为非空列表"
    for i, frame in enumerate(frames):
        if not isinstance(frame, list) or not frame:
            return f"第 {i} 帧数据无效：必须为非空列表"
        if any(not isinstance(x, (int, float)) for x in frame):
            return f"第 {i} 帧数据无效：必须为数值类型"
    return None


@router.post("/predict_stream", dependencies=[Depends(require_permission("lnn:write"))])
@limiter.limit("20/minute")
async def predict_stream(request: Request, body: LNNStreamPredictRequest):
    """流式长时序推理（NDJSON 流式响应）。

    借鉴 lingbot-map GCT 思想：关键帧缓存 + 锚点漂移修正 + 轨迹记忆约束，
    适用于传感器实时采样流、长时序加工监控等场景。

    响应体为 ``application/x-ndjson``，每行一个 JSON 对象，对应一帧推理结果。
    每帧结果包含 prediction / confidence / metadata（含 is_keyframe、
    anchor_drift、trajectory_deviation 等流式元信息）。
    """
    import json

    try:
        # 输入校验
        err_msg = _validate_streaming_frames(body.frames)
        if err_msg:
            return error(
                code=ErrorCode.INVALID_REQUEST,
                message=err_msg,
            )

        # 模型存在性检查
        entry = model_registry.registry.get(body.model_name)
        if not entry:
            return error(
                code=ErrorCode.NOT_FOUND,
                message=f"Model '{body.model_name}' not found",
            )

        # 构建流式预测器（每次新建，保证隐状态隔离）
        try:
            streaming_predictor = _build_streaming_predictor(body.model_name, body.config)
        except (ValueError, KeyError, TypeError, RuntimeError, OSError, ImportError) as exc:
            safe = safe_error_message(
                exc,
                context=f"lnn.predict_stream.build[{body.model_name}]",
            )
            logger.error("构建流式预测器失败: %s", exc, exc_info=True)
            return error(
                code=ErrorCode.INTERNAL_ERROR,
                message=safe["message"],
                detail=safe.get("detail"),
            )

        # 注册到混合引擎并执行流式推理
        engine = _get_hybrid_engine()
        engine.register_streaming_predictor(body.model_name, streaming_predictor)

        # 审计日志（SOC 2 / ISO 27001 合规）
        audit_log.log_decision(
            ai_module=AIModule.LNN_PREDICT,
            ai_recommendation={
                "model_name": body.model_name,
                "streaming": True,
                "frame_count": len(body.frames),
            },
            user_decision=UserDecision.AUTO_EXECUTED,
            final_execution={"frame_count": len(body.frames)},
            operation_status=OperationStatus.SUCCESS,
            input_parameters={
                "model_name": body.model_name,
                "frame_count": len(body.frames),
                "config": body.config.model_dump() if body.config else None,
            },
            confidence=None,
            reasoning="streaming_inference",
        )

        get_ring_log_buffer().append(
            "ai_inference",
            level="INFO",
            message=f"Streaming inference started for model '{body.model_name}'",
            data={
                "model": body.model_name,
                "frame_count": len(body.frames),
                "streaming": True,
            },
        )

        # NDJSON 流式响应：每帧一行 JSON
        async def _ndjson_stream():
            for result in engine.infer_stream(body.model_name, iter(body.frames)):
                line = (
                    json.dumps(
                        _inference_result_to_dict(result),
                        ensure_ascii=False,
                    )
                    + "\n"
                )
                yield line

        return StreamingResponse(
            _ndjson_stream(),
            media_type="application/x-ndjson",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    except (ValueError, TypeError, OSError, RuntimeError, ImportError) as e:
        safe = safe_error_message(e, context=f"lnn.predict_stream[{body.model_name}]")
        logger.error("流式推理失败: %s", e, exc_info=True)
        return error(
            code=ErrorCode.INTERNAL_ERROR,
            message=safe["message"],
            detail=safe.get("detail"),
        )


@router.post("/predict_windowed", dependencies=[Depends(require_permission("lnn:write"))])
@limiter.limit("10/hour")
async def predict_windowed(request: Request, body: LNNWindowedPredictRequest):
    """窗口化超长序列推理（一次性 JSON 响应）。

    对应 lingbot-map 的 windowed mode：将序列切分为多个窗口，窗口间通过
    ``overlap_keyframes`` 传递隐状态，避免每次窗口都从零初始化。适用于
    万帧以上跨工序连续切削监控、长时序颤振检测等场景。

    响应体为标准 ``success()`` 包装，``data.results`` 为完整序列的推理结果列表。
    """
    try:
        # 输入校验
        err_msg = _validate_streaming_frames(body.frames)
        if err_msg:
            return error(
                code=ErrorCode.INVALID_REQUEST,
                message=err_msg,
            )

        # 模型存在性检查
        entry = model_registry.registry.get(body.model_name)
        if not entry:
            return error(
                code=ErrorCode.NOT_FOUND,
                message=f"Model '{body.model_name}' not found",
            )

        # 构建流式预测器
        try:
            streaming_predictor = _build_streaming_predictor(body.model_name, body.config)
        except (ValueError, KeyError, TypeError, RuntimeError, OSError, ImportError) as exc:
            safe = safe_error_message(
                exc,
                context=f"lnn.predict_windowed.build[{body.model_name}]",
            )
            logger.error("构建流式预测器失败: %s", exc, exc_info=True)
            return error(
                code=ErrorCode.INTERNAL_ERROR,
                message=safe["message"],
                detail=safe.get("detail"),
            )

        # 注册到混合引擎并执行窗口化推理
        engine = _get_hybrid_engine()
        engine.register_streaming_predictor(body.model_name, streaming_predictor)

        try:
            results = engine.infer_windowed(
                model_name=body.model_name,
                data_list=body.frames,
                window_size=body.window_size,
                overlap_keyframes=body.overlap_keyframes,
            )
        except (ValueError, TypeError, RuntimeError, OSError) as exc:
            safe = safe_error_message(
                exc,
                context=f"lnn.predict_windowed.infer[{body.model_name}]",
            )
            logger.error("窗口化推理失败: %s", exc, exc_info=True)
            return error(
                code=ErrorCode.INTERNAL_ERROR,
                message=safe["message"],
                detail=safe.get("detail"),
            )

        results_data = [_inference_result_to_dict(r) for r in results]

        # 审计日志
        audit_log.log_decision(
            ai_module=AIModule.LNN_PREDICT,
            ai_recommendation={
                "model_name": body.model_name,
                "streaming": True,
                "windowed": True,
                "frame_count": len(body.frames),
                "window_size": body.window_size,
                "overlap_keyframes": body.overlap_keyframes,
            },
            user_decision=UserDecision.AUTO_EXECUTED,
            final_execution={"result_count": len(results_data)},
            operation_status=OperationStatus.SUCCESS,
            input_parameters={
                "model_name": body.model_name,
                "frame_count": len(body.frames),
                "window_size": body.window_size,
                "overlap_keyframes": body.overlap_keyframes,
            },
            confidence=None,
            reasoning="windowed_inference",
        )

        get_ring_log_buffer().append(
            "ai_inference",
            level="INFO",
            message=f"Windowed inference completed for model '{body.model_name}'",
            data={
                "model": body.model_name,
                "frame_count": len(body.frames),
                "result_count": len(results_data),
                "windowed": True,
            },
        )

        return success(
            data={
                "results": results_data,
                "total_frames": len(results_data),
                "model_name": body.model_name,
            },
            message="Windowed streaming inference completed",
        )

    except (ValueError, TypeError, OSError, RuntimeError, ImportError) as e:
        safe = safe_error_message(e, context=f"lnn.predict_windowed[{body.model_name}]")
        logger.error("窗口化推理失败: %s", e, exc_info=True)
        return error(
            code=ErrorCode.INTERNAL_ERROR,
            message=safe["message"],
            detail=safe.get("detail"),
        )
