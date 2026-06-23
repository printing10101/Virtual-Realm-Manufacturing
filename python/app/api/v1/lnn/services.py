"""LNN API 业务服务层。"""

import os
import time
import asyncio
import uuid
import logging
from typing import Callable
from datetime import datetime

import torch
import numpy as np
from torch.utils.data import DataLoader, TensorDataset

from app.core.response import ErrorCode, error, success
from app.core.safe_errors import safe_error_message
from app.audit.audit_log import AIModule, UserDecision, OperationStatus
from app.utils.ring_buffer import get_ring_log_buffer
from app.ai.lnn.inference.predictor import LNNPredictor, PredictionResult
from app.ai.lnn.inference.registry import (
    get_torch_model_class,
    is_quantized_model,
    get_quantized_model_name,
)
from app.ai.lnn.models.torch_base_lnn import LNNConfig
from app.ai.lnn.training.trainer import LNNTrainer
from app.ai.lnn.training.device_manager import (
    detect_device,
    get_optimal_batch_size,
    get_optimal_num_workers,
)
from app.tasks.task_manager import TaskType, TaskStatus
from app.models.schemas import (
    LNNModelInfo,
    AlternativePlan,
)
from app.api.v1.sse import sse_manager

logger = logging.getLogger(__name__)


def _format_size(size_bytes: int) -> str:
    """格式化文件大小为人类可读格式。"""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.2f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.2f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"


def _generate_prediction_reasoning(
    model_name: str,
    input_data: list[float],
    prediction: float | list[float],
    confidence: float | None,
    inference_time: float,
) -> str:
    """生成预测推理解释。"""
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
                f"置信度较高 ({confidence:.2f}),表明模型对当前输入数据的预测结果有较高的把握。"
            )
        elif confidence >= 0.5:
            reasoning_parts.append(
                f"置信度中等 ({confidence:.2f}),建议结合实际情况综合判断预测结果。"
            )
        else:
            reasoning_parts.append(
                f"置信度较低 ({confidence:.2f}),建议参考备选方案或调整输入数据后重新预测。"
            )

    reasoning_parts.append(f"推理耗时 {inference_time:.2f}ms。")

    return " ".join(reasoning_parts)


def _generate_alternatives(
    model_name: str,
    input_data: list[float],
    primary_value: float | list[float],
    primary_confidence: float,
) -> list[AlternativePlan]:
    """生成备选方案。"""
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
                expected_outcome=f"保守方案:预测值 {alt_1_value:.4f},偏向安全边际,适合对稳定性要求高的场景。",
                confidence=max(0.0, primary_confidence - 0.05),
                reasoning="保守方案通过降低预测值约5%提供额外的安全缓冲,适用于风险敏感型决策。",
            )
        )

        alternatives.append(
            AlternativePlan(
                plan_id=f"alt_{uuid.uuid4().hex[:8]}",
                parameters={
                    "optimization_target": "aggressive",
                    "efficiency_gain": "+5%",
                },
                expected_outcome=f"激进方案:预测值 {alt_2_value:.4f},偏向性能优化,适合追求效率的场景。",
                confidence=max(0.0, primary_confidence - 0.08),
                reasoning="激进方案通过提高预测值约5%追求性能最优,适用于对效率要求高的场景。",
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
                expected_outcome="保守方案:输出值整体下调5%,偏向安全边际,适合对稳定性要求高的场景。",
                confidence=max(0.0, primary_confidence - 0.05),
                reasoning="保守方案通过降低各输出值约5%提供额外的安全缓冲,适用于风险敏感型决策。",
            )
        )

        alternatives.append(
            AlternativePlan(
                plan_id=f"alt_{uuid.uuid4().hex[:8]}",
                parameters={
                    "optimization_target": "aggressive",
                    "efficiency_gain": "+5%",
                },
                expected_outcome="激进方案:输出值整体上调5%,偏向性能优化,适合追求效率的场景。",
                confidence=max(0.0, primary_confidence - 0.08),
                reasoning="激进方案通过提高各输出值约5%追求性能最优,适用于对效率要求高的场景。",
            )
        )

    return alternatives


async def _broadcast_error(task_id: str, code: str, message: str):
    """通过 SSE 广播错误消息。"""
    await sse_manager.broadcast(
        task_id,
        "error",
        {
            "code": code,
            "message": message,
            "details": {},
        },
    )


async def _run_training_task(  # pragma: no cover - legacy stub
    task_id: str,
    model_name: str,
    data_path: str,
    hyperparameters: dict,
    device_preference: str = "auto",
):
    """Legacy V1 训练执行器:已被 _run_training_task_async + task_manager 取代。

    保留为 stub 是为了:
      1. 避免被反射式 import(getattr / 模块 __getattr__)的下游代码踩坑;
      2. 在 health_check / 监控端点观测到时打印明确警告,便于排查残留调用方。

    实际的训练路径请参考 /api/v1/lnn/train → task_manager.execute_task →
    run_training_task_v2 链路。
    """
    logger.warning(
        "run_training_task v1 invoked for %s; please migrate to v2 path "
        "(task_manager + run_training_task_v2)",
        task_id,
    )
    return error(
        code=ErrorCode.GONE,
        message="run_training_task v1 is deprecated; use task_manager.execute_task with run_training_task_v2 instead.",
    )


