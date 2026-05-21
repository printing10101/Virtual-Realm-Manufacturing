"""Agent Gateway middleware: audit logging, rate limiting, idempotency."""

from __future__ import annotations

import logging
import time
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from app.core.permissions import PERMISSION_HIERARCHY, PermissionLevel

logger = logging.getLogger(__name__)


@dataclass
class AgentAuditEntry:
    timestamp_ms: int
    agent_id: str
    route: str
    permission_class: str
    status_code: int
    latency_ms: float


class AgentAuditLog:
    """JSONL-based audit log for Agent requests."""

    def __init__(self, log_path: str | None = None):
        if log_path is None:
            log_path = str(Path.home() / ".lingjing" / "agent_audit.log")
        self._log_path = Path(log_path)
        self._log_path.parent.mkdir(parents=True, exist_ok=True)

    def log(
        self,
        agent_id: str,
        route: str,
        permission_class: str,
        status_code: int,
        latency_ms: float,
    ):
        import json

        entry = AgentAuditEntry(
            timestamp_ms=int(time.time() * 1000),
            agent_id=agent_id,
            route=route,
            permission_class=permission_class,
            status_code=status_code,
            latency_ms=round(latency_ms, 2),
        )
        self._log_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(str(self._log_path), "a", encoding="utf-8") as f:
                f.write(json.dumps(entry.__dict__) + "\n")
        except (OSError, IOError):
            pass  # Log write should not break the request

    def get_entries(
        self,
        agent_id: str | None = None,
        permission_class: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict]:
        import json

        entries = []
        if self._log_path.exists():
            with self._log_path.open("r") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        e = json.loads(line)
                        if agent_id and e.get("agent_id") != agent_id:
                            continue
                        if (
                            permission_class
                            and e.get("permission_class") != permission_class
                        ):
                            continue
                        entries.append(e)
                    except json.JSONDecodeError:
                        continue
        entries.reverse()
        return entries[offset : offset + limit]


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


class IdempotencyStore:
    """Store idempotency keys for W/B/T requests."""

    def __init__(self):
        self._keys: dict[str, dict] = {}

    def check_and_set(self, key: str, agent_id: str) -> Optional[dict]:
        """Returns cached result if key exists, None if new."""
        self.cleanup()
        if key in self._keys:
            entry = self._keys[key]
            if entry["agent_id"] == agent_id:
                return entry.get("result")
        return None

    def store(self, key: str, agent_id: str, result: dict):
        self._keys[key] = {
            "agent_id": agent_id,
            "result": result,
            "created_at": time.time(),
        }

    def cleanup(self, max_age: int = 3600):
        now = time.time()
        expired = [k for k, v in self._keys.items() if now - v["created_at"] > max_age]
        for k in expired:
            del self._keys[k]


# Singletons
agent_audit_log = AgentAuditLog()
agent_rate_limiter = AgentRateLimiter()
idempotency_store = IdempotencyStore()


# Permission class mapping for Agent API endpoints
AGENT_ENDPOINT_PERMISSIONS: dict[str, PermissionLevel] = {
    "GET /api/agent/v1/health": PermissionLevel.R,
    "GET /api/agent/v1/models": PermissionLevel.R,
    "GET /api/agent/v1/models/{name}/info": PermissionLevel.R,
    "POST /api/agent/v1/predict": PermissionLevel.R,
    "POST /api/agent/v1/train": PermissionLevel.B,
    "GET /api/agent/v1/train/{job_id}": PermissionLevel.R,
    "GET /api/agent/v1/train/{job_id}/stream": PermissionLevel.R,
    "POST /api/agent/v1/execute": PermissionLevel.T,
    "GET /api/agent/v1/audit-log": PermissionLevel.C,
}

WRITE_SCOPES = {"W", "B", "T"}


async def get_permission_class(method: str, path: str) -> PermissionLevel:
    """Determine the permission class for a given endpoint."""
    key = f"{method} {path}"
    if key in AGENT_ENDPOINT_PERMISSIONS:
        return AGENT_ENDPOINT_PERMISSIONS[key]
    # Fallback to default based on method
    defaults = {
        "GET": PermissionLevel.R,
        "POST": PermissionLevel.W,
        "PUT": PermissionLevel.W,
        "DELETE": PermissionLevel.C,
    }
    return defaults.get(method, PermissionLevel.R)


def check_scope(token_scopes: list[str], required: PermissionLevel) -> bool:
    """Check if token has the required scope."""
    if required.value in token_scopes:
        return True
    # Hierarchical: T includes B, B includes W, W includes R
    hierarchy = PERMISSION_HIERARCHY
    token_max = max((hierarchy.get(s, 0) for s in token_scopes), default=0)
    required_value = hierarchy.get(required.value, 0)
    return token_max >= required_value
