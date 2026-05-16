"""Ollama status and model management routes."""

from __future__ import annotations

import logging
from typing import Any

import httpx
from fastapi import APIRouter

from app.config import config
from app.core.response import success, error, ErrorCode

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/ollama", tags=["Ollama"])


@router.get("/status")
async def get_ollama_status() -> dict[str, Any]:
    """获取 Ollama 服务状态"""
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            response = await client.get(f"{config.ai.ollama_base_url}/api/tags")
            if response.status_code == 200:
                data = response.json()
                models = data.get("models", [])
                return success(
                    data={
                        "status": "running",
                        "base_url": config.ai.ollama_base_url,
                        "model_count": len(models),
                        "models": [m.get("name", "unknown") for m in models],
                    }
                )
            else:
                logger.warning("Ollama returned status %d", response.status_code)
                return error(
                    code=ErrorCode.SERVICE_UNAVAILABLE,
                    message=f"Ollama returned status {response.status_code}",
                )
    except Exception as e:
        logger.error("Ollama status check failed: %s", e)
        return error(
            code=ErrorCode.SERVICE_UNAVAILABLE,
            message=f"Ollama service unavailable: {e!s}",
        )


@router.get("/models")
async def list_ollama_models() -> dict[str, Any]:
    """获取 Ollama 已安装模型列表"""
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            response = await client.get(f"{config.ai.ollama_base_url}/api/tags")
            if response.status_code == 200:
                data = response.json()
                models = data.get("models", [])
                return success(
                    data={
                        "models": [
                            {
                                "name": m.get("name", "unknown"),
                                "size": m.get("size", 0),
                                "digest": m.get("digest", ""),
                            }
                            for m in models
                        ]
                    }
                )
            else:
                logger.warning(
                    "Ollama returned status %d for model listing", response.status_code
                )
                return error(
                    code=ErrorCode.SERVICE_UNAVAILABLE,
                    message=f"Ollama returned status {response.status_code}",
                )
    except Exception as e:
        logger.error("Failed to list Ollama models: %s", e)
        return error(
            code=ErrorCode.SERVICE_UNAVAILABLE,
            message=f"Failed to list Ollama models: {e!s}",
        )
