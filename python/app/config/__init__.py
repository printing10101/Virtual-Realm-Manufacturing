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
- SharpConfig: SHARP 三元组验证智能体配置
- ImageTo3DConfig: 拍照重建模块配置（COLMAP+OpenMVS / Hunyuan3D）
- FeatureExtractionConfig: 几何特征提取模块配置（RANSAC 平面/圆柱/孔检测）
- ParametricGeometryConfig: 参数化几何输出模块配置（特征→B-rep→STEP）
- CuttingParametersConfig: 切削参数推荐模块配置（材料→切削参数→ChatterParams）
- ChatterPredictionConfig: 颤振预测接入模块配置（ChatterParams→双路径预测→ChatterReport）
- GCodeGenerationConfig: G 代码生成模块配置（ChatterReport→OperationPlan→GeneratorAdapter→审核→G 代码导出）
- CamValidationConfig: CAM 校验模块配置（G 代码→InternalValidator→CamAdapter→审核→CAM 校验报告导出）
- DreamingConfig: Dreaming 离线反思模块配置（ADR-021，Memory+Dreaming+Outcomes 闭环）
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

# 注意：本模块原为 app/config.py 单文件，现已重构为 app/config/ 包。
# __file__ 路径由 app/config.py 变为 app/config/__init__.py，需多向上一级目录。
PROJECT_ROOT: str = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)
PYTHON_DIR: str = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)

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
    except ValueError as e:
        logger.debug("环境变量 %s 转换整数失败，使用默认值: %s", key, e, exc_info=True)
        return default


def _float_env(key: str, default: float) -> float:
    try:
        return float(_env(key, str(default)))
    except ValueError as e:
        logger.debug("环境变量 %s 转换浮点数失败，使用默认值: %s", key, e, exc_info=True)
        return default


# =============================================================================
# Token Configuration
# =============================================================================


@dataclass
class MESConfig:
    """MES/ERP 系统集成配置。"""
    base_url: str = field(default_factory=lambda: _env("MES_BASE_URL", ""))
    api_key: str = field(default_factory=lambda: _env("MES_API_KEY", ""))
    timeout: float = field(default_factory=lambda: _float_env("MES_TIMEOUT", 30.0))
    enabled: bool = field(default_factory=lambda: _bool_env("MES_ENABLED", False))


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
            except (OSError, IOError, PermissionError) as e:
                logger.warning("Failed to read token file", exc_info=True)

        new_token = str(uuid.uuid4())
        try:
            token_file.parent.mkdir(parents=True, exist_ok=True)
            token_file.write_text(new_token)
            logger.info("Generated and saved new token to %s", token_file)
        except (OSError, IOError, PermissionError) as e:
            logger.warning(
                "Could not persist token. Token is ephemeral for this session.",
                exc_info=True,
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
        except (OSError, IOError, PermissionError) as e:
            logger.warning("Could not persist rotated token", exc_info=True)
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

    def __post_init__(self) -> None:
        """P2-14 修复：启动时校验云端模式关键配置。

        当 ``AI_MODE=cloud`` 但 ``CLOUD_API_KEY`` 为空时，云端调用必然
        鉴权失败；此时仅记录 WARNING 不阻断启动，保持与现有容错策略一致
        （本地 Ollama 可能仍可用作回退）。测试环境下静默。
        """
        if _env("ENVIRONMENT", "development").lower() == "testing":
            return
        if self.mode == "cloud" and not self.cloud_api_key.strip():
            logger.warning(
                "AI_MODE=cloud 但 CLOUD_API_KEY 为空，云端 API 调用将失败。"
                "请设置 CLOUD_API_KEY 环境变量，或切换 AI_MODE=local 使用本地 Ollama。"
            )


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
# Hardware Tier Configuration
# =============================================================================
# [U-P0-2] 防复发：硬件档位声明 + 轻量模式
# 设计依据：用户三方评估指出"本地化承诺 vs 硬件现实"矛盾——
#   项目承诺全本地 LLM，但用户机器可能无 GPU/内存不足，导致 Ollama 启动失败。
#   通过显式档位声明 + 轻量模式开关，让用户根据硬件条件选择合适的能力子集。
# 档位定义（与 docs/user-guide/安装指南.md 硬件配置表对齐）：
#   - minimal : 4 核 CPU / 8 GB RAM / 无 GPU（仅规则引擎 + 云端 API）
#   - standard: 8 核 CPU / 16 GB RAM / 可选 GPU（默认，支持本地小模型）
#   - high    : 8 核+ CPU / 32 GB RAM / NVIDIA GPU ≥ 6 GB（本地 7B-14B 模型）
#   - ultra   : 工作站级（本地 14B+ 模型 + GPU 训练）
# 轻量模式（lightweight_mode）：
#   - 跳过 Ollama 启动探测（即使安装了 Ollama 也不加载）
#   - 禁用本地模型路由，强制使用云端 API 或规则引擎
#   - 限制 AI 并发数为 1，降低内存占用
#   - 适用于老旧硬件 / 临时演示 / 仅需 CAM 核心功能的场景


@dataclass
class HardwareTierConfig:
    """硬件档位配置。

    通过环境变量 ``LNN_HARDWARE_TIER`` / ``LNN_LIGHTWEIGHT_MODE`` /
    ``LNN_SKIP_OLLAMA`` / ``LNN_MAX_CONCURRENT_AI`` 控制。
    前端 ``useSettingsStore`` 同步持久化用户偏好（localStorage），
    后端通过环境变量在启动时固化（运行时不可变，需重启生效）。
    """

    tier: str = field(
        default_factory=lambda: _env("LNN_HARDWARE_TIER", "standard")
    )
    lightweight_mode: bool = field(
        default_factory=lambda: _bool_env("LNN_LIGHTWEIGHT_MODE", False)
    )
    skip_ollama: bool = field(
        default_factory=lambda: _bool_env("LNN_SKIP_OLLAMA", False)
    )
    max_concurrent_ai: int = field(
        default_factory=lambda: _int_env("LNN_MAX_CONCURRENT_AI", 2)
    )

    def __post_init__(self) -> None:
        """校验档位值合法性，非法值回退到 standard 并记录警告。"""
        valid_tiers = {"minimal", "standard", "high", "ultra"}
        if self.tier not in valid_tiers:
            import warnings

            warnings.warn(
                f"Invalid LNN_HARDWARE_TIER='{self.tier}', "
                f"expected one of {sorted(valid_tiers)}. "
                f"Falling back to 'standard'.",
                stacklevel=2,
            )
            self.tier = "standard"

        # 轻量模式自动派生：minimal 档位隐式启用轻量模式
        if self.tier == "minimal":
            self.lightweight_mode = True
            self.skip_ollama = True

        # 轻量模式下限制 AI 并发数为 1
        if self.lightweight_mode and self.max_concurrent_ai > 1:
            self.max_concurrent_ai = 1


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
            # 默认路径与原 main.py 中 Path(__file__).parent.parent / "data" / "app.db" 一致
            # 使用 PYTHON_DIR 以保持向后兼容（现有 DB 位于 python/data/app.db）
            f"sqlite+aiosqlite:///{PYTHON_DIR}/data/app.db",
        )
    )


# =============================================================================
# Security Configuration
# =============================================================================


def _resolve_cors_origins() -> list[str]:
    """统一解析 CORS 允许的来源列表。

    修复 [B30]：原本 SecurityConfig.cors_origins 仅读取 CORS_ORIGINS 环境变量，
    而 main.py 实际使用 cors_config.py 中的 cors_settings（读取 ALLOWED_ORIGINS）。
    这导致两个系统读取不同的环境变量，配置不一致。

    本函数统一读取顺序为：
    1. ALLOWED_ORIGINS（与 cors_config.py 一致，逗号分隔，优先级最高）
    2. CORS_ORIGINS（向后兼容字段，逗号分隔）

    这样 config.security.cors_origins 与 cors_settings.get_origins()
    将基于相同的环境变量来源，保持单一配置源。
    """
    # 优先级 1：ALLOWED_ORIGINS（与 cors_config.py 保持一致）
    allowed = _env("ALLOWED_ORIGINS", "")
    if allowed:
        return [o.strip() for o in allowed.split(",") if o.strip()]
    # 优先级 2：CORS_ORIGINS（向后兼容字段）
    legacy = _env("CORS_ORIGINS", "")
    if legacy:
        return [o.strip() for o in legacy.split(",") if o.strip()]
    return []


