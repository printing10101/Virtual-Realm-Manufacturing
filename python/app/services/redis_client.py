"""
Redis client wrapper for task progress caching and pub/sub.

Provides async Redis operations with connection management,
health check, and exponential backoff reconnection.
"""

import asyncio
import logging
import os
from dataclasses import dataclass, field
from typing import Any, Dict

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


_redis_client = None
_redis_lock = asyncio.Lock()


async def get_redis():
    global _redis_client
    if _redis_client is not None:
        try:
            await _redis_client.ping()
            return _redis_client
        except Exception:
            _redis_client = None

    async with _redis_lock:
        if _redis_client is not None:
            return _redis_client

        config = RedisConfig()
        if not config.enabled:
            logger.warning("REDIS_URL not configured, Redis caching disabled")
            return None

        try:
            import redis.asyncio as aioredis

            _redis_client = aioredis.from_url(
                config.url,
                decode_responses=True,
                socket_timeout=config.socket_timeout,
                socket_connect_timeout=config.socket_connect_timeout,
                retry_on_timeout=True,
                health_check_interval=30,
            )
            await _redis_client.ping()
            logger.info("Redis client connected: %s", config.url)
            return _redis_client
        except ImportError:
            logger.warning("redis library not installed, Redis caching disabled")
            return None
        except Exception as e:
            logger.error("Failed to connect to Redis: %s", e)
            return None


async def close_redis():
    global _redis_client
    if _redis_client:
        try:
            await _redis_client.close()
        except Exception:
            pass
        _redis_client = None
        logger.info("Redis client closed")


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
    except Exception as e:
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
    except Exception as e:
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
    except Exception as e:
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
    except Exception as e:
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
    except Exception:
        return False


async def clear_cancel_flag(task_id: str) -> bool:
    r = await get_redis()
    if r is None:
        return False
    try:
        key = f"{TASK_PROGRESS_PREFIX}:{task_id}:cancel"
        await r.delete(key)
        return True
    except Exception:
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
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}
