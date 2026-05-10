import os
import time
import asyncio
import uuid
import logging
from datetime import datetime
from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.core.response import ErrorCode, error, success
from app.config import config
from app.models.schemas import (
    LNNPredictRequest,
    LNNTrainRequest,
    LNNModelInfo,
    LNNQuantizeRequest,
    LNNModelSizeResponse,
)
from app.ai.lnn.inference.registry import LNNModelRegistry, ModelRegistry
from app.ai.lnn.inference.predictor import LNNPredictor, PredictionResult
from app.ai.lnn.inference.model_cache import ModelCache
from app.ai.lnn.inference.registry import (
    is_quantized_model,
    get_quantized_model_name,
    get_base_model_name,
)
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

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/lnn", tags=["LNN Models"])

model_registry = LNNModelRegistry()
pytorch_registry = ModelRegistry()
model_cache = ModelCache()

training_tasks: dict[str, dict] = {}

MAX_CONCURRENT_TRAINING_TASKS = 3
_active_training_tasks: set[str] = set()
_training_semaphore = asyncio.Semaphore(MAX_CONCURRENT_TRAINING_TASKS)


async def _broadcast_error(task_id: str, code: str, message: str):
    """Broadcast error message via SSE."""
    await sse_manager.broadcast(task_id, "error", {
        "code": code,
        "message": message,
        "details": {},
    })


