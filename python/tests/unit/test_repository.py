"""
Repository 单元测试套件

为每个 Repository 实现提供独立单元测试，模拟存储依赖，确保测试隔离性。
覆盖 CRUD 操作、异常处理、边界条件。
"""

import contextlib
import json
import os
import tempfile

import pytest

from app.core.repository.chroma_repository import ChromaRepository
from app.core.repository.config import (
    ChromaConfig,
    FileConfig,
    JsonConfig,
    SQLiteConfig,
)
from app.core.repository.exceptions import (
    ValidationError,
)
from app.core.repository.file_repository import FileRepository
from app.core.repository.json_repository import JsonRepository
from app.core.repository.sqlite_repository import SQLiteRepository


class TestSQLiteRepository:
    @pytest.fixture
    def repo(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            config = SQLiteConfig(db_path=db_path)
            repo = SQLiteRepository(config=config, record_type="setting")
            yield repo
            repo.close()

    def test_create_and_read(self, repo):
        data = {"id": "theme", "value": json.dumps("dark"), "category": "ui"}
        created = repo.create(data)

        assert created["id"] == "theme"
        assert created["category"] == "ui"

        read = repo.read("theme")
        assert read is not None
        assert read["id"] == "theme"

    def test_update(self, repo):
        repo.create({"id": "theme", "value": json.dumps("dark")})

        updated = repo.update("theme", {"value": json.dumps("light")})
        assert updated["value"] == json.dumps("light")

        read = repo.read("theme")
        assert read["value"] == json.dumps("light")

    def test_delete(self, repo):
        repo.create({"id": "temp", "value": json.dumps("test")})
        assert repo.delete("temp") is True
        assert repo.read("temp") is None

    def test_delete_nonexistent(self, repo):
        assert repo.delete("nonexistent") is False

    def test_list(self, repo):
        repo.create({"id": "s1", "value": json.dumps("v1"), "category": "a"})
        repo.create({"id": "s2", "value": json.dumps("v2"), "category": "a"})
        repo.create({"id": "s3", "value": json.dumps("v3"), "category": "b"})

        all_items = repo.list()
        assert len(all_items) == 3

        filtered = repo.list(filters={"category": "a"})
        assert len(filtered) == 2

    def test_create_duplicate(self, repo):
        repo.create({"id": "key1", "value": json.dumps("v1")})
        with pytest.raises((ValueError, Exception)):
            repo.create({"id": "key1", "value": json.dumps("v2")})

    def test_transaction_commit(self, repo):
        repo.begin_transaction()
        repo.create({"id": "t1", "value": json.dumps("v1")})
        repo.commit()

        assert repo.read("t1") is not None

    def test_transaction_rollback(self, repo):
        repo.begin_transaction()
        repo.create({"id": "t2", "value": json.dumps("v2")})
        repo.rollback()

        assert repo.read("t2") is None

    def test_context_manager_transaction(self, repo):
        with repo.transaction():
            repo.create({"id": "ctx1", "value": json.dumps("v1")})

        assert repo.read("ctx1") is not None

    def test_context_manager_rollback_on_error(self, repo):
        try:
            with repo.transaction():
                repo.create({"id": "ctx2", "value": json.dumps("v2")})
                raise ValueError("Simulated error")
        except ValueError:
            pass

        assert repo.read("ctx2") is None

    def test_bulk_create(self, repo):
        records = [
            {"id": "b1", "value": json.dumps("v1")},
            {"id": "b2", "value": json.dumps("v2")},
            {"id": "b3", "value": json.dumps("v3")},
        ]
        created = repo.bulk_create(records)
        assert len(created) == 3
        assert repo.read("b1") is not None
        assert repo.read("b2") is not None

    def test_bulk_delete(self, repo):
        repo.create({"id": "d1", "value": json.dumps("v1")})
        repo.create({"id": "d2", "value": json.dumps("v2")})
        repo.create({"id": "d3", "value": json.dumps("v3")})

        count = repo.bulk_delete(["d1", "d2"])
        assert count == 2
        assert repo.read("d1") is None
        assert repo.read("d3") is not None


class TestChromaRepository:
    @pytest.fixture
    def repo(self):
        import tempfile
        tmpdir = tempfile.mkdtemp()
        persist_dir = os.path.join(tmpdir, "chroma")
        os.makedirs(persist_dir, exist_ok=True)
        try:
            config = ChromaConfig(persist_directory=persist_dir)
            repo = ChromaRepository(config=config, collection_name="test_collection")
            yield repo
        finally:
            import shutil
            with contextlib.suppress(Exception):
                shutil.rmtree(tmpdir, ignore_errors=True)

    def test_create_and_read(self, repo):
        data = {
            "id": "doc1",
            "document": "This is a test document about manufacturing",
            "metadata": {"type": "test", "category": "manufacturing"},
        }
        created = repo.create(data)

        assert created["id"] == "doc1"
        assert created["document"] == data["document"]

        read = repo.read("doc1")
        assert read is not None
        assert read["document"] == data["document"]

    def test_update(self, repo):
        repo.create({
            "id": "doc2",
            "document": "Original content",
            "metadata": {"version": "1"},
        })

        updated = repo.update("doc2", {
            "document": "Updated content",
            "metadata": {"version": "2"},
        })
        assert updated["document"] == "Updated content"

    def test_delete(self, repo):
        repo.create({"id": "doc3", "document": "Test document"})
        assert repo.delete("doc3") is True
        assert repo.read("doc3") is None

    def test_delete_nonexistent(self, repo):
        assert repo.delete("nonexistent") is False

    def test_list(self, repo):
        repo.create({"id": "d1", "document": "doc one", "metadata": {"tag": "a"}})
        repo.create({"id": "d2", "document": "doc two", "metadata": {"tag": "a"}})
        repo.create({"id": "d3", "document": "doc three", "metadata": {"tag": "b"}})

        all_items = repo.list()
        assert len(all_items) == 3

        filtered = repo.list(filters={"tag": "a"})
        assert len(filtered) == 2

    def test_query_similar(self, repo):
        repo.create({"id": "v1", "document": "车削加工基础参数说明"})
        repo.create({"id": "v2", "document": "铣削加工工艺参数"})
        repo.create({"id": "v3", "document": "磨削表面粗糙度控制"})

        results = repo.query_similar("车削加工", n_results=2)
        assert len(results) <= 2

    def test_bulk_add_vectors(self, repo):
        documents = ["doc1", "doc2", "doc3"]
        ids = repo.bulk_add_vectors(documents)
        assert len(ids) == 3
        assert repo.count() == 3

    def test_transaction_commit(self, repo):
        repo.begin_transaction()
        repo.create({"id": "t1", "document": "test1"})
        repo.commit()

        assert repo.read("t1") is not None

    def test_transaction_rollback(self, repo):
        repo.begin_transaction()
        repo.create({"id": "t2", "document": "test2"})
        repo.rollback()

        assert repo.read("t2") is None


class TestJsonRepository:
    @pytest.fixture
    def repo(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config = JsonConfig(data_directory=tmpdir, version_control=True)
            repo = JsonRepository(config=config, store_name="test_store")
            yield repo

    def test_create_and_read(self, repo):
        data = {"id": "item1", "name": "Test Item", "value": 42}
        created = repo.create(data)

        assert created["id"] == "item1"
        assert created["name"] == "Test Item"

        read = repo.read("item1")
        assert read is not None
        assert read["name"] == "Test Item"

    def test_update(self, repo):
        repo.create({"id": "item2", "name": "Old Name"})
        updated = repo.update("item2", {"name": "New Name"})

        assert updated["name"] == "New Name"
        assert repo.read("item2")["name"] == "New Name"

    def test_delete(self, repo):
        repo.create({"id": "item3", "data": "test"})
        assert repo.delete("item3") is True
        assert repo.read("item3") is None

    def test_delete_nonexistent(self, repo):
        assert repo.delete("nonexistent") is False

    def test_list(self, repo):
        repo.create({"id": "r1", "type": "a", "value": 1})
        repo.create({"id": "r2", "type": "a", "value": 2})
        repo.create({"id": "r3", "type": "b", "value": 3})

        all_items = repo.list()
        assert len(all_items) == 3

        filtered = repo.list(filters={"type": "a"})
        assert len(filtered) == 2

    def test_version_control(self, repo):
        repo.create({"id": "v1", "data": "initial"})
        version_after_create = repo.get_version()

        repo.update("v1", {"data": "updated"})
        version_after_update = repo.get_version()

        assert version_after_update > version_after_create

    def test_version_history(self, repo):
        repo.create({"id": "vh1", "data": "data1"})
        repo.update("vh1", {"data": "data2"})
        repo.update("vh1", {"data": "data3"})

        history = repo.get_version_history()
        assert len(history) >= 3

    def test_create_duplicate(self, repo):
        repo.create({"id": "dup1", "data": "test"})
        with pytest.raises(ValueError):
            repo.create({"id": "dup1", "data": "test2"})

    def test_create_without_id(self, repo):
        with pytest.raises(ValidationError):
            repo.create({"data": "no id"})

    def test_transaction_commit(self, repo):
        repo.begin_transaction()
        repo.create({"id": "tx1", "data": "test"})
        repo.commit()

        assert repo.read("tx1") is not None

    def test_transaction_rollback(self, repo):
        repo.begin_transaction()
        repo.create({"id": "tx2", "data": "test"})
        repo.rollback()

        assert repo.read("tx2") is None

    def test_context_manager_transaction(self, repo):
        with repo.transaction():
            repo.create({"id": "ctx1", "data": "context test"})

        assert repo.read("ctx1") is not None


class TestFileRepository:
    @pytest.fixture
    def repo(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config = FileConfig(base_directory=tmpdir, use_hash_verification=True)
            repo = FileRepository(config=config, subdirectory="test_files")
            yield repo

    def test_create_and_read(self, repo):
        data = {
            "id": "file1.txt",
            "content": "Hello, World!",
            "category": "text",
            "description": "Test file",
        }
        created = repo.create(data)

        assert created["id"] == "file1.txt"
        assert created["category"] == "text"

        read = repo.read("file1.txt")
        assert read is not None
        assert read["exists"] is True

    def test_update(self, repo):
        repo.create({"id": "file2.txt", "content": "Original content"})
        updated = repo.update("file2.txt", {"content": "Updated content"})

        assert updated["size"] > 0

    def test_delete(self, repo):
        repo.create({"id": "file3.txt", "content": "To be deleted"})
        assert repo.delete("file3.txt") is True
        assert repo.read("file3.txt") is None

    def test_delete_nonexistent(self, repo):
        assert repo.delete("nonexistent") is False

    def test_list(self, repo):
        repo.create({"id": "f1.txt", "content": "content1", "category": "a"})
        repo.create({"id": "f2.txt", "content": "content2", "category": "a"})
        repo.create({"id": "f3.txt", "content": "content3", "category": "b"})

        all_items = repo.list()
        assert len(all_items) == 3

        filtered = repo.list(filters={"category": "a"})
        assert len(filtered) == 2

    def test_read_file_content(self, repo):
        repo.create({"id": "read_test.txt", "content": "Test content"})
        content = repo.read_file_content("read_test.txt")
        assert content == b"Test content"

    def test_file_hash_verification(self, repo):
        repo.create({"id": "hash_test.txt", "content": "Content for hash"})
        metadata = repo.read("hash_test.txt")
        assert "hash" in metadata

    def test_get_file_size(self, repo):
        content = "Size test content"
        repo.create({"id": "size_test.txt", "content": content})
        size = repo.get_file_size("size_test.txt")
        assert size > 0

    def test_transaction_commit(self, repo):
        repo.begin_transaction()
        repo.create({"id": "tx_file.txt", "content": "Transaction test"})
        repo.commit()

        assert repo.read("tx_file.txt") is not None

    def test_transaction_rollback(self, repo):
        repo.begin_transaction()
        repo.create({"id": "rollback_file.txt", "content": "Should be rolled back"})
        repo.rollback()

        assert repo.read("rollback_file.txt") is None

    def test_context_manager_transaction(self, repo):
        with repo.transaction():
            repo.create({"id": "ctx_file.txt", "content": "Context manager test"})

        assert repo.read("ctx_file.txt") is not None
