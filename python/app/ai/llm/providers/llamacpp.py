"""llama.cpp 本地 LLM Provider。

支持探测 llama.cpp server 服务、列出模型、调用对话补全 API。
llama.cpp 默认端口 8080，提供 OpenAI 兼容 API：
- GET  /v1/models
- POST /v1/chat/completions

llama.cpp server 启动命令通常为：./server --host 0.0.0.0 --port 8080。
"""

from __future__ import annotations

import logging
from typing import Any

from app.ai.llm.provider_base import (
    LLMProvider,
    ProviderConfig,
    ProviderError,
    ProviderStatus,
    ProviderType,
)

logger = logging.getLogger(__name__)


class LlamaCppProvider(LLMProvider):
    """llama.cpp 本地 Provider（OpenAI 兼容 API）。"""

    DEFAULT_PORT = 8080
    DEFAULT_BASE_URL = "http://127.0.0.1:8080"

    def __init__(self, config: ProviderConfig) -> None:
        # 如果未指定 base_url，使用默认本地地址
        if not config.base_url:
            config.base_url = self.DEFAULT_BASE_URL
        # 确保类型正确
        config.provider_type = ProviderType.LLAMACPP
        super().__init__(config)

    async def detect(self) -> bool:
        """探测 llama.cpp 服务是否运行。"""
        try:
            response = await self._http_get(
                f"{self.config.base_url}/v1/models",
                headers=self._build_auth_headers(),
            )
            return response.status_code == 200
        except Exception as e:
            logger.debug("LlamaCpp detect failed: %s", e)
            return False

    async def health_check(self) -> ProviderStatus:
        """健康检查：调用 /v1/models 验证服务可用性。"""
        try:
            response = await self._http_get(
                f"{self.config.base_url}/v1/models",
                headers=self._build_auth_headers(),
            )
            if response.status_code == 200:
                self._update_status(ProviderStatus.ONLINE)
            else:
                self._update_status(ProviderStatus.OFFLINE)
        except Exception as e:
            logger.debug("LlamaCpp health check failed: %s", e)
            self._update_status(ProviderStatus.OFFLINE)
        return self._last_status

    async def list_models(self) -> list[str]:
        """列出 llama.cpp 可用的模型。"""
        try:
            response = await self._http_get(
                f"{self.config.base_url}/v1/models",
                headers=self._build_auth_headers(),
            )
            if response.status_code != 200:
                return []
            data = response.json()
            return [
                m.get("id", "")
                for m in data.get("data", [])
                if m.get("id")
            ]
        except Exception as e:
            logger.warning("LlamaCpp list_models failed: %s", e)
            return []

    async def chat_completion(
        self,
        messages: list[dict[str, str]],
        max_tokens: int = 2048,
        temperature: float = 0.7,
        model: str | None = None,
    ) -> dict[str, Any]:
        """调用 llama.cpp /v1/chat/completions 端点（OpenAI 兼容）。"""
        import time

        target_model = self._resolve_model(model)
        payload = {
            "model": target_model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": False,
        }
        start = time.time()
        response = await self._http_post(
            f"{self.config.base_url}/v1/chat/completions",
            payload,
            headers=self._build_auth_headers(),
        )
        self._measure_latency(start)
        if response.status_code != 200:
            raise ProviderError(
                f"LlamaCpp API error: {response.status_code} - {response.text}"
            )
        data = response.json()
        self._update_status(ProviderStatus.ONLINE)
        choices = data.get("choices", [])
        content = ""
        finish_reason = "stop"
        if choices:
            first = choices[0]
            content = first.get("message", {}).get("content", "")
            finish_reason = first.get("finish_reason", "stop")
        return {
            "content": content,
            "model": data.get("model", target_model),
            "finish_reason": finish_reason,
            "usage": data.get("usage", {}),
        }
