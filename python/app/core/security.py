from __future__ import annotations

import os
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from pathlib import Path

import bcrypt
from jose import JWTError, jwt

logger = logging.getLogger(__name__)

SECRET_KEY = os.environ.get("LNN_JWT_SECRET", "lingjing-default-jwt-secret-change-in-production-x9k2m")
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