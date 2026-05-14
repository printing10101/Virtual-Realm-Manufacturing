"""Template Update Service — proactively pushes template optimization suggestions to projects."""
import json
import logging
import os
import sqlite3
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class UpdateNotification:
    notification_id: str
    project_id: str
    suggestion_id: str
    priority: str
    title: str
    description: str
    change_preview: Dict[str, Any]
    expected_impact: Dict[str, Any]
    created_at: float = field(default_factory=time.time)
    status: str = "pending"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "notification_id": self.notification_id,
            "project_id": self.project_id,
            "suggestion_id": self.suggestion_id,
            "priority": self.priority,
            "title": self.title,
            "description": self.description,
            "change_preview": self.change_preview,
            "expected_impact": self.expected_impact,
            "created_at": self.created_at,
            "status": self.status,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "UpdateNotification":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


class TemplateUpdateService:
    """Monitors projects for applicable template optimizations and pushes notifications."""

    PRIORITY_THRESHOLDS = {
        "critical": 0.10,
        "recommended": 0.03,
    }

    def __init__(self, db_path: str = "data/templates/updates.db"):
        self.db_path = db_path
        self._lock = threading.RLock()
        self._db: Optional[sqlite3.Connection] = None
        self._notifications: Dict[str, UpdateNotification] = {}

    def initialize(self) -> None:
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)

        self._db = sqlite3.connect(self.db_path, check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        self._db.execute("""
            CREATE TABLE IF NOT EXISTS update_notifications (
                notification_id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                suggestion_id TEXT,
                priority TEXT,
                title TEXT,
                description TEXT,
                change_preview TEXT,
                expected_impact TEXT,
                created_at REAL,
                status TEXT
            )
        """)
        self._db.commit()
        self._load_data()
        logger.info("TemplateUpdateService initialized: db=%s", self.db_path)

    def _load_data(self) -> None:
        cursor = self._db.execute("SELECT * FROM update_notifications ORDER BY created_at DESC")
        for row in cursor.fetchall():
            self._notifications[row["notification_id"]] = UpdateNotification(
                notification_id=row["notification_id"],
                project_id=row["project_id"],
                suggestion_id=row["suggestion_id"] or "",
                priority=row["priority"],
                title=row["title"] or "",
                description=row["description"] or "",
                change_preview=json.loads(row["change_preview"]) if row["change_preview"] else {},
                expected_impact=json.loads(row["expected_impact"]) if row["expected_impact"] else {},
                created_at=row["created_at"],
                status=row["status"],
            )

    def classify_priority(self, improvement: float) -> str:
        if improvement >= self.PRIORITY_THRESHOLDS["critical"]:
            return "critical"
        elif improvement >= self.PRIORITY_THRESHOLDS["recommended"]:
            return "recommended"
        else:
            return "optional"

    def create_notification(
        self,
        project_id: str,
        suggestion: Dict[str, Any],
        priority: str,
    ) -> UpdateNotification:
        with self._lock:
            notif = UpdateNotification(
                notification_id=f"upd_{uuid.uuid4().hex[:8]}",
                project_id=project_id,
                suggestion_id=suggestion.get("suggestion_id", ""),
                priority=priority,
                title=suggestion.get("title", "Template Optimization Available"),
                description=suggestion.get("description", ""),
                change_preview=suggestion.get("change_preview", {}),
                expected_impact=suggestion.get("expected_impact", {}),
            )
            self._notifications[notif.notification_id] = notif
            self._db.execute(
                """INSERT INTO update_notifications
                   (notification_id, project_id, suggestion_id, priority, title, description, change_preview, expected_impact, created_at, status)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    notif.notification_id,
                    notif.project_id,
                    notif.suggestion_id,
                    notif.priority,
                    notif.title,
                    notif.description,
                    json.dumps(notif.change_preview),
                    json.dumps(notif.expected_impact),
                    notif.created_at,
                    notif.status,
                ),
            )
            self._db.commit()
            logger.info("Update notification created: id=%s, project=%s, priority=%s",
                        notif.notification_id, project_id, priority)
            return notif

    def scan_for_updates(
        self,
        project_id: str,
        suggestions: List[Dict[str, Any]],
    ) -> List[UpdateNotification]:
        with self._lock:
            notifications = []
            for suggestion in suggestions:
                improvement = suggestion.get("expected_impact", {}).get("improvement", 0)
                priority = self.classify_priority(improvement)

                existing = [
                    n for n in self._notifications.values()
                    if n.project_id == project_id
                    and n.suggestion_id == suggestion.get("suggestion_id", "")
                    and n.status in ("pending", "dismissed", "applied")
                ]
                if existing:
                    continue

                notif = self.create_notification(project_id, suggestion, priority)
                notifications.append(notif)

            return notifications

    def apply_update(self, notification_id: str) -> Optional[UpdateNotification]:
        with self._lock:
            notif = self._notifications.get(notification_id)
            if notif is None:
                return None

            notif.status = "applied"
            self._db.execute(
                "UPDATE update_notifications SET status = ? WHERE notification_id = ?",
                ("applied", notification_id),
            )
            self._db.commit()
            logger.info("Update applied: id=%s", notification_id)
            return notif

    def dismiss_notification(self, notification_id: str) -> bool:
        with self._lock:
            notif = self._notifications.get(notification_id)
            if notif is None:
                return False

            notif.status = "dismissed"
            self._db.execute(
                "UPDATE update_notifications SET status = ? WHERE notification_id = ?",
                ("dismissed", notification_id),
            )
            self._db.commit()
            logger.info("Notification dismissed: id=%s", notification_id)
            return True

    def preview_update(self, notification_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            notif = self._notifications.get(notification_id)
            if notif is None:
                return None
            return {
                "title": notif.title,
                "description": notif.description,
                "change_preview": notif.change_preview,
                "expected_impact": notif.expected_impact,
                "priority": notif.priority,
            }

    def get_notifications(
        self,
        project_id: str,
        status_filter: Optional[str] = None,
    ) -> List[UpdateNotification]:
        with self._lock:
            notifs = [n for n in self._notifications.values() if n.project_id == project_id]
            if status_filter:
                notifs = [n for n in notifs if n.status == status_filter]
            return sorted(notifs, key=lambda n: n.created_at, reverse=True)

    def close(self) -> None:
        if self._db:
            self._db.close()


_update_service: Optional[TemplateUpdateService] = None
_update_lock = threading.Lock()


def get_update_service() -> TemplateUpdateService:
    global _update_service
    if _update_service is None:
        with _update_lock:
            if _update_service is None:
                _update_service = TemplateUpdateService()
                _update_service.initialize()
    return _update_service


def init_update_service(
    db_path: str = "data/templates/updates.db",
) -> TemplateUpdateService:
    global _update_service
    with _update_lock:
        if _update_service is not None:
            _update_service.close()
        _update_service = TemplateUpdateService(db_path=db_path)
        _update_service.initialize()
    return _update_service
