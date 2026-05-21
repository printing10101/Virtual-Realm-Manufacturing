"""Agent Gateway API endpoints."""

from __future__ import annotations

import asyncio
import logging
import os
import time
import uuid

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.core.response import ErrorCode, error, success
from app.core.permissions import paper_only_guard
from app.agent.auth import agent_token_store
from app.agent.middleware import (
    agent_audit_log,
)
from app.models.schemas import (
    AgentTokenCreateRequest,
    AgentTokenResponse,
    AgentPredictRequest,
    AgentTrainRequest,
    AgentExecuteRequest,
)
from app.ai.lnn.inference.predictor import LNNPredictor, PredictionResult
from app.services.model_registry_service import get_model_registry_service
from app.api.v1.sse import sse_manager, create_progress_callback

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/agent/v1", tags=["Agent Gateway"])

# Use the unified service layer — do NOT instantiate LNNModelRegistry directly
registry_service = get_model_registry_service()
model_registry = registry_service.model_registry
agent_model_cache = registry_service.model_cache
training_tasks = registry_service.get_training_tasks()

MAX_CONCURRENT_TRAINING = 3
_active_training: set[str] = set()
_training_sem = asyncio.Semaphore(MAX_CONCURRENT_TRAINING)


@router.get("/health")
async def agent_health():
    """健康检查（R类，免认证）"""
    return {
        "status": "healthy",
        "timestamp": time.time(),
        "models_registered": len(model_registry.registry),
    }


@router.get("/models")
async def list_models():
    """已注册模型列表（R类）"""
    models = model_registry.list_models(return_objects=True)
    return success(
        data={
            "models": [
                {
                    "name": m.name,
                    "model_type": m.model_type,
                    "version": m.version,
                    "input_features": m.input_features,
                    "output_features": m.output_features,
                }
                for m in models
            ],
            "total": len(models),
        }
    )


@router.get("/models/{name}/info")
async def model_info(name: str):
    """模型详细信息（R类）"""
    entry = model_registry.registry.get(name)
    if not entry:
        return error(code=ErrorCode.NOT_FOUND, message=f"Model '{name}' not found")

    info = entry.info
    return success(
        data={
            "name": info.name,
            "model_type": info.model_type,
            "model_path": info.model_path,
            "input_features": info.input_features,
            "output_features": info.output_features,
            "version": info.version,
            "is_loaded": entry.is_loaded,
            "access_count": entry.access_count,
        }
    )


@router.post("/predict")
async def agent_predict(request: AgentPredictRequest):
    """LNN 预测（R类）"""
    try:
        entry = model_registry.registry.get(request.model_name)
        if not entry:
            return error(
                code=ErrorCode.NOT_FOUND,
                message=f"Model '{request.model_name}' not found",
            )

        if not request.input_data or any(
            not isinstance(x, (int, float)) for x in request.input_data
        ):
            return error(
                code=ErrorCode.INVALID_REQUEST, message="输入数据必须为非空数值数组"
            )

        expected_dim = (
            len(entry.info.input_features) if entry.info.input_features else None
        )
        if expected_dim:
            input_len = len(request.input_data)
            if input_len != expected_dim and input_len % expected_dim != 0:
                return error(
                    code=ErrorCode.INVALID_REQUEST,
                    message=f"输入维度不匹配: 期望{expected_dim}维或其倍数，实际{input_len}维",
                )

        predictor = agent_model_cache.get(request.model_name)
        if predictor is None:
            predictor = LNNPredictor.from_registry(
                registry=model_registry,
                model_name=request.model_name,
                use_amp=True,
                auto_device=True,
            )
            agent_model_cache.put(request.model_name, predictor)

        result = predictor.predict(
            input_data=request.input_data,
            return_confidence=request.return_confidence,
        )

        if not isinstance(result, PredictionResult):
            result = PredictionResult(value=result, confidence=0.0, inference_time=0.0)

        value = result.value
        if hasattr(value, "tolist"):
            value = value.tolist()
        if isinstance(value, list) and len(value) == 1:
            value = value[0]

        resp = {
            "value": value,
            "inference_time": result.inference_time,
            "model_info": {
                "name": entry.info.name,
                "version": entry.info.version,
            },
        }
        if request.return_confidence:
            resp["confidence"] = result.confidence

        return success(data=resp, message="Prediction completed")

    except Exception as e:
        return error(code=ErrorCode.INTERNAL_ERROR, message=f"Prediction failed: {e!s}")


