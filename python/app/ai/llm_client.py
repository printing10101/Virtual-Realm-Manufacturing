"""LLM client implementations for Ollama and cloud providers."""
from __future__ import annotations

import asyncio
import json
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
        return ServiceUnavailableError(f"Service temporarily unavailable: {status_code} - {body}")
    return LLMError(f"API error: {status_code} - {body}")


class OllamaClient:
    """Client for Ollama API."""

    def __init__(
        self,
        base_url: str,
        model: str,
        timeout: int = 60,
        max_retries: int = DEFAULT_MAX_RETRIES,
        retry_delay: float = DEFAULT_RETRY_DELAY,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay

    async def chat_completion(
        self,
        messages: list[dict[str, str]],
        max_tokens: int = 2048,
        temperature: float = 0.7,
        model: str | None = None,
    ) -> dict[str, Any]:
        """Call Ollama chat completion API."""
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

        last_error: Exception | None = None
        for attempt in range(1, self.max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.post(
                        f"{self.base_url}/api/chat",
                        json=payload,
                    )
                if response.status_code != 200:
                    raise _classify_error(response.status_code, response.text)
                data = response.json()
                return {
                    "content": data.get("message", {}).get("content", ""),
                    "model": target_model,
                    "finish_reason": "stop",
                    "usage": data.get("usage", {}),
                }
            except httpx.TimeoutException as e:
                last_error = e
                logger.warning(
                    "Ollama API timeout (attempt %d/%d): %s",
                    attempt, self.max_retries, e,
                )
            except httpx.NetworkError as e:
                last_error = e
                logger.warning(
                    "Ollama API network error (attempt %d/%d): %s",
                    attempt, self.max_retries, e,
                )
            except (ServiceUnavailableError, RateLimitError) as e:
                last_error = e
                logger.warning(
                    "Ollama API %s (attempt %d/%d): %s",
                    type(e).__name__, attempt, self.max_retries, e,
                )
            except LLMError:
                raise

            if attempt < self.max_retries:
                await asyncio.sleep(self.retry_delay * attempt)

        raise ServiceUnavailableError(
            f"Ollama API call failed after {self.max_retries} retries"
        ) from last_error


class CloudLLMClient:
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
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay

    async def chat_completion(
        self,
        messages: list[dict[str, str]],
        max_tokens: int = 2048,
        temperature: float = 0.7,
        model: str | None = None,
    ) -> dict[str, Any]:
        """Call cloud LLM chat completion API."""
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

        last_error: Exception | None = None
        for attempt in range(1, self.max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.post(
                        f"{self.base_url}/chat/completions",
                        headers=headers,
                        json=payload,
                    )
                if response.status_code != 200:
                    raise _classify_error(response.status_code, response.text)
                data = response.json()
                choices = data.get("choices", [])
                if not choices:
                    raise InvalidResponseError("No choices returned from API")
                choice = choices[0]
                message = choice.get("message", {})
                return {
                    "content": message.get("content", ""),
                    "model": target_model,
                    "finish_reason": choice.get("finish_reason", "stop"),
                    "usage": data.get("usage", {}),
                }
            except httpx.TimeoutException as e:
                last_error = e
                logger.warning(
                    "Cloud API timeout (attempt %d/%d): %s",
                    attempt, self.max_retries, e,
                )
            except httpx.NetworkError as e:
                last_error = e
                logger.warning(
                    "Cloud API network error (attempt %d/%d): %s",
                    attempt, self.max_retries, e,
                )
            except (ServiceUnavailableError, RateLimitError) as e:
                last_error = e
                logger.warning(
                    "Cloud API %s (attempt %d/%d): %s",
                    type(e).__name__, attempt, self.max_retries, e,
                )
            except LLMError:
                raise

            if attempt < self.max_retries:
                await asyncio.sleep(self.retry_delay * attempt)

        raise ServiceUnavailableError(
            f"Cloud API call failed after {self.max_retries} retries"
        ) from last_error