@router.post("/predict")
async def predict_lnn(request: LNNPredictRequest):
    try:
        entry = model_registry.registry.get(request.model_name)
        if not entry:
            return error(
                code=ErrorCode.NOT_FOUND,
                message=f"Model '{request.model_name}' not found",
            )

        model_info = entry.info

        if not request.input_data:
            return error(
                code=ErrorCode.INVALID_REQUEST,
                message="输入数据必须为非空列表",
            )

        if any(not isinstance(x, (int, float)) for x in request.input_data):
            return error(
                code=ErrorCode.INVALID_REQUEST,
                message="输入数据必须为数值类型",
            )

        expected_dim = len(model_info.input_features) if model_info.input_features else None
        if expected_dim:
            input_len = len(request.input_data)
            if input_len != expected_dim and input_len % expected_dim != 0:
                return error(
                    code=ErrorCode.INVALID_REQUEST,
                    message=f"输入维度不匹配: 期望{expected_dim}维或其倍数，实际{input_len}维",
                )

        predictor = LNNPredictor.from_registry(
            registry=model_registry,
            model_name=request.model_name,
            use_amp=True,
            auto_device=True,
        )

        try:
            result = predictor.predict(
                input_data=request.input_data,
                return_confidence=request.return_confidence,
            )
        except Exception as model_err:
            logger.error(f"Model inference error: {model_err}")
            return error(
                code=ErrorCode.INTERNAL_ERROR,
                message=f"Model inference failed: {model_err!s}",
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
        confidence = result.confidence if request.return_confidence else None
        inference_time = result.inference_time

        model_info_response = LNNModelInfo(
            name=model_info.name,
            version=model_info.version,
            last_updated=datetime.now().isoformat(),
        )

        response_data = {
            "value": value,
            "inference_time": inference_time,
            "model_info": model_info_response.model_dump(),
        }
        if confidence is not None:
            response_data["confidence"] = confidence

        return success(data=response_data, message="Prediction completed successfully")

    except KeyError:
        return error(
            code=ErrorCode.NOT_FOUND,
            message=f"Model '{request.model_name}' not found in registry",
        )
    except Exception as e:
        return error(
            code=ErrorCode.INTERNAL_ERROR,
            message=f"Prediction failed: {e!s}",
        )


async def run_training_task(
    task_id: str,
    model_name: str,
    data_path: str,
    hyperparameters: dict,
    device_preference: str = "auto",
):
    async with _training_semaphore:
        _active_training_tasks.add(task_id)
        try:
            training_tasks[task_id]["status"] = "in_progress"

            if not os.path.exists(data_path):
                training_tasks[task_id]["status"] = "failed"
                training_tasks[task_id]["message"] = f"Data file not found: {data_path}"
                await _broadcast_error(task_id, "DATA_NOT_FOUND", f"Data file not found: {data_path}")
                return

            if not os.path.isfile(data_path):
                training_tasks[task_id]["status"] = "failed"
                training_tasks[task_id]["message"] = f"Not a regular file: {data_path}"
                await _broadcast_error(task_id, "INVALID_FILE", f"Not a regular file: {data_path}")
                return

            real_path = os.path.realpath(data_path)
            allowed_stem = os.path.realpath(config.storage.output_dir)
            if not real_path.startswith(allowed_stem + os.sep):
                training_tasks[task_id]["status"] = "failed"
                training_tasks[task_id]["message"] = (
                    f"File path is outside allowed directory: {data_path}"
                )
                await _broadcast_error(task_id, "PATH_NOT_ALLOWED", f"File path is outside allowed directory: {data_path}")
                return

            suffix = os.path.splitext(data_path)[1].lower()
            if suffix not in (".csv", ".txt", ".dat"):
                training_tasks[task_id]["status"] = "failed"
                training_tasks[task_id]["message"] = (
                    f"Unsupported file type '{suffix}', expected .csv/.txt/.dat"
                )
                await _broadcast_error(task_id, "UNSUPPORTED_FILE_TYPE", f"Unsupported file type '{suffix}'")
                return

            file_size = os.path.getsize(data_path)
            max_size = 100 * 1024 * 1024
            if file_size > max_size:
                training_tasks[task_id]["status"] = "failed"
                training_tasks[task_id]["message"] = (
                    f"File too large ({file_size / 1024 / 1024:.1f} MB), max {max_size / 1024 / 1024:.0f} MB"
                )
                await _broadcast_error(task_id, "FILE_TOO_LARGE", f"File too large ({file_size / 1024 / 1024:.1f} MB)")
                return

            entry = model_registry.registry.get(model_name)
            if not entry:
                training_tasks[task_id]["status"] = "failed"
                training_tasks[task_id]["message"] = f"Model '{model_name}' not found"
                await _broadcast_error(task_id, "MODEL_NOT_FOUND", f"Model '{model_name}' not found")
                return

            from app.ai.lnn.inference.registry import get_torch_model_class

            model_class = get_torch_model_class(entry.info.model_type)
            if not model_class:
                training_tasks[task_id]["status"] = "failed"
                training_tasks[task_id]["message"] = f"Unsupported model type: {entry.info.model_type}"
                await _broadcast_error(task_id, "UNSUPPORTED_MODEL_TYPE", f"Unsupported model type: {entry.info.model_type}")
                return

            import torch
            from torch.utils.data import DataLoader, TensorDataset
            import numpy as np
            from multiprocessing import cpu_count

            data = np.loadtxt(data_path, delimiter=",")
            if data.ndim == 1:
                data = data.reshape(-1, 1)

            if data.size == 0:
                training_tasks[task_id]["status"] = "failed"
                training_tasks[task_id]["message"] = "Data file is empty"
                await _broadcast_error(task_id, "EMPTY_DATA", "Data file is empty")
                return

            if data.shape[0] < 2:
                training_tasks[task_id]["status"] = "failed"
                training_tasks[task_id]["message"] = (
                    f"Need at least 2 samples for train/val split, got {data.shape[0]}"
                )
                await _broadcast_error(task_id, "INSUFFICIENT_DATA", f"Need at least 2 samples, got {data.shape[0]}")
                return

            if not np.isfinite(data).all():
                training_tasks[task_id]["status"] = "failed"
                training_tasks[task_id]["message"] = "Data contains NaN or Inf values"
                await _broadcast_error(task_id, "INVALID_DATA_VALUES", "Data contains NaN or Inf values")
                return

            if data.shape[1] == 1:
                data = np.column_stack([data, data])

            X = data[:, :-1]
            y = data[:, -1]
            input_dim = data.shape[1] - 1
            output_dim = 1

            X_tensor = torch.FloatTensor(X)
            y_tensor = torch.FloatTensor(y)
            dataset = TensorDataset(X_tensor, y_tensor)
            train_size = int(0.8 * len(dataset))
            val_size = len(dataset) - train_size
            train_dataset, val_dataset = torch.utils.data.random_split(dataset, [train_size, val_size])

            device, device_info = detect_device(device_preference)

            batch_size = hyperparameters.get("batch_size", 32)
            if device.type == "cuda":
                batch_size = get_optimal_batch_size(device, batch_size)

            num_workers = get_optimal_num_workers()
            pin_memory = device.type == "cuda"

            train_loader = DataLoader(
                train_dataset,
                batch_size=batch_size,
                shuffle=True,
                num_workers=num_workers,
                pin_memory=pin_memory,
            )
            val_loader = DataLoader(
                val_dataset,
                batch_size=batch_size,
                num_workers=num_workers,
                pin_memory=pin_memory,
            )

            from app.ai.lnn.models.torch_base_lnn import LNNConfig
            from app.ai.lnn.models.torch_cfc_model import CFCModel as TorchCFCModel
            from app.ai.lnn.models.torch_ltc_model import LTCModel as TorchLTCModel
            from app.ai.lnn.models.torch_hybrid_lnn import HybridLNN as TorchHybridLNN

            model_type_key = model_name.split("_")[0].upper() if "_" in model_name else "CFC"
            if "ltc" in model_name.lower() or model_type_key == "LTC":
                TorchModel = TorchLTCModel
            elif "hybrid" in model_name.lower() or model_type_key == "HYBRID":
                TorchModel = TorchHybridLNN
            else:
                TorchModel = TorchCFCModel

            hidden_size = min(256, max(64, input_dim * 2))

            config_obj = LNNConfig(
                input_size=input_dim,
                hidden_size=hidden_size,
                output_size=output_dim,
                num_layers=2,
                dropout=0.1,
            )
            model = TorchModel(config_obj)

            use_amp = device.type == "cuda" and torch.cuda.is_available()

            epochs = hyperparameters.get("epochs", 100)
            progress_cb = create_progress_callback(task_id, epochs)
            cancel_evt = sse_manager.get_cancel_event(task_id)

            trainer = LNNTrainer(
                model=model,
                learning_rate=hyperparameters.get("learning_rate", 0.001),
                optimizer_type=hyperparameters.get("optimizer", "adam"),
                loss_type="mse",
                batch_size=batch_size,
                epochs=epochs,
                device=str(device),
                use_amp=use_amp,
                progress_callback=progress_cb,
                cancel_event=cancel_evt,
            )

            start_time = time.perf_counter()
            try:
                history = trainer.fit(train_loader, val_loader)
                training_time = time.perf_counter() - start_time

                final_val_loss = history["val_loss"][-1] if history["val_loss"] else 0.0

                r2_score = None
                if y is not None:
                    model.eval()
                    all_preds = []
                    all_targets = []
                    with torch.no_grad():
                        for batch_X, batch_y in val_loader:
                            batch_X = batch_X.to(device)
                            outputs = model(batch_X)
                            if isinstance(outputs, tuple):
                                outputs = outputs[0]
                            all_preds.append(outputs.cpu().numpy())
                            all_targets.append(batch_y.numpy())

                    preds = np.concatenate(all_preds).flatten()
                    targets = np.concatenate(all_targets).flatten()

                    ss_res = np.sum((targets - preds) ** 2)
                    ss_tot = np.sum((targets - np.mean(targets)) ** 2)
                    r2_score = float(1.0 - ss_res / ss_tot) if ss_tot > 0 else 0.0

                training_tasks[task_id]["status"] = "success"
                training_tasks[task_id]["message"] = "Training completed successfully"
                training_tasks[task_id]["metrics"] = {
                    "r2_score": round(r2_score, 4) if r2_score is not None else None,
                    "loss": round(final_val_loss, 4),
                    "training_time": round(training_time, 2),
                    "epochs_completed": len(history["train_loss"]),
                }

                await progress_cb.send_complete("completed", final_val_loss, training_time)

            except asyncio.CancelledError:
                training_tasks[task_id]["status"] = "cancelled"
                training_tasks[task_id]["message"] = "Training cancelled by user"
                await progress_cb.send_error("CANCELLED", "Training cancelled by user")
            except Exception as e:
                training_tasks[task_id]["status"] = "failed"
                training_tasks[task_id]["message"] = f"Training failed: {e!s}"
                await progress_cb.send_error("TRAINING_ERROR", str(e), {"exception_type": type(e).__name__})

        finally:
            _active_training_tasks.discard(task_id)


@router.post("/train")
async def train_lnn(request: LNNTrainRequest):
    try:
        import uuid
        task_id = str(uuid.uuid4())

        training_tasks[task_id] = {
            "status": "in_progress",
            "message": "Training task started",
            "metrics": None,
        }

        hyperparams = {
            "learning_rate": request.hyperparameters.learning_rate,
            "epochs": request.hyperparameters.epochs,
            "batch_size": request.hyperparameters.batch_size,
            "optimizer": request.hyperparameters.optimizer,
        }

        device_pref = getattr(request, 'device', 'auto')

        training_coro = run_training_task(
            task_id,
            request.model_name,
            request.data_path,
            hyperparams,
            device_pref,
        )
        asyncio.create_task(training_coro)

        deadline = time.monotonic() + 30.0
        while task_id not in _active_training_tasks:
            if time.monotonic() > deadline:
                return success(
                    data={
                        "status": "in_progress",
                        "message": "Training task queued (waiting for available slot)",
                    },
                    message="Training task queued",
                )
            await asyncio.sleep(0.01)

        task_result = training_tasks[task_id]

        response_data = {
            "status": task_result["status"],
            "message": task_result["message"],
        }
        if task_result.get("metrics"):
            response_data["metrics"] = task_result["metrics"]

        return success(data=response_data, message="Training task started")

    except Exception as e:
        return error(
            code=ErrorCode.INTERNAL_ERROR,
            message=f"Training initiation failed: {e!s}",
        )


@router.get("/models")
async def list_lnn_models():
    try:
        models = model_registry.list_models(return_objects=True)

        models_list = []
        for model_info in models:
            models_list.append({
                "name": model_info.name,
                "model_type": model_info.model_type,
                "version": model_info.version,
                "input_features": model_info.input_features,
                "output_features": model_info.output_features,
            })

        return success(data={"models": models_list, "total": len(models_list)}, message="Models retrieved successfully")

    except Exception as e:
        return error(
            code=ErrorCode.INTERNAL_ERROR,
            message=f"Failed to retrieve models: {e!s}",
        )


@router.get("/models/{model_name}/info")
async def get_model_info(model_name: str):
    try:
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

    except Exception as e:
        return error(
            code=ErrorCode.INTERNAL_ERROR,
            message=f"Failed to retrieve model info: {e!s}",
        )


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

        return success(data=info_data, message="Model validation completed successfully")

    except Exception as e:
        return error(
            code=ErrorCode.INTERNAL_ERROR,
            message=f"Model validation failed: {e!s}",
        )


@router.get("/health")
async def health_check():
    """LNN 系统健康检查"""
    try:
        model_count = len(model_registry.registry)
        active_tasks = len(_active_training_tasks)
        total_slots = MAX_CONCURRENT_TRAINING_TASKS

        health_status = {
            "status": "healthy" if model_count > 0 else "degraded",
            "models_registered": model_count,
            "active_training_tasks": active_tasks,
            "available_training_slots": total_slots - active_tasks,
            "max_concurrent_tasks": total_slots,
        }

        return success(data=health_status, message="Health check completed")

    except Exception as e:
        return error(
            code=ErrorCode.INTERNAL_ERROR,
            message=f"Health check failed: {e!s}",
        )


@router.get("/tasks")
async def list_training_tasks():
    """列出所有训练任务"""
    try:
        tasks_list = []
        for task_id, task_info in training_tasks.items():
            tasks_list.append({
                "task_id": task_id,
                "status": task_info["status"],
                "message": task_info["message"],
                "metrics": task_info.get("metrics"),
                "is_active": task_id in _active_training_tasks,
            })

        return success(data={"tasks": tasks_list, "total": len(tasks_list)}, message="Training tasks retrieved")

    except Exception as e:
        return error(
            code=ErrorCode.INTERNAL_ERROR,
            message=f"Failed to retrieve training tasks: {e!s}",
        )


@router.get("/cache/stats")
async def get_cache_stats():
    """获取模型缓存统计信息"""
    try:
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
            message="Cache statistics retrieved successfully"
        )

    except Exception as e:
        return error(
            code=ErrorCode.INTERNAL_ERROR,
            message=f"Failed to retrieve cache statistics: {e!s}",
        )


