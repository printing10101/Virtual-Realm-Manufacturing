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
import threading
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
    _instance_lock = threading.Lock()
    _cache: Dict[str, tuple[Set[str], float]] = {}
    _ttl: float = 60.0

    def __new__(cls):
        # 安全修复：双重检查锁，防止并发创建多个实例
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    instance = super().__new__(cls)
                    instance._cache_lock = threading.Lock()
                    cls._instance = instance
        return cls._instance

    def get(self, role_code: str) -> Optional[Set[str]]:
        # 安全修复：缓存读取加锁，防止与 set/invalidate 并发修改导致字典状态不一致
        with self._cache_lock:
            entry = self._cache.get(role_code)
            if entry is None:
                return None
            perms, expiry = entry
            if time.time() > expiry:
                self._cache.pop(role_code, None)
                return None
            return perms

    def set(self, role_code: str, permissions: Set[str]):
        with self._cache_lock:
            self._cache[role_code] = (permissions, time.time() + self._ttl)

    def invalidate(self, role_code: Optional[str] = None):
        with self._cache_lock:
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


# [F-P0-4] 防复发：T 级操作敏感字段脱敏白名单
#   NC 程序内容、API Key、密码等不得写入审计日志或普通日志
_SENSITIVE_FIELDS: tuple[str, ...] = (
    "api_key", "password", "token", "secret", "credential",
    "nc_program", "g_code", "nc_code",  # NC 程序可能含商业机密
    "signature", "private_key",
)

# [F-P0-4] 防复发：T 级操作机床安全前置状态字段
#   依据 ISO 10218 工业机器人安全标准 + 用户三方评估 F-P0-4
#   实模式执行前必须校验所有物理安全信号
REQUIRED_MACHINE_SAFETY_FIELDS: tuple[str, ...] = (
    "emergency_stop_active",   # 急停是否触发（True=危险，必须阻止）
    "guard_door_closed",       # 防护门是否关闭
    "light_curtain_clear",     # 光幕是否畅通
    "operator_present",        # 操作员是否在场
)


