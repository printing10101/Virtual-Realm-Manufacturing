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


class CheckpointLifecycleManager:
    """Manages checkpoint file lifecycle to prevent disk space exhaustion"""

    def __init__(self, base_dir: str = CHECKPOINT_BASE_DIR):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def get_agent_checkpoint_dir(self, agent_id: str) -> Path:
        agent_dir = self.base_dir / agent_id
        agent_dir.mkdir(parents=True, exist_ok=True)
        return agent_dir

    def cleanup_agent_checkpoints(
        self,
        agent_id: str,
        max_age_seconds: float = CHECKPOINT_MAX_AGE_SECONDS,
        max_count: int = CHECKPOINT_MAX_COUNT,
    ) -> int:
        agent_dir = self.get_agent_checkpoint_dir(agent_id)
        now = time.time()
        removed = 0
        files = sorted(
            agent_dir.glob("*.pt"),
            key=lambda f: f.stat().st_mtime,
            reverse=True,
        )
        for f in files:
            if f.stat().st_mtime < now - max_age_seconds:
                f.unlink(missing_ok=True)
                removed += 1
        remaining = sorted(
            agent_dir.glob("*.pt"),
            key=lambda f: f.stat().st_mtime,
            reverse=True,
        )
        for f in remaining[max_count:]:
            f.unlink(missing_ok=True)
            removed += 1
        return removed

    def get_checkpoint_path(self, agent_id: str, checkpoint_id: str) -> Path:
        return self.get_agent_checkpoint_dir(agent_id) / f"{checkpoint_id}.pt"

    def size_bytes(self, agent_id: str) -> int:
        agent_dir = self.get_agent_checkpoint_dir(agent_id)
        return sum(f.stat().st_size for f in agent_dir.glob("*.pt"))

    def save_checkpoint_file(
        self, agent_id: str, checkpoint_id: str, data: bytes
    ) -> Path:
        path = self.get_checkpoint_path(agent_id, checkpoint_id)
        compressed = zlib.compress(data, level=6)
        path.write_bytes(compressed)
        return path

    def load_checkpoint_file(
        self, agent_id: str, checkpoint_id: str
    ) -> Optional[bytes]:
        path = self.get_checkpoint_path(agent_id, checkpoint_id)
        if not path.exists():
            return None
        compressed = path.read_bytes()
        return zlib.decompress(compressed)

    def remove_checkpoint(self, agent_id: str, checkpoint_id: str):
        path = self.get_checkpoint_path(agent_id, checkpoint_id)
        path.unlink(missing_ok=True)


class StateCompressor:
    """Compresses large session contexts to balance performance and storage"""

    @staticmethod
    def should_compress(context: SessionContext) -> bool:
        raw = json.dumps(context.to_dict(), ensure_ascii=False).encode("utf-8")
        return len(raw) > CONTEXT_COMPRESSION_THRESHOLD_BYTES

    @staticmethod
    def compress_context(context: SessionContext) -> bytes:
        raw = json.dumps(context.to_dict(), ensure_ascii=False).encode("utf-8")
        return zlib.compress(raw, level=6)

    @staticmethod
    def decompress_context(data: bytes) -> SessionContext:
        raw = zlib.decompress(data)
        return SessionContext.from_dict(json.loads(raw.decode("utf-8")))

    @staticmethod
    def compact_conversation_history(
        context: SessionContext, max_entries: int = 200
    ) -> SessionContext:
        if len(context.conversation_history) <= max_entries:
            return context
        context.conversation_history = context.conversation_history[-max_entries:]
        return context


class StateMigrationEngine:
    """Handles automatic state migration when schema changes"""

    def __init__(self):
        self._migrations: List[Dict[str, Any]] = []

    def register_migration(
        self, from_version: str, to_version: str, migrator: Callable[[Dict], Dict]
    ):
        self._migrations.append(
            {
                "from": from_version,
                "to": to_version,
                "migrator": migrator,
            }
        )

    def migrate(self, data: Dict[str, Any]) -> Dict[str, Any]:
        return migrate_state(data, CURRENT_SCHEMA_VERSION)

    def get_migration_path(self, from_version: str) -> List[str]:
        path = [from_version]
        visited = {from_version}
        changed = True
        while changed:
            changed = False
            for m in self._migrations:
                if m["from"] == path[-1] and m["to"] not in visited:
                    path.append(m["to"])
                    visited.add(m["to"])
                    changed = True
        return path


