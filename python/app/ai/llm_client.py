"""LLM client implementations for Ollama and cloud providers."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class LLMError(Exception):
    """Base exception for LLM client errors."""


class RateLimitError(LLMError):
    """Raised when the API rate limit is exceeded (HTTP 429)."""


class ServiceUnavailableError(LLMError):
    """Raised when the API service is temporarily unavailable (HTTP 5xx)."""


class InvalidResponseError(LLMError):
    """Raised when the API returns an empty or malformed response."""


DEFAULT_MAX_RETRIES = 3
DEFAULT_RETRY_DELAY = 1.0


def _classify_error(status_code: int, body: str) -> LLMError:
    if status_code == 429:
        return RateLimitError(f"Rate limit exceeded: {status_code} - {body}")
    if 500 <= status_code < 600:
        return ServiceUnavailableError(
            f"Service temporarily unavailable: {status_code} - {body}"
        )
    return LLMError(f"API error: {status_code} - {body}")


class BaseLLMClient:
    """Base class for LLM clients with shared retry logic."""

    def __init__(
        self,
        timeout: int = 60,
        max_retries: int = DEFAULT_MAX_RETRIES,
        retry_delay: float = DEFAULT_RETRY_DELAY,
    ) -> None:
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay

    async def _build_payload(
        self,
        messages: list[dict[str, str]],
        max_tokens: int,
        temperature: float,
        model: str | None,
    ) -> tuple[dict[str, Any], dict[str, str] | None, str]:
        raise NotImplementedError("LLM 客户端必须实现 _do_call() 方法来调用模型 API")

    def _parse_response(self, data: dict[str, Any], model: str) -> dict[str, Any]:
        raise NotImplementedError("LLM 客户端必须实现 _parse_response() 方法来解析模型响应")

    def _default_model(self) -> str:
        """Return the default model name for this client."""
        raise NotImplementedError("LLM 客户端必须实现 _default_model() 方法返回默认模型名称")

    @staticmethod
    def _validate_inputs(
        messages: list[dict[str, str]],
        max_tokens: int,
        temperature: float,
    ) -> None:
        if not messages:
            raise ValueError(
                "LLM API 调用失败：'messages' 参数不能为空。LLM API 需要至少一条消息（包含 role 和 content）才能发起请求。请传入格式如 [{'role': 'user', 'content': 'your prompt'}] 的消息列表。"  # noqa: E501
            )
        if max_tokens < 1:
            raise ValueError(f"max_tokens must be >= 1, got {max_tokens}")
        if not (0.0 <= temperature <= 2.0):
            raise ValueError(
                f"LLM API 调用失败：'temperature' 参数值必须在 [0.0, 2.0] 区间内，当前值: {temperature}。temperature 控制生成结果的随机性（0.0=最确定，2.0=最随机）。请调整至合理区间。"  # noqa: E501
            )

    @staticmethod
    def _safe_parse(
        parser, response_data: dict[str, Any], model: str
    ) -> dict[str, Any]:
        try:
            return parser(response_data, model)
        except (LLMError, InvalidResponseError):
            raise
        except (ValueError, KeyError, TypeError, AttributeError) as e:
            logger.error("Failed to parse response from %s: %s", model, e, exc_info=True)
            raise InvalidResponseError(
                f"Failed to parse response from {model}: {e}"
            ) from e

    async def chat_completion(
        self,
        messages: list[dict[str, str]],
        max_tokens: int = 2048,
        temperature: float = 0.7,
        model: str | None = None,
    ) -> dict[str, Any]:
        """Call LLM chat completion API with retry logic."""
        self._validate_inputs(messages, max_tokens, temperature)

        payload, headers, endpoint = self._build_payload(
            messages, max_tokens, temperature, model
        )
        target_model = model or self._default_model()

        last_error: Exception | None = None
        for attempt in range(1, self.max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.post(
                        endpoint,
                        headers=headers,
                        json=payload,
                    )
                if response.status_code != 200:
                    raise _classify_error(response.status_code, response.text)
                return self._safe_parse(
                    self._parse_response, response.json(), target_model
                )
            except httpx.TimeoutException as e:
                last_error = e
                logger.warning(
                    "%s API timeout (attempt %d/%d): %s",
                    type(self).__name__,
                    attempt,
                    self.max_retries,
                    e,
                )
            except httpx.NetworkError as e:
                last_error = e
                logger.warning(
                    "%s API network error (attempt %d/%d): %s",
                    type(self).__name__,
                    attempt,
                    self.max_retries,
                    e,
                )
            except (ServiceUnavailableError, RateLimitError) as e:
                last_error = e
                logger.warning(
                    "%s API %s (attempt %d/%d): %s",
                    type(self).__name__,
                    type(e).__name__,
                    attempt,
                    self.max_retries,
                    e,
                )
            except (LLMError, InvalidResponseError):
                raise

            if attempt < self.max_retries:
                await asyncio.sleep(self.retry_delay * attempt)

        raise ServiceUnavailableError(
            f"{type(self).__name__} API call failed after {self.max_retries} retries"
        ) from last_error


class OllamaClient(BaseLLMClient):
    """Client for Ollama API."""

    def __init__(
        self,
        base_url: str,
        model: str,
        timeout: int = 60,
        max_retries: int = DEFAULT_MAX_RETRIES,
        retry_delay: float = DEFAULT_RETRY_DELAY,
    ) -> None:
        super().__init__(
            timeout=timeout, max_retries=max_retries, retry_delay=retry_delay
        )
        self.base_url = base_url.rstrip("/")
        self.model = model

    def _default_model(self) -> str:
        return self.model

    async def _build_payload(
        self,
        messages: list[dict[str, str]],
        max_tokens: int,
        temperature: float,
        model: str | None,
    ) -> tuple[dict[str, Any], dict[str, str] | None, str]:
        target_model = model or self.model
        payload = {
            "model": target_model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }
        endpoint = f"{self.base_url}/api/chat"
        return payload, None, endpoint

    def _parse_response(self, data: dict[str, Any], model: str) -> dict[str, Any]:
        return {
            "content": data.get("message", {}).get("content", ""),
            "model": model,
            "finish_reason": "stop",
            "usage": data.get("usage", {}),
        }


class CloudLLMClient(BaseLLMClient):
    """Client for cloud LLM providers (OpenAI-compatible API)."""

    def __init__(
        self,
        api_key: str,
        base_url: str,
        model: str,
        timeout: int = 60,
        max_retries: int = DEFAULT_MAX_RETRIES,
        retry_delay: float = DEFAULT_RETRY_DELAY,
    ) -> None:
        super().__init__(
            timeout=timeout, max_retries=max_retries, retry_delay=retry_delay
        )
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model

    def _default_model(self) -> str:
        return self.model

    async def _build_payload(
        self,
        messages: list[dict[str, str]],
        max_tokens: int,
        temperature: float,
        model: str | None,
    ) -> tuple[dict[str, Any], dict[str, str] | None, str]:
        target_model = model or self.model
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": target_model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        endpoint = f"{self.base_url}/chat/completions"
        return payload, headers, endpoint

    def _parse_response(self, data: dict[str, Any], model: str) -> dict[str, Any]:
        choices = data.get("choices", [])
        if not choices:
            raise InvalidResponseError(
                "LLM API 响应解析失败：API 返回的响应中未包含任何候选结果（choices 列表为空）。可能原因：1) API 服务异常或返回了空响应；2) 请求参数配置有误。请检查 API 请求参数，或调用 API 健康检查端点确认服务状态。"  # noqa: E501
            )
        choice = choices[0]
        message = choice.get("message", {})
        return {
            "content": message.get("content", ""),
            "model": model,
            "finish_reason": choice.get("finish_reason", "stop"),
            "usage": data.get("usage", {}),
        }
