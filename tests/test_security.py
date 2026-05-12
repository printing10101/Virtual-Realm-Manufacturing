"""
Comprehensive Security Tests

Tests for:
- CORS configuration (environment-aware)
- Bearer Token authentication middleware
- Permission model (R/W/B/N/C/T)
- Paper-Only mode guard
- Log sanitizer enhancements
- Path security validation
"""
import os
import sys
import tempfile
import pytest
import stat
from unittest.mock import patch, MagicMock
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "python"))

from app.core.cors_config import CorsSettings, is_allowed_origin, get_cors_origins, get_cors_config, is_development, is_production
from app.core.auth import AuthMiddleware, generate_token, save_token, load_token, initialize_token, PUBLIC_ENDPOINTS
from app.core.permissions import PermissionLevel, PermissionChecker, PaperOnlyGuard, PERMISSION_HIERARCHY, permission_checker
from app.core.log_sanitizer import LogSanitizer, sanitizer


class TestCorsConfig:
    def setup_method(self):
        os.environ.pop("LINGJING_ENV", None)
        os.environ.pop("ALLOWED_ORIGINS", None)

    def teardown_method(self):
        os.environ.pop("LINGJING_ENV", None)
        os.environ.pop("ALLOWED_ORIGINS", None)

    def test_production_default(self):
        with patch.dict(os.environ, {"LINGJING_ENV": "production", "ALLOWED_ORIGINS": ""}, clear=False):
            os.environ.pop("ALLOWED_ORIGINS", None)
            settings = CorsSettings()
            origins = settings.get_origins()
            assert "*" not in origins
            assert "tauri://localhost" in origins
            assert "https://tauri.localhost" in origins

    def test_development_allows_localhost(self):
        with patch.dict(os.environ, {"LINGJING_ENV": "development", "ALLOWED_ORIGINS": ""}, clear=False):
            os.environ.pop("ALLOWED_ORIGINS", None)
            settings = CorsSettings()
            origins = settings.get_origins()
            assert len(origins) > 0
            assert any("localhost" in o for o in origins)

    def test_is_allowed_origin_production(self):
        with patch.dict(os.environ, {"LINGJING_ENV": "production"}, clear=False):
            os.environ.pop("ALLOWED_ORIGINS", None)
            assert is_allowed_origin("tauri://localhost", "production")
            assert is_allowed_origin("https://tauri.localhost", "production")
            assert not is_allowed_origin("https://evil.com", "production")
            assert not is_allowed_origin("http://malicious-site.com", "production")

    def test_is_allowed_origin_development(self):
        with patch.dict(os.environ, {"LINGJING_ENV": "development"}, clear=False):
            os.environ.pop("ALLOWED_ORIGINS", None)
            assert is_allowed_origin("http://localhost:5173", "development")
            assert is_allowed_origin("http://localhost:3000", "development")
            assert is_allowed_origin("https://localhost:8080", "development")
            assert not is_allowed_origin("https://evil.com", "development")

    def test_env_override(self):
        with patch.dict(os.environ, {"ALLOWED_ORIGINS": "http://custom.local,http://other.local"}, clear=False):
            os.environ.pop("LINGJING_ENV", None)
            origins = get_cors_origins()
            assert "http://custom.local" in origins
            assert "http://other.local" in origins

    def test_cors_config_structure(self):
        with patch.dict(os.environ, {"LINGJING_ENV": "production"}, clear=False):
            os.environ.pop("ALLOWED_ORIGINS", None)
            config = get_cors_config("production")
            assert "allow_origins" in config
            assert "allow_credentials" in config
            assert "allow_methods" in config
            assert "allow_headers" in config
            assert "max_age" in config
            assert config["max_age"] == 600

    def test_cors_config_dev_max_age(self):
        with patch.dict(os.environ, {"LINGJING_ENV": "development"}, clear=False):
            os.environ.pop("ALLOWED_ORIGINS", None)
            config = get_cors_config("development")
            assert config["max_age"] == 3600

    def test_is_development_production(self):
        with patch.dict(os.environ, {"LINGJING_ENV": "production"}, clear=False):
            os.environ.pop("ALLOWED_ORIGINS", None)
            assert is_production()
            assert not is_development()

    def test_is_development_dev(self):
        with patch.dict(os.environ, {"LINGJING_ENV": "development"}, clear=False):
            os.environ.pop("ALLOWED_ORIGINS", None)
            assert is_development()
            assert not is_production()

    def test_env_fallback_to_production(self):
        with patch.dict(os.environ, {"LINGJING_ENV": "invalid"}, clear=False):
            os.environ.pop("ALLOWED_ORIGINS", None)
            assert is_production()