@dataclass
class SecurityConfig:
    # 安全修复：CORS 默认改为空列表，强制部署时显式配置允许的来源。
    # 通配符 "*" 配合 allow_credentials=True 会导致 CSRF 型凭证泄露。
    # 修复 [B30]：与 cors_config.py 统一读取 ALLOWED_ORIGINS（优先）和 CORS_ORIGINS（回退），
    # 保证 config.security.cors_origins 与 cors_settings.get_origins() 数据源一致。
    cors_origins: list[str] = field(default_factory=_resolve_cors_origins)
    allow_credentials: bool = field(
        default_factory=lambda: _bool_env("CORS_ALLOW_CREDENTIALS", True)
    )
    cors_origin_regex: str | None = field(
        default_factory=lambda: _env("CORS_ORIGIN_REGEX", "") or None
    )
    # 修复 [B30]：LINGJING_ENV 用于环境感知的 CORS 默认配置，
    # 与 cors_config.py 中的 _resolve_environment() 保持一致。
    lingjing_env: str = field(
        default_factory=lambda: _env("LINGJING_ENV", "production").lower()
        if _env("LINGJING_ENV", "").lower() in ("development", "production")
        else "production"
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
    # JWT 认证开关，统一通过 config 管理，避免在 main.py 中直接读取环境变量
    jwt_auth_enabled: bool = field(
        default_factory=lambda: _bool_env("LNN_JWT_AUTH_ENABLED", True)
    )
    # 修复 [B32]：JWT 密钥统一在 config 中声明，便于配置审计和文档化。
    # 注意：实际的密钥验证逻辑仍由 app/auth/security.py 的
    # _validate_and_get_secret() 负责（包含长度、随机性等安全检查），
    # 此字段仅作为配置项暴露，避免在多处直接读取环境变量。
    jwt_secret: str = field(default_factory=lambda: _env("LNN_JWT_SECRET", ""))
    # 修复 [B39]：注册邀请码统一在 config 中声明，避免在 auth.py 中
    # 直接读取 os.environ.get("LNN_REGISTRATION_CODE") 绕过配置审计。
    # 当该字段为空字符串时，注册功能视为已关闭（返回 403）。
    registration_code: str = field(
        default_factory=lambda: _env("LNN_REGISTRATION_CODE", "")
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
                # 包转换后 __file__ 路径多一级，需多一层 .parent
                Path(__file__).resolve().parent.parent.parent.parent
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
# SHARP Configuration (Schema-Hybrid Agent for Reliable Prediction)
# =============================================================================


@dataclass
class SharpConfig:
    """SHARP 三元组验证智能体配置。

    对应论文 4 大组件的运行时开关与超参数，所有项均可通过环境变量覆盖：
    - ``LNN_SHARP_MAX_REACT_STEPS``：ReAct 循环最大步数（默认 8）
    - ``LNN_SHARP_CONFIDENCE_THRESHOLD``：终止置信度阈值（默认 0.85）
    - ``LNN_SHARP_EVIDENCE_CONVERGENCE_WINDOW``：证据收敛窗口（默认 2）
    - ``LNN_SHARP_MEMORY_TOP_K``：Memory-Augmented 检索 Top-K（默认 3）
    - ``LNN_SHARP_TOOL_EVIDENCE_TOP_K``：单工具证据返回 Top-K（默认 5）
    - ``LNN_SHARP_ENABLE_SCHEMA_PLANNER``：开关 Schema-Aware 规划器
    - ``LNN_SHARP_ENABLE_MEMORY_AUGMENT``：开关 Memory-Augmented 机制
    - ``LNN_SHARP_ENABLE_HYBRID_TOOLSET``：开关 Hybrid Knowledge Toolset
    - ``LNN_SHARP_ENABLE_REACT_LOOP``：开关 ReAct 循环（关则降级为单次 LLM 推理）
    - ``LNN_SHARP_ABLATION_MODE``：消融模式（none/no_schema/no_memory/no_react/no_toolset）

    消融模式优先级高于单独开关：设置 ``LNN_SHARP_ABLATION_MODE=no_memory``
    会强制 ``enable_memory_augment=False``，由 SharpService 在构建 pipeline 时处理。
    """

    max_react_steps: int = field(
        default_factory=lambda: _int_env("LNN_SHARP_MAX_REACT_STEPS", 8)
    )
    confidence_threshold: float = field(
        default_factory=lambda: _float_env("LNN_SHARP_CONFIDENCE_THRESHOLD", 0.85)
    )
    evidence_convergence_window: int = field(
        default_factory=lambda: _int_env(
            "LNN_SHARP_EVIDENCE_CONVERGENCE_WINDOW", 2
        )
    )
    memory_top_k: int = field(
        default_factory=lambda: _int_env("LNN_SHARP_MEMORY_TOP_K", 3)
    )
    tool_evidence_top_k: int = field(
        default_factory=lambda: _int_env("LNN_SHARP_TOOL_EVIDENCE_TOP_K", 5)
    )
    enable_schema_planner: bool = field(
        default_factory=lambda: _bool_env("LNN_SHARP_ENABLE_SCHEMA_PLANNER", True)
    )
    enable_memory_augment: bool = field(
        default_factory=lambda: _bool_env("LNN_SHARP_ENABLE_MEMORY_AUGMENT", True)
    )
    enable_hybrid_toolset: bool = field(
        default_factory=lambda: _bool_env("LNN_SHARP_ENABLE_HYBRID_TOOLSET", True)
    )
    enable_react_loop: bool = field(
        default_factory=lambda: _bool_env("LNN_SHARP_ENABLE_REACT_LOOP", True)
    )
    ablation_mode: str = field(
        default_factory=lambda: _env("LNN_SHARP_ABLATION_MODE", "")
    )

    @property
    def resolved_ablation_mode(self) -> str | None:
        """规范化消融模式：空字符串或 'none' 视为 None（完整 SHARP）。"""
        v = (self.ablation_mode or "").strip().lower()
        if not v or v == "none":
            return None
        return v


# =============================================================================
# Image-to-3D Reconstruction Configuration
# =============================================================================
# 拍照重建模块配置（ADR-006）
#
# 设计目标：用户用普通手机拍摄非标零件多张照片 → 重建粗几何 → 进入 CAM 软件校验
# 工程现实：手机多视角摄影测量精度 0.1-1mm，配合面公差 0.01mm 物理上够不到。
#          因此本模块定位为"工艺感知入口"而非"自动生产建模"，
#          输出的粗 mesh 必须经人工确认 + CAM 软件二次校验才能上机床。
#
# 支持三条 pipeline：
#   - colmap_openmvs：传统多视角摄影测量（推荐，无需 GPU，精度可控）
#   - hunyuan3d     ：单图/少图神经生成（需 GPU，作为备选）
#   - part_prior    ：零件专属先验补全（ADR-020 思路 2，COLMAP 稀疏点云 + VAE 先验补全）
#
# 环境变量命名约定：LNN_I2T3D_*


@dataclass
class PartPriorConfig:
    """零件专属先验模型配置（ADR-020 思路 2）。

    作为拍照重建的第三条路径 ``part_prior``，与 COLMAP/Hunyuan3D 并列。
    用公开 CAD 数据集预训练的 VAE 对 COLMAP 稀疏点云做先验补全，输出稠密 mesh。

    工程边界：
    - 不替代 COLMAP+OpenMVS 主 pipeline（精度仍受手机照片物理极限限制）
    - 不直接输出 STEP（mesh→参数化 CAD 仍走 ADR-008 human-in-the-loop）
    - 精度 0.1-1mm，配合面 0.01mm 不可达

    环境变量命名约定：LNN_I2T3D_PART_PRIOR_*
    """

    # 预训练 VAE 权重路径（.pt/.pth）。空字符串表示未配置，part_prior 路径不可用
    pretrained_model_path: str = field(
        default_factory=lambda: _env("LNN_I2T3D_PART_PRIOR_MODEL_PATH", "")
    )
    # 体素网格维度（必须与预训练 VAE 一致，默认 64³）
    voxel_dim: int = field(
        default_factory=lambda: _int_env("LNN_I2T3D_PART_PRIOR_VOXEL_DIM", 64)
    )
    # latent 维度（必须与预训练 VAE 一致）
    latent_dim: int = field(
        default_factory=lambda: _int_env("LNN_I2T3D_PART_PRIOR_LATENT_DIM", 256)
    )
    # 基础通道数（必须与预训练 VAE 一致）
    base_channels: int = field(
        default_factory=lambda: _int_env("LNN_I2T3D_PART_PRIOR_BASE_CHANNELS", 32)
    )
    # 推理随机种子（D-2 学术诚信硬约束：固定种子保证可复现）
    inference_seed: int = field(
        default_factory=lambda: _int_env("LNN_I2T3D_PART_PRIOR_SEED", 42)
    )
    # marching cubes 阈值（体素占据概率，0-1）
    marching_cubes_threshold: float = field(
        default_factory=lambda: _float_env("LNN_I2T3D_PART_PRIOR_MC_THRESHOLD", 0.5)
    )

    def __post_init__(self) -> None:
        """校验 part_prior 配置合法性。"""
        if self.voxel_dim <= 0:
            logger.warning(
                "LNN_I2T3D_PART_PRIOR_VOXEL_DIM=%s invalid, must be > 0. "
                "Setting to 64.",
                self.voxel_dim,
            )
            self.voxel_dim = 64
        if self.latent_dim <= 0:
            logger.warning(
                "LNN_I2T3D_PART_PRIOR_LATENT_DIM=%s invalid, must be > 0. "
                "Setting to 256.",
                self.latent_dim,
            )
            self.latent_dim = 256
        if self.base_channels <= 0:
            logger.warning(
                "LNN_I2T3D_PART_PRIOR_BASE_CHANNELS=%s invalid, must be > 0. "
                "Setting to 32.",
                self.base_channels,
            )
            self.base_channels = 32
        if not 0.0 < self.marching_cubes_threshold < 1.0:
            logger.warning(
                "LNN_I2T3D_PART_PRIOR_MC_THRESHOLD=%s invalid, must be in (0, 1). "
                "Setting to 0.5.",
                self.marching_cubes_threshold,
            )
            self.marching_cubes_threshold = 0.5


@dataclass
class ImageTo3DConfig:
    """拍照重建模块配置。

    所有配置项支持环境变量覆盖，遵循 12-Factor App 原则。
    """

    # 总开关：桌面轻量档位下可关闭，避免冷启动延迟
    enabled: bool = field(
        default_factory=lambda: _bool_env("LNN_I2T3D_ENABLED", True)
    )
    # 默认 pipeline：colmap_openmvs（无需 GPU）或 hunyuan3d（需 GPU）
    pipeline: str = field(
        default_factory=lambda: _env("LNN_I2T3D_PIPELINE", "colmap_openmvs")
    )

    # COLMAP 二进制路径：用户需单独安装 COLMAP（https://colmap.github.io/install.html）
    # Windows 默认安装路径示例：C:/Program Files/COLMAP/colmap.exe
    # Linux/macOS：通常在 PATH 中可直接调用 colmap
    colmap_bin: str = field(
        default_factory=lambda: _env("LNN_I2T3D_COLMAP_BIN", "colmap")
    )
    # OpenMVS 二进制路径：用户需单独安装 OpenMVS（https://github.com/cdcseacave/openMVS）
    # 默认 DensifyMesh 是 OpenMVS 的网格稠密化命令
    openmvs_bin: str = field(
        default_factory=lambda: _env("LNN_I2T3D_OPENMVS_BIN", "DensifyMesh")
    )

    # 输出目录：存放每次重建任务的中间产物和最终 GLB/PLY
    output_dir: str = field(
        default_factory=lambda: _path(
            "LNN_I2T3D_OUTPUT_DIR", os.path.join("output", "image_to_3d")
        )
    )

    # 照片数量约束：少则重建失败，多则 SfM 慢
    min_photos: int = field(
        default_factory=lambda: _int_env("LNN_I2T3D_MIN_PHOTOS", 8)
    )
    max_photos: int = field(
        default_factory=lambda: _int_env("LNN_I2T3D_MAX_PHOTOS", 200)
    )

    # 标定块实际边长（mm）：用户拍照时在场景中放置已知尺寸的标定块（如 30mm 量块），
    # 重建后据此做尺度归一化。无标定块时输出无单位 mesh（仅相对几何，不可生产用）
    calibration_block_mm: float = field(
        default_factory=lambda: _float_env("LNN_I2T3D_CALIBRATION_BLOCK_MM", 30.0)
    )

    # 精度档位：影响 COLMAP SfM 的特征点数量阈值与 OpenMVS 网格密度
    #   coarse  : 快，0.5-2mm，适合工艺理解/可视化
    #   standard: 默认，0.1-1mm，适合非配合面尺寸复核
    #   high    : 慢，0.1-0.5mm，小零件细节，仍达不到配合面公差
    precision_tier: str = field(
        default_factory=lambda: _env("LNN_I2T3D_PRECISION_TIER", "standard")
    )

    # 并发约束：重建任务重 IO+CPU，桌面模式默认串行
    max_concurrent: int = field(
        default_factory=lambda: _int_env("LNN_I2T3D_MAX_CONCURRENT", 1)
    )

    # 任务超时（秒）：COLMAP 在 200 张照片 + high 档位下单次约 30-60 分钟
    task_timeout_seconds: int = field(
        default_factory=lambda: _int_env("LNN_I2T3D_TASK_TIMEOUT", 3600)
    )

    # Hunyuan3D-2 备选 pipeline 配置（需 GPU）
    hunyuan3d_model_dir: str = field(
        default_factory=lambda: _env("LNN_I2T3D_HUNYUAN3D_MODEL_DIR", "")
    )
    hunyuan3d_device: str = field(
        default_factory=lambda: _env("LNN_I2T3D_HUNYUAN3D_DEVICE", "cuda")
    )
    hunyuan3d_dtype: str = field(
        default_factory=lambda: _env("LNN_I2T3D_HUNYUAN3D_DTYPE", "float16")
    )

    # Part Prior 备选 pipeline 配置（ADR-020 思路 2，需预训练 VAE 权重）
    part_prior: PartPriorConfig = field(default_factory=PartPriorConfig)

    # 任务历史保留时长（小时）：超过自动清理
    task_retention_hours: int = field(
        default_factory=lambda: _int_env("LNN_I2T3D_TASK_RETENTION_HOURS", 72)
    )

    def __post_init__(self) -> None:
        """启动时校验配置合法性。"""
        valid_pipelines = {"colmap_openmvs", "hunyuan3d", "part_prior"}
        if self.pipeline not in valid_pipelines:
            logger.warning(
                "Invalid LNN_I2T3D_PIPELINE='%s', expected one of %s. "
                "Falling back to 'colmap_openmvs'.",
                self.pipeline,
                sorted(valid_pipelines),
            )
            self.pipeline = "colmap_openmvs"

        # part_prior 路径需要预训练 VAE 权重，未配置时回退到 colmap_openmvs
        if self.pipeline == "part_prior" and not self.part_prior.pretrained_model_path:
            logger.warning(
                "LNN_I2T3D_PIPELINE=part_prior 但未配置预训练权重 "
                "(LNN_I2T3D_PART_PRIOR_MODEL_PATH 为空)，回退到 colmap_openmvs。"
            )
            self.pipeline = "colmap_openmvs"

        valid_tiers = {"coarse", "standard", "high", "part_prior"}
        if self.precision_tier not in valid_tiers:
            logger.warning(
                "Invalid LNN_I2T3D_PRECISION_TIER='%s', expected one of %s. "
                "Falling back to 'standard'.",
                self.precision_tier,
                sorted(valid_tiers),
            )
            self.precision_tier = "standard"

        if self.min_photos < 3:
            logger.warning(
                "LNN_I2T3D_MIN_PHOTOS=%s too small, SfM requires >= 3. "
                "Setting to 3.",
                self.min_photos,
            )
            self.min_photos = 3

        if self.max_photos < self.min_photos:
            logger.warning(
                "LNN_I2T3D_MAX_PHOTOS=%s < MIN_PHOTOS=%s, adjusting.",
                self.max_photos,
                self.min_photos,
            )
            self.max_photos = self.min_photos

        if self.calibration_block_mm <= 0:
            logger.warning(
                "LNN_I2T3D_CALIBRATION_BLOCK_MM=%s invalid, must be > 0. "
                "Setting to 30.0 (default gauge block).",
                self.calibration_block_mm,
            )
            self.calibration_block_mm = 30.0

    @property
    def precision_specs(self) -> dict:
        """返回当前精度档位对应的工程参数。"""
        specs = {
            "coarse": {
                "expected_accuracy_mm": "0.5-2.0",
                "suitable_for": [
                    "工艺理解卡片",
                    "可视化展示",
                    "与客户沟通形状",
                    "装夹方向预判",
                ],
                "not_suitable_for": [
                    "配合面尺寸",
                    "公差检验",
                    "CAM 加工",
                ],
                "colmap_feature_threshold": 500,
                "openmvs_resolution_level": 1,
            },
            "standard": {
                "expected_accuracy_mm": "0.1-1.0",
                "suitable_for": [
                    "非配合面尺寸复核",
                    "铸锻毛坯检验",
                    "外形轮廓参考",
                    "孔位粗定位（±0.5mm）",
                ],
                "not_suitable_for": [
                    "配合面（H7/h6 等）",
                    "螺纹、退刀槽、盲孔",
                    "CAM 直接加工",
                ],
                "colmap_feature_threshold": 2000,
                "openmvs_resolution_level": 0,
            },
            "high": {
                "expected_accuracy_mm": "0.1-0.5",
                "suitable_for": [
                    "小零件细节观察",
                    "复杂曲面参考",
                    "特征点对齐参考",
                ],
                "not_suitable_for": [
                    "工业级配合面（0.01mm）",
                    "几何公差（GD&T）",
                    "直接上机床",
                ],
                "colmap_feature_threshold": 8000,
                "openmvs_resolution_level": -1,
            },
            # ADR-020 思路 2：零件专属先验补全路径
            # 精度 0.1-1mm（与 standard 同量级，受 VAE 先验质量 + 稀疏点云双重限制）
            "part_prior": {
                "expected_accuracy_mm": "0.1-1.0",
                "suitable_for": [
                    "少纹理零件先验补全",
                    "COLMAP 稀疏点云稠密化",
                    "非配合面尺寸复核",
                    "工艺理解卡片",
                ],
                "not_suitable_for": [
                    "配合面（H7/h6 等，0.01mm）",
                    "几何公差（GD&T）",
                    "CAM 直接加工",
                    "未配置预训练权重的场景",
                ],
                # part_prior 路径仍用 COLMAP 生成稀疏点云，feature_threshold 适用
                "colmap_feature_threshold": 2000,
                # part_prior 路径不走 OpenMVS，此字段保留为 0（占位，runner 不读取）
                "openmvs_resolution_level": 0,
            },
        }
        return specs[self.precision_tier]


# =============================================================================
# Feature Extraction Configuration
# =============================================================================
# 阶段 2：几何特征辅助提取模块配置
# 设计依据：项目记忆硬约束——
#   - mesh → 参数化 CAD 自动转换工业上未解决，必须 human-in-the-loop
#   - 系统定位「工程师助手」，非「全自动生产线」
#   - 所有特征参数必须经工程师审核 + CAM 二次校验才能上机床
#
# 环境变量命名约定：LNN_FE_*（feature_extraction 缩写）
# 字段命名与 precision_disclaimer.py 中引用的字段保持一致


@dataclass
class FeatureExtractionConfig:
    """几何特征提取模块配置。

    所有配置项支持环境变量覆盖，遵循 12-Factor App 原则。
    """

    # 总开关：桌面轻量档位下可关闭，避免 trimesh/open3d 依赖加载
    enabled: bool = field(
        default_factory=lambda: _bool_env("LNN_FE_ENABLED", True)
    )

    # 输出目录：存放每次特征提取任务的中间产物和最终 JSON
    output_dir: str = field(
        default_factory=lambda: _path(
            "LNN_FE_OUTPUT_DIR", os.path.join("output", "feature_extraction")
        )
    )

    # 并发约束：特征提取是 CPU 密集型（RANSAC），桌面模式默认串行
    max_concurrent: int = field(
        default_factory=lambda: _int_env("LNN_FE_MAX_CONCURRENT", 1)
    )

    # 任务超时（秒）：RANSAC + 圆柱拟合 + 孔检测在 5 万顶点 mesh 上约 30-300 秒
    task_timeout_seconds: int = field(
        default_factory=lambda: _int_env("LNN_FE_TASK_TIMEOUT", 600)
    )

    # 任务历史保留时长（小时）：比拍照重建长，因为工程师审核需要时间
    task_retention_hours: int = field(
        default_factory=lambda: _int_env("LNN_FE_TASK_RETENTION_HOURS", 168)
    )

    # --------- 平面提取参数（RANSAC） ---------
    # RANSAC 距离阈值（mm）：顶点到平面的距离小于此值才算内点
    # 越小越严格，但太小会导致噪声干扰；标准档位 0.5mm 较合理
    plane_ransac_threshold_mm: float = field(
        default_factory=lambda: _float_env("LNN_FE_PLANE_RANSAC_THRESHOLD_MM", 0.5)
    )
    # 最小内点数：少于此数的平面被丢弃（避免噪声碎片）
    plane_min_inliers: int = field(
        default_factory=lambda: _int_env("LNN_FE_PLANE_MIN_INLIERS", 1000)
    )
    # 最多提取多少个平面（避免过拟合噪声）
    plane_max_features: int = field(
        default_factory=lambda: _int_env("LNN_FE_PLANE_MAX_FEATURES", 20)
    )

    # --------- 圆柱提取参数 ---------
    # 圆柱半径范围（mm）：超出此范围的圆柱被丢弃
    cylinder_min_radius_mm: float = field(
        default_factory=lambda: _float_env("LNN_FE_CYLINDER_MIN_RADIUS_MM", 1.0)
    )
    cylinder_max_radius_mm: float = field(
        default_factory=lambda: _float_env("LNN_FE_CYLINDER_MAX_RADIUS_MM", 100.0)
    )
    cylinder_min_inliers: int = field(
        default_factory=lambda: _int_env("LNN_FE_CYLINDER_MIN_INLIERS", 500)
    )
    cylinder_max_features: int = field(
        default_factory=lambda: _int_env("LNN_FE_CYLINDER_MAX_FEATURES", 10)
    )

    # --------- 孔/凸台检测参数 ---------
    # 孔半径范围（mm）：超出此范围的孔被丢弃
    hole_min_radius_mm: float = field(
        default_factory=lambda: _float_env("LNN_FE_HOLE_MIN_RADIUS_MM", 0.5)
    )
    hole_max_radius_mm: float = field(
        default_factory=lambda: _float_env("LNN_FE_HOLE_MAX_RADIUS_MM", 50.0)
    )
    hole_max_features: int = field(
        default_factory=lambda: _int_env("LNN_FE_HOLE_MAX_FEATURES", 30)
    )

    # --------- mesh 预处理参数 ---------
    # 大 mesh 降采样目标顶点数：避免 RANSAC 在百万顶点 mesh 上过慢
    mesh_decimation_target_vertices: int = field(
        default_factory=lambda: _int_env("LNN_FE_MESH_DECIMATION_TARGET", 50000)
    )
    # 是否计算法向量（孔检测需要，依赖 trimesh）
    mesh_compute_normals: bool = field(
        default_factory=lambda: _bool_env("LNN_FE_MESH_COMPUTE_NORMALS", True)
    )

    # 精度档位（仅用于显示告知，实际精度由上游 mesh 决定）
    precision_tier: str = field(
        default_factory=lambda: _env("LNN_FE_PRECISION_TIER", "standard")
    )

    def __post_init__(self) -> None:
        """启动时校验配置合法性。"""
        valid_tiers = {"coarse", "standard", "high"}
        if self.precision_tier not in valid_tiers:
            logger.warning(
                "Invalid LNN_FE_PRECISION_TIER='%s', expected one of %s. "
                "Falling back to 'standard'.",
                self.precision_tier,
                sorted(valid_tiers),
            )
            self.precision_tier = "standard"

        if self.plane_ransac_threshold_mm <= 0:
            logger.warning(
                "LNN_FE_PLANE_RANSAC_THRESHOLD_MM=%s invalid, must be > 0. "
                "Setting to 0.5 (default).",
                self.plane_ransac_threshold_mm,
            )
            self.plane_ransac_threshold_mm = 0.5

        if self.plane_min_inliers < 100:
            logger.warning(
                "LNN_FE_PLANE_MIN_INLIERS=%s too small, must be >= 100. "
                "Setting to 100.",
                self.plane_min_inliers,
            )
            self.plane_min_inliers = 100

        if self.cylinder_min_radius_mm >= self.cylinder_max_radius_mm:
            logger.warning(
                "LNN_FE_CYLINDER_MIN_RADIUS_MM=%s >= MAX_RADIUS_MM=%s, "
                "adjusting to defaults.",
                self.cylinder_min_radius_mm,
                self.cylinder_max_radius_mm,
            )
            self.cylinder_min_radius_mm = 1.0
            self.cylinder_max_radius_mm = 100.0

        if self.hole_min_radius_mm >= self.hole_max_radius_mm:
            logger.warning(
                "LNN_FE_HOLE_MIN_RADIUS_MM=%s >= MAX_RADIUS_MM=%s, "
                "adjusting to defaults.",
                self.hole_min_radius_mm,
                self.hole_max_radius_mm,
            )
            self.hole_min_radius_mm = 0.5
            self.hole_max_radius_mm = 50.0

        if self.mesh_decimation_target_vertices < 1000:
            logger.warning(
                "LNN_FE_MESH_DECIMATION_TARGET=%s too small, must be >= 1000. "
                "Setting to 1000.",
                self.mesh_decimation_target_vertices,
            )
            self.mesh_decimation_target_vertices = 1000


# =============================================================================
# Parametric Geometry Configuration
# =============================================================================
# 阶段 3：参数化几何输出模块配置（ADR-008）
#
# 设计依据：项目记忆硬约束——
#   - mesh → 参数化 CAD 自动转换工业上未解决，必须 human-in-the-loop
#   - 系统定位「工程师助手」，非「全自动生产线」
#   - 生成的 STEP 文件必须经 CAM 软件（NX/PowerMill/PyCAM）二次校验后才允许上机床
#   - 普通手机摄影测量精度 0.1-1mm，配合面公差 0.01mm 物理上不可达
#
# 精度继承链：阶段 1 image_to_3d.precision_tier → 阶段 2 feature_extraction.precision_tier
#           → 阶段 3（本模块不引入新的精度档位，全程继承上游告知）
#
# 环境变量命名约定：LNN_PG_*（parametric_geometry 缩写）
# 字段命名与 step_disclaimer.py / pipeline.py 中引用的字段保持一致


@dataclass
class ParametricGeometryConfig:
    """参数化几何输出模块配置。

    所有配置项支持环境变量覆盖，遵循 12-Factor App 原则。
    """

    # 总开关：桌面轻量档位下可关闭，避免 pythonOCC/FreeCAD 依赖探测开销
    enabled: bool = field(
        default_factory=lambda: _bool_env("LNN_PG_ENABLED", True)
    )

    # 输出目录：存放每次参数化几何任务的工作目录（含 STEP/assembly_plan/brep_shapes）
    output_dir: str = field(
        default_factory=lambda: _path(
            "LNN_PG_OUTPUT_DIR", os.path.join("output", "parametric_geometry")
        )
    )

    # 并发约束：STEP 写入是 CPU 密集型（pythonOCC 布尔运算），桌面模式默认串行
    max_concurrent: int = field(
        default_factory=lambda: _int_env("LNN_PG_MAX_CONCURRENT", 1)
    )

    # 任务超时（秒）：pythonOCC 在 50 个形状的布尔运算下约 10-60 秒；
    # 复杂零件（100+ 形状）可能数分钟，默认 600 秒兜底
    task_timeout_seconds: int = field(
        default_factory=lambda: _int_env("LNN_PG_TASK_TIMEOUT", 600)
    )

    # 任务历史保留时长（小时）：与阶段 2 一致，工程师审核需要时间
    task_retention_hours: int = field(
        default_factory=lambda: _int_env("LNN_PG_TASK_RETENTION_HOURS", 168)
    )

    # 毛坯余量（mm）：装配器在 add 形状 bbox 并集外扩此值得到毛坯尺寸
    # 2.0mm 是粗加工常见余量；精加工余量 0.5mm 由阶段 4 切削参数推荐覆盖
    blank_margin_mm: float = field(
        default_factory=lambda: _float_env("LNN_PG_BLANK_MARGIN_MM", 2.0)
    )

    # 精度档位（仅用于显示告知，实际精度由上游 mesh 决定）
    # 继承自阶段 1/2，本模块不引入新档位
    precision_tier: str = field(
        default_factory=lambda: _env("LNN_PG_PRECISION_TIER", "standard")
    )

    # 默认 mesh 标定状态：当任务创建时未显式传入 mesh_calibrated 时使用
    # 保守默认为 False，强制上游显式声明已标定
    default_mesh_calibrated: bool = field(
        default_factory=lambda: _bool_env("LNN_PG_DEFAULT_MESH_CALIBRATED", False)
    )

    def __post_init__(self) -> None:
        """启动时校验配置合法性。"""
        valid_tiers = {"coarse", "standard", "high"}
        if self.precision_tier not in valid_tiers:
            logger.warning(
                "Invalid LNN_PG_PRECISION_TIER='%s', expected one of %s. "
                "Falling back to 'standard'.",
                self.precision_tier,
                sorted(valid_tiers),
            )
            self.precision_tier = "standard"

        if self.blank_margin_mm <= 0:
            logger.warning(
                "LNN_PG_BLANK_MARGIN_MM=%s invalid, must be > 0. "
                "Setting to 2.0 (default roughing margin).",
                self.blank_margin_mm,
            )
            self.blank_margin_mm = 2.0

        if self.blank_margin_mm > 20.0:
            logger.warning(
                "LNN_PG_BLANK_MARGIN_MM=%s too large (>20mm), "
                "may produce oversized blank. Verify before production use.",
                self.blank_margin_mm,
            )

        if self.max_concurrent < 1:
            logger.warning(
                "LNN_PG_MAX_CONCURRENT=%s invalid, must be >= 1. "
                "Setting to 1 (serial).",
                self.max_concurrent,
            )
            self.max_concurrent = 1

        if self.task_timeout_seconds < 60:
            logger.warning(
                "LNN_PG_TASK_TIMEOUT=%s too small (<60s), "
                "pythonOCC 布尔运算可能未完成。Setting to 600.",
                self.task_timeout_seconds,
            )
            self.task_timeout_seconds = 600


class CuttingParametersConfig:
    """切削参数推荐模块配置（阶段 4）。

    所有配置项支持环境变量覆盖，遵循 12-Factor App 原则。
    环境变量前缀：LNN_CP_*
    """

    # 总开关：桌面轻量档位下可关闭，避免材料数据库加载开销
    enabled: bool = field(
        default_factory=lambda: _bool_env("LNN_CP_ENABLED", True)
    )

    # 输出目录：存放每次切削参数任务的工作目录（含 ChatterParams JSON）
    output_dir: str = field(
        default_factory=lambda: _path(
            "LNN_CP_OUTPUT_DIR", os.path.join("output", "cutting_parameters")
        )
    )

    # 并发约束：切削参数推荐为 CPU 密集型（Taylor 估算 + 数学计算），桌面模式默认串行
    max_concurrent: int = field(
        default_factory=lambda: _int_env("LNN_CP_MAX_CONCURRENT", 1)
    )

    # 任务超时（秒）：单任务推荐 < 1 秒，但工程师审核可能耗时数小时
    # 此 timeout 仅覆盖 run_pipeline 阶段，审核等待不计入
    task_timeout_seconds: int = field(
        default_factory=lambda: _int_env("LNN_CP_TASK_TIMEOUT", 60)
    )

    # 任务历史保留时长（小时）：与阶段 2/3 一致，工程师审核需要时间
    task_retention_hours: int = field(
        default_factory=lambda: _int_env("LNN_CP_TASK_RETENTION_HOURS", 168)
    )

    # 默认刀具直径（mm）：用户未指定时使用
    default_tool_diameter_mm: float = field(
        default_factory=lambda: _float_env("LNN_CP_DEFAULT_TOOL_DIAMETER_MM", 10.0)
    )

    # 默认齿数：用户未指定时使用
    default_num_flutes: int = field(
        default_factory=lambda: _int_env("LNN_CP_DEFAULT_NUM_FLUTES", 4)
    )

    # 默认机床类型（仅供追溯，实际机床动态参数由阶段 5 查询）
    default_machine_type: str = field(
        default_factory=lambda: _env("LNN_CP_DEFAULT_MACHINE_TYPE", "vmc_850")
    )

    # 精度档位（仅用于显示告知，实际精度由上游 mesh 决定）
    # 继承自阶段 1/2/3，本模块不引入新档位
    precision_tier: str = field(
        default_factory=lambda: _env("LNN_CP_PRECISION_TIER", "standard")
    )

    # 默认 mesh 标定状态：保守默认为 False，强制上游显式声明已标定
    default_mesh_calibrated: bool = field(
        default_factory=lambda: _bool_env("LNN_CP_DEFAULT_MESH_CALIBRATED", False)
    )

    # 是否允许 SUCCEEDED 状态任务删除（项目记忆硬约束：始终 False）
    # SUCCEEDED 任务可能已被阶段 5 引用，删除会破坏追溯链
    allow_delete_succeeded: bool = field(
        default_factory=lambda: _bool_env("LNN_CP_ALLOW_DELETE_SUCCEEDED", False)
    )

    def __post_init__(self) -> None:
        """启动时校验配置合法性。"""
        valid_tiers = {"coarse", "standard", "high"}
        if self.precision_tier not in valid_tiers:
            logger.warning(
                "Invalid LNN_CP_PRECISION_TIER='%s', expected one of %s. "
                "Falling back to 'standard'.",
                self.precision_tier,
                sorted(valid_tiers),
            )
            self.precision_tier = "standard"

        if self.default_tool_diameter_mm <= 0:
            logger.warning(
                "LNN_CP_DEFAULT_TOOL_DIAMETER_MM=%s invalid, must be > 0. "
                "Setting to 10.0 (default endmill).",
                self.default_tool_diameter_mm,
            )
            self.default_tool_diameter_mm = 10.0

        if self.default_num_flutes < 1:
            logger.warning(
                "LNN_CP_DEFAULT_NUM_FLUTES=%s invalid, must be >= 1. "
                "Setting to 4 (default endmill).",
                self.default_num_flutes,
            )
            self.default_num_flutes = 4

        if self.max_concurrent < 1:
            logger.warning(
                "LNN_CP_MAX_CONCURRENT=%s invalid, must be >= 1. "
                "Setting to 1 (serial).",
                self.max_concurrent,
            )
            self.max_concurrent = 1

        if self.task_timeout_seconds < 10:
            logger.warning(
                "LNN_CP_TASK_TIMEOUT=%s too small (<10s), "
                "材料查询可能未完成。Setting to 60.",
                self.task_timeout_seconds,
            )
            self.task_timeout_seconds = 60

        if self.allow_delete_succeeded:
            logger.warning(
                "LNN_CP_ALLOW_DELETE_SUCCEEDED=true 违反项目记忆硬约束"
                "（SUCCEEDED 任务可能被阶段 5 引用），强制重置为 false。"
            )
            self.allow_delete_succeeded = False


@dataclass
class ChatterPredictionConfig:
    """颤振预测接入模块配置（阶段 5）。

    所有配置项支持环境变量覆盖，遵循 12-Factor App 原则。
    环境变量前缀：LNN_CH_*

    工程优先策略（项目记忆硬约束）：
    - 默认走 Tlusty 解析法路径（stability.py 已实现，工程可用）
    - LTC 神经网络路径标记为「实验性」，仅在 chatter_model.pt 存在时尝试
    - chatter_model.pt 不存在或推理失败时自动回退到 Tlusty 解析法
    - cam_validation_required 始终 True（项目记忆硬约束，不可关闭）
    - allow_delete_succeeded 始终 False（SUCCEEDED 任务可能被阶段 6 引用）
    """

    # 总开关：桌面轻量档位下可关闭，避免 stability 模块加载开销
    enabled: bool = field(
        default_factory=lambda: _bool_env("LNN_CH_ENABLED", True)
    )

    # 输出目录：存放每次颤振预测任务的工作目录（含 ChatterReport JSON）
    output_dir: str = field(
        default_factory=lambda: _path(
            "LNN_CH_OUTPUT_DIR", os.path.join("output", "chatter_prediction")
        )
    )

    # 并发约束：双路径预测为 CPU 密集型（解析法 < 10ms / 特征，LTC 推理视模型而定）
    # 桌面模式默认串行，避免与 stage 1-4 抢占资源
    max_concurrent: int = field(
        default_factory=lambda: _int_env("LNN_CH_MAX_CONCURRENT", 1)
    )

    # 任务超时（秒）：单特征预测 < 1 秒，多特征批量需更长时间
    # 此 timeout 仅覆盖 run_pipeline 阶段，工程师审核等待不计入
    task_timeout_seconds: int = field(
        default_factory=lambda: _int_env("LNN_CH_TASK_TIMEOUT", 120)
    )

    # 任务历史保留时长（小时）：与阶段 2/3/4 一致，工程师审核需要时间
    task_retention_hours: int = field(
        default_factory=lambda: _int_env("LNN_CH_TASK_RETENTION_HOURS", 168)
    )

    # 默认精度档位（仅用于显示告知，实际精度由上游 mesh 决定）
    # 继承自阶段 1/2/3/4，本模块不引入新档位
    precision_tier: str = field(
        default_factory=lambda: _env("LNN_CH_PRECISION_TIER", "standard")
    )

    # 默认 mesh 标定状态：保守默认为 False，强制上游显式声明已标定
    default_mesh_calibrated: bool = field(
        default_factory=lambda: _bool_env("LNN_CH_DEFAULT_MESH_CALIBRATED", False)
    )

    # 默认机床类型（仅供追溯，实际机床动态参数由阶段 4 ChatterParams 携带）
    default_machine_type: str = field(
        default_factory=lambda: _env("LNN_CH_DEFAULT_MACHINE_TYPE", "vmc_850")
    )

    # 是否强制走解析法路径（测试用，忽略 chatter_model.pt 存在性）
    # 生产环境应保持 False，让适配器自动检测 LTC 可用性
    force_analytical: bool = field(
        default_factory=lambda: _bool_env("LNN_CH_FORCE_ANALYTICAL", False)
    )

    # 是否允许 SUCCEEDED 状态任务删除（项目记忆硬约束：始终 False）
    # SUCCEEDED 任务可能已被阶段 6 G 代码生成引用，删除会破坏追溯链
    allow_delete_succeeded: bool = field(
        default_factory=lambda: _bool_env("LNN_CH_ALLOW_DELETE_SUCCEEDED", False)
    )

    # CAM 二次校验强制（项目记忆硬约束：始终 True，不可关闭）
    # 本系统输出的 ChatterReport 仅供阶段 6 参考，实际加工必须经 CAM 校验
    cam_validation_required: bool = field(
        default_factory=lambda: _bool_env("LNN_CH_CAM_VALIDATION_REQUIRED", True)
    )

    def __post_init__(self) -> None:
        """启动时校验配置合法性。"""
        valid_tiers = {"coarse", "standard", "high"}
        if self.precision_tier not in valid_tiers:
            logger.warning(
                "Invalid LNN_CH_PRECISION_TIER='%s', expected one of %s. "
                "Falling back to 'standard'.",
                self.precision_tier,
                sorted(valid_tiers),
            )
            self.precision_tier = "standard"

        if self.max_concurrent < 1:
            logger.warning(
                "LNN_CH_MAX_CONCURRENT=%s invalid, must be >= 1. "
                "Setting to 1 (serial).",
                self.max_concurrent,
            )
            self.max_concurrent = 1

        if self.task_timeout_seconds < 10:
            logger.warning(
                "LNN_CH_TASK_TIMEOUT=%s too small (<10s), "
                "批量预测可能未完成。Setting to 120.",
                self.task_timeout_seconds,
            )
            self.task_timeout_seconds = 120

        # 项目记忆硬约束：SUCCEEDED 禁删，强制 False
        if self.allow_delete_succeeded:
            logger.warning(
                "LNN_CH_ALLOW_DELETE_SUCCEEDED=true 违反项目记忆硬约束"
                "（SUCCEEDED 任务可能被阶段 6 G 代码生成引用），强制重置为 false。"
            )
            self.allow_delete_succeeded = False

        # 项目记忆硬约束：CAM 二次校验强制，始终 True
        if not self.cam_validation_required:
            logger.warning(
                "LNN_CH_CAM_VALIDATION_REQUIRED=false 违反项目记忆硬约束"
                "（生成的 ChatterReport 仅供阶段 6 参考，"
                "实际加工必须经 CAM 软件二次校验），强制重置为 true。"
            )
            self.cam_validation_required = True


@dataclass
class GCodeGenerationConfig:
    """G 代码生成模块配置（阶段 6）。

    所有配置项支持环境变量覆盖，遵循 12-Factor App 原则。
    环境变量前缀：LNN_GC_*

    工程优先策略（项目记忆硬约束）：
    - 系统定位「工程师助手」，非「全自动 G 代码生成器」
    - 生成的 G 代码必须经 CAM 软件（NX/PowerMill/PyCAM）二次校验后方可上机床
    - 系统绝不直接接口 CNC 控制器，G 代码文件需手动加载到 CAM 软件
    - 复用现有 app.postprocessor 包 + GCodeGenerator（212 个测试用例覆盖）
    - cam_validation_required 始终 True（项目记忆硬约束，不可关闭）
    - allow_delete_succeeded 始终 False（SUCCEEDED 任务可能被阶段 7 CAM 校验引用）

    pipeline.py 实际使用字段范围：
    - cfg.output_dir（pipeline.py 第 634 行：决定 G 代码导出根目录）
    - cfg.precision_tier（pipeline.py 第 684 行：写入 disclaimer，仅用于显示告知）
    其他参数（controller_type / program_number / safe_z / stock_top_z）由 API 请求传入，不在 Config 中。
    """

    # 总开关：桌面轻量档位下可关闭
    enabled: bool = field(
        default_factory=lambda: _bool_env("LNN_GC_ENABLED", True)
    )

    # 输出目录：存放每次 G 代码生成任务的工作目录（含 .gcode 文件 + 审核 JSON）
    # pipeline.py 在此目录下为每个任务创建独立 workspace_dir
    output_dir: str = field(
        default_factory=lambda: _path(
            "LNN_GC_OUTPUT_DIR", os.path.join("output", "gcode_generation")
        )
    )

    # 并发约束：G 代码生成为 CPU 密集型（GeneratorAdapter 单次 < 500ms）
    # 桌面模式默认串行，避免与阶段 1-5 抢占资源
    max_concurrent: int = field(
        default_factory=lambda: _int_env("LNN_GC_MAX_CONCURRENT", 1)
    )

    # 任务超时（秒）：单任务生成 + 导出 < 5 秒，审核等待不计入
    task_timeout_seconds: int = field(
        default_factory=lambda: _int_env("LNN_GC_TASK_TIMEOUT", 60)
    )

    # 任务历史保留时长（小时）：与阶段 2-5 一致，工程师审核需要时间
    task_retention_hours: int = field(
        default_factory=lambda: _int_env("LNN_GC_TASK_RETENTION_HOURS", 168)
    )

    # 默认精度档位（仅用于 disclaimer 显示告知，实际精度由上游 mesh 决定）
    # pipeline.py 通过 getattr(cfg, "precision_tier", "mesh_calibrated") 读取
    precision_tier: str = field(
        default_factory=lambda: _env("LNN_GC_PRECISION_TIER", "mesh_calibrated")
    )

    # 默认 mesh 标定状态：保守默认为 False，强制上游显式声明已标定
    default_mesh_calibrated: bool = field(
        default_factory=lambda: _bool_env("LNN_GC_DEFAULT_MESH_CALIBRATED", False)
    )

    # 默认控制器类型（仅供 disclaimer 显示追溯，实际 controller_type 由 API 请求传入）
    default_controller_type: str = field(
        default_factory=lambda: _env("LNN_GC_DEFAULT_CONTROLLER_TYPE", "fanuc_0i")
    )

    # 是否允许 SUCCEEDED 状态任务删除（项目记忆硬约束：始终 False）
    # SUCCEEDED 任务可能已被阶段 7 CAM 校验引用，删除会破坏追溯链
    allow_delete_succeeded: bool = field(
        default_factory=lambda: _bool_env("LNN_GC_ALLOW_DELETE_SUCCEEDED", False)
    )

    # CAM 二次校验强制（项目记忆硬约束：始终 True，不可关闭）
    # 生成的 G 代码仅供人工加载到 CAM 软件，系统绝不直接接口 CNC 控制器
    cam_validation_required: bool = field(
        default_factory=lambda: _bool_env("LNN_GC_CAM_VALIDATION_REQUIRED", True)
    )

    def __post_init__(self) -> None:
        """启动时校验配置合法性。"""
        # precision_tier 接受阶段 1-5 已有的档位 + mesh_calibrated（阶段 6 默认值）
        valid_tiers = {"coarse", "standard", "high", "mesh_calibrated"}
        if self.precision_tier not in valid_tiers:
            logger.warning(
                "Invalid LNN_GC_PRECISION_TIER='%s', expected one of %s. "
                "Falling back to 'mesh_calibrated'.",
                self.precision_tier,
                sorted(valid_tiers),
            )
            self.precision_tier = "mesh_calibrated"

        if self.max_concurrent < 1:
            logger.warning(
                "LNN_GC_MAX_CONCURRENT=%s invalid, must be >= 1. "
                "Setting to 1 (serial).",
                self.max_concurrent,
            )
            self.max_concurrent = 1

        if self.task_timeout_seconds < 5:
            logger.warning(
                "LNN_GC_TASK_TIMEOUT=%s too small (<5s), "
                "G 代码生成可能未完成。Setting to 60.",
                self.task_timeout_seconds,
            )
            self.task_timeout_seconds = 60

        # 项目记忆硬约束：SUCCEEDED 禁删，强制 False
        if self.allow_delete_succeeded:
            logger.warning(
                "LNN_GC_ALLOW_DELETE_SUCCEEDED=true 违反项目记忆硬约束"
                "（SUCCEEDED 任务可能被阶段 7 CAM 校验引用），强制重置为 false。"
            )
            self.allow_delete_succeeded = False

        # 项目记忆硬约束：CAM 二次校验强制，始终 True
        if not self.cam_validation_required:
            logger.warning(
                "LNN_GC_CAM_VALIDATION_REQUIRED=false 违反项目记忆硬约束"
                "（生成的 G 代码必须经 CAM 软件二次校验后方可上机床，"
                "系统绝不直接接口 CNC 控制器），强制重置为 true。"
            )
            self.cam_validation_required = True


# =============================================================================
# Stage 7 Configuration: CAM Validation (G 代码二次校验)
# =============================================================================
# [ADR-018] 阶段 7 CAM 校验模块配置
# 设计依据：docs/adr/ADR-018-CAM校验.md
# pipeline 数据流：
#   阶段 6 G 代码文件 + report.json
#       → GCodeLoader.load() 加载 G 代码 + 特征行号区间 + 控制器类型
#       → InternalValidator.validate() 复用 CollisionDetector 内部预校验（AABB 包围盒）
#           + 按 block_number 归因到 feature_results.line_range
#       → CamAdapter.validate() CAM 软件二次校验
#           （internal_only / pycam / nx_open / powermill / manual 五后端策略）
#       → CAM 软件不可用时自动降级到 manual（生成校验清单 + 工程师回填）
#       → 工程师审核每个特征校验结果（pending → confirmed / rejected / edited）
#       → confirm_task → SUCCEEDED
#       → 导出 cam_report.json（最终结论）+ internal_report.json（调试细节）


@dataclass
class CamValidationConfig:
    """CAM 校验模块配置（阶段 7）。

    所有配置项支持环境变量覆盖，遵循 12-Factor App 原则。
    环境变量前缀：LNN_CAM_*

    工程优先策略（项目记忆硬约束）：
    - 系统定位「工程师助手」，非「全自动 CAM 仿真器」
    - 系统绝不直接接口 CNC 控制器，阶段 7 产物终止于「CAM 校验报告 JSON」
    - 大一独立项目不触及物理机床；阶段 7 产物终止于「CAM 校验报告 JSON」
    - cam_validation_required 始终 True（项目记忆硬约束，不可关闭）
    - allow_delete_succeeded 始终 False（避免阶段 5 任务悬空，与阶段 6 对齐）
    - HRC52 pending_calibration 由阶段 5 标注，阶段 7 仅继承，不二次拟合
    - 复用现有 app.simulation.collision_detector.CollisionDetector（组合 has-a）
    - 复用现有 app.simulation.toolpath_parser.ToolpathParser

    pipeline.py 实际使用字段范围：
    - cfg.output_dir：决定 CAM 校验任务工作目录（cam_report.json + internal_report.json）
    - cfg.precision_tier：写入 disclaimer，仅用于显示告知
    - cfg.default_cam_backend：CamAdapter 默认后端（internal_only / pycam / nx_open / powermill / manual）
    - cfg.nx_open_executable / powermill_executable / pycam_executable：CAM 软件 subprocess 调用入口
    - cfg.cam_validation_required / cfg.allow_delete_succeeded：__post_init__ 强制约束
    """

    # 总开关：桌面轻量档位下可关闭
    enabled: bool = field(
        default_factory=lambda: _bool_env("LNN_CAM_ENABLED", True)
    )

    # 输出目录：存放每次 CAM 校验任务的工作目录（含 cam_report.json + internal_report.json）
    # pipeline.py 在此目录下为每个任务创建独立 workspace_dir
    output_dir: str = field(
        default_factory=lambda: _path(
            "LNN_CAM_OUTPUT_DIR", os.path.join("output", "cam_validation")
        )
    )

    # 并发约束：CAM 校验为 CPU 密集型（InternalValidator 秒级 + CAM 软件 subprocess 分钟级）
    # 桌面模式默认串行，避免与阶段 1-6 抢占资源
    max_concurrent: int = field(
        default_factory=lambda: _int_env("LNN_CAM_MAX_CONCURRENT", 1)
    )

    # 任务超时（秒）：CAM 软件 subprocess 可能耗时数分钟，留足缓冲
    # internal_only 后端秒级返回，manual 后端等待工程师回填可能跨日
    task_timeout_seconds: int = field(
        default_factory=lambda: _int_env("LNN_CAM_TASK_TIMEOUT", 600)
    )

    # 任务历史保留时长（小时）：与阶段 2-6 一致，工程师审核需要时间
    task_retention_hours: int = field(
        default_factory=lambda: _int_env("LNN_CAM_TASK_RETENTION_HOURS", 168)
    )

    # 默认精度档位（仅用于 disclaimer 显示告知，实际精度由上游 mesh 决定）
    # 阶段 7 继承阶段 6 的 precision_tier，不重新标定
    precision_tier: str = field(
        default_factory=lambda: _env("LNN_CAM_PRECISION_TIER", "mesh_calibrated")
    )

    # 默认 CAM 后端（CamAdapter 策略模式）
    # - internal_only：仅运行 InternalValidator（秒级，AABB 包围盒），不调用外部 CAM 软件
    # - pycam：subprocess 调用开源 PyCAM 包装器脚本（4 项基础检查，无需许可证）
    # - nx_open：调用 Siemens NX Open subprocess（需 NX 许可证）
    # - powermill：调用 Autodesk PowerMill subprocess（需 PowerMill 许可证）
    # - manual：生成校验清单 + 工程师回填（默认降级路径，无需任何外部软件）
    default_cam_backend: str = field(
        default_factory=lambda: _env("LNN_CAM_DEFAULT_BACKEND", "internal_only")
    )

    # NX Open 可执行文件路径（仅 default_cam_backend=nx_open 时使用）
    # 留空时 CamAdapter 自动降级到 manual
    nx_open_executable: str = field(
        default_factory=lambda: _env("LNN_CAM_NX_OPEN_EXECUTABLE", "")
    )

    # PowerMill 可执行文件路径（仅 default_cam_backend=powermill 时使用）
    # 留空时 CamAdapter 自动降级到 manual
    powermill_executable: str = field(
        default_factory=lambda: _env("LNN_CAM_POWERMILL_EXECUTABLE", "")
    )

    # PyCAM 包装器脚本路径（仅 default_cam_backend=pycam 时使用）
    # 指向项目自带的 python/scripts/cam_adapters/pycam/autorun_gcode_check.py
    # 留空时 CamAdapter 自动降级到 manual（与 nx_open_executable / powermill_executable 风格对齐）
    pycam_executable: str = field(
        default_factory=lambda: _env("LNN_CAM_PYCAM_EXECUTABLE", "")
    )

    # 是否允许 SUCCEEDED 状态任务删除（项目记忆硬约束：始终 False）
    # SUCCEEDED 任务包含 cam_report.json，删除会破坏追溯链
    allow_delete_succeeded: bool = field(
        default_factory=lambda: _bool_env("LNN_CAM_ALLOW_DELETE_SUCCEEDED", False)
    )

    # CAM 二次校验强制（项目记忆硬约束：始终 True，不可关闭）
    # 阶段 6 G 代码必须经阶段 7 CAM 软件二次校验后方可上机床
    # 系统绝不直接接口 CNC 控制器，CAM 校验报告 JSON 为阶段 7 最终产物
    cam_validation_required: bool = field(
        default_factory=lambda: _bool_env("LNN_CAM_VALIDATION_REQUIRED", True)
    )

    def __post_init__(self) -> None:
        """启动时校验配置合法性。"""
        # precision_tier 接受阶段 1-6 已有的档位
        valid_tiers = {"coarse", "standard", "high", "mesh_calibrated"}
        if self.precision_tier not in valid_tiers:
            logger.warning(
                "Invalid LNN_CAM_PRECISION_TIER='%s', expected one of %s. "
                "Falling back to 'mesh_calibrated'.",
                self.precision_tier,
                sorted(valid_tiers),
            )
            self.precision_tier = "mesh_calibrated"

        # default_cam_backend 必须是 5 个合法后端之一
        valid_backends = {
            "internal_only",
            "pycam",
            "nx_open",
            "powermill",
            "manual",
        }
        if self.default_cam_backend not in valid_backends:
            logger.warning(
                "Invalid LNN_CAM_DEFAULT_BACKEND='%s', expected one of %s. "
                "Falling back to 'internal_only'.",
                self.default_cam_backend,
                sorted(valid_backends),
            )
            self.default_cam_backend = "internal_only"

        if self.max_concurrent < 1:
            logger.warning(
                "LNN_CAM_MAX_CONCURRENT=%s invalid, must be >= 1. "
                "Setting to 1 (serial).",
                self.max_concurrent,
            )
            self.max_concurrent = 1

        if self.task_timeout_seconds < 30:
            logger.warning(
                "LNN_CAM_TASK_TIMEOUT=%s too small (<30s), "
                "CAM 软件 subprocess 可能未完成。Setting to 600.",
                self.task_timeout_seconds,
            )
            self.task_timeout_seconds = 600

        # 项目记忆硬约束：SUCCEEDED 禁删，强制 False
        # LNN_CAM_ALLOW_DELETE_SUCCEEDED 环境变量不可开启
        if self.allow_delete_succeeded:
            logger.warning(
                "LNN_CAM_ALLOW_DELETE_SUCCEEDED=true 违反项目记忆硬约束"
                "（SUCCEEDED 任务包含 cam_report.json，删除会破坏追溯链），"
                "强制重置为 false。"
            )
            self.allow_delete_succeeded = False

        # 项目记忆硬约束：CAM 二次校验强制，始终 True
        # LNN_CAM_VALIDATION_REQUIRED 环境变量不可关闭
        if not self.cam_validation_required:
            logger.warning(
                "LNN_CAM_VALIDATION_REQUIRED=false 违反项目记忆硬约束"
                "（阶段 6 G 代码必须经阶段 7 CAM 软件二次校验后方可上机床，"
                "系统绝不直接接口 CNC 控制器），强制重置为 true。"
            )
            self.cam_validation_required = True


# =============================================================================
# Dreaming Configuration (ADR-021 离线反思机制)
# =============================================================================
# 对应 Anthropic Claude Managed Agents 的 Dreaming 机制本地化集成。
#
# 仿生神经科学"记忆巩固"理论：Agent 在 Session 间隙离线审查 Memory Store，
# 执行去重合并、过时更新、跨 Session 洞察浮现，并将洞察转化为可执行规则。
#
# 三阶段闭环：
#   Memory（工作中学习）→ Dreaming（休息时反思）→ Outcomes（自检反馈）
#
# 硬约束（__post_init__ 强制对齐项目记忆硬约束）：
#   - cam_validation_required 始终 True（不被反思规则绕过）
#   - allow_delete_succeeded 始终 False（SUCCEEDED 任务禁删）
#   - hrc52_pending_calibration_penalty > 0（HRC52 强制降低置信度）
#   - k_s_direct_passthrough 始终 True（K_s → cutting_force_coeff 直接传递，不二次拟合）
#
# 环境变量命名约定：LNN_DREAM_*（dreaming 缩写）


@dataclass
class DreamingConfig:
    """Dreaming 离线反思模块配置（ADR-021）。

    所有配置项支持环境变量覆盖，遵循 12-Factor App 原则。
    环境变量前缀：LNN_DREAM_*

    P0/P1/P2 阶段已实现模块：
        - P0：LocalMemoryStore / SessionExtractor / DreamReflector /
              RuleSynthesizer / ReportGenerator / DreamingCLI
        - P1：DreamingAuditRecorder / DreamingSchedulerAdapter /
              RuleValidator / RuleApplicator
        - P2：ProgressivePublisher / EffectivenessMetricsCollector /
              RollbackManager / ClosedLoop
    """

    # --------- 总开关 ---------
    # 桌面轻量档位下可关闭，避免 GraphStore + ChromaDB 加载开销
    enabled: bool = field(
        default_factory=lambda: _bool_env("LNN_DREAM_ENABLED", True)
    )

    # --------- 反思调度（P1 DreamingSchedulerAdapter） ---------
    # HeartbeatScheduler cron 表达式：默认每天凌晨 02:00 触发反思
    # 生产环境应避开加工时段，避免与 CAM 校验任务竞争资源
    dream_cron_expression: str = field(
        default_factory=lambda: _env("LNN_DREAM_CRON", "0 2 * * *")
    )
    # 单次反思任务超时（秒）：GraphStore 遍历 + 洞察提取 + 规则合成约 5-30 分钟
    dream_task_timeout_seconds: int = field(
        default_factory=lambda: _int_env("LNN_DREAM_TASK_TIMEOUT", 1800)
    )

    # --------- Memory Store（P0 LocalMemoryStore） ---------
    # GraphStore + 反思历史持久化目录
    memory_store_dir: str = field(
        default_factory=lambda: _path(
            "LNN_DREAM_MEMORY_DIR", os.path.join("output", "dreaming", "memory")
        )
    )
    # Git 仓库目录（反思产物以分支形式归档）
    git_repo_dir: str = field(
        default_factory=lambda: _path(
            "LNN_DREAM_GIT_DIR", os.path.join("output", "dreaming", "git")
        )
    )

    # --------- Session 提取（P0 SessionExtractor） ---------
    # MLflow tracking URI（Session 数据源之一）
    mlflow_tracking_uri: str = field(
        default_factory=lambda: _env(
            "LNN_DREAM_MLFLOW_URI",
            os.path.join("output", "mlruns"),
        )
    )
    # audit_log 路径（Session 数据源之二）
    audit_log_path: str = field(
        default_factory=lambda: _env(
            "LNN_DREAM_AUDIT_LOG_PATH",
            os.path.join("output", "logs", "audit_log.jsonl"),
        )
    )
    # cutting_store 路径（Session 数据源之三）
    cutting_store_path: str = field(
        default_factory=lambda: _env(
            "LNN_DREAM_CUTTING_STORE_PATH",
            os.path.join("output", "cutting_store.json"),
        )
    )
    # CAM 校验报告目录（Session 数据源之四）
    cam_report_dir: str = field(
        default_factory=lambda: _env(
            "LNN_DREAM_CAM_REPORT_DIR",
            os.path.join("output", "cam_validation"),
        )
    )

    # --------- Reflector（P0 DreamReflector） ---------
    # 最少触发反思的 Session 数：低于此值不触发反思（避免数据不足）
    min_sessions_for_dream: int = field(
        default_factory=lambda: _int_env("LNN_DREAM_MIN_SESSIONS", 5)
    )
    # 洞察去重相似度阈值（0-1，余弦相似度）
    dedup_similarity_threshold: float = field(
        default_factory=lambda: _float_env("LNN_DEDUP_THRESHOLD", 0.85)
    )
    # 单次反思最多提取的洞察数
    max_insights_per_dream: int = field(
        default_factory=lambda: _int_env("LNN_DREAM_MAX_INSIGHTS", 20)
    )

    # --------- Rule Synthesizer（P0 RuleSynthesizer） ---------
    # 规则草稿输出目录
    rule_output_dir: str = field(
        default_factory=lambda: _path(
            "LNN_DREAM_RULE_DIR", os.path.join("output", "dreaming", "rules")
        )
    )
    # 单次反思最多合成的规则数
    max_rules_per_dream: int = field(
        default_factory=lambda: _int_env("LNN_DREAM_MAX_RULES", 10)
    )

    # --------- Rule Validator（P1 RuleValidator） ---------
    # 沙箱验证工作目录
    sandbox_validation_dir: str = field(
        default_factory=lambda: _path(
            "LNN_DREAM_SANDBOX_DIR",
            os.path.join("output", "dreaming", "sandbox"),
        )
    )
    # 单条规则沙箱验证超时（秒）
    validation_timeout_seconds: int = field(
        default_factory=lambda: _int_env("LNN_DREAM_VALIDATION_TIMEOUT", 120)
    )

    # --------- Progressive Publisher（P2） ---------
    # 灰度发布记录持久化目录
    publication_records_dir: str = field(
        default_factory=lambda: _path(
            "LNN_DREAM_PUB_DIR",
            os.path.join("output", "dreaming", "publications"),
        )
    )
    # 默认初始灰度阶段（shadow / canary / rolling_10 / rolling_50 / full）
    # 生产环境应保持 shadow，仅在验证通过后通过 promote晋级
    default_initial_stage: str = field(
        default_factory=lambda: _env("LNN_DREAM_INITIAL_STAGE", "shadow")
    )
    # 晋级阈值：准确率达到此值才允许晋级
    promote_accuracy_threshold: float = field(
        default_factory=lambda: _float_env("LNN_DREAM_PROMOTE_ACC", 0.75)
    )
    # 降级阈值：准确率低于此值触发降级
    demote_accuracy_threshold: float = field(
        default_factory=lambda: _float_env("LNN_DREAM_DEMOTE_ACC", 0.45)
    )

    # --------- Effectiveness Metrics（P2） ---------
    # 度量样本持久化目录
    metrics_samples_dir: str = field(
        default_factory=lambda: _path(
            "LNN_DREAM_METRICS_DIR",
            os.path.join("output", "dreaming", "metrics_samples"),
        )
    )
    # 度量窗口天数（滚动窗口）
    metrics_window_days: int = field(
        default_factory=lambda: _int_env("LNN_DREAM_METRICS_WINDOW", 7)
    )
    # 最小样本数（低于此值标记 insufficient_data，不阻断发布但置信度低）
    metrics_min_sample_size: int = field(
        default_factory=lambda: _int_env("LNN_DREAM_MIN_SAMPLES", 10)
    )

    # --------- Rollback Manager（P2） ---------
    # 回滚历史持久化目录
    rollback_history_dir: str = field(
        default_factory=lambda: _path(
            "LNN_DREAM_ROLLBACK_DIR",
            os.path.join("output", "dreaming", "rollback_history"),
        )
    )
    # 冷却期小时数：回滚后规则进入冷却，期间不可重新发布
    rollback_cooldown_hours: int = field(
        default_factory=lambda: _int_env("LNN_DREAM_COOLDOWN_HOURS", 24)
    )
    # 连续异常次数阈值：连续 N 次指标低于阈值触发回滚
    rollback_consecutive_anomaly_threshold: int = field(
        default_factory=lambda: _int_env("LNN_DREAM_CONSECUTIVE_ANOMALY", 3)
    )
    # 生产异常率阈值：超过此值立即回滚
    rollback_production_error_rate_threshold: float = field(
        default_factory=lambda: _float_env("LNN_DREAM_PROD_ERROR_RATE", 0.25)
    )

    # --------- Closed Loop（P2，DempsterShaferFusion + TaskRouter） ---------
    # 闭环状态持久化目录
    closed_loop_state_dir: str = field(
        default_factory=lambda: _path(
            "LNN_DREAM_CLOSED_LOOP_DIR",
            os.path.join("output", "dreaming", "closed_loop"),
        )
    )
    # 闭环决策置信度阈值（fused_confidence 高于此值才允许 promote）
    closed_loop_promote_confidence: float = field(
        default_factory=lambda: _float_env("LNN_DREAM_CL_PROMOTE_CONF", 0.75)
    )
    # 闭环决策置信度阈值（fused_confidence 低于此值触发 demote）
    closed_loop_demote_confidence: float = field(
        default_factory=lambda: _float_env("LNN_DREAM_CL_DEMOTE_CONF", 0.45)
    )
    # 闭环决策最小样本数（低于此值返回 keep，不触发 promote/demote）
    closed_loop_min_samples_for_decision: int = field(
        default_factory=lambda: _int_env("LNN_DREAM_CL_MIN_SAMPLES", 5)
    )
    # 规则效果滚动窗口大小（每条规则最多保留的 outcome 样本数）
    rule_outcome_window_size: int = field(
        default_factory=lambda: _int_env("LNN_DREAM_RULE_WINDOW", 64)
    )

    # --------- 硬约束（__post_init__ 强制，不可被环境变量关闭） ---------
    # CAM 二次校验强制（始终 True，不被反思规则绕过）
    cam_validation_required: bool = field(
        default_factory=lambda: _bool_env("LNN_DREAM_CAM_VALIDATION_REQUIRED", True)
    )
    # SUCCEEDED 任务禁删（始终 False，避免追溯链断裂）
    allow_delete_succeeded: bool = field(
        default_factory=lambda: _bool_env("LNN_DREAM_ALLOW_DELETE_SUCCEEDED", False)
    )
    # HRC52 pending_calibration 置信度惩罚系数（0-1，规则触发 HRC52 时强制乘以此值）
    hrc52_pending_calibration_penalty: float = field(
        default_factory=lambda: _float_env("LNN_DREAM_HRC52_PENALTY", 0.5)
    )
    # K_s → cutting_force_coeff 直接传递（始终 True，不二次拟合）
    k_s_direct_passthrough: bool = field(
        default_factory=lambda: _bool_env("LNN_DREAM_KS_DIRECT_PASSTHROUGH", True)
    )

    def __post_init__(self) -> None:
        """启动时校验配置合法性，强制项目记忆硬约束。"""
        # 校验 cron 表达式非空
        if not self.dream_cron_expression.strip():
            logger.warning(
                "LNN_DREAM_CRON 为空，使用默认值 '0 2 * * *'（每天凌晨 02:00）。"
            )
            self.dream_cron_expression = "0 2 * * *"

        # 校验灰度阶段合法性
        valid_stages = {
            "shadow",
            "canary",
            "rolling_10",
            "rolling_50",
            "full",
        }
        if self.default_initial_stage not in valid_stages:
            logger.warning(
                "Invalid LNN_DREAM_INITIAL_STAGE='%s', expected one of %s. "
                "Falling back to 'shadow'.",
                self.default_initial_stage,
                sorted(valid_stages),
            )
            self.default_initial_stage = "shadow"

        # 校验阈值范围
        if not 0.0 <= self.promote_accuracy_threshold <= 1.0:
            logger.warning(
                "LNN_DREAM_PROMOTE_ACC=%s 超出 [0,1] 范围，重置为 0.75。",
                self.promote_accuracy_threshold,
            )
            self.promote_accuracy_threshold = 0.75

        if not 0.0 <= self.demote_accuracy_threshold <= 1.0:
            logger.warning(
                "LNN_DREAM_DEMOTE_ACC=%s 超出 [0,1] 范围，重置为 0.45。",
                self.demote_accuracy_threshold,
            )
            self.demote_accuracy_threshold = 0.45

        if self.demote_accuracy_threshold >= self.promote_accuracy_threshold:
            logger.warning(
                "LNN_DREAM_DEMOTE_ACC=%s >= PROMOTE_ACC=%s，"
                "会导致规则在 promote 与 demote 之间震荡，"
                "强制调整 demote 到 promote 的 60%%。",
                self.demote_accuracy_threshold,
                self.promote_accuracy_threshold,
            )
            self.demote_accuracy_threshold = (
                self.promote_accuracy_threshold * 0.6
            )

        # 校验闭环置信度阈值
        if not 0.0 <= self.closed_loop_promote_confidence <= 1.0:
            logger.warning(
                "LNN_DREAM_CL_PROMOTE_CONF=%s 超出 [0,1] 范围，重置为 0.75。",
                self.closed_loop_promote_confidence,
            )
            self.closed_loop_promote_confidence = 0.75

        if not 0.0 <= self.closed_loop_demote_confidence <= 1.0:
            logger.warning(
                "LNN_DREAM_CL_DEMOTE_CONF=%s 超出 [0,1] 范围，重置为 0.45。",
                self.closed_loop_demote_confidence,
            )
            self.closed_loop_demote_confidence = 0.45

        # 校验 HRC52 惩罚系数
        if not 0.0 < self.hrc52_pending_calibration_penalty <= 1.0:
            logger.warning(
                "LNN_DREAM_HRC52_PENALTY=%s 超出 (0,1] 范围，"
                "HRC52 pending_calibration 必须强制降低置信度，重置为 0.5。",
                self.hrc52_pending_calibration_penalty,
            )
            self.hrc52_pending_calibration_penalty = 0.5

        # 校验窗口大小
        if self.rule_outcome_window_size < 10:
            logger.warning(
                "LNN_DREAM_RULE_WINDOW=%s 太小（<10），"
                "样本不足以支撑 DS 融合，重置为 64。",
                self.rule_outcome_window_size,
            )
            self.rule_outcome_window_size = 64

        if self.min_sessions_for_dream < 1:
            logger.warning(
                "LNN_DREAM_MIN_SESSIONS=%s 无效（<1），重置为 5。",
                self.min_sessions_for_dream,
            )
            self.min_sessions_for_dream = 5

        # ========== 项目记忆硬约束（不可被环境变量绕过） ==========

        # 硬约束 1：CAM 二次校验始终 True（不被反思规则绕过）
        if not self.cam_validation_required:
            logger.warning(
                "LNN_DREAM_CAM_VALIDATION_REQUIRED=false 违反项目记忆硬约束"
                "（反思生成的规则不得绕过 CAM 二次校验），强制重置为 true。"
            )
            self.cam_validation_required = True

        # 硬约束 2：SUCCEEDED 任务禁删（始终 False，避免追溯链断裂）
        if self.allow_delete_succeeded:
            logger.warning(
                "LNN_DREAM_ALLOW_DELETE_SUCCEEDED=true 违反项目记忆硬约束"
                "（SUCCEEDED 任务可能被后续阶段引用，删除会破坏追溯链），"
                "强制重置为 false。"
            )
            self.allow_delete_succeeded = False

        # 硬约束 3：K_s → cutting_force_coeff 直接传递（始终 True，不二次拟合）
        if not self.k_s_direct_passthrough:
            logger.warning(
                "LNN_DREAM_KS_DIRECT_PASSTHROUGH=false 违反项目记忆硬约束"
                "（K_s → cutting_force_coeff 必须直接传递，不二次拟合），"
                "强制重置为 true。"
            )
            self.k_s_direct_passthrough = True


# =============================================================================
# Top-Level Application Configuration
# =============================================================================


@dataclass
class AppConfig:
    app_name: str = field(default_factory=lambda: _env("APP_NAME", "灵境制造"))
    app_version: str = field(default_factory=lambda: _env("APP_VERSION", "2.6.0"))
    offline_mode: bool = field(
        default_factory=lambda: _bool_env("OFFLINE_MODE", False)
    )
    environment: EnvironmentConfig = field(default_factory=EnvironmentConfig)
    server: ServerConfig = field(default_factory=ServerConfig)
    ai: AIConfig = field(default_factory=AIConfig)
    model_router: ModelRouterSettings = field(default_factory=ModelRouterSettings)
    finetune: FineTuneSettings = field(default_factory=FineTuneSettings)
    simulation: SimulationConfig = field(default_factory=SimulationConfig)
    hardware: HardwareTierConfig = field(default_factory=HardwareTierConfig)
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
    mes: MESConfig = field(default_factory=MESConfig)
    sharp: SharpConfig = field(default_factory=SharpConfig)
    image_to_3d: ImageTo3DConfig = field(default_factory=ImageTo3DConfig)
    feature_extraction: FeatureExtractionConfig = field(
        default_factory=FeatureExtractionConfig
    )
    parametric_geometry: ParametricGeometryConfig = field(
        default_factory=ParametricGeometryConfig
    )
    cutting_parameters: CuttingParametersConfig = field(
        default_factory=CuttingParametersConfig
    )
    chatter_prediction: ChatterPredictionConfig = field(
        default_factory=ChatterPredictionConfig
    )
    gcode_generation: GCodeGenerationConfig = field(
        default_factory=GCodeGenerationConfig
    )
    cam_validation: CamValidationConfig = field(
        default_factory=CamValidationConfig
    )
    dreaming: DreamingConfig = field(default_factory=DreamingConfig)


config = AppConfig()
