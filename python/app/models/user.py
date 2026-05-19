from __future__ import annotations

import os
import json
import threading
from datetime import datetime, timezone
from typing import Optional
from pathlib import Path
from pydantic import BaseModel, Field


USER_STORE_FILE = os.environ.get("LNN_USER_STORE_FILE", ".lnn_users.json")


class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=32, pattern=r"^[a-zA-Z0-9_]+$")
    password: str = Field(..., min_length=8, max_length=128)


class UserLogin(BaseModel):
    username: str
    password: str


class UserResponse(BaseModel):
    username: str
    role: str = "user"
    created_at: str = ""
    last_login: Optional[str] = None


class UserRecord:
    def __init__(
        self,
        username: str,
        password_hash: str,
        role: str = "user",
        created_at: Optional[str] = None,
        last_login: Optional[str] = None,
        is_active: bool = True,
    ):
        self.username = username
        self.password_hash = password_hash
        self.role = role
        self.created_at = created_at or datetime.now(timezone.utc).isoformat()
        self.last_login = last_login
        self.is_active = is_active

    def to_dict(self) -> dict:
        return {
            "username": self.username,
            "password_hash": self.password_hash,
            "role": self.role,
            "created_at": self.created_at,
            "last_login": self.last_login,
            "is_active": self.is_active,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "UserRecord":
        return cls(
            username=data["username"],
            password_hash=data["password_hash"],
            role=data.get("role", "user"),
            created_at=data.get("created_at"),
            last_login=data.get("last_login"),
            is_active=data.get("is_active", True),
        )


class UserStore:
    def __init__(self, file_path: Optional[str] = None):
        self._file_path = Path(file_path or USER_STORE_FILE)
        self._users: dict[str, UserRecord] = {}
        self._lock = threading.Lock()
        self._load()

    def _load(self):
        if self._file_path.exists():
            try:
                data = json.loads(self._file_path.read_text())
                self._users = {
                    u["username"]: UserRecord.from_dict(u)
                    for u in data.get("users", [])
                }
            except Exception:
                self._users = {}

    def _save(self):
        data = {"users": [u.to_dict() for u in self._users.values()]}
        self._file_path.write_text(json.dumps(data, ensure_ascii=False, indent=2))

    def create_user(self, username: str, password_hash: str, role: str = "user") -> UserRecord:
        with self._lock:
            if username in self._users:
                raise ValueError(f"User '{username}' already exists")
            record = UserRecord(username=username, password_hash=password_hash, role=role)
            self._users[username] = record
            self._save()
            return record

    def get_user(self, username: str) -> Optional[UserRecord]:
        with self._lock:
            return self._users.get(username)

    def update_last_login(self, username: str):
        with self._lock:
            if username in self._users:
                self._users[username].last_login = datetime.now(timezone.utc).isoformat()
                self._save()

    def set_active(self, username: str, active: bool):
        with self._lock:
            if username in self._users:
                self._users[username].is_active = active
                self._save()

    def set_role(self, username: str, role: str):
        with self._lock:
            if username in self._users:
                self._users[username].role = role
                self._save()

    def list_users(self) -> list[UserRecord]:
        with self._lock:
            return list(self._users.values())


_user_store: Optional[UserStore] = None


def get_user_store() -> UserStore:
    global _user_store
    if _user_store is None:
        _user_store = UserStore()
    return _user_store