class TestAuthMiddleware:
    def test_generate_token_is_uuid(self):
        token = generate_token()
        assert len(token) == 36
        parts = token.split("-")
        assert len(parts) == 5
        assert len(parts[0]) == 8

    def test_save_and_load_token(self):
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".token") as f:
            token_path = Path(f.name)

        try:
            test_token = "test-token-12345"
            save_token(test_token, token_path)
            loaded = load_token(token_path)
            assert loaded == test_token
        finally:
            token_path.unlink(missing_ok=True)

    def test_load_nonexistent_token(self):
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".token") as f:
            token_path = Path(f.name)
        token_path.unlink()
        result = load_token(token_path)
        assert result is None

    def test_initialize_token_creates_new(self):
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".token") as f:
            token_path = Path(f.name)
        token_path.unlink(missing_ok=True)

        try:
            with patch("app.core.auth.get_token_file_path", return_value=token_path):
                token = initialize_token()
                assert token is not None
                assert len(token) == 36
                loaded = load_token(token_path)
                assert loaded == token
        finally:
            token_path.unlink(missing_ok=True)

    def test_initialize_token_reuses_existing(self):
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".token") as f:
            f.write("existing-token-uuid")
            token_path = Path(f.name)

        try:
            with patch("app.core.auth.get_token_file_path", return_value=token_path):
                token = initialize_token()
                assert token == "existing-token-uuid"
        finally:
            token_path.unlink(missing_ok=True)

    def test_public_endpoints_exempted(self):
        assert "/api/health" in PUBLIC_ENDPOINTS
        assert "/api/health/ping" in PUBLIC_ENDPOINTS
        assert "/api/metrics" in PUBLIC_ENDPOINTS

    @pytest.mark.asyncio
    async def test_auth_middleware_blocks_without_token(self):
        mock_app = MagicMock()
        middleware = AuthMiddleware(mock_app, enabled=True)
        middleware._token = "valid-token"

        request = MagicMock()
        request.url.path = "/api/v1/lnn/predict"
        request.headers = {}
        request.client = MagicMock()
        request.client.host = "127.0.0.1"

        response = await middleware.dispatch(request, MagicMock())
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_auth_middleware_allows_with_valid_token(self):
        mock_app = MagicMock()
        middleware = AuthMiddleware(mock_app, enabled=True)
        middleware._token = "valid-token"

        request = MagicMock()
        request.url.path = "/api/v1/lnn/predict"
        request.headers = {"Authorization": "Bearer valid-token"}

        async def mock_call_next(req):
            return MagicMock()

        response = await middleware.dispatch(request, mock_call_next)
        assert response is not None

    @pytest.mark.asyncio
    async def test_auth_middleware_allows_health_check(self):
        mock_app = MagicMock()
        middleware = AuthMiddleware(mock_app, enabled=True)
        middleware._token = "valid-token"

        request = MagicMock()
        request.url.path = "/api/health"
        request.headers = {}

        async def mock_call_next(req):
            return MagicMock()

        response = await middleware.dispatch(request, mock_call_next)
        assert response is not None

    @pytest.mark.asyncio
    async def test_auth_middleware_disabled(self):
        mock_app = MagicMock()
        middleware = AuthMiddleware(mock_app, enabled=False)

        request = MagicMock()
        request.url.path = "/api/v1/lnn/predict"
        request.headers = {}

        async def mock_call_next(req):
            return MagicMock()

        response = await middleware.dispatch(request, mock_call_next)
        assert response is not None

    @pytest.mark.asyncio
    async def test_auth_middleware_blocks_invalid_token(self):
        mock_app = MagicMock()
        middleware = AuthMiddleware(mock_app, enabled=True)
        middleware._token = "valid-token"

        request = MagicMock()
        request.url.path = "/api/v1/lnn/predict"
        request.headers = {"Authorization": "Bearer wrong-token"}
        request.client = MagicMock()
        request.client.host = "127.0.0.1"

        response = await middleware.dispatch(request, MagicMock())
        assert response.status_code == 401


