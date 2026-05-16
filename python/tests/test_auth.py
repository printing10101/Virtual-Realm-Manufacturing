"""
Test Authentication Module

Tests for:
- Token generation and storage
- AuthMiddleware: Bearer token authentication
- Permission enforcement logic
- Public endpoint handling
"""

import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.auth import (
    AuthMiddleware,
    generate_token,
    save_token,
    load_token,
    initialize_token,
    PUBLIC_ENDPOINTS,
)


class TestTokenGeneration:
    """Test token generation utilities"""

    def test_generate_token_returns_uuid(self):
        token1 = generate_token()
        token2 = generate_token()

        assert isinstance(token1, str)
        assert len(token1) == 36
        assert token1 != token2

    def test_generate_token_format(self):
        token = generate_token()
        parts = token.split("-")

        assert len(parts) == 5
        assert len(parts[0]) == 8
        assert len(parts[1]) == 4
        assert len(parts[2]) == 4
        assert len(parts[3]) == 4
        assert len(parts[4]) == 12


class TestTokenStorage:
    """Test token save and load functionality"""

    def test_save_token_creates_file(self, tmp_path):
        token = "test-token-12345"
        file_path = tmp_path / ".test_token"

        result = save_token(token, file_path)

        assert result == file_path
        assert file_path.exists()
        assert file_path.read_text() == token

    def test_load_token_success(self, tmp_path):
        token = "test-token-67890"
        file_path = tmp_path / ".test_token"
        file_path.write_text(token)

        result = load_token(file_path)

        assert result == token

    def test_load_token_nonexistent_file(self, tmp_path):
        file_path = tmp_path / "nonexistent"
        result = load_token(file_path)
        assert result is None

    def test_load_token_empty_file(self, tmp_path):
        file_path = tmp_path / "empty_token"
        file_path.write_text("")

        result = load_token(file_path)
        assert result is None

    def test_load_token_whitespace_only(self, tmp_path):
        file_path = tmp_path / "whitespace_token"
        file_path.write_text("   \n\t  ")

        result = load_token(file_path)
        assert result is None

    def test_initialize_token_creates_new(self, tmp_path, monkeypatch):
        monkeypatch.setenv("LNN_TOKEN_FILE", str(tmp_path / ".lnn_token"))

        result = initialize_token()

        assert isinstance(result, str)
        assert len(result) == 36

    def test_initialize_token_reuses_existing(self, tmp_path, monkeypatch):
        monkeypatch.setenv("LNN_TOKEN_FILE", str(tmp_path / ".lnn_token"))

        existing = initialize_token()
        reused = initialize_token()

        assert existing == reused


class TestPublicEndpoints:
    """Test public endpoint configuration"""

    def test_public_endpoints_defined(self):
        assert "/api/health" in PUBLIC_ENDPOINTS
        assert "/api/health/ping" in PUBLIC_ENDPOINTS
        assert "/api/metrics" in PUBLIC_ENDPOINTS

    def test_public_endpoints_count(self):
        assert len(PUBLIC_ENDPOINTS) >= 3


