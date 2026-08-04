"""认证相关的 FastAPI 依赖注入工厂。

本模块将 ``get_current_user`` 和 ``security_scheme`` 从 ``api/v1/auth.py``
提升到 ``app/auth/`` 层，使域层模块（simulation/rag/cad 等)可以从
``app.auth.dependencies`` 导入认证依赖，而无需通过 API 层，从而消除
``simulation → api`` 循环依赖。
"""

from __future__ import annotations

from typing import Any

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from starlette import status
from starlette.exceptions import HTTPException

from app.auth.security import decode_token_strict, get_token_ban_list
from app.models.user import get_user_store

# 安全方案：HTTP Bearer Token 认证（单例）
security_scheme = HTTPBearer()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security_scheme),
) -> dict[str, Any]:
    """FastAPI 依赖：从 Authorization Header 解析当前用户。

    验证流程：
    1. 提取 Bearer token
    2. 检查 token 是否在撤销列表中
    3. 解码并验证 JWT
    4. 从 UserStore 查找用户

    Returns:
        ``{"username": ..., "role": ...}`` 字典。

    Raises:
        HTTPException(401): Token 无效、过期、被撤销或用户不存在/已禁用。
    """
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
