"""Pure ASGI Unified Authentication Middleware.

Merges AuthMiddleware, JwtAuthMiddleware, and AgentAuthMiddleware into a
single ASGI middleware that performs early path detection to short-circuit
public paths and only runs auth logic for protected endpoints.

All three token types are supported:
  1. LNN flat token  (Bearer lj_... or any UUID-style token)
  2. JWT access token (Bearer eyJ...)
  3. Agent token     (Bearer lj_agent_...)

Public paths (docs, health, auth endpoints, metrics) are detected at the
ASGI layer and pass through without any auth processing, significantly
reducing latency for those routes.
"""

from __future__ import annotations

import hmac
import json
import logging
import os
import stat
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Optional

from starlette.types import ASGIApp, Receive, Scope, Send

logger = logging.getLogger(__name__)


# ============================================================
# Public path definitions (merged from all three middlewares)
# ============================================================

PUBLIC_PATHS: set[str] = {
    "/api/health",
    "/api/health/ping",
    "/api/metrics",
    "/api/v1/auth/register",
    "/api/v1/auth/login",
    "/api/v1/auth/refresh",
    "/api/v1/auth/logout",
    "/api/v1/auth/me",
    "/health",
    "/api/openapi.json",
    "/api/docs",
    "/api/redoc",
}

PUBLIC_PREFIXES: list[str] = [
    "/api/docs",
    "/api/redoc",
    "/api/openapi",
    "/api/openapi.json",
]


def _is_public_path(path: str) -> bool:
    """Check if the path is a public (non-authenticated) path."""
    if path in PUBLIC_PATHS:
        return True
    return any(path.startswith(p) for p in PUBLIC_PREFIXES)


# ============================================================
# LNN Token Auth (from AuthMiddleware)
# ============================================================

