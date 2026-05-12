"""
Additional tests to improve coverage for core modules:
- auth.py (target: 80%+)
- cors_config.py (target: 80%+)
- log_sanitizer.py (target: 80%+)
"""
import os
import sys
import tempfile
import json
import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "python"))

from app.core.auth import AuthMiddleware, generate_token, save_token, load_token, initialize_token, _get_token_metadata, PUBLIC_ENDPOINTS
from app.core.cors_config import (
    CorsSettings, get_environment, is_allowed_origin, get_cors_origins, 
    get_cors_config, get_security_headers, is_development, is_production,
    PRODUCTION_ORIGINS, DEVELOPMENT_ORIGINS
)
from app.core.log_sanitizer import LogSanitizer, sanitizer


class TestAuthCoverage:
    """Target uncovered lines in auth.py: 35-49, 67, 83-85, 110, 145-153"""

    def setup_method(self):
        os.environ.pop("LNN_TOKEN_META_FILE", None)
        os.environ.pop("LNN_TOKEN_FILE", None)

    def teardown_method(self):
        os.environ.pop("LNN_TOKEN_META_FILE", None)
        os.environ.pop("LNN_TOKEN_FILE", None)

    def test_get_token_metadata_no_file(self):
        """Test token metadata when meta file doesn't exist - line 36-37"""
        with patch("pathlib.Path.exists", return_value=False):
            result = _get_token_metadata("any-token")
            assert result == {"level": "T"}

    def test_get_token_metadata_list_format(self):
        """Test token metadata with list format - lines 40-43"""
        test_token = "test-token-uuid-123"
        meta_data = [
            {"token": "other-token", "level": "R"},
            {"token": test_token, "level": "W"},
        ]
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
            json.dump(meta_data, f)
            meta_path = Path(f.name)
        
        try:
            with patch.dict(os.environ, {"LNN_TOKEN_META_FILE": str(meta_path)}, clear=False):
                result = _get_token_metadata(test_token)
                assert result["level"] == "W"
        finally:
            meta_path.unlink(missing_ok=True)

    def test_get_token_metadata_dict_format(self):
        """Test token metadata with dict format - lines 44-46"""
        test_token = "dict-format-token"
        meta_data = {"token": test_token, "level": "B"}
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
            json.dump(meta_data, f)
            meta_path = Path(f.name)
        
        try:
            with patch.dict(os.environ, {"LNN_TOKEN_META_FILE": str(meta_path)}, clear=False):
                result = _get_token_metadata(test_token)
                assert result["level"] == "B"
        finally:
            meta_path.unlink(missing_ok=True)

    def test_get_token_metadata_invalid_json(self):
        """Test token metadata with invalid JSON - lines 47-48"""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
            f.write("invalid json{{{")
            meta_path = Path(f.name)
        
        try:
            with patch.dict(os.environ, {"LNN_TOKEN_META_FILE": str(meta_path)}, clear=False):
                result = _get_token_metadata("any-token")
                assert result == {"level": "T"}
        finally:
            meta_path.unlink(missing_ok=True)

    def test_save_token_unix_permissions(self):
        """Test token save with Unix permissions - line 67"""
        if os.name == "nt":
            pytest.skip("Unix permissions test not applicable on Windows")
        
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.token') as f:
            token_path = Path(f.name)
        
        try:
            save_token("test-token", token_path)
            stat_result = os.stat(str(token_path))
            assert stat_result.st_mode & 0o777 == 0o600
        finally:
            token_path.unlink(missing_ok=True)

    def test_load_token_exception_handling(self):
        """Test load_token exception handling - lines 83-85"""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.token') as f:
            token_path = Path(f.name)
        
        try:
            with patch.object(Path, 'read_text', side_effect=PermissionError("Access denied")):
                result = load_token(token_path)
                assert result is None
        finally:
            token_path.unlink(missing_ok=True)

    def test_auth_middleware_token_property(self):
        """Test AuthMiddleware.token property - line 110"""
        mock_app = MagicMock()
        middleware = AuthMiddleware(mock_app, enabled=False)
        assert middleware.token is None

    @pytest.mark.asyncio
    async def test_auth_middleware_permission_enforcement_r_level(self):
        """Test permission enforcement with R level token - lines 145-153"""
        test_token = "r-level-token"
        meta_data = {"token": test_token, "level": "R"}
        
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
            json.dump(meta_data, f)
            meta_path = Path(f.name)
        
        try:
            with patch.dict(os.environ, {"LNN_TOKEN_META_FILE": str(meta_path)}, clear=False):
                mock_app = MagicMock()
                middleware = AuthMiddleware(mock_app, enabled=True, permission_enforced=True)
                middleware._token = test_token

                request = MagicMock()
                request.url.path = "/api/v1/lnn/train"
                request.method = "POST"
                request.headers = {"Authorization": f"Bearer {test_token}"}

                response = await middleware.dispatch(request, MagicMock())
                assert response.status_code == 403
                assert "Insufficient permission" in response.body.decode()
        finally:
            meta_path.unlink(missing_ok=True)

    @pytest.mark.asyncio
    async def test_auth_middleware_permission_enforcement_invalid_level(self):
        """Test permission enforcement with invalid token level - lines 149-150"""
        test_token = "invalid-level-token"
        meta_data = {"token": test_token, "level": "INVALID"}
        
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
            json.dump(meta_data, f)
            meta_path = Path(f.name)
        
        try:
            with patch.dict(os.environ, {"LNN_TOKEN_META_FILE": str(meta_path)}, clear=False):
                mock_app = MagicMock()
                middleware = AuthMiddleware(mock_app, enabled=True, permission_enforced=True)
                middleware._token = test_token

                request = MagicMock()
                request.url.path = "/api/v1/lnn/predict"
                request.method = "GET"
                request.headers = {"Authorization": f"Bearer {test_token}"}

                async def mock_call_next(req):
                    return MagicMock()

                response = await middleware.dispatch(request, mock_call_next)
                assert response is not None
        finally:
            meta_path.unlink(missing_ok=True)

    @pytest.mark.asyncio
    async def test_auth_middleware_docs_endpoints_exempted(self):
        """Test that /api/docs endpoints are exempted - line 118"""
        mock_app = MagicMock()
        middleware = AuthMiddleware(mock_app, enabled=True)

        for path in ["/api/docs", "/api/docs/v1", "/api/redoc", "/api/openapi.json"]:
            request = MagicMock()
            request.url.path = path
            request.headers = {}

            async def mock_call_next(req):
                return MagicMock()

            response = await middleware.dispatch(request, mock_call_next)
            assert response is not None

    @pytest.mark.asyncio
    async def test_auth_middleware_no_client_host(self):
        """Test auth middleware when request.client is None - line 135"""
        mock_app = MagicMock()
        middleware = AuthMiddleware(mock_app, enabled=True)
        middleware._token = "valid-token"

        request = MagicMock()
        request.url.path = "/api/v1/lnn/predict"
        request.headers = {"Authorization": "Bearer wrong-token"}
        request.client = None

        response = await middleware.dispatch(request, MagicMock())
        assert response.status_code == 401


