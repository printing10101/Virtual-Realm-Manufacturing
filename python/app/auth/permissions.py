"""
Capability-Based Permission Model + RBAC Permission Code Check

Implements R/W/B/N/C/T six-level permission classification:
- R (Read): LNN prediction queries, model lists, dataset info - default allow
- W (Workspace Write): Save predictions, create projects - default allow
- B (Batch/Training): LNN model training, batch inference - default allow
- N (Notification): Training completion notifications - default allow (rate limited)
- C (Credentials): System config, API key management - default deny, admin only
- T (Execute): Process parameter dispatch to machines - default deny, explicit auth required

Also provides RBAC permission-code-based decorators and dependency injection.

Reference: QuantDinger permission model design
"""

from __future__ import annotations
import os
import time
import logging
from enum import Enum
from functools import wraps
from typing import Dict, Callable, Optional, List, Set

from dataclasses import dataclass, field
from fastapi import HTTPException, status, Request

logger = logging.getLogger(__name__)


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


@dataclass
class RateLimitConfig:
    max_requests: int = 100
    window_seconds: int = 60


@dataclass
class RateLimitState:
    requests: list = field(default_factory=list)

    def is_allowed(self, config: RateLimitConfig) -> bool:
        now = time.time()
        cutoff = now - config.window_seconds
        self.requests = [t for t in self.requests if t > cutoff]
        return len(self.requests) < config.max_requests

    def record(self):
        self.requests.append(time.time())


class PermissionChecker:
    ENDPOINT_PERMISSIONS: Dict[str, PermissionLevel] = {
        "GET /api/v1/lnn/predict": PermissionLevel.R,
        "GET /api/v1/lnn/models": PermissionLevel.R,
        "GET /api/v1/lnn/tasks": PermissionLevel.R,
        "GET /api/v1/lnn/tasks/{task_id}": PermissionLevel.R,
        "GET /api/v1/wear/predict": PermissionLevel.R,
        "POST /api/v1/wear/predict": PermissionLevel.R,
        "GET /api/v1/datasets": PermissionLevel.R,
        "GET /api/v1/datasets/{dataset_id}": PermissionLevel.R,
        "GET /api/v1/datasets/{dataset_id}/info": PermissionLevel.R,
        "POST /api/v1/lnn/predict": PermissionLevel.W,
        "POST /api/v1/lnn/save_prediction": PermissionLevel.W,
        "POST /api/v1/projects": PermissionLevel.W,
        "PUT /api/v1/projects/{project_id}": PermissionLevel.W,
        "POST /api/v1/lnn/train": PermissionLevel.B,
        "POST /api/v1/lnn/batch_predict": PermissionLevel.B,
        "POST /api/v1/wear/train": PermissionLevel.B,
        "POST /api/v1/notifications": PermissionLevel.N,
        "GET /api/v1/notifications": PermissionLevel.N,
        "GET /api/v1/config": PermissionLevel.C,
        "PUT /api/v1/config": PermissionLevel.C,
        "POST /api/v1/api-keys": PermissionLevel.C,
        "DELETE /api/v1/api-keys/{key_id}": PermissionLevel.C,
        "POST /api/v1/machine/params": PermissionLevel.T,
        "POST /api/v1/machine/execute": PermissionLevel.T,
        "PUT /api/v1/machine/{machine_id}/params": PermissionLevel.T,
    }

    DEFAULT_PERMISSIONS = {
        "GET": PermissionLevel.R,
        "POST": PermissionLevel.W,
        "PUT": PermissionLevel.W,
        "DELETE": PermissionLevel.C,
        "PATCH": PermissionLevel.W,
    }

    def __init__(self):
        self._rate_limiter: Dict[str, RateLimitState] = {}
        self._rate_limit_config = RateLimitConfig()

    def has_permission(
        self, token_level: PermissionLevel, endpoint: str, method: str
    ) -> bool:
        key = f"{method} {endpoint}"
        required_level = self.ENDPOINT_PERMISSIONS.get(key)

        if required_level is None:
            required_level = self.DEFAULT_PERMISSIONS.get(method, PermissionLevel.R)

        token_level_value = PERMISSION_HIERARCHY.get(token_level, 0)
        required_level_value = PERMISSION_HIERARCHY.get(required_level, 0)

        return token_level_value >= required_level_value

    def check_rate_limit(self, token_id: str) -> bool:
        if token_id not in self._rate_limiter:
            self._rate_limiter[token_id] = RateLimitState()

        state = self._rate_limiter[token_id]

        if not state.is_allowed(self._rate_limit_config):
            logger.warning("Rate limit exceeded for token %s", token_id)
            return False

        state.record()
        return True

    def get_required_permission(self, method: str, path: str) -> PermissionLevel:
        key = f"{method} {path}"
        return self.ENDPOINT_PERMISSIONS.get(
            key, self.DEFAULT_PERMISSIONS.get(method, PermissionLevel.R)
        )


permission_checker = PermissionChecker()


class RBACPermissionCache:
    _instance: Optional[RBACPermissionCache] = None
    _cache: Dict[str, tuple[Set[str], float]] = {}
    _ttl: float = 60.0

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def get(self, role_code: str) -> Optional[Set[str]]:
        entry = self._cache.get(role_code)
        if entry is None:
            return None
        perms, expiry = entry
        if time.time() > expiry:
            del self._cache[role_code]
            return None
        return perms

    def set(self, role_code: str, permissions: Set[str]):
        self._cache[role_code] = (permissions, time.time() + self._ttl)

    def invalidate(self, role_code: Optional[str] = None):
        if role_code:
            self._cache.pop(role_code, None)
        else:
            self._cache.clear()