@router.delete("/cache/clear")
async def clear_cache():
    """清空所有模型缓存"""
    try:
        count, memory_freed = model_cache.clear()

        return success(
            data={
                "models_cleared": count,
                "memory_freed_bytes": memory_freed,
                "memory_freed_mb": round(memory_freed / (1024 * 1024), 2),
            },
            message=f"Cache cleared successfully: {count} models removed"
        )

    except Exception as e:
        return error(
            code=ErrorCode.INTERNAL_ERROR,
            message=f"Failed to clear cache: {e!s}",
        )


@router.get("/device/info")
async def get_device_info():
    """返回系统中可用的计算设备信息"""
    try:
        import torch

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
            "cudnn_version": torch.backends.cudnn.version() if torch.cuda.is_available() else None,
        }

        return success(data=response_data, message="Device info retrieved successfully")

    except Exception as e:
        return error(
            code=ErrorCode.INTERNAL_ERROR,
            message=f"Failed to retrieve device info: {e!s}",
        )


@router.get("/device/status")
async def get_device_status_endpoint():
    """返回当前设备利用率和温度等信息"""
    try:
        import torch

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
                "total_memory_mb": round(torch.cuda.get_device_properties(gpu_index).total_memory / (1024 ** 2), 2),
                "allocated_memory_mb": round(torch.cuda.memory_allocated(gpu_index) / (1024 ** 2), 2),
                "reserved_memory_mb": round(torch.cuda.memory_reserved(gpu_index) / (1024 ** 2), 2),
                "max_memory_mb": round(torch.cuda.max_memory_allocated(gpu_index) / (1024 ** 2), 2),
            }

        return success(data=response_data, message="Device status retrieved successfully")

    except Exception as e:
        return error(
            code=ErrorCode.INTERNAL_ERROR,
            message=f"Failed to retrieve device status: {e!s}",
        )


