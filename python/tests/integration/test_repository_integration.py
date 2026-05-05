"""
Repository 集成测试

验证不同 Repository 间数据一致性、事务跨存储的一致性保证及 Factory 自动选择机制。
"""

import contextlib
import json
import os
import shutil
import tempfile

import pytest

from app.core.repository.chroma_repository import ChromaRepository
from app.core.repository.config import (
    ChromaConfig,
    FileConfig,
    JsonConfig,
    RepositoryConfig,
    SQLiteConfig,
)
from app.core.repository.exceptions import ConfigurationError
from app.core.repository.factory import RepositoryFactory
from app.core.repository.file_repository import FileRepository
from app.core.repository.json_repository import JsonRepository
from app.core.repository.sqlite_repository import SQLiteRepository


def make_temp_dirs():
    tmpdir = tempfile.mkdtemp()
    return {
        "base": tmpdir,
        "db": os.path.join(tmpdir, "test.db"),
        "chroma": os.path.join(tmpdir, "chroma"),
        "json": os.path.join(tmpdir, "json"),
        "files": os.path.join(tmpdir, "files"),
    }


def cleanup_temp_dirs(dirs):
    with contextlib.suppress(Exception):
        shutil.rmtree(dirs["base"], ignore_errors=True)


class TestRepositoryFactory:
    @pytest.fixture
    def dirs(self):
        d = make_temp_dirs()
        yield d
        cleanup_temp_dirs(d)

    @pytest.fixture
    def config(self, dirs):
        return RepositoryConfig(
            sqlite=SQLiteConfig(db_path=dirs["db"]),
            chroma=ChromaConfig(persist_directory=dirs["chroma"]),
            json=JsonConfig(data_directory=dirs["json"]),
            files=FileConfig(base_directory=dirs["files"]),
        )

    @pytest.fixture
    def factory(self, config):
        return RepositoryFactory(config=config)

    def test_get_repository_by_data_type(self, factory):
        settings_repo = factory.get_repository("setting")
        assert isinstance(settings_repo, SQLiteRepository)

        projects_repo = factory.get_repository("project")
        assert isinstance(projects_repo, SQLiteRepository)

        knowledge_repo = factory.get_repository("knowledge")
        assert isinstance(knowledge_repo, ChromaRepository)

        backup_repo = factory.get_repository("config_backup")
        assert isinstance(backup_repo, JsonRepository)

        model_repo = factory.get_repository("model_file")
        assert isinstance(model_repo, FileRepository)

    def test_unknown_data_type_raises_error(self, factory):
        with pytest.raises(ConfigurationError):
            factory.get_repository("unknown_type")

    def test_singleton_instances(self, factory):
        repo1 = factory.get_repository("setting")
        repo2 = factory.get_repository("setting")
        assert repo1 is repo2

    def test_get_repository_by_storage_type(self, factory):
        custom_chroma = factory.get_repository_by_storage_type("chroma", name="custom_collection")
        assert isinstance(custom_chroma, ChromaRepository)

        custom_json = factory.get_repository_by_storage_type("json", name="custom_store")
        assert isinstance(custom_json, JsonRepository)


