"""
Test JSON Repository Implementation

Tests for:
- JsonRepository: JSON file storage with file locking and version control
- Record CRUD operations with validation
- Concurrent access with threading locks
- Version control and history tracking
- Transaction support (begin/commit/rollback)
"""

import pytest
import tempfile
import shutil
import threading

from app.repository.json_repository import JsonRepository
from app.repository.config import JsonConfig
from app.repository.exceptions import (
    RecordNotFoundError,
    StorageError,
    ValidationError,
)


@pytest.fixture
def temp_storage_dir():
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def repository(temp_storage_dir):
    config = JsonConfig(data_directory=temp_storage_dir, version_control=True)
    return JsonRepository(config=config, store_name="test_store")


@pytest.fixture
def repository_no_version(temp_storage_dir):
    config = JsonConfig(data_directory=temp_storage_dir, version_control=False)
    return JsonRepository(config=config, store_name="test_store")


class TestJsonRepositoryCreate:
    """Test record creation"""

    def test_create_single_record(self, repository):
        data = {"id": "record1", "name": "Test Record", "value": 42}
        result = repository.create(data)

        assert result["id"] == "record1"
        assert result["name"] == "Test Record"
        assert result["value"] == 42
        assert "_created_at" in result
        assert "_updated_at" in result

    def test_create_multiple_records(self, repository):
        for i in range(5):
            data = {"id": f"record{i}", "index": i}
            repository.create(data)

        assert repository.get_version() == 5

    def test_create_without_id_raises(self, repository):
        with pytest.raises(ValidationError):
            repository.create({"name": "No ID"})

    def test_create_duplicate_id_raises(self, repository):
        repository.create({"id": "duplicate", "name": "First"})
        with pytest.raises(ValueError, match="已存在"):
            repository.create({"id": "duplicate", "name": "Second"})

    def test_create_timestamp_set(self, repository):
        data = {"id": "timestamp_test"}
        result = repository.create(data)

        assert result["_created_at"] is not None
        assert result["_updated_at"] is not None
        assert result["_created_at"] == result["_updated_at"]


class TestJsonRepositoryRead:
    """Test record reading"""

    def test_read_existing_record(self, repository):
        repository.create({"id": "readable", "data": "test"})
        result = repository.read("readable")

        assert result is not None
        assert result["id"] == "readable"
        assert result["data"] == "test"

    def test_read_nonexistent_record(self, repository):
        result = repository.read("nonexistent")
        assert result is None

    def test_read_returns_copy(self, repository):
        repository.create({"id": "copy_test", "value": 100})
        record = repository.read("copy_test")

        record["value"] = 999
        original = repository.read("copy_test")
        assert original["value"] == 100


class TestJsonRepositoryUpdate:
    """Test record updates"""

    def test_update_existing_record(self, repository):
        repository.create({"id": "updatable", "value": 10})
        result = repository.update("updatable", {"value": 20})

        assert result["value"] == 20
        assert "_updated_at" in result

    def test_update_partial_data(self, repository):
        repository.create({"id": "partial", "a": 1, "b": 2})
        result = repository.update("partial", {"b": 3})

        assert result["a"] == 1
        assert result["b"] == 3

    def test_update_nonexistent_record_raises(self, repository):
        with pytest.raises(RecordNotFoundError):
            repository.update("nonexistent", {"data": "test"})


class TestJsonRepositoryDelete:
    """Test record deletion"""

    def test_delete_existing_record(self, repository):
        repository.create({"id": "deletable"})
        result = repository.delete("deletable")

        assert result is True
        assert repository.read("deletable") is None

    def test_delete_nonexistent_record(self, repository):
        result = repository.delete("nonexistent")
        assert result is False


class TestJsonRepositoryList:
    """Test record listing with filters"""

    def test_list_all_records(self, repository):
        for i in range(5):
            repository.create({"id": f"list{i}", "category": "A"})

        for i in range(3):
            repository.create({"id": f"list_extra{i}", "category": "B"})

        results = repository.list()
        assert len(results) == 8

    def test_list_with_filters(self, repository):
        repository.create({"id": "filter1", "type": "A", "value": 1})
        repository.create({"id": "filter2", "type": "B", "value": 2})
        repository.create({"id": "filter3", "type": "A", "value": 3})

        results = repository.list(filters={"type": "A"})
        assert len(results) == 2
        assert all(r["type"] == "A" for r in results)

    def test_list_no_matches(self, repository):
        repository.create({"id": "match", "type": "A"})
        results = repository.list(filters={"type": "Z"})
        assert len(results) == 0


class TestJsonRepositoryVersioning:
    """Test version control"""

    def test_initial_version(self, repository):
        assert repository.get_version() == 0

    def test_version_increments_on_create(self, repository):
        repository.create({"id": "v1"})
        assert repository.get_version() == 1

        repository.create({"id": "v2"})
        assert repository.get_version() == 2

    def test_version_increments_on_update(self, repository):
        repository.create({"id": "versioned"})
        initial_version = repository.get_version()

        repository.update("versioned", {"data": "updated"})
        assert repository.get_version() == initial_version + 1

    def test_version_increments_on_delete(self, repository):
        repository.create({"id": "to_delete"})
        repository.delete("to_delete")
        assert repository.get_version() == 2

    def test_version_history(self, repository):
        repository.create({"id": "h1"})
        repository.create({"id": "h2"})
        repository.update("h1", {"updated": True})

        history = repository.get_version_history()
        assert len(history) == 3

        versions = [h["version"] for h in history]
        assert versions == [1, 2, 3]


