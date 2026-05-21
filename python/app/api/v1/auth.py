from __future__ import annotations

import uuid
import logging

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.models.user import UserCreate, UserLogin, UserResponse, get_user_store
from app.core.security import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
    decode_token_strict,
    get_token_ban_list,
)

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
async def register(body: UserCreate):
    store = get_user_store()
    if store.get_user(body.username) is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="用户名已存在")

    try:
        hashed = hash_password(body.password)
        record = store.create_user(body.username, hashed)
        logger.info("User registered: %s", body.username)
        return {
            "code": 0,
            "message": "注册成功",
            "data": UserResponse(
                username=record.username,
                role=record.role,
                created_at=record.created_at,
                last_login=record.last_login,
            ).model_dump(),
        }
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))


@router.post("/login", response_model=dict)
async def login(body: UserLogin):
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
