from abc import ABC, abstractmethod
from typing import Optional

import httpx

from app.models.schemas import LLMRequest, LLMResponse


class BaseLLMClient(ABC):
    @abstractmethod
    async def chat(self, request: LLMRequest) -> LLMResponse:
        pass

    @abstractmethod
    async def is_available(self) -> bool:
        pass

    async def chat_completion(self, messages: list, max_tokens: int = 2048, temperature: float = 0.7, model: str = None) -> dict:
        request = LLMRequest(
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
            model=model
        )
        response = await self.chat(request)
        return {
            'content': response.content,
            'model': response.model,
            'finish_reason': response.finish_reason,
            'usage': response.usage
        }


class OllamaClient(BaseLLMClient):
    def __init__(self, base_url: str = "http://localhost:11434", model: str = "qwen2.5-coder:7b", timeout: int = 60):
        self.base_url = base_url
        self.model = model
        self.timeout = timeout

    async def chat(self, request: LLMRequest) -> LLMResponse:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.base_url}/api/chat",
                json={
                    "model": request.model or self.model,
                    "messages": request.messages,
                    "stream": request.stream,
                    "options": {
                        "temperature": request.temperature,
                        "num_predict": request.max_tokens
                    }
                }
            )
            response.raise_for_status()
            data = response.json()
            return LLMResponse(
                content=data.get("message", {}).get("content", ""),
                model=self.model,
                finish_reason="stop"
            )

    async def is_available(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                response = await client.get(f"{self.base_url}/api/version")
                return response.status_code == 200
        except Exception:
            return False

    async def list_models(self) -> list[str]:
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                response = await client.get(f"{self.base_url}/api/tags")
                response.raise_for_status()
                data = response.json()
                return [m.get("name") for m in data.get("models", [])]
        except Exception:
            return []

    async def get_version(self) -> Optional[str]:
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                response = await client.get(f"{self.base_url}/api/version")
                response.raise_for_status()
                return response.json().get("version")
        except Exception:
            return None


class CloudLLMClient(BaseLLMClient):
    def __init__(self, api_key: str, base_url: str = "https://api.openai.com/v1", model: str = "gpt-3.5-turbo", timeout: int = 60):
        self.api_key = api_key
        self.base_url = base_url
        self.model = model
        self.timeout = timeout

    async def chat(self, request: LLMRequest) -> LLMResponse:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": request.model or self.model,
                    "messages": request.messages,
                    "temperature": request.temperature,
                    "max_tokens": request.max_tokens,
                    "stream": request.stream
                }
            )
            response.raise_for_status()
            data = response.json()
            choice = data.get("choices", [{}])[0]
            return LLMResponse(
                content=choice.get("message", {}).get("content", ""),
                model=self.model,
                finish_reason=choice.get("finish_reason"),
                usage=data.get("usage")
            )

    async def is_available(self) -> bool:
        return bool(self.api_key)


class RuleEngineClient(BaseLLMClient):
    async def chat(self, request: LLMRequest) -> LLMResponse:
        return LLMResponse(
            content="规则引擎模式：此功能需要配置具体的规则逻辑。",
            model="rule_engine",
            finish_reason="stop"
        )

    async def is_available(self) -> bool:
        return True


def get_llm_client(mode: Optional[str] = None) -> BaseLLMClient:
    from app.config import config

    if mode is None:
        mode = config.ai.mode

    if mode == "local":
        return OllamaClient(
            base_url=config.ai.ollama_base_url,
            model=config.ai.ollama_model,
            timeout=config.ai.timeout
        )
    elif mode == "cloud":
        return CloudLLMClient(
            api_key=config.ai.cloud_api_key,
            base_url=config.ai.cloud_base_url,
            model=config.ai.cloud_model,
            timeout=config.ai.timeout
        )
    else:
        return RuleEngineClient()
