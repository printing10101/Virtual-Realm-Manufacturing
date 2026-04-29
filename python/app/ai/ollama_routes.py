from fastapi import APIRouter
from fastapi.responses import StreamingResponse
import json

from app.ai.ollama_manager import OllamaManager, RECOMMENDED_MODELS
from app.core.response import success, error, ErrorCode

router = APIRouter(prefix="/api/ollama", tags=["Ollama"])

_manager = OllamaManager()


@router.get("/status")
async def get_ollama_status():
    is_available = await _manager.is_available()
    version = await _manager.get_version()
    return success(data={
        "available": is_available,
        "version": version,
        "base_url": _manager.base_url,
    })


@router.get("/models")
async def list_models():
    models = await _manager.list_models()
    return success(data={
        "models": models,
        "total": len(models),
    })


@router.get("/models/recommended")
async def get_recommended_models():
    return success(data={
        "models": RECOMMENDED_MODELS,
        "total": len(RECOMMENDED_MODELS),
    })


@router.post("/models/pull/{model_name}")
async def pull_model(model_name: str):
    async def event_generator():
        async for progress in _manager.pull_model(model_name):
            yield f"data: {json.dumps(progress)}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.delete("/models/{model_name}")
async def delete_model(model_name: str):
    result = await _manager.delete_model(model_name)
    if result:
        return success(data={"message": f"模型 {model_name} 已删除"})
    return error(code=ErrorCode.INVALID_REQUEST, message=f"删除模型 {model_name} 失败")


@router.get("/models/{model_name}/info")
async def get_model_info(model_name: str):
    info = await _manager.show_model_info(model_name)
    if info:
        return success(data=info)
    return error(code=ErrorCode.FILE_NOT_FOUND, message=f"模型 {model_name} 不存在")


@router.get("/gpu-info")
async def get_gpu_info():
    gpu_info = await _manager.get_gpu_info()
    return success(data=gpu_info)
