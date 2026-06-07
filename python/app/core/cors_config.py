"""
CORS Configuration Module

Provides environment-aware CORS configuration for the LNN AI service.
- Development: Uses explicit localhost origins (no wildcards)
- Production: Strictly limits allowed origins via regex pattern matching

Environment detection is driven by LINGJING_ENV environment variable.
Allowed values: "development" | "production" (default: "production")

Security notes:
    Using allow_origins=["*"] together with allow_credentials=True is a known
    CORS security risk. It allows any origin to make credentialed requests,
    enabling cross-origin attacks and potential sensitive data exposure.
    This module enforces startup validation to prevent such dangerous
    configurations from being deployed.
"""

from __future__ import annotations

import logging
import os
import re
from typing import List, Optional

logger = logging.getLogger(__name__)


class CorsConfigError(Exception):
    """Raised when CORS configuration is invalid or insecure."""


# ---------------------------------------------------------------------------
# Production environment
# ---------------------------------------------------------------------------
# Only localhost origins are allowed in production, matched via regex.
# The origins list is intentionally empty — all validation is delegated to
# the regex pattern for clarity and maintainability.
PRODUCTION_ORIGINS: List[str] = []

# Matches http://localhost with an optional port number (e.g. :5173, :8080).
# The protocol must be exactly "http" — HTTPS is not used for localhost
# communication with the Tauri frontend. Explicit port matching prevents
# open-redirect-style bypasses.
PRODUCTION_ORIGIN_REGEX = r"http://localhost(:\d+)?"


# ---------------------------------------------------------------------------
# Development environment
# ---------------------------------------------------------------------------
# Explicitly list every origin that should be allowed.  Wildcards ("*")
# MUST NOT be used here because allow_credentials is always True — the
# combination is a CORS security violation (see module docstring).
#
# Common frontend development server ports:
#   3000  – Create React App / Next.js (default)
#   5173  – Vite (default)
#   8080  – Webpack dev server / common backend proxy
DEVELOPMENT_ORIGINS = [
    "http://localhost:3000",
    "http://localhost:5173",
    "http://localhost:8080",
]

# No regex needed in development — every allowed origin is enumerated above.
DEVELOPMENT_ORIGIN_REGEX: Optional[str] = None


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate_cors_config(
    allow_origins: Optional[List[str]],
    allow_credentials: bool,
) -> None:
    """Validate CORS configuration for security issues.

    Checks for the dangerous combination of ``allow_origins`` containing ``"*"``
    and ``allow_credentials`` being ``True``.  This combination violates the CORS
    specification and opens the application to cross-origin attacks.

    Args:
        allow_origins: List of allowed origins (may be ``None`` or empty).
        allow_credentials: Whether credentials are allowed in CORS requests.

    Raises:
        CorsConfigError: If ``"*"`` is present in ``allow_origins`` while
            ``allow_credentials`` is ``True``.
    """
    if allow_origins and "*" in allow_origins and allow_credentials:
        logger.error(
            "SECURITY RISK: CORS configuration contains wildcard '*' in "
            "allow_origins with allow_credentials=True.  This violates CORS "
            "security best practices and may expose sensitive data to any "
            "origin.  Application startup aborted."
        )
        raise CorsConfigError(
            "Insecure CORS configuration: cannot use wildcard '*' origins "
            "with allow_credentials=True.  Specify explicit origins instead."
        )


# ---------------------------------------------------------------------------
# Settings class
# ---------------------------------------------------------------------------

class CorsSettings:
    """Environment-aware CORS settings.

    Provides CORS configuration based on the current environment.
    Automatically validates configuration for security issues on initialization.

    Attributes:
        allow_credentials: Whether to allow credentials (cookies, auth headers)
            in CORS requests.  Always ``True`` for this application.
        max_age: Maximum time (in seconds) that the CORS preflight response
            can be cached by the client.
    """

    def __init__(self) -> None:
        # --- Environment detection ---
        self._env = os.environ.get("LINGJING_ENV", "production").lower()
        if self._env not in ("development", "production"):
            self._env = "production"

        # --- Origin resolution ---
        # ALLOWED_ORIGINS env var takes the highest priority.
        env_override = os.environ.get("ALLOWED_ORIGINS", "")
        if env_override:
            self._origins = [
                o.strip() for o in env_override.split(",") if o.strip()
            ]
            self._origin_regex = None
        elif self._env == "development":
            self._origins = list(DEVELOPMENT_ORIGINS)
            self._origin_regex = DEVELOPMENT_ORIGIN_REGEX
        else:
            self._origins = list(PRODUCTION_ORIGINS)
            self._origin_regex = PRODUCTION_ORIGIN_REGEX

        # --- CORS flags ---
        self.allow_credentials = True
        self.max_age = 3600 if self._env == "development" else 600

        # --- Startup validation ---
        validate_cors_config(self._origins, self.allow_credentials)

    # -- Public accessors ---------------------------------------------------

    def get_origins(self) -> List[str]:
        """Return the list of explicitly allowed origins."""
        return self._origins

    def get_origin_regex(self) -> Optional[str]:
        """Return the origin regex pattern, or ``None``."""
        return self._origin_regex

    def get_methods(self) -> List[str]:
        """Return allowed HTTP methods for CORS."""
        return ["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"]

    def get_headers(self) -> List[str]:
        """Return allowed request headers for CORS."""
        return ["*"]

    def get_expose_headers(self) -> List[str]:
        """Return response headers exposed to the client."""
        return [
            "X-Content-Type-Options",
            "X-Frame-Options",
            "X-XSS-Protection",
        ]

    def is_allowed_origin(self, origin: str) -> bool:
        """Check whether *origin* is permitted by the current configuration.

        Args:
            origin: The Origin header value from the incoming request.

        Returns:
            ``True`` if the origin is allowed, ``False`` otherwise.
        """
        if not origin:
            return False

        # ALLOWED_ORIGINS env var override
        env_override = os.environ.get("ALLOWED_ORIGINS", "")
        if env_override:
            allowed = [o.strip() for o in env_override.split(",") if o.strip()]
            return origin in allowed

        # Exact match
        if origin in self._origins:
            return True

        # Regex match
        if self._origin_regex and re.match(self._origin_regex, origin):
            return True

        return False