class TestPermissionModel:
    def test_permission_hierarchy(self):
        assert PERMISSION_HIERARCHY[PermissionLevel.R] < PERMISSION_HIERARCHY[PermissionLevel.W]
        assert PERMISSION_HIERARCHY[PermissionLevel.W] < PERMISSION_HIERARCHY[PermissionLevel.B]
        assert PERMISSION_HIERARCHY[PermissionLevel.B] < PERMISSION_HIERARCHY[PermissionLevel.N]
        assert PERMISSION_HIERARCHY[PermissionLevel.N] < PERMISSION_HIERARCHY[PermissionLevel.C]
        assert PERMISSION_HIERARCHY[PermissionLevel.C] < PERMISSION_HIERARCHY[PermissionLevel.T]

    def test_read_access(self):
        pc = PermissionChecker()
        assert pc.has_permission(PermissionLevel.R, "/api/v1/lnn/predict", "GET")
        assert pc.has_permission(PermissionLevel.W, "/api/v1/lnn/predict", "GET")
        assert pc.has_permission(PermissionLevel.T, "/api/v1/lnn/predict", "GET")

    def test_write_access(self):
        pc = PermissionChecker()
        assert not pc.has_permission(PermissionLevel.R, "/api/v1/lnn/save_prediction", "POST")
        assert pc.has_permission(PermissionLevel.W, "/api/v1/lnn/save_prediction", "POST")
        assert pc.has_permission(PermissionLevel.B, "/api/v1/lnn/save_prediction", "POST")

    def test_training_access(self):
        pc = PermissionChecker()
        assert not pc.has_permission(PermissionLevel.R, "/api/v1/lnn/train", "POST")
        assert not pc.has_permission(PermissionLevel.W, "/api/v1/lnn/train", "POST")
        assert pc.has_permission(PermissionLevel.B, "/api/v1/lnn/train", "POST")

    def test_credential_access(self):
        pc = PermissionChecker()
        assert not pc.has_permission(PermissionLevel.R, "/api/v1/config", "GET")
        assert not pc.has_permission(PermissionLevel.B, "/api/v1/config", "GET")
        assert pc.has_permission(PermissionLevel.C, "/api/v1/config", "GET")
        assert pc.has_permission(PermissionLevel.T, "/api/v1/config", "GET")

    def test_execute_access(self):
        pc = PermissionChecker()
        assert not pc.has_permission(PermissionLevel.R, "/api/v1/machine/params", "POST")
        assert not pc.has_permission(PermissionLevel.C, "/api/v1/machine/params", "POST")
        assert pc.has_permission(PermissionLevel.T, "/api/v1/machine/params", "POST")

    def test_default_permissions(self):
        pc = PermissionChecker()
        assert pc.has_permission(PermissionLevel.R, "/api/v1/unknown", "GET")
        assert pc.has_permission(PermissionLevel.W, "/api/v1/unknown", "POST")

    def test_rate_limit(self):
        pc = PermissionChecker()
        token_id = "test-token"
        assert pc.check_rate_limit(token_id)
        assert pc.check_rate_limit(token_id)

    def test_rate_limit_exceeded(self):
        pc = PermissionChecker()
        pc._rate_limit_config.max_requests = 2
        pc._rate_limit_config.window_seconds = 60

        token_id = "rate-test-token"
        assert pc.check_rate_limit(token_id)
        assert pc.check_rate_limit(token_id)
        assert not pc.check_rate_limit(token_id)

    def test_get_required_permission(self):
        pc = PermissionChecker()
        assert pc.get_required_permission("GET", "/api/v1/lnn/predict") == PermissionLevel.R
        assert pc.get_required_permission("POST", "/api/v1/lnn/train") == PermissionLevel.B
        assert pc.get_required_permission("POST", "/api/v1/machine/params") == PermissionLevel.T


class TestPaperOnlyMode:
    def test_default_paper_only(self):
        guard = PaperOnlyGuard()
        assert not guard.is_live_execution_allowed()

    def test_live_execution_enabled(self):
        with patch.dict(os.environ, {"LNN_LIVE_EXECUTION_ENABLED": "true"}):
            guard = PaperOnlyGuard()
            assert guard.is_live_execution_allowed()

    def test_paper_only_simulates(self):
        guard = PaperOnlyGuard()
        result = guard.simulate_t_operation({"action": "send_params", "machine_id": 1})
        assert result["status"] == "simulated"
        assert "Paper-Only" in result["message"]

    def test_triple_check_all_pass(self):
        with patch.dict(os.environ, {"LNN_LIVE_EXECUTION_ENABLED": "true"}):
            guard = PaperOnlyGuard()
            allowed, msg = guard.check_t_operation(
                has_t_permission=True,
                ui_confirmed=True
            )
            assert allowed
            assert "approved" in msg

    def test_triple_check_no_live_execution(self):
        guard = PaperOnlyGuard()
        allowed, msg = guard.check_t_operation(
            has_t_permission=True,
            ui_confirmed=True
        )
        assert not allowed
        assert "Paper-Only" in msg

    def test_triple_check_no_t_permission(self):
        with patch.dict(os.environ, {"LNN_LIVE_EXECUTION_ENABLED": "true"}):
            guard = PaperOnlyGuard()
            allowed, msg = guard.check_t_operation(
                has_t_permission=False,
                ui_confirmed=True
            )
            assert not allowed
            assert "Insufficient permission" in msg

    def test_triple_check_no_ui_confirmation(self):
        with patch.dict(os.environ, {"LNN_LIVE_EXECUTION_ENABLED": "true"}):
            guard = PaperOnlyGuard()
            allowed, msg = guard.check_t_operation(
                has_t_permission=True,
                ui_confirmed=False
            )
            assert not allowed
            assert "UI confirmation" in msg


