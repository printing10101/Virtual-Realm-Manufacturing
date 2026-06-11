import os
import time
import asyncio
import uuid
import logging
import threading
from datetime import datetime
from typing import Optional, Callable
from fastapi import APIRouter, Header, Request
from fastapi.responses import StreamingResponse

from app.core.response import ErrorCode, error, success
from app.core.safe_errors import safe_error_message
from app.core.api_response import api_response
from app.audit.audit_log import AuditLog, AIModule, UserDecision, OperationStatus
from app.utils.ring_buffer import get_ring_log_buffer
from app.middleware.rate_limiter import limiter
from app.config import config
from app.models.schemas import (
    LNNPredictRequest,
    LNNTrainRequest,
    LNNModelInfo,
    LNNQuantizeRequest,
    LNNModelSizeResponse,
    LNNTrainDryRunRequest,
    LNNTrainDryRunResponse,
    TrainingPlanSummary,
    AlternativePlan,
    LNNBatchInferenceRequest,
)
from app.tasks.task_system import AsyncTaskManager
from app.tasks.task_manager import TaskType, TaskStatus
from app.ai.lnn.inference.registry import (
    get_torch_model_class,
)
from app.ai.lnn.inference.predictor import LNNPredictor, PredictionResult
from app.services.model_registry_service import get_model_registry_service
from app.ai.lnn.inference.registry import (
    is_quantized_model,
    get_quantized_model_name,
)
from app.ai.lnn.models.torch_base_lnn import LNNConfig
from app.ai.lnn.training.trainer import LNNTrainer
from app.ai.lnn.training.device_manager import (
    detect_device,
    get_available_devices,
    get_device_status,
    get_optimal_batch_size,
    get_optimal_num_workers,
    clear_gpu_memory,
)
from app.api.v1.sse import sse_manager, create_progress_callback
import torch
import numpy as np
from torch.utils.data import DataLoader, TensorDataset

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/lnn", tags=["LNN Models"])

# Use the unified service layer — do NOT instantiate LNNModelRegistry directly
registry_service = get_model_registry_service()
model_registry = registry_service.model_registry
pytorch_registry = registry_service.pytorch_registry
model_cache = registry_service.model_cache
training_tasks = registry_service.get_training_tasks()
audit_log = AuditLog()

MAX_CONCURRENT_TRAINING_TASKS = 3
# 仅用于兼容旧 health_check 端点的活跃任务计数；
# 真正的并发控制由 AsyncTaskManager._semaphore 统一管理。
_active_training_tasks: set[str] = set()

task_manager = AsyncTaskManager()


