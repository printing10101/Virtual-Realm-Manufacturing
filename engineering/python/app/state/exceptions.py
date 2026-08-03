"""
State Persistence System - Persistent Agent State & Session Recovery

References Paperclip's Persistent Agent State design:
- Three-tier storage: Redis (cache) + PostgreSQL (metadata) + Filesystem (checkpoints)
- Dual-trigger save: timer heartbeat (15min) + event-driven (epoch complete, status change)
- Async non-blocking save operations
- State compression for large contexts
- Checkpoint lifecycle management
- Multi-agent state isolation
- Permission-controlled state operations
- Comprehensive audit logging
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
import zlib
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

# shared imports moved to state/__init__.py
from app.models.agent_state import (
    AgentState,
    AgentStatus,
    Checkpoint,
    MemoryEntry,
    SessionContext,
    StateVersion,
    CURRENT_SCHEMA_VERSION,
    migrate_state,
)

HEARTBEAT_INTERVAL_SECONDS = 15 * 60
CHECKPOINT_MAX_AGE_SECONDS = 7 * 24 * 3600
CHECKPOINT_MAX_COUNT = 50
MAX_MEMORY_ENTRIES = 1000
MEMORY_PRUNING_THRESHOLD = 800
CONTEXT_COMPRESSION_THRESHOLD_BYTES = 1024 * 100
CHECKPOINT_BASE_DIR = "data/checkpoints"

logger = logging.getLogger(__name__)


class StatePersistenceError(Exception):
    pass


class StateConflictError(StatePersistenceError):
    pass


class StateNotFoundError(StatePersistenceError):
    pass
