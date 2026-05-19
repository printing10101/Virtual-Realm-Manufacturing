"""
Database connection pool management for PostgreSQL.

Provides async SQLAlchemy engine with connection pooling,
health check, and lifecycle management.
"""

import logging
import os
from dataclasses import dataclass, field
from typing import Optional

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy import text

logger = logging.getLogger(__name__)


@dataclass
class DatabaseConfig:
    url: str = field(default_factory=lambda: os.environ.get("DB_URL", ""))
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


_db_engine = None
_db_sessionmaker: Optional[async_sessionmaker] = None


def get_engine():
    global _db_engine
    if _db_engine is None:
        config = DatabaseConfig()
        if not config.enabled:
            logger.warning("DB_URL not configured, database persistence disabled")
            return None
        _db_engine = create_async_engine(
            config.async_url,
            echo=config.echo,
            pool_size=config.pool_size,
            max_overflow=config.max_overflow,
            pool_timeout=config.pool_timeout,
            pool_recycle=config.pool_recycle,
            pool_pre_ping=True,
        )
        logger.info(
            "Database engine created: pool_size=%d max_overflow=%d",
            config.pool_size,
            config.max_overflow,
        )
    return _db_engine


def get_sessionmaker() -> Optional[async_sessionmaker]:
    global _db_sessionmaker
    if _db_sessionmaker is None:
        engine = get_engine()
        if engine is None:
            return None
        _db_sessionmaker = async_sessionmaker(engine, expire_on_commit=False)
    return _db_sessionmaker


async def get_session() -> AsyncSession:
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
        return {"status": "unhealthy", "error": str(e)}


async def close_db():
    global _db_engine, _db_sessionmaker
    if _db_engine:
        await _db_engine.dispose()
        _db_engine = None
        _db_sessionmaker = None
        logger.info("Database engine disposed")