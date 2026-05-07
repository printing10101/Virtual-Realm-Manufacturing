import os
from dataclasses import dataclass, field


def env(key: str, default: str = "") -> str:
    return os.environ.get(key, default)


@dataclass
class ServerConfig:
    host: str = field(default_factory=lambda: env("SERVER_HOST", "127.0.0.1"))
    port: int = field(default_factory=lambda: int(env("SERVER_PORT", "8765")))
    debug: bool = field(default_factory=lambda: env("DEBUG", "false").lower() == "true")


@dataclass
class AIConfig:
    mode: str = field(default_factory=lambda: env("AI_MODE", "local"))
    ollama_base_url: str = field(default_factory=lambda: env("OLLAMA_BASE_URL", "http://localhost:11434"))
    ollama_model: str = field(default_factory=lambda: env("OLLAMA_MODEL", "qwen2.5-coder:7b"))
    cloud_api_key: str = field(default_factory=lambda: env("CLOUD_API_KEY", ""))
    cloud_base_url: str = field(default_factory=lambda: env("CLOUD_BASE_URL", "https://api.openai.com/v1"))
    cloud_model: str = field(default_factory=lambda: env("CLOUD_MODEL", "gpt-3.5-turbo"))
    timeout: int = field(default_factory=lambda: int(env("AI_TIMEOUT", "60")))
    max_retries: int = field(default_factory=lambda: int(env("AI_MAX_RETRIES", "3")))


@dataclass
class StorageConfig:
    output_dir: str = field(default_factory=lambda: env("OUTPUT_DIR", os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "output")))
    temp_dir: str = field(default_factory=lambda: env("TEMP_DIR", os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "temp")))


@dataclass
class DatabaseConfig:
    cad_db_path: str = field(default_factory=lambda: env("CAD_DB_PATH", os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "cad_tasks.db")))
    model_library_path: str = field(default_factory=lambda: env("MODEL_LIBRARY_PATH", os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "model_library.db")))


@dataclass
class ModelRouterSettings:
    local_model: str = field(default_factory=lambda: env("LOCAL_MODEL", "qwen2.5:7b"))
    cloud_provider: str = field(default_factory=lambda: env("CLOUD_PROVIDER", "openai"))
    cloud_model: str = field(default_factory=lambda: env("CLOUD_MODEL_ROUTER", "gpt-4o"))
    fallback_threshold: int = field(default_factory=lambda: int(env("FALLBACK_THRESHOLD", "3")))
    local_timeout: int = field(default_factory=lambda: int(env("LOCAL_TIMEOUT", "30")))


@dataclass
class FineTuneSettings:
    finetune_auto_trigger: bool = field(default_factory=lambda: env("FINETUNE_AUTO_TRIGGER", "false").lower() == "true")
    finetune_min_samples: int = field(default_factory=lambda: int(env("FINETUNE_MIN_SAMPLES", "50")))
    finetune_interval_days: int = field(default_factory=lambda: int(env("FINETUNE_INTERVAL_DAYS", "7")))
    finetune_output_dir: str = field(default_factory=lambda: env("FINETUNE_OUTPUT_DIR", os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "output", "models", "finetuned")))


@dataclass
class SecurityConfig:
    cors_origins: list[str] = field(default_factory=lambda: [
        origin.strip() for origin in env("CORS_ORIGINS", "*").split(",") if origin.strip()
    ])
    allow_credentials: bool = field(default_factory=lambda: env("CORS_ALLOW_CREDENTIALS", "true").lower() == "true")
    rate_limit_enabled: bool = field(default_factory=lambda: env("RATE_LIMIT_ENABLED", "false").lower() == "true")
    rate_limit_requests: int = field(default_factory=lambda: int(env("RATE_LIMIT_REQUESTS", "100")))
    rate_limit_window: int = field(default_factory=lambda: int(env("RATE_LIMIT_WINDOW", "60")))


@dataclass
class EnvironmentConfig:
    environment: str = field(default_factory=lambda: env("ENVIRONMENT", "development").lower())


@dataclass
class PathsConfig:
    backup_dir: str = field(default_factory=lambda: env("BACKUP_DIR", "./backups"))
    db_path: str = field(default_factory=lambda: env("DB_PATH", "./data/app.db"))
    vector_db_path: str = field(default_factory=lambda: env("VECTOR_DB_PATH", "./data/chroma_db"))
    config_path: str = field(default_factory=lambda: env("CONFIG_PATH", "./config.json"))

    def get(self, key: str, default: str = "") -> str:
        return getattr(self, key, default)


@dataclass
class AppConfig:
    app_name: str = field(default_factory=lambda: env("APP_NAME", "灵境制造"))
    app_version: str = field(default_factory=lambda: env("APP_VERSION", "1.2.0"))
    offline_mode: bool = field(default_factory=lambda: env("OFFLINE_MODE", "false").lower() == "true")
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