@router.post("/device/clear-cache")
async def clear_device_cache():
    """清空GPU缓存"""
    try:
        import torch

        if not torch.cuda.is_available():
            return error(
                code=ErrorCode.INVALID_REQUEST,
                message="No CUDA device available",
            )

        clear_gpu_memory(torch.device("cuda"))

        return success(
            data={"message": "GPU cache cleared successfully"},
            message="Device cache cleared"
        )

    except Exception as e:
        return error(
            code=ErrorCode.INTERNAL_ERROR,
            message=f"Failed to clear device cache: {e!s}",
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

    Clients connect to this endpoint to receive live training progress,
    completion, and error events for the specified task.
    """
    if task_id not in training_tasks:
        return error(
            code=ErrorCode.NOT_FOUND,
            message=f"Training task '{task_id}' not found",
        )

    client_id = f"client_{uuid.uuid4().hex[:8]}"
    logger.info(f"Client {client_id} connecting to SSE stream for task {task_id}")

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
    """Cancel a running training task via SSE signal."""
    if task_id not in training_tasks:
        return error(
            code=ErrorCode.NOT_FOUND,
            message=f"Training task '{task_id}' not found",
        )

    if task_id not in _active_training_tasks:
        return error(
            code=ErrorCode.INVALID_REQUEST,
            message=f"Training task '{task_id}' is not currently running",
        )

    await sse_manager.signal_cancel(task_id)
    training_tasks[task_id]["status"] = "cancelling"
    training_tasks[task_id]["message"] = "Training cancellation requested"

    return success(
        data={"task_id": task_id, "status": "cancelling"},
        message="Training cancellation requested",
    )


quantization_tasks: dict[str, dict] = {}


def _format_size(size_bytes: int) -> str:
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.2f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.2f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"


async def _run_quantization_task(
    task_id: str,
    model_name: str,
    quantization_type: str,
    calibration_data_path: str | None = None,
):
    try:
        from app.ai.lnn.quantization.quantizer import (
            Quantizer,
            QuantizationConfig,
            QuantizationType,
        )
        from app.ai.lnn.inference.registry import get_torch_model_class

        entry = model_registry.registry.get(model_name)
        if not entry:
            quantization_tasks[task_id]["status"] = "failed"
            quantization_tasks[task_id]["message"] = f"Model '{model_name}' not found"
            return

        if not os.path.exists(entry.info.model_path):
            quantization_tasks[task_id]["status"] = "failed"
            quantization_tasks[task_id]["message"] = f"Model file not found: {entry.info.model_path}"
            return

        quantization_tasks[task_id]["status"] = "in_progress"

        model_class = get_torch_model_class(entry.info.model_type)
        if not model_class:
            quantization_tasks[task_id]["status"] = "failed"
            quantization_tasks[task_id]["message"] = f"Unsupported model type: {entry.info.model_type}"
            return

        from app.ai.lnn.models.torch_base_lnn import LNNConfig

        config_obj = LNNConfig(
            input_size=len(entry.info.input_features),
            hidden_size=128,
            output_size=len(entry.info.output_features),
            num_layers=2,
            dropout=0.1,
        )
        model = model_class(config_obj)

        try:
            model.load(entry.info.model_path)
            model.build()
        except Exception:
            pass

        model.eval()

        quant_type = QuantizationType.DYNAMIC if quantization_type == "dynamic" else QuantizationType.STATIC
        quant_config = QuantizationConfig(quantization_type=quant_type)

        calibration_data = None
        if quant_type == QuantizationType.STATIC:
            if not calibration_data_path or not os.path.exists(calibration_data_path):
                quantization_tasks[task_id]["status"] = "failed"
                quantization_tasks[task_id]["message"] = "Calibration data path required for static quantization"
                return

            try:
                import numpy as np
                calibration_data = np.loadtxt(calibration_data_path, delimiter=",")
                if calibration_data.ndim == 1:
                    calibration_data = calibration_data.reshape(-1, 1)
                if calibration_data.shape[1] == 1:
                    calibration_data = np.column_stack([calibration_data, calibration_data])
                calibration_data = calibration_data[:, :-1]
            except Exception as e:
                quantization_tasks[task_id]["status"] = "failed"
                quantization_tasks[task_id]["message"] = f"Failed to load calibration data: {e}"
                return

        quantized_model_name = get_quantized_model_name(model_name)
        output_dir = os.path.dirname(entry.info.model_path)
        quantized_model_path = os.path.join(output_dir, f"{quantized_model_name}.pt")

        quantizer = Quantizer(quant_config)

        quantized_model, result = quantizer.quantize(
            model=model,
            calibration_data=calibration_data,
            save_path=quantized_model_path,
            metadata={
                "base_model": model_name,
                "quantization_type": quantization_type,
            },
        )

        original_size = quantizer.get_model_size(entry.info.model_path)
        quantized_size = quantizer.get_model_size(quantized_model_path)
        result.original_size_bytes = original_size
        result.quantized_size_bytes = quantized_size

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

        quantization_tasks[task_id]["status"] = "success"
        quantization_tasks[task_id]["message"] = "Quantization completed successfully"
        quantization_tasks[task_id]["metrics"] = {
            "quantized_model_name": quantized_model_name,
            "quantized_model_path": quantized_model_path,
            "original_size_bytes": original_size,
            "quantized_size_bytes": quantized_size,
            "original_size_human": _format_size(original_size),
            "quantized_size_human": _format_size(quantized_size),
            "compression_ratio": round(result.compression_ratio, 4),
            "speedup_ratio": round(result.speedup_ratio, 4),
            "quantization_time_seconds": round(result.quantization_time_seconds, 2),
        }

    except Exception as e:
        logger.error(f"Quantization task {task_id} failed: {e}")
        quantization_tasks[task_id]["status"] = "failed"
        quantization_tasks[task_id]["message"] = f"Quantization failed: {e!s}"


@router.post("/models/{model_name}/quantize")
async def quantize_model(model_name: str, request: LNNQuantizeRequest):
    """Quantize a model using INT8 quantization."""
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

        if request.quantization_type == "static" and not request.calibration_data_path:
            return error(
                code=ErrorCode.INVALID_REQUEST,
                message="Calibration data path is required for static quantization",
            )

        task_id = str(uuid.uuid4())

        quantization_tasks[task_id] = {
            "status": "in_progress",
            "message": "Quantization task started",
            "metrics": None,
        }

        quantization_coro = _run_quantization_task(
            task_id,
            model_name,
            request.quantization_type,
            request.calibration_data_path,
        )
        asyncio.create_task(quantization_coro)

        deadline = time.monotonic() + 60.0
        while quantization_tasks[task_id]["status"] == "in_progress":
            if time.monotonic() > deadline:
                break
            await asyncio.sleep(0.1)

        task_result = quantization_tasks[task_id]

        response_data = {
            "task_id": task_id,
            "status": task_result["status"],
            "message": task_result["message"],
        }
        if task_result.get("metrics"):
            response_data["metrics"] = task_result["metrics"]

        return success(data=response_data, message="Quantization completed")

    except Exception as e:
        return error(
            code=ErrorCode.INTERNAL_ERROR,
            message=f"Model quantization failed: {e!s}",
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
        original_size = os.path.getsize(original_path) if os.path.exists(original_path) else 0

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
            quantized_size_human=_format_size(quantized_size) if quantized_size else None,
            size_reduction_bytes=original_size - quantized_size if quantized_size else None,
            size_reduction_percent=round((1.0 - quantized_size / original_size) * 100, 2) if quantized_size and original_size > 0 else None,
        )

        return success(data=response.model_dump(), message="Model size retrieved successfully")

    except Exception as e:
        return error(
            code=ErrorCode.INTERNAL_ERROR,
            message=f"Failed to get model size: {e!s}",
        )