async def _broadcast_error(task_id: str, code: str, message: str):
    """Broadcast error message via SSE."""
    await sse_manager.broadcast(
        task_id,
        "error",
        {
            "code": code,
            "message": message,
            "details": {},
        },
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
                    message=f"输入维度不匹配: 期望{expected_dim}维或其倍数，实际{input_len}维",
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
        except Exception as model_err:
            # 修复：避免直接 str(model_err) 暴露内部异常详情；
            # 通过 safe_error_message 包装，仅透出错误类型 + error_id，
            # 完整堆栈仍写入日志供排查。
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
    except Exception as e:
        # 修复：不直接 str(e) 暴露内部异常，使用 safe_error_message 包装
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


async def _run_training_task(  # pragma: no cover - legacy stub, see _run_training_task_async
    task_id: str,
    model_name: str,
    data_path: str,
    hyperparameters: dict,
    device_preference: str = "auto",
):
    """Legacy V1 训练执行器：已被 ``_run_training_task_async`` + ``task_manager`` 取代。

    保留为 stub 是为了：
      1. 避免被反射式 import（``getattr`` / 模块 ``__getattr__``）的下游代码踩坑；
      2. 在 health_check / 监控端点观测到时打印明确警告，便于排查残留调用方。

    实际的训练路径请参考 ``/api/v1/lnn/train`` → ``task_manager.execute_task`` →
    ``run_training_task_v2`` 链路。
    """
    logger.warning(
        "run_training_task v1 invoked for %s; please migrate to v2 path "
        "(task_manager + run_training_task_v2)",
        task_id,
    )
    raise NotImplementedError(
        "run_training_task v1 is deprecated; use task_manager.execute_task "
        "with run_training_task_v2 instead."
    )


@router.post("/train/dry_run")
async def dry_run_training(request: LNNTrainDryRunRequest):
    try:
        if not os.path.exists(request.data_path):
            return error(
                code=ErrorCode.NOT_FOUND,
                message=f"Data file not found: {request.data_path}",
            )

        if not os.path.isfile(request.data_path):
            return error(
                code=ErrorCode.INVALID_REQUEST,
                message=f"Not a regular file: {request.data_path}",
            )

        file_size = os.path.getsize(request.data_path)
        max_size = 100 * 1024 * 1024
        if file_size > max_size:
            return error(
                code=ErrorCode.INVALID_REQUEST,
                message=f"File too large ({file_size / 1024 / 1024:.1f} MB), max {max_size / 1024 / 1024:.0f} MB",
            )

        import numpy as np

        data = np.loadtxt(request.data_path, delimiter=",")
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
            potential_risks.append("数据集样本较少（<100），可能导致模型过拟合")
            recommendations.append("建议增加训练数据量以提升模型泛化能力")

        if epochs > 500:
            potential_risks.append("训练轮数较多（>500），训练时间可能较长")
            recommendations.append("可考虑使用早停策略（early stopping）避免过拟合")

        if request.hyperparameters.learning_rate > 0.01:
            potential_risks.append("学习率较高（>0.01），可能导致训练不稳定")
            recommendations.append("建议从较低学习率（0.001-0.005）开始训练")

        if device.type == "cpu":
            recommendations.append("当前使用CPU训练，如需加速可考虑使用GPU")

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
            f"基于数据集规模（{dataset_samples} 样本）和超参数配置，"
            f"预计训练时间约为 {estimated_duration_minutes:.2f} 分钟。"
            f"{'检测到以下风险：' + '、'.join(potential_risks) if potential_risks else '未发现重大风险。'}"
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

    except Exception as e:
        safe = safe_error_message(e, context="lnn.dry_run_training")
        return error(
            code=ErrorCode.INTERNAL_ERROR,
            message=safe["message"],
            detail=safe.get("detail"),
        )


_TRAINING_QUEUES: dict = {}


async def _run_training_task_async(
    task_id: str,
    model_name: str,
    data_path: str,
    hyperparameters: dict,
    device: str,
):
    """在 FastAPI 主事件循环中跑训练任务。

    重构说明：
        原实现通过 ``threading.Thread`` 创建一个独立的 asyncio 事件循环，
        再用 std ``queue.Queue`` + ``threading.Event`` 在主循环和子循环之间
        通信。这有两个隐患：
          1. 跨循环传递 std 队列需要锁保护，且 std 队列 ``put_nowait`` / ``get_nowait``
             会短暂阻塞调用线程，间接影响主事件循环；
          2. 取消回调 (``threading.Event.set``) 在主循环线程中执行，但
             ``wait()`` 跑在子循环，状态同步无强保证。

        重构后：直接用 ``asyncio.create_task`` 在主循环上调度训练协程；
        进度队列改为 ``asyncio.Queue``，取消事件改为 ``asyncio.Event``；
        主循环和后台训练共享同一调度器，状态同步天然一致。
    """
    from datetime import datetime as _datetime

    queue_data = _TRAINING_QUEUES.get(task_id, {})
    progress_q = queue_data.get("progress")
    cancel_evt = queue_data.get("cancel")
    if progress_q is None or cancel_evt is None:
        return

    started_at = _datetime.now().isoformat()
    await progress_q.put(
        (
            "started",
            {
                "job_id": task_id,
                "started_at": started_at,
                "resources": {"max_concurrent": 3},
            },
        )
    )

    async def progress_updater(progress, message="", metrics=None):
        # 队列满时丢弃进度帧：训练优先级高于日志完整性
        try:
            progress_q.put_nowait(
                (
                    "progress",
                    {
                        "job_id": task_id,
                        "percent": round(progress, 1),
                        "message": message,
                        "metrics": metrics or {},
                    },
                )
            )
        except asyncio.QueueFull:
            logger.debug("SSE progress queue full, dropping message")

    try:
        result = await run_training_task_v2(
            task_id,
            model_name,
            data_path,
            hyperparameters,
            device,
            cancel_evt,
            progress_updater,
        )
        await progress_q.put(
            (
                "complete",
                {
                    "job_id": task_id,
                    "result": result,
                    "completed_at": _datetime.now().isoformat(),
                },
            )
        )
    except asyncio.CancelledError:
        await progress_q.put(
            (
                "cancelled",
                {
                    "job_id": task_id,
                    "cancelled_at": _datetime.now().isoformat(),
                    "progress": 0,
                },
            )
        )
    except Exception as e:
        # 修复：原代码直接 str(e) 暴露内部异常到 SSE 事件，
        # 而 SSE 事件会进入前端日志/告警，存在信息泄露风险。
        # 这里只透出错误类型 + error_id 供前端关联服务端日志。
        safe = safe_error_message(
            e,
            context=f"lnn.training_worker[{task_id}]",
        )
        logger.error(
            "lnn training worker failed | task_id=%s | error_id=%s | exc=%s: %s",
            task_id,
            safe.get("error_id"),
            type(e).__name__,
            e,
        )
        await progress_q.put(
            (
                "failed",
                {
                    "job_id": task_id,
                    "error": safe["message"],
                    "error_id": safe.get("error_id"),
                    "failed_at": _datetime.now().isoformat(),
                },
            )
        )


async def _broadcast_training_events(task_id: str):
    q = _TRAINING_QUEUES.get(task_id)
    if not q:
        return
    cancel_evt: asyncio.Event = q["cancel"]
    progress_q: asyncio.Queue = q["progress"]

    while True:
        try:
            item = await progress_q.get()
            event_type, data = item
            logger.debug("[BROADCAST] %s: %s", task_id, event_type)
            if event_type == "progress":
                await task_manager._broadcast_event(task_id, "progress", data)
            elif event_type == "complete":
                record = await task_manager.get_task(task_id)
                if record:
                    record.status = TaskStatus.COMPLETED
                    record.progress = 100.0
                    record.completed_at = time.time()
                    record.result = data.get("result")
                    await task_manager._persist_task_to_db(record)
                    await task_manager._broadcast_event(task_id, "complete", data)
                    if task_id in task_manager._tasks:
                        task_manager._tasks[task_id].status = TaskStatus.COMPLETED
                        task_manager._tasks[task_id].progress = 100.0
                        task_manager._tasks[task_id].completed_at = time.time()
                        task_manager._tasks[task_id].result = data.get("result")
                break
            elif event_type == "cancelled":
                record = await task_manager.get_task(task_id)
                if record:
                    record.status = TaskStatus.CANCELLED
                    record.completed_at = time.time()
                    await task_manager._persist_task_to_db(record)
                    await task_manager._broadcast_event(task_id, "cancelled", data)
                    if task_id in task_manager._tasks:
                        task_manager._tasks[task_id].status = TaskStatus.CANCELLED
                        task_manager._tasks[task_id].completed_at = time.time()
                break
            elif event_type == "failed":
                record = await task_manager.get_task(task_id)
                if record:
                    record.status = TaskStatus.FAILED
                    record.error = data.get("error", "")
                    record.completed_at = time.time()
                    await task_manager._persist_task_to_db(record)
                    await task_manager._broadcast_event(task_id, "failed", data)
                    if task_id in task_manager._tasks:
                        task_manager._tasks[task_id].status = TaskStatus.FAILED
                        task_manager._tasks[task_id].error = data.get("error", "")
                        task_manager._tasks[task_id].completed_at = time.time()
                break
            elif event_type == "started":
                record = await task_manager.get_task(task_id)
                if record:
                    record.status = TaskStatus.RUNNING
                    record.started_at = time.time()
                    await task_manager._persist_task_to_db(record)
                    await task_manager._broadcast_event(task_id, "started", data)
                    if task_id in task_manager._tasks:
                        task_manager._tasks[task_id].status = TaskStatus.RUNNING
        except asyncio.CancelledError:
            # 父任务被取消时优雅退出，避免泄漏循环
            break
        except (RuntimeError, ValueError, KeyError) as exc:
            # 修复：原代码用裸 except Exception 静默吞掉所有错误，
            # 一旦后台训练 worker 真的崩溃，SSE 循环会悄悄 break，
            # 导致前端停留在「训练中」而服务侧已无任务可消费。
            # 这里只捕获协作取消/运行时/协议类错误并记录，便于排查。
            logger.warning(
                "lnn SSE consumer loop异常退出 | task_id=%s | exc=%s: %s",
                task_id,
                type(exc).__name__,
                exc,
            )
            break
        else:
            # 显式判断取消事件，避免无消息时无限空转
            if cancel_evt.is_set() and progress_q.empty():
                break


@router.post("/train")
@limiter.limit("5/hour")
async def train_lnn(
    request: Request,
    body: LNNTrainRequest,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
):
    """Start LNN training asynchronously. Returns job_id immediately."""
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

        # 修复：原实现使用 std ``queue.Queue`` + ``threading.Event`` 配合
        # ``threading.Thread``，需要在线程间手动同步状态。改为 asyncio 原生
        # 队列和事件后，训练和广播跑在同一事件循环上，无需线程桥接。
        progress_q: asyncio.Queue = asyncio.Queue(maxsize=1024)
        cancel_evt = asyncio.Event()
        _TRAINING_QUEUES[task_id] = {"cancel": cancel_evt, "progress": progress_q}

        def cancel_training_hook():
            # asyncio.Event.set() 是同步调用，从同步上下文触发也安全。
            cancel_evt.set()

        task_manager.register_cancel_hook(task_id, cancel_training_hook)

        asyncio.create_task(
            _run_training_task_async(
                task_id,
                body.model_name,
                body.data_path,
                body.hyperparameters.model_dump(),
                body.device,
            )
        )
        asyncio.create_task(_broadcast_training_events(task_id))

        return success(
            data={"job_id": task_id, "status": "queued"},
            message="Training job queued",
        )

    except Exception as e:
        safe = safe_error_message(e, context=f"lnn.train_init[{body.model_name}]")
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

    except Exception as e:
        safe = safe_error_message(e, context=f"lnn.validate_model[{model_name}]")
        return error(
            code=ErrorCode.INTERNAL_ERROR,
            message=safe["message"],
            detail=safe.get("detail"),
        )


@router.get("/health")
@api_response
async def health_check():
    """LNN 系统健康检查（包含持久层状态）"""
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
            # 单个模型性能获取失败时跳过该模型，继续收集其他模型
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


async def sse_event_generator(task_id: str, client_id: str):
    """
    SSE event generator for a training task.

    Yields SSE formatted events from the task's event queue.
    """
    client = await sse_manager.subscribe(task_id, client_id)
    try:
        while True:
            try:
                event = await asyncio.wait_for(client.queue.get(), timeout=30.0)
                yield event
            except asyncio.TimeoutError:
                yield ": heartbeat\n\n"
    except asyncio.CancelledError:
        logger.info(f"SSE stream cancelled for client {client_id}")
    finally:
        await sse_manager.unsubscribe(task_id, client_id)


@router.get("/train/{task_id}/stream")
async def stream_training_status(task_id: str):
    """
    SSE endpoint for real-time training status updates.
    """
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
    """Cancel a running training task."""

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


def _format_size(size_bytes: int) -> str:
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.2f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.2f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"


async def _run_quantization_task_v2(
    task_id: str,
    model_name: str,
    quantization_type: str,
    calibration_data_path: str | None,
    cancel_evt: asyncio.Event,
    progress_updater: Callable,
):
    """真正的量化执行器（可取消，带进度回调）。"""
    from app.ai.lnn.quantization.quantizer import (
        Quantizer,
        QuantizationConfig,
        QuantizationType,
    )
    from app.ai.lnn.inference.registry import get_torch_model_class

    await progress_updater(5.0, "加载模型元信息...")

    entry = model_registry.registry.get(model_name)
    if not entry:
        raise ValueError(f"Model '{model_name}' not found")

    if not os.path.exists(entry.info.model_path):
        raise FileNotFoundError(
            f"Model file not found: {entry.info.model_path}"
        )

    model_class = get_torch_model_class(entry.info.model_type)
    if not model_class:
        raise ValueError(f"Unsupported model type: {entry.info.model_type}")

    from app.ai.lnn.models.torch_base_lnn import LNNConfig

    config_obj = LNNConfig(
        input_size=len(entry.info.input_features),
        hidden_size=128,
        output_size=len(entry.info.output_features),
        num_layers=2,
        dropout=0.1,
    )
    model = model_class(config_obj)

    await progress_updater(15.0, "加载模型权重...")

    try:
        model.load(entry.info.model_path)
        model.build()
    except (OSError, RuntimeError, ValueError, TypeError) as e:
        # 模型权重加载失败时使用初始化权重继续量化流程，记录以便排查
        logger.warning(
            f"Failed to load model weights for quantization, "
            f"falling back to initialized weights: {e}",
            exc_info=True,
        )

    model.eval()

    quant_type = (
        QuantizationType.DYNAMIC
        if quantization_type == "dynamic"
        else QuantizationType.STATIC
    )
    quant_config = QuantizationConfig(quantization_type=quant_type)

    calibration_data = None
    if quant_type == QuantizationType.STATIC:
        if not calibration_data_path or not os.path.exists(calibration_data_path):
            raise FileNotFoundError(
                "Calibration data path required for static quantization"
            )

        await progress_updater(30.0, "加载校准数据...")

        try:
            import numpy as np

            calibration_data = np.loadtxt(calibration_data_path, delimiter=",")
            if calibration_data.ndim == 1:
                calibration_data = calibration_data.reshape(-1, 1)
            if calibration_data.shape[1] == 1:
                calibration_data = np.column_stack(
                    [calibration_data, calibration_data]
                )
            calibration_data = calibration_data[:, :-1]
        except Exception as e:
            # 校准数据加载失败属于用户数据问题，使用更具体的错误类型便于上层归类
            raise ValueError(f"Failed to load calibration data: {e}") from e

    quantized_model_name = get_quantized_model_name(model_name)
    output_dir = os.path.dirname(entry.info.model_path)
    quantized_model_path = os.path.join(output_dir, f"{quantized_model_name}.pt")

    quantizer = Quantizer(quant_config)

    await progress_updater(50.0, "执行量化...")

    if cancel_evt.is_set():
        raise asyncio.CancelledError()

    quantized_model, result = quantizer.quantize(
        model=model,
        calibration_data=calibration_data,
        save_path=quantized_model_path,
        metadata={
            "base_model": model_name,
            "quantization_type": quantization_type,
        },
    )

    await progress_updater(85.0, "计算模型大小...")

    original_size = quantizer.get_model_size(entry.info.model_path)
    quantized_size = quantizer.get_model_size(quantized_model_path)
    result.original_size_bytes = original_size
    result.quantized_size_bytes = quantized_size

    await progress_updater(95.0, "注册量化模型...")

    pytorch_registry.register_quantized_model(
        model_name=quantized_model_name,
        model_type=entry.config.model_type if entry.config else None,
        model_path=quantized_model_path,
        metadata={
            "quantization_type": quantization_type,
            "quantization_date": time.strftime("%Y-%m-%d %H:%M:%S"),
            "original_size_bytes": original_size,
            "quantized_size_bytes": quantized_size,
            "compression_ratio": result.compression_ratio,
            "speedup_ratio": result.speedup_ratio,
        },
    )

    await progress_updater(100.0, "量化完成")

    return {
        "task_id": task_id,
        "status": "success",
        "message": "Quantization completed successfully",
        "metrics": {
            "quantized_model_name": quantized_model_name,
            "quantized_model_path": quantized_model_path,
            "original_size_bytes": original_size,
            "quantized_size_bytes": quantized_size,
            "original_size_human": _format_size(original_size),
            "quantized_size_human": _format_size(quantized_size),
            "compression_ratio": round(result.compression_ratio, 4),
            "speedup_ratio": round(result.speedup_ratio, 4),
            "quantization_time_seconds": round(result.quantization_time_seconds, 2),
        },
    }


# 兼容旧入口的轻量包装器（被 ``_run_quantization_task_v2`` 取代后保留空实现）
# 之所以保留符号：避免其他模块反射式 import 时出现 ImportError。
async def _run_quantization_task(  # pragma: no cover - legacy stub
    task_id: str,
    model_name: str,
    quantization_type: str,
    calibration_data_path: str | None = None,
):
    """兼容旧调用的 stub，已由 task_manager + _run_quantization_task_v2 取代。

    直接抛出未实现错误，确保误用时立刻暴露而非悄悄返回错误状态。
    """
    logger.error(
        "_run_quantization_task v1 invoked for %s; please migrate to v2 path "
        "(task_manager + _run_quantization_task_v2)",
        task_id,
    )
    raise NotImplementedError(
        "_run_quantization_task v1 is deprecated; use task_manager.execute_task "
        "with _run_quantization_task_v2 instead."
    )


@router.post("/models/{model_name}/quantize")
@limiter.limit("10/hour")
async def quantize_model(request: Request, model_name: str, body: LNNQuantizeRequest):
    """异步启动 INT8 量化任务，立即返回 job_id。

    重构说明：
        原实现使用 ``asyncio.create_task`` 启动后台协程后，在请求协程内
        用 ``while ... await asyncio.sleep(0.1)`` 轮询状态，最长阻塞 60 秒。
        这导致：
          1. 长时间任务被强制 60 秒超时截断；
          2. HTTP 连接被占用无法释放，客户端无法拿到真正的进度；
          3. 任务状态没有持久化，服务重启后丢失；
          4. 与 ``/train`` 端点的实现割裂。

        重构后：复用统一的 ``task_manager``，将量化任务作为可追踪、可取消、
        可 SSE 推送的标准化任务管理；客户端通过 ``/tasks`` 端点查询进度。
    """
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

        asyncio.create_task(
            task_manager.execute_task(task_id, quantization_executor)
        )

        return success(
            data={"task_id": task_id, "status": "queued"},
            message="Quantization job queued",
        )

    except Exception as e:
        safe = safe_error_message(e, context=f"lnn.quantize[{model_name}]")
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
    """Get the size information of a model and its quantized version."""
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

    except Exception as e:
        safe = safe_error_message(e, context=f"lnn.get_model_size[{model_name}]")
        return error(
            code=ErrorCode.INTERNAL_ERROR,
            message=safe["message"],
            detail=safe.get("detail"),
        )


def _generate_prediction_reasoning(
    model_name: str,
    input_data: list[float],
    prediction: float | list[float],
    confidence: float | None,
    inference_time: float,
) -> str:
    reasoning_parts = [
        f"模型 {model_name} 基于输入的 {len(input_data)} 个特征进行推理。",
    ]

    if isinstance(prediction, (int, float)):
        reasoning_parts.append(f"预测值为 {prediction}。")
    else:
        reasoning_parts.append(f"输出 {len(prediction)} 个预测值。")

    if confidence is not None:
        if confidence >= 0.8:
            reasoning_parts.append(
                f"置信度较高 ({confidence:.2f})，表明模型对当前输入数据的预测结果有较高的把握。"
            )
        elif confidence >= 0.5:
            reasoning_parts.append(
                f"置信度中等 ({confidence:.2f})，建议结合实际情况综合判断预测结果。"
            )
        else:
            reasoning_parts.append(
                f"置信度较低 ({confidence:.2f})，建议参考备选方案或调整输入数据后重新预测。"
            )

    reasoning_parts.append(f"推理耗时 {inference_time:.2f}ms。")

    return " ".join(reasoning_parts)


def _generate_alternatives(
    model_name: str,
    input_data: list[float],
    primary_value: float | list[float],
    primary_confidence: float,
) -> list[AlternativePlan]:
    alternatives = []

    if isinstance(primary_value, (int, float)):
        alt_1_value = primary_value * 0.95
        alt_2_value = primary_value * 1.05

        alternatives.append(
            AlternativePlan(
                plan_id=f"alt_{uuid.uuid4().hex[:8]}",
                parameters={
                    "optimization_target": "conservative",
                    "safety_margin": "+5%",
                },
                expected_outcome=f"保守方案：预测值 {alt_1_value:.4f}，偏向安全边际，适合对稳定性要求高的场景。",
                confidence=max(0.0, primary_confidence - 0.05),
                reasoning="保守方案通过降低预测值约5%提供额外的安全缓冲，适用于风险敏感型决策。",
            )
        )

        alternatives.append(
            AlternativePlan(
                plan_id=f"alt_{uuid.uuid4().hex[:8]}",
                parameters={
                    "optimization_target": "aggressive",
                    "efficiency_gain": "+5%",
                },
                expected_outcome=f"激进方案：预测值 {alt_2_value:.4f}，偏向性能优化，适合追求效率的场景。",
                confidence=max(0.0, primary_confidence - 0.08),
                reasoning="激进方案通过提高预测值约5%追求性能最优，适用于对效率要求高的场景。",
            )
        )
    else:
        alt_1_value = [v * 0.95 for v in primary_value]
        alt_2_value = [v * 1.05 for v in primary_value]

        alternatives.append(
            AlternativePlan(
                plan_id=f"alt_{uuid.uuid4().hex[:8]}",
                parameters={
                    "optimization_target": "conservative",
                    "safety_margin": "+5%",
                },
                expected_outcome="保守方案：输出值整体下调5%，偏向安全边际，适合对稳定性要求高的场景。",
                confidence=max(0.0, primary_confidence - 0.05),
                reasoning="保守方案通过降低各输出值约5%提供额外的安全缓冲，适用于风险敏感型决策。",
            )
        )

        alternatives.append(
            AlternativePlan(
                plan_id=f"alt_{uuid.uuid4().hex[:8]}",
                parameters={
                    "optimization_target": "aggressive",
                    "efficiency_gain": "+5%",
                },
                expected_outcome="激进方案：输出值整体上调5%，偏向性能优化，适合追求效率的场景。",
                confidence=max(0.0, primary_confidence - 0.08),
                reasoning="激进方案通过提高各输出值约5%追求性能最优，适用于对效率要求高的场景。",
            )
        )

    return alternatives


async def run_training_task_v2(
    task_id: str,
    model_name: str,
    data_path: str,
    hyperparameters: dict,
    device_preference: str,
    cancel_evt: asyncio.Event,
    progress_updater: Callable,
):
    """V2 training executor with progress callbacks and cancellation support"""
    try:
        from app.utils.utils import get_metrics_collector

        metrics = get_metrics_collector()
        metrics.set_active_training_tasks(max(0, metrics._active_training_tasks + 1))
    except (ImportError, AttributeError, RuntimeError) as e:
        # 训练指标递增失败仅影响可观测性，不影响训练执行
        logger.debug(
            f"Failed to increment active training tasks counter: {e}",
            exc_info=True,
        )

    await progress_updater(5.0, "Loading data...")

    if not os.path.exists(data_path):
        raise FileNotFoundError(f"Data file not found: {data_path}")

    try:
        data = np.loadtxt(data_path, delimiter=",", skiprows=1, dtype=float)
    except (ValueError, UnicodeDecodeError):
        with open(data_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        numeric_lines = []
        for line in lines[1:]:
            parts = line.strip().split(",")
            numeric_line = []
            for p in parts:
                try:
                    numeric_line.append(float(p))
                except ValueError as e:
                    # CSV 解析中非数值字段是常见情况，记录后继续处理数值列
                    logger.debug(
                        f"Skipping non-numeric value in row: {e}",
                        exc_info=True,
                    )
            if numeric_line:
                numeric_lines.append(numeric_line)
        data = np.array(numeric_lines)

    if data.ndim == 1:
        data = data.reshape(-1, 1)
    if data.shape[1] == 1:
        data = np.column_stack([data, data])

    X = data[:, :-1]
    y = data[:, -1]
    input_dim = X.shape[1]

    await progress_updater(10.0, "Preparing datasets...")

    X_tensor = torch.FloatTensor(X)
    y_tensor = torch.FloatTensor(y)
    dataset = TensorDataset(X_tensor, y_tensor)
    train_size = int(0.8 * len(dataset))
    train_dataset, val_dataset = torch.utils.data.random_split(
        dataset, [train_size, len(dataset) - train_size]
    )

    device, _ = detect_device(device_preference)
    batch_size = hyperparameters.get("batch_size", 32)
    if device.type == "cuda":
        batch_size = get_optimal_batch_size(device, batch_size)

    num_workers = get_optimal_num_workers()
    train_loader = DataLoader(
        train_dataset, batch_size=batch_size, shuffle=True, num_workers=num_workers
    )
    val_loader = DataLoader(val_dataset, batch_size=batch_size, num_workers=num_workers)

    lnn_registry = registry_service.model_registry
    entry = lnn_registry.registry.get(model_name)
    if not entry:
        raise ValueError(f"Model '{model_name}' not found")

    model_class = get_torch_model_class(entry.info.model_type)
    if not model_class:
        raise ValueError(f"Unsupported model type: {entry.info.model_type}")

    hidden_size = min(256, max(64, input_dim * 2))
    config_obj = LNNConfig(
        input_size=input_dim,
        hidden_size=hidden_size,
        output_size=1,
        num_layers=2,
        dropout=0.1,
    )
    model = model_class(config_obj)

    use_amp = device.type == "cuda" and torch.cuda.is_available()
    epochs = hyperparameters.get("epochs", 100)

    await progress_updater(15.0, f"Starting training on {device.type}...")

    trainer = LNNTrainer(
        model=model,
        learning_rate=hyperparameters.get("learning_rate", 0.001),
        optimizer_type=hyperparameters.get("optimizer", "adam"),
        loss_type="mse",
        batch_size=batch_size,
        epochs=epochs,
        device=str(device),
        use_amp=use_amp,
    )

    start_time = time.perf_counter()
    history = {"train_loss": [], "val_loss": []}
    best_val_loss = float("inf")
    patience = 5
    patience_counter = 0

    for epoch in range(1, epochs + 1):
        if cancel_evt.is_set():
            raise asyncio.CancelledError()

        train_loss, train_acc = trainer.train_epoch(train_loader)
        val_loss, val_acc = trainer.validate(val_loader)

        history["train_loss"].append(train_loss)
        history["val_loss"].append(val_loss)

        if val_loss < best_val_loss:
            best_val_loss = val_loss
            patience_counter = 0
        else:
            patience_counter += 1

        progress = 15.0 + (epoch / epochs) * 80.0
        await progress_updater(
            progress,
            f"Training: epoch {epoch}/{epochs}, val_loss={val_loss:.4f}",
            {
                "epoch": epoch,
                "train_loss": round(train_loss, 4),
                "val_loss": round(val_loss, 4),
            },
        )

        if patience_counter >= patience:
            logger.info(f"Early stopping at epoch {epoch}")
            break

    training_time = time.perf_counter() - start_time
    final_val_loss = best_val_loss

    try:
        from app.utils.utils import get_metrics_collector

        m = get_metrics_collector()
        m.set_active_training_tasks(max(0, m._active_training_tasks - 1))
    except (ImportError, AttributeError, RuntimeError) as e:
        # 训练指标递减失败仅影响可观测性，不影响训练完成
        logger.debug(
            f"Failed to decrement active training tasks counter: {e}",
            exc_info=True,
        )

    return {
        "status": "completed",
        "model_name": model_name,
        "epochs_completed": epoch,
        "final_val_loss": round(final_val_loss, 4),
        "training_time": round(training_time, 2),
        "metrics": {
            "r2_score": None,
            "loss": round(final_val_loss, 4),
            "training_time": round(training_time, 2),
            "epochs_completed": epoch,
        },
    }


@router.post("/batch-inference")
async def batch_inference(
    request: LNNBatchInferenceRequest,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
):
    """Start batch inference asynchronously. Returns job_id immediately."""
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

        asyncio.create_task(task_manager.execute_task(record.job_id, batch_executor))

        return success(
            data={"job_id": record.job_id, "status": "queued"},
            message="Batch inference job queued",
        )

    except Exception as e:
        safe = safe_error_message(
            e, context=f"lnn.batch_inference_init[{request.model_name}]"
        )
        return error(
            code=ErrorCode.INTERNAL_ERROR,
            message=safe["message"],
            detail=safe.get("detail"),
        )


async def run_batch_inference_v2(
    job_id: str,
    model_name: str,
    input_data: list,
    batch_size: int,
    cancel_evt: asyncio.Event,
    progress_updater: Callable,
):
    """V2 batch inference executor with progress callbacks"""
    await progress_updater(5.0, "Loading model...")

    predictor = LNNPredictor.from_registry(
        registry=model_registry,
        model_name=model_name,
        use_amp=True,
        auto_device=True,
    )

    results = []
    total = len(input_data)

    for i in range(0, total, batch_size):
        if cancel_evt.is_set():
            raise asyncio.CancelledError()

        batch = input_data[i : i + batch_size]
        batch_results = []

        for sample in batch:
            result = predictor.predict(input_data=sample, return_confidence=True)
            value = result.value
            if hasattr(value, "tolist"):
                value = value.tolist()
            batch_results.append({"value": value, "confidence": result.confidence})

        results.extend(batch_results)

        progress = 10.0 + ((i + len(batch)) / total) * 85.0
        await progress_updater(progress, f"Processed {i + len(batch)}/{total} samples")

    await progress_updater(100.0, "Batch inference completed")

    return {
        "status": "completed",
        "total_samples": total,
        "results": results,
        "metrics": {"samples_processed": total},
    }
