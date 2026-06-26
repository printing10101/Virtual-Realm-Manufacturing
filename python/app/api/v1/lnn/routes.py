"""LNN API 路由定义。"""

import os
import uuid
import asyncio
import logging
from typing import Optional
from datetime import datetime

from fastapi import APIRouter, Header, Request
from fastapi.responses import StreamingResponse

from app.core.response import ErrorCode, error, success
from app.core.safe_errors import safe_error_message
from app.core.api_response import api_response
from app.audit.audit_log import AIModule, UserDecision, OperationStatus
from app.utils.ring_buffer import get_ring_log_buffer
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
    _run_training_task,
    _run_training_task_async,
    _broadcast_training_events,
    _run_quantization_task_v2,
    _run_quantization_task,
    _format_size,
    run_batch_inference_v2,
    sse_event_generator,
)

import torch
import numpy as np

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/lnn", tags=["LNN Models"])

# 训练队列(模块级状态)
_TRAINING_QUEUES: dict = {}


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


@router.post("/predict")
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


@router.post("/train/dry_run")
async def dry_run_training(request: LNNTrainDryRunRequest):
    try:
        max_size = 100 * 1024 * 1024
        try:
            with open(request.data_path, 'rb') as f:
                f.seek(0, 2)
                file_size = f.tell()

                if file_size > max_size:
                    return error(
                        code=ErrorCode.INVALID_REQUEST,
                        message=f"File too large ({file_size / 1024 / 1024:.1f} MB), max {max_size / 1024 / 1024:.0f} MB",
                    )

                f.seek(0)

                data = np.loadtxt(f, delimiter=",")
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


@router.post("/train")
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
        _TRAINING_QUEUES[task_id] = {"cancel": cancel_evt, "progress": progress_q}

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


@router.post("/models/{model_name}/validate")
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


@router.delete("/cache/clear")
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


@router.post("/device/clear-cache")
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


@router.get("/train/{task_id}/stream")
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


@router.post("/train/{task_id}/cancel")
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


@router.post("/models/{model_name}/quantize")
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


@router.post("/quantize/{task_id}/cancel")
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


@router.post("/batch-inference")
async def batch_inference(
    request: LNNBatchInferenceRequest,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
):
    """异步启动批量推理,立即返回 job_id。"""
    try:
        record = await task_manager.create_task(
            TaskType.LNN_BATCH_INFERENCE,
            {
                "model_name": request.model_name,
                "input_data": request.input_data,
                "batch_size": request.batch_size,
            },
            idempotency_key=idempotency_key,
        )

        async def batch_executor(cancel_evt, progress_updater):
            return await run_batch_inference_v2(
                record.job_id,
                request.model_name,
                request.input_data,
                request.batch_size,
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
            e, context=f"lnn.batch_inference_init[{request.model_name}]"
        )
        logger.warning("Batch inference init failed: %s", e)
        return error(
            code=ErrorCode.INTERNAL_ERROR,
            message=safe["message"],
            detail=safe.get("detail"),
        )