class TestLogSanitizer:
    def test_sanitize_api_key(self):
        s = LogSanitizer()
        data = {"api_key": "sk-1234567890abcdef", "name": "test"}
        result = s.sanitize(data)
        assert "1234567890abcdef" not in str(result["api_key"])
        assert result["name"] == "test"

    def test_sanitize_bearer_token(self):
        s = LogSanitizer()
        text = "Authorization: Bearer abcdef12-3456-7890-abcd-ef1234567890abc"
        result = s._sanitize_string(text)
        assert "abcdef12-3456-7890-abcd-ef1234567890abc" not in result

    def test_sanitize_file_paths(self):
        s = LogSanitizer()
        text = "C:\\Users\\john\\Documents\\file.txt"
        result = s._sanitize_string(text)
        assert "john" not in result

    def test_sanitize_process_params(self):
        s = LogSanitizer()
        data = {"cutting_speed": 1500, "feed_rate": 200}
        result = s.sanitize(data)
        assert "1500" not in str(result["cutting_speed"])
        assert "工艺参数已脱敏" in str(result["cutting_speed"])

    def test_sanitize_file_content(self):
        s = LogSanitizer()
        data = {"file_content": "very long content" * 100}
        result = s.sanitize(data)
        assert "very long content" not in result["file_content"]
        assert "已脱敏" in result["file_content"]

    def test_sanitize_config_keys(self):
        s = LogSanitizer()
        data = {"database_url": "postgresql://admin:secret@host/db", "name": "test"}
        result = s.sanitize(data)
        assert "secret" not in str(result["database_url"])
        assert "已脱敏" in str(result["database_url"])

    def test_sanitize_error_response(self):
        s = LogSanitizer()
        error = Exception("Internal file path: C:\\secret\\data.db")
        result = s.sanitize_error_response(error)
        assert "Internal file path" not in result["message"]
        assert "C:\\secret" not in result["message"]
        assert result["message"] == "Internal server error"

    def test_sanitize_list(self):
        s = LogSanitizer()
        data = [{"api_key": "secret123"}, {"name": "public"}]
        result = s.sanitize(data)
        assert "secret123" not in str(result[0]["api_key"])
        assert result[1]["name"] == "public"

    def test_sanitize_none(self):
        s = LogSanitizer()
        assert s.sanitize(None) is None

    def test_sanitize_int(self):
        s = LogSanitizer()
        assert s.sanitize(42) == 42

    def test_sanitize_user_input_truncated(self):
        s = LogSanitizer()
        data = {"description": "A" * 100}
        result = s.sanitize(data)
        assert len(result["description"]) <= s.USER_INPUT_MAX_LENGTH + 3


class TestSecurityIntegration:
    def test_cors_and_auth_compatibility(self):
        with patch.dict(os.environ, {"LINGJING_ENV": "development"}):
            settings = CorsSettings()
            origins = settings.get_origins()
            assert len(origins) > 0
            assert any("localhost" in o for o in origins)

    def test_permissions_map_all_endpoints(self):
        pc = PermissionChecker()
        for endpoint_key, level in pc.ENDPOINT_PERMISSIONS.items():
            parts = endpoint_key.split(" ", 1)
            if len(parts) == 2:
                method, path = parts
                assert pc.has_permission(level, path, method)
                assert not pc.has_permission(PermissionLevel.R, path, method) if level != PermissionLevel.R else True

    def test_paper_only_and_permission_integration(self):
        with patch.dict(os.environ, {"LNN_LIVE_EXECUTION_ENABLED": "true"}):
            guard = PaperOnlyGuard()
            pc = PermissionChecker()

            has_t = pc.has_permission(PermissionLevel.T, "/api/v1/machine/params", "POST")
            allowed, msg = guard.check_t_operation(
                has_t_permission=has_t,
                ui_confirmed=True
            )
            assert allowed


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
