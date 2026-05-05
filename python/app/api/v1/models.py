from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

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


async def _check_local_model(base_url: str) -> bool:
    try:
        import httpx
        async with httpx.AsyncClient(timeout=5) as client:
            response = await client.get(f"{base_url}/api/version")
            return response.status_code == 200
    except Exception:
        return False