# Module-level singleton – imported by ``main.py``.
cors_settings = CorsSettings()


# ---------------------------------------------------------------------------
# Standalone helper functions
# ---------------------------------------------------------------------------

def get_environment() -> str:
    """Return the current environment name (``"development"`` or ``"production"``).

    Falls back to ``"production"`` when ``LINGJING_ENV`` is unset or invalid.
    """
    env = os.environ.get("LINGJING_ENV", "production").lower()
    return env if env in ("development", "production") else "production"


def is_allowed_origin(origin: str, override_env: Optional[str] = None) -> bool:
    """Standalone check whether *origin* is allowed.

    Args:
        origin: The Origin header value.
        override_env: If provided, check as if this environment were active.

    Returns:
        ``True`` if the origin is allowed, ``False`` otherwise.
    """
    if not origin:
        return False

    env = override_env or get_environment()

    # ALLOWED_ORIGINS env var override
    env_override = os.environ.get("ALLOWED_ORIGINS", "")
    if env_override:
        allowed = [o.strip() for o in env_override.split(",") if o.strip()]
        return origin in allowed

    # Resolve origins/regex for the target environment
    if env == "development":
        origins = DEVELOPMENT_ORIGINS
        origin_regex = DEVELOPMENT_ORIGIN_REGEX
    else:
        origins = PRODUCTION_ORIGINS
        origin_regex = PRODUCTION_ORIGIN_REGEX

    if origin in origins:
        return True
    if origin_regex and re.match(origin_regex, origin):
        return True
    return False


def get_cors_origins(override_env: Optional[str] = None) -> list[str]:
    """Return the allowed origin list for the given (or current) environment.

    When ``ALLOWED_ORIGINS`` env var is set it takes precedence over
    the per-environment constants.
    """
    env_override = os.environ.get("ALLOWED_ORIGINS", "")
    if env_override:
        return [
            origin.strip()
            for origin in env_override.split(",")
            if origin.strip()
        ]

    env = override_env or get_environment()
    if env == "development":
        return list(DEVELOPMENT_ORIGINS)
    return list(PRODUCTION_ORIGINS)


def get_cors_origin_regex(override_env: Optional[str] = None) -> Optional[str]:
    """Return the origin regex for the given (or current) environment.

    Returns ``None`` when ``ALLOWED_ORIGINS`` env var is set or when
    the environment does not use a regex pattern.
    """
    env_override = os.environ.get("ALLOWED_ORIGINS", "")
    if env_override:
        return None

    env = override_env or get_environment()
    if env == "development":
        return DEVELOPMENT_ORIGIN_REGEX
    return PRODUCTION_ORIGIN_REGEX


def get_cors_config(override_env: Optional[str] = None) -> dict:
    """Return a complete CORS configuration dictionary.

    The returned dict can be unpacked directly into
    ``CORSMiddleware(**get_cors_config())``.

    Args:
        override_env: If provided, generate config for this environment.
    """
    origins = get_cors_origins(override_env)
    origin_regex = get_cors_origin_regex(override_env)
    env = override_env or get_environment()

    return {
        "allow_origins": origins,
        "allow_origin_regex": origin_regex,
        "allow_credentials": True,
        "allow_methods": ["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
        "allow_headers": ["*"],
        "expose_headers": [
            "X-Content-Type-Options",
            "X-Frame-Options",
            "X-XSS-Protection",
        ],
        "max_age": 600 if env == "production" else 3600,
    }


def get_security_headers() -> dict[str, str]:
    """Return a dict of recommended security response headers."""
    return {
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "X-XSS-Protection": "1; mode=block",
    }


def is_development() -> bool:
    """Return ``True`` when the current environment is ``"development"``."""
    return get_environment() == "development"


def is_production() -> bool:
    """Return ``True`` when the current environment is ``"production"``."""
    return get_environment() == "production"
