"""
Settings Repository 服务

使用 Repository 模式管理应用设置，替代直接 SQLite 操作。
提供类型安全的设置访问、批量设置操作和默认值管理。
"""

import json
from typing import Any

from app.core.repository.factory import get_repository_factory


class SettingsService:
    """
    应用设置服务

    使用 SQLiteRepository 管理应用设置，提供：
    - 单个设置项读写
    - 批量设置操作
    - 设置分类管理
    - 默认值管理
    """

    DEFAULT_SETTINGS = {
        "python_backend_url": "http://127.0.0.1:8765",
        "ollama_url": "http://localhost:11434",
        "default_model": "qwen2.5-coder:7b",
        "theme": "dark",
        "auto_save": "true",
        "language": "zh-CN",
    }

    def __init__(self, repo=None):
        if repo is not None:
            self._repo = repo
        else:
            self._repo = get_repository_factory().get_repository("setting")

    def get(self, key: str, default: Any | None = None) -> Any:
        record = self._repo.read(key)
        if record is None:
            return self.DEFAULT_SETTINGS.get(key, default)

        try:
            return json.loads(record["value"])
        except (json.JSONDecodeError, KeyError):
            return record.get("value", default)

    def set(self, key: str, value: Any, category: str | None = None, description: str | None = None) -> dict[str, Any]:
        existing = self._repo.read(key)

        data = {
            "id": key,
            "value": json.dumps(value, ensure_ascii=False),
        }

        if category:
            data["category"] = category
        elif existing and existing.get("category"):
            data["category"] = existing["category"]

        if description:
            data["description"] = description
        elif existing and existing.get("description"):
            data["description"] = existing["description"]

        if existing:
            return self._repo.update(key, data)
        else:
            return self._repo.create(data)

    def delete(self, key: str) -> bool:
        return self._repo.delete(key)

    def get_all(self, category: str | None = None) -> dict[str, Any]:
        filters = {"category": category} if category else None
        records = self._repo.list(filters=filters)

        result = {}
        for record in records:
            try:
                result[record["id"]] = json.loads(record["value"])
            except (json.JSONDecodeError, KeyError):
                result[record["id"]] = record.get("value")

        for key, default_value in self.DEFAULT_SETTINGS.items():
            if key not in result:
                result[key] = default_value

        return result

    def set_batch(self, settings: dict[str, Any], category: str | None = None) -> list[dict[str, Any]]:
        results = []
        with self._repo.transaction():
            for key, value in settings.items():
                results.append(self.set(key, value, category=category))
        return results

    def reset(self, key: str) -> dict[str, Any]:
        if key not in self.DEFAULT_SETTINGS:
            raise KeyError(f"No default value for setting: {key}")
        return self.set(key, self.DEFAULT_SETTINGS[key])

    def reset_all(self) -> list[dict[str, Any]]:
        return self.set_batch(self.DEFAULT_SETTINGS, category="system")

    def get_category_list(self) -> list[str]:
        records = self._repo.list()
        categories = set()
        for record in records:
            if record.get("category"):
                categories.add(record["category"])
        return sorted(categories)

    def get_settings_with_metadata(self) -> list[dict[str, Any]]:
        records = self._repo.list()
        result = []
        for record in records:
            try:
                parsed_value = json.loads(record["value"])
            except (json.JSONDecodeError, KeyError):
                parsed_value = record.get("value")

            result.append({
                "key": record["id"],
                "value": parsed_value,
                "category": record.get("category"),
                "description": record.get("description"),
                "updated_at": record.get("updated_at"),
            })
        return result

    def close(self) -> None:
        self._repo.close()


_settings_service: SettingsService | None = None


def get_settings_service() -> SettingsService:
    global _settings_service
    if _settings_service is None:
        _settings_service = SettingsService()
    return _settings_service
