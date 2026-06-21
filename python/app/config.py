"""灵境制造 全局配置管理。

所有配置项集中管理，支持环境变量覆盖。
遵循12-Factor App原则：配置存储在环境变量中，代码中仅提供合理的开发默认值。

配置层级：
- ServerConfig: HTTP服务器绑定参数
- AIConfig: AI推理/训练模型配置
- SimulationConfig: 数控加工仿真参数
- DatabaseConfig: 数据库路径和连接配置
- StorageConfig: 文件存储路径配置
- SecurityConfig: 安全和认证配置
- PathsConfig: 项目路径约定
- TaskSystemConfig: 异步任务系统配置
- LoggingConfig: 日志轮转和保留策略
- ProcessPlanningConfig: 工艺规划阈值参数
- TokenConfig: LNN认证令牌管理
- AppConfig: 顶层聚合配置

环境变量命名约定: LNN_<SECTION>_<KEY>
示例: LNN_SIM_VOXEL_SIZE 对应 SimulationConfig.voxel_size
"""

from __future__ import annotations

import os
import sys
import uuid
import logging
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

PROJECT_ROOT: str = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)
PYTHON_DIR: str = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

_ROOT_DIR = PROJECT_ROOT


def _env(key: str, default: str = "") -> str:
    return os.environ.get(key, default)


def _path(key: str, default_rel: str) -> str:
    return _env(key, os.path.join(_ROOT_DIR, default_rel))


def _bool_env(key: str, default: bool = False) -> bool:
    return _env(key, "true" if default else "false").lower() == "true"


def _int_env(key: str, default: int) -> int:
    try:
        return int(_env(key, str(default)))
    except ValueError:
        return default


def _float_env(key: str, default: float) -> float:
    try:
        return float(_env(key, str(default)))
    except ValueError:
        return default


# =============================================================================
# Token Configuration
# =============================================================================


@dataclass
class TokenConfig:
    _TOKEN_FILE_NAME = ".lnn_token"
    _TOKEN_META_FILE_NAME = ".lnn_token_meta.json"
    _token_cache: str | None = field(default=None, repr=False, init=False)

    def _resolve_token(self) -> str:
        token = _env("LNN_TOKEN", "")
        if token:
            logger.info("Using token from LNN_TOKEN environment variable")
            return token

        token_file = Path(_env("LNN_TOKEN_FILE", self._TOKEN_FILE_NAME))
        if not token_file.is_absolute():
            token_file = Path(_ROOT_DIR) / token_file

        if token_file.exists():
            try:
                token = token_file.read_text().strip()
                if token:
                    logger.info("Loaded token from %s", token_file)
                    return token
            except Exception as e:
                logger.warning("Failed to read token file %s: %s", token_file, e)

        new_token = str(uuid.uuid4())
        try:
            token_file.parent.mkdir(parents=True, exist_ok=True)
            token_file.write_text(new_token)
            logger.info("Generated and saved new token to %s", token_file)
        except Exception as e:
            logger.warning(
                "Could not persist token to %s: %s. Token is ephemeral for this session.",
                token_file,
                e,
            )

        self._print_setup_guidance(token_file, new_token)
        return new_token

    def _print_setup_guidance(self, token_file: Path, token: str) -> None:
        guidance = f"""
╔══════════════════════════════════════════════════════════════╗
║  LNN认证令牌配置                                            ║
╠══════════════════════════════════════════════════════════════╣
║  系统已生成新的认证令牌。请选择以下方式之一管理令牌：      ║
║                                                              ║
║  方式一（推荐）：设置环境变量                                ║
║    export LNN_TOKEN="你的令牌值"                             ║
║                                                              ║
║  方式二：将令牌写入文件                                      ║
║    文件路径: {str(token_file):<44}║
║                                                              ║
║  当前会话令牌: {token}  ║
║                                                              ║
║  安全须知：                                                  ║
║  - 切勿将令牌提交到版本控制系统                              ║
║  - 定期轮换令牌以保障安全性                                  ║
║  - 生产环境请使用环境变量方式                                ║
╚══════════════════════════════════════════════════════════════╝
"""
        sys.stderr.write(guidance)

    @property
    def token(self) -> str:
        if self._token_cache is None:
            self._token_cache = self._resolve_token()
        return self._token_cache

    def rotate(self) -> str:
        new_token = str(uuid.uuid4())
        self._token_cache = new_token
        token_file = Path(_env("LNN_TOKEN_FILE", self._TOKEN_FILE_NAME))
        if not token_file.is_absolute():
            token_file = Path(_ROOT_DIR) / token_file
        try:
            token_file.parent.mkdir(parents=True, exist_ok=True)
            token_file.write_text(new_token)
            logger.info("Token rotated and saved to %s", token_file)
        except Exception as e:
            logger.warning("Could not persist rotated token: %s", e)
        return new_token


