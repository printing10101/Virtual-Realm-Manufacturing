from __future__ import annotations

import os
import logging
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional
from pathlib import Path

import bcrypt
from jose import JWTError, jwt

logger = logging.getLogger(__name__)

# ============================================================
# JWT Secret 安全管理
# - 所有环境（开发、测试、生产）必须设置 LNN_JWT_SECRET 环境变量
# - 密钥长度 >= 32 字符，且具备足够的随机性，否则拒绝启动
# ============================================================

_MIN_SECRET_LENGTH = 32
_GENERATE_SECRET_CMD = 'python -c "import secrets; print(secrets.token_urlsafe(32))"'


def generate_secure_jwt_secret(length: int = 64) -> str:
    """
    生成符合安全标准的随机 JWT 密钥。

    使用 Python secrets 模块生成密码学安全的随机字符串，
    默认长度为 64 字符（可通过 length 参数自定义，但至少 32 字符）。

    用法:
        from app.core.security import generate_secure_jwt_secret
        print(generate_secure_jwt_secret())  # 输出类似: 'a3F8kLm2...'
        # 将输出的密钥设置为环境变量 LNN_JWT_SECRET

    Args:
        length: 密钥长度，默认 64，最小 32。

    Returns:
        安全的随机密钥字符串。
    """
    if length < _MIN_SECRET_LENGTH:
        raise ValueError(f"密钥长度必须至少为 {_MIN_SECRET_LENGTH} 字符")
    return secrets.token_urlsafe(length)


def _validate_and_get_secret() -> str:
    """
    验证并获取 JWT 密钥。

    安全验证逻辑:
        1. 必须从环境变量 LNN_JWT_SECRET 读取密钥，无任何 fallback 机制
        2. 未设置环境变量时，抛出异常拒绝启动并提供密钥生成指导
        3. 密钥长度不足 32 字符时，抛出异常拒绝启动
        4. 密钥缺乏随机性（如全相同字符、简单序列）时，输出警告并拒绝启动
    """
    custom_secret = os.environ.get("LNN_JWT_SECRET")

    # 未提供密钥，拒绝启动
    if not custom_secret:
        raise RuntimeError(
            f"未设置 LNN_JWT_SECRET 环境变量，应用拒绝启动。"
            f"所有环境（包括开发、测试和生产）必须提供有效的 JWT 密钥。\n"
            f"请使用以下命令生成安全密钥：\n"
            f"    {_GENERATE_SECRET_CMD}\n"
            f"然后将输出值设置为环境变量 LNN_JWT_SECRET。"
        )

    # 密钥长度不足
    if len(custom_secret) < _MIN_SECRET_LENGTH:
        raise ValueError(
            f"JWT 密钥长度不足：当前 {len(custom_secret)} 字符，至少需要 {_MIN_SECRET_LENGTH} 字符。\n"
            f"请使用以下命令生成安全密钥：\n"
            f"    {_GENERATE_SECRET_CMD}"
        )

    # 随机性验证：检测明显不安全的密钥模式
    _check_secret_randomness(custom_secret)

    return custom_secret


def _check_secret_randomness(secret: str) -> None:
    """
    检查密钥是否具备足够的随机性。

    检测以下不安全模式:
        1. 全由相同字符组成（如 'aaaa...'）
        2. 字符种类过少（去重后 <= 2 种字符且长度超过 16）
        3. 存在简单重复模式（如 'ababab...'）
    """
    unique_chars = len(set(secret))

    # 全相同字符
    if unique_chars == 1:
        raise ValueError(
            f"JWT 密钥安全性不足：密钥由全相同字符组成。\n"
            f"请使用以下命令生成符合安全标准的密钥：\n"
            f"    {_GENERATE_SECRET_CMD}"
        )

    # 字符种类过少
    if unique_chars <= 2 and len(secret) > 16:
        raise ValueError(
            f"JWT 密钥安全性不足：密钥仅包含 {unique_chars} 种字符，随机性不足。\n"
            f"请使用以下命令生成符合安全标准的密钥：\n"
            f"    {_GENERATE_SECRET_CMD}"
        )

    # 简单重复模式检测（检查前 16 个字符是否为短模式重复）
    for pattern_len in range(1, 9):
        pattern = secret[:pattern_len]
        if len(secret) >= pattern_len * 4 and secret[:pattern_len * 4] == pattern * 4:
            raise ValueError(
                f"JWT 密钥安全性不足：检测到简单重复模式。\n"
                f"请使用以下命令生成符合安全标准的密钥：\n"
                f"    {_GENERATE_SECRET_CMD}"
            )


SECRET_KEY = _validate_and_get_secret()
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
REFRESH_TOKEN_EXPIRE_DAYS = 7

BANNED_TOKENS_FILE = os.environ.get("LNN_BANNED_TOKENS_FILE", ".lnn_banned_tokens.json")


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire, "type": "access"})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def create_refresh_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS))
    to_encode.update({"exp": expire, "type": "refresh"})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> Optional[dict]:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None


def decode_token_strict(token: str, expected_type: str = "access") -> Optional[dict]:
    payload = decode_token(token)
    if payload is None:
        return None
    if payload.get("type") != expected_type:
        return None
    return payload


class TokenBanList:
    def __init__(self, file_path: Optional[str] = None):
        self._file_path = Path(file_path or BANNED_TOKENS_FILE)
        self._banned: set[str] = set()
        self._load()

    def _load(self):
        if self._file_path.exists():
            try:
                import json
                data = json.loads(self._file_path.read_text())
                self._banned = set(data.get("tokens", []))
                self._cleanup_expired(data.get("expiry", {}))
            except Exception:
                self._banned = set()

    def _save(self):
        import json
        data = {"tokens": list(self._banned), "expiry": self._expiry}
        self._file_path.write_text(json.dumps(data))

    def _cleanup_expired(self, expiry: dict):
        self._expiry: dict[str, str] = {}
        now = datetime.now(timezone.utc).isoformat()
        for token_jti, exp_str in expiry.items():
            if exp_str > now:
                self._expiry[token_jti] = exp_str
        self._banned = {t for t in self._banned if t in self._expiry}

    def ban(self, token: str):
        payload = decode_token(token)
        if payload is None:
            jti = token[:32]
            self._banned.add(jti)
            self._save()
            logger.info("Token banned (undecodable): jti=%s", jti)
            return
        if payload.get("exp"):
            jti = payload.get("jti", token[:32])
            self._banned.add(jti)
            exp_time = datetime.fromtimestamp(payload["exp"], tz=timezone.utc).isoformat()
            self._expiry[jti] = exp_time
            self._save()
            logger.info("Token banned: jti=%s", jti)

    def is_banned(self, token: str) -> bool:
        payload = decode_token(token)
        if payload is None:
            return token[:32] in self._banned
        jti = payload.get("jti", token[:32])
        return jti in self._banned


_token_ban_list: Optional[TokenBanList] = None


def get_token_ban_list() -> TokenBanList:
    global _token_ban_list
    if _token_ban_list is None:
        _token_ban_list = TokenBanList()
    return _token_ban_list
