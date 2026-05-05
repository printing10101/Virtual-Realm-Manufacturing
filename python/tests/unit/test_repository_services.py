"""
Settings 和 Project Repository 服务测试

验证 settings_repository 和 project_repository 的业务逻辑。
"""

import os
import tempfile

import pytest

from app.core.repository.config import (
    ChromaConfig,
    FileConfig,
    JsonConfig,
    RepositoryConfig,
    SQLiteConfig,
)
from app.core.repository.factory import RepositoryFactory
from app.services.project_repository import ProjectService
from app.services.settings_repository import SettingsService


@pytest.fixture
def test_config():
    with tempfile.TemporaryDirectory() as tmpdir:
        yield RepositoryConfig(
            sqlite=SQLiteConfig(db_path=os.path.join(tmpdir, "test.db")),
            chroma=ChromaConfig(persist_directory=os.path.join(tmpdir, "chroma")),
            json=JsonConfig(data_directory=os.path.join(tmpdir, "json")),
            files=FileConfig(base_directory=os.path.join(tmpdir, "files")),
        )


@pytest.fixture
def sqlite_repo_for_settings(test_config):
    factory = RepositoryFactory(config=test_config)
    repo = factory.get_repository("setting")
    yield repo
    repo.close()


@pytest.fixture
def sqlite_repo_for_projects(test_config):
    factory = RepositoryFactory(config=test_config)
    repo = factory.get_repository("project")
    yield repo
    repo.close()


class TestSettingsService:
    @pytest.fixture
    def service(self, sqlite_repo_for_settings):
        return SettingsService(repo=sqlite_repo_for_settings)

    def test_get_default(self, service):
        value = service.get("python_backend_url")
        assert value == "http://127.0.0.1:8765"

    def test_set_and_get(self, service):
        service.set("custom_key", "custom_value")
        assert service.get("custom_key") == "custom_value"

    def test_get_nonexistent_with_default(self, service):
        value = service.get("nonexistent", default="fallback")
        assert value == "fallback"

    def test_set_batch(self, service):
        settings = {
            "batch_key1": "value1",
            "batch_key2": "value2",
            "batch_key3": "value3",
        }
        results = service.set_batch(settings)
        assert len(results) == 3
        assert service.get("batch_key1") == "value1"

    def test_get_all(self, service):
        service.set("test1", "v1")
        service.set("test2", "v2")

        all_settings = service.get_all()
        assert "test1" in all_settings
        assert "test2" in all_settings

    def test_reset(self, service):
        service.set("python_backend_url", "http://changed")
        service.reset("python_backend_url")
        assert service.get("python_backend_url") == "http://127.0.0.1:8765"

    def test_get_category_list(self, service):
        service.set("cat1_key", "v1", category="cat1")
        service.set("cat2_key", "v2", category="cat2")

        categories = service.get_category_list()
        assert "cat1" in categories
        assert "cat2" in categories


class TestProjectService:
    @pytest.fixture
    def service(self, sqlite_repo_for_projects):
        return ProjectService(repo=sqlite_repo_for_projects)

    def test_create_project(self, service):
        project = service.create_project(
            name="Test Project",
            description="A test project",
            scenario="robotics",
        )
        assert project["name"] == "Test Project"
        assert project["scenario"] == "robotics"
        assert project["status"] == "draft"

    def test_get_project(self, service):
        project = service.create_project(name="Get Test")
        retrieved = service.get_project(project["id"])
        assert retrieved is not None
        assert retrieved["name"] == "Get Test"

    def test_update_project(self, service):
        project = service.create_project(name="Update Test")
        updated = service.update_project(project["id"], {"name": "Updated Name"})
        assert updated["name"] == "Updated Name"

    def test_delete_project(self, service):
        project = service.create_project(name="Delete Test")
        assert service.delete_project(project["id"]) is True
        assert service.get_project(project["id"]) is None

    def test_list_projects(self, service):
        service.create_project(name="P1", status="draft")
        service.create_project(name="P2", status="active")
        service.create_project(name="P3", status="draft")

        all_projects = service.list_projects()
        assert len(all_projects) >= 3

        drafts = service.list_projects(status="draft")
        assert len(drafts) >= 2

    def test_update_project_status(self, service):
        project = service.create_project(name="Status Test")
        service.update_project_status(project["id"], "active")

        retrieved = service.get_project(project["id"])
        assert retrieved["status"] == "active"

    def test_invalid_status_raises_error(self, service):
        with pytest.raises(ValueError):
            service.create_project(name="Invalid", status="invalid_status")

    def test_search_projects(self, service):
        service.create_project(name="车削加工项目", description="车削相关")
        service.create_project(name="铣削加工项目", description="铣削相关")

        results = service.search_projects("车削")
        assert len(results) >= 1

    def test_get_project_stats(self, service):
        service.create_project(name="S1", status="draft")
        service.create_project(name="S2", status="active")
        service.create_project(name="S3", status="draft")

        stats = service.get_project_stats()
        assert stats["total_projects"] >= 3
        assert "draft" in stats["status_distribution"]

    def test_bulk_update_status(self, service):
        p1 = service.create_project(name="B1")
        p2 = service.create_project(name="B2")
        p3 = service.create_project(name="B3")

        count = service.bulk_update_status(
            [p1["id"], p2["id"], p3["id"]],
            "completed"
        )
        assert count == 3

        assert service.get_project(p1["id"])["status"] == "completed"
        assert service.get_project(p2["id"])["status"] == "completed"
