"""
Goal Alignment API Routes

Endpoints for goal hierarchy management, task goal association,
alignment verification, and progress tracking.
"""

from __future__ import annotations

import time
import uuid
import logging
from typing import Optional

from fastapi import APIRouter, Query

from app.core.response import ErrorCode, error, success
from app.core.goal_chain_store import get_goal_chain_store
from app.core.goal_alignment import GoalAlignmentChecker, GoalAlignmentError
from app.models.goals import (
    Goal,
    GoalLevel,
    GoalStatus,
)
from app.models.tasks import (
    EnhancedTask,
    EnhancedTaskType,
    EnhancedTaskStatus,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/goal-alignment", tags=["Goal Alignment"])

_alignment_checker: Optional[GoalAlignmentChecker] = None


def get_alignment_checker() -> GoalAlignmentChecker:
    global _alignment_checker
    if _alignment_checker is None:
        _alignment_checker = GoalAlignmentChecker()
    return _alignment_checker


@router.get("/goals/tree")
async def get_goal_tree():
    store = get_goal_chain_store()
    tree = store.get_goal_tree()
    return success(data=tree, message="Goal tree retrieved")


@router.get("/goals")
async def list_goals(
    level: Optional[str] = Query(
        None, description="Filter by level: mission/strategic_goal/project/task"
    ),
):
    store = get_goal_chain_store()
    lvl = GoalLevel(level) if level else None
    goals = store.get_all_goals(lvl)
    return success(data=[g.to_dict() for g in goals], message="Goals retrieved")


@router.get("/goals/{goal_id}")
async def get_goal(goal_id: str):
    store = get_goal_chain_store()
    goal = store.get_goal(goal_id)
    if goal is None:
        return error(code=ErrorCode.NOT_FOUND, message=f"Goal '{goal_id}' not found")
    return success(data=goal.to_dict(), message="Goal retrieved")


@router.get("/goals/{goal_id}/chain")
async def get_goal_chain(goal_id: str):
    store = get_goal_chain_store()
    chain = store.resolve_goal_chain(goal_id)
    return success(data=[ref.to_dict() for ref in chain], message="Goal chain resolved")


@router.get("/goals/{goal_id}/children")
async def get_goal_children(goal_id: str):
    store = get_goal_chain_store()
    goal = store.get_goal(goal_id)
    if goal is None:
        return error(code=ErrorCode.NOT_FOUND, message=f"Goal '{goal_id}' not found")
    children = store.get_children(goal_id)
    return success(data=[c.to_dict() for c in children], message="Children retrieved")


@router.get("/goals/{goal_id}/progress")
async def get_goal_progress(goal_id: str):
    checker = get_alignment_checker()
    progress = checker.compute_goal_progress(goal_id)
    return success(data=progress.to_dict(), message="Progress computed")


@router.get("/goals/{goal_id}/history")
async def get_goal_history(goal_id: str, limit: int = Query(50, ge=1, le=200)):
    store = get_goal_chain_store()
    goal = store.get_goal(goal_id)
    if goal is None:
        return error(code=ErrorCode.NOT_FOUND, message=f"Goal '{goal_id}' not found")
    versions = store.get_version_history(goal_id, limit)
    return success(
        data=[v.to_dict() for v in versions], message="Version history retrieved"
    )


@router.post("/goals")
async def create_goal(data: dict):
    store = get_goal_chain_store()

    try:
        level = GoalLevel(data.get("level", "task"))
        status = GoalStatus(data.get("status", "not_started"))
    except ValueError as e:
        return error(code=ErrorCode.INVALID_REQUEST, message=f"Invalid enum value: {e}")

    goal_id = data.get("id", f"{level.value}-{uuid.uuid4().hex[:8]}")
    goal = Goal(
        id=goal_id,
        name=data.get("name", ""),
        description=data.get("description", ""),
        level=level,
        parent_id=data.get("parent_id"),
        status=status,
        created_at=time.time(),
    )

    if goal.level != GoalLevel.MISSION and goal.parent_id is None:
        return error(
            code=ErrorCode.INVALID_REQUEST,
            message="Non-mission goals must have a parent_id",
        )

    existing = store.get_goal(goal_id)
    if existing:
        return error(
            code=ErrorCode.INVALID_REQUEST, message=f"Goal '{goal_id}' already exists"
        )

    store.add_goal(goal)
    return success(data=goal.to_dict(), message="Goal created")


@router.put("/goals/{goal_id}")
async def update_goal(goal_id: str, data: dict):
    store = get_goal_chain_store()
    checker = get_alignment_checker()

    updatable = {}
    if "name" in data:
        updatable["name"] = data["name"]
    if "description" in data:
        updatable["description"] = data["description"]
    if "status" in data:
        try:
            updatable["status"] = GoalStatus(data["status"])
        except ValueError:
            return error(
                code=ErrorCode.INVALID_REQUEST,
                message=f"Invalid status: {data['status']}",
            )
    if "parent_id" in data:
        updatable["parent_id"] = data["parent_id"]

    if not updatable:
        return error(code=ErrorCode.INVALID_REQUEST, message="No fields to update")

    goal = store.update_goal(goal_id, **updatable)
    if goal is None:
        return error(code=ErrorCode.NOT_FOUND, message=f"Goal '{goal_id}' not found")

    if goal.status == GoalStatus.CANCELLED:
        checker.propagate_goal_change(goal_id)

    return success(data=goal.to_dict(), message="Goal updated")


@router.delete("/goals/{goal_id}")
async def delete_goal(goal_id: str):
    store = get_goal_chain_store()
    goal = store.get_goal(goal_id)
    if goal is None:
        return error(code=ErrorCode.NOT_FOUND, message=f"Goal '{goal_id}' not found")
    if goal.level == GoalLevel.MISSION:
        return error(
            code=ErrorCode.INVALID_REQUEST, message="Cannot delete the mission"
        )

    store.delete_goal(goal_id)
    return success(message="Goal deleted")


@router.post("/tasks")
async def create_task(data: dict):
    store = get_goal_chain_store()
    checker = get_alignment_checker()

    try:
        task_type = EnhancedTaskType(data["task_type"])
    except (KeyError, ValueError):
        valid = [t.value for t in EnhancedTaskType]
        return error(
            code=ErrorCode.INVALID_REQUEST,
            message=f"Invalid task_type. Must be one of: {valid}",
        )

    parent_goal_id = data.get("parent_goal_id")
    if not parent_goal_id:
        return error(
            code=ErrorCode.INVALID_REQUEST,
            message="parent_goal_id is required. All tasks must be associated with a parent goal.",
        )

    goal = store.get_goal(parent_goal_id)
    if goal is None:
        return error(
            code=ErrorCode.NOT_FOUND,
            message=f"Parent goal '{parent_goal_id}' not found",
        )

    chain = store.resolve_goal_chain(parent_goal_id)
    if not chain:
        return error(
            code=ErrorCode.INVALID_REQUEST,
            message=f"Cannot resolve goal chain for '{parent_goal_id}'",
        )

    task_id = data.get("id", f"task-{uuid.uuid4().hex[:8]}")
    task = EnhancedTask(
        id=task_id,
        title=data.get("title", ""),
        description=data.get("description", ""),
        task_type=task_type,
        goal_chain=chain,
        blockers=data.get("blockers", []),
        params=data.get("params"),
    )

    try:
        checker.validate_task_goal_chain(task)
    except GoalAlignmentError as e:
        return error(code=ErrorCode.INVALID_REQUEST, message=str(e))

    checker.register_task(task)

    context = checker.build_task_context(task)

    return success(
        data={
            "task": task.to_dict(),
            "context": context,
        },
        message="Task created with goal alignment",
    )


@router.post("/tasks/{task_id}/status")
async def update_task_status(task_id: str, data: dict):
    checker = get_alignment_checker()

    try:
        new_status = EnhancedTaskStatus(data["status"])
    except (KeyError, ValueError):
        valid = [s.value for s in EnhancedTaskStatus]
        return error(
            code=ErrorCode.INVALID_REQUEST,
            message=f"Invalid status. Must be one of: {valid}",
        )

    if task_id not in checker._task_map:
        return error(code=ErrorCode.NOT_FOUND, message=f"Task '{task_id}' not found")

    task = checker._task_map[task_id]
    if not task.can_transition_to(new_status):
        return error(
            code=ErrorCode.INVALID_REQUEST,
            message=f"Cannot transition from {task.status.value} to {new_status.value}",
        )

    if new_status == EnhancedTaskStatus.IN_PROGRESS and not task.are_blockers_resolved(
        set(
            tid
            for tid, t in checker._task_map.items()
            if t.status == EnhancedTaskStatus.COMPLETED
        )
    ):
        return error(
            code=ErrorCode.INVALID_REQUEST,
            message=f"Task has unresolved blockers: {task.blockers}",
        )

    checker.update_task_status(task_id, new_status)

    return success(
        data={"task_id": task_id, "status": new_status.value},
        message="Task status updated",
    )


@router.get("/tasks/{task_id}/context")
async def get_task_context(task_id: str):
    checker = get_alignment_checker()

    if task_id not in checker._task_map:
        return error(code=ErrorCode.NOT_FOUND, message=f"Task '{task_id}' not found")

    task = checker._task_map[task_id]
    context = checker.build_task_context(task)
    return success(data=context, message="Task context retrieved")


@router.get("/tasks/{task_id}/alignment")
async def check_task_alignment(task_id: str):
    checker = get_alignment_checker()

    if task_id not in checker._task_map:
        return error(code=ErrorCode.NOT_FOUND, message=f"Task '{task_id}' not found")

    task = checker._task_map[task_id]
    try:
        checker.validate_task_goal_chain(task)
        return success(
            data={
                "task_id": task_id,
                "aligned": True,
                "chain_length": len(task.goal_chain),
            },
            message="Task is properly aligned",
        )
    except GoalAlignmentError as e:
        return success(
            data={"task_id": task_id, "aligned": False, "issue": str(e)},
            message="Task alignment issue found",
        )


@router.post("/scan")
async def run_alignment_scan():
    checker = get_alignment_checker()
    result = checker.run_alignment_scan()
    return success(data=result, message="Alignment scan completed")


@router.get("/summary")
async def get_alignment_summary():
    checker = get_alignment_checker()
    summary = checker.get_alignment_summary()
    return success(data=summary, message="Alignment summary retrieved")


@router.get("/progress/all")
async def get_all_progress():
    checker = get_alignment_checker()
    progresses = checker.compute_all_progress()
    return success(
        data=[p.to_dict() for p in progresses], message="All progress computed"
    )


@router.post("/goals/{goal_id}/propagate")
async def propagate_goal_change(goal_id: str):
    store = get_goal_chain_store()
    goal = store.get_goal(goal_id)
    if goal is None:
        return error(code=ErrorCode.NOT_FOUND, message=f"Goal '{goal_id}' not found")

    checker = get_alignment_checker()
    result = checker.propagate_goal_change(goal_id)
    return success(data=result, message="Goal change propagated")
