"""
Project Repository 服务

使用 Repository 模式管理项目元数据，替代直接数据库操作。
提供项目 CRUD、状态管理、搜索和统计功能。
"""

import uuid
from datetime import datetime
from typing import Any

from app.core.repository.exceptions import RecordNotFoundError
from app.core.repository.factory import get_repository_factory


class ProjectService:
    """
    项目元数据服务

    使用 SQLiteRepository 管理项目数据，提供：
    - 项目 CRUD 操作
    - 项目状态管理
    - 项目搜索和筛选
    - 项目统计
    """

    VALID_STATUSES = {"draft", "active", "completed", "archived"}

    def __init__(self, repo=None):
        if repo is not None:
            self._repo = repo
        else:
            self._repo = get_repository_factory().get_repository("project")

    def create_project(
        self,
        name: str,
        description: str = "",
        scenario: str | None = None,
        status: str = "draft",
        model_path: str = "",
        nc_program_path: str = "",
    ) -> dict[str, Any]:
        if status not in self.VALID_STATUSES:
            raise ValueError(f"Invalid status: {status}. Must be one of {self.VALID_STATUSES}")

        project_id = str(uuid.uuid4())
        now = datetime.utcnow().isoformat()

        data = {
            "id": project_id,
            "name": name,
            "description": description,
            "scenario": scenario,
            "status": status,
            "created_at": now,
            "updated_at": now,
            "model_path": model_path,
            "nc_program_path": nc_program_path,
        }

        return self._repo.create(data)

    def get_project(self, project_id: str) -> dict[str, Any] | None:
        return self._repo.read(project_id)

    def update_project(self, project_id: str, updates: dict[str, Any]) -> dict[str, Any]:
        existing = self._repo.read(project_id)
        if existing is None:
            raise RecordNotFoundError(project_id, repository_type="project")

        if "status" in updates and updates["status"] not in self.VALID_STATUSES:
            raise ValueError(f"Invalid status: {updates['status']}")

        updates["updated_at"] = datetime.utcnow().isoformat()

        return self._repo.update(project_id, updates)

    def delete_project(self, project_id: str) -> bool:
        return self._repo.delete(project_id)

    def list_projects(
        self,
        status: str | None = None,
        scenario: str | None = None,
    ) -> list[dict[str, Any]]:
        filters = {}
        if status:
            filters["status"] = status
        if scenario:
            filters["scenario"] = scenario

        records = self._repo.list(filters=filters if filters else None)
        return sorted(records, key=lambda x: x.get("created_at", ""), reverse=True)

    def update_project_status(self, project_id: str, new_status: str) -> dict[str, Any]:
        if new_status not in self.VALID_STATUSES:
            raise ValueError(f"Invalid status: {new_status}")
        return self.update_project(project_id, {"status": new_status})

    def search_projects(self, keyword: str) -> list[dict[str, Any]]:
        all_projects = self.list_projects()
        keyword_lower = keyword.lower()
        return [
            p for p in all_projects
            if keyword_lower in p.get("name", "").lower()
            or keyword_lower in p.get("description", "").lower()
        ]

    def get_project_stats(self) -> dict[str, Any]:
        all_projects = self.list_projects()
        total = len(all_projects)
        status_counts = {}
        scenario_counts = {}

        for project in all_projects:
            status = project.get("status", "unknown")
            status_counts[status] = status_counts.get(status, 0) + 1

            scenario = project.get("scenario")
            if scenario:
                scenario_counts[scenario] = scenario_counts.get(scenario, 0) + 1

        return {
            "total_projects": total,
            "status_distribution": status_counts,
            "scenario_distribution": scenario_counts,
        }

    def bulk_update_status(self, project_ids: list[str], new_status: str) -> int:
        if new_status not in self.VALID_STATUSES:
            raise ValueError(f"Invalid status: {new_status}")

        count = 0
        with self._repo.transaction():
            for project_id in project_ids:
                try:
                    self.update_project(project_id, {"status": new_status})
                    count += 1
                except RecordNotFoundError:
                    pass
        return count

    def close(self) -> None:
        self._repo.close()


_project_service: ProjectService | None = None


def get_project_service() -> ProjectService:
    global _project_service
    if _project_service is None:
        _project_service = ProjectService()
    return _project_service
