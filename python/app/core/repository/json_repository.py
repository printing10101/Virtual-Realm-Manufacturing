"""
JSON Repository 实现

实现文件锁机制确保并发安全，支持数据版本控制和增量更新。
"""

import json
import threading
from datetime import datetime
from pathlib import Path
from typing import Any

try:
    import fcntl
    HAS_FCNTL = True
except ImportError:
    HAS_FCNTL = False

import builtins

from app.core.repository.base import Repository
from app.core.repository.config import JsonConfig
from app.core.repository.exceptions import (
    RecordNotFoundError,
    StorageError,
    ValidationError,
)


class JsonRepository(Repository):
    """
    JSON 文件存储库实现

    使用文件锁保证并发安全，支持版本控制和增量更新。
    """

    def __init__(self, config: JsonConfig | None = None, store_name: str = "default"):
        super().__init__(repository_type="json")
        self._config = config or JsonConfig()
        self._store_name = store_name
        self._store_file = Path(self._config.data_directory) / f"{store_name}.json"
        self._version_file = Path(self._config.data_directory) / f"{store_name}_versions.jsonl"
        self._data: dict[str, Any] = {}
        self._current_version = 0
        self._lock = threading.Lock()
        self._load_data()

    def _lock_file(self, f, exclusive=True):
        if HAS_FCNTL:
            fcntl.flock(f, fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH)

    def _unlock_file(self, f):
        if HAS_FCNTL:
            fcntl.flock(f, fcntl.LOCK_UN)

    def _load_data(self) -> None:
        if self._store_file.exists():
            try:
                with self._lock:
                    with open(self._store_file, encoding="utf-8") as f:
                        self._lock_file(f, exclusive=False)
                        try:
                            self._data = json.load(f)
                            self._current_version = self._data.get("_version", 0)
                        finally:
                            self._unlock_file(f)
            except (OSError, json.JSONDecodeError):
                self._data = {}
                self._current_version = 0
        else:
            self._data = {"_version": 0}

    def _save_data(self) -> None:
        self._current_version += 1
        self._data["_version"] = self._current_version
        self._data["_updated_at"] = datetime.utcnow().isoformat()

        Path(self._store_file).parent.mkdir(parents=True, exist_ok=True)

        with self._lock, open(self._store_file, "w", encoding="utf-8") as f:
            self._lock_file(f, exclusive=True)
            try:
                json.dump(self._data, f, ensure_ascii=False, indent=2)
            finally:
                self._unlock_file(f)

        if self._config.version_control:
            self._append_version_log()

    def _append_version_log(self) -> None:
        log_entry = {
            "version": self._current_version,
            "timestamp": datetime.utcnow().isoformat(),
            "record_count": len([k for k in self._data if k != "_version" and k != "_updated_at"]),
        }
        with self._lock, open(self._version_file, "a", encoding="utf-8") as f:
            self._lock_file(f, exclusive=True)
            try:
                f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
            finally:
                self._unlock_file(f)

    def _get_record_data(self) -> dict[str, Any]:
        return {k: v for k, v in self._data.items() if k not in ("_version", "_updated_at")}

    def _do_begin_transaction(self) -> None:
        self._transaction_snapshot = dict(self._data)
        self._transaction_version = self._current_version

    def _do_commit(self) -> None:
        if hasattr(self, "_transaction_snapshot"):
            self._save_data()
            del self._transaction_snapshot

    def _do_rollback(self) -> None:
        if hasattr(self, "_transaction_snapshot"):
            self._data = self._transaction_snapshot
            self._current_version = self._transaction_version
            del self._transaction_snapshot

    def create(self, data: dict[str, Any]) -> dict[str, Any]:
        try:
            record_id = data.get("id")
            if record_id is None:
                raise ValidationError("Data must contain 'id' field", repository_type="json")

            if record_id in self._get_record_data():
                raise ValueError(f"Record already exists: {record_id}")

            record = dict(data)
            record["_created_at"] = datetime.utcnow().isoformat()
            record["_updated_at"] = record["_created_at"]

            self._data[record_id] = record
            if not self._in_transaction:
                self._save_data()

            return dict(record)
        except (ValueError, ValidationError):
            raise
        except Exception as e:
            raise StorageError(str(e), repository_type="json", detail=str(e))

    def read(self, id: str) -> dict[str, Any] | None:
        record = self._data.get(id)
        if record is None:
            return None
        return dict(record)

    def update(self, id: str, data: dict[str, Any]) -> dict[str, Any]:
        try:
            if id not in self._get_record_data():
                raise RecordNotFoundError(id, repository_type="json")

            record = self._data[id]
            record.update(data)
            record["_updated_at"] = datetime.utcnow().isoformat()

            if not self._in_transaction:
                self._save_data()

            return dict(record)
        except RecordNotFoundError:
            raise
        except Exception as e:
            raise StorageError(str(e), repository_type="json", detail=str(e))

    def delete(self, id: str) -> bool:
        try:
            if id not in self._get_record_data():
                return False

            del self._data[id]
            if not self._in_transaction:
                self._save_data()

            return True
        except Exception as e:
            raise StorageError(str(e), repository_type="json", detail=str(e))

    def list(self, filters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        records = []
        for _key, value in self._get_record_data().items():
            if filters:
                match = all(value.get(k) == v for k, v in filters.items())
                if match:
                    records.append(dict(value))
            else:
                records.append(dict(value))
        return records

    def get_version(self) -> int:
        return self._current_version

    def get_version_history(self) -> builtins.list[dict[str, Any]]:
        history = []
        if self._version_file.exists():
            with open(self._version_file, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        history.append(json.loads(line))
        return history

    def close(self) -> None:
        pass
