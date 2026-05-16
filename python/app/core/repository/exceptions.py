from __future__ import annotations


class RepositoryError(Exception):
    def __init__(
        self, message: str, repository_type: str = "generic", detail: str | None = None
    ):
        self.repository_type = repository_type
        self.detail = detail
        super().__init__(message)


class RecordNotFoundError(RepositoryError):
    def __init__(self, record_id: str, repository_type: str = "generic"):
        super().__init__(
            f"Record not found: {record_id}",
            repository_type=repository_type,
        )
        self.record_id = record_id


class StorageError(RepositoryError):
    pass


class ValidationError(RepositoryError):
    pass