# =============================================================================
# Server Configuration
# =============================================================================


@dataclass
class ServerConfig:
    host: str = field(default_factory=lambda: _env("SERVER_HOST", "127.0.0.1"))
    port: int = field(default_factory=lambda: int(_env("SERVER_PORT", "8765")))
    debug: bool = field(default_factory=lambda: _bool_env("DEBUG", False))


# =============================================================================
# AI Configuration
# =============================================================================


@dataclass
class AIConfig:
    mode: str = field(default_factory=lambda: _env("AI_MODE", "local"))
    ollama_base_url: str = field(
        default_factory=lambda: _env("OLLAMA_BASE_URL", "http://localhost:11434")
    )
    ollama_model: str = field(
        default_factory=lambda: _env("OLLAMA_MODEL", "qwen2.5-coder:7b")
    )
    cloud_api_key: str = field(default_factory=lambda: _env("CLOUD_API_KEY", ""))
    cloud_base_url: str = field(
        default_factory=lambda: _env("CLOUD_BASE_URL", "https://api.openai.com/v1")
    )
    cloud_model: str = field(
        default_factory=lambda: _env("CLOUD_MODEL", "gpt-3.5-turbo")
    )
    timeout: int = field(default_factory=lambda: _int_env("AI_TIMEOUT", 60))
    max_retries: int = field(default_factory=lambda: _int_env("AI_MAX_RETRIES", 3))


# =============================================================================
# Model Router Configuration
# =============================================================================


@dataclass
class ModelRouterSettings:
    local_model: str = field(default_factory=lambda: _env("LOCAL_MODEL", "qwen2.5:7b"))
    cloud_provider: str = field(
        default_factory=lambda: _env("CLOUD_PROVIDER", "openai")
    )
    cloud_model: str = field(
        default_factory=lambda: _env("CLOUD_MODEL_ROUTER", "gpt-4o")
    )
    fallback_threshold: int = field(
        default_factory=lambda: _int_env("FALLBACK_THRESHOLD", 3)
    )
    local_timeout: int = field(
        default_factory=lambda: _int_env("LOCAL_TIMEOUT", 30)
    )


# =============================================================================
# Fine-Tune Configuration
# =============================================================================


@dataclass
class FineTuneSettings:
    finetune_auto_trigger: bool = field(
        default_factory=lambda: _bool_env("FINETUNE_AUTO_TRIGGER", False)
    )
    finetune_min_samples: int = field(
        default_factory=lambda: _int_env("FINETUNE_MIN_SAMPLES", 50)
    )
    finetune_interval_days: int = field(
        default_factory=lambda: _int_env("FINETUNE_INTERVAL_DAYS", 7)
    )
    finetune_output_dir: str = field(
        default_factory=lambda: _path(
            "FINETUNE_OUTPUT_DIR", os.path.join("output", "models", "finetuned")
        )
    )


# =============================================================================
# Simulation Configuration
# =============================================================================


@dataclass
class SimulationConfig:
    voxel_size: float = field(
        default_factory=lambda: _float_env("LNN_SIM_VOXEL_SIZE", 1.0)
    )
    voxel_size_min: float = 0.1
    voxel_size_max: float = 10.0
    max_store_size: int = field(
        default_factory=lambda: _int_env("LNN_SIM_MAX_STORE", 500)
    )
    max_store_age_seconds: int = field(
        default_factory=lambda: _int_env("LNN_SIM_STORE_AGE", 86400)
    )
    collision_margin_mm: float = field(
        default_factory=lambda: _float_env("LNN_SIM_COLLISION_MARGIN", 0.5)
    )
    batch_processing_size: int = field(
        default_factory=lambda: _int_env("LNN_SIM_BATCH_SIZE", 2000)
    )
    default_safe_z_height_mm: float = field(
        default_factory=lambda: _float_env("LNN_SIM_SAFE_Z", 10.0)
    )
    idle_timeout_seconds: int = field(
        default_factory=lambda: _int_env("LNN_IDLE_TIMEOUT", 1800)
    )


