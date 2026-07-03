"""Database connection pool management for PostgreSQL.

Provides async SQLAlchemy engine with connection pooling,
health check, and lifecycle management.

Refactored to use thread-safe lazy singleton instead of ``global _``
pattern.  All public helpers are also exposed as FastAPI dependency
factories (see :func:`get_db`, :func:`get_db_sessionmaker`,
:func:`get_db_engine`).
"""

from __future__ import annotations

import logging
import os
import threading
from dataclasses import dataclass, field
from typing import Optional

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy import text

logger = logging.getLogger(__name__)


def _resolve_db_url() -> str:
    # 优先使用 DB_URL 环境变量以保持向后兼容，否则回退到 config.database.db_url
    # 这样配置统一由 config.py 管理（DATABASE_URL），main.py 不再需要设置 DB_URL
    url = os.environ.get("DB_URL")
    if url:
        return url
    from app.config import config
    return config.database.db_url


@dataclass
class DatabaseConfig:
    url: str = field(default_factory=_resolve_db_url)
    pool_size: int = field(default_factory=lambda: int(os.environ.get("DB_POOL_SIZE", "15")))
    max_overflow: int = field(default_factory=lambda: int(os.environ.get("DB_MAX_OVERFLOW", "10")))
    pool_timeout: int = field(default_factory=lambda: int(os.environ.get("DB_POOL_TIMEOUT", "30")))
    pool_recycle: int = field(default_factory=lambda: int(os.environ.get("DB_POOL_RECYCLE", "3600")))
    echo: bool = field(default_factory=lambda: os.environ.get("DB_ECHO", "false").lower() == "true")

    @property
    def async_url(self) -> str:
        url = self.url
        if url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        elif url.startswith("sqlite://"):
            url = url.replace("sqlite://", "sqlite+aiosqlite://", 1)
        return url

    @property
    def enabled(self) -> bool:
        return bool(self.url)


# ---------------------------------------------------------------------------
# Thread-safe lazy singletons (替代 ``global _`` 模式)
# ---------------------------------------------------------------------------
# 设计要点：
# - 使用 ``_SingletonHolder`` 内部类封装可变状态，避免在模块顶层暴露
#   ``_db_engine = None`` 这种"模块级可写变量"。
# - 构造时使用 ``threading.Lock`` 保证多线程并发首次创建时仅产生一个实例。
# - 重置（``close_db``）时使用同一把锁，确保 dispose 与重新初始化互斥。
# ---------------------------------------------------------------------------