_PUBLIC_ENDPOINTS_LNN = {
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

_JWT_PUBLIC_PREFIXES = [
    "/api/docs",
    "/api/redoc",
    "/api/openapi",
]


def _get_token_metadata(token: str) -> dict:
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


def _generate_token() -> str:
    return str(uuid.uuid4())


def _get_token_file_path() -> Path:
    return Path(os.environ.get("LNN_TOKEN_FILE", ".lnn_token"))


def _save_token(token: str, file_path: Optional[Path] = None) -> Path:
    if file_path is None:
        file_path = _get_token_file_path()
    file_path.write_text(token)
    if os.name != "nt":
        os.chmod(str(file_path), stat.S_IRUSR | stat.S_IWUSR)
    logger.info("Token saved to %s", file_path)
    return file_path


def _load_token(file_path: Optional[Path] = None) -> Optional[str]:
    if file_path is None:
        file_path = _get_token_file_path()
    if not file_path.exists():
        return None
    try:
        token = file_path.read_text().strip()
        return token if token else None
    except Exception as e:
        logger.error("Failed to load token: %s", e)
        return None


def _initialize_token() -> str:
    existing = _load_token()
    if existing:
        logger.info("Loaded existing token")
        return existing
    new_token = _generate_token()
    _save_token(new_token)
    return new_token


# ============================================================
# JWT Auth (from JwtAuthMiddleware)
# ============================================================

AUTH_PUBLIC_PATHS = {
    "/api/v1/auth/register",
    "/api/v1/auth/login",
    "/api/v1/auth/refresh",
    "/api/health",
    "/api/health/ping",
    "/api/metrics",
    "/api/docs",
    "/api/redoc",
    "/api/openapi.json",
    "/health",
}

AUTH_PUBLIC_PREFIXES = [
    "/api/docs",
    "/api/redoc",
    "/api/openapi",
]


def _decode_token(token: str) -> Optional[dict]:
    """Decode a JWT token (from security module)."""
    try:
        from app.core.security import decode_token
        return decode_token(token)
    except Exception:
        return None


def _decode_token_strict(token: str, expected_type: str = "access") -> Optional[dict]:
    """Strictly decode a JWT token (from security module)."""
    try:
        from app.core.security import decode_token_strict
        return decode_token_strict(token, expected_type)
    except Exception:
        return None


def _get_token_ban_list():
    """Get token ban list (from security module)."""
    try:
        from app.core.security import get_token_ban_list
        return get_token_ban_list()
    except Exception:
        return None


# ============================================================
# Agent Auth (from AgentAuthMiddleware)
# ============================================================

class PermissionLevel(str, Enum):
    R = "R"
    W = "W"
    B = "B"
    N = "N"
    C = "C"
    T = "T"


PERMISSION_HIERARCHY = {
    PermissionLevel.R: 0,
    PermissionLevel.W: 1,
    PermissionLevel.B: 2,
    PermissionLevel.N: 3,
    PermissionLevel.C: 4,
    PermissionLevel.T: 5,
}


AGENT_ENDPOINT_PERMISSIONS: dict[str, PermissionLevel] = {
    "GET /api/agent/v1/health": PermissionLevel.R,
    "GET /api/agent/v1/models": PermissionLevel.R,
    "GET /api/agent/v1/models/{name}/info": PermissionLevel.R,
    "POST /api/agent/v1/predict": PermissionLevel.R,
    "POST /api/agent/v1/train": PermissionLevel.B,
    "GET /api/agent/v1/train/{job_id}": PermissionLevel.R,
    "GET /api/agent/v1/train/{job_id}/stream": PermissionLevel.R,
    "POST /api/agent/v1/execute": PermissionLevel.T,
    "GET /api/agent/v1/audit-log": PermissionLevel.C,
}

WRITE_SCOPES = {"W", "B", "T"}


def _get_permission_class(method: str, path: str) -> PermissionLevel:
    """Determine the permission class for a given endpoint."""
    key = f"{method} {path}"
    if key in AGENT_ENDPOINT_PERMISSIONS:
        return AGENT_ENDPOINT_PERMISSIONS[key]
    defaults = {
        "GET": PermissionLevel.R,
        "POST": PermissionLevel.W,
        "PUT": PermissionLevel.W,
        "DELETE": PermissionLevel.C,
    }
    return defaults.get(method, PermissionLevel.R)


def _check_scope(token_scopes: list[str], required: PermissionLevel) -> bool:
    """Check if token has the required scope."""
    if required.value in token_scopes:
        return True
    hierarchy = PERMISSION_HIERARCHY
    token_max = max((hierarchy.get(s, 0) for s in token_scopes), default=0)
    required_value = hierarchy.get(required.value, 0)
    return token_max >= required_value


def _get_agent_token_store():
    """Get agent token store singleton."""
    from app.agent.auth import agent_token_store
    return agent_token_store


@dataclass
class AgentAuditEntry:
    timestamp_ms: int
    agent_id: str
    route: str
    permission_class: str
    status_code: int
    latency_ms: float


class AgentAuditLog:
    """JSONL-based audit log for Agent requests."""

    def __init__(self, log_path: str | None = None):
        if log_path is None:
            log_path = str(Path.home() / ".lingjing" / "agent_audit.log")
        self._log_path = Path(log_path)
        self._log_path.parent.mkdir(parents=True, exist_ok=True)

    def log(
        self,
        agent_id: str,
        route: str,
        permission_class: str,
        status_code: int,
        latency_ms: float,
    ):
        entry = AgentAuditEntry(
            timestamp_ms=int(time.time() * 1000),
            agent_id=agent_id,
            route=route,
            permission_class=permission_class,
            status_code=status_code,
            latency_ms=round(latency_ms, 2),
        )
        self._log_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(str(self._log_path), "a", encoding="utf-8") as f:
                f.write(json.dumps(entry.__dict__) + "\n")
        except (OSError, IOError):
            pass

    def get_entries(
        self,
        agent_id: str | None = None,
        permission_class: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict]:
        entries = []
        if self._log_path.exists():
            with self._log_path.open("r") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        e = json.loads(line)
                        if agent_id and e.get("agent_id") != agent_id:
                            continue
                        if (
                            permission_class
                            and e.get("permission_class") != permission_class
                        ):
                            continue
                        entries.append(e)
                    except json.JSONDecodeError:
                        continue
        entries.reverse()
        return entries[offset : offset + limit]


class AgentRateLimiter:
    """Per-token rate limiter: max requests per minute and max concurrent tasks."""

    def __init__(
        self,
        max_requests_per_minute: int = 60,
        max_concurrent_tasks: int = 3,
    ):
        self._max_rpm = max_requests_per_minute
        self._max_concurrent = max_concurrent_tasks
        self._request_log: dict[str, list[float]] = defaultdict(list)
        self._active_tasks: dict[str, int] = defaultdict(int)

    def check_rate_limit(self, agent_id: str) -> bool:
        now = time.time()
        cutoff = now - 60
        self._request_log[agent_id] = [
            t for t in self._request_log[agent_id] if t > cutoff
        ]
        if len(self._request_log[agent_id]) >= self._max_rpm:
            return False
        self._request_log[agent_id].append(now)
        return True

    def acquire_task(self, agent_id: str) -> bool:
        if self._active_tasks.get(agent_id, 0) >= self._max_concurrent:
            return False
        self._active_tasks[agent_id] += 1
        return True

    def release_task(self, agent_id: str):
        self._active_tasks[agent_id] = max(0, self._active_tasks.get(agent_id, 0) - 1)

    def get_active_tasks(self, agent_id: str) -> int:
        return self._active_tasks.get(agent_id, 0)


class IdempotencyStore:
    """Store idempotency keys for W/B/T requests."""

    def __init__(self):
        self._keys: dict[str, dict] = {}

    def check_and_set(self, key: str, agent_id: str) -> Optional[dict]:
        """Returns cached result if key exists, None if new."""
        self.cleanup()
        if key in self._keys:
            entry = self._keys[key]
            if entry["agent_id"] == agent_id:
                return entry.get("result")
        return None

    def store(self, key: str, agent_id: str, result: dict):
        self._keys[key] = {
            "agent_id": agent_id,
            "result": result,
            "created_at": time.time(),
        }

    def cleanup(self, max_age: int = 3600):
        now = time.time()
        expired = [k for k, v in self._keys.items() if now - v["created_at"] > max_age]
        for k in expired:
            del self._keys[k]


# Singletons
agent_audit_log = AgentAuditLog()
agent_rate_limiter = AgentRateLimiter()
idempotency_store = IdempotencyStore()


# ============================================================
# Permission class mapping for Agent API endpoints
# ============================================================


# ============================================================
# Unified ASGI Middleware
# ============================================================


def _make_json_response(
    status_code: int,
    body: dict,
) -> tuple[int, list[tuple[bytes, bytes]], bytes]:
    """Build an ASGI response tuple (status, headers, body)."""
    body_bytes = json.dumps(body, ensure_ascii=False).encode("utf-8")
    headers = [
        (b"content-type", b"application/json; charset=utf-8"),
        (b"content-length", str(len(body_bytes)).encode("latin-1")),
        (b"x-content-type-options", b"nosniff"),
    ]
    return status_code, headers, body_bytes


async def _send_json_response(
    send: Send,
    status_code: int,
    body: dict,
) -> None:
    """Send an immediate JSON response."""
    sc, headers, body_bytes = _make_json_response(status_code, body)
    await send(
        {
            "type": "http.response.start",
            "status": sc,
            "headers": headers,
        }
    )
    await send(
        {
            "type": "http.response.body",
            "body": body_bytes,
        }
    )


class UnifiedAuthMiddleware:
    """Pure ASGI unified authentication middleware.

    Merges AuthMiddleware, JwtAuthMiddleware, and AgentAuthMiddleware
    into a single middleware that:

    1. Detects public paths early and skips all auth logic
    2. Supports three token types: LNN flat token, JWT, and Agent token
    3. Does NOT buffer the full request or response body
    4. Works correctly with SSE streaming
    """

    def __init__(
        self,
        app: ASGIApp,
        lnn_auth_enabled: bool = True,
        lnn_permission_enforced: bool = False,
        jwt_auth_enabled: bool = True,
        agent_auth_enabled: bool = True,
    ) -> None:
        self.app = app
        self.lnn_auth_enabled = lnn_auth_enabled
        self.lnn_permission_enforced = lnn_permission_enforced
        self.jwt_auth_enabled = jwt_auth_enabled
        self.agent_auth_enabled = agent_auth_enabled

        # LNN token singleton
        self._lnn_token: Optional[str] = None
        if lnn_auth_enabled:
            self._lnn_token = _initialize_token()

    def _is_public_path(self, path: str) -> bool:
        return _is_public_path(path)

    def _is_agent_path(self, path: str) -> bool:
        return path.startswith("/api/agent/v1/")

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        method = scope.get("method", "GET")
        path = scope.get("path", "")

        # ================================================================
        # Early public path detection - fast path, no auth processing
        # ================================================================
        if self._is_public_path(path):
            await self.app(scope, receive, send)
            return

        # ================================================================
        # Extract Authorization header and all headers
        # ================================================================
        raw_headers = scope.get("headers", [])
        auth_header = ""
        for key, value in raw_headers:
            if key.lower() == b"authorization":
                auth_header = value.decode("utf-8", errors="ignore")
                break

        # ================================================================
        # Agent API path - use agent token authentication
        # ================================================================
        if self._is_agent_path(path) and self.agent_auth_enabled:
            # Health check and token creation exempt
            if path == "/api/agent/v1/health":
                await self.app(scope, receive, send)
                return
            if path == "/api/agent/v1/tokens" and method == "POST":
                await self.app(scope, receive, send)
                return

            start = time.perf_counter()
            auth_result = await self._check_agent_auth(
                method, path, auth_header, start, raw_headers
            )
            if auth_result is not None:
                await auth_result(send)
                return

            # Store agent info in scope for downstream use
            scope["state"] = scope.get("state", {})
            await self.app(scope, receive, send)
            return

        # ================================================================
        # Regular API path - unified LNN + JWT auth
        # Strategy: detect token type and route to the appropriate handler.
        #   - JWT tokens start with "eyJ" -> try JWT first
        #   - Flat LNN tokens -> try LNN first, fallback to JWT
        # Either one passing is sufficient.
        # ================================================================
        token = auth_header[7:] if auth_header.startswith("Bearer ") else ""

        if token:
            if token.startswith("eyJ"):
                # JWT token path
                if self.jwt_auth_enabled:
                    jwt_result = await self._check_jwt_auth(method, path, auth_header, token)
                    if jwt_result is not None:
                        await jwt_result(send)
                        return
                elif self.lnn_auth_enabled:
                    # JWT disabled but LNN enabled, reject
                    await _send_json_response(
                        send,
                        401,
                        {
                            "error": "unauthorized",
                            "message": "JWT authentication is disabled",
                        },
                    )
                    return
            else:
                # Flat LNN token path - try LNN first, then JWT fallback
                if self.lnn_auth_enabled:
                    lnn_result = await self._check_lnn_auth(method, path, auth_header, token)
                    if lnn_result is None:
                        # LNN auth passed
                        pass
                    else:
                        # LNN auth failed, try JWT as fallback
                        if self.jwt_auth_enabled:
                            jwt_result = await self._check_jwt_auth(method, path, auth_header, token)
                            if jwt_result is None:
                                # JWT auth passed
                                pass
                            else:
                                # JWT also failed
                                await jwt_result(send)
                                return
                        else:
                            # LNN failed and JWT not enabled
                            await lnn_result(send)
                            return
                elif self.jwt_auth_enabled:
                    # Only JWT enabled, try it for flat tokens too
                    jwt_result = await self._check_jwt_auth(method, path, auth_header, token)
                    if jwt_result is not None:
                        await jwt_result(send)
                        return
                else:
                    # Neither auth enabled
                    pass
        else:
            # No auth header at all
            if self.lnn_auth_enabled or self.jwt_auth_enabled:
                await _send_json_response(
                    send,
                    401,
                    {
                        "error": "unauthorized",
                        "message": "Missing or invalid Authorization header",
                    },
                )
                return

        # ================================================================
        # Auth passed - forward to app
        # ================================================================
        await self.app(scope, receive, send)

    async def _check_lnn_auth(
        self, method: str, path: str, auth_header: str, token: str
    ):
        """Check LNN flat token authentication.

        Returns None if auth passes or is disabled, or a callable that sends
        the error response if auth fails.
        """
        if not self.lnn_auth_enabled:
            return None

        # Check if this path is LNN-public
        if path in _PUBLIC_ENDPOINTS_LNN:
            return None
        if any(path.startswith(p) for p in _JWT_PUBLIC_PREFIXES):
            return None

        if not auth_header.startswith("Bearer "):
            return lambda send: _send_json_response(
                send,
                401,
                {
                    "error": "unauthorized",
                    "message": "Missing or invalid Authorization header",
                },
            )

        if not hmac.compare_digest(token, self._lnn_token or ""):
            # Token doesn't match LNN flat token.
            # Only log a warning if the token looks like a flat token (not JWT).
            if not token.startswith("eyJ"):
                logger.warning(
                    "Invalid LNN token attempt from path %s", path
                )
            return lambda send: _send_json_response(
                send,
                401,
                {
                    "error": "unauthorized",
                    "message": "Invalid authentication token",
                },
            )

        if self.lnn_permission_enforced:
            from app.core.permissions import (
                permission_checker,
                PermissionLevel as PL,
            )

            metadata = _get_token_metadata(token)
            token_level_str = metadata.get("level", "T")
            try:
                token_level = PL(token_level_str)
            except ValueError:
                token_level = PL.T

            if not permission_checker.has_permission(token_level, path, method):
                return lambda send: _send_json_response(
                    send,
                    403,
                    {
                        "error": "forbidden",
                        "message": f"Insufficient permission: token has {token_level_str} level, endpoint requires {permission_checker.get_required_permission(method, path).value} level",  # noqa: E501
                    },
                )

        return None

    async def _check_jwt_auth(
        self, method: str, path: str, auth_header: str, token: str
    ):
        """Check JWT authentication.

        Returns None if auth passes or is disabled, or a callable that sends
        the error response if auth fails.
        """
        if not self.jwt_auth_enabled:
            return None

        # JWT public paths
        if path in AUTH_PUBLIC_PATHS:
            return None
        if any(path.startswith(p) for p in AUTH_PUBLIC_PREFIXES):
            return None

        if not auth_header.startswith("Bearer "):
            return lambda send: _send_json_response(
                send,
                401,
                {
                    "code": 401,
                    "message": "未提供认证Token",
                    "detail": "请在Authorization头中提供Bearer Token",
                },
            )

        if not token:
            return lambda send: _send_json_response(
                send,
                401,
                {
                    "code": 401,
                    "message": "Token为空",
                },
            )

        # Check ban list
        ban_list = _get_token_ban_list()
        if ban_list and ban_list.is_banned(token):
            return lambda send: _send_json_response(
                send,
                401,
                {
                    "code": 401,
                    "message": "Token已被撤销，请重新登录",
                },
            )

        # Strict JWT decode - try access token first
        payload = _decode_token_strict(token, expected_type="access")
        if payload is None:
            # Also try refresh token if it's a valid JWT
            payload = _decode_token_strict(token, expected_type="refresh")
            if payload is None:
                # If the token looks like a JWT but fails decode, reject
                if token.startswith("eyJ"):
                    return lambda send: _send_json_response(
                        send,
                        401,
                        {
                            "code": 401,
                            "message": "Token无效或已过期",
                        },
                    )
                # Non-JWT token - skip JWT check, let LNN auth handle it
                return None

        # JWT auth passed - store user info
        # Note: In pure ASGI we use scope["state"] instead of request.state
        # This is set via the receive wrapper pattern
        return None

    async def _check_agent_auth(
        self,
        method: str,
        path: str,
        auth_header: str,
        start_time: float,
        headers: list,
    ):
        """Check Agent API authentication.

        Returns None if auth passes, or a callable that sends the error
        response if auth fails.
        """
        if not self.agent_auth_enabled:
            return None

        if not auth_header.startswith("Bearer "):
            elapsed = (time.perf_counter() - start_time) * 1000
            agent_audit_log.log(
                agent_id="unknown",
                route=path,
                permission_class="auth",
                status_code=401,
                latency_ms=elapsed,
            )
            return lambda send: _send_json_response(
                send,
                401,
                {
                    "error": "unauthorized",
                    "message": "Missing or invalid Authorization header. Use Bearer lj_agent_xxxx token.",
                },
            )

        raw_token = auth_header[7:]

        # Validate token
        store = _get_agent_token_store()
        agent_token = store.validate_token(raw_token)
        if agent_token is None:
            elapsed = (time.perf_counter() - start_time) * 1000
            agent_audit_log.log(
                agent_id="unknown",
                route=path,
                permission_class="auth",
                status_code=401,
                latency_ms=elapsed,
            )
            return lambda send: _send_json_response(
                send,
                401,
                {
                    "error": "unauthorized",
                    "message": "Invalid or expired Agent token",
                },
            )

        agent_id = agent_token.agent_id
        scopes = agent_token.scopes

        # Check rate limit
        if not agent_rate_limiter.check_rate_limit(agent_id):
            elapsed = (time.perf_counter() - start_time) * 1000
            agent_audit_log.log(
                agent_id=agent_id,
                route=path,
                permission_class="rate_limit",
                status_code=429,
                latency_ms=elapsed,
            )
            return lambda send: _send_json_response(
                send,
                429,
                {
                    "error": "rate_limit_exceeded",
                    "message": f"Rate limit exceeded. Max {agent_rate_limiter._max_rpm} requests per minute.",
                },
            )

        # Determine required permission class
        required_level = _get_permission_class(method, path)

        # Check scope permission
        if not _check_scope(scopes, required_level):
            elapsed = (time.perf_counter() - start_time) * 1000
            agent_audit_log.log(
                agent_id=agent_id,
                route=path,
                permission_class=required_level.value,
                status_code=403,
                latency_ms=elapsed,
            )
            return lambda send: _send_json_response(
                send,
                403,
                {
                    "error": "forbidden",
                    "message": f"Insufficient permission. Token scopes: {scopes}, required: {required_level.value}",
                },
            )

        # Check Idempotency-Key for W/B/T requests
        if required_level.value in WRITE_SCOPES:
            idem_key = None
            for key, value in headers:
                if key.lower() == b"idempotency-key":
                    idem_key = value.decode("utf-8", errors="ignore")
                    break

            if not idem_key:
                elapsed = (time.perf_counter() - start_time) * 1000
                agent_audit_log.log(
                    agent_id=agent_id,
                    route=path,
                    permission_class=required_level.value,
                    status_code=400,
                    latency_ms=elapsed,
                )
                return lambda send: _send_json_response(
                    send,
                    400,
                    {
                        "error": "missing_idempotency_key",
                        "message": f"Idempotency-Key header required for {required_level.value}-class requests",
                    },
                )

            cached_result = idempotency_store.check_and_set(idem_key, agent_id)
            if cached_result is not None:
                elapsed = (time.perf_counter() - start_time) * 1000
                agent_audit_log.log(
                    agent_id=agent_id,
                    route=path,
                    permission_class=required_level.value,
                    status_code=200,
                    latency_ms=elapsed,
                )
                return lambda send: _send_json_response(
                    send,
                    200,
                    {
                        **cached_result,
                        "idempotent_replay": True,
                    },
                )

        return None
