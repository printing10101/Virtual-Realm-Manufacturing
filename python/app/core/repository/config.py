"""
Repository 配置管理模块

集中管理各存储方式的连接参数和配置信息，支持数据类型与存储方式的映射。
"""

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class SQLiteConfig:
    """SQLite 存储配置"""
    db_path: str = ""
    pool_size: int = 5
    max_overflow: int = 10
    echo: bool = False

    def __post_init__(self):
        if not self.db_path:
            project_root = Path(__file__).parent.parent.parent.parent
            self.db_path = str(project_root / "data" / "app.db")

        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)


@dataclass
class ChromaConfig:
    """ChromaDB 存储配置"""
    persist_directory: str = ""

    def __post_init__(self):
        if not self.persist_directory:
            project_root = Path(__file__).parent.parent.parent.parent
            self.persist_directory = str(project_root / "data" / "chroma_db")

        Path(self.persist_directory).mkdir(parents=True, exist_ok=True)


@dataclass
class JsonConfig:
    """JSON 文件存储配置"""
    data_directory: str = ""
    use_file_lock: bool = True
    version_control: bool = True

    def __post_init__(self):
        if not self.data_directory:
            project_root = Path(__file__).parent.parent.parent.parent
            self.data_directory = str(project_root / "data" / "json_store")

        Path(self.data_directory).mkdir(parents=True, exist_ok=True)


@dataclass
class FileConfig:
    """文件系统存储配置"""
    base_directory: str = ""
    chunk_size: int = 1024 * 1024  # 1MB
    use_hash_verification: bool = True

    def __post_init__(self):
        if not self.base_directory:
            project_root = Path(__file__).parent.parent.parent.parent
            self.base_directory = str(project_root / "data" / "files")

        Path(self.base_directory).mkdir(parents=True, exist_ok=True)


@dataclass
class RepositoryConfig:
    """统一 Repository 配置"""
    sqlite: SQLiteConfig = field(default_factory=SQLiteConfig)
    chroma: ChromaConfig = field(default_factory=ChromaConfig)
    json: JsonConfig = field(default_factory=JsonConfig)
    files: FileConfig = field(default_factory=FileConfig)

    # 数据类型到存储方式的映射
    type_mappings: dict[str, str] = field(default_factory=lambda: {
        "setting": "sqlite",
        "project": "sqlite",
        "knowledge": "chroma",
        "experience": "chroma",
        "config_backup": "json",
        "route_stats": "json",
        "model_file": "file",
        "log_file": "file",
    })


_default_config: RepositoryConfig | None = None


def get_repository_config() -> RepositoryConfig:
    """获取全局单例配置"""
    global _default_config
    if _default_config is None:
        _default_config = RepositoryConfig()
    return _default_config


def set_repository_config(config: RepositoryConfig) -> None:
    """设置全局配置"""
    global _default_config
    _default_config = config