rbac_cache = RBACPermissionCache()


async def _get_role_permissions_from_db(role_code: str) -> Set[str]:
    from app.database.connection import get_sessionmaker
    from sqlalchemy import select
    from app.database.models import Role, Permission, RolePermission

    cached = rbac_cache.get(role_code)
    if cached is not None:
        return cached

    sessionmaker = get_sessionmaker()
    if sessionmaker is None:
        logger.warning("Database not configured, using default empty permissions for role: %s", role_code)
        return set()

    async with sessionmaker() as session:
        stmt = select(Role).where(Role.code == role_code)
        result = await session.execute(stmt)
        role = result.scalar_one_or_none()
        if role is None:
            return set()

        perm_stmt = (
            select(Permission.code)
            .join(RolePermission, RolePermission.permission_id == Permission.id)
            .where(RolePermission.role_id == role.id)
        )
        result = await session.execute(perm_stmt)
        perms = {row[0] for row in result.fetchall()}

    rbac_cache.set(role_code, perms)
    return perms


async def get_user_permissions(username: str) -> Set[str]:
    from app.models.user import get_user_store

    store = get_user_store()
    user = store.get_user(username)
    if user is None:
        return set()

    return await _get_role_permissions_from_db(user.role)


async def check_user_has_permission(username: str, required: str) -> bool:
    perms = await get_user_permissions(username)
    return required in perms


async def check_user_has_any_permission(username: str, required: List[str]) -> bool:
    perms = await get_user_permissions(username)
    return any(p in perms for p in required)


async def check_user_has_all_permissions(username: str, required: List[str]) -> bool:
    perms = await get_user_permissions(username)
    return all(p in perms for p in required)


def require_permission(permission: str):
    """
    FastAPI dependency: check single permission.
    Usage: @router.get("/path", dependencies=[Depends(require_permission("project:create"))])
    """

    async def checker(request: Request):
        if not hasattr(request.state, "username") or not request.state.username:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

        username = request.state.username
        has_perm = await check_user_has_permission(username, permission)
        if not has_perm:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient permission: {permission}",
            )

    return checker


def require_any_permission(*permissions: str):
    """
    FastAPI dependency: check if user has at least one of the given permissions (OR logic).
    """

    async def checker(request: Request):
        if not hasattr(request.state, "username") or not request.state.username:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

        username = request.state.username
        has_perm = await check_user_has_any_permission(username, list(permissions))
        if not has_perm:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient permission: need any of {permissions}",
            )

    return checker


def require_all_permissions(*permissions: str):
    """
    FastAPI dependency: check if user has ALL given permissions (AND logic).
    """

    async def checker(request: Request):
        if not hasattr(request.state, "username") or not request.state.username:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

        username = request.state.username
        has_perm = await check_user_has_all_permissions(username, list(permissions))
        if not has_perm:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient permission: need all of {permissions}",
            )

    return checker


def permission_required(permission: str):
    """
    Decorator for route functions: check single permission.
    Usage:
        @router.get("/path")
        @permission_required("project:create")
        async def my_route(...):
            ...
    """

    def decorator(func: Callable):
        setattr(func, "_required_permission", permission)

        @wraps(func)
        async def wrapper(*args, **kwargs):
            request = kwargs.get("request")
            if request is None:
                for arg in args:
                    if hasattr(arg, "state") and hasattr(arg.state, "username"):
                        request = arg
                        break

            if request is not None and hasattr(request.state, "username") and request.state.username:
                username = request.state.username
                has_perm = await check_user_has_permission(username, permission)
                if not has_perm:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail=f"Insufficient permission: {permission}",
                    )

            return await func(*args, **kwargs)

        return wrapper

    return decorator


def require_role(*roles: str):
    """
    FastAPI dependency: check user role.
    Usage: @router.get("/path", dependencies=[Depends(require_role("admin"))])
    """

    async def role_checker(request: Request):
        if not hasattr(request.state, "username") or not request.state.username:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

        role = request.state.user_role
        if role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient role: need {roles}",
            )

    return role_checker


class PaperOnlyGuard:
    def __init__(self):
        self.live_execution_enabled = (
            os.environ.get("LNN_LIVE_EXECUTION_ENABLED", "false").lower() == "true"
        )

    def is_live_execution_allowed(self) -> bool:
        return self.live_execution_enabled

    def check_t_operation(
        self, has_t_permission: bool, ui_confirmed: bool
    ) -> tuple[bool, str]:
        if not self.live_execution_enabled:
            return False, "Paper-Only mode: T operations are simulated"

        if not has_t_permission:
            return False, "Insufficient permission: T-level required"

        if not ui_confirmed:
            return False, "UI confirmation required for T operations"

        return True, "T operation approved"

    def simulate_t_operation(self, operation: dict) -> dict:
        logger.info("SIMULATED T operation (Paper-Only mode): %s", operation)
        return {
            "status": "simulated",
            "message": "Operation recorded but not executed (Paper-Only mode)",
            "operation": operation,
        }


paper_only_guard = PaperOnlyGuard()