class TestJsonRepositoryTransactions:
    """Test transaction support"""

    def test_begin_transaction(self, repository):
        repository.begin_transaction()
        assert repository._in_transaction is True

    def test_commit_transaction(self, repository):
        repository.begin_transaction()
        repository.create({"id": "tx1"})
        repository.create({"id": "tx2"})
        repository.commit()

        assert repository._in_transaction is False
        assert repository.read("tx1") is not None
        assert repository.read("tx2") is not None

    def test_rollback_transaction(self, repository):
        repository.create({"id": "before_tx"})
        original_version = repository.get_version()

        repository.begin_transaction()
        repository.create({"id": "tx_rolled_back"})
        repository.rollback()

        assert repository.read("tx_rolled_back") is None
        assert repository.get_version() == original_version

    def test_rollback_creates_snapshot(self, repository):
        repository.create({"id": "snapshot_test", "value": 100})
        original_version = repository.get_version()

        repository.begin_transaction()
        assert hasattr(repository, "_transaction_snapshot")

        repository.rollback()
        assert not hasattr(repository, "_transaction_snapshot")
        assert repository.get_version() == original_version


class TestJsonRepositoryPersistence:
    """Test data persistence across instances"""

    def test_data_persists_after_reload(self, temp_storage_dir):
        config = JsonConfig(data_directory=temp_storage_dir)

        repo1 = JsonRepository(config=config, store_name="persist_test")
        repo1.create({"id": "persisted", "data": "value"})

        repo2 = JsonRepository(config=config, store_name="persist_test")
        assert repo2.read("persisted")["data"] == "value"

    def test_version_persists_after_reload(self, temp_storage_dir):
        config = JsonConfig(data_directory=temp_storage_dir)

        repo1 = JsonRepository(config=config, store_name="version_test")
        repo1.create({"id": "v1"})
        repo1.create({"id": "v2"})

        repo2 = JsonRepository(config=config, store_name="version_test")
        assert repo2.get_version() == 2


class TestJsonRepositoryConcurrency:
    """Test concurrent access"""

    def test_concurrent_creates(self, repository):
        errors = []

        def create_records(thread_id):
            try:
                for i in range(10):
                    repository.create(
                        {
                            "id": f"concurrent_{thread_id}_{i}",
                            "thread": thread_id,
                        }
                    )
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=create_records, args=(i,)) for i in range(5)]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert repository.get_version() == 50

    def test_concurrent_reads(self, repository):
        repository.create({"id": "shared", "value": 42})

        results = []
        errors = []

        def read_record():
            try:
                for _ in range(100):
                    result = repository.read("shared")
                    results.append(result["value"])
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=read_record) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert all(v == 42 for v in results)

    def test_concurrent_mixed_operations(self, repository):
        repository.create({"id": "base"})

        errors = []

        def mixed_ops(thread_id):
            try:
                for i in range(20):
                    repo_id = f"mixed_{thread_id}_{i}"
                    repository.create({"id": repo_id, "thread": thread_id})
                    repository.read("base")
                    repository.update("base", {"thread": thread_id, "iteration": i})
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=mixed_ops, args=(i,)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0


class TestJsonRepositoryEdgeCases:
    """Test edge cases"""

    def test_empty_data_read(self, repository):
        result = repository.list()
        assert result == []

    def test_create_with_nested_data(self, repository):
        data = {
            "id": "nested",
            "nested": {"level1": {"level2": {"level3": "deep"}}},
            "list": [1, 2, 3],
        }
        result = repository.create(data)

        assert result["nested"]["level1"]["level2"]["level3"] == "deep"
        assert result["list"] == [1, 2, 3]

    def test_update_with_nested_data(self, repository):
        repository.create({"id": "nested_update", "data": {"a": 1}})
        result = repository.update("nested_update", {"extra": "field"})

        assert result["data"]["a"] == 1
        assert result["extra"] == "field"

    def test_special_characters_in_id(self, repository):
        special_ids = ["id-with-dash", "id_with_underscore", "id.with.dot"]
        for sid in special_ids:
            repository.create({"id": sid, "data": sid})
            assert repository.read(sid) is not None

    def test_unicode_data(self, repository):
        unicode_data = {
            "id": "unicode_test",
            "name": "测试数据",
            "description": "包含中文的记录",
        }
        result = repository.create(unicode_data)

        assert result["name"] == "测试数据"
        assert result["description"] == "包含中文的记录"

    def test_large_value(self, repository):
        large_data = {
            "id": "large",
            "large_array": list(range(10000)),
        }
        result = repository.create(large_data)

        assert len(result["large_array"]) == 10000


class TestJsonRepositoryNoVersionControl:
    """Test repository behavior without version control"""

    def test_operations_work_without_versioning(self, repository_no_version):
        repository_no_version.create({"id": "no_ver"})
        assert repository_no_version.read("no_ver") is not None

    def test_version_history_empty_without_versioning(self, repository_no_version):
        repository_no_version.create({"id": "test"})
        history = repository_no_version.get_version_history()
        assert len(history) == 0


class TestJsonRepositoryLockTimeout:
    """Test lock timeout behavior"""

    def test_lock_timeout_on_contention(self, temp_storage_dir):
        config = JsonConfig(data_directory=temp_storage_dir)
        repo1 = JsonRepository(config=config, store_name="lock_test")
        repo1._lock.acquire()

        try:
            repo2 = JsonRepository(config=config, store_name="lock_test")
            repo2._lock_acquired()
        except StorageError as e:
            assert "超时" in str(e)
        finally:
            repo1._lock.release()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
