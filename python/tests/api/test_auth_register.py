"""Tests for /api/v1/auth/register endpoint.

覆盖范围：
- 邀请码环境变量未配置 / 邀请码错误：HTTP 403
- 用户名冲突：HTTP 409
- 注册成功：HTTP 200，标准化 JSON 响应
- IP 速率限制：60 分钟内第 6 次请求触发 HTTP 429 且响应头包含 Retry-After
"""

from __future__ import annotations

from typing import Any, Generator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v1.auth import (
    router as auth_router,
)
from app.middleware.rate_limiter import limiter as _registration_limiter
from app.models import user as user_module
from app.models.user import UserStore


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def isolated_user_store(tmp_path, monkeypatch) -> Generator[Any, None, None]:
    """为每个测试用例提供独立的 user store。

    实现策略：
    - 直接用 ``monkeypatch.setattr`` 覆盖 ``app.models.user.USER_STORE_FILE``，
      避免 ``importlib.reload`` 触发 torch/扩展模块的重复初始化（与 coverage 工具链
      存在已知冲突，会抛 ``RuntimeError: function '_has_torch_function' already
      has a docstring``）。
    - 同时把 ``get_user_store`` 函数替换为返回新 store 实例的工厂，确保模块级
      单例被重置。
    """
    store_file = tmp_path / "users_test.json"
    monkeypatch.setattr(user_module, "USER_STORE_FILE", str(store_file))
    # 复位模块级单例（_UserStoreHolder 内部维护 _instance）
    monkeypatch.setattr(user_module._holder, "_instance", None)

    def _factory(file_path: str = str(store_file)) -> UserStore:
        return UserStore(file_path=file_path)

    monkeypatch.setattr(user_module, "get_user_store", _factory)
    yield user_module


@pytest.fixture
def client(isolated_user_store) -> Generator[TestClient, None, None]:
    """提供独立的 FastAPI 测试客户端。

    注册 slowapi 的 ``RateLimitExceeded`` 异常处理器，确保 429 响应携带
    ``Retry-After`` 头与统一的中文提示消息。
    """
    from slowapi.errors import RateLimitExceeded

    from app.middleware.rate_limiter import rate_limit_handler

    app = FastAPI()
    app.state.limiter = _registration_limiter
    app.add_exception_handler(RateLimitExceeded, rate_limit_handler)
    app.include_router(auth_router)
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(autouse=True)
def reset_rate_limiter() -> Generator[None, None, None]:
    """每个用例开始前重置模块级速率限制器，避免相互污染。"""
    # 清空 slowapi 全局 limiter 存储（注册端点 3/hour 限流）
    try:
        storage = getattr(_registration_limiter, "_storage", None)
        if storage is not None and hasattr(storage, "reset"):
            storage.reset()
        elif storage is not None and hasattr(storage, "storage"):
            storage.storage.clear()
    except Exception:
        pass
    yield
    try:
        storage = getattr(_registration_limiter, "_storage", None)
        if storage is not None and hasattr(storage, "reset"):
            storage.reset()
        elif storage is not None and hasattr(storage, "storage"):
            storage.storage.clear()
    except Exception:
        pass


# ---------------------------------------------------------------------------
# 注册功能测试
# ---------------------------------------------------------------------------


class TestRegisterEnvCodeMissing:
    """邀请码环境变量未配置时的注册行为。"""

    def test_returns_403_when_env_var_not_set(self, client, monkeypatch):
        """未配置 LNN_REGISTRATION_CODE 时直接拒绝，返回 403。"""
        monkeypatch.delenv("LNN_REGISTRATION_CODE", raising=False)
        response = client.post(
            "/api/v1/auth/register",
            json={"username": "alice", "password": "Passw0rd!", "invite_code": "ANY"},
        )
        assert response.status_code == 403
        body = response.json()
        assert body["code"] == 1003
        assert "注册功能已关闭" in body["message"]

    def test_returns_403_when_env_var_is_empty(self, client, monkeypatch):
        """LNN_REGISTRATION_CODE 设置为空字符串视为已关闭。"""
        monkeypatch.setenv("LNN_REGISTRATION_CODE", "")
        response = client.post(
            "/api/v1/auth/register",
            json={"username": "alice", "password": "Passw0rd!", "invite_code": "ANY"},
        )
        assert response.status_code == 403
        body = response.json()
        assert body["code"] == 1003
        assert "注册功能已关闭" in body["message"]