async def run_training_task_v2(
    task_id: str,
    model_name: str,
    data_path: str,
    hyperparameters: dict,
    device_preference: str,
    cancel_evt: asyncio.Event,
    progress_updater: Callable,
):
    """V2 训练执行器,带进度回调和取消支持。"""
    try:
        from app.utils.utils import get_metrics_collector

        metrics = get_metrics_collector()
        metrics.set_active_training_tasks(max(0, metrics._active_training_tasks + 1))
    except (ImportError, AttributeError, RuntimeError) as e:
        logger.debug(
            f"Failed to increment active training tasks counter: {e}",
            exc_info=True,
        )

    await progress_updater(5.0, "Loading data...")

    try:
        data = np.loadtxt(data_path, delimiter=",", skiprows=1, dtype=float)
    except FileNotFoundError:
        raise FileNotFoundError(f"Data file not found: {data_path}")
    except (ValueError, UnicodeDecodeError):
        try:
            with open(data_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
        except FileNotFoundError:
            raise FileNotFoundError(f"Data file not found: {data_path}")
        numeric_lines = []
        for line in lines[1:]:
            parts = line.strip().split(",")
            numeric_line = []
            for p in parts:
                try:
                    numeric_line.append(float(p))
                except ValueError as e:
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

    from app.api.v1.lnn.dependencies import registry_service

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


async def _run_training_task_async(
    task_id: str,
    model_name: str,
    data_path: str,
    hyperparameters: dict,
    device: str,
):
    """在 FastAPI 主事件循环中跑训练任务。"""
    from datetime import datetime as _datetime
    from app.api.v1.lnn.dependencies import task_manager

    _TRAINING_QUEUES = getattr(task_manager, "_training_queues", {})
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
    """广播训练事件到 SSE 客户端。"""
    from app.api.v1.lnn.dependencies import task_manager

    _TRAINING_QUEUES = getattr(task_manager, "_training_queues", {})
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
            break
        except (RuntimeError, ValueError, KeyError) as exc:
            logger.warning(
                "lnn SSE consumer loop异常退出 | task_id=%s | exc=%s: %s",
                task_id,
                type(exc).__name__,
                exc,
            )
            break
        else:
            if cancel_evt.is_set() and progress_q.empty():
                break


async def _run_quantization_task_v2(
    task_id: str,
    model_name: str,
    quantization_type: str,
    calibration_data_path: str | None,
    cancel_evt: asyncio.Event,
    progress_updater: Callable,
):
    """真正的量化执行器(可取消,带进度回调)。"""
    from app.ai.lnn.quantization.quantizer import (
        Quantizer,
        QuantizationConfig,
        QuantizationType,
    )
    from app.api.v1.lnn.dependencies import (
        model_registry,
        pytorch_registry,
    )

    await progress_updater(5.0, "加载模型元信息...")

    entry = model_registry.registry.get(model_name)
    if not entry:
        raise ValueError(f"Model '{model_name}' not found")

    model_class = get_torch_model_class(entry.info.model_type)
    if not model_class:
        raise ValueError(f"Unsupported model type: {entry.info.model_type}")

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
    except FileNotFoundError:
        raise FileNotFoundError(
            f"Model file not found: {entry.info.model_path}"
        )
    except (OSError, RuntimeError, ValueError, TypeError) as e:
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
            calibration_data = np.loadtxt(calibration_data_path, delimiter=",")
            if calibration_data.ndim == 1:
                calibration_data = calibration_data.reshape(-1, 1)
            if calibration_data.shape[1] == 1:
                calibration_data = np.column_stack(
                    [calibration_data, calibration_data]
                )
            calibration_data = calibration_data[:, :-1]
        except Exception as e:
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


async def _run_quantization_task(  # pragma: no cover - legacy stub
    task_id: str,
    model_name: str,
    quantization_type: str,
    calibration_data_path: str | None = None,
):
    """兼容旧调用的 stub,已由 task_manager + _run_quantization_task_v2 取代。"""
    logger.error(
        "_run_quantization_task v1 invoked for %s; please migrate to v2 path "
        "(task_manager + _run_quantization_task_v2)",
        task_id,
    )
    return error(
        code=ErrorCode.GONE,
        message="_run_quantization_task v1 is deprecated; use task_manager.execute_task with _run_quantization_task_v2 instead.",
    )


async def run_batch_inference_v2(
    job_id: str,
    model_name: str,
    input_data: list,
    batch_size: int,
    cancel_evt: asyncio.Event,
    progress_updater: Callable,
):
    """V2 批量推理执行器,带进度回调。"""
    from app.api.v1.lnn.dependencies import model_registry

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


async def sse_event_generator(task_id: str, client_id: str):
    """SSE 事件生成器,用于训练任务状态更新。"""
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
