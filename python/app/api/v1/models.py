from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.core.container import container
from app.core.response import ErrorCode, error, success

router = APIRouter(prefix="/api/v1/models", tags=["Model Management"])


class RouteTestRequest(BaseModel):
    material: str = ""
    tool: str = ""
    constraints: list = []
    geometry: dict[str, Any] = {}
    history: list = []


class FineTuneTriggerRequest(BaseModel):
    force: bool = False


class ModelConfigRequest(BaseModel):
    local_model: str | None = None
    cloud_provider: str | None = None
    cloud_model: str | None = None
    fallback_threshold: int | None = None
    local_timeout: int | None = None


class BoschFinetunePrepareRequest(BaseModel):
    data_dir: str = "python/app/data/datasets/bosch_cnc"
    categories: list[str] | None = None


class BoschFinetuneStartRequest(BaseModel):
    base_model: str = Field(
        default="qwen2.5:7b",
        description="基础模型名称",
        min_length=1,
        max_length=64,
    )
    categories: list[str] | None = None
    epochs: int = Field(
        default=3,
        ge=1,
        le=50,
        description="训练轮次（1-50）",
    )
    learning_rate: float = Field(
        default=2e-4,
        gt=0,
        lt=1.0,
        description="学习率（0 < lr < 1.0）",
    )
    task_id: str | None = Field(
        default=None,
        max_length=64,
        description="任务ID",
    )


@router.get("/status")
async def get_model_status():
    model_router = container.get_service("model_router")
    finetuner = container.get_service("finetuner")
    cfg = container.get_service("config")

    local_available = await _check_local_model(cfg.ai.ollama_base_url)
    cloud_available = bool(cfg.ai.cloud_api_key)

    router_stats = await model_router.get_stats()
    finetune_status = finetuner.get_finetune_status()

    return success(data={
        "local_model": {
            "name": cfg.model_router.local_model,
            "available": local_available,
            "base_url": cfg.ai.ollama_base_url
        },
        "cloud_model": {
            "provider": cfg.model_router.cloud_provider,
            "name": cfg.model_router.cloud_model,
            "available": cloud_available
        },
        "router_stats": router_stats,
        "finetune_status": finetune_status,
        "config": {
            "fallback_threshold": cfg.model_router.fallback_threshold,
            "local_timeout": cfg.model_router.local_timeout,
            "finetune_auto_trigger": cfg.finetune.finetune_auto_trigger,
            "finetune_min_samples": cfg.finetune.finetune_min_samples,
            "finetune_interval_days": cfg.finetune.finetune_interval_days
        }
    })


@router.post("/route")
async def test_route_decision(request: RouteTestRequest):
    model_router = container.get_service("model_router")

    input_data = {
        "material": request.material,
        "tool": request.tool,
        "constraints": request.constraints,
        "geometry": request.geometry,
        "history": request.history
    }

    route_info = await model_router.route(input_data)

    return success(data={
        "route_decision": route_info["route_decision"],
        "complexity_score": route_info["complexity_score"],
        "reasons": route_info["reasons"],
        "breakdown": route_info["breakdown"]
    })


@router.post("/finetune/trigger")
async def trigger_finetune(request: FineTuneTriggerRequest):
    finetuner = container.get_service("finetuner")
    result = finetuner.trigger_finetune(force=request.force)

    if result["status"] in ("completed", "skipped", "insufficient_data"):
        return success(data=result)
    else:
        return error(code=ErrorCode.INTERNAL_ERROR, message=result.get("error", "FineTune failed"))


@router.get("/finetune/status")
async def get_finetune_status():
    finetuner = container.get_service("finetuner")
    status = finetuner.get_finetune_status()
    return success(data=status)


@router.post("/finetune/rollback")
async def rollback_model():
    finetuner = container.get_service("finetuner")
    result = finetuner.rollback_model()

    if result["status"] == "rollback_completed":
        return success(data=result)
    else:
        return error(code=ErrorCode.INTERNAL_ERROR, message=result.get("message", result.get("error", "Rollback failed")))


@router.get("/stats")
async def get_router_stats():
    model_router = container.get_service("model_router")
    stats = await model_router.get_stats()
    return success(data=stats)


@router.post("/bosch-finetune/prepare")
async def prepare_bosch_finetune(request: BoschFinetunePrepareRequest):
    finetuner = container.get_service("finetuner")
    result = finetuner.prepare_bosch_finetune_data(
        data_dir=request.data_dir,
        categories=request.categories,
    )
    if result["status"] == "success":
        return success(data=result)
    else:
        return error(code=ErrorCode.INTERNAL_ERROR, message=result.get("message", "准备微调数据失败"))


@router.post("/bosch-finetune/start")
async def start_bosch_finetune(request: BoschFinetuneStartRequest):
    import uuid
    finetuner = container.get_service("finetuner")
    task_id = request.task_id or f"bosch_finetune_{uuid.uuid4().hex[:8]}"
    try:
        finetune_task_id = finetuner.start_finetune_with_bosch_data(
            task_id=task_id,
            base_model=request.base_model,
            categories=request.categories,
            epochs=request.epochs,
            learning_rate=request.learning_rate,
        )
        return success(data={"task_id": finetune_task_id, "status": "started"})
    except ValueError as e:
        return error(code=ErrorCode.INTERNAL_ERROR, message=str(e))
    except Exception as e:
        return error(code=ErrorCode.INTERNAL_ERROR, message=f"启动微调失败：{e}")


@router.get("/bosch-finetune/samples")
async def preview_bosch_finetune_samples(category: str | None = None, limit: int = 10):
    from app.services.bosch_finetune_builder import BoschFinetuneBuilder
    from pathlib import Path

    finetune = container.get_service("finetuner")
    output_dir = finetune.output_dir / "bosch_finetune"
    train_path = output_dir / "train.jsonl"

    if not train_path.exists():
        builder = BoschFinetuneBuilder()
        all_samples = []
        if category is None or category == "diagnosis":
            all_samples.extend(builder.generate_diagnosis_samples())
        if category is None or category == "parameter_optimization":
            all_samples.extend(builder.generate_parameter_optimization_samples())
        if category is None or category == "comparison":
            all_samples.extend(builder.generate_comparison_samples())
        if category is None or category == "maintenance":
            all_samples.extend(builder.generate_preventive_maintenance_samples())
    else:
        all_samples = []
        with open(train_path, encoding="utf-8") as f:
            for line in f:
                import json
                sample = json.loads(line.strip())
                if category is None or sample.get("category") == category:
                    all_samples.append(sample)

    return success(data={
        "total": len(all_samples),
        "limit": limit,
        "samples": all_samples[:limit],
    })


@router.get("/bosch-finetune/stats")
async def get_bosch_finetune_stats():
    from pathlib import Path
    import json

    finetune = container.get_service("finetuner")
    output_dir = finetune.output_dir / "bosch_finetune"
    info_path = output_dir / "dataset_info.json"

    if info_path.exists():
        with open(info_path, encoding="utf-8") as f:
            info = json.load(f)
        return success(data=info)
    else:
        return success(data={
            "status": "not_built",
            "message": "微调数据集尚未构建，请先调用 prepare 接口",
        })


async def _check_local_model(base_url: str) -> bool:
    try:
        import httpx
        async with httpx.AsyncClient(timeout=5) as client:
            response = await client.get(f"{base_url}/api/version")
            return response.status_code == 200
    except Exception:
        return False