class TestCorsCoverage:
    """Target uncovered lines in cors_config.py: 41, 45, 59, 62, 65, 68-82, 97, 101-102, 141"""

    def setup_method(self):
        os.environ.pop("LINGJING_ENV", None)
        os.environ.pop("ALLOWED_ORIGINS", None)

    def teardown_method(self):
        os.environ.pop("LINGJING_ENV", None)
        os.environ.pop("ALLOWED_ORIGINS", None)

    def test_invalid_env_fallback_to_production(self):
        """Test invalid environment falls back to production - line 41"""
        with patch.dict(os.environ, {"LINGJING_ENV": "staging"}, clear=False):
            settings = CorsSettings()
            assert settings._env == "production"

    def test_env_override_with_commas(self):
        """Test environment variable override with multiple origins - line 45"""
        with patch.dict(os.environ, {"ALLOWED_ORIGINS": "http://a.com, http://b.com, , http://c.com"}, clear=False):
            settings = CorsSettings()
            origins = settings.get_origins()
            assert "http://a.com" in origins
            assert "http://b.com" in origins
            assert "http://c.com" in origins
            assert "" not in origins

    def test_get_methods(self):
        """Test get_methods - line 59"""
        settings = CorsSettings()
        methods = settings.get_methods()
        assert "GET" in methods
        assert "POST" in methods
        assert "OPTIONS" in methods

    def test_get_headers(self):
        """Test get_headers - line 62"""
        settings = CorsSettings()
        headers = settings.get_headers()
        assert headers == ["*"]

    def test_get_expose_headers(self):
        """Test get_expose_headers - line 65"""
        settings = CorsSettings()
        headers = settings.get_expose_headers()
        assert "X-Content-Type-Options" in headers
        assert "X-Frame-Options" in headers

    def test_is_allowed_origin_empty(self):
        """Test is_allowed_origin with empty origin - lines 68-69"""
        with patch.dict(os.environ, {"LINGJING_ENV": "production"}, clear=False):
            settings = CorsSettings()
            assert not settings.is_allowed_origin("")
            assert not settings.is_allowed_origin(None)

    def test_is_allowed_origin_development_patterns(self):
        """Test is_allowed_origin with development patterns - lines 76-80"""
        with patch.dict(os.environ, {"LINGJING_ENV": "development"}, clear=False):
            settings = CorsSettings()
            assert settings.is_allowed_origin("http://localhost:9999")
            assert settings.is_allowed_origin("https://localhost:4000")
            assert not settings.is_allowed_origin("https://evil.com")

    def test_is_allowed_origin_production_exact_match(self):
        """Test is_allowed_origin with production exact match - line 82"""
        with patch.dict(os.environ, {"LINGJING_ENV": "production"}, clear=False):
            settings = CorsSettings()
            assert settings.is_allowed_origin("tauri://localhost")
            assert settings.is_allowed_origin("http://localhost:*")
            assert not settings.is_allowed_origin("http://localhost:3000")

    def test_get_environment_invalid_value(self):
        """Test get_environment with invalid value - line 90"""
        with patch.dict(os.environ, {"LINGJING_ENV": "invalid"}, clear=False):
            env = get_environment()
            assert env == "production"

    def test_is_allowed_origin_with_override_env(self):
        """Test is_allowed_origin with override_env parameter - line 95-97"""
        with patch.dict(os.environ, {"LINGJING_ENV": "production"}, clear=False):
            assert is_allowed_origin("http://localhost:3000", override_env="development")
            assert not is_allowed_origin("http://localhost:3000", override_env="production")

    def test_is_allowed_origin_with_override_and_env_override(self):
        """Test is_allowed_origin with environment variable override - lines 101-102"""
        with patch.dict(os.environ, {"ALLOWED_ORIGINS": "http://custom.local"}, clear=False):
            assert is_allowed_origin("http://custom.local")
            assert not is_allowed_origin("http://other.local")

    def test_get_security_headers(self):
        """Test get_security_headers - line 141"""
        headers = get_security_headers()
        assert headers["X-Content-Type-Options"] == "nosniff"
        assert headers["X-Frame-Options"] == "DENY"
        assert headers["X-XSS-Protection"] == "1; mode=block"

    def test_is_development_and_is_production(self):
        """Test is_development and is_production helper functions - lines 149, 153"""
        with patch.dict(os.environ, {"LINGJING_ENV": "development"}, clear=False):
            assert is_development()
            assert not is_production()
        
        with patch.dict(os.environ, {"LINGJING_ENV": "production"}, clear=False):
            assert is_production()
            assert not is_development()


