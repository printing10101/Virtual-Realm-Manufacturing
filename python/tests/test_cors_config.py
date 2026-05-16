"""
Test CORS Configuration Module

Tests for:
- Development environment: wildcard "*" origin with no regex
- Production environment: "http://localhost:*" origins with regex matching
- Environment variable override via ALLOWED_ORIGINS
- Default values and error handling for invalid LINGJING_ENV values
"""

import os
import pytest
from unittest.mock import patch

from app.core.cors_config import (
    CorsSettings,
    get_environment,
    get_cors_origins,
    get_cors_origin_regex,
    get_cors_config,
    is_allowed_origin,
    is_development,
    is_production,
    PRODUCTION_ORIGIN_REGEX,
    PRODUCTION_ORIGINS,
)


class TestDevEnvironment:
    """Tests for CORS behavior in development environment."""

    @patch.dict(os.environ, {"LINGJING_ENV": "development"}, clear=True)
    def test_dev_origins_are_wildcard(self):
        settings = CorsSettings()
        assert settings.get_origins() == ["*"]

    @patch.dict(os.environ, {"LINGJING_ENV": "development"}, clear=True)
    def test_dev_origin_regex_is_none(self):
        settings = CorsSettings()
        assert settings.get_origin_regex() is None

    @patch.dict(os.environ, {"LINGJING_ENV": "development"}, clear=True)
    def test_dev_allows_any_origin(self):
        settings = CorsSettings()
        assert settings.is_allowed_origin("http://localhost:5173") is True
        assert settings.is_allowed_origin("https://example.com") is True
        assert settings.is_allowed_origin("http://localhost:3000") is True
        assert settings.is_allowed_origin("https://evil.com") is True

    @patch.dict(os.environ, {"LINGJING_ENV": "development"}, clear=True)
    def test_dev_environment_detection(self):
        assert get_environment() == "development"
        assert is_development() is True
        assert is_production() is False

    @patch.dict(os.environ, {"LINGJING_ENV": "development"}, clear=True)
    def test_dev_get_cors_origins_func(self):
        assert get_cors_origins() == ["*"]

    @patch.dict(os.environ, {"LINGJING_ENV": "development"}, clear=True)
    def test_dev_get_cors_origin_regex_func(self):
        assert get_cors_origin_regex() is None

    @patch.dict(os.environ, {"LINGJING_ENV": "development"}, clear=True)
    def test_dev_get_cors_config(self):
        config = get_cors_config()
        assert config["allow_origins"] == ["*"]
        assert config["allow_origin_regex"] is None
        assert config["allow_credentials"] is True
        assert config["max_age"] == 3600


class TestProdEnvironment:
    """Tests for CORS behavior in production environment."""

    @patch.dict(os.environ, {"LINGJING_ENV": "production"}, clear=True)
    def test_prod_origins_are_localhost_wildcard_str(self):
        settings = CorsSettings()
        assert settings.get_origins() == ["http://localhost:*"]

    @patch.dict(os.environ, {"LINGJING_ENV": "production"}, clear=True)
    def test_prod_origin_regex_matches_localhost_ports(self):
        settings = CorsSettings()
        regex = settings.get_origin_regex()
        assert regex == PRODUCTION_ORIGIN_REGEX

    @patch.dict(os.environ, {"LINGJING_ENV": "production"}, clear=True)
    def test_prod_allows_localhost_with_port(self):
        settings = CorsSettings()
        assert settings.is_allowed_origin("http://localhost:5173") is True
        assert settings.is_allowed_origin("http://localhost:8080") is True
        assert settings.is_allowed_origin("http://localhost:3000") is True

    @patch.dict(os.environ, {"LINGJING_ENV": "production"}, clear=True)
    def test_prod_allows_localhost_without_port(self):
        settings = CorsSettings()
        assert settings.is_allowed_origin("http://localhost") is True

    @patch.dict(os.environ, {"LINGJING_ENV": "production"}, clear=True)
    def test_prod_blocks_https_localhost(self):
        settings = CorsSettings()
        assert settings.is_allowed_origin("https://localhost:5173") is False

    @patch.dict(os.environ, {"LINGJING_ENV": "production"}, clear=True)
    def test_prod_blocks_external_origins(self):
        settings = CorsSettings()
        assert settings.is_allowed_origin("https://example.com") is False
        assert settings.is_allowed_origin("https://evil.com") is False
        assert settings.is_allowed_origin("http://127.0.0.1:8080") is False

    @patch.dict(os.environ, {"LINGJING_ENV": "production"}, clear=True)
    def test_prod_blocks_tauri_direct(self):
        settings = CorsSettings()
        assert settings.is_allowed_origin("tauri://localhost") is False

    @patch.dict(os.environ, {"LINGJING_ENV": "production"}, clear=True)
    def test_prod_environment_detection(self):
        assert get_environment() == "production"
        assert is_production() is True
        assert is_development() is False

    @patch.dict(os.environ, {"LINGJING_ENV": "production"}, clear=True)
    def test_prod_get_cors_origins_func(self):
        assert get_cors_origins() == ["http://localhost:*"]

    @patch.dict(os.environ, {"LINGJING_ENV": "production"}, clear=True)
    def test_prod_get_cors_origin_regex_func(self):
        assert get_cors_origin_regex() == PRODUCTION_ORIGIN_REGEX

    @patch.dict(os.environ, {"LINGJING_ENV": "production"}, clear=True)
    def test_prod_get_cors_config(self):
        config = get_cors_config()
        assert config["allow_origins"] == ["http://localhost:*"]
        assert config["allow_origin_regex"] == PRODUCTION_ORIGIN_REGEX
        assert config["allow_credentials"] is True
        assert config["max_age"] == 600


