from __future__ import annotations

import hmac
import os
import uuid
import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.models.user import UserCreate, UserLogin, UserResponse, get_user_store
from app.auth.security import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
    decode_token_strict,
    get_token_ban_list,
)
from app.middleware.rate_limiter import limiter
from app.core.request_id import get_request_id as _get_request_id


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/auth", tags=["auth"])
security_scheme = HTTPBearer()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security_scheme),
) -> dict:
    token = credentials.credentials
    ban_list = get_token_ban_list()
    if ban_list.is_banned(token):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token已被撤销")

    payload = decode_token_strict(token, expected_type="access")
    if payload is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="无效或过期的Token")

    username = payload.get("sub")
    if not username:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token载荷无效")

    store = get_user_store()
    user = store.get_user(username)
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户不存在或已禁用")

    return {"username": username, "role": user.role}


def require_role(*roles: str):
    async def role_checker(current_user: dict = Depends(get_current_user)):
        if current_user["role"] not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="权限不足")
        return current_user
    return role_checker


@router.post("/register", response_model=dict)
@limiter.limit("3/hour")
async def register(request: Request, body: UserCreate):
    """注册新用户。

    安全控制（按执行顺序）：
    1. 邀请码环境变量检查：当 ``LNN_REGISTRATION_CODE`` 未设置或为空时，
       视为注册功能已关闭，直接返回 403。
    2. 邀请码验证：请求体中的 ``invite_code`` 必须与环境变量值完全匹配
       （使用 ``hmac.compare_digest`` 防止时序攻击）。
    3. 速率限制（slowapi）：同一 IP 在 1 小时内最多允许 3 次注册尝试；超限返回 429，
       响应头携带 ``Retry-After`` 字段，由 slowapi 中间件统一处理。
    4. 用户名唯一性检查：用户名已存在时返回 409。
    """
    # 1) 邀请码环境变量检查：未配置时注册功能视为已关闭
    reg_code = os.environ.get("LNN_REGISTRATION_CODE", "")
    if not reg_code:
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={"code": 1003, "message": "注册功能已关闭", "request_id": _get_request_id()},
        )

    # 2) 邀请码验证（防时序攻击）
    invite_code = body.invite_code or ""
    if not invite_code or not hmac.compare_digest(invite_code, reg_code):
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={"code": 1003, "message": "无效的邀请码", "request_id": _get_request_id()},
        )

    # 3) 速率限制由 slowapi @limiter.limit("3/hour") 装饰器统一处理

    # 4) 用户名唯一性检查
    store = get_user_store()
    if store.get_user(body.username) is not None:
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={"code": 1009, "message": "用户名已存在", "request_id": _get_request_id()},
        )

    try:
        hashed = hash_password(body.password)
        record = store.create_user(body.username, hashed)
        logger.info("User registered: %s", body.username)
        return {
            "status": status.HTTP_200_OK,
            "message": "注册成功",
            "data": UserResponse(
                username=record.username,
                role=record.role,
                created_at=record.created_at,
                last_login=record.last_login,
            ).model_dump(),
        }
    except ValueError as e:
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={"code": 1009, "message": str(e), "request_id": _get_request_id()},
        )


@router.post("/login", response_model=dict)
@limiter.limit("5/minute")
async def login(request: Request, body: UserLogin):
    store = get_user_store()
    user = store.get_user(body.username)

    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户名或密码错误")

    if not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户名或密码错误")

    store.update_last_login(body.username)

    jti = str(uuid.uuid4())
    access_token = create_access_token({"sub": user.username, "role": user.role, "jti": jti})
    refresh_token = create_refresh_token({"sub": user.username, "jti": str(uuid.uuid4())})

    logger.info("User logged in: %s", body.username)
    return {
        "code": 0,
        "message": "登录成功",
        "data": {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "user": UserResponse(
                username=user.username,
                role=user.role,
                created_at=user.created_at,
                last_login=user.last_login,
            ).model_dump(),
        },
    }


@router.post("/refresh", response_model=dict)
async def refresh_token(body: dict):
    refresh_token_str = body.get("refresh_token", "")
    if not refresh_token_str:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="缺少refresh_token")

    ban_list = get_token_ban_list()
    if ban_list.is_banned(refresh_token_str):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="RefreshToken已被撤销，请重新登录")

    payload = decode_token_strict(refresh_token_str, expected_type="refresh")
    if payload is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="RefreshToken无效或已过期")

    username = payload.get("sub")
    if not username:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token载荷无效")

    store = get_user_store()
    user = store.get_user(username)
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户不存在或已禁用")

    ban_list.ban(refresh_token_str)
    new_jti = str(uuid.uuid4())
    new_access = create_access_token({"sub": username, "role": user.role, "jti": new_jti})
    new_refresh = create_refresh_token({"sub": username, "jti": str(uuid.uuid4())})

    logger.info("Token refreshed for user: %s", username)
    return {
        "code": 0,
        "message": "Token刷新成功",
        "data": {
            "access_token": new_access,
            "refresh_token": new_refresh,
            "token_type": "bearer",
        },
    }


@router.post("/logout", response_model=dict)
async def logout(body: dict):
    access_token_str = body.get("access_token", "")
    refresh_token_str = body.get("refresh_token", "")

    ban_list = get_token_ban_list()
    if access_token_str:
        ban_list.ban(access_token_str)
    if refresh_token_str:
        ban_list.ban(refresh_token_str)

    logger.info("User logged out")
    return {"code": 0, "message": "登出成功"}


@router.get("/me", response_model=dict)
async def get_me(current_user: dict = Depends(get_current_user)):
    store = get_user_store()
    user = store.get_user(current_user["username"])
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")
    return {
        "code": 0,
        "message": "OK",
        "data": UserResponse(
            username=user.username,
            role=user.role,
            created_at=user.created_at,
            last_login=user.last_login,
        ).model_dump(),
    }
