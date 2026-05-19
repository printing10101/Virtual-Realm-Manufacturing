"""
Bearer Token Authentication Middleware

Implements token-based authentication for all non-public API endpoints.
- Tokens are generated at Tauri app startup
- Tokens are stored in memory and local file (0o600 permissions)
- Health check and metrics endpoints are exempted
"""

from __future__ import annotations
import os
import json
import uuid
import hmac
import logging
import stat
from pathlib import Path
from typing import Optional
from fastapi import Request, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.core.permissions import PermissionLevel, permission_checker

logger = logging.getLogger(__name__)


PUBLIC_ENDPOINTS = {
    "/api/health",
    "/api/health/ping",
    "/api/metrics",
    "/api/v1/auth/register",
    "/api/v1/auth/login",
    "/api/v1/auth/refresh",
    "/api/v1/auth/logout",
    "/api/v1/auth/me",
    "/health",
}

JWT_PUBLIC_PREFIXES = [
    "/api/docs",
    "/api/redoc",
    "/api/openapi",
]


def _get_token_metadata(token: str) -> dict:
    """Get token metadata from token metadata file if exists."""
    meta_file = Path(os.environ.get("LNN_TOKEN_META_FILE", ".lnn_token_meta.json"))
    if not meta_file.exists():
        return {"level": "T"}
    try:
        data = json.loads(meta_file.read_text())
        if isinstance(data, list):
            for entry in data:
                if entry.get("token") == token:
                    return entry
        elif isinstance(data, dict):
            if data.get("token") == token:
                return data
    except Exception:
        pass
    return {"level": "T"}


def generate_token() -> str:
    return str(uuid.uuid4())


def get_token_file_path() -> Path:
    return Path(os.environ.get("LNN_TOKEN_FILE", ".lnn_token"))


def save_token(token: str, file_path: Optional[Path] = None) -> Path:
    if file_path is None:
        file_path = get_token_file_path()

    file_path.write_text(token)

    if os.name != "nt":
        os.chmod(str(file_path), stat.S_IRUSR | stat.S_IWUSR)

    logger.info("Token saved to %s", file_path)
    return file_path


def load_token(file_path: Optional[Path] = None) -> Optional[str]:
    if file_path is None:
        file_path = get_token_file_path()

    if not file_path.exists():
        return None

    try:
        token = file_path.read_text().strip()
        return token if token else None
    except Exception as e:
        logger.error("Failed to load token: %s", e)
        return None


def initialize_token() -> str:
    existing = load_token()
    if existing:
        logger.info("Loaded existing token")
        return existing

    new_token = generate_token()
    save_token(new_token)
    return new_token


class AuthMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, enabled: bool = True, permission_enforced: bool = False):
        super().__init__(app)
        self.enabled = enabled
        self.permission_enforced = permission_enforced
        self._token = None
        if enabled:
            self._token = initialize_token()

    @property
    def token(self) -> Optional[str]:
        return self._token

    async def dispatch(self, request: Request, call_next):
        if not self.enabled:
            return await call_next(request)

        path = request.url.path

        if (
            path in PUBLIC_ENDPOINTS
            or any(path.startswith(prefix) for prefix in JWT_PUBLIC_PREFIXES)
        ):
            return await call_next(request)

        auth_header = request.headers.get("Authorization", "")

        if not auth_header.startswith("Bearer "):
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={
                    "error": "unauthorized",
                    "message": "Missing or invalid Authorization header",
                },
            )

        token = auth_header[7:]

        if not hmac.compare_digest(token, self._token or ""):
            logger.warning(
                "Invalid token attempt from %s",
                request.client.host if request.client else "unknown",
            )
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={
                    "error": "unauthorized",
                    "message": "Invalid authentication token",
                },
            )

        if self.permission_enforced:
            metadata = _get_token_metadata(token)
            token_level_str = metadata.get("level", "T")
            try:
                token_level = PermissionLevel(token_level_str)
            except ValueError:
                token_level = PermissionLevel.T

            if not permission_checker.has_permission(token_level, path, request.method):
                return JSONResponse(
                    status_code=status.HTTP_403_FORBIDDEN,
                    content={
                        "error": "forbidden",
                        "message": f"Insufficient permission: token has {token_level_str} level, endpoint requires {permission_checker.get_required_permission(request.method, path).value} level",
                    },
                )

        return await call_next(request)