class TestEnvOverride:
    """Tests for ALLOWED_ORIGINS environment variable override."""

    @patch.dict(
        os.environ,
        {
            "LINGJING_ENV": "production",
            "ALLOWED_ORIGINS": "http://custom.local,https://custom.local",
        },
        clear=True,
    )
    def test_override_origins_in_production(self):
        settings = CorsSettings()
        assert settings.get_origins() == ["http://custom.local", "https://custom.local"]
        assert settings.get_origin_regex() is None

    @patch.dict(
        os.environ,
        {"LINGJING_ENV": "development", "ALLOWED_ORIGINS": "http://custom.local"},
        clear=True,
    )
    def test_override_origins_in_development(self):
        settings = CorsSettings()
        assert settings.get_origins() == ["http://custom.local"]
        assert settings.get_origin_regex() is None

    @patch.dict(
        os.environ,
        {"ALLOWED_ORIGINS": "http://custom.local,https://custom.local"},
        clear=True,
    )
    def test_override_is_allowed_origin(self):
        settings = CorsSettings()
        assert settings.is_allowed_origin("http://custom.local") is True
        assert settings.is_allowed_origin("https://custom.local") is True
        assert settings.is_allowed_origin("https://evil.com") is False

    @patch.dict(
        os.environ,
        {"ALLOWED_ORIGINS": "http://custom.local, https://custom.local"},
        clear=True,
    )
    def test_override_handles_whitespace(self):
        settings = CorsSettings()
        assert settings.get_origins() == ["http://custom.local", "https://custom.local"]


class TestDefaultFallback:
    """Tests for default behavior when LINGJING_ENV is not set."""

    @patch.dict(os.environ, {}, clear=True)
    def test_default_is_production(self):
        assert get_environment() == "production"
        assert is_production() is True

    @patch.dict(os.environ, {}, clear=True)
    def test_default_settings_are_production(self):
        settings = CorsSettings()
        assert settings.get_origins() == PRODUCTION_ORIGINS
        assert settings.get_origin_regex() == PRODUCTION_ORIGIN_REGEX

    @patch.dict(os.environ, {"LINGJING_ENV": "staging"}, clear=True)
    def test_invalid_env_falls_back_to_production(self):
        assert get_environment() == "production"
        settings = CorsSettings()
        assert settings.get_origins() == PRODUCTION_ORIGINS

    @patch.dict(os.environ, {"LINGJING_ENV": ""}, clear=True)
    def test_empty_env_falls_back_to_production(self):
        settings = CorsSettings()
        assert settings.get_origins() == PRODUCTION_ORIGINS


class TestOverrideEnvParam:
    """Tests for override_env parameter in helper functions."""

    def test_get_cors_origins_with_override(self):
        assert get_cors_origins(override_env="development") == ["*"]
        assert get_cors_origins(override_env="production") == ["http://localhost:*"]

    def test_get_cors_origin_regex_with_override(self):
        assert get_cors_origin_regex(override_env="development") is None
        assert (
            get_cors_origin_regex(override_env="production") == PRODUCTION_ORIGIN_REGEX
        )

    def test_is_allowed_origin_with_override(self):
        assert is_allowed_origin("https://evil.com", override_env="development") is True
        assert (
            is_allowed_origin("http://localhost:5173", override_env="production")
            is True
        )
        assert is_allowed_origin("https://evil.com", override_env="production") is False


class TestSecurityHeaders:
    """Tests for security headers helper."""

    def test_get_security_headers(self):
        from app.core.cors_config import get_security_headers

        headers = get_security_headers()
        assert headers["X-Content-Type-Options"] == "nosniff"
        assert headers["X-Frame-Options"] == "DENY"
        assert headers["X-XSS-Protection"] == "1; mode=block"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