async def _run_agent_training(
    task_id: str,
    model_name: str,
    data_path: str,
    hyperparameters: dict,
    device: str = "auto",
):
    """Background training task."""
    async with _training_sem:
        _active_training.add(task_id)
        try:
            training_tasks[task_id]["status"] = "in_progress"

            if not os.path.exists(data_path):
                training_tasks[task_id]["status"] = "failed"
                training_tasks[task_id]["message"] = f"Data file not found: {data_path}"
                return

            entry = model_registry.registry.get(model_name)
            if not entry:
                training_tasks[task_id]["status"] = "failed"
                training_tasks[task_id]["message"] = f"Model '{model_name}' not found"
                return

            import torch
            import numpy as np
            from torch.utils.data import DataLoader, TensorDataset
            from app.ai.lnn.models.torch_base_lnn import LNNConfig
            from app.ai.lnn.models.torch_cfc_model import CFCModel as TorchCFCModel
            from app.ai.lnn.training.trainer import LNNTrainer
            from app.ai.lnn.training.device_manager import (
                detect_device,
                get_optimal_batch_size,
                get_optimal_num_workers,
            )

            data = np.loadtxt(data_path, delimiter=",")
            if data.ndim == 1:
                data = data.reshape(-1, 1)
            if data.shape[0] < 2:
                training_tasks[task_id]["status"] = "failed"
                training_tasks[task_id]["message"] = "Need at least 2 samples"
                return

            X = data[:, :-1]
            y = data[:, -1]
            input_dim = data.shape[1] - 1

            X_tensor = torch.FloatTensor(X)
            y_tensor = torch.FloatTensor(y)
            dataset = TensorDataset(X_tensor, y_tensor)
            train_size = int(0.8 * len(dataset))
            train_ds, val_ds = torch.utils.data.random_split(
                dataset, [train_size, len(dataset) - train_size]
            )

            device_obj, _ = detect_device(device)
            batch_size = hyperparameters.get("batch_size", 32)
            if device_obj.type == "cuda":
                batch_size = get_optimal_batch_size(device_obj, batch_size)
            num_workers = get_optimal_num_workers()

            train_loader = DataLoader(
                train_ds, batch_size=batch_size, shuffle=True, num_workers=num_workers
            )
            val_loader = DataLoader(
                val_ds, batch_size=batch_size, num_workers=num_workers
            )

            hidden_size = min(256, max(64, input_dim * 2))
            config_obj = LNNConfig(
                input_size=input_dim,
                hidden_size=hidden_size,
                output_size=1,
                num_layers=2,
                dropout=0.1,
            )
            model = TorchCFCModel(config_obj)

            use_amp = device_obj.type == "cuda" and torch.cuda.is_available()
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
                device=str(device_obj),
                use_amp=use_amp,
                progress_callback=progress_cb,
                cancel_event=cancel_evt,
            )

            start = time.perf_counter()
            try:
                history = trainer.fit(train_loader, val_loader)
                elapsed = time.perf_counter() - start
                final_val_loss = history["val_loss"][-1] if history["val_loss"] else 0.0

                training_tasks[task_id]["status"] = "success"
                training_tasks[task_id]["message"] = "Training completed"
                training_tasks[task_id]["metrics"] = {
                    "loss": round(final_val_loss, 4),
                    "training_time": round(elapsed, 2),
                    "epochs_completed": len(history["train_loss"]),
                }
                await progress_cb.send_complete("completed", final_val_loss, elapsed)
            except asyncio.CancelledError:
                training_tasks[task_id]["status"] = "cancelled"
                training_tasks[task_id]["message"] = "Training cancelled"
            except Exception as e:
                training_tasks[task_id]["status"] = "failed"
                training_tasks[task_id]["message"] = f"Training failed: {e!s}"

        finally:
            _active_training.discard(task_id)


@router.post("/train")
async def agent_train(request: AgentTrainRequest):
    """启动训练（B类，异步，返回job_id）"""
    try:
        task_id = str(uuid.uuid4())
        training_tasks[task_id] = {
            "status": "queued",
            "message": "Training task queued",
            "metrics": None,
        }

        hyperparams = {
            "learning_rate": request.hyperparameters.learning_rate,
            "epochs": request.hyperparameters.epochs,
            "batch_size": request.hyperparameters.batch_size,
            "optimizer": request.hyperparameters.optimizer,
        }

        asyncio.create_task(
            _run_agent_training(
                task_id,
                request.model_name,
                request.data_path,
                hyperparams,
                request.device,
            )
        )

        return success(
            data={
                "job_id": task_id,
                "status": "queued",
                "message": "Training task queued",
            },
            message="Training task started",
        )

    except Exception as e:
        return error(
            code=ErrorCode.INTERNAL_ERROR, message=f"Training initiation failed: {e!s}"
        )


