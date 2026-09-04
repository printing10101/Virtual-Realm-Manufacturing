"""本地 OpenAI 兼容 Provider（preset 基类）测试。

五个本地推理服务（lmstudio/llamacpp/vllm/tgi/koboldcpp）共享
``openai_compat_base.OpenAICompatLocalProvider`` 实现。
本测试锁定：URL 拼接（含 llama.cpp 前缀规范化）、类型注入、占位 Key、
类属性接口（DEFAULT_PORT/DEFAULT_BASE_URL）与工厂注册链路。
"""

import pytest

from app.ai.llm.provider_base import ProviderConfig, ProviderType
from app.ai.llm.providers import (
    KoboldCppProvider,
    LlamaCppProvider,
    LMStudioProvider,
    TGIProvider,
    VllmProvider,
)
from app.ai.llm.providers.openai_compat_base import OpenAICompatLocalProvider

ALL_LOCAL = [LMStudioProvider, LlamaCppProvider, VllmProvider, TGIProvider, KoboldCppProvider]


def _cfg(base_url: str = "") -> ProviderConfig:
    return ProviderConfig(provider_id="t", name="t", provider_type=ProviderType.VLLM, base_url=base_url)


@pytest.mark.parametrize("cls", ALL_LOCAL)
def test_default_base_url_injected(cls):
    provider = cls(_cfg())
    assert provider.config.base_url == cls.preset.default_base_url


def test_llamacpp_path_prefix():
    """llama.cpp 默认 base_url 不含 /v1，路径需自带 /v1 前缀。"""
    provider = LlamaCppProvider(_cfg())
    assert provider._models_url() == "http://127.0.0.1:8080/v1/models"
    assert provider._chat_url() == "http://127.0.0.1:8080/v1/chat/completions"


def test_llamacpp_prefix_not_duplicated():
    """用户配置带 /v1 的 base_url 时不得产生 /v1/v1 双前缀。"""
    provider = LlamaCppProvider(_cfg(base_url="http://127.0.0.1:9000/v1"))
    assert provider.config.base_url == "http://127.0.0.1:9000"
    assert provider._models_url() == "http://127.0.0.1:9000/v1/models"


def test_custom_base_url_preserved():
    provider = VllmProvider(_cfg(base_url="http://192.168.1.5:8000/v1"))
    assert provider._models_url() == "http://192.168.1.5:8000/v1/models"


def test_provider_type_injected():
    assert LMStudioProvider(_cfg()).config.provider_type == ProviderType.LMSTUDIO
    assert KoboldCppProvider(_cfg()).config.provider_type == ProviderType.KOBOLDCPP
    assert TGIProvider(_cfg()).config.provider_type == ProviderType.TGI


def test_lmstudio_placeholder_key(monkeypatch):
    monkeypatch.delenv("LMSTUDIO_API_KEY", raising=False)
    assert LMStudioProvider(_cfg()).config.api_key == "lm-studio"

    monkeypatch.setenv("LMSTUDIO_API_KEY", "custom-key")
    assert LMStudioProvider(_cfg()).config.api_key == "custom-key"


def test_other_providers_do_not_inject_key():
    for cls in (VllmProvider, LlamaCppProvider, TGIProvider, KoboldCppProvider):
        assert cls(_cfg()).config.api_key == ""


def test_class_attr_interface_preserved():
    """provider_base 声明的 DEFAULT_PORT/DEFAULT_BASE_URL 类属性由 preset 回填。"""
    assert VllmProvider.DEFAULT_PORT == 8000
    assert LlamaCppProvider.DEFAULT_BASE_URL == "http://127.0.0.1:8080"
    assert issubclass(VllmProvider, OpenAICompatLocalProvider)


def test_chat_completion_parses_response():
    import asyncio

    class _Resp:
        status_code = 200

        def json(self):
            return {
                "model": "served-model",
                "choices": [{"message": {"content": "hi"}, "finish_reason": "stop"}],
                "usage": {"total_tokens": 3},
            }

    provider = VllmProvider(_cfg())
    provider._http_post = lambda *a, **kw: _async_return(_Resp())  # type: ignore[method-assign]
    result = asyncio.run(provider.chat_completion([{"role": "user", "content": "hi"}]))

    assert result["content"] == "hi"
    assert result["model"] == "served-model"
    assert result["finish_reason"] == "stop"
    assert result["usage"] == {"total_tokens": 3}


def _async_return(value):

    async def _inner():
        return value

    return _inner()
