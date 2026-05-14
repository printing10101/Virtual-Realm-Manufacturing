"""
Goal Chain Store

SQLite-backed storage for goal hierarchy with version tracking,
goal chain resolution, and progress computation.
"""
import logging
import time
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.models.goals import (
    Goal, GoalLevel, GoalStatus, GoalRef, GoalVersion, GoalProgress,
    DEFAULT_GOALS,
)

logger = logging.getLogger(__name__)


class GoalChainStore:
    """Persistent goal chain storage with SQLite backend"""

    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            db_path = str(Path(".lingjing/.gstack") / "goal_chain.db")
        self._db_path = db_path
        Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_tables()
        self._seed_defaults()

    def _init_tables(self):
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS goals (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                level TEXT NOT NULL,
                parent_id TEXT,
                status TEXT NOT NULL DEFAULT 'not_started',
                created_at REAL,
                completed_at REAL,
                version INTEGER NOT NULL DEFAULT 1,
                FOREIGN KEY (parent_id) REFERENCES goals(id)
            );

            CREATE TABLE IF NOT EXISTS goal_versions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                goal_id TEXT NOT NULL,
                version INTEGER NOT NULL,
                changed_at REAL,
                changed_by TEXT NOT NULL DEFAULT 'system',
                change_type TEXT NOT NULL,
                field_name TEXT NOT NULL,
                old_value TEXT DEFAULT '',
                new_value TEXT DEFAULT '',
                FOREIGN KEY (goal_id) REFERENCES goals(id)
            );

            CREATE INDEX IF NOT EXISTS idx_goals_level ON goals(level);
            CREATE INDEX IF NOT EXISTS idx_goals_parent ON goals(parent_id);
            CREATE INDEX IF NOT EXISTS idx_goals_status ON goals(status);
            CREATE INDEX IF NOT EXISTS idx_versions_goal ON goal_versions(goal_id);
        """)
        self._conn.commit()

    def _seed_defaults(self):
        existing = self._conn.execute("SELECT COUNT(*) FROM goals").fetchone()[0]
        if existing == 0:
            for goal in DEFAULT_GOALS:
                self._conn.execute(
                    "INSERT INTO goals (id, name, description, level, parent_id, status, created_at, version) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        goal.id, goal.name, goal.description,
                        goal.level.value, goal.parent_id, goal.status.value,
                        time.time(), goal.version,
                    ),
                )
            self._conn.commit()
            logger.info("Default goal hierarchy seeded")

    def add_goal(self, goal: Goal) -> Goal:
        if goal.created_at is None:
            goal.created_at = time.time()
        self._conn.execute(
            "INSERT INTO goals (id, name, description, level, parent_id, status, created_at, version) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                goal.id, goal.name, goal.description,
                goal.level.value, goal.parent_id, goal.status.value,
                goal.created_at, goal.version,
            ),
        )
        self._conn.commit()
        return goal

    def get_goal(self, goal_id: str) -> Optional[Goal]:
        row = self._conn.execute("SELECT * FROM goals WHERE id = ?", (goal_id,)).fetchone()
        if row is None:
            return None
        return self._row_to_goal(row)

    def update_goal(self, goal_id: str, **kwargs) -> Optional[Goal]:
        goal = self.get_goal(goal_id)
        if goal is None:
            return None

        changes = []
        for key, value in kwargs.items():
            if hasattr(goal, key) and value != getattr(goal, key):
                old = str(getattr(goal, key))
                new = str(value)
                self._record_version(
                    goal_id=goal_id,
                    version=goal.version + 1,
                    change_type="update",
                    field_name=key,
                    old_value=old,
                    new_value=new,
                )
                changes.append((key, value))
                setattr(goal, key, value)

        if not changes:
            return goal

        for key, value in changes:
            self._conn.execute(
                f"UPDATE goals SET {key} = ? WHERE id = ?",
                (value, goal_id),
            )

        goal.version += 1
        self._conn.execute("UPDATE goals SET version = ? WHERE id = ?", (goal.version, goal_id))
        self._conn.commit()
        return goal

    def delete_goal(self, goal_id: str) -> bool:
        row = self._conn.execute("SELECT id FROM goals WHERE id = ?", (goal_id,)).fetchone()
        if row is None:
            return False
        self._conn.execute("DELETE FROM goals WHERE id = ?", (goal_id,))
        self._conn.execute("DELETE FROM goal_versions WHERE goal_id = ?", (goal_id,))
        self._conn.commit()
        return True

    def get_children(self, goal_id: str) -> List[Goal]:
        rows = self._conn.execute(
            "SELECT * FROM goals WHERE parent_id = ? ORDER BY created_at",
            (goal_id,),
        ).fetchall()
        return [self._row_to_goal(r) for r in rows]

    def resolve_goal_chain(self, goal_id: str) -> List[GoalRef]:
        chain: List[GoalRef] = []
        visited = set()
        current_id = goal_id

        while current_id and current_id not in visited:
            visited.add(current_id)
            goal = self.get_goal(current_id)
            if goal is None:
                break
            chain.append(GoalRef(
                id=goal.id,
                level=goal.level,
                name=goal.name,
                description=goal.description,
            ))
            current_id = goal.parent_id

        return chain

    def get_all_goals(self, level: Optional[GoalLevel] = None) -> List[Goal]:
        if level:
            rows = self._conn.execute(
                "SELECT * FROM goals WHERE level = ? ORDER BY created_at",
                (level.value,),
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM goals ORDER BY level, created_at"
            ).fetchall()
        return [self._row_to_goal(r) for r in rows]

    def get_goal_tree(self) -> List[Dict[str, Any]]:
        all_goals = self.get_all_goals()
        goal_map = {g.id: g for g in all_goals}
        root_goals = [g for g in all_goals if g.parent_id is None or g.level == GoalLevel.MISSION]

        def _build_tree(goal: Goal) -> Dict[str, Any]:
            children = [g for g in all_goals if g.parent_id == goal.id]
            node: Dict[str, Any] = {
                **goal.to_dict(),
                "children": [_build_tree(c) for c in children],
            }
            return node

        return [_build_tree(g) for g in root_goals]

    def compute_progress(self, goal_id: str, task_status_map: Optional[Dict[str, str]] = None) -> GoalProgress:
        goal = self.get_goal(goal_id)
        if goal is None:
            return GoalProgress()

        child_goals = self.get_children(goal_id)
        total = 0
        completed = 0
        in_progress = 0

        if task_status_map is None:
            task_status_map = {}

        for cg in child_goals:
            sub = self.compute_progress(cg.id, task_status_map)
            total += sub.total_tasks
            completed += sub.completed_tasks
            in_progress += sub.in_progress_tasks

        direct_tasks = {tid: st for tid, st in task_status_map.items() if self._task_belongs_to_goal(tid, goal_id)}
        for tid, st in direct_tasks.items():
            if st == "completed":
                completed += 1
            elif st in ("in_progress", "running", "queued"):
                in_progress += 1
            total += 1

        progress = GoalProgress(
            goal_id=goal_id,
            goal_name=goal.name,
            level=goal.level,
            total_tasks=total,
            completed_tasks=completed,
            in_progress_tasks=in_progress,
            progress_percent=round((completed / total * 100) if total > 0 else 0.0, 1),
            last_updated=time.time(),
        )
        return progress

    def get_version_history(self, goal_id: str, limit: int = 50) -> List[GoalVersion]:
        rows = self._conn.execute(
            "SELECT * FROM goal_versions WHERE goal_id = ? ORDER BY changed_at DESC LIMIT ?",
            (goal_id, limit),
        ).fetchall()
        return [self._row_to_version(r) for r in rows]

    def propagate_cancellation(self, cancelled_goal_id: str) -> List[str]:
        affected_ids: List[str] = []
        self._mark_descendants_needs_review(cancelled_goal_id, affected_ids)
        return affected_ids

    def _mark_descendants_needs_review(self, parent_id: str, affected: List[str]):
        children = self.get_children(parent_id)
        for child in children:
            if child.level == GoalLevel.TASK and child.status in (GoalStatus.IN_PROGRESS, GoalStatus.NOT_STARTED):
                self._conn.execute(
                    "UPDATE goals SET status = ? WHERE id = ?",
                    (GoalStatus.NEEDS_REVIEW.value, child.id),
                )
                affected.append(child.id)
            self._mark_descendants_needs_review(child.id, affected)
        self._conn.commit()

    def _record_version(self, goal_id: str, version: int, change_type: str, field_name: str, old_value: str, new_value: str, changed_by: str = "system"):
        self._conn.execute(
            "INSERT INTO goal_versions (goal_id, version, changed_at, changed_by, change_type, field_name, old_value, new_value) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (goal_id, version, time.time(), changed_by, change_type, field_name, old_value, new_value),
        )

    def _task_belongs_to_goal(self, task_id: str, goal_id: str) -> bool:
        return False

    def set_task_belongs_checker(self, checker):
        self._task_belongs_checker = checker

    def _task_belongs_to_goal(self, task_id: str, goal_id: str) -> bool:
        if hasattr(self, '_task_belongs_checker'):
            return self._task_belongs_checker(task_id, goal_id)
        return False

    def _row_to_goal(self, row) -> Goal:
        return Goal(
            id=row["id"],
            name=row["name"],
            description=row["description"],
            level=GoalLevel(row["level"]),
            parent_id=row["parent_id"],
            status=GoalStatus(row["status"]),
            created_at=row["created_at"],
            completed_at=row["completed_at"],
            version=row["version"],
        )

    def _row_to_version(self, row) -> GoalVersion:
        return GoalVersion(
            id=row["id"],
            goal_id=row["goal_id"],
            version=row["version"],
            changed_at=row["changed_at"],
            changed_by=row["changed_by"],
            change_type=row["change_type"],
            field_name=row["field_name"],
            old_value=row["old_value"],
            new_value=row["new_value"],
        )

    def close(self):
        if self._conn:
            self._conn.close()


_global_store: Optional[GoalChainStore] = None


def get_goal_chain_store(db_path: Optional[str] = None) -> GoalChainStore:
    global _global_store
    if _global_store is None:
        _global_store = GoalChainStore(db_path)
    return _global_store


def init_goal_chain_store(db_path: Optional[str] = None) -> GoalChainStore:
    global _global_store
    _global_store = GoalChainStore(db_path)
    return _global_store
