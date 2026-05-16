"""
SQLite 操作重试包装器

在异步 + check_same_thread=False 的上下文中，
并发写操作可能触发 database is locked 错误。
本模块提供装饰器和上下文管理器，以指数退避 + jitter 自动重试。
"""

import functools
import logging
import random
import sqlite3
import time
from typing import Any, Callable, TypeVar

logger = logging.getLogger(__name__)

F = TypeVar("F", bound=Callable[..., Any])

DEFAULT_MAX_RETRIES = 5
DEFAULT_BASE_DELAY = 0.05
DEFAULT_MAX_DELAY = 2.0


def _is_lock_error(error: Exception) -> bool:
    if isinstance(error, sqlite3.OperationalError):
        msg = str(error).lower()
        return "database is locked" in msg or "database is busy" in msg
    return False


def sqlite_retry(
    max_retries: int = DEFAULT_MAX_RETRIES,
    base_delay: float = DEFAULT_BASE_DELAY,
    max_delay: float = DEFAULT_MAX_DELAY,
):
    """
    装饰器：自动重试 SQLite 数据库锁定错误

    Args:
        max_retries: 最大重试次数
        base_delay: 基础延迟（秒）
        max_delay: 最大延迟（秒）
    """

    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            last_error: Optional[Exception] = None
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except sqlite3.OperationalError as e:
                    if not _is_lock_error(e):
                        raise
                    last_error = e
                    if attempt >= max_retries:
                        break
                    delay = min(base_delay * (2**attempt), max_delay)
                    jitter = random.uniform(0, delay * 0.5)
                    sleep_time = delay + jitter
                    logger.debug(
                        "SQLite lock retry %d/%d after %.3fs: %s",
                        attempt + 1,
                        max_retries,
                        sleep_time,
                        e,
                    )
                    time.sleep(sleep_time)
                except Exception:
                    raise

            logger.error(
                "SQLite operation failed after %d retries: %s",
                max_retries,
                last_error,
            )
            raise last_error  # type: ignore[misc]

        return wrapper  # type: ignore[return-value]

    return decorator


class SqliteTransaction:
    """带重试的 SQLite 事务上下文管理器"""

    def __init__(
        self,
        conn: sqlite3.Connection,
        max_retries: int = DEFAULT_MAX_RETRIES,
        base_delay: float = DEFAULT_BASE_DELAY,
        max_delay: float = DEFAULT_MAX_DELAY,
    ):
        self._conn = conn
        self._max_retries = max_retries
        self._base_delay = base_delay
        self._max_delay = max_delay

    def execute(self, sql: str, params: Any = None) -> sqlite3.Cursor:
        last_error: Optional[Exception] = None
        for attempt in range(self._max_retries + 1):
            try:
                if params is not None:
                    return self._conn.execute(sql, params)
                return self._conn.execute(sql)
            except sqlite3.OperationalError as e:
                if not _is_lock_error(e):
                    raise
                last_error = e
                if attempt >= self._max_retries:
                    break
                delay = min(self._base_delay * (2**attempt), self._max_delay)
                time.sleep(delay + random.uniform(0, delay * 0.5))

        raise last_error  # type: ignore[misc]

    def commit(self) -> None:
        last_error: Optional[Exception] = None
        for attempt in range(self._max_retries + 1):
            try:
                self._conn.commit()
                return
            except sqlite3.OperationalError as e:
                if not _is_lock_error(e):
                    raise
                last_error = e
                if attempt >= self._max_retries:
                    break
                delay = min(self._base_delay * (2**attempt), self._max_delay)
                time.sleep(delay + random.uniform(0, delay * 0.5))

        raise last_error  # type: ignore[misc]
