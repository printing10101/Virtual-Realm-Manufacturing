"""Ollama 本地 LLM Provider。

支持探测 Ollama 服务、列出已安装模型、调用对话补全 API。
Ollama 默认端口 11434，API 端点 /api/chat 和 /api/tags。
"""

from __future__ import annotations

import logging
import socket
from typing import Any

from app.ai.llm.provider_base import (
    LLMProvider,
    ProviderConfig,
    ProviderError,
    ProviderStatus,
    ProviderType,
)

logger = logging.getLogger(__name__)


class OllamaProvider(LLMProvider):
    """Ollama 本地 Provider。"""

    DEFAULT_PORT = 11434
    DEFAULT_BASE_URL = "http://127.0.0.1:11434"

    def __init__(self, config: ProviderConfig) -> None:
        # 如果未指定 base_url，使用默认本地地址
        if not config.base_url:
            config.base_url = self.DEFAULT_BASE_URL
        # 确保类型正确
        config.provider_type = ProviderType.OLLAMA
        super().__init__(config)

    async def detect(self) -> bool:
        """探测 Ollama 服务是否运行。"""
        try:
            response = await self._http_get(f"{self.config.base_url}/api/tags")
            return response.status_code == 200
        except Exception as e:
            logger.debug("Ollama detect failed: %s", e)
            return False

    async def health_check(self) -> ProviderStatus:
        """健康检查：调用 /api/tags 验证服务可用性。"""
        try:
            response = await self._http_get(f"{self.config.base_url}/api/tags")
            if response.status_code == 200:
                self._update_status(ProviderStatus.ONLINE)
            else:
                self._update_status(ProviderStatus.OFFLINE)
        except Exception as e:
            logger.debug("Ollama health check failed: %s", e)
            self._update_status(ProviderStatus.OFFLINE)
        return self._last_status

    async def list_models(self) -> list[str]:
        """列出 Ollama 已安装的模型。"""
        try:
            response = await self._http_get(f"{self.config.base_url}/api/tags")
            if response.status_code != 200:
                return []
            data = response.json()
            return [m.get("name", "") for m in data.get("models", []) if m.get("name")]
        except Exception as e:
            logger.warning("Ollama list_models failed: %s", e)
            return []

    async def chat_completion(
        self,
        messages: list[dict[str, str]],
        max_tokens: int = 2048,
        temperature: float = 0.7,
        model: str | None = None,
    ) -> dict[str, Any]:
        """调用 Ollama /api/chat 端点。"""
        import time

        target_model = self._resolve_model(model)
        payload = {
            "model": target_model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }
        start = time.time()
        response = await self._http_post(
            f"{self.config.base_url}/api/chat", payload
        )
        self._measure_latency(start)
        if response.status_code != 200:
            raise ProviderError(
                f"Ollama API error: {response.status_code} - {response.text}"
            )
        data = response.json()
        self._update_status(ProviderStatus.ONLINE)
        return {
            "content": data.get("message", {}).get("content", ""),
            "model": target_model,
            "finish_reason": "stop",
            "usage": data.get("usage", {}),
        }

