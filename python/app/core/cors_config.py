"""
CORS Configuration Module

Provides environment-aware CORS configuration for the LNN AI service.
- Development: Allows any localhost origin and tauri://localhost
- Production: Only allows tauri://localhost and https://tauri.localhost
- Supports reading allowed origins from environment variable
"""
import os
from typing import Optional


# Allowed origins for each environment
PRODUCTION_ORIGINS = [
    "tauri://localhost",
    "https://tauri.localhost",
]

DEVELOPMENT_PATTERNS = [
    "http://localhost",
    "https://localhost",
    "tauri://localhost",
]


def get_environment() -> str:
    """Get current environment from LINGJING_ENV variable.

    Returns:
        'development' or 'production'. Defaults to 'production' for safety.
    """
    env = os.environ.get("LINGJING_ENV", "production").lower()
    return env if env in ("development", "production") else "production"


def is_allowed_origin(origin: str, override_env: Optional[str] = None) -> bool:
    """Check if an origin is allowed in the current environment.

    Development mode allows any localhost origin (any port).
    Production mode only allows exact matches.

    Args:
        origin: The origin to check (e.g. 'http://localhost:5173')
        override_env: Optional environment override for testing

    Returns:
        True if the origin is allowed
    """
    if not origin:
        return False

    env_override = os.environ.get("ALLOWED_ORIGINS", "")
    if env_override:
        allowed = [o.strip() for o in env_override.split(",") if o.strip()]
        return origin in allowed

    env = override_env or get_environment()

    if env == "development":
        for pattern in DEVELOPMENT_PATTERNS:
            if origin.startswith(pattern):
                return True
        return False

    return origin in PRODUCTION_ORIGINS


def get_cors_origins(override_env: Optional[str] = None) -> list[str]:
    """Get explicit CORS origins list.

    Note: For development, this returns common dev ports as fallback.
    The actual origin matching in main.py uses is_allowed_origin() for pattern support.

    Args:
        override_env: Optional environment override for testing

    Returns:
        List of allowed CORS origins
    """
    env_override = os.environ.get("ALLOWED_ORIGINS", "")
    if env_override:
        return [origin.strip() for origin in env_override.split(",") if origin.strip()]

    env = override_env or get_environment()

    if env == "development":
        return [
            "http://localhost:3000",
            "http://localhost:5173",
            "http://localhost:8080",
            "http://localhost:8765",
            "https://localhost:3000",
            "https://localhost:5173",
            "tauri://localhost",
        ]

    return list(PRODUCTION_ORIGINS)


def get_cors_config(override_env: Optional[str] = None) -> dict:
    """Get CORS configuration for FastAPI middleware.

    Returns origins list, but actual filtering is done by custom middleware
    to support pattern matching in development mode.

    Args:
        override_env: Optional environment override for testing

    Returns:
        Dictionary with CORS middleware configuration
    """
    origins = get_cors_origins(override_env)
    env = override_env or get_environment()

    return {
        "allow_origins": origins,
        "allow_credentials": True,
        "allow_methods": ["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
        "allow_headers": ["*"],
        "expose_headers": ["X-Content-Type-Options", "X-Frame-Options", "X-XSS-Protection"],
        "max_age": 600 if env == "production" else 3600,
    }


def get_security_headers() -> dict[str, str]:
    """Get security headers to add to all responses.

    Returns:
        Dictionary of security headers
    """
    return {
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "X-XSS-Protection": "1; mode=block",
    }


def is_development() -> bool:
    """Check if current environment is development."""
    return get_environment() == "development"


def is_production() -> bool:
    """Check if current environment is production."""
    return get_environment() == "production"
