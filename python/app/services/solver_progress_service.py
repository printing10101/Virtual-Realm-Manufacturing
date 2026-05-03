import asyncio
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class SolverProgressState:
    task_id: str
    phase_states: List[Dict[str, Any]] = field(default_factory=list)
    performance_report: Optional[Dict[str, Any]] = None
    is_active: bool = False
    can_terminate: bool = False
    termination_reason: str = ""
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "phase_states": self.phase_states,
            "performance_report": self.performance_report,
            "is_active": self.is_active,
            "can_terminate": self.can_terminate,
            "termination_reason": self.termination_reason,
            "updated_at": self.updated_at
        }


class SolverProgressService:
    _instance: Optional['SolverProgressService'] = None
    _progress_states: Dict[str, SolverProgressState] = {}
    _subscribers: Dict[str, List[asyncio.Queue]] = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def initialize_progress(self, task_id: str) -> None:
        self._progress_states[task_id] = SolverProgressState(task_id=task_id, is_active=True, can_terminate=True)

    def update_phase_progress(self, task_id: str, phase_data: Dict[str, Any]) -> None:
        state = self._progress_states.get(task_id)
        if not state:
            return

        existing_phase = None
        for ps in state.phase_states:
            if ps.get("phase") == phase_data.get("phase"):
                existing_phase = ps
                break

        if existing_phase:
            existing_phase.update(phase_data)
        else:
            state.phase_states.append(phase_data)

        state.updated_at = datetime.now().isoformat()

        self._notify_subscribers(task_id, {
            "event": "solver_phase_update",
            "task_id": task_id,
            "phase_data": phase_data,
            "state": state.to_dict()
        })

    def complete_solving(self, task_id: str, performance_report: Dict[str, Any]) -> None:
        state = self._progress_states.get(task_id)
        if state:
            state.is_active = False
            state.can_terminate = False
            state.performance_report = performance_report
            state.updated_at = datetime.now().isoformat()

            self._notify_subscribers(task_id, {
                "event": "solver_completed",
                "task_id": task_id,
                "state": state.to_dict()
            })

    def terminate_solving(self, task_id: str, reason: str) -> None:
        state = self._progress_states.get(task_id)
        if state:
            state.is_active = False
            state.can_terminate = False
            state.termination_reason = reason
            state.updated_at = datetime.now().isoformat()

            self._notify_subscribers(task_id, {
                "event": "solver_terminated",
                "task_id": task_id,
                "reason": reason,
                "state": state.to_dict()
            })

    def get_progress_state(self, task_id: str) -> Optional[SolverProgressState]:
        return self._progress_states.get(task_id)

    async def subscribe(self, task_id: str) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue()
        if task_id not in self._subscribers:
            self._subscribers[task_id] = []
        self._subscribers[task_id].append(queue)

        state = self._progress_states.get(task_id)
        if state:
            await queue.put({
                "event": "solver_state_snapshot",
                "task_id": task_id,
                "state": state.to_dict()
            })

        return queue

    def unsubscribe(self, task_id: str, queue: asyncio.Queue) -> None:
        if task_id in self._subscribers:
            try:
                self._subscribers[task_id].remove(queue)
            except ValueError:
                pass

    def _notify_subscribers(self, task_id: str, event: Dict[str, Any]) -> None:
        if task_id in self._subscribers:
            for queue in self._subscribers[task_id]:
                try:
                    queue.put_nowait(event)
                except asyncio.QueueFull:
                    pass

    def clear_task(self, task_id: str) -> None:
        self._progress_states.pop(task_id, None)
        self._subscribers.pop(task_id, None)


def get_solver_progress_service() -> SolverProgressService:
    return SolverProgressService()
