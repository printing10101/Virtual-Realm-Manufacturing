"""LM Studio 本地 LLM Provider。

支持探测 LM Studio 服务、列出已加载模型、调用对话补全 API。
LM Studio 默认端口 1234，提供 OpenAI 兼容 API：
- GET  /v1/models
- POST /v1/chat/completions

本地默认 API Key 为 "lm-studio"（LM Studio 占位 key，无需真实鉴权）。
"""

from __future__ import annotations

import logging
import time
from typing import Any

from app.ai.llm.provider_base import (
    LLMProvider,
    ProviderConfig,
    ProviderError,
    ProviderStatus,
    ProviderType,
)

logger = logging.getLogger(__name__)


class LMStudioProvider(LLMProvider):
    """LM Studio 本地 Provider（OpenAI 兼容 API）。"""

    DEFAULT_PORT = 1234
    DEFAULT_BASE_URL = "http://127.0.0.1:1234/v1"
    # LM Studio 本地占位 key（OpenAI 兼容接口需要 Authorization 头）。
    # 这是 LM Studio 官方文档公开的占位字符串，非真实凭证，本地服务不校验此值。
    # nosec B105: 跳过 bandit 硬编码密码字符串检查（此处为公开占位 key，非凭证）
    DEFAULT_API_KEY = "lm-studio"  # nosec B105

    def __init__(self, config: ProviderConfig) -> None:
        # 如果未指定 base_url，使用默认本地地址
        if not config.base_url:
            config.base_url = self.DEFAULT_BASE_URL
        # LM Studio 本地占位 key（OpenAI 兼容接口需要 Authorization 头）
        if not config.api_key:
            config.api_key = self.DEFAULT_API_KEY
        # 确保类型正确
        config.provider_type = ProviderType.LMSTUDIO
        super().__init__(config)

    async def detect(self) -> bool:
        """探测 LM Studio 服务是否运行。"""
        try:
            response = await self._http_get(
                f"{self.config.base_url}/models",
                headers=self._build_auth_headers(),
            )
            return response.status_code == 200
        except Exception as e:
            logger.debug("LMStudio detect failed: %s", e)
            return False

    async def health_check(self) -> ProviderStatus:
        """健康检查：调用 /v1/models 验证服务可用性。"""
        try:
            response = await self._http_get(
                f"{self.config.base_url}/models",
                headers=self._build_auth_headers(),
            )
            if response.status_code == 200:
                self._update_status(ProviderStatus.ONLINE)
            else:
                self._update_status(ProviderStatus.OFFLINE)
        except Exception as e:
            logger.debug("LMStudio health check failed: %s", e)
            self._update_status(ProviderStatus.OFFLINE)
        return self._last_status

    async def list_models(self) -> list[str]:
        """列出 LM Studio 已加载的模型。"""
        try:
            response = await self._http_get(
                f"{self.config.base_url}/models",
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
            logger.warning("LMStudio list_models failed: %s", e)
            return []

    async def chat_completion(
        self,
        messages: list[dict[str, str]],
        max_tokens: int = 2048,
        temperature: float = 0.7,
        model: str | None = None,
    ) -> dict[str, Any]:
        """调用 LM Studio /v1/chat/completions 端点（OpenAI 兼容）。"""
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
            f"{self.config.base_url}/chat/completions",
            payload,
            headers=self._build_auth_headers(),
        )
        self._measure_latency(start)
        if response.status_code != 200:
            raise ProviderError(
                f"LMStudio API error: {response.status_code} - {response.text}"
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
