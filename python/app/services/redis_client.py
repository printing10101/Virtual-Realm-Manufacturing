"""Redis client wrapper for task progress caching and pub/sub.

Provides async Redis operations with connection management,
health check, and exponential backoff reconnection.

Refactored to use a thread-safe async-safe holder instead of the
``global _`` pattern.  :func:`get_redis` is also exposed as a FastAPI
dependency factory.
"""

from __future__ import annotations

import asyncio
import logging
import os
import threading
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from app.services.memory_cache import get_memory_cache, init_memory_cache, close_memory_cache

logger = logging.getLogger(__name__)

TASK_PROGRESS_PREFIX = "task"
TASK_PROGRESS_TTL = 7 * 24 * 3600


@dataclass
class RedisConfig:
    url: str = field(default_factory=lambda: os.environ.get("REDIS_URL", ""))
    socket_timeout: int = field(default_factory=lambda: int(os.environ.get("REDIS_TIMEOUT", "5")))
    socket_connect_timeout: int = field(default_factory=lambda: int(os.environ.get("REDIS_CONNECT_TIMEOUT", "3")))

    @property
    def enabled(self) -> bool:
        return bool(self.url)


# ---------------------------------------------------------------------------
# Thread + asyncio safe lazy singleton (替代 ``global _`` 模式)
# ---------------------------------------------------------------------------
# 原实现使用 ``global _redis_client`` + ``asyncio.Lock``；现改为将状态
# 封装到 ``_RedisHolder`` 内部，并保留异步锁以保证并发 ``get_redis()``
# 调用只产生一次连接。
# ---------------------------------------------------------------------------


class _RedisHolder:
    """异步安全的 Redis 单例容器。"""

    def __init__(self) -> None:
        # 保护首次创建期间的并发；连接成功后仅读，无锁开销
        self._lock = asyncio.Lock()
        self._init_lock = threading.Lock()  # 保护 _client 字段的可见性
        self._client: Optional[Any] = None

    async def get(self) -> Optional[Any]:
        # 快速路径：已有客户端直接返回。
        # Redis 客户端已配置 health_check_interval=30，会自动进行健康检查
        # 并在连接异常时重连；内存缓存无需健康检查。
        # 移除每次 get() 都 ping 的冗余往返，将延迟降低 ~1 个 RTT。
        client = self._client
        if client is not None:
            return client

        async with self._lock:
            # 双重检查：可能在获取锁的过程中其他协程已建立连接
            if self._client is not None:
                return self._client

            config = RedisConfig()
            if not config.enabled:
                # 桌面模式：使用内存缓存替代 Redis
                logger.info("REDIS_URL not configured, using in-memory cache (desktop mode)")
                try:
                    cache = await init_memory_cache()
                    with self._init_lock:
                        self._client = cache
                    return cache
                except Exception as e:
                    logger.warning("Failed to initialize memory cache: %s", e)
                    return None

            try:
                import redis.asyncio as aioredis

                client = aioredis.from_url(
                    config.url,
                    decode_responses=True,
                    socket_timeout=config.socket_timeout,
                    socket_connect_timeout=config.socket_connect_timeout,
                    retry_on_timeout=True,
                    health_check_interval=30,
                )
                await client.ping()
                with self._init_lock:
                    self._client = client
                logger.info("Redis client connected: %s", config.url)
                return client
            except ImportError:
                logger.warning("redis library not installed, falling back to memory cache")
                try:
                    cache = await init_memory_cache()
                    with self._init_lock:
                        self._client = cache
                    return cache
                except Exception as e:
                    logger.warning("Failed to initialize memory cache: %s", e)
                    return None
            except (ConnectionError, OSError, ValueError, TimeoutError) as e:
                # Redis 连接失败时降级到内存缓存
                logger.error("Failed to connect to Redis: %s, falling back to memory cache", e)
                try:
                    cache = await init_memory_cache()
                    with self._init_lock:
                        self._client = cache
                    return cache
                except Exception as fallback_err:
                    logger.warning("Failed to initialize memory cache: %s", fallback_err)
                    return None

    async def close(self) -> None:
        with self._init_lock:
            client = self._client
            self._client = None
        if client is not None:
            try:
                await client.close()
            except (ConnectionError, OSError, RuntimeError) as close_err:
                # Redis 关闭失败不应阻塞主流程，记录以便排查
                logger.debug(
                    "Redis client close failed, continuing shutdown: %s",
                    close_err,
                    exc_info=True,
                )
            logger.info("Redis client closed")