class TestAuthMiddleware:
    """Test AuthMiddleware functionality"""

    @pytest.fixture
    def app_with_auth(self):
        app = FastAPI()

        @app.get("/protected")
        async def protected():
            return {"status": "ok"}

        @app.get("/api/health")
        async def health():
            return {"status": "healthy"}

        middleware = AuthMiddleware(app, enabled=True)
        app.add_middleware(AuthMiddleware, enabled=True, permission_enforced=False)

        return app

    def test_middleware_initialization(self):
        app = FastAPI()
        middleware = AuthMiddleware(app, enabled=True)
        assert middleware.enabled is True
        assert middleware._token is not None

    def test_middleware_disabled(self):
        app = FastAPI()
        middleware = AuthMiddleware(app, enabled=False)
        assert middleware.enabled is False

    def test_middleware_token_property(self):
        app = FastAPI()
        middleware = AuthMiddleware(app, enabled=True)
        assert middleware.token is not None
        assert isinstance(middleware.token, str)

    def test_public_endpoint_no_auth_required(self, tmp_path, monkeypatch):
        monkeypatch.setenv("LNN_TOKEN_FILE", str(tmp_path / ".lnn_token"))

        app = FastAPI()

        @app.get("/api/health")
        async def health():
            return {"status": "healthy"}

        app.add_middleware(AuthMiddleware, enabled=True)

        client = TestClient(app)
        response = client.get("/api/health")

        assert response.status_code == 200

    def test_missing_authorization_header(self, tmp_path, monkeypatch):
        monkeypatch.setenv("LNN_TOKEN_FILE", str(tmp_path / ".lnn_token"))

        app = FastAPI()

        @app.get("/protected")
        async def protected():
            return {"status": "ok"}

        app.add_middleware(AuthMiddleware, enabled=True)

        client = TestClient(app)
        response = client.get("/protected")

        assert response.status_code == 401
        assert "unauthorized" in response.json()["error"]

    def test_invalid_authorization_format(self, tmp_path, monkeypatch):
        monkeypatch.setenv("LNN_TOKEN_FILE", str(tmp_path / ".lnn_token"))

        app = FastAPI()

        @app.get("/protected")
        async def protected():
            return {"status": "ok"}

        app.add_middleware(AuthMiddleware, enabled=True)

        client = TestClient(app)
        response = client.get("/protected", headers={"Authorization": "Basic token"})

        assert response.status_code == 401

    def test_invalid_token(self, tmp_path, monkeypatch):
        monkeypatch.setenv("LNN_TOKEN_FILE", str(tmp_path / ".lnn_token"))

        app = FastAPI()

        @app.get("/protected")
        async def protected():
            return {"status": "ok"}

        app.add_middleware(AuthMiddleware, enabled=True)

        client = TestClient(app)
        response = client.get(
            "/protected", headers={"Authorization": "Bearer invalid_token"}
        )

        assert response.status_code == 401
        assert "Invalid authentication token" in response.json()["message"]

    def test_valid_token(self, tmp_path, monkeypatch):
        token_file = tmp_path / ".lnn_token"
        monkeypatch.setenv("LNN_TOKEN_FILE", str(token_file))

        app = FastAPI()

        @app.get("/protected")
        async def protected():
            return {"status": "ok"}

        app.add_middleware(AuthMiddleware, enabled=True)

        client = TestClient(app)
        response = client.get(
            "/protected", headers={"Authorization": f"Bearer {token_file.read_text()}"}
        )

        assert response.status_code == 200

    def test_docs_endpoints_excluded(self, tmp_path, monkeypatch):
        monkeypatch.setenv("LNN_TOKEN_FILE", str(tmp_path / ".lnn_token"))

        app = FastAPI()

        @app.get("/protected")
        async def protected():
            return {"status": "ok"}

        app.add_middleware(AuthMiddleware, enabled=True)

        client = TestClient(app)

        for path in ["/api/docs", "/api/redoc", "/api/openapi.json"]:
            response = client.get(path)
            assert response.status_code != 401


class TestAuthMiddlewarePermissionEnforcement:
    """Test AuthMiddleware with permission enforcement enabled"""

    def test_permission_enforcement_enabled(self, tmp_path, monkeypatch):
        token_file = tmp_path / ".lnn_token"
        monkeypatch.setenv("LNN_TOKEN_FILE", str(token_file))
        monkeypatch.setenv(
            "LNN_TOKEN_META_FILE", str(tmp_path / ".lnn_token_meta.json")
        )

        meta_data = {"token": token_file.read_text(), "level": "R"}
        (tmp_path / ".lnn_token_meta.json").write_text(json.dumps(meta_data))

        app = FastAPI()

        @app.post("/api/v1/lnn/train")
        async def train():
            return {"status": "training"}

        app.add_middleware(AuthMiddleware, enabled=True, permission_enforced=True)

        client = TestClient(app)

        token = token_file.read_text()
        response = client.post(
            "/api/v1/lnn/train", headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 403
        assert "Insufficient permission" in response.json()["message"]

    def test_permission_satisfied(self, tmp_path, monkeypatch):
        token_file = tmp_path / ".lnn_token"
        monkeypatch.setenv("LNN_TOKEN_FILE", str(token_file))
        monkeypatch.setenv(
            "LNN_TOKEN_META_FILE", str(tmp_path / ".lnn_token_meta.json")
        )

        meta_data = {"token": token_file.read_text(), "level": "B"}
        (tmp_path / ".lnn_token_meta.json").write_text(json.dumps(meta_data))

        app = FastAPI()

        @app.post("/api/v1/lnn/train")
        async def train():
            return {"status": "training"}

        app.add_middleware(AuthMiddleware, enabled=True, permission_enforced=True)

        client = TestClient(app)

        token = token_file.read_text()
        response = client.post(
            "/api/v1/lnn/train", headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 200


class TestAuthMiddlewareEdgeCases:
    """Test edge cases for authentication"""

    def test_empty_token_file(self, tmp_path, monkeypatch):
        token_file = tmp_path / ".lnn_token"
        token_file.write_text("")
        monkeypatch.setenv("LNN_TOKEN_FILE", str(token_file))

        app = FastAPI()
        middleware = AuthMiddleware(app, enabled=True)

        assert middleware.token is not None

    def test_permission_level_fallback(self, tmp_path, monkeypatch):
        token_file = tmp_path / ".lnn_token"
        monkeypatch.setenv("LNN_TOKEN_FILE", str(token_file))
        monkeypatch.setenv(
            "LNN_TOKEN_META_FILE", str(tmp_path / ".lnn_token_meta.json")
        )

        (tmp_path / ".lnn_token_meta.json").write_text("{}")

        app = FastAPI()

        @app.post("/api/v1/machine/params")
        async def machine_params():
            return {"status": "ok"}

        app.add_middleware(AuthMiddleware, enabled=True, permission_enforced=True)

        client = TestClient(app)

        token = token_file.read_text()
        response = client.post(
            "/api/v1/machine/params", headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 403


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