class _DatabaseSingletons:
    """Thread-safe lazy holder for engine & sessionmaker."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._engine: Optional[AsyncEngine] = None
        self._sessionmaker: Optional[async_sessionmaker] = None

    def get_engine(self) -> Optional[AsyncEngine]:
        # 快速路径：已存在则直接返回，避免持锁开销
        if self._engine is not None:
            return self._engine
        with self._lock:
            if self._engine is not None:
                return self._engine
            config = DatabaseConfig()
            if not config.enabled:
                logger.warning("DB_URL not configured, database persistence disabled")
                return None
            # Build engine kwargs (SQLite does not support pool_size/max_overflow)
            engine_kwargs = {"echo": config.echo}
            if config.async_url.startswith("sqlite"):
                # SQLite: use StaticPool or NullPool, no pool params
                engine_kwargs["pool_pre_ping"] = False
            else:
                engine_kwargs.update({
                    "pool_size": config.pool_size,
                    "max_overflow": config.max_overflow,
                    "pool_timeout": config.pool_timeout,
                    "pool_recycle": config.pool_recycle,
                    "pool_pre_ping": True,
                })
            self._engine = create_async_engine(config.async_url, **engine_kwargs)
            logger.info(
                "Database engine created: pool_size=%d max_overflow=%d",
                config.pool_size,
                config.max_overflow,
            )
            return self._engine

    def get_sessionmaker(self) -> Optional[async_sessionmaker]:
        if self._sessionmaker is not None:
            return self._sessionmaker
        with self._lock:
            if self._sessionmaker is not None:
                return self._sessionmaker
            engine = self.get_engine()
            if engine is None:
                return None
            self._sessionmaker = async_sessionmaker(engine, expire_on_commit=False)
            return self._sessionmaker

    async def close(self) -> None:
        with self._lock:
            if self._engine is not None:
                try:
                    await self._engine.dispose()
                except Exception as e:  # pragma: no cover - 资源释放失败仅记录
                    logger.warning("Error disposing DB engine: %s", e)
                self._engine = None
                self._sessionmaker = None
                logger.info("Database engine disposed")


_singletons = _DatabaseSingletons()


# ---------------------------------------------------------------------------
# Public helpers (保留重构前的同名 API，确保向后兼容)
# ---------------------------------------------------------------------------


def get_engine() -> Optional[AsyncEngine]:
    """获取全局数据库引擎（首次访问时惰性创建）。

    Returns:
        异步 SQLAlchemy 引擎实例；如果未配置 ``DB_URL`` 则返回 ``None``。
    """
    return _singletons.get_engine()


def get_sessionmaker() -> Optional[async_sessionmaker]:
    """获取全局 sessionmaker（首次访问时惰性创建）。

    Returns:
        :class:`async_sessionmaker` 实例；如果底层引擎不可用则返回 ``None``。
    """
    return _singletons.get_sessionmaker()


async def get_session() -> AsyncSession:
    """获取一个新的 :class:`AsyncSession`（非依赖注入风格，仅供内部调用）。

    Returns:
        已配置 ``expire_on_commit=False`` 的新会话。

    Raises:
        RuntimeError: 数据库未配置（``DB_URL`` 为空）。
    """
    sessionmaker = get_sessionmaker()
    if sessionmaker is None:
        raise RuntimeError("Database not configured")
    return sessionmaker()


async def check_db_health() -> dict:
    engine = get_engine()
    if engine is None:
        return {"status": "disabled", "message": "DB_URL not configured"}
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
            pool = engine.pool
            return {
                "status": "healthy",
                "pool_size": pool.size() if hasattr(pool, "size") else "N/A",
                "checked_out": pool.checkedout() if hasattr(pool, "checkedout") else "N/A",
            }
    except Exception as e:
        logger.warning("数据库健康检查失败: %s", e, exc_info=True)
        return {"status": "unhealthy", "error": f"database: {type(e).__name__}"}


async def close_db() -> None:
    """关闭并释放数据库引擎（FastAPI shutdown 时调用）。"""
    await _singletons.close()


# ---------------------------------------------------------------------------
# FastAPI dependency factories
# ---------------------------------------------------------------------------
# 这些函数可直接用于 ``Depends(...)``。与原 ``get_session`` 不同的是：
# - 返回类型更精确（``Optional[...]`` 表示未配置时为 None）
# - ``get_db`` 是 yield-式依赖，FastAPI 会负责关闭会话
# ---------------------------------------------------------------------------


async def get_db_engine() -> Optional[AsyncEngine]:
    """FastAPI 依赖：返回当前数据库引擎（可能为 ``None``）。

    用法::

        @router.get("/health")
        async def health(engine: AsyncEngine = Depends(get_db_engine)):
            ...
    """
    return _singletons.get_engine()


async def get_db_sessionmaker() -> Optional[async_sessionmaker]:
    """FastAPI 依赖：返回当前 sessionmaker（可能为 ``None``）。"""
    return _singletons.get_sessionmaker()


async def get_db() -> AsyncSession:
    """FastAPI 依赖：yield 一个 :class:`AsyncSession`，请求结束自动关闭。

    用法::

        @router.get("/items")
        async def list_items(session: AsyncSession = Depends(get_db)):
            result = await session.execute(...)

    Raises:
        RuntimeError: 数据库未配置（``DB_URL`` 为空）。
    """
    sessionmaker = _singletons.get_sessionmaker()
    if sessionmaker is None:
        raise RuntimeError("Database not configured")
    async with sessionmaker() as session:
        try:
            yield session
        except (RuntimeError, OSError, ValueError) as e:
            await session.rollback()
            logger.error("Database session error, rolled back: %s", e, exc_info=True)
            raise
        else:
            await session.commit()