# =============================================================================
# Storage Configuration
# =============================================================================


@dataclass
class StorageConfig:
    output_dir: str = field(default_factory=lambda: _path("OUTPUT_DIR", "output"))
    temp_dir: str = field(default_factory=lambda: _path("TEMP_DIR", "temp"))


# =============================================================================
# Database Configuration
# =============================================================================


@dataclass
class DatabaseConfig:
    cad_db_path: str = field(
        default_factory=lambda: _path("CAD_DB_PATH", "cad_tasks.db")
    )
    model_library_path: str = field(
        default_factory=lambda: _path("MODEL_LIBRARY_PATH", "model_library.db")
    )
    db_url: str = field(
        default_factory=lambda: _env(
            "DATABASE_URL",
            f"sqlite+aiosqlite:///{_ROOT_DIR}/data/app.db",
        )
    )


# =============================================================================
# Security Configuration
# =============================================================================


@dataclass
class SecurityConfig:
    cors_origins: list[str] = field(
        default_factory=lambda: [
            origin.strip()
            for origin in _env("CORS_ORIGINS", "*").split(",")
            if origin.strip()
        ]
    )
    allow_credentials: bool = field(
        default_factory=lambda: _bool_env("CORS_ALLOW_CREDENTIALS", True)
    )
    cors_origin_regex: str | None = field(
        default_factory=lambda: _env("CORS_ORIGIN_REGEX", "") or None
    )
    rate_limit_enabled: bool = field(
        default_factory=lambda: _bool_env("RATE_LIMIT_ENABLED", True)
    )
    rate_limit_requests: int = field(
        default_factory=lambda: _int_env("RATE_LIMIT_REQUESTS", 100)
    )
    rate_limit_window: int = field(
        default_factory=lambda: _int_env("RATE_LIMIT_WINDOW", 60)
    )
    auth_enabled: bool = field(
        default_factory=lambda: _bool_env("LNN_AUTH_ENABLED", True)
    )
    # 修复：默认开启权限检查，避免在配置缺失时出现安全盲区
    permission_enforced: bool = field(
        default_factory=lambda: _bool_env("LNN_PERMISSION_ENFORCED", True)
    )
    agent_auth_enabled: bool = field(
        default_factory=lambda: _bool_env("AGENT_AUTH_ENABLED", True)
    )

    def __post_init__(self) -> None:
        """启动时安全审计：检测到权限检查被显式关闭时输出 WARNING。"""
        # 测试环境（conftest 中设置 ENVIRONMENT=testing）下静默，避免日志噪音
        if _env("ENVIRONMENT", "development").lower() == "testing":
            return
        if not self.permission_enforced:
            logger.warning(
                "权限检查功能已被禁用，这可能导致安全风险 "
                "(LNN_PERMISSION_ENFORCED=%s)",
                os.environ.get("LNN_PERMISSION_ENFORCED", "false"),
            )


# =============================================================================
# Environment Configuration
# =============================================================================


@dataclass
class EnvironmentConfig:
    environment: str = field(
        default_factory=lambda: _env("ENVIRONMENT", "development").lower()
    )

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def is_development(self) -> bool:
        return self.environment in ("development", "dev")


# =============================================================================
# Paths Configuration
# =============================================================================


@dataclass
class PathsConfig:
    backup_dir: str = field(default_factory=lambda: _env("BACKUP_DIR", "./backups"))
    db_path: str = field(default_factory=lambda: _env("DB_PATH", "./data/app.db"))
    vector_db_path: str = field(
        default_factory=lambda: _env("VECTOR_DB_PATH", "./data/chroma_db")
    )
    config_path: str = field(
        default_factory=lambda: _env("CONFIG_PATH", "./config.json")
    )
    gstack_dir: str = field(
        default_factory=lambda: _env("LNN_GSTACK_DIR", ".lingjing/.gstack")
    )
    skills_dir: str = field(
        default_factory=lambda: _env(
            "LNN_SKILLS_DIR",
            str(
                Path(__file__).resolve().parent.parent.parent
                / ".trae"
                / "skills"
            ),
        )
    )


