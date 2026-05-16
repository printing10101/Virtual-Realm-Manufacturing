"""Shared pytest fixtures for the Lingjing Manufacturing test suite."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path
from typing import Generator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


@pytest.fixture(autouse=True)
def _env_setup(monkeypatch):
    """Ensure test environment variables are set before each test."""
    monkeypatch.setenv("LNN_AUTH_ENABLED", "false")
    monkeypatch.setenv("AGENT_AUTH_ENABLED", "false")
    monkeypatch.setenv("LNN_PERMISSION_ENFORCED", "false")
    monkeypatch.setenv("LNN_GSTACK_DIR", ".lingjing/.gstack_test")
    yield


@pytest.fixture
def app() -> FastAPI:
    """Provide a fresh FastAPI app instance for testing."""
    from app.main import app as _app

    return _app


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    """Provide a TestClient bound to the app."""
    from starlette.testclient import TestClient as _TestClient

    return _TestClient(app)


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """Provide a temporary directory that is cleaned up after the test."""
    with tempfile.TemporaryDirectory() as tmp:
        yield Path(tmp)


@pytest.fixture
def sample_predict_request() -> dict:
    """Provide a valid LNN predict request payload."""
    return {
        "model_name": "test_model",
        "input_data": [1.0, 2.0, 3.0, 4.0, 5.0],
    }


@pytest.fixture
def sample_train_request() -> dict:
    """Provide a valid training request payload."""
    return {
        "model_name": "test_model",
        "model_type": "cfc",
        "dataset_config": {
            "type": "csv",
            "path": "/fake/path.csv",
            "target_column": "wear",
            "feature_columns": ["speed", "feed", "depth"],
        },
        "training_config": {
            "epochs": 10,
            "batch_size": 32,
            "learning_rate": 0.001,
        },
    }
