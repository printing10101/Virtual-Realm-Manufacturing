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
class SecurityConfig:
    cors_origins: list[str] = field(default_factory=lambda: [
        origin.strip() for origin in env("CORS_ORIGINS", "*").split(",") if origin.strip()
    ])
    allow_credentials: bool = field(default_factory=lambda: env("CORS_ALLOW_CREDENTIALS", "true").lower() == "true")
    rate_limit_enabled: bool = field(default_factory=lambda: env("RATE_LIMIT_ENABLED", "false").lower() == "true")
    rate_limit_requests: int = field(default_factory=lambda: int(env("RATE_LIMIT_REQUESTS", "100")))
    rate_limit_window: int = field(default_factory=lambda: int(env("RATE_LIMIT_WINDOW", "60")))


@dataclass
class AppConfig:
    app_name: str = field(default_factory=lambda: env("APP_NAME", "灵境制造"))
    app_version: str = field(default_factory=lambda: env("APP_VERSION", "4.0.0"))
    offline_mode: bool = field(default_factory=lambda: env("OFFLINE_MODE", "false").lower() == "true")
    server: ServerConfig = field(default_factory=ServerConfig)
    ai: AIConfig = field(default_factory=AIConfig)
    storage: StorageConfig = field(default_factory=StorageConfig)
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    security: SecurityConfig = field(default_factory=SecurityConfig)


config = AppConfig()