# =============================================================================
# Task System Configuration
# =============================================================================


@dataclass
class TaskSystemConfig:
    max_concurrent: int = field(
        default_factory=lambda: _int_env("TASK_MAX_CONCURRENT", 3)
    )
    recovery_strategy: str = field(
        default_factory=lambda: _env("TASK_RECOVERY_STRATEGY", "mark_failed")
    )
    max_task_history: int = field(
        default_factory=lambda: _int_env("TASK_MAX_HISTORY", 10000)
    )


# =============================================================================
# Logging Configuration
# =============================================================================


@dataclass
class LoggingConfig:
    log_level: str = field(
        default_factory=lambda: _env("LNN_LOG_LEVEL", "INFO")
    )
    log_dir: str = field(
        default_factory=lambda: _env(
            "LNN_LOG_DIR",
            str(Path.home() / ".lingjing" / "logs"),
        )
    )
    max_bytes: int = field(
        default_factory=lambda: _int_env("LNN_LOG_MAX_BYTES", 52428800)
    )
    backup_count: int = field(
        default_factory=lambda: _int_env("LNN_LOG_BACKUP_COUNT", 5)
    )
    retention_days: int = field(
        default_factory=lambda: _int_env("LNN_LOG_RETENTION_DAYS", 30)
    )


# =============================================================================
# Process Planning Configuration
# =============================================================================


@dataclass
class ProcessPlanningConfig:
    surface_roughness_ra_default: float = field(
        default_factory=lambda: _float_env("LNN_PP_RA_DEFAULT", 3.2)
    )
    min_plane_area_mm2: float = field(
        default_factory=lambda: _float_env("LNN_PP_MIN_PLANE_AREA", 1.0)
    )
    min_cavity_dimension_mm: float = field(
        default_factory=lambda: _float_env("LNN_PP_MIN_CAVITY_DIM", 0.5)
    )
    min_boss_diameter_mm: float = field(
        default_factory=lambda: _float_env("LNN_PP_MIN_BOSS_DIAM", 1.0)
    )
    min_hole_diameter_mm: float = field(
        default_factory=lambda: _float_env("LNN_PP_MIN_HOLE_DIAM", 0.5)
    )
    standard_drill_point_angle_deg: float = field(
        default_factory=lambda: _float_env("LNN_PP_DRILL_ANGLE", 118.0)
    )
    gcode_default_program_number: int = field(
        default_factory=lambda: _int_env("LNN_PP_GCODE_PROG_NUM", 1000)
    )


# =============================================================================
# Top-Level Application Configuration
# =============================================================================


@dataclass
class AppConfig:
    app_name: str = field(default_factory=lambda: _env("APP_NAME", "灵境制造"))
    app_version: str = field(default_factory=lambda: _env("APP_VERSION", "2.2.0"))
    offline_mode: bool = field(
        default_factory=lambda: _bool_env("OFFLINE_MODE", False)
    )
    environment: EnvironmentConfig = field(default_factory=EnvironmentConfig)
    server: ServerConfig = field(default_factory=ServerConfig)
    ai: AIConfig = field(default_factory=AIConfig)
    model_router: ModelRouterSettings = field(default_factory=ModelRouterSettings)
    finetune: FineTuneSettings = field(default_factory=FineTuneSettings)
    simulation: SimulationConfig = field(default_factory=SimulationConfig)
    storage: StorageConfig = field(default_factory=StorageConfig)
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    security: SecurityConfig = field(default_factory=SecurityConfig)
    paths: PathsConfig = field(default_factory=PathsConfig)
    token: TokenConfig = field(default_factory=TokenConfig)
    tasks: TaskSystemConfig = field(default_factory=TaskSystemConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    process_planning: ProcessPlanningConfig = field(
        default_factory=ProcessPlanningConfig
    )


config = AppConfig()
