"""lingjing-mcp: 灵境制造 Agent Gateway MCP工具集。

通过Agent Gateway API与后端通信，提供LNN模型管理、预测和训练能力。
所有工具均通过HTTP调用FastAPI后端，使用Bearer Token认证。

统一错误处理策略：
- 所有工具返回标准化的文本响应（JSON格式）
- 网络异常和API错误均被捕获并返回结构化错误信息
- 输入参数经过严格的物理边界校验
"""

from __future__ import annotations

import asyncio
import hmac
import json
import logging
import os
import re as _re
import secrets
from typing import Any

import httpx

logger = logging.getLogger("lingjing-mcp")

AGENT_TOKEN: str = os.environ.get("LINGJING_AGENT_TOKEN", "")
BASE_URL: str = os.environ.get("LINGJING_API_URL", "http://localhost:8765")

_DEFAULT_TIMEOUT = 30.0
_USER_AGENT = "lingjing-mcp/1.0"

_ALLOWED_MODEL_NAME_PATTERN = _re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_.-]{0,127}$")

# 输入长度限制，防止 DoS
_MAX_INPUT_SIZE = 100_000  # predict() 输入的浮点数列表最大长度
_MAX_DATA_PATH_LEN = 1024  # train() 的 data_path 最大字符数
_MAX_MODEL_NAME_LEN = 128  # 模型名称最大字符数
_MAX_JOB_ID_LEN = 256  # job_id 最大字符数


def _sanitize_model_name(name: str) -> str:
    """校验并清理模型名称，防止路径遍历和注入。"""
    if not name or len(name) > _MAX_MODEL_NAME_LEN:
        raise ValueError(f"模型名称不能为空且最长 {_MAX_MODEL_NAME_LEN} 字符")
    if ".." in name or "/" in name or "\\" in name:
        raise ValueError(f"模型名称包含非法字符: {name!r}")
    if not _ALLOWED_MODEL_NAME_PATTERN.match(name):
        raise ValueError(f"模型名称格式无效: {name!r}")
    return name


def _sanitize_job_id(job_id: str) -> str:
    """校验 job_id 格式。"""
    if not job_id or len(job_id) > _MAX_JOB_ID_LEN:
        raise ValueError(f"job_id 不能为空且最长 {_MAX_JOB_ID_LEN} 字符")
    if not _ALLOWED_MODEL_NAME_PATTERN.match(job_id):
        raise ValueError(f"job_id 格式无效: {job_id!r}")
    return job_id


def _sanitize_data_path(path: str) -> str:
    """校验 data_path，防止路径遍历。"""
    if not path or len(path) > _MAX_DATA_PATH_LEN:
        raise ValueError(f"data_path 不能为空且最长 {_MAX_DATA_PATH_LEN} 字符")
    if ".." in path:
        raise ValueError(f"data_path 包含非法路径遍历字符: {path!r}")
    return path


def _validate_predict_input(input_data: list[float]) -> list[float]:
    """校验 predict() 输入数据的尺寸和值域。"""
    if not input_data:
        raise ValueError("input_data 不能为空")
    if len(input_data) > _MAX_INPUT_SIZE:
        raise ValueError(
            f"input_data 长度 {len(input_data)} 超过最大限制 {_MAX_INPUT_SIZE}"
        )
    # 检查 NaN/Inf
    import math

    for i, v in enumerate(input_data):
        if math.isnan(v):
            raise ValueError(f"input_data[{i}] = NaN")
        if math.isinf(v):
            raise ValueError(f"input_data[{i}] = Inf")
    return input_data
_USER_AGENT = "lingjing-mcp/1.0"

# 安全修复：启动时校验 AGENT_TOKEN 强度，避免空 token 导致认证失效。
# 开发环境（LINGJING_MCP_DEV=1）可跳过校验，但会打印警告。
_DEV_MODE = os.environ.get("LINGJING_MCP_DEV", "").lower() in ("1", "true", "yes")
if not AGENT_TOKEN:
    if _DEV_MODE:
        logger.warning(
            "LINGJING_AGENT_TOKEN is empty. Running in dev mode with a random "
            "ephemeral token. This MUST NOT be used in production."
        )
        AGENT_TOKEN = secrets.token_urlsafe(32)
    else:
        raise RuntimeError(
            "LINGJING_AGENT_TOKEN environment variable is required "
            "(must be >= 32 chars). Set LINGJING_MCP_DEV=1 only for local development."
        )
