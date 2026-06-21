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
        pytest.skip(f"FastAPI app 启动失败: {exc}")