class TestLogSanitizerCoverage:
    """Target uncovered lines in log_sanitizer.py: 103-104, 118, 171-177, 180-183, 189-195, 202-211, 215, 219-220, 225, 227, 239"""

    def test_sanitizer_getpass_exception(self):
        """Test sanitizer initialization when getpass fails - lines 103-104"""
        with patch("getpass.getuser", side_effect=Exception("Cannot get user")):
            s = LogSanitizer()
            assert s._current_user is None

    def test_sanitize_unknown_type(self):
        """Test sanitize with unknown type - line 118"""
        s = LogSanitizer()
        class CustomObject:
            def __str__(self):
                return "custom_object_str"
        
        obj = CustomObject()
        result = s.sanitize(obj)
        assert result == "custom_object_str"

    def test_sanitize_process_param_dict_with_numbers(self):
        """Test process param dict with numeric values - lines 171-177"""
        s = LogSanitizer()
        data = {"cutting_speed": {"value": 1500, "unit": "rpm"}}
        result = s.sanitize(data)
        assert result["cutting_speed"]["value"] == "[工艺参数已脱敏]"
        assert result["cutting_speed"]["unit"] == "rpm"

    def test_sanitize_process_param_string(self):
        """Test process param string value - lines 180-181"""
        s = LogSanitizer()
        data = {"cutting_speed": "切削速度: 1500 rpm"}
        result = s.sanitize(data)
        assert "[工艺参数已脱敏]" in result["cutting_speed"]

    def test_sanitize_process_param_other_type(self):
        """Test process param with other type - line 183"""
        s = LogSanitizer()
        data = {"cutting_speed": ["list", "of", "values"]}
        result = s.sanitize(data)
        assert result["cutting_speed"] == ["list", "of", "values"]

    def test_sanitize_file_content_bytes(self):
        """Test file content sanitization with bytes - lines 202-204"""
        s = LogSanitizer()
        data = {"file_content": b"binary data here"}
        result = s.sanitize(data)
        assert "字节" in result["file_content"]
        assert "16" in result["file_content"]

    def test_sanitize_file_content_dict(self):
        """Test file content sanitization with dict - lines 205-209"""
        s = LogSanitizer()
        data = {"file_content": {"type": "cad", "size": "2MB", "format": "step"}}
        result = s.sanitize(data)
        assert "cad" in result["file_content"]
        assert "2MB" in result["file_content"]
        assert "step" in result["file_content"]

    def test_sanitize_file_content_dict_missing_keys(self):
        """Test file content dict with missing keys - lines 206-208"""
        s = LogSanitizer()
        data = {"file_content": {"other_key": "value"}}
        result = s.sanitize(data)
        assert "unknown" in result["file_content"]

    def test_sanitize_file_content_other_type(self):
        """Test file content with other type - line 211"""
        s = LogSanitizer()
        data = {"file_content": 12345}
        result = s.sanitize(data)
        assert result["file_content"] == "[文件内容已脱敏]"

    def test_sanitize_user_input_none(self):
        """Test user input sanitization with None - line 215"""
        s = LogSanitizer()
        data = {"description": None}
        result = s.sanitize(data)
        assert result["description"] is None

    def test_sanitize_user_input_short_string(self):
        """Test user input with short string - line 219"""
        s = LogSanitizer()
        data = {"description": "short"}
        result = s.sanitize(data)
        assert result["description"] == "short"

    def test_sanitize_user_input_non_string(self):
        """Test user input with non-string value - line 220"""
        s = LogSanitizer()
        data = {"description": 12345}
        result = s.sanitize(data)
        assert result["description"] == "12345"

    def test_sanitize_api_key_short_value(self):
        """Test API key sanitization with short value - line 225"""
        s = LogSanitizer()
        data = {"api_key": "ab"}
        result = s.sanitize(data)
        assert result["api_key"] == "[已脱敏]"

    def test_sanitize_api_key_non_string(self):
        """Test API key sanitization with non-string value - line 227"""
        s = LogSanitizer()
        data = {"api_key": 12345}
        result = s.sanitize(data)
        assert result["api_key"] == "[已脱敏]"

    def test_sanitize_api_key_pattern_short_masked_value(self):
        """Test API key pattern with short masked value - line 239"""
        s = LogSanitizer()
        text = "Bearer short"
        result = s._sanitize_string(text)
        assert "[已脱敏]" in result

    def test_sanitize_process_param_pattern_with_unit(self):
        """Test process param pattern sanitization with unit - lines 189-195"""
        s = LogSanitizer()
        text = "切削速度: 1500 rpm"
        result = s._sanitize_string(text)
        assert "[工艺参数已脱敏]" in result
        assert "rpm" in result

    def test_sanitize_multiple_process_params(self):
        """Test multiple process parameters in one string"""
        s = LogSanitizer()
        text = "cutting speed: 2000 m/min, feed rate: 0.5 mm/min"
        result = s._sanitize_string(text)
        assert "[工艺参数已脱敏]" in result
