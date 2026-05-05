import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

from app.config import config


class TaskDatabase:
    def __init__(self):
        self.db_path = Path(config.storage.output_dir) / "cad_tasks.db"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_conn(self):
        conn = sqlite3.connect(str(self.db_path), timeout=30.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        conn.execute("PRAGMA synchronous=NORMAL")
        return conn

    @contextmanager
    def get_connection(self):
        conn = self._get_conn()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _init_db(self):
        with self.get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS tasks (
                    task_id TEXT PRIMARY KEY,
                    status TEXT NOT NULL DEFAULT 'pending',
                    progress REAL NOT NULL DEFAULT 0.0,
                    task_type TEXT NOT NULL,
                    front_view_path TEXT,
                    top_view_path TEXT,
                    left_view_path TEXT,
                    extracted_params TEXT,
                    cadquery_script TEXT,
                    model_path TEXT,
                    model_format TEXT,
                    error_message TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    completed_at TEXT
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS model_library (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    shape_type TEXT NOT NULL,
                    parameters TEXT NOT NULL,
                    cadquery_script TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
            """)

    def create_task(self, task_type: str, views: dict, task_id: str | None = None) -> str:
        if task_id is None:
            task_id = str(uuid.uuid4())
        now = datetime.now().isoformat()

        with self.get_connection() as conn:
            conn.execute("""
                INSERT INTO tasks
                (task_id, status, progress, task_type, front_view_path, top_view_path,
                 left_view_path, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                task_id, 'pending', 0.0, task_type,
                views.get('front'), views.get('top'), views.get('left'),
                now, now
            ))

        return task_id

    def update_task_status(self, task_id: str, status: str, progress: float | None = None,
                          error_message: str | None = None, extracted_params: str | None = None,
                          cadquery_script: str | None = None, model_path: str | None = None,
                          model_format: str | None = None):
        now = datetime.now().isoformat()

        with self.get_connection() as conn:
            if status == 'completed':
                conn.execute("""
                    UPDATE tasks
                    SET status=?, updated_at=?, completed_at=?,
                        progress=?, error_message=?, extracted_params=?,
                        cadquery_script=?, model_path=?, model_format=?
                    WHERE task_id=?
                """, (status, now, now, progress or 100.0, error_message,
                      extracted_params, cadquery_script, model_path, model_format, task_id))
            elif status == 'failed':
                conn.execute("""
                    UPDATE tasks
                    SET status=?, updated_at=?, progress=?, error_message=?
                    WHERE task_id=?
                """, (status, now, progress or 0.0, error_message, task_id))
            else:
                conn.execute("""
                    UPDATE tasks
                    SET status=?, updated_at=?, progress=?,
                        extracted_params=?, cadquery_script=?
                    WHERE task_id=?
                """, (status, now, progress or 0.0, extracted_params,
                      cadquery_script, task_id))

    def get_task(self, task_id: str) -> dict | None:
        with self.get_connection() as conn:
            cursor = conn.execute("SELECT * FROM tasks WHERE task_id=?", (task_id,))
            row = cursor.fetchone()
            if row:
                return dict(row)
            return None

    def list_tasks(self, limit: int = 50) -> list[dict]:
        with self.get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM tasks ORDER BY created_at DESC LIMIT ?",
                (limit,)
            )
            return [dict(row) for row in cursor.fetchall()]

    def add_to_model_library(self, shape_type: str, parameters: str, cadquery_script: str):
        now = datetime.now().isoformat()
        with self.get_connection() as conn:
            conn.execute("""
                INSERT INTO model_library (shape_type, parameters, cadquery_script, created_at)
                VALUES (?, ?, ?, ?)
            """, (shape_type, parameters, cadquery_script, now))

    def search_model_library(self, shape_type: str) -> list[dict]:
        with self.get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM model_library WHERE shape_type=? ORDER BY created_at DESC",
                (shape_type,)
            )
            return [dict(row) for row in cursor.fetchall()]


task_db = TaskDatabase()
