"""Idempotency store (moved from unified_auth.py).

Store idempotency keys for W/B/T requests.

修复点:
1) 内存泄漏：每次 `check_and_set` / `store` 都会按时间窗口清理过期条目；
   即使在低流量情况下也保证条目不会无限累积。
2) 竞态条件：使用线程锁序列化 check-and-set，避免并发请求同时通过校验。
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Optional

logger = logging.getLogger(__name__)


class IdempotencyStore:
    """Store idempotency keys for W/B/T requests.

    修复点:
    1) 内存泄漏：每次 `check_and_set` / `store` 都会按时间窗口清理过期条目；
       即使在低流量情况下也保证条目不会无限累积。
    2) 竞态条件：使用线程锁序列化 check-and-set，避免并发请求同时通过校验。
    """

    def __init__(self, max_age: int = 3600, max_entries: int = 10000):
        self._keys: dict[str, dict] = {}
        self._max_age = max_age
        self._max_entries = max_entries
        self._lock = threading.Lock()
        self._last_cleanup = time.time()
        self._cleanup_interval = min(300, max_age // 4 or 60)

    def check_and_set(self, key: str, agent_id: str) -> Optional[dict]:
        """Returns cached result if key exists, None if new."""
        with self._lock:
            self._maybe_cleanup_locked()
            entry = self._keys.get(key)
            if entry is not None and entry["agent_id"] == agent_id:
                return entry.get("result")
            return None

    def store(self, key: str, agent_id: str, result: dict):
        with self._lock:
            self._maybe_cleanup_locked()
            # 强制上限保护，防止极端场景下内存膨胀
            if len(self._keys) >= self._max_entries and key not in self._keys:
                # 按 created_at 淘汰最旧条目
                oldest_key = min(
                    self._keys,
                    key=lambda k: self._keys[k].get("created_at", 0.0),
                )
                self._keys.pop(oldest_key, None)
            self._keys[key] = {
                "agent_id": agent_id,
                "result": result,
                "created_at": time.time(),
            }

    def _maybe_cleanup_locked(self):
        now = time.time()
        if now - self._last_cleanup < self._cleanup_interval:
            return
        self._last_cleanup = now
        expired = [k for k, v in self._keys.items() if now - v["created_at"] > self._max_age]
        for k in expired:
            del self._keys[k]

    def cleanup(self, max_age: Optional[int] = None):
        """兼容旧接口：显式调用以立即清理过期条目。"""
        threshold = max_age if max_age is not None else self._max_age
        with self._lock:
            now = time.time()
            expired = [k for k, v in self._keys.items() if now - v["created_at"] > threshold]
            for k in expired:
                del self._keys[k]
            self._last_cleanup = now


# Singleton
idempotency_store = IdempotencyStore()
