"""Agent 状态 Repository（V3.0 Repository 层）。"""

from __future__ import annotations

from app.state.manager import StatePersistenceManager, get_state_persistence


class AgentStateRepo:
    def __init__(self, persistence: StatePersistenceManager):
        self._p = persistence

    async def save(self, state, trigger: str = ""):
        await self._p.save_state(state, trigger=trigger)

    async def load(self, agent_id: str):
        return await self._p.load_state(agent_id)


def get_agent_state_repo():
    return AgentStateRepo(get_state_persistence())
