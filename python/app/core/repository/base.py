"""
Repository 模式基类模块

定义统一的存储访问层接口，包括 CRUD 操作、事务支持、批量操作和上下文管理器。
所有具体的 Repository 实现都必须继承此基类并实现抽象方法。
"""

import builtins
from abc import ABC, abstractmethod
from contextlib import contextmanager
from typing import Any

from app.core.repository.exceptions import TransactionError


class Repository(ABC):
    """
    Repository 抽象基类

    提供统一的存储访问接口，支持：
    - 标准 CRUD 操作
    - 事务管理（begin_transaction, commit, rollback）
    - 批量操作（bulk_create, bulk_update, bulk_delete）
    - 上下文管理器（with 语句）
    """

    def __init__(self, repository_type: str):
        self._repository_type = repository_type
        self._in_transaction = False

    @property
    def repository_type(self) -> str:
        return self._repository_type

    @abstractmethod
    def create(self, data: dict[str, Any]) -> dict[str, Any]:
        """
        创建新记录

        Args:
            data: 包含新记录数据的字典

        Returns:
            创建后的完整记录字典

        Raises:
            ValidationError: 数据验证失败
            StorageError: 底层存储异常
        """
        pass

    @abstractmethod
    def read(self, id: str) -> dict[str, Any] | None:
        """
        根据 ID 读取记录

        Args:
            id: 记录的唯一标识符

        Returns:
            记录字典，如果不存在则返回 None
        """
        pass

    @abstractmethod
    def update(self, id: str, data: dict[str, Any]) -> dict[str, Any]:
        """
        更新指定 ID 的记录

        Args:
            id: 记录的唯一标识符
            data: 要更新的字段字典

        Returns:
            更新后的完整记录字典

        Raises:
            RecordNotFoundError: 记录不存在
            ValidationError: 数据验证失败
        """
        pass

    @abstractmethod
    def delete(self, id: str) -> bool:
        """
        删除指定 ID 的记录

        Args:
            id: 记录的唯一标识符

        Returns:
            True 如果删除成功，False 如果记录不存在
        """
        pass

    @abstractmethod
    def list(self, filters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        """
        根据筛选条件列出记录

        Args:
            filters: 可选的筛选条件字典

        Returns:
            符合条件的记录列表
        """
        pass

    def begin_transaction(self) -> None:
        """
        开始事务

        Raises:
            TransactionError: 已在事务中或无法开始事务
        """
        if self._in_transaction:
            raise TransactionError(
                "Transaction already in progress",
                repository_type=self._repository_type
            )
        self._in_transaction = True
        self._do_begin_transaction()

    def commit(self) -> None:
        """
        提交事务

        Raises:
            TransactionError: 不在事务中或提交失败
        """
        if not self._in_transaction:
            raise TransactionError(
                "No transaction in progress",
                repository_type=self._repository_type
            )
        try:
            self._do_commit()
        finally:
            self._in_transaction = False

    def rollback(self) -> None:
        """
        回滚事务

        Raises:
            TransactionError: 不在事务中或回滚失败
        """
        if not self._in_transaction:
            raise TransactionError(
                "No transaction in progress",
                repository_type=self._repository_type
            )
        try:
            self._do_rollback()
        finally:
            self._in_transaction = False

    @abstractmethod
    def _do_begin_transaction(self) -> None:
        """具体的事务开始实现（由子类实现）"""
        pass

    @abstractmethod
    def _do_commit(self) -> None:
        """具体的事务提交实现（由子类实现）"""
        pass

    @abstractmethod
    def _do_rollback(self) -> None:
        """具体的事务回滚实现（由子类实现）"""
        pass

    def bulk_create(self, records: builtins.list[dict[str, Any]]) -> builtins.list[dict[str, Any]]:
        """
        批量创建记录

        Args:
            records: 要创建的记录列表

        Returns:
            创建后的完整记录列表
        """
        self.begin_transaction()
        try:
            created = []
            for record in records:
                created.append(self.create(record))
            self.commit()
            return created
        except Exception:
            self.rollback()
            raise

    def bulk_update(self, updates: builtins.list[dict[str, Any]]) -> builtins.list[dict[str, Any]]:
        """
        批量更新记录

        Args:
            updates: 更新列表，每个元素必须包含 'id' 字段和其他要更新的字段

        Returns:
            更新后的记录列表
        """
        self.begin_transaction()
        try:
            updated = []
            for update_data in updates:
                if "id" not in update_data:
                    raise ValueError("Each update must contain 'id' field")
                record_id = update_data.pop("id")
                updated.append(self.update(record_id, update_data))
            self.commit()
            return updated
        except Exception:
            self.rollback()
            raise

    def bulk_delete(self, ids: builtins.list[str]) -> int:
        """
        批量删除记录

        Args:
            ids: 要删除的记录 ID 列表

        Returns:
            成功删除的记录数量
        """
        self.begin_transaction()
        try:
            count = 0
            for record_id in ids:
                if self.delete(record_id):
                    count += 1
            self.commit()
            return count
        except Exception:
            self.rollback()
            raise

    @contextmanager
    def transaction(self):
        """
        事务上下文管理器

        用法:
            with repo.transaction():
                repo.create(data1)
                repo.update(id2, data2)
        """
        self.begin_transaction()
        try:
            yield
            self.commit()
        except Exception:
            self.rollback()
            raise

    def close(self) -> None:
        """
        关闭 Repository 连接（可选实现）
        """
        pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            if self._in_transaction:
                self.rollback()
        else:
            if self._in_transaction:
                self.commit()
        self.close()
        return False
