"""
Repository Factory 实现

根据数据类型或存储策略自动实例化对应的 Repository，确保单例模式。
"""

import contextlib
from threading import Lock

from app.core.repository.base import Repository
from app.core.repository.chroma_repository import ChromaRepository
from app.core.repository.config import RepositoryConfig, get_repository_config
from app.core.repository.exceptions import ConfigurationError
from app.core.repository.file_repository import FileRepository
from app.core.repository.json_repository import JsonRepository
from app.core.repository.sqlite_repository import SQLiteRepository


class RepositoryFactory:
    """
    Repository 工厂类

    负责：
    - 根据数据类型自动选择对应的 Repository
    - 确保同类 Repository 的单例实例
    - 集中管理存储配置
    """

    REPOSITORY_CLASSES = {
        "sqlite": SQLiteRepository,
        "chroma": ChromaRepository,
        "json": JsonRepository,
        "file": FileRepository,
    }

    def __init__(self, config: RepositoryConfig | None = None):
        self._config = config or get_repository_config()
        self._instances: dict[str, Repository] = {}
        self._lock = Lock()

    def get_repository(self, data_type: str, **kwargs) -> Repository:
        storage_type = self._resolve_storage_type(data_type)
        cache_key = f"{storage_type}:{data_type}"

        if cache_key not in self._instances:
            with self._lock:
                if cache_key not in self._instances:
                    repo = self._create_repository(storage_type, data_type, **kwargs)
                    self._instances[cache_key] = repo
        return self._instances[cache_key]

    def get_repository_by_storage_type(self, storage_type: str, name: str = "default", **kwargs) -> Repository:
        cache_key = f"{storage_type}:{name}"

        if cache_key not in self._instances:
            with self._lock:
                if cache_key not in self._instances:
                    repo = self._create_repository(storage_type, name, **kwargs)
                    self._instances[cache_key] = repo
        return self._instances[cache_key]

    def _resolve_storage_type(self, data_type: str) -> str:
        storage_type = self._config.type_mappings.get(data_type)
        if storage_type is None:
            raise ConfigurationError(
                f"Unknown data type: {data_type}. Available types: {list(self._config.type_mappings.keys())}"
            )
        return storage_type

    def _create_repository(self, storage_type: str, name: str, **kwargs) -> Repository:
        repo_class = self.REPOSITORY_CLASSES.get(storage_type)
        if repo_class is None:
            raise ConfigurationError(
                f"Unknown storage type: {storage_type}. Available types: {list(self.REPOSITORY_CLASSES.keys())}"
            )

        if storage_type == "sqlite":
            from app.core.repository.config import SQLiteConfig
            config = kwargs.pop("config", SQLiteConfig(db_path=self._config.sqlite.db_path))
            return repo_class(config=config, record_type=name, **kwargs)

        elif storage_type == "chroma":
            from app.core.repository.config import ChromaConfig
            config = kwargs.pop("config", ChromaConfig(persist_directory=self._config.chroma.persist_directory))
            return repo_class(config=config, collection_name=name, **kwargs)

        elif storage_type == "json":
            from app.core.repository.config import JsonConfig
            config = kwargs.pop("config", JsonConfig(data_directory=self._config.json.data_directory))
            return repo_class(config=config, store_name=name, **kwargs)

        elif storage_type == "file":
            from app.core.repository.config import FileConfig
            config = kwargs.pop("config", FileConfig(base_directory=self._config.files.base_directory))
            return repo_class(config=config, subdirectory=name, **kwargs)

        raise ConfigurationError(f"Cannot create repository for type: {storage_type}")

    def close_all(self) -> None:
        for repo in self._instances.values():
            with contextlib.suppress(Exception):
                repo.close()
        self._instances.clear()

    @property
    def config(self) -> RepositoryConfig:
        return self._config


_default_factory: RepositoryFactory | None = None
_factory_lock = Lock()


def get_repository_factory(config: RepositoryConfig | None = None) -> RepositoryFactory:
    """获取全局单例 Factory"""
    global _default_factory
    if _default_factory is None:
        with _factory_lock:
            if _default_factory is None:
                _default_factory = RepositoryFactory(config=config)
    return _default_factory