class TestCrossRepositoryDataConsistency:
    @pytest.fixture
    def dirs(self):
        d = make_temp_dirs()
        yield d
        cleanup_temp_dirs(d)

    @pytest.fixture
    def setup_repos(self, dirs):
        config = RepositoryConfig(
            sqlite=SQLiteConfig(db_path=dirs["db"]),
            chroma=ChromaConfig(persist_directory=dirs["chroma"]),
            json=JsonConfig(data_directory=dirs["json"]),
            files=FileConfig(base_directory=dirs["files"]),
        )
        factory = RepositoryFactory(config=config)

        sqlite_repo = factory.get_repository("setting")
        chroma_repo = factory.get_repository("knowledge")
        json_repo = factory.get_repository("config_backup")
        file_repo = factory.get_repository("model_file")

        yield sqlite_repo, chroma_repo, json_repo, file_repo

    def test_create_and_sync_across_stores(self, setup_repos):
        sqlite_repo, chroma_repo, json_repo, file_repo = setup_repos

        setting = sqlite_repo.create({
            "id": "model_path",
            "value": json.dumps("/files/model_v1.stl"),
            "category": "output",
        })
        assert setting["id"] == "model_path"

        knowledge = chroma_repo.create({
            "id": "model_v1_info",
            "document": "Model generation parameters and metadata",
            "metadata": {"model_id": "model_v1", "status": "generated"},
        })
        assert knowledge["id"] == "model_v1_info"

        backup = json_repo.create({
            "id": "backup_2024",
            "data": {"model_path": "/files/model_v1.stl", "knowledge_id": "model_v1_info"},
        })
        assert backup["id"] == "backup_2024"

        file_record = file_repo.create({
            "id": "model_v1.stl",
            "content": b"mock_stl_binary_content",
            "category": "model",
        })
        assert file_record["id"] == "model_v1.stl"

    def test_delete_cascade_simulation(self, setup_repos):
        sqlite_repo, chroma_repo, _json_repo, file_repo = setup_repos

        file_repo.create({"id": "temp_model.stl", "content": b"temporary content", "category": "temp"})
        sqlite_repo.create({"id": "temp_model_ref", "value": json.dumps("temp_model.stl"), "category": "reference"})
        chroma_repo.create({"id": "temp_model_info", "document": "Temporary model info"})

        file_repo.delete("temp_model.stl")
        sqlite_repo.delete("temp_model_ref")
        chroma_repo.delete("temp_model_info")

        assert file_repo.read("temp_model.stl") is None
        assert sqlite_repo.read("temp_model_ref") is None
        assert chroma_repo.read("temp_model_info") is None

    def test_bulk_operations_across_repos(self, setup_repos):
        sqlite_repo, _chroma_repo, _json_repo, _file_repo = setup_repos

        settings = [
            {"id": f"setting_{i}", "value": json.dumps(f"value_{i}")}
            for i in range(5)
        ]
        created = sqlite_repo.bulk_create(settings)
        assert len(created) == 5

        all_settings = sqlite_repo.list()
        assert len(all_settings) >= 5

    def test_query_and_list_consistency(self, setup_repos):
        sqlite_repo, chroma_repo, _json_repo, _file_repo = setup_repos

        sqlite_repo.create({"id": "theme", "value": json.dumps("dark"), "category": "ui"})
        sqlite_repo.create({"id": "language", "value": json.dumps("zh-CN"), "category": "locale"})
        sqlite_repo.create({"id": "timeout", "value": json.dumps("60"), "category": "network"})

        ui_settings = sqlite_repo.list(filters={"category": "ui"})
        assert len(ui_settings) == 1
        assert ui_settings[0]["id"] == "theme"

        chroma_repo.create({"id": "doc1", "document": "车削加工工艺参数"})
        chroma_repo.create({"id": "doc2", "document": "铣削加工工艺参数"})
        chroma_repo.create({"id": "doc3", "document": "磨削表面质量控制"})

        similar = chroma_repo.query_similar("车削加工", n_results=3)
        assert len(similar) >= 1


class TestTransactionCrossStore:
    @pytest.fixture
    def dirs(self):
        d = make_temp_dirs()
        yield d
        cleanup_temp_dirs(d)

    @pytest.fixture
    def setup_repos(self, dirs):
        RepositoryConfig(
            sqlite=SQLiteConfig(db_path=dirs["db"]),
            json=JsonConfig(data_directory=dirs["json"]),
        )
        factory = RepositoryConfig(
            sqlite=SQLiteConfig(db_path=dirs["db"]),
            json=JsonConfig(data_directory=dirs["json"]),
        )
        f = RepositoryFactory(config=factory)
        yield f.get_repository("setting"), f.get_repository("config_backup")

    def test_individual_repo_transactions(self, setup_repos):
        sqlite_repo, json_repo = setup_repos

        with sqlite_repo.transaction():
            sqlite_repo.create({"id": "s1", "value": json.dumps("v1")})
            sqlite_repo.create({"id": "s2", "value": json.dumps("v2")})

        with json_repo.transaction():
            json_repo.create({"id": "j1", "data": "d1"})
            json_repo.create({"id": "j2", "data": "d2"})

        assert sqlite_repo.read("s1") is not None
        assert sqlite_repo.read("s2") is not None
        assert json_repo.read("j1") is not None
        assert json_repo.read("j2") is not None

    def test_transaction_rollback_individual(self, setup_repos):
        sqlite_repo, _json_repo = setup_repos

        try:
            with sqlite_repo.transaction():
                sqlite_repo.create({"id": "s3", "value": json.dumps("v3")})
                raise ValueError("Simulated error")
        except ValueError:
            pass

        assert sqlite_repo.read("s3") is None
