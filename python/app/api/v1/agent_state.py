"""
Agent State Management API Routes

Provides REST endpoints for:
- Agent state CRUD (list, get, save, delete)
- Checkpoint management (save, list, rollback)
- Context updates (incremental updates)
- Session recovery and resumption
- State cloning for A/B testing
- Checkpoint lifecycle management
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from app.api.v1.auth import get_current_user
from app.auth.permissions import require_permission
from app.core.response import api_response
from app.state.state_persistence import StatePersistenceManager, StateRecoveryManager
from app.models.agent_state import (
    AgentState,
    Checkpoint,
    CheckpointType,
    MemoryEntry,
)

router = APIRouter(prefix="/agents", tags=["Agent State Management"])


class _AgentStateHolder:
    """Thread-safe holder for agent state managers (initialized externally)."""

    def __init__(self) -> None:
        import threading

        self._lock = threading.Lock()
        self._persistence: Optional[StatePersistenceManager] = None
        self._recovery: Optional[StateRecoveryManager] = None

    def set_persistence(self, manager: StatePersistenceManager) -> None:
        """Set the persistence manager and (re)build the recovery manager."""
        with self._lock:
            self._persistence = manager
            self._recovery = StateRecoveryManager(manager)

    def get_persistence(self) -> Optional[StatePersistenceManager]:
        with self._lock:
            return self._persistence

    def get_recovery(self) -> Optional[StateRecoveryManager]:
        with self._lock:
            return self._recovery

    def reset(self) -> None:
        with self._lock:
            self._persistence = None
            self._recovery = None


_holder = _AgentStateHolder()


def get_persistence() -> StatePersistenceManager:
    """FastAPI 依赖：获取 :class:`StatePersistenceManager` 实例。

    Returns:
        :class:`StatePersistenceManager` 实例。

    Raises:
        HTTPException: 如果尚未通过 :func:`set_persistence_manager` 初始化则返回 503。
    """
    persistence = _holder.get_persistence()
    if persistence is None:
        raise HTTPException(
            status_code=503, detail="State persistence not initialized"
        )
    return persistence


def get_recovery() -> StateRecoveryManager:
    """FastAPI 依赖：获取 :class:`StateRecoveryManager` 实例。

    Returns:
        :class:`StateRecoveryManager` 实例。

    Raises:
        HTTPException: 如果尚未通过 :func:`set_persistence_manager` 初始化则返回 503。
    """
    recovery = _holder.get_recovery()
    if recovery is None:
        raise HTTPException(
            status_code=503, detail="State recovery not initialized"
        )
    return recovery


def set_persistence_manager(manager: StatePersistenceManager):
    """Initialize the agent state managers (typically called at app startup)."""
    _holder.set_persistence(manager)


@router.get("/")
async def list_agents(
    status: Optional[str] = Query(None, description="Filter by agent status"),
    persistence: StatePersistenceManager = Depends(get_persistence),
    _user: dict = Depends(get_current_user),
):
    require_permission(_user, "agents:read")
    agents = await persistence.list_all_agent_states()
    if status:
        agents = [a for a in agents if a.get("status") == status]
    return api_response(data=agents)


@router.get("/{agent_id}")
async def get_agent_state(
    agent_id: str,
    persistence: StatePersistenceManager = Depends(get_persistence),
    _user: dict = Depends(get_current_user),
):
    require_permission(_user, "agents:read")
    state = await persistence.load_state(agent_id)
    if not state:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found")
    return api_response(data=state.to_dict())


@router.post("/{agent_id}/save")
async def save_agent_state(
    agent_id: str,
    payload: dict,
    persistence: StatePersistenceManager = Depends(get_persistence),
    _user: dict = Depends(get_current_user),
):
    require_permission(_user, "agents:write")
    state = await persistence.load_state(agent_id)
    if state:
        for key, value in payload.items():
            if hasattr(state, key):
                setattr(state, key, value)
    else:
        state = AgentState(agent_id=agent_id, **payload)
    await persistence.save_state(state, trigger="api_manual")
    return api_response(data=state.to_dict(), message="Agent state saved")


@router.delete("/{agent_id}")
async def delete_agent_state(
    agent_id: str,
    persistence: StatePersistenceManager = Depends(get_persistence),
    _user: dict = Depends(get_current_user),
):
    require_permission(_user, "agents:admin")
    await persistence.delete_state(agent_id)
    return api_response(message=f"Agent '{agent_id}' state deleted")


@router.post("/{agent_id}/heartbeat/start")
async def start_heartbeat(
    agent_id: str,
    persistence: StatePersistenceManager = Depends(get_persistence),
    _user: dict = Depends(get_current_user),
):
    require_permission(_user, "agents:write")
    await persistence.start_heartbeat(agent_id)
    return api_response(message=f"Heartbeat started for agent '{agent_id}'")


@router.post("/{agent_id}/heartbeat/stop")
async def stop_heartbeat(
    agent_id: str,
    persistence: StatePersistenceManager = Depends(get_persistence),
    _user: dict = Depends(get_current_user),
):
    require_permission(_user, "agents:write")
    await persistence.stop_heartbeat(agent_id)
    return api_response(message=f"Heartbeat stopped for agent '{agent_id}'")


@router.post("/{agent_id}/checkpoints/save")
async def save_checkpoint(
    agent_id: str,
    payload: dict,
    persistence: StatePersistenceManager = Depends(get_persistence),
    _user: dict = Depends(get_current_user),
):
    require_permission(_user, "agents:write")
    checkpoint = Checkpoint(
        epoch=payload.get("epoch", 0),
        step=payload.get("step", 0),
        best_metric=payload.get("best_metric"),
        best_metric_name=payload.get("best_metric_name", "loss"),
        state_dict_path=payload.get("state_dict_path", ""),
        optimizer_state_path=payload.get("optimizer_state_path", ""),
        rng_state=payload.get("rng_state"),
        checkpoint_type=CheckpointType(payload.get("checkpoint_type", "manual")),
        metrics=payload.get("metrics", {}),
        metadata=payload.get("metadata", {}),
    )
    state = await persistence.save_checkpoint(agent_id, checkpoint, trigger="api")
    return api_response(data=state.to_dict(), message="Checkpoint saved")


@router.get("/{agent_id}/checkpoints")
async def list_checkpoints(
    agent_id: str,
    persistence: StatePersistenceManager = Depends(get_persistence),
    _user: dict = Depends(get_current_user),
):
    require_permission(_user, "agents:read")
    state = await persistence.load_state(agent_id)
    if not state:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found")
    checkpoints = [c.to_dict() for c in state.checkpoints_history]
    return api_response(data=checkpoints)


@router.post("/{agent_id}/checkpoints/rollback")
async def rollback_checkpoint(
    agent_id: str,
    payload: dict,
    persistence: StatePersistenceManager = Depends(get_persistence),
    _user: dict = Depends(get_current_user),
):
    require_permission(_user, "agents:write")
    checkpoint_id = payload.get("checkpoint_id")
    if not checkpoint_id:
        raise HTTPException(status_code=400, detail="checkpoint_id is required")
    state = await persistence.load_state(agent_id)
    if not state:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found")
    success = state.rollback_to_checkpoint(checkpoint_id)
    if not success:
        raise HTTPException(
            status_code=404, detail=f"Checkpoint '{checkpoint_id}' not found"
        )
    await persistence.save_state(state, trigger="rollback")
    return api_response(
        data=state.to_dict(), message=f"Rolled back to checkpoint '{checkpoint_id}'"
    )


@router.post("/{agent_id}/checkpoints/cleanup")
async def cleanup_checkpoints(
    agent_id: str,
    persistence: StatePersistenceManager = Depends(get_persistence),
    _user: dict = Depends(get_current_user),
):
    require_permission(_user, "agents:admin")
    removed = await persistence.cleanup_checkpoints(agent_id)
    return api_response(message=f"Cleaned up {removed} checkpoint files")


@router.post("/{agent_id}/context/update")
async def update_context(
    agent_id: str,
    payload: dict,
    persistence: StatePersistenceManager = Depends(get_persistence),
    _user: dict = Depends(get_current_user),
):
    require_permission(_user, "agents:write")
    updates = payload.get("updates", payload)
    state = await persistence.update_context_increment(agent_id, updates)
    return api_response(data=state.to_dict(), message="Context updated")


@router.post("/{agent_id}/memory/add")
async def add_memory(
    agent_id: str,
    payload: dict,
    persistence: StatePersistenceManager = Depends(get_persistence),
    _user: dict = Depends(get_current_user),
):
    require_permission(_user, "agents:write")
    state = await persistence.load_state(agent_id)
    if not state:
        state = AgentState(agent_id=agent_id)
    entry = MemoryEntry(
        content=payload.get("content", ""),
        memory_type=payload.get("memory_type", "observation"),
        importance=payload.get("importance", 0.5),
        tags=payload.get("tags", []),
        metadata=payload.get("metadata", {}),
    )
    state.add_memory(entry)
    await persistence.save_state(state, trigger="memory_add")
    return api_response(data=state.to_dict(), message="Memory entry added")


@router.post("/{agent_id}/memory/prune")
async def prune_memory(
    agent_id: str,
    persistence: StatePersistenceManager = Depends(get_persistence),
    _user: dict = Depends(get_current_user),
):
    require_permission(_user, "agents:write")
    state = await persistence.prune_memory(agent_id)
    return api_response(data=state.to_dict(), message="Memory pruned")


@router.post("/{agent_id}/resume")
async def resume_agent(
    agent_id: str,
    request: Request,
    persistence: StatePersistenceManager = Depends(get_persistence),
    recovery: StateRecoveryManager = Depends(get_recovery),
    _user: dict = Depends(get_current_user),
):
    require_permission(_user, "agents:write")
    result = await recovery.resume_agent(agent_id)
    return api_response(data=result)


@router.post("/{agent_id}/clone")
async def clone_agent(
    agent_id: str,
    payload: dict,
    persistence: StatePersistenceManager = Depends(get_persistence),
    recovery: StateRecoveryManager = Depends(get_recovery),
    _user: dict = Depends(get_current_user),
):
    require_permission(_user, "agents:write")
    target_id = payload.get("target_agent_id")
    if not target_id:
        raise HTTPException(status_code=400, detail="target_agent_id is required")
    clone = await recovery.clone_agent_state(agent_id, target_id)
    if not clone:
        raise HTTPException(
            status_code=404, detail=f"Source agent '{agent_id}' not found"
        )
    return api_response(
        data=clone.to_dict(), message=f"Cloned agent '{agent_id}' to '{target_id}'"
    )


@router.post("/{agent_id}/snapshot")
async def create_snapshot(
    agent_id: str,
    persistence: StatePersistenceManager = Depends(get_persistence),
    _user: dict = Depends(get_current_user),
):
    require_permission(_user, "agents:write")
    key = await persistence.snapshot_for_rollback(agent_id)
    if not key:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found")
    return api_response(message="Snapshot created", data={"snapshot_key": key})


@router.post("/{agent_id}/rollback")
async def rollback_state(
    agent_id: str,
    persistence: StatePersistenceManager = Depends(get_persistence),
    _user: dict = Depends(get_current_user),
):
    require_permission(_user, "agents:admin")
    state = await persistence.rollback_to_version(agent_id)
    if not state:
        raise HTTPException(status_code=404, detail="No rollback snapshot available")
    return api_response(data=state.to_dict(), message="Rollback successful")


@router.get("/{agent_id}/history")
async def get_state_history(
    agent_id: str,
    persistence: StatePersistenceManager = Depends(get_persistence),
    recovery: StateRecoveryManager = Depends(get_recovery),
    _user: dict = Depends(get_current_user),
):
    require_permission(_user, "agents:read")
    history = await recovery.get_recovery_history(agent_id)
    return api_response(data=history)