class TestRegisterInvalidInviteCode:
    """邀请码错误或缺失时的注册行为。"""

    def test_missing_invite_code_returns_403(self, client, monkeypatch):
        """请求体不包含 invite_code 时返回 403。"""
        monkeypatch.setenv("LNN_REGISTRATION_CODE", "SECRET-1234")
        response = client.post(
            "/api/v1/auth/register",
            json={"username": "alice", "password": "Passw0rd!"},
        )
        assert response.status_code == 403
        body = response.json()
        assert body["code"] == 1003
        assert "无效的邀请码" in body["message"]

    def test_wrong_invite_code_returns_403(self, client, monkeypatch):
        """邀请码值不匹配时返回 403。"""
        monkeypatch.setenv("LNN_REGISTRATION_CODE", "SECRET-1234")
        response = client.post(
            "/api/v1/auth/register",
            json={
                "username": "alice",
                "password": "Passw0rd!",
                "invite_code": "WRONG",
            },
        )
        assert response.status_code == 403
        body = response.json()
        assert "无效的邀请码" in body["message"]


class TestRegisterSuccess:
    """注册成功的标准路径。"""

    def test_valid_invite_code_creates_user(self, client, monkeypatch):
        """正确邀请码 + 新用户名应返回 200。"""
        monkeypatch.setenv("LNN_REGISTRATION_CODE", "SECRET-1234")
        response = client.post(
            "/api/v1/auth/register",
            json={
                "username": "alice",
                "password": "Passw0rd!",
                "invite_code": "SECRET-1234",
            },
        )
        assert response.status_code == 200
        body = response.json()
        assert body["message"] == "注册成功"
        assert body["data"]["username"] == "alice"

    def test_duplicate_username_returns_409(self, client, monkeypatch):
        """用户名已存在时返回 409。"""
        monkeypatch.setenv("LNN_REGISTRATION_CODE", "SECRET-1234")
        client.post(
            "/api/v1/auth/register",
            json={
                "username": "bob",
                "password": "Passw0rd!",
                "invite_code": "SECRET-1234",
            },
        )
        response = client.post(
            "/api/v1/auth/register",
            json={
                "username": "bob",
                "password": "OtherPass1!",
                "invite_code": "SECRET-1234",
            },
        )
        assert response.status_code == 409
        body = response.json()
        assert body["code"] == 1009
        assert "用户名已存在" in body["message"]


# ---------------------------------------------------------------------------
# 速率限制测试
# ---------------------------------------------------------------------------


class TestRegisterRateLimitEndpoint:
    """通过 HTTP 接口验证端到端速率限制。

    slowapi 的 @limiter.limit("3/hour") 装饰器对注册端点限流，3 次之后的
    请求会返回 429。验证行为：
    1. 短时间内连续 4 次注册，第 4 次应触发 429；
    2. 响应中包含 ``Retry-After`` 头。
    """

    def test_fourth_request_returns_429_with_retry_after(
        self, client, monkeypatch
    ):
        """同一 IP 在 1 小时内连续 4 次注册，第 4 次返回 429 且响应头有 Retry-After。"""
        monkeypatch.setenv("LNN_REGISTRATION_CODE", "SECRET-1234")
        # 使用不同的用户名避免 409 干扰
        for i in range(3):
            response = client.post(
                "/api/v1/auth/register",
                json={
                    "username": f"user_{i}",
                    "password": "Passw0rd!",
                    "invite_code": "SECRET-1234",
                },
            )
            assert response.status_code == 200, response.text

        # 第 4 次触发限流
        response = client.post(
            "/api/v1/auth/register",
            json={
                "username": "user_4th",
                "password": "Passw0rd!",
                "invite_code": "SECRET-1234",
            },
        )
        assert response.status_code == 429
        assert "Retry-After" in response.headers
        retry_after = int(response.headers["Retry-After"])
        assert 0 < retry_after <= 3600


# ---------------------------------------------------------------------------
# 响应格式一致性测试
# ---------------------------------------------------------------------------


class TestResponseFormat:
    """验证错误响应统一使用 code/message 字段。"""

    def test_403_response_uses_code_and_message(self, client, monkeypatch):
        """403 响应必须包含 code 和 message 字段。"""
        monkeypatch.delenv("LNN_REGISTRATION_CODE", raising=False)
        response = client.post(
            "/api/v1/auth/register",
            json={"username": "alice", "password": "Passw0rd!"},
        )
        body = response.json()
        assert "code" in body
        assert "message" in body
        assert body["code"] == 1003

    def test_409_response_uses_code_and_message(self, client, monkeypatch):
        """409 响应必须包含 code 和 message 字段。"""
        monkeypatch.setenv("LNN_REGISTRATION_CODE", "SECRET-1234")
        # 先注册一次
        client.post(
            "/api/v1/auth/register",
            json={
                "username": "carol",
                "password": "Passw0rd!",
                "invite_code": "SECRET-1234",
            },
        )
        # 第二次同名
        response = client.post(
            "/api/v1/auth/register",
            json={
                "username": "carol",
                "password": "Passw0rd!",
                "invite_code": "SECRET-1234",
            },
        )
        body = response.json()
        assert "code" in body
        assert "message" in body
        assert body["code"] == 1009
