from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from app.core.repository.exceptions import StorageError


class Repository(ABC):
    def __init__(self, repository_type: str = "generic"):
        self._repository_type = repository_type
        self._in_transaction = False
        self._transaction_snapshot: dict[str, Any] | None = None
        self._transaction_version = 0

    def begin_transaction(self):
        if self._in_transaction:
            raise StorageError("事务已在进行中", repository_type=self._repository_type)
        self._do_begin_transaction()
        self._in_transaction = True

    def commit(self):
        if not self._in_transaction:
            raise StorageError("没有活跃的事务", repository_type=self._repository_type)
        self._do_commit()
        self._in_transaction = False

    def rollback(self):
        if not self._in_transaction:
            raise StorageError("没有活跃的事务", repository_type=self._repository_type)
        self._do_rollback()
        self._in_transaction = False

    @abstractmethod
    def create(self, data: dict[str, Any]) -> dict[str, Any]: ...

    @abstractmethod
    def read(self, id: str) -> dict[str, Any] | None: ...

    @abstractmethod
    def update(self, id: str, data: dict[str, Any]) -> dict[str, Any]: ...

    @abstractmethod
    def delete(self, id: str) -> bool: ...

    @abstractmethod
    def list(self, filters: dict[str, Any] | None = None) -> list[dict[str, Any]]: ...

    @abstractmethod
    def close(self) -> None: ...

    def _do_begin_transaction(self) -> None:
        raise NotImplementedError

    def _do_commit(self) -> None:
        raise NotImplementedError

    def _do_rollback(self) -> None:
        raise NotImplementedError