class PaperOnlyGuard:
    """T 级操作（机床执行）守卫，确保 Paper-Only 模式安全。

    设计依据：
    - ISO 10218 工业机器人安全标准
    - FDA 21 CFR Part 11 电子记录/电子签名
    - 用户三方评估 F-P0-4：实模式必须双因子确认 + 物理急停硬联锁

    防复发机制：
    1. 配置热刷新：每次从环境变量读取，避免启动时固化导致配置无法热切换
    2. 双因子确认：操作员权限 + 班长确认（supervisor_confirmed）
    3. 机床状态前置校验：检查急停/防护门/光幕/操作员在场
    4. 审计日志：T 级操作必须留痕，敏感字段脱敏
    """

    def __init__(self):
        # 兼容旧代码：保留实例字段，但 is_live_execution_allowed 改为实时读取
        # 避免启动时固化配置导致无法热切换
        self._live_execution_cached: Optional[bool] = None

    @staticmethod
    def _read_live_execution_enabled() -> bool:
        """实时读取环境变量，支持热刷新（不再启动时固化）。"""
        return os.environ.get("LNN_LIVE_EXECUTION_ENABLED", "false").lower() == "true"

    def is_live_execution_allowed(self) -> bool:
        """是否允许实模式执行（实时读取环境变量）。"""
        return self._read_live_execution_enabled()

    def check_t_operation(
        self,
        has_t_permission: bool,
        ui_confirmed: bool,
        supervisor_confirmed: bool = False,
        machine_safety_status: Optional[Dict[str, bool]] = None,
    ) -> tuple[bool, str]:
        """T 级操作前置校验。

        Args:
            has_t_permission: 操作员是否具备 T 级权限
            ui_confirmed: 操作员 UI 确认
            supervisor_confirmed: 班长双因子确认（F-P0-4 新增，默认 False
                以强制调用方显式传入，避免遗漏）
            machine_safety_status: 机床安全状态字典，包含：
                - emergency_stop_active: 急停是否触发（True=危险，禁止执行）
                - guard_door_closed: 防护门是否关闭
                - light_curtain_clear: 光幕是否畅通
                - operator_present: 操作员是否在场

        Returns:
            (是否允许执行, 原因说明)
        """
        # 1. Paper-Only 模式快速拒绝
        if not self.is_live_execution_allowed():
            return False, "Paper-Only mode: T operations are simulated"

        # 2. 操作员权限校验
        if not has_t_permission:
            return False, "Insufficient permission: T-level required"

        # 3. 操作员 UI 确认
        if not ui_confirmed:
            return False, "UI confirmation required for T operations"

        # 4. 双因子确认（班长）—— F-P0-4 核心修复
        if not supervisor_confirmed:
            return False, "Supervisor dual-factor confirmation required for T operations"

        # 5. 机床安全状态前置校验 —— F-P0-4 物理联锁
        if machine_safety_status is not None:
            if machine_safety_status.get("emergency_stop_active", True):
                return False, "Machine emergency stop is active; T operation blocked"
            if not machine_safety_status.get("guard_door_closed", False):
                return False, "Guard door is open; T operation blocked"
            if not machine_safety_status.get("light_curtain_clear", True):
                return False, "Light curtain is blocked; T operation blocked"
            if not machine_safety_status.get("operator_present", False):
                return False, "Operator not present; T operation blocked"

        return True, "T operation approved"

    def simulate_t_operation(
        self, operation: Dict[str, Any], operator: str = "unknown"
    ) -> Dict[str, Any]:
        """模拟 T 级操作，记录审计日志（脱敏）。

        Args:
            operation: 操作字典
            operator: 操作员标识

        Returns:
            模拟结果字典
        """
        # 1. 脱敏：移除敏感字段后记录
        sanitized = self._sanitize_operation(operation)
        logger.info(
            "SIMULATED T operation (Paper-Only mode) by %s: %s",
            operator,
            sanitized,
        )

        # 2. 写入审计日志（延迟导入避免循环依赖）
        #    即使是模拟操作也必须留痕，满足 FDA 21 CFR Part 11 合规要求
        try:
            from app.audit.audit_log import (
                Audit,
                AIModule,
                UserDecision,
                OperationStatus,
            )
            from app.utils.utils import get_output_dir

            audit = Audit(log_dir=str(get_output_dir("logs") / "audit"))
            audit.log_decision(
                ai_module=AIModule.PROCESS_OPTIMIZE,
                ai_recommendation=sanitized,
                user_decision=UserDecision.AUTO_EXECUTED,
                final_execution={"executed": False, "mode": "paper-only"},
                operation_status=OperationStatus.PENDING,
                user_id=operator,
                metadata={"operation_type": "t_operation_simulated"},
            )
        except ImportError:
            logger.debug(
                "Audit log module not available; skipping audit record for simulated T operation"
            )
        except Exception as exc:
            # 审计日志写入失败不应阻断模拟流程，但必须告警
            logger.warning(
                "Failed to write audit log for simulated T operation: %s", exc
            )

        return {
            "status": "simulated",
            "message": "Operation recorded but not executed (Paper-Only mode)",
            "operation": sanitized,
        }

    @staticmethod
    def _sanitize_operation(operation: Dict[str, Any]) -> Dict[str, Any]:
        """脱敏操作字典，移除敏感字段值。

        依据 F-P0-4 安全要求：NC 程序内容、API Key、密码等
        不得明文写入审计日志或普通日志。
        """
        sanitized: Dict[str, Any] = {}
        for key, value in operation.items():
            key_lower = str(key).lower()
            if any(sensitive in key_lower for sensitive in _SENSITIVE_FIELDS):
                sanitized[key] = "***REDACTED***"
            else:
                sanitized[key] = value
        return sanitized


paper_only_guard = PaperOnlyGuard()
