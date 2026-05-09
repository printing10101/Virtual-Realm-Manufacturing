import os
import time
import asyncio
import logging
from datetime import datetime
from fastapi import APIRouter

from app.core.response import ErrorCode, error, success
from app.config import config
from app.models.schemas import (
    LNNPredictRequest,
    LNNTrainRequest,
    LNNModelInfo,
)
from app.ai.lnn.inference.registry import LNNModelRegistry, ModelRegistry
from app.ai.lnn.inference.predictor import LNNPredictor, PredictionResult
from app.ai.lnn.training.trainer import LNNTrainer

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/lnn", tags=["LNN Models"])

model_registry = LNNModelRegistry()
pytorch_registry = ModelRegistry()

training_tasks: dict[str, dict] = {}

MAX_CONCURRENT_TRAINING_TASKS = 3
_active_training_tasks: set[str] = set()
_training_semaphore = asyncio.Semaphore(MAX_CONCURRENT_TRAINING_TASKS)


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
):
    async with _training_semaphore:
        _active_training_tasks.add(task_id)
        try:
            training_tasks[task_id]["status"] = "in_progress"

            if not os.path.exists(data_path):
                training_tasks[task_id]["status"] = "failed"
                training_tasks[task_id]["message"] = f"Data file not found: {data_path}"
                return

            if not os.path.isfile(data_path):
                training_tasks[task_id]["status"] = "failed"
                training_tasks[task_id]["message"] = f"Not a regular file: {data_path}"
                return

            real_path = os.path.realpath(data_path)
            allowed_stem = os.path.realpath(config.storage.output_dir)
            if not real_path.startswith(allowed_stem + os.sep):
                training_tasks[task_id]["status"] = "failed"
                training_tasks[task_id]["message"] = (
                    f"File path is outside allowed directory: {data_path}"
                )
                return

            suffix = os.path.splitext(data_path)[1].lower()
            if suffix not in (".csv", ".txt", ".dat"):
                training_tasks[task_id]["status"] = "failed"
                training_tasks[task_id]["message"] = (
                    f"Unsupported file type '{suffix}', expected .csv/.txt/.dat"
                )
                return

            file_size = os.path.getsize(data_path)
            max_size = 100 * 1024 * 1024
            if file_size > max_size:
                training_tasks[task_id]["status"] = "failed"
                training_tasks[task_id]["message"] = (
                    f"File too large ({file_size / 1024 / 1024:.1f} MB), max {max_size / 1024 / 1024:.0f} MB"
                )
                return

            entry = model_registry.registry.get(model_name)
            if not entry:
                training_tasks[task_id]["status"] = "failed"
                training_tasks[task_id]["message"] = f"Model '{model_name}' not found"
                return

            from app.ai.lnn.inference.registry import get_torch_model_class

            model_class = get_torch_model_class(entry.info.model_type)
            if not model_class:
                training_tasks[task_id]["status"] = "failed"
                training_tasks[task_id]["message"] = f"Unsupported model type: {entry.info.model_type}"
                return

            import torch
            from torch.utils.data import DataLoader, TensorDataset
            import numpy as np

            data = np.loadtxt(data_path, delimiter=",")
            if data.ndim == 1:
                data = data.reshape(-1, 1)

            if data.size == 0:
                training_tasks[task_id]["status"] = "failed"
                training_tasks[task_id]["message"] = "Data file is empty"
                return

            if data.shape[0] < 2:
                training_tasks[task_id]["status"] = "failed"
                training_tasks[task_id]["message"] = (
                    f"Need at least 2 samples for train/val split, got {data.shape[0]}"
                )
                return

            if not np.isfinite(data).all():
                training_tasks[task_id]["status"] = "failed"
                training_tasks[task_id]["message"] = "Data contains NaN or Inf values"
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

            train_loader = DataLoader(train_dataset, batch_size=hyperparameters.get("batch_size", 32), shuffle=True)
            val_loader = DataLoader(val_dataset, batch_size=hyperparameters.get("batch_size", 32))

            model = model_class(
                model_name=model_name,
                input_dim=input_dim,
                output_dim=output_dim,
            )

            device = "cuda" if torch.cuda.is_available() else "cpu"

            trainer = LNNTrainer(
                model=model,
                learning_rate=hyperparameters.get("learning_rate", 0.001),
                optimizer_type=hyperparameters.get("optimizer", "adam"),
                loss_type="mse",
                batch_size=hyperparameters.get("batch_size", 32),
                epochs=hyperparameters.get("epochs", 100),
                device=device,
            )

            start_time = time.perf_counter()
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

        except Exception as e:
            training_tasks[task_id]["status"] = "failed"
            training_tasks[task_id]["message"] = f"Training failed: {e!s}"
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

        training_coro = run_training_task(
            task_id,
            request.model_name,
            request.data_path,
            hyperparams,
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
