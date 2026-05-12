"""lingjing-mcp: MCP server for 灵境制造 Agent Gateway."""
from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
from typing import Any

import httpx

logger = logging.getLogger("lingjing-mcp")

AGENT_TOKEN = os.environ.get("LINGJING_AGENT_TOKEN", "")
BASE_URL = os.environ.get("LINGJING_API_URL", "http://localhost:8000")


def _headers() -> dict[str, str]:
    h = {"Content-Type": "application/json"}
    if AGENT_TOKEN:
        h["Authorization"] = f"Bearer {AGENT_TOKEN}"
    return h


def _generate_idempotency_key() -> str:
    import uuid
    return str(uuid.uuid4())


async def list_models() -> dict[str, Any]:
    """列出所有已注册的 LNN 模型"""
    async with httpx.AsyncClient() as client:
        resp = await client.get(f"{BASE_URL}/api/agent/v1/models", headers=_headers())
        resp.raise_for_status()
        return resp.json()


async def get_model_info(name: str) -> dict[str, Any]:
    """获取指定模型的详细信息"""
    async with httpx.AsyncClient() as client:
        resp = await client.get(f"{BASE_URL}/api/agent/v1/models/{name}/info", headers=_headers())
        resp.raise_for_status()
        return resp.json()


async def predict(model_name: str, input_data: list[float], return_confidence: bool = False) -> dict[str, Any]:
    """调用 LNN 模型进行预测"""
    payload = {
        "model_name": model_name,
        "input_data": input_data,
        "return_confidence": return_confidence,
    }
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{BASE_URL}/api/agent/v1/predict",
            headers={**_headers(), "Idempotency-Key": _generate_idempotency_key()},
            json=payload,
        )
        resp.raise_for_status()
        return resp.json()


async def train(
    model_name: str,
    data_path: str,
    learning_rate: float = 0.001,
    epochs: int = 100,
    batch_size: int = 32,
    optimizer: str = "adam",
    device: str = "auto",
) -> dict[str, Any]:
    """启动 LNN 模型训练任务（异步，返回 job_id）"""
    payload = {
        "model_name": model_name,
        "data_path": data_path,
        "hyperparameters": {
            "learning_rate": learning_rate,
            "epochs": epochs,
            "batch_size": batch_size,
            "optimizer": optimizer,
        },
        "device": device,
    }
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{BASE_URL}/api/agent/v1/train",
            headers={**_headers(), "Idempotency-Key": _generate_idempotency_key()},
            json=payload,
        )
        resp.raise_for_status()
        return resp.json()


async def get_train_status(job_id: str) -> dict[str, Any]:
    """查询训练任务状态"""
    async with httpx.AsyncClient() as client:
        resp = await client.get(f"{BASE_URL}/api/agent/v1/train/{job_id}", headers=_headers())
        resp.raise_for_status()
        return resp.json()


async def wait_for_training(job_id: str, poll_interval: float = 2.0, timeout: float = 3600.0) -> dict[str, Any]:
    """等待训练任务完成，轮询状态"""
    start = asyncio.get_event_loop().time()
    while True:
        result = await get_train_status(job_id)
        status = result.get("data", {}).get("status", "")
        if status in ("success", "failed", "cancelled"):
            return result
        if asyncio.get_event_loop().time() - start > timeout:
            return {"error": "timeout", "job_id": job_id}
        await asyncio.sleep(poll_interval)


def register_tools(server) -> None:
    """Register all MCP tools on the given MCP server."""

    @server.tool(
        name="lnn_list_models",
        description="列出所有已注册的 LNN 模型（权限类: R）",
    )
    async def lnn_list_models() -> list[dict]:
        result = await list_models()
        return [{"type": "text", "text": json.dumps(result, indent=2, ensure_ascii=False)}]

    @server.tool(
        name="lnn_get_model_info",
        description="获取指定模型的详细信息（权限类: R）",
    )
    async def lnn_get_model_info(name: str) -> list[dict]:
        result = await get_model_info(name)
        return [{"type": "text", "text": json.dumps(result, indent=2, ensure_ascii=False)}]

    @server.tool(
        name="lnn_predict",
        description="调用 LNN 模型进行预测（权限类: R）",
    )
    async def lnn_predict(model_name: str, input_data: list[float], return_confidence: bool = False) -> list[dict]:
        result = await predict(model_name, input_data, return_confidence)
        return [{"type": "text", "text": json.dumps(result, indent=2, ensure_ascii=False)}]

    @server.tool(
        name="lnn_train",
        description="启动 LNN 模型训练任务，异步返回 job_id（权限类: B）",
    )
    async def lnn_train(
        model_name: str,
        data_path: str,
        learning_rate: float = 0.001,
        epochs: int = 100,
        batch_size: int = 32,
        optimizer: str = "adam",
        device: str = "auto",
    ) -> list[dict]:
        result = await train(model_name, data_path, learning_rate, epochs, batch_size, optimizer, device)
        return [{"type": "text", "text": json.dumps(result, indent=2, ensure_ascii=False)}]

    @server.tool(
        name="lnn_get_train_status",
        description="查询训练任务状态（权限类: R）",
    )
    async def lnn_get_train_status(job_id: str) -> list[dict]:
        result = await get_train_status(job_id)
        return [{"type": "text", "text": json.dumps(result, indent=2, ensure_ascii=False)}]

    @server.tool(
        name="lnn_wait_for_training",
        description="等待训练任务完成，轮询直至结束（权限类: R）",
    )
    async def lnn_wait_for_training(job_id: str, poll_interval: float = 2.0) -> list[dict]:
        result = await wait_for_training(job_id, poll_interval)
        return [{"type": "text", "text": json.dumps(result, indent=2, ensure_ascii=False)}]
