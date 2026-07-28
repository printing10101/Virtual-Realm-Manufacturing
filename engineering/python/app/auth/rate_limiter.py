"""Agent rate limiter (moved from unified_auth.py).

Per-token rate limiter: max requests per minute and max concurrent tasks.
"""

from __future__ import annotations

import logging
import time
from collections import defaultdict

logger = logging.getLogger(__name__)


class AgentRateLimiter:
    """Per-token rate limiter: max requests per minute and max concurrent tasks."""

    def __init__(
        self,
        max_requests_per_minute: int = 60,
        max_concurrent_tasks: int = 3,
    ):
        self._max_rpm = max_requests_per_minute
        self._max_concurrent = max_concurrent_tasks
        self._request_log: dict[str, list[float]] = defaultdict(list)
        self._active_tasks: dict[str, int] = defaultdict(int)

    def check_rate_limit(self, agent_id: str) -> bool:
        now = time.time()
        cutoff = now - 60
        self._request_log[agent_id] = [
            t for t in self._request_log[agent_id] if t > cutoff
        ]
        if len(self._request_log[agent_id]) >= self._max_rpm:
            return False
        self._request_log[agent_id].append(now)
        return True

    def acquire_task(self, agent_id: str) -> bool:
        if self._active_tasks.get(agent_id, 0) >= self._max_concurrent:
            return False
        self._active_tasks[agent_id] += 1
        return True

    def release_task(self, agent_id: str):
        self._active_tasks[agent_id] = max(0, self._active_tasks.get(agent_id, 0) - 1)

    def get_active_tasks(self, agent_id: str) -> int:
        return self._active_tasks.get(agent_id, 0)


# Singleton
agent_rate_limiter = AgentRateLimiter()
