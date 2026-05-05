"""
SQLite Repository 实现

使用 SQLAlchemy 作为 ORM 层，实现数据库连接池管理和复杂查询支持。
"""

import contextlib
from datetime import datetime
from typing import Any

from sqlalchemy import and_, create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.repository.base import Repository
from app.core.repository.config import SQLiteConfig
from app.core.repository.exceptions import (
    RecordNotFoundError,
    StorageError,
    TransactionError,
)
from app.core.repository.models import Base, ProjectRecord, SettingRecord


class SQLiteRepository(Repository):
    """
    SQLite 存储库实现

    使用 SQLAlchemy ORM 进行数据库操作，支持连接池、事务和复杂查询。
    """

    RECORD_TYPE_MAP = {
        "setting": SettingRecord,
        "project": ProjectRecord,
    }

    def __init__(self, config: SQLiteConfig | None = None, record_type: str = "setting"):
        super().__init__(repository_type="sqlite")
        self._config = config or SQLiteConfig()
        self._record_type = record_type
        self._engine = create_engine(
            f"sqlite:///{self._config.db_path}",
            poolclass=StaticPool,
            connect_args={"check_same_thread": False},
            echo=self._config.echo,
        )
        self._session_factory = sessionmaker(bind=self._engine)
        self._session: Session | None = None
        Base.metadata.create_all(self._engine)

    @property
    def record_model(self):
        model = self.RECORD_TYPE_MAP.get(self._record_type)
        if model is None:
            raise ValueError(f"Unknown record type: {self._record_type}")
        return model

    def _get_session(self) -> Session:
        if self._session is None:
            self._session = self._session_factory()
        return self._session

    def _do_begin_transaction(self) -> None:
        session = self._get_session()
        if session.in_transaction():
            return
        session.begin()

    def _do_commit(self) -> None:
        try:
            session = self._get_session()
            if session.in_transaction():
                session.commit()
        except Exception as e:
            raise TransactionError(str(e), repository_type="sqlite", detail=str(e))

    def _do_rollback(self) -> None:
        try:
            session = self._get_session()
            if session.in_transaction():
                session.rollback()
        except Exception as e:
            raise TransactionError(str(e), repository_type="sqlite", detail=str(e))

    def create(self, data: dict[str, Any]) -> dict[str, Any]:
        try:
            model = self.record_model
            record_data = dict(data)
            record_id = record_data.pop("id", None)

            existing = None
            if record_id:
                existing = self._get_session().get(model, record_id)

            if existing is not None:
                raise ValueError(f"Record already exists: {record_id}")

            for key in ["created_at", "updated_at"]:
                if key in record_data and isinstance(record_data[key], str):
                    with contextlib.suppress(ValueError):
                        record_data[key] = datetime.fromisoformat(record_data[key])

            record = model(id=record_id, **record_data)
            self._get_session().add(record)
            if not self._in_transaction:
                self._get_session().commit()

            return record.to_dict()
        except ValueError:
            raise
        except Exception as e:
            raise StorageError(str(e), repository_type="sqlite", detail=str(e))

    def read(self, id: str) -> dict[str, Any] | None:
        try:
            model = self.record_model
            record = self._get_session().get(model, id)
            if record is None:
                return None
            return record.to_dict()
        except Exception as e:
            raise StorageError(str(e), repository_type="sqlite", detail=str(e))

    def update(self, id: str, data: dict[str, Any]) -> dict[str, Any]:
        try:
            model = self.record_model
            record = self._get_session().get(model, id)
            if record is None:
                raise RecordNotFoundError(id, repository_type="sqlite")

            for key, value in data.items():
                if hasattr(record, key) and key != "id":
                    if key in ["created_at", "updated_at"] and isinstance(value, str):
                        with contextlib.suppress(ValueError):
                            value = datetime.fromisoformat(value)
                    setattr(record, key, value)

            if not self._in_transaction:
                self._get_session().commit()

            return record.to_dict()
        except RecordNotFoundError:
            raise
        except Exception as e:
            raise StorageError(str(e), repository_type="sqlite", detail=str(e))

    def delete(self, id: str) -> bool:
        try:
            model = self.record_model
            record = self._get_session().get(model, id)
            if record is None:
                return False

            self._get_session().delete(record)
            if not self._in_transaction:
                self._get_session().commit()

            return True
        except Exception as e:
            raise StorageError(str(e), repository_type="sqlite", detail=str(e))

    def list(self, filters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        try:
            model = self.record_model
            query = self._get_session().query(model)

            if filters:
                conditions = []
                for key, value in filters.items():
                    if hasattr(model, key):
                        conditions.append(getattr(model, key) == value)
                if conditions:
                    query = query.filter(and_(*conditions))

            records = query.all()
            return [record.to_dict() for record in records]
        except Exception as e:
            raise StorageError(str(e), repository_type="sqlite", detail=str(e))

    def close(self) -> None:
        if self._session is not None:
            self._session.close()
            self._session = None
        self._engine.dispose()