class StatePersistenceManager:
    """Core persistence manager with three-tier storage architecture"""

    def __init__(
        self,
        redis_client=None,
        db_session_factory=None,
        checkpoint_base_dir: str = CHECKPOINT_BASE_DIR,
    ):
        self._redis = redis_client
        self._db_session_factory = db_session_factory
        self._checkpoint_manager = CheckpointLifecycleManager(checkpoint_base_dir)
        self._compressor = StateCompressor()
        self._migration_engine = StateMigrationEngine()
        self._heartbeat_interval = HEARTBEAT_INTERVAL_SECONDS
        self._heartbeat_tasks: Dict[str, asyncio.Task] = {}
        self._save_locks: Dict[str, asyncio.Lock] = {}
        self._active_states: Dict[str, AgentState] = {}
        self._event_handlers: Dict[str, List[Callable]] = {}
        self._running = False

    @property
    def running(self) -> bool:
        return self._running

    def _get_lock(self, agent_id: str) -> asyncio.Lock:
        if agent_id not in self._save_locks:
            self._save_locks[agent_id] = asyncio.Lock()
        return self._save_locks[agent_id]

    def _redis_key(self, agent_id: str) -> str:
        return f"agent_state:{agent_id}"

    async def _save_redis(self, state: AgentState):
        if not self._redis:
            return
        try:
            key = self._redis_key(state.agent_id)
            data = json.dumps(state.to_dict(), ensure_ascii=False)
            await asyncio.to_thread(
                self._redis.setex, key, self._heartbeat_interval * 2, data
            )
        except Exception as e:
            logger.warning(
                "Failed to save heartbeat state to Redis: agent=%s error=%s",
                state.agent_id,
                e,
            )

    async def _load_redis(self, agent_id: str) -> Optional[AgentState]:
        if not self._redis:
            return None
        try:
            key = self._redis_key(agent_id)
            data = await asyncio.to_thread(self._redis.get, key)
            if data:
                raw = json.loads(
                    data.decode("utf-8") if isinstance(data, bytes) else data
                )
                raw = self._migration_engine.migrate(raw)
                return AgentState.from_dict(raw)
        except Exception as e:
            logger.warning(
                "Failed to load state from Redis: agent=%s error=%s", agent_id, e
            )
        return None

    async def _save_db(self, state: AgentState):
        if not self._db_session_factory:
            return
        try:
            session = await self._db_session_factory()
            json.dumps(state.to_dict(), ensure_ascii=False)
            compressed = self._compressor.should_compress(state.session_context)
            import sqlalchemy as sa

            result = await session.execute(
                sa.text("SELECT 1 FROM agent_states WHERE agent_id = :agent_id"),
                {"agent_id": state.agent_id},
            )
            exists = result.scalar() is not None

            if exists:
                await session.execute(
                    sa.text(
                        """UPDATE agent_states SET
                            current_task_id = :task_id,
                            session_context = :session_ctx,
                            memory_json = :memory,
                            checkpoint_json = :checkpoint,
                            last_heartbeat = to_timestamp(:hb),
                            status = :status,
                            state_version = :sv,
                            updated_at = NOW(),
                            metadata_json = :meta,
                            compressed = :compressed
                        WHERE agent_id = :agent_id"""
                    ),
                    {
                        "agent_id": state.agent_id,
                        "task_id": state.current_task_id,
                        "session_ctx": json.dumps(
                            state.session_context.to_dict(), ensure_ascii=False
                        ),
                        "memory": json.dumps(
                            [m.to_dict() for m in state.memory], ensure_ascii=False
                        ),
                        "checkpoint": json.dumps(
                            state.checkpoint.to_dict(), ensure_ascii=False
                        )
                        if state.checkpoint
                        else None,
                        "hb": state.last_heartbeat,
                        "status": state.status.value,
                        "sv": json.dumps(
                            state.state_version.to_dict(), ensure_ascii=False
                        ),
                        "meta": json.dumps(state.metadata, ensure_ascii=False),
                        "compressed": compressed,
                    },
                )
            else:
                await session.execute(
                    sa.text(
                        """INSERT INTO agent_states
                            (agent_id, current_task_id, session_context, memory_json, checkpoint_json,
                             last_heartbeat, status, checkpoints_history_json, state_version,
                             created_at, updated_at, metadata_json, compressed)
                        VALUES
                            (:agent_id, :task_id, :session_ctx, :memory, :checkpoint,
                             to_timestamp(:hb), :status, :chk_hist, :sv,
                             NOW(), NOW(), :meta, :compressed)"""
                    ),
                    {
                        "agent_id": state.agent_id,
                        "task_id": state.current_task_id,
                        "session_ctx": json.dumps(
                            state.session_context.to_dict(), ensure_ascii=False
                        ),
                        "memory": json.dumps(
                            [m.to_dict() for m in state.memory], ensure_ascii=False
                        ),
                        "checkpoint": json.dumps(
                            state.checkpoint.to_dict(), ensure_ascii=False
                        )
                        if state.checkpoint
                        else None,
                        "hb": state.last_heartbeat,
                        "status": state.status.value,
                        "chk_hist": json.dumps(
                            [c.to_dict() for c in state.checkpoints_history],
                            ensure_ascii=False,
                        ),
                        "sv": json.dumps(
                            state.state_version.to_dict(), ensure_ascii=False
                        ),
                        "meta": json.dumps(state.metadata, ensure_ascii=False),
                        "compressed": compressed,
                    },
                )
            await session.commit()
            await session.close()
        except Exception as e:
            logger.error("DB save failed for agent %s: %s", state.agent_id, e)

    async def _load_db(self, agent_id: str) -> Optional[AgentState]:
        if not self._db_session_factory:
            return None
        try:
            session = await self._db_session_factory()
            import sqlalchemy as sa

            result = await session.execute(
                sa.text(
                    """SELECT
                        agent_id, current_task_id, session_context, memory_json,
                        checkpoint_json, last_heartbeat, status, checkpoints_history_json,
                        state_version, created_at, updated_at, metadata_json
                    FROM agent_states WHERE agent_id = :agent_id"""
                ),
                {"agent_id": agent_id},
            )
            row = result.fetchone()
            await session.close()
            if not row:
                return None

            session_ctx = json.loads(row.session_context) if row.session_context else {}
            memory = json.loads(row.memory_json) if row.memory_json else []
            checkpoint = (
                json.loads(row.checkpoint_json) if row.checkpoint_json else None
            )
            chk_hist = (
                json.loads(row.checkpoints_history_json)
                if row.checkpoints_history_json
                else []
            )
            state_ver = json.loads(row.state_version) if row.state_version else {}
            metadata = json.loads(row.metadata_json) if row.metadata_json else {}

            state = AgentState(
                agent_id=row.agent_id,
                current_task_id=row.current_task_id,
                session_context=SessionContext.from_dict(session_ctx),
                memory=[MemoryEntry.from_dict(m) for m in memory],
                checkpoint=Checkpoint.from_dict(checkpoint) if checkpoint else None,
                last_heartbeat=float(row.last_heartbeat.timestamp())
                if hasattr(row.last_heartbeat, "timestamp")
                else row.last_heartbeat,
                status=AgentStatus(row.status),
                checkpoints_history=[Checkpoint.from_dict(c) for c in chk_hist],
                state_version=StateVersion.from_dict(state_ver),
                created_at=float(row.created_at.timestamp())
                if hasattr(row.created_at, "timestamp")
                else row.created_at,
                updated_at=float(row.updated_at.timestamp())
                if hasattr(row.updated_at, "timestamp")
                else row.updated_at,
                metadata=metadata,
            )
            return state
        except Exception as e:
            logger.error("DB load failed for agent %s: %s", agent_id, e)
        return None

    async def _save_checkpoint_files(self, state: AgentState):
        if not state.checkpoint:
            return
        agent_id = state.agent_id
        ckpt = state.checkpoint
        if ckpt.state_dict_path and os.path.exists(ckpt.state_dict_path):
            data = Path(ckpt.state_dict_path).read_bytes()
            path = self._checkpoint_manager.save_checkpoint_file(
                agent_id, ckpt.checkpoint_id, data
            )
            ckpt.file_size_bytes = os.path.getsize(path)

    async def _load_checkpoint_files(self, state: AgentState):
        if not state.checkpoint:
            return
        agent_id = state.agent_id
        ckpt = state.checkpoint
        data = self._checkpoint_manager.load_checkpoint_file(
            agent_id, ckpt.checkpoint_id
        )
        if data:
            temp_path = self._checkpoint_manager.get_checkpoint_path(
                agent_id, ckpt.checkpoint_id
            )
            ckpt.state_dict_path = str(temp_path.with_suffix(".restored.pt"))
            Path(ckpt.state_dict_path).write_bytes(data)

    async def save_state(
        self, state: AgentState, trigger: str = "manual"
    ) -> AgentState:
        """Atomic save to all three storage tiers"""
        lock = self._get_lock(state.agent_id)
        async with lock:
            state.update_heartbeat()
            tasks = []
            tasks.append(asyncio.create_task(self._save_redis(state)))
            tasks.append(asyncio.create_task(self._save_db(state)))
            tasks.append(asyncio.create_task(self._save_checkpoint_files(state)))
            await asyncio.gather(*tasks, return_exceptions=True)
            self._active_states[state.agent_id] = state
            logger.info(
                "State saved: agent=%s trigger=%s status=%s",
                state.agent_id,
                trigger,
                state.status.value,
            )
            return state

    async def load_state(self, agent_id: str) -> Optional[AgentState]:
        """Load state from fastest available storage tier"""
        if agent_id in self._active_states:
            return self._active_states[agent_id]
        state = await self._load_redis(agent_id)
        if state:
            self._active_states[agent_id] = state
            return state
        state = await self._load_db(agent_id)
        if state:
            self._active_states[agent_id] = state
            await self._save_redis(state)
            logger.info("State loaded from DB: agent=%s", agent_id)
            return state
        return None

    async def delete_state(self, agent_id: str):
        if self._redis:
            try:
                await asyncio.to_thread(self._redis.delete, self._redis_key(agent_id))
            except Exception as e:
                logger.warning(
                    "Failed to delete state from Redis: agent=%s error=%s", agent_id, e
                )
        if self._db_session_factory:
            try:
                session = await self._db_session_factory()
                import sqlalchemy as sa

                await session.execute(
                    sa.text("DELETE FROM agent_states WHERE agent_id = :agent_id"),
                    {"agent_id": agent_id},
                )
                await session.commit()
                await session.close()
            except (OSError, sa.exc.SQLAlchemyError, RuntimeError) as e:
                # 数据库删除失败不应阻塞内存状态清理
                logger.warning(
                    f"Failed to delete agent state from DB for {agent_id}: {e}",
                    exc_info=True,
                )
        self._active_states.pop(agent_id, None)
        self._stop_heartbeat(agent_id)
        self._checkpoint_manager.cleanup_agent_checkpoints(agent_id, max_age_seconds=0)
        logger.info("State deleted: agent=%s", agent_id)

    async def save_checkpoint(
        self,
        agent_id: str,
        checkpoint: Checkpoint,
        trigger: str = "auto",
    ) -> AgentState:
        state = await self.load_state(agent_id)
        if not state:
            state = AgentState(agent_id=agent_id)
        state.set_checkpoint(checkpoint)
        await self.save_state(state, trigger=f"checkpoint_{trigger}")
        return state

    async def update_context_increment(
        self,
        agent_id: str,
        updates: Dict[str, Any],
        trigger: str = "incremental",
    ) -> AgentState:
        state = await self.load_state(agent_id)
        if not state:
            state = AgentState(agent_id=agent_id)
        state.add_context_increment(updates)
        await self.save_state(state, trigger=f"context_{trigger}")
        return state

    async def prune_memory(self, agent_id: str) -> AgentState:
        state = await self.load_state(agent_id)
        if not state:
            return AgentState(agent_id=agent_id)
        if len(state.memory) > MAX_MEMORY_ENTRIES:
            state.memory.sort(key=lambda m: m.importance, reverse=True)
            state.memory = state.memory[:MEMORY_PRUNING_THRESHOLD]
            await self.save_state(state, trigger="memory_prune")
        return state

    async def cleanup_checkpoints(self, agent_id: str) -> int:
        return self._checkpoint_manager.cleanup_agent_checkpoints(agent_id)

    def _start_heartbeat(self, agent_id: str):
        if agent_id in self._heartbeat_tasks:
            return
        self._heartbeat_tasks[agent_id] = asyncio.create_task(
            self._heartbeat_loop(agent_id)
        )

    def _stop_heartbeat(self, agent_id: str):
        task = self._heartbeat_tasks.pop(agent_id, None)
        if task and not task.done():
            task.cancel()

    async def _heartbeat_loop(self, agent_id: str):
        while self._running:
            await asyncio.sleep(self._heartbeat_interval)
            try:
                state = await self.load_state(agent_id)
                if state:
                    state.update_heartbeat()
                    await self.save_state(state, trigger="heartbeat")
            except asyncio.CancelledError:
                break
            except (OSError, RuntimeError, AttributeError, KeyError) as e:
                # 心跳循环中单次失败不应中断后续心跳，记录后继续
                logger.debug(
                    f"Heartbeat iteration failed for {agent_id}: {e}",
                    exc_info=True,
                )

    async def start_heartbeat(self, agent_id: str):
        self._start_heartbeat(agent_id)

    async def stop_heartbeat(self, agent_id: str):
        self._stop_heartbeat(agent_id)

    async def snapshot_for_rollback(self, agent_id: str) -> Optional[str]:
        """Create a snapshot and return its version identifier"""
        state = await self.load_state(agent_id)
        if not state:
            return None
        rollback_key = f"agent_state_rollback:{agent_id}"
        if self._redis:
            try:
                data = json.dumps(state.to_dict(), ensure_ascii=False)
                await asyncio.to_thread(
                    self._redis.setex, rollback_key, 86400 * 7, data
                )
            except (TypeError, ValueError, ConnectionError, OSError) as e:
                # Redis 回滚快照写入失败不应阻塞当前状态保存
                logger.warning(
                    f"Failed to write rollback snapshot to Redis for {agent_id}: {e}",
                    exc_info=True,
                )
        return rollback_key

    async def rollback_to_version(self, agent_id: str) -> Optional[AgentState]:
        rollback_key = f"agent_state_rollback:{agent_id}"
        if not self._redis:
            return None
        try:
            data = await asyncio.to_thread(self._redis.get, rollback_key)
            if not data:
                return None
            raw = json.loads(data.decode("utf-8") if isinstance(data, bytes) else data)
            raw = self._migration_engine.migrate(raw)
            state = AgentState.from_dict(raw)
            await self.save_state(state, trigger="rollback")
            return state
        except Exception:
            return None

    def on_event(self, event: str):
        def decorator(func: Callable):
            self._event_handlers.setdefault(event, [])
            self._event_handlers[event].append(func)
            return func

        return decorator

    async def emit_event(self, event: str, agent_id: str, data: Optional[Dict] = None):
        handlers = self._event_handlers.get(event, [])
        for handler in handlers:
            try:
                if data is not None:
                    await handler(agent_id, data)
                else:
                    await handler(agent_id)
            except (TypeError, ValueError, RuntimeError, AttributeError) as e:
                # 单个事件处理器失败不应阻塞其他处理器执行
                logger.warning(
                    f"Event handler {getattr(handler, '__name__', repr(handler))} "
                    f"failed for event {event}, agent {agent_id}: {e}",
                    exc_info=True,
                )

    async def start(self):
        self._running = True

    async def stop(self):
        self._running = False
        for agent_id, task in list(self._heartbeat_tasks.items()):
            self._stop_heartbeat(agent_id)
        for agent_id, state in list(self._active_states.items()):
            try:
                state.status = AgentStatus.STOPPED
                await self.save_state(state, trigger="pre_shutdown")
            except (OSError, RuntimeError, AttributeError) as e:
                # 关闭时单 agent 状态保存失败不应阻塞其他 agent 的关闭流程
                logger.warning(
                    f"Failed to save pre-shutdown state for {agent_id}: {e}",
                    exc_info=True,
                )
        self._active_states.clear()
        self._heartbeat_tasks.clear()

    async def list_all_agent_states(self) -> List[Dict[str, Any]]:
        if not self._db_session_factory:
            return [
                {
                    "agent_id": aid,
                    "status": s.status.value,
                    "current_task_id": s.current_task_id,
                    "last_heartbeat": s.last_heartbeat,
                }
                for aid, s in self._active_states.items()
            ]
        try:
            session = await self._db_session_factory()
            import sqlalchemy as sa

            result = await session.execute(
                sa.text(
                    """SELECT agent_id, status, current_task_id, last_heartbeat, updated_at
                    FROM agent_states ORDER BY updated_at DESC"""
                )
            )
            rows = result.fetchall()
            await session.close()
            return [
                {
                    "agent_id": r.agent_id,
                    "status": r.status,
                    "current_task_id": r.current_task_id,
                    "last_heartbeat": r.last_heartbeat.isoformat()
                    if hasattr(r.last_heartbeat, "isoformat")
                    else r.last_heartbeat,
                    "updated_at": r.updated_at.isoformat()
                    if hasattr(r.updated_at, "isoformat")
                    else r.updated_at,
                }
                for r in rows
            ]
        except Exception:
            return [
                {
                    "agent_id": aid,
                    "status": s.status.value,
                    "current_task_id": s.current_task_id,
                    "last_heartbeat": s.last_heartbeat,
                    "updated_at": s.updated_at,
                }
                for aid, s in self._active_states.items()
            ]