elif len(AGENT_TOKEN) < 32 and not _DEV_MODE:
    raise RuntimeError(
        f"LINGJING_AGENT_TOKEN too short ({len(AGENT_TOKEN)} chars, need >= 32). "
        "Set LINGJING_MCP_DEV=1 only for local development."
    )

# 强制 BASE_URL 使用 HTTPS，除非是 localhost 开发环境
if not BASE_URL.startswith("https://"):
    if "localhost" not in BASE_URL and "127.0.0.1" not in BASE_URL:
        if not _DEV_MODE:
            raise RuntimeError(
                f"LINGJING_API_URL must use HTTPS in production: {BASE_URL}"
            )
    else:
        logger.debug("Using non-HTTPS BASE_URL for localhost development: %s", BASE_URL)


_PARAM_CONSTRAINTS = {
    "learning_rate": (1e-6, 0.1),
    "epochs": (1, 10000),
    "batch_size": (1, 1024),
    "poll_interval": (0.5, 60.0),
}


def _headers() -> dict[str, str]:
    h = {
        "Content-Type": "application/json",
        "User-Agent": _USER_AGENT,
    }
    if AGENT_TOKEN:
        # 使用 hmac.compare_digest 进行 token 比较时序攻击防护
        # （此处仅设置头，实际比较在后端）
        h["Authorization"] = f"Bearer {AGENT_TOKEN}"
    return h


def _generate_idempotency_key() -> str:
    import uuid

    return str(uuid.uuid4())


def _format_error(message: str, detail: Any = None) -> str:
    error_response = {"error": True, "message": message}
    if detail is not None:
        error_response["detail"] = detail
    return json.dumps(error_response, indent=2, ensure_ascii=False)


def _format_success(data: Any) -> str:
    return json.dumps(data, indent=2, ensure_ascii=False)


def _validate_range(
    name: str, value: float, constraints: tuple[float, float]
) -> str | None:
    lo, hi = constraints
    if value < lo or value > hi:
        return f"{name}={value}超出有效范围[{lo}, {hi}]"
    return None


async def list_models() -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=_DEFAULT_TIMEOUT) as client:
        resp = await client.get(
            f"{BASE_URL}/api/agent/v1/models", headers=_headers()
        )
        resp.raise_for_status()
        return resp.json()


async def get_model_info(name: str) -> dict[str, Any]:
    name = _sanitize_model_name(name)
    async with httpx.AsyncClient(timeout=_DEFAULT_TIMEOUT) as client:
        resp = await client.get(
            f"{BASE_URL}/api/agent/v1/models/{name}/info", headers=_headers()
        )
        resp.raise_for_status()
        return resp.json()


async def predict(
    model_name: str, input_data: list[float], return_confidence: bool = False
) -> dict[str, Any]:
    model_name = _sanitize_model_name(model_name)
    input_data = _validate_predict_input(input_data)
    payload = {
        "model_name": model_name,
        "input_data": input_data,
        "return_confidence": return_confidence,
    }
    async with httpx.AsyncClient(timeout=_DEFAULT_TIMEOUT) as client:
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
    model_name = _sanitize_model_name(model_name)
    data_path = _sanitize_data_path(data_path)
    for param_name, value in [
        ("learning_rate", learning_rate),
        ("epochs", float(epochs)),
        ("batch_size", float(batch_size)),
    ]:
        if param_name in _PARAM_CONSTRAINTS:
            err = _validate_range(param_name, value, _PARAM_CONSTRAINTS[param_name])
            if err:
                raise ValueError(err)

    valid_optimizers = frozenset({"adam", "sgd", "adamw", "rmsprop"})
    if optimizer.lower() not in valid_optimizers:
        raise ValueError(
            f"optimizer='{optimizer}'无效，可选: {sorted(valid_optimizers)}"
        )

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
    async with httpx.AsyncClient(timeout=_DEFAULT_TIMEOUT) as client:
        resp = await client.post(
            f"{BASE_URL}/api/agent/v1/train",
            headers={**_headers(), "Idempotency-Key": _generate_idempotency_key()},
            json=payload,
        )
        resp.raise_for_status()
        return resp.json()


async def get_train_status(job_id: str) -> dict[str, Any]:
    job_id = _sanitize_job_id(job_id)
    async with httpx.AsyncClient(timeout=_DEFAULT_TIMEOUT) as client:
        resp = await client.get(
            f"{BASE_URL}/api/agent/v1/train/{job_id}", headers=_headers()
        )
        resp.raise_for_status()
        return resp.json()


