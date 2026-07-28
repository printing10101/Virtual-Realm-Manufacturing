"""Fixtures for API tests."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    """FastAPI TestClient fixture."""
    try:
        from app.main import app

        with TestClient(app) as c:
            yield c
    except Exception as exc:
        # FastAPI 启动失败属于基础设施故障，不应被 skip 掩盖；
        # 改为 fail 使 CI 真实反映启动问题。
        pytest.fail(f"FastAPI app 启动失败: {exc}")