class StateRecoveryManager:
    """Handles agent state recovery and session resumption"""

    def __init__(self, persistence: StatePersistenceManager):
        self._persistence = persistence

    async def resume_agent(
        self,
        agent_id: str,
        task_loader: Optional[Callable[[str], Any]] = None,
        task_runner: Optional[Callable[[str, Optional[Checkpoint]], Any]] = None,
    ) -> Dict[str, Any]:
        """
        Resume an agent from its persisted state.
        Returns a dict with recovery status and details.
        """
        result = {
            "agent_id": agent_id,
            "recovered": False,
            "action": "no_state_found",
            "state": None,
            "task": None,
            "checkpoint_used": None,
            "error": None,
        }
        try:
            state = await self._persistence.load_state(agent_id)
            if not state:
                state = AgentState(agent_id=agent_id)
                state.status = AgentStatus.IDLE
                await self._persistence.save_state(state, trigger="recovery_new")
                result["state"] = state
                return result
            state.status = AgentStatus.RECOVERING
            await self._persistence.save_state(state, trigger="recovery_start")
            if not state.current_task_id:
                state.status = AgentStatus.IDLE
                await self._persistence.save_state(state, trigger="recovery_no_task")
                result["recovered"] = True
                result["action"] = "idle_resume"
                result["state"] = state
                return result
            if not task_loader:
                state.status = AgentStatus.IDLE
                await self._persistence.save_state(state, trigger="recovery_no_loader")
                result["recovered"] = True
                result["action"] = "idle_no_loader"
                result["state"] = state
                return result
            task = (
                await task_loader(state.current_task_id)
                if asyncio.iscoroutinefunction(task_loader)
                else task_loader(state.current_task_id)
            )
            if not task:
                state.current_task_id = None
                state.status = AgentStatus.IDLE
                await self._persistence.save_state(
                    state, trigger="recovery_task_not_found"
                )
                result["recovered"] = True
                result["action"] = "idle_task_gone"
                result["state"] = state
                return result
            task_status = getattr(task, "status", None)
            task_status_str = (
                task_status.value if hasattr(task_status, "value") else str(task_status)
            )
            result["task"] = {
                "task_id": state.current_task_id,
                "status": task_status_str,
            }
            if task_status and task_status_str in ("in_progress", "running"):
                if state.checkpoint and task_runner:
                    try:
                        (
                            await task_runner(state.current_task_id, state.checkpoint)
                            if asyncio.iscoroutinefunction(task_runner)
                            else task_runner(state.current_task_id, state.checkpoint)
                        )
                        state.status = AgentStatus.BUSY
                        await self._persistence.save_state(
                            state, trigger="recovery_resumed"
                        )
                        result["recovered"] = True
                        result["action"] = "resumed_with_checkpoint"
                        result["checkpoint_used"] = state.checkpoint.checkpoint_id
                        result["state"] = state
                        return result
                    except Exception as e:
                        from app.core.safe_errors import safe_error_message

                        safe = safe_error_message(
                            e,
                            context="state_persistence.resume_with_checkpoint",
                            fallback="从检查点恢复失败",
                        )
                        result["error"] = safe["message"]
                        result["error_id"] = safe["error_id"]
                if task_runner:
                    try:
                        (
                            await task_runner(state.current_task_id, None)
                            if asyncio.iscoroutinefunction(task_runner)
                            else task_runner(state.current_task_id, None)
                        )
                        state.status = AgentStatus.BUSY
                        await self._persistence.save_state(
                            state, trigger="recovery_restarted"
                        )
                        result["recovered"] = True
                        result["action"] = "restarted_without_checkpoint"
                        result["state"] = state
                        return result
                    except Exception as e:
                        from app.core.safe_errors import safe_error_message

                        safe = safe_error_message(
                            e,
                            context="state_persistence.restart_without_checkpoint",
                            fallback="无检查点重启失败",
                        )
                        result["error"] = safe["message"]
                        result["error_id"] = safe["error_id"]
                state.status = AgentStatus.IDLE
                await self._persistence.save_state(
                    state, trigger="recovery_fallback_idle"
                )
                result["recovered"] = True
                result["action"] = "fallback_idle"
                result["state"] = state
                return result
            else:
                state.status = AgentStatus.IDLE
                await self._persistence.save_state(
                    state, trigger="recovery_task_complete"
                )
                result["recovered"] = True
                result["action"] = "idle_task_done"
                result["state"] = state
                return result
        except Exception as e:
            from app.core.safe_errors import safe_error_message

            safe = safe_error_message(
                e,
                context="state_persistence.recover",
                fallback="状态恢复失败",
            )
            result["error"] = safe["message"]
            result["error_id"] = safe["error_id"]
            result["action"] = "recovery_failed"
            try:
                fallback_state = AgentState(agent_id=agent_id)
                fallback_state.status = AgentStatus.IDLE
                await self._persistence.save_state(
                    fallback_state, trigger="recovery_fallback"
                )
                result["state"] = fallback_state
            except (OSError, RuntimeError, AttributeError) as e:
                # 恢复回退状态失败时仅记录，仍返回已有恢复信息
                logger.warning(
                    f"Failed to write recovery fallback state for {agent_id}: {e}",
                    exc_info=True,
                )
            return result

    async def clone_agent_state(
        self,
        source_agent_id: str,
        target_agent_id: str,
    ) -> Optional[AgentState]:
        source = await self._persistence.load_state(source_agent_id)
        if not source:
            return None
        clone = source.clone(target_agent_id)
        await self._persistence.save_state(clone, trigger="clone")
        return clone

    async def get_recovery_history(self, agent_id: str) -> List[Dict[str, Any]]:
        state = await self._persistence.load_state(agent_id)
        if not state:
            return []
        return state.state_version.migration_history