_holder = _RedisHolder()


# ---------------------------------------------------------------------------
# Public helpers (兼容原 API)
# ---------------------------------------------------------------------------


async def get_redis() -> Optional[Any]:
    """获取共享的 Redis 客户端；首次访问时建立连接。

    Returns:
        redis.asyncio.Redis 实例；如果未配置 ``REDIS_URL`` 或连接失败则返回 ``None``。

    Note:
        同时也是 FastAPI 依赖工厂，可直接用于 ``Depends(get_redis)``。
    """
    return await _holder.get()


async def close_redis() -> None:
    """关闭并释放 Redis 客户端（FastAPI shutdown 时调用）。"""
    await _holder.close()


def _progress_key(task_id: str) -> str:
    return f"{TASK_PROGRESS_PREFIX}:{task_id}:progress"


async def save_task_progress(task_id: str, data: Dict[str, Any]) -> bool:
    r = await get_redis()
    if r is None:
        return False
    try:
        key = _progress_key(task_id)
        await r.hset(key, mapping={k: str(v) for k, v in data.items()})
        await r.expire(key, TASK_PROGRESS_TTL)
        return True
    except (ConnectionError, OSError, TimeoutError, ValueError, TypeError) as e:
        logger.warning("Failed to save task progress to Redis: %s", e)
        return False


async def get_task_progress(task_id: str) -> Dict[str, Any]:
    r = await get_redis()
    if r is None:
        return {}
    try:
        key = _progress_key(task_id)
        raw = await r.hgetall(key)
        result = {}
        for k, v in raw.items():
            try:
                result[k] = float(v)
            except (ValueError, TypeError):
                result[k] = v
        return result
    except (ConnectionError, OSError, TimeoutError, ValueError, TypeError) as e:
        logger.warning("Failed to get task progress from Redis: %s", e)
        return {}


async def delete_task_progress(task_id: str) -> bool:
    r = await get_redis()
    if r is None:
        return False
    try:
        key = _progress_key(task_id)
        await r.delete(key)
        return True
    except (ConnectionError, OSError, TimeoutError, ValueError, TypeError) as e:
        logger.warning("Failed to delete task progress from Redis: %s", e)
        return False


async def set_cancel_flag(task_id: str) -> bool:
    r = await get_redis()
    if r is None:
        return False
    try:
        key = f"{TASK_PROGRESS_PREFIX}:{task_id}:cancel"
        await r.set(key, "1", ex=3600)
        return True
    except (ConnectionError, OSError, TimeoutError, ValueError, TypeError) as e:
        logger.warning("Failed to set cancel flag in Redis: %s", e)
        return False


async def check_cancel_flag(task_id: str) -> bool:
    r = await get_redis()
    if r is None:
        return False
    try:
        key = f"{TASK_PROGRESS_PREFIX}:{task_id}:cancel"
        val = await r.get(key)
        return val == "1"
    except (ConnectionError, OSError, TimeoutError, ValueError, TypeError):
        return False


async def clear_cancel_flag(task_id: str) -> bool:
    r = await get_redis()
    if r is None:
        return False
    try:
        key = f"{TASK_PROGRESS_PREFIX}:{task_id}:cancel"
        await r.delete(key)
        return True
    except (ConnectionError, OSError, TimeoutError, ValueError, TypeError):
        return False


async def check_redis_health() -> dict:
    r = await get_redis()
    if r is None:
        return {"status": "disabled", "message": "REDIS_URL not configured"}
    try:
        await r.ping()
        info = await r.info("memory")
        return {
            "status": "healthy",
            "used_memory_human": info.get("used_memory_human", "N/A"),
            "connected_clients": info.get("connected_clients", "N/A"),
        }
    except (ConnectionError, OSError, TimeoutError, ValueError, TypeError) as e:
        logger.warning("Redis健康检查失败: %s", e, exc_info=True)
        return {"status": "unhealthy", "error": f"redis: {type(e).__name__}"}