async def wait_for_training(
    job_id: str,
    poll_interval: float = 2.0,
    timeout: float = 3600.0,
) -> dict[str, Any]:
    job_id = _sanitize_job_id(job_id)
    # 限制最大超时时间为 24 小时，防止无限制轮询
    timeout = min(timeout, 86400.0)
    err = _validate_range("poll_interval", poll_interval, (0.5, 60.0))
    if err:
        raise ValueError(err)

    start = asyncio.get_event_loop().time()
    while True:
        result = await get_train_status(job_id)
        status = result.get("data", {}).get("status", "")
        if status in ("success", "failed", "cancelled"):
            return result
        if asyncio.get_event_loop().time() - start > timeout:
            return {"error": "timeout", "job_id": job_id, "message": "训练超时"}
        await asyncio.sleep(poll_interval)


def register_tools(server) -> None:
    """在MCP Server实例上注册所有工具。

    注册6个标准化工具：
    - lnn_list_models: 列出所有模型 (R)
    - lnn_get_model_info: 获取模型详情 (R)
    - lnn_predict: 预测推理 (R)
    - lnn_train: 启动训练 (B)
    - lnn_get_train_status: 查询训练状态 (R)
    - lnn_wait_for_training: 等待训练完成 (R)

    权限类: R = Read, B = Budgeted Write
    """

    @server.tool(
        name="lnn_list_models",
        description="列出所有已注册的LNN模型及其基本元数据"
    )
    async def lnn_list_models() -> list[dict]:
        try:
            result = await list_models()
            return [{"type": "text", "text": _format_success(result)}]
        except Exception as exc:
            logger.exception("lnn_list_models failed")
            return [{"type": "text", "text": _format_error(str(exc))}]

    @server.tool(
        name="lnn_get_model_info",
        description="获取指定LNN模型的详细信息，包括架构、参数量和性能指标",
    )
    async def lnn_get_model_info(name: str) -> list[dict]:
        try:
            result = await get_model_info(name)
            return [{"type": "text", "text": _format_success(result)}]
        except Exception as exc:
            logger.exception("lnn_get_model_info failed for %s", name)
            return [{"type": "text", "text": _format_error(str(exc))}]

    @server.tool(
        name="lnn_predict",
        description=(
            "使用指定LNN模型对输入数据进行预测推理。"
            "input_data为浮点数列表，长度需与模型输入维度匹配"
        ),
    )
    async def lnn_predict(
        model_name: str,
        input_data: list[float],
        return_confidence: bool = False,
    ) -> list[dict]:
        try:
            if not input_data:
                return [{"type": "text", "text": _format_error("input_data不能为空")}]
            result = await predict(model_name, input_data, return_confidence)
            return [{"type": "text", "text": _format_success(result)}]
        except Exception as exc:
            logger.exception(
                "lnn_predict failed for %s with %d inputs",
                model_name,
                len(input_data),
            )
            return [{"type": "text", "text": _format_error(str(exc))}]

    @server.tool(
        name="lnn_train",
        description=(
            "启动LNN模型异步训练任务，返回job_id用于追踪进度。"
            "支持配置学习率、epoch数、batch_size、优化器和计算设备"
        ),
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
        try:
            result = await train(
                model_name, data_path, learning_rate, epochs, batch_size, optimizer, device
            )
            return [{"type": "text", "text": _format_success(result)}]
        except ValueError as exc:
            logger.warning("lnn_train validation error: %s", exc)
            return [{"type": "text", "text": _format_error(str(exc))}]
        except Exception as exc:
            logger.exception("lnn_train failed for %s", model_name)
            return [{"type": "text", "text": _format_error(str(exc))}]

    @server.tool(
        name="lnn_get_train_status",
        description="查询指定训练任务的当前状态（pending/running/success/failed/cancelled）",
    )
    async def lnn_get_train_status(job_id: str) -> list[dict]:
        try:
            result = await get_train_status(job_id)
            return [{"type": "text", "text": _format_success(result)}]
        except Exception as exc:
            logger.exception("lnn_get_train_status failed for %s", job_id)
            return [{"type": "text", "text": _format_error(str(exc))}]

    @server.tool(
        name="lnn_wait_for_training",
        description="等待训练任务完成，以poll_interval秒间隔轮询直至状态为终态",
    )
    async def lnn_wait_for_training(
        job_id: str, poll_interval: float = 2.0
    ) -> list[dict]:
        try:
            result = await wait_for_training(job_id, poll_interval)
            return [{"type": "text", "text": _format_success(result)}]
        except Exception as exc:
            logger.exception("lnn_wait_for_training failed for %s", job_id)
            return [{"type": "text", "text": _format_error(str(exc))}]