async def create_state_persistence(
    redis_url: Optional[str] = None,
    db_url: Optional[str] = None,
    checkpoint_dir: str = CHECKPOINT_BASE_DIR,
) -> StatePersistenceManager:
    redis_client = None
    db_session_factory = None

    if redis_url:
        try:
            import redis.asyncio as aioredis

            redis_client = aioredis.from_url(redis_url, decode_responses=False)
        except ImportError:
            try:
                import redis

                redis_client = redis.from_url(redis_url, decode_responses=False)
            except (ImportError, ConnectionError, ValueError) as e:
                # Redis 可选依赖未安装或连接失败时跳过（系统可降级为仅 DB 存储）
                logger.debug(
                    f"Failed to initialize Redis client: {e}",
                    exc_info=True,
                )

    if db_url:
        try:
            from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

            async_url = db_url
            if async_url.startswith("postgresql://"):
                async_url = async_url.replace(
                    "postgresql://", "postgresql+asyncpg://", 1
                )
            elif async_url.startswith("sqlite://"):
                async_url = async_url.replace("sqlite://", "sqlite+aiosqlite://", 1)

            engine = create_async_engine(async_url, echo=False)
            sessionmaker = async_sessionmaker(engine, expire_on_commit=False)

            async def session_factory():
                return sessionmaker()

            async with engine.begin() as conn:
                import sqlalchemy as sa

                await conn.execute(
                    sa.text(
                        """CREATE TABLE IF NOT EXISTS agent_states (
                            agent_id VARCHAR(128) PRIMARY KEY,
                            current_task_id VARCHAR(128),
                            session_context JSONB DEFAULT '{}',
                            memory_json JSONB DEFAULT '[]',
                            checkpoint_json JSONB DEFAULT NULL,
                            last_heartbeat TIMESTAMPTZ DEFAULT NOW(),
                            status VARCHAR(32) DEFAULT 'idle',
                            checkpoints_history_json JSONB DEFAULT '[]',
                            state_version JSONB DEFAULT '{}',
                            created_at TIMESTAMPTZ DEFAULT NOW(),
                            updated_at TIMESTAMPTZ DEFAULT NOW(),
                            metadata_json JSONB DEFAULT '{}',
                            compressed BOOLEAN DEFAULT FALSE
                        )"""
                    )
                )
                await conn.execute(
                    sa.text(
                        "CREATE INDEX IF NOT EXISTS idx_agent_states_status ON agent_states (status)"
                    )
                )
                await conn.execute(
                    sa.text(
                        "CREATE INDEX IF NOT EXISTS idx_agent_states_heartbeat ON agent_states (last_heartbeat)"
                    )
                )
            db_session_factory = session_factory
        except Exception:
            try:
                from sqlalchemy import create_engine, text

                sync_url = db_url
                if sync_url.startswith("postgresql+asyncpg://"):
                    sync_url = sync_url.replace(
                        "postgresql+asyncpg://", "postgresql://", 1
                    )
                sync_engine = create_engine(sync_url, echo=False)
                with sync_engine.begin() as conn:
                    conn.execute(
                        text(
                            """CREATE TABLE IF NOT EXISTS agent_states (
                                agent_id VARCHAR(128) PRIMARY KEY,
                                current_task_id VARCHAR(128),
                                session_context TEXT DEFAULT '{}',
                                memory_json TEXT DEFAULT '[]',
                                checkpoint_json TEXT DEFAULT NULL,
                                last_heartbeat TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                                status VARCHAR(32) DEFAULT 'idle',
                                checkpoints_history_json TEXT DEFAULT '[]',
                                state_version TEXT DEFAULT '{}',
                                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                                metadata_json TEXT DEFAULT '{}',
                                compressed BOOLEAN DEFAULT FALSE
                            )"""
                        )
                    )
                from sqlalchemy.orm import Session  # noqa: F811

                def db_session_factory():
                    return Session(sync_engine)
            except Exception:
                db_session_factory = None

    return StatePersistenceManager(
        redis_client=redis_client,
        db_session_factory=db_session_factory,
        checkpoint_base_dir=checkpoint_dir,
    )
