from __future__ import annotations

import os
import logging
import secrets
import threading
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
        from app.auth.security import generate_secure_jwt_secret
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


def _reset_secret_for_testing(secret: Optional[str] = None) -> str:
    """仅供单元测试使用：允许在运行时替换 SECRET_KEY 以避开模块级副作用。

    正常业务代码不应调用此函数。
    """
    global SECRET_KEY
    if secret is None:
        os.environ.setdefault("LNN_JWT_SECRET", "a" * 64)
        secret = _validate_and_get_secret()
    SECRET_KEY = secret
    return SECRET_KEY


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
    except JWTError:
        return None
    # 修复：对载荷做严格类型校验，避免 None/非字符串 sub 通过验证
    # 导致下游用户标识处理出现 AttributeError 或 SQL 注入风险。
    if not isinstance(payload, dict):
        return None
    sub = payload.get("sub")
    if sub is not None and not isinstance(sub, str):
        return None
    return payload


def decode_token_strict(token: str, expected_type: str = "access") -> Optional[dict]:
    payload = decode_token(token)
    if payload is None:
        return None
    if payload.get("type") != expected_type:
        return None
    # 严格模式额外校验 sub 必存在且为非空字符串
    sub = payload.get("sub")
    if not isinstance(sub, str) or not sub:
        return None
    return payload


class TokenBanList:
    def __init__(self, file_path: Optional[str] = None):
        self._file_path = Path(file_path or BANNED_TOKENS_FILE)
        self._banned: set[str] = set()
        # 修复：_expiry 必须在 __init__ 中显式初始化，避免 _load/_cleanup_expired
        # 出现 AttributeError；之前仅在 _cleanup_expired 内做变量注解是脆弱的。
        self._expiry: dict[str, str] = {}
        # 修复 [并发安全]：保护内存态 + 文件写，避免多线程下
        # ``_banned`` 读写竞争以及 ``_save()`` 写文件时相互覆盖。
        self._lock = threading.Lock()
        self._load()

    def _load(self):
        if self._file_path.exists():
            try:
                import json
                data = json.loads(self._file_path.read_text())
                self._banned = set(data.get("tokens", []))
                self._cleanup_expired(data.get("expiry", {}))
            except Exception as e:
                logger.warning("加载 token 黑名单文件失败，使用空黑名单: %s", e)
                self._banned = set()

    def _save(self):
        import json
        # 修复 [并发安全]：通过临时文件 + 原子替换避免半写状态导致黑名单丢失；
        # 同时持锁保证内存与磁盘视图一致。
        data = {"tokens": list(self._banned), "expiry": self._expiry}
        tmp_path = self._file_path.with_suffix(self._file_path.suffix + ".tmp")
        tmp_path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp_path, self._file_path)

    def _cleanup_expired(self, expiry: dict):
        # 不再在方法体内做类型注解，确保 self._expiry 已存在
        now = datetime.now(timezone.utc).isoformat()
        for token_jti, exp_str in expiry.items():
            if exp_str > now:
                self._expiry[token_jti] = exp_str
        # 只保留在 _expiry 中出现的 jti，删除已过期但残留在 banned 的条目
        self._banned = {t for t in self._banned if t in self._expiry}

    def ban(self, token: str):
        # 修复 [并发安全]：ban/is_banned/ban 都需持锁，否则在多线程下
        # _save() 与 _banned 修改可能产生不一致。
        with self._lock:
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
        # 修复 [并发安全]：持锁读取 _banned，避免 ban() 写入过程中产生
        # 集合中途状态被读到的风险（Python set 本身非线程安全）。
        with self._lock:
            payload = decode_token(token)
            if payload is None:
                return token[:32] in self._banned
            jti = payload.get("jti", token[:32])
            return jti in self._banned


class _TokenBanListHolder:
    """Thread-safe lazy holder for the :class:`TokenBanList` singleton."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._instance: Optional[TokenBanList] = None

    def get(self) -> TokenBanList:
        # 快速路径：已存在则直接返回，避免持锁开销
        if self._instance is not None:
            return self._instance
        with self._lock:
            # 双重检查：可能在获取锁的过程中其他线程已创建实例
            if self._instance is not None:
                return self._instance
            self._instance = TokenBanList()
            return self._instance

    def reset(self) -> None:
        """Reset the cached instance (mainly for tests)."""
        with self._lock:
            self._instance = None


_holder = _TokenBanListHolder()


def get_token_ban_list() -> TokenBanList:
    """获取共享的 :class:`TokenBanList` 单例；首次访问时懒初始化。

    Returns:
        :class:`TokenBanList` 实例（应用生命周期内同一实例）。

    Note:
        同时也是 FastAPI 依赖工厂，可直接用于 ``Depends(get_token_ban_list)``。
        实现是线程安全的，行为与重构前完全一致。
    """
    return _holder.get()
