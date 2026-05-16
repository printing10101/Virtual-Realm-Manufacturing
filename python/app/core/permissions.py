"""
Capability-Based Permission Model

Implements R/W/B/N/C/T six-level permission classification:
- R (Read): LNN prediction queries, model lists, dataset info - default allow
- W (Workspace Write): Save predictions, create projects - default allow
- B (Batch/Training): LNN model training, batch inference - default allow
- N (Notification): Training completion notifications - default allow (rate limited)
- C (Credentials): System config, API key management - default deny, admin only
- T (Execute): Process parameter dispatch to machines - default deny, explicit auth required

Reference: QuantDinger permission model design
"""

from __future__ import annotations
import os
import logging
import time
from enum import Enum
from typing import Dict
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


class PermissionLevel(str, Enum):
    R = "R"
    W = "W"
    B = "B"
    N = "N"
    C = "C"
    T = "T"


PERMISSION_HIERARCHY = {
    PermissionLevel.R: 0,
    PermissionLevel.W: 1,
    PermissionLevel.B: 2,
    PermissionLevel.N: 3,
    PermissionLevel.C: 4,
    PermissionLevel.T: 5,
}


@dataclass
class RateLimitConfig:
    max_requests: int = 100
    window_seconds: int = 60


@dataclass
class RateLimitState:
    requests: list = field(default_factory=list)

    def is_allowed(self, config: RateLimitConfig) -> bool:
        now = time.time()
        cutoff = now - config.window_seconds
        self.requests = [t for t in self.requests if t > cutoff]
        return len(self.requests) < config.max_requests

    def record(self):
        self.requests.append(time.time())


class PermissionChecker:
    ENDPOINT_PERMISSIONS: Dict[str, PermissionLevel] = {
        "GET /api/v1/lnn/predict": PermissionLevel.R,
        "GET /api/v1/lnn/models": PermissionLevel.R,
        "GET /api/v1/lnn/tasks": PermissionLevel.R,
        "GET /api/v1/lnn/tasks/{task_id}": PermissionLevel.R,
        "GET /api/v1/wear/predict": PermissionLevel.R,
        "POST /api/v1/wear/predict": PermissionLevel.R,
        "GET /api/v1/datasets": PermissionLevel.R,
        "GET /api/v1/datasets/{dataset_id}": PermissionLevel.R,
        "GET /api/v1/datasets/{dataset_id}/info": PermissionLevel.R,
        "POST /api/v1/lnn/predict": PermissionLevel.W,
        "POST /api/v1/lnn/save_prediction": PermissionLevel.W,
        "POST /api/v1/projects": PermissionLevel.W,
        "PUT /api/v1/projects/{project_id}": PermissionLevel.W,
        "POST /api/v1/lnn/train": PermissionLevel.B,
        "POST /api/v1/lnn/batch_predict": PermissionLevel.B,
        "POST /api/v1/wear/train": PermissionLevel.B,
        "POST /api/v1/notifications": PermissionLevel.N,
        "GET /api/v1/notifications": PermissionLevel.N,
        "GET /api/v1/config": PermissionLevel.C,
        "PUT /api/v1/config": PermissionLevel.C,
        "POST /api/v1/api-keys": PermissionLevel.C,
        "DELETE /api/v1/api-keys/{key_id}": PermissionLevel.C,
        "POST /api/v1/machine/params": PermissionLevel.T,
        "POST /api/v1/machine/execute": PermissionLevel.T,
        "PUT /api/v1/machine/{machine_id}/params": PermissionLevel.T,
    }

    DEFAULT_PERMISSIONS = {
        "GET": PermissionLevel.R,
        "POST": PermissionLevel.W,
        "PUT": PermissionLevel.W,
        "DELETE": PermissionLevel.C,
        "PATCH": PermissionLevel.W,
    }

    def __init__(self):
        self._rate_limiter: Dict[str, RateLimitState] = {}
        self._rate_limit_config = RateLimitConfig()

    def has_permission(
        self, token_level: PermissionLevel, endpoint: str, method: str
    ) -> bool:
        key = f"{method} {endpoint}"
        required_level = self.ENDPOINT_PERMISSIONS.get(key)

        if required_level is None:
            required_level = self.DEFAULT_PERMISSIONS.get(method, PermissionLevel.R)

        token_level_value = PERMISSION_HIERARCHY.get(token_level, 0)
        required_level_value = PERMISSION_HIERARCHY.get(required_level, 0)

        return token_level_value >= required_level_value

    def check_rate_limit(self, token_id: str) -> bool:
        if token_id not in self._rate_limiter:
            self._rate_limiter[token_id] = RateLimitState()

        state = self._rate_limiter[token_id]

        if not state.is_allowed(self._rate_limit_config):
            logger.warning("Rate limit exceeded for token %s", token_id)
            return False

        state.record()
        return True

    def get_required_permission(self, method: str, path: str) -> PermissionLevel:
        key = f"{method} {path}"
        return self.ENDPOINT_PERMISSIONS.get(
            key, self.DEFAULT_PERMISSIONS.get(method, PermissionLevel.R)
        )


permission_checker = PermissionChecker()


class PaperOnlyGuard:
    def __init__(self):
        self.live_execution_enabled = (
            os.environ.get("LNN_LIVE_EXECUTION_ENABLED", "false").lower() == "true"
        )

    def is_live_execution_allowed(self) -> bool:
        return self.live_execution_enabled

    def check_t_operation(
        self, has_t_permission: bool, ui_confirmed: bool
    ) -> tuple[bool, str]:
        if not self.live_execution_enabled:
            return False, "Paper-Only mode: T operations are simulated"

        if not has_t_permission:
            return False, "Insufficient permission: T-level required"

        if not ui_confirmed:
            return False, "UI confirmation required for T operations"

        return True, "T operation approved"

    def simulate_t_operation(self, operation: dict) -> dict:
        logger.info("SIMULATED T operation (Paper-Only mode): %s", operation)
        return {
            "status": "simulated",
            "message": "Operation recorded but not executed (Paper-Only mode)",
            "operation": operation,
        }


paper_only_guard = PaperOnlyGuard()
