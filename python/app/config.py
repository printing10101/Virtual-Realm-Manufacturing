import os
from dataclasses import dataclass, field

# 项目根目录（python/ 的上级目录，即项目根）
PROJECT_ROOT: str = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# Python包目录
PYTHON_DIR: str = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

_ROOT_DIR = PROJECT_ROOT


def _env(key: str, default: str = "") -> str:
    return os.environ.get(key, default)


def _path(key: str, default_rel: str) -> str:
    return _env(key, os.path.join(_ROOT_DIR, default_rel))


@dataclass
class ServerConfig:
    host: str = field(default_factory=lambda: _env("SERVER_HOST", "127.0.0.1"))
    port: int = field(default_factory=lambda: int(_env("SERVER_PORT", "8765")))
    debug: bool = field(default_factory=lambda: _env("DEBUG", "false").lower() == "true")


@dataclass
class AIConfig:
    mode: str = field(default_factory=lambda: _env("AI_MODE", "local"))
    ollama_base_url: str = field(default_factory=lambda: _env("OLLAMA_BASE_URL", "http://localhost:11434"))
    ollama_model: str = field(default_factory=lambda: _env("OLLAMA_MODEL", "qwen2.5-coder:7b"))
    cloud_api_key: str = field(default_factory=lambda: _env("CLOUD_API_KEY", ""))
    cloud_base_url: str = field(default_factory=lambda: _env("CLOUD_BASE_URL", "https://api.openai.com/v1"))
    cloud_model: str = field(default_factory=lambda: _env("CLOUD_MODEL", "gpt-3.5-turbo"))
    timeout: int = field(default_factory=lambda: int(_env("AI_TIMEOUT", "60")))
    max_retries: int = field(default_factory=lambda: int(_env("AI_MAX_RETRIES", "3")))


@dataclass
class StorageConfig:
    output_dir: str = field(default_factory=lambda: _path("OUTPUT_DIR", "output"))
    temp_dir: str = field(default_factory=lambda: _path("TEMP_DIR", "temp"))


@dataclass
class DatabaseConfig:
    cad_db_path: str = field(default_factory=lambda: _path("CAD_DB_PATH", "cad_tasks.db"))
    model_library_path: str = field(default_factory=lambda: _path("MODEL_LIBRARY_PATH", "model_library.db"))


@dataclass
class ModelRouterSettings:
    local_model: str = field(default_factory=lambda: _env("LOCAL_MODEL", "qwen2.5:7b"))
    cloud_provider: str = field(default_factory=lambda: _env("CLOUD_PROVIDER", "openai"))
    cloud_model: str = field(default_factory=lambda: _env("CLOUD_MODEL_ROUTER", "gpt-4o"))
    fallback_threshold: int = field(default_factory=lambda: int(_env("FALLBACK_THRESHOLD", "3")))
    local_timeout: int = field(default_factory=lambda: int(_env("LOCAL_TIMEOUT", "30")))


@dataclass
class FineTuneSettings:
    finetune_auto_trigger: bool = field(default_factory=lambda: _env("FINETUNE_AUTO_TRIGGER", "false").lower() == "true")
    finetune_min_samples: int = field(default_factory=lambda: int(_env("FINETUNE_MIN_SAMPLES", "50")))
    finetune_interval_days: int = field(default_factory=lambda: int(_env("FINETUNE_INTERVAL_DAYS", "7")))
    finetune_output_dir: str = field(default_factory=lambda: _path("FINETUNE_OUTPUT_DIR", os.path.join("output", "models", "finetuned")))


@dataclass
class SecurityConfig:
    cors_origins: list[str] = field(default_factory=lambda: [
        origin.strip() for origin in _env("CORS_ORIGINS", "*").split(",") if origin.strip()
    ])
    allow_credentials: bool = field(default_factory=lambda: _env("CORS_ALLOW_CREDENTIALS", "true").lower() == "true")
    rate_limit_enabled: bool = field(default_factory=lambda: _env("RATE_LIMIT_ENABLED", "false").lower() == "true")
    rate_limit_requests: int = field(default_factory=lambda: int(_env("RATE_LIMIT_REQUESTS", "100")))
    rate_limit_window: int = field(default_factory=lambda: int(_env("RATE_LIMIT_WINDOW", "60")))


@dataclass
class EnvironmentConfig:
    environment: str = field(default_factory=lambda: _env("ENVIRONMENT", "development").lower())


@dataclass
class PathsConfig:
    backup_dir: str = field(default_factory=lambda: _env("BACKUP_DIR", "./backups"))
    db_path: str = field(default_factory=lambda: _env("DB_PATH", "./data/app.db"))
    vector_db_path: str = field(default_factory=lambda: _env("VECTOR_DB_PATH", "./data/chroma_db"))
    config_path: str = field(default_factory=lambda: _env("CONFIG_PATH", "./config.json"))


@dataclass
class AppConfig:
    app_name: str = field(default_factory=lambda: _env("APP_NAME", "灵境制造"))
    app_version: str = field(default_factory=lambda: _env("APP_VERSION", "1.7.0"))
    offline_mode: bool = field(default_factory=lambda: _env("OFFLINE_MODE", "false").lower() == "true")
    environment: EnvironmentConfig = field(default_factory=EnvironmentConfig)
    server: ServerConfig = field(default_factory=ServerConfig)
    ai: AIConfig = field(default_factory=AIConfig)
    model_router: ModelRouterSettings = field(default_factory=ModelRouterSettings)
    finetune: FineTuneSettings = field(default_factory=FineTuneSettings)
    storage: StorageConfig = field(default_factory=StorageConfig)
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    security: SecurityConfig = field(default_factory=SecurityConfig)
    paths: PathsConfig = field(default_factory=PathsConfig)


config = AppConfig()