@router.get("/train/{job_id}")
async def get_train_status(job_id: str):
    """训练状态（R类）"""
    if job_id not in training_tasks:
        return error(
            code=ErrorCode.NOT_FOUND, message=f"Training task '{job_id}' not found"
        )

    result = training_tasks[job_id]
    return success(
        data={
            "job_id": job_id,
            "status": result["status"],
            "message": result["message"],
            "metrics": result.get("metrics"),
            "is_active": job_id in _active_training,
        }
    )


async def _sse_stream(task_id: str, client_id: str):
    client = await sse_manager.subscribe(task_id, client_id)
    try:
        while True:
            try:
                event = await asyncio.wait_for(client.queue.get(), timeout=30.0)
                yield event
            except asyncio.TimeoutError:
                yield ": heartbeat\n\n"
    except asyncio.CancelledError:
        pass
    finally:
        await sse_manager.unsubscribe(task_id, client_id)


@router.get("/train/{job_id}/stream")
async def stream_training(job_id: str):
    """训练进度SSE流（R类）"""
    if job_id not in training_tasks:
        return error(
            code=ErrorCode.NOT_FOUND, message=f"Training task '{job_id}' not found"
        )

    client_id = f"agent_{uuid.uuid4().hex[:8]}"
    return StreamingResponse(
        _sse_stream(job_id, client_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/execute")
async def agent_execute(request: AgentExecuteRequest):
    """工艺参数下发（T类，paper_only默认）"""
    try:
        # Paper-Only 安全检查
        is_live = paper_only_guard.is_live_execution_allowed()
        if request.simulate or not is_live:
            result = paper_only_guard.simulate_t_operation(
                {
                    "machine_id": request.machine_id,
                    "parameters": request.parameters,
                }
            )
            return success(data=result, message="Operation simulated (Paper-Only mode)")

        # Actual execution (requires LNN_LIVE_EXECUTION_ENABLED=true + token paper_only=false)
        # Placeholder for actual machine dispatch
        return success(
            data={
                "status": "executed",
                "message": f"Parameters dispatched to machine {request.machine_id}",
                "machine_id": request.machine_id,
                "parameters": request.parameters,
            },
            message="Operation executed successfully",
        )

    except Exception as e:
        return error(code=ErrorCode.INTERNAL_ERROR, message=f"Execution failed: {e!s}")


@router.get("/audit-log")
async def get_audit_log(
    agent_id: str | None = None,
    permission_class: str | None = None,
    limit: int = 100,
    offset: int = 0,
):
    """审计日志查询（C类，仅管理员）"""
    entries = agent_audit_log.get_entries(
        agent_id=agent_id,
        permission_class=permission_class,
        limit=limit,
        offset=offset,
    )
    return success(
        data={
            "entries": entries,
            "total": len(entries),
            "limit": limit,
            "offset": offset,
        },
        message="Audit log retrieved",
    )


# Token management endpoints (for internal use / settings page)
@router.post("/tokens")
async def create_agent_token(req: AgentTokenCreateRequest):
    """创建 Agent Token"""
    try:
        for scope in req.scopes:
            if scope not in ("R", "W", "B", "N", "C", "T"):
                return error(
                    code=ErrorCode.INVALID_REQUEST, message=f"Invalid scope: {scope}"
                )

        raw_token, token = agent_token_store.create_token(
            scopes=req.scopes,
            expires_in=req.expires_in,
            paper_only=req.paper_only,
        )

        return success(
            data=AgentTokenResponse(
                agent_id=token.agent_id,
                token=raw_token,
                scopes=token.scopes,
                created_at=token.created_at,
                expires_at=token.expires_at,
                paper_only=token.paper_only,
            ).model_dump(),
            message="Agent token created successfully. Save the token now, it will not be shown again.",
        )

    except Exception as e:
        return error(
            code=ErrorCode.INTERNAL_ERROR, message=f"Token creation failed: {e!s}"
        )


@router.get("/tokens")
async def list_agent_tokens():
    """列出所有 Agent Token"""
    tokens = agent_token_store.list_tokens()
    return success(data={"tokens": tokens, "total": len(tokens)})


@router.delete("/tokens/{agent_id}")
async def revoke_agent_token(agent_id: str):
    """撤销 Agent Token"""
    if agent_token_store.revoke_token(agent_id):
        return success(data={"agent_id": agent_id}, message="Token revoked")
    return error(code=ErrorCode.NOT_FOUND, message=f"Token '{agent_id}' not found")


@router.post("/tokens/revoke-t-all")
async def revoke_all_t_tokens():
    """一键撤销所有 T 类 Token（紧急停止）"""
    count = agent_token_store.revoke_t_tokens()
    return success(
        data={"revoked_count": count}, message=f"Revoked {count} T-class tokens"
    )
