"""FastAPI application entry point."""

from __future__ import annotations

import asyncio
import ipaddress
import logging
import logging.config
import os
import signal
import sys
import time
from pathlib import Path

import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response, JSONResponse

from app.api.v1.sse import sse_manager
from app.middleware.cors_config import (
    cors_settings,
    enforce_startup_security,
    validate_cors_config,
    CorsConfigError,
)
from app.core.exception_handlers import register_exception_handlers
from app.core.request_id import RequestIdMiddleware, get_request_id
from app.core.logging_config import configure_logging
from app.utils.utils import get_metrics_collector
from app.sidecar.sidecar_lifecycle import (
    IdleAutoShutdownMiddleware,
    GracefulShutdownHandler,
)
from app.utils.ring_buffer import get_ring_log_buffer, BUFFER_TYPES
from app.auth.security_headers_asgi import SecurityHeadersMiddleware
from app.auth.unified_auth import UnifiedAuthMiddleware
from app.middleware.rate_limiter import limiter, rate_limit_handler
from slowapi.errors import RateLimitExceeded
from app.config import config
from app.version import get_version_info, VERSION as PY_VERSION
from app.api.v1 import (
    lnn_uncertain,
    wear_prediction,
    user_sovereignty,
    agent_gateway,
    jobs,
    health,
    auth,
    users,
    skills,
    cost_budget,
    governance,
    goal_alignment,
    heartbeat,
    task_checkout,
    flywheel,
    template_ab_testing_routes as template_ab,
    template_branching_routes as template_branches,
    template_evolution_routes as template_evolution,
    template_update_routes as template_updates,
    pattern_engine_routes as pattern_engine,
    knowledge_graph as knowledge_graph_routes,
    status as status_routes,
    dxf_pipeline as dxf_pipeline_routes,
    materials,
    equipment,
    quality,
    production,
    process_routes,
    documents,
    collision_check,
    tools,
    dnc as dnc_routes,
    plugins,
    template_market,
    llm_providers,
    sharp as sharp_routes,
    dynamic_adjustment as dynamic_adjustment_routes,
    signal_fusion_kb as signal_fusion_kb_routes,
    agent_state as agent_state_routes,  # P0-8 修复：补齐 agent_state 路由
    workflows,  # ADR-005 阶段 1：DAG 工作流编排 API
    datasets,  # ADR-005 阶段 2：数据集 / 版本 / 血缘 API
    snapshots,  # ADR-005 阶段 2：实验快照 / 一键复现 API
    workflow_templates,  # ADR-010 阶段 6 p6-1：工作流模板市场 API
    project_sync,  # ADR-011 阶段 6 p6-2：项目级 Git 同步 API
    resource_cards,  # ADR-012 阶段 6 p6-3：资源卡片 API
    project_packages,  # ADR-015 阶段 6 p6-4：项目导入导出 API
    explainability,  # ADR-016 阶段 7 p7：可解释性可视化 API
    world_model,  # ADR-017 阶段 8 p8：世界模型 API
    rl_agent,  # ADR-017 阶段 8 p8：RL Agent API
)
from app.integrations.mes import api as mes_api

# torch 相关模块：桌面版可能没有 torch，条件导入
_TORCH_AVAILABLE = False
try:
    from app.api.v1 import lnn
    _TORCH_AVAILABLE = True
except ImportError as e:
    # P2-5-1 修复：顶部已 import logging，移除分支内重复导入
    logging.warning(
        f"torch 模块导入失败: {e}。"
        "影响: LNN 神经网络相关功能将不可用。"
        "修复: 请安装 PyTorch，运行 'pip install torch torchvision torchaudio'"
    )
from app.rag import routes as rag_routes
from app.ai.process_understanding import routes as process_understanding_routes

# ollama 相关模块：桌面版可能没有 ollama，条件导入
# [U-P0-2] 防复发：尊重 config.hardware.skip_ollama 标志
#   - 轻量模式 / minimal 档位下显式跳过 Ollama 加载，降低内存占用
#   - 避免 Ollama 启动探测失败导致应用卡死（老旧硬件常见问题）
_OLLAMA_AVAILABLE = False
if config.hardware.skip_ollama:
    # P2-5-1 修复：顶部已 import logging，移除分支内重复导入
    logging.info(
        "Ollama 模块已跳过加载（LNN_SKIP_OLLAMA=true 或硬件档位=minimal）。"
        "轻量模式下将仅使用规则引擎 + 云端 API。"
        "如需启用本地 LLM，请设置 LNN_SKIP_OLLAMA=false 并提高硬件档位。"
    )
else:
    try:
        from app.ai import ollama_routes
        _OLLAMA_AVAILABLE = True
    except ImportError as e:
        # P2-5-1 修复：顶部已 import logging，移除分支内重复导入
        logging.warning(
            f"ollama 模块导入失败: {e}。"
            "影响: Ollama AI 模型集成功能将不可用。"
            "修复: 请安装 ollama Python 包，运行 'pip install ollama'"
        )

from app.simulation import api as simulation_api
from app.simulation.chatter import api as chatter_api
from app.simulation.cutting_force import api as cutting_force_api
from app.projects import project_api as project_routes
from app.step_import import api as step_import_api
from app.rules import router as rules_router

# image_to_3d 拍照重建模块：依赖 COLMAP/OpenMVS 外部二进制 + trimesh/Pillow 可选依赖。
# 桌面版可能未安装外部二进制或可选 Python 依赖，条件导入避免启动失败。
# ADR-006 阶段 1：手机多角度拍照 → COLMAP SfM → OpenMVS 稠密化 → 标定块尺度归一化 mesh
_IMAGE_TO_3D_AVAILABLE = False
try:
    from app.api.v1.image_to_3d import routes as image_to_3d_routes
    _IMAGE_TO_3D_AVAILABLE = True
except ImportError as e:
    logging.warning(
        f"image_to_3d 模块导入失败: {e}。"
        "影响: 拍照重建功能（COLMAP+OpenMVS / Hunyuan3D）将不可用。"
        "修复: 请安装 COLMAP 与 OpenMVS 二进制，并运行 "
        "'pip install trimesh Pillow' 启用尺度归一化与图像处理。"
    )

# feature_extraction 几何特征辅助提取模块：依赖 numpy（必需）+ sklearn/pyransac3d/trimesh（可选）。
# ADR-007 阶段 2：mesh → RANSAC 平面/圆柱/孔检测 → 工程师审核 → 导出已确认特征集 JSON
# 设计原则（项目记忆硬约束）：mesh → 参数化 CAD 自动转换工业上未解决，
#   本模块输出「算法建议特征」，必须经工程师逐条审核后才允许进入阶段 3。
_FEATURE_EXTRACTION_AVAILABLE = False
try:
    from app.api.v1.feature_extraction import routes as feature_extraction_routes
    _FEATURE_EXTRACTION_AVAILABLE = True
except ImportError as e:
    logging.warning(
        f"feature_extraction 模块导入失败: {e}。"
        "影响: 几何特征辅助提取功能（平面/圆柱/孔检测 + 工程师审核）将不可用。"
        "修复: 请确认 numpy 已安装；如需更精确的圆柱拟合，可运行 "
        "'pip install scikit-learn pyransac3d trimesh'。"
    )

# parametric_geometry 参数化几何输出模块：依赖 pythonOCC（首选）/ FreeCAD API（备选）/ 简易模板（兜底）。
# ADR-008 阶段 3：阶段 2 confirmed_features.json → B-rep → 装配 → STEP → 工程师两轮审核 → 最终 STEP
# 设计原则（项目记忆硬约束）：mesh → 参数化 CAD 自动转换工业上未解决，本模块输出「算法建议 STEP」，
#   工程师必须两轮审核（STEP_GENERATED + finalize）后才允许下载最终 STEP。
#   最终 STEP 必须经 CAM 软件（NX/PowerMill/PyCAM）二次校验后才允许上机床。
#   本系统定位为「工程师助手」，非「全自动生产线」。
_PARAMETRIC_GEOMETRY_AVAILABLE = False
try:
    from app.api.v1.parametric_geometry import routes as parametric_geometry_routes
    _PARAMETRIC_GEOMETRY_AVAILABLE = True
except ImportError as e:
    logging.warning(
        f"parametric_geometry 模块导入失败: {e}。"
        "影响: 参数化几何输出功能（特征→B-rep→装配→STEP）将不可用。"
        "修复: 该模块已实现三级降级（pythonOCC → FreeCAD API → 简易模板），"
        "默认无依赖也能用简易模板生成基础 STEP。"
        "若需工业级 STEP 表达，可运行 'pip install pyoccl' 或安装 FreeCAD。"
    )

# cutting_parameters 切削参数推荐模块：依赖材料数据库 + 推荐引擎（纯 Python，无外部重依赖）。
# ADR-009 阶段 4：阶段 3 STEP + 阶段 2 confirmed_features.json + material_id
#   → MaterialResolver 查询材料基线 → CuttingParamRecommender 推荐切削参数
#   → 工程师审核（confirmed / rejected / edited）→ 导出 ChatterParams JSON（供阶段 5 颤振预测）
# 设计原则（项目记忆硬约束）：
# - 本模块是「工程师助手」，非「全自动切削参数生成器」
# - 推荐参数必须经工程师逐条审核后才允许导出 ChatterParams
# - ChatterParams 仅供阶段 5 LTC 颤振预测参考，实际加工必须经 CAM 软件二次校验
# - SUCCEEDED 状态禁止删除（阶段 5 颤振预测可能已引用其 ChatterParams）
# - HRC52 数据待自采校准，K_s 标记为 pending_calibration（影响阶段 5 颤振预测精度）
_CUTTING_PARAMETERS_AVAILABLE = False
try:
    from app.api.v1.cutting_parameters import routes as cutting_parameters_routes
    _CUTTING_PARAMETERS_AVAILABLE = True
except ImportError as e:
        logging.warning(
            f"cutting_parameters 模块导入失败: {e}。"
            "影响: 切削参数推荐功能（材料→切削参数→ChatterParams）将不可用，"
            "阶段 5 颤振预测将无法获取输入参数。"
            "修复: 该模块为纯 Python 实现，无外部重依赖，"
            "请检查 app/cutting_parameters/ 与 app/api/v1/cutting_parameters/ 是否完整。"
        )

# chatter_prediction 颤振预测接入 LTC 模块：依赖阶段 4 输出的 ChatterParams + stability.py 解析法（默认）。
# LTC 神经网络路径为实验性，仅在 chatter_model.pt 存在时启用；缺失时自动回退到 Tlusty 解析法。
# ADR-013 阶段 5：阶段 4 ChatterParams → 双路径预测（解析法 / LTC 神经网络 / 兜底默认值）
#   → 工程师单轮审核（PENDING → RUNNING → PREDICTED → REVIEWED → SUCCEEDED）→ 导出 ChatterReport JSON（供阶段 6 G 代码生成）
# 设计原则（项目记忆硬约束）：
# - 本模块是「工程师助手」，非「全自动颤振预测器」
# - HRC52 数据待自采校准，预测置信度强制降至 PENDING_CALIBRATION_CONFIDENCE=0.5
# - K_s → cutting_force_coeff 直接传递，不二次拟合
# - SUCCEEDED 状态禁止删除（阶段 6 G 代码生成可能已引用其 ChatterReport）
# - cam_validation_required 始终 True，ChatterReport 仅供阶段 6 G 代码生成参考，实际加工必须经 CAM 软件二次校验
# - MC dropout 模式切换使用锁保护；推理路径禁止 fit_transform
_CHATTER_PREDICTION_AVAILABLE = False
try:
    from app.api.v1.chatter_prediction import routes as chatter_prediction_routes
    _CHATTER_PREDICTION_AVAILABLE = True
except ImportError as e:
    logging.warning(
        f"chatter_prediction 模块导入失败: {e}。"
        "影响: 颤振预测功能（ChatterParams→双路径预测→ChatterReport）将不可用，"
        "阶段 6 G 代码生成将无法获取颤振稳定性预测。"
        "修复: 请检查 app/chatter_prediction/ 与 app/api/v1/chatter_prediction/ 是否完整。"
    )

# gcode_generation G 代码生成接入模块：依赖阶段 5 输出的 ChatterReport + 阶段 3 输出的 OperationPlan
# → GeneratorAdapter 封装现有 GCodeGenerator（212 测试覆盖）→ 工程师单轮审核 → 导出 G 代码 + 审核记录 JSON
# ADR-014 阶段 6：阶段 5 ChatterReport + 阶段 3 OperationPlan → GCodeGenerator → 审核状态机
#   PENDING → RUNNING → GENERATED → REVIEWED → SUCCEEDED（单轮审核）
# 设计原则（项目记忆硬约束）：
# - 本模块是「工程师助手」，非「全自动 G 代码生成器」
# - 复用现有 app.postprocessor + GCodeGenerator（212 测试覆盖），不重写
# - stable == False 的特征禁止生成 G 代码（强制回阶段 5 降低切深）
# - SUCCEEDED 状态禁止删除（阶段 7 CAM 校验可能已引用 G 代码产物）
# - allow_delete_succeeded 始终 False（不可由环境变量开启）
# - cam_validation_required 始终 True，G 代码必须经 CAM 软件（NX/PowerMill/PyCAM）二次校验后方可上机
# - 系统绝不直接接口 CNC 控制器
_GCODE_GENERATION_AVAILABLE = False
try:
    from app.api.v1.gcode_generation import routes as gcode_generation_routes
    _GCODE_GENERATION_AVAILABLE = True
except ImportError as e:
    logging.warning(
        f"gcode_generation 模块导入失败: {e}。"
        "影响: G 代码生成功能（ChatterReport+OperationPlan→G 代码→审核→CAM 校验输入）将不可用，"
        "阶段 7 CAM 校验将无法获取 G 代码产物。"
        "修复: 请检查 app/gcode_generation/ 与 app/api/v1/gcode_generation/ 是否完整。"
    )

# === CAM 校验模块（阶段 7，ADR-018）===
# 数据流：阶段 6 G 代码 + report.json
#   → GCodeLoader 加载 G 代码文本 + feature_results
#   → InternalValidator 复用 CollisionDetector 执行内部预校验
#   → CamAdapter 调用 CAM 软件二次校验（5 后端策略）
#   → 工程师审核每个特征校验结果 → confirm_task → SUCCEEDED
#   → 导出 cam_report.json + internal_report.json（链路最终产物）
#
# 工业硬约束（项目记忆）：
# - 系统定位「工程师助手」，非「全自动 CAM 仿真器」
# - 系统绝不直接接口 CNC 控制器，阶段 7 产物终止于「CAM 校验报告 JSON」
# - cam_validation_required 始终 True（不可关闭）
# - SUCCEEDED 状态禁止删除（cam_report.json 是链路最终产物，需保留供审计追溯）
# - allow_delete_succeeded 强制 False（不可由环境变量开启）
# - HRC52 pending_calibration 由阶段 5 标注，阶段 7 仅继承
_CAM_VALIDATION_AVAILABLE = False
try:
    from app.api.v1.cam_validation import routes as cam_validation_routes
    _CAM_VALIDATION_AVAILABLE = True
except ImportError as e:
    logging.warning(
        f"cam_validation 模块导入失败: {e}。"
        "影响: CAM 校验功能（G 代码→内部预校验→CAM 软件二次校验→审核→cam_report.json）将不可用，"
        "阶段 7 链路终点（CAM 校验报告）将无法生成。"
        "修复: 请检查 app/cam_validation/ 与 app/api/v1/cam_validation/ 是否完整。"
    )

# P2-5-2 修复：提取日志配置魔法数字为命名常量，便于统一管理
LOG_MAX_BYTES: int = 50 * 1024 * 1024  # 50 MB
LOG_RETENTION_DAYS: int = 30
# Alembic 迁移日志截断长度（防止 stdout/stderr 过长污染日志）
ALEMBIC_STDOUT_LOG_LIMIT: int = 200
ALEMBIC_STDERR_LOG_LIMIT: int = 500
# 优雅关闭延迟（秒）：等待 HTTP 响应发送完成后再触发 shutdown
SHUTDOWN_DELAY_SECONDS: float = 0.2

_log_root = os.environ.get("LNN_LOG_DIR", str(Path(config.paths.gstack_dir).parent / "logs"))
configure_logging(
    level=logging.INFO,
    log_root=_log_root,
    module_name="python",
    max_bytes=LOG_MAX_BYTES,
    retention_days=LOG_RETENTION_DAYS,
)
logger = logging.getLogger(__name__)

metrics = get_metrics_collector()
ring_log = get_ring_log_buffer(base_dir=config.paths.gstack_dir)

auth_enabled = config.security.auth_enabled
permission_enforced = config.security.permission_enforced

# P0-11 修复：state_file 路径三方一致。
# 此前 STATE_FILE_PATH 取自 gstack_dir/sidecar.json，但 Rust 端（sidecar.rs wait_ready）
# 读取的是 LNN_LOG_DIR/sidecar.json，sidecar_main.py 默认也是 LNN_LOG_DIR/sidecar.json。
# 三方不一致导致 Rust 端永远读不到 Python 写入的 state 文件，无法快速感知 failed/stopped 状态。
# 现统一为：优先使用 LNN_LOG_DIR/sidecar.json；若 LNN_LOG_DIR 未设置则回退到 gstack_dir/sidecar.json
# （保持桌面开发模式兼容）。
if os.environ.get("LNN_LOG_DIR"):
    STATE_FILE_PATH = str(Path(os.environ["LNN_LOG_DIR"]) / "sidecar.json")
else:
    STATE_FILE_PATH = str(Path(config.paths.gstack_dir) / "sidecar.json")


def get_state_file_path() -> str:
    return STATE_FILE_PATH


# P2-1 修复：生产环境关闭 docs_url/redoc_url/openapi_url，避免接口暴露
# 通过 LNN_ENVIRONMENT / ENVIRONMENT 控制：production 时关闭，其他环境开启
_LNN_ENV = os.environ.get("LNN_ENVIRONMENT", os.environ.get("ENVIRONMENT", "development")).lower()
_DOCS_DISABLED = _LNN_ENV == "production"

app = FastAPI(
    title="灵境制造 API",
    version="2.5.0",
    description="Lingjing Manufacturing - NC Machining AI Platform",
    docs_url=None if _DOCS_DISABLED else "/api/docs",
    redoc_url=None if _DOCS_DISABLED else "/api/redoc",
    openapi_url=None if _DOCS_DISABLED else "/api/openapi.json",
)

shutdown_handler = GracefulShutdownHandler(app=app, state_file_path=STATE_FILE_PATH)

# Ensure state file directory exists
Path(STATE_FILE_PATH).parent.mkdir(parents=True, exist_ok=True)

# IdleAutoShutdownMiddleware configuration
# P1-1 修复：通过 LNN_IDLE_AUTO_SHUTDOWN 环境变量控制是否启用空闲自动关机。
# - 桌面 sidecar 模式（sidecar_main.py 启动）：默认禁用（"false"），用户随时回来使用
# - Docker / 独立服务模式：默认启用（"true"），节省云端资源
# 默认值：未设置环境变量时启用（保持向后兼容）
_IDLE_AUTO_SHUTDOWN_ENABLED = os.environ.get("LNN_IDLE_AUTO_SHUTDOWN", "true").lower() == "true"
IDLE_TIMEOUT_SECONDS = 1800


async def _run_alembic_upgrade() -> None:
    """P0-3 修复：执行 alembic upgrade head，保证 schema 版本一致。

    设计：
    - 失败仅告警不阻断启动（init_db 已通过 create_all 保证基础表存在）
    - 仅在 LNN_ALEMBIC_ENABLED != "false" 时执行（默认开启）
    - 在子线程中同步执行，避免阻塞事件循环
    """
    import subprocess

    if os.environ.get("LNN_ALEMBIC_ENABLED", "true").lower() == "false":
        logger.info("[startup] Alembic migration skipped (LNN_ALEMBIC_ENABLED=false)")
        return

    python_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    try:
        proc = await asyncio.create_subprocess_exec(
            sys.executable, "-m", "alembic", "upgrade", "head",
            cwd=python_dir,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode == 0:
            logger.info(
                "[startup] Alembic upgrade head done: %s",
                stdout.decode("utf-8", "replace").strip()[:ALEMBIC_STDOUT_LOG_LIMIT],
            )
        else:
            logger.warning(
                "[startup] Alembic upgrade returned non-zero (rc=%s): %s",
                proc.returncode,
                stderr.decode("utf-8", "replace").strip()[:ALEMBIC_STDERR_LOG_LIMIT],
            )
    except FileNotFoundError:
        logger.warning("[startup] alembic not installed, skip migration")
    except (OSError, subprocess.SubprocessError) as e:
        logger.warning("[startup] Alembic migration failed (non-fatal): %s", e, exc_info=True)


async def _verify_critical_dependencies() -> None:
    """P1-15 修复：启动后验证关键依赖（DB / Redis）连通性。

    设计：
    - DB 不可达：warning（init_db 已通过 create_all 建表，但连接可能因
      配置错误或网络分区失败；运行时查询会 500，需提前告警）
    - Redis 不可达：debug（Redis 为可选依赖，未配置时返回 None 属正常）
    - 任一失败仅记录日志，不阻断启动（保持与现有容错策略一致）
    """
    # DB 连通性
    try:
        from app.database.connection import check_db_health
        db_status = await check_db_health()
        if db_status.get("status") == "unhealthy":
            logger.warning(
                "[startup] DB 连通性自检失败: %s（运行时查询可能 500）",
                db_status.get("error", "unknown"),
            )
        else:
            logger.info(
                "[startup] DB 连通性自检通过: status=%s",
                db_status.get("status"),
            )
    except Exception as e:  # noqa: BLE001
        logger.warning("[startup] DB 连通性自检异常: %s", e, exc_info=True)

    # Redis 连通性（可选依赖）
    try:
        from app.services.redis_client import check_redis_health
        redis_status = await check_redis_health()
        if redis_status.get("status") == "unhealthy":
            logger.warning(
                "[startup] Redis 连通性自检失败: %s（任务进度/取消标志缓存不可用）",
                redis_status.get("error", "unknown"),
            )
        else:
            logger.info(
                "[startup] Redis 连通性自检通过: status=%s",
                redis_status.get("status"),
            )
    except Exception as e:  # noqa: BLE001
        logger.debug("[startup] Redis 连通性自检跳过: %s", e, exc_info=True)


@app.on_event("startup")
async def startup_event():
    # CORS 安全配置验证：通配符 * 与 allow_credentials=True 同时使用属于
    # 严重安全风险，必须在进程绑定端口之前完成强制校验。校验失败时
    # 输出 ERROR 日志并以非零退出码终止启动流程，绝不允许带病上线。
    try:
        enforce_startup_security()
        logger.info(
            "CORS 配置安全验证通过: allow_origins=%s, env=%s",
            cors_settings.get_origins(),
            cors_settings._env,
        )
    except CorsConfigError as e:
        # CorsConfigError 自身已经写过 ERROR 日志（包含中文告警），这里
        # 再补一条更具体的启动上下文，然后强制以非零退出码终止进程。
        logger.error("CORS 启动安全校验失败，进程即将退出: %s", e)
        # 在 FastAPI 启动事件中 raise 会让 uvicorn 报告并以非零退出码
        # 终止；这里额外 sys.exit 用来保证独立运行（python -m app.main）
        # 时也立即退出。
        sys.exit(1)

    shutdown_handler.setup()
    await ring_log.start()

    # 权限检查机制状态检查
    if not config.security.permission_enforced:
        logger.warning("权限检查机制已被关闭，这可能导致安全风险")

    from app.database.models import init_db
    from app.tasks.task_system import AsyncTaskManager
    from app.services.redis_client import get_redis

    # --- Step 1: 确保默认 SQLite 数据库目录存在 ---
    # DB_URL 环境变量不再由 main.py 设置，统一由 config.database.db_url 管理
    _db_url = config.database.db_url
    if _db_url.startswith("sqlite"):
        _db_file = _db_url.split("///", 1)[-1]
        Path(_db_file).parent.mkdir(parents=True, exist_ok=True)

    # --- Step 2: Initialize async DB tables + seed RBAC ---
    # (init_db uses Base.metadata.create_all, which handles fresh DB creation)
    logger.info("[startup] Calling init_db() ...")
    await init_db()
    logger.info("[startup] init_db() done")

    # --- Step 2b: Alembic 迁移（失败不阻断启动，仅告警）---
    # P0-3 修复：在 init_db 后执行 alembic upgrade head，保证 schema 版本一致
    await _run_alembic_upgrade()

    # --- Step 3: Redis (optional, returns None if not configured) ---
    logger.info("[startup] Calling get_redis() ...")
    await get_redis()
    logger.info("[startup] get_redis() done")

    # --- Step 3b: 关键依赖连通性自检（P1-15 修复）---
    # 启动后立即验证 DB / Redis 可达性，失败仅 warning 不阻断启动
    # （保持与 Alembic 迁移相同的容错策略：桌面开发模式可能未配置全部依赖）。
    # 避免应用以"僵尸态"启动——进程存活但所有请求因依赖不可达而 500。
    await _verify_critical_dependencies()

    # --- Step 4: Task manager ---
    logger.info("[startup] Initializing AsyncTaskManager ...")
    task_mgr = AsyncTaskManager()
    await task_mgr.initialize(max_concurrent=config.tasks.max_concurrent)
    logger.info("[startup] AsyncTaskManager initialized")

    ring_log.append(
        "system_event",
        level="INFO",
        source="startup",
        message="Application started",
        data={"version": PY_VERSION},
    )
    logger.info("Graceful shutdown handler and signal processors registered")
    logger.info("Idle auto-shutdown middleware registered (timeout: %ds)", IDLE_TIMEOUT_SECONDS)
    logger.info("State file path: %s", STATE_FILE_PATH)


@app.on_event("shutdown")
async def shutdown_event():
    ring_log.append(
        "system_event",
        level="INFO",
        source="shutdown",
        message="Application shutting down",
    )
    await ring_log.stop()
    await sse_manager.shutdown()

    from app.tasks.task_system import AsyncTaskManager
    from app.database.connection import close_db
    from app.services.redis_client import close_redis
    from app.ai.llm_client import close_shared_http_client
    from app.core.logging_config import shutdown_logging

    task_mgr = AsyncTaskManager()
    await task_mgr.shutdown()
    await close_redis()
    await close_shared_http_client()
    await close_db()

    # 显式关闭 ChromaDB PersistentClient，释放底层 SQLite/DuckDB 资源，
    # 避免 Windows 文件句柄锁定导致下次启动失败。
    try:
        from app.rag.vector_store import get_vector_store
        get_vector_store().close()
    except Exception as e:  # noqa: BLE001
        logger.warning("VectorStore close failed during shutdown: %s", e)

    shutdown_logging()

    logger.info("FastAPI shutdown event completed")


# P2-3 修复：中间件执行顺序（外→内）与注册顺序（内→外）对齐。
# Starlette 中 add_middleware 后注册的位于外层（最先执行），因此
# 注册顺序必须与期望的执行顺序相反。
#
# 期望执行顺序（外→内）：
#   1. RequestIdMiddleware        -> 生成 X-Request-ID，所有后续日志可关联
#   2. SecurityHeadersMiddleware  -> 纯 ASGI，添加安全响应头
#   3. CORSMiddleware              -> 处理预检 OPTIONS，必须早于 auth
#   4. MetricsMiddleware           -> 记录请求指标（BaseHTTPMiddleware）
#   5. UnifiedAuthMiddleware       -> 纯 ASGI，LNN+JWT+Agent 鉴权
#   6. IdleAutoShutdownMiddleware -> 空闲追踪（BaseHTTPMiddleware，最内层）
#
# 关键修复点：CORS 必须在 UnifiedAuth 外层，否则浏览器 OPTIONS 预检请求
# 会因缺少 Authorization 头被 auth 拦截返回 401，导致跨域前端无法工作。
# RequestId 在最外层确保所有中间件日志都可关联同一请求 ID。


class MetricsMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start = time.perf_counter()
        # P1-11 修复：下游异常也必须记录指标，否则最需要观测的错误请求
        # 会从指标中消失。同时指标记录自身异常不得吞没已生成的响应。
        status_code = 500
        response = None  # P1-11：预初始化，避免 except 路径中 finally 引用未定义变量
        try:
            response = await call_next(request)
            status_code = response.status_code
            return response
        except Exception:
            # 下游抛异常时仍记录 500 指标后重新抛出，保证错误请求可观测
            try:
                elapsed = time.perf_counter() - start
                metrics.record(request.url.path, elapsed, 500)
            except Exception:
                logger.warning(
                    "metrics.record failed for failed request %s",
                    request.url.path,
                    exc_info=True,
                )
            raise
        finally:
            # 仅在正常返回时记录（异常路径已在 except 中记录）
            if response is not None:
                try:
                    elapsed = time.perf_counter() - start
                    # P0-14/15 修复：传入 status_code 以便按状态码族分类计入
                    # http_requests_total{status="..."}，使 HighErrorRate 告警可正常工作
                    if status_code != 500:
                        metrics.record(request.url.path, elapsed, status_code)
                    ring_log.append(
                        "request",
                        level="INFO",
                        source=request.url.path,
                        message=f"{request.method} {request.url.path}",
                        data={
                            "method": request.method,
                            "path": request.url.path,
                            "status": status_code,
                            "elapsed_ms": round(elapsed * 1000, 3),
                        },
                    )
                except Exception:
                    logger.warning(
                        "MetricsMiddleware observability sidecar failed for %s",
                        request.url.path,
                        exc_info=True,
                    )


# 注册顺序（内→外，后注册先执行）：
#   最内层先注册，最外层最后注册

# 1. IdleAutoShutdownMiddleware（最内层，条件注册）
# P1-1 修复：桌面 sidecar 模式下默认禁用（LNN_IDLE_AUTO_SHUTDOWN=false）
if _IDLE_AUTO_SHUTDOWN_ENABLED:
    app.add_middleware(
        IdleAutoShutdownMiddleware,
        idle_timeout=IDLE_TIMEOUT_SECONDS,
        state_file_path=STATE_FILE_PATH,
    )
    logger.info(
        "IdleAutoShutdownMiddleware enabled (timeout=%ds, state_file=%s)",
        IDLE_TIMEOUT_SECONDS, STATE_FILE_PATH,
    )
else:
    logger.info("IdleAutoShutdownMiddleware disabled (LNN_IDLE_AUTO_SHUTDOWN=false)")

# 2. UnifiedAuthMiddleware（鉴权，CORS 内层）
jwt_auth_enabled = config.security.jwt_auth_enabled
app.add_middleware(
    UnifiedAuthMiddleware,
    lnn_auth_enabled=auth_enabled,
    lnn_permission_enforced=permission_enforced,
    jwt_auth_enabled=jwt_auth_enabled,
    agent_auth_enabled=config.security.agent_auth_enabled,
)

# 3. MetricsMiddleware
app.add_middleware(MetricsMiddleware)

# 4. CORSMiddleware（必须在 UnifiedAuth 外层，正确处理 OPTIONS 预检）
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_settings.get_origins(),
    allow_origin_regex=cors_settings.get_origin_regex(),
    allow_credentials=cors_settings.allow_credentials,
    allow_methods=cors_settings.get_methods(),
    allow_headers=cors_settings.get_headers(),
    expose_headers=cors_settings.get_expose_headers(),
    max_age=cors_settings.max_age,
)

# 5. SecurityHeadersMiddleware（纯 ASGI，无 body 缓冲）
app.add_middleware(SecurityHeadersMiddleware)

# 6. RequestIdMiddleware（最外层，最先执行，生成 X-Request-ID）
app.add_middleware(RequestIdMiddleware)

# =============================================================================
# Rate limiting with slowapi
# =============================================================================
if config.security.rate_limit_enabled:
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, rate_limit_handler)
    logger.info("Rate limiting enabled (default: 100 req/min per IP, per-endpoint overrides apply)")
else:
    logger.info("Rate limiting is disabled via config")


# P1-12 修复：/api/metrics 暴露运行时指标（路径/权限/模型/错误率），
# 三层鉴权（PUBLIC_PATHS/_PUBLIC_ENDPOINTS_LNN/AUTH_PUBLIC_PATHS）全部放行，
# 任何未认证客户端均可获取。此处增加 IP 白名单作为终端防护：
# - 默认仅允许 loopback + RFC 1918 私有网段（Prometheus scraper 通常部署在内网）
# - 通过 LNN_METRICS_ALLOW_IPS 环境变量可自定义（逗号分隔，支持 CIDR）
# - 白名单外请求返回 403，避免指标数据泄露给外部攻击者
_DEFAULT_METRICS_ALLOW_IPS = (
    "127.0.0.1,::1,10.0.0.0/8,172.16.0.0/12,192.168.0.0/16"
)


def _load_metrics_allowlist() -> tuple[list[ipaddress.IPv4Network | ipaddress.IPv6Network], list[ipaddress.IPv4Address | ipaddress.IPv6Address]]:
    """解析 LNN_METRICS_ALLOW_IPS 环境变量为 (networks, addresses) 二元组。"""
    raw = os.environ.get("LNN_METRICS_ALLOW_IPS", _DEFAULT_METRICS_ALLOW_IPS)
    networks: list[ipaddress.IPv4Network | ipaddress.IPv6Network] = []
    addresses: list[ipaddress.IPv4Address | ipaddress.IPv6Address] = []
    for token in raw.split(","):
        item = token.split("#", 1)[0].strip()
        if not item:
            continue
        try:
            if "/" in item:
                networks.append(ipaddress.ip_network(item, strict=False))
            else:
                addresses.append(ipaddress.ip_address(item))
        except ValueError as exc:
            logger.warning("LNN_METRICS_ALLOW_IPS 无效条目 '%s': %s", item, exc)
    return networks, addresses


_METRICS_NETWORKS, METRICS_ADDRESSES = _load_metrics_allowlist()


def _is_metrics_allowed(client_ip: str) -> bool:
    """检查客户端 IP 是否在 metrics 白名单中。"""
    if not client_ip:
        return False
    try:
        ip_obj = ipaddress.ip_address(client_ip)
    except ValueError:
        return False
    # IPv4/IPv6 类型不匹配时 == 返回 False（不抛异常），可直接比较
    if any(ip_obj == addr for addr in METRICS_ADDRESSES):
        return True
    # IPv4Address in IPv6Network 会抛 TypeError，需逐个 try
    for net in _METRICS_NETWORKS:
        try:
            if ip_obj in net:
                return True
        except TypeError:
            continue
    return False


@app.get("/api/metrics")
async def get_metrics(request: Request):
    # P1-12 修复：IP 白名单鉴权，阻止外部未授权访问运行时指标
    client_ip = request.client.host if request.client else ""
    if not _is_metrics_allowed(client_ip):
        logger.warning(
            "/api/metrics 访问被拒（IP 不在白名单）: client_ip=%s, path=%s",
            client_ip,
            request.url.path,
        )
        return JSONResponse(
            content={"detail": "Forbidden: metrics endpoint not accessible from this IP"},
            status_code=403,
        )
    # P0-14/15 修复：使用 Prometheus exposition format 标准 media_type
    # （version=0.0.4），确保 Prometheus scraper 正确解析。
    return Response(
        content=metrics.export(),
        media_type="text/plain; version=0.0.4; charset=utf-8",
    )


@app.get("/api/v1/version")
async def get_version():
    return get_version_info()


# =============================================================================
# P1-4 修复：桌面 sidecar 优雅关闭端点
# =============================================================================
# 设计：
# - 仅在桌面 sidecar 模式（LNN_IDLE_AUTO_SHUTDOWN=false）下注册
# - 仅监听 127.0.0.1，外部网络无法访问
# - 接收 POST 后异步触发 graceful shutdown（通过 GracefulShutdownHandler）
# - Rust 端 stop() 先 POST 此端点，等待最多 8s，超时才 fallback 到 kill()
# - 避免直接 SIGKILL 导致 SQLite WAL 未 checkpoint / 文件句柄锁定
if not _IDLE_AUTO_SHUTDOWN_ENABLED:
    @app.post("/api/v1/admin/shutdown")
    async def trigger_graceful_shutdown():
        """触发后端优雅关闭。

        由 Tauri Rust 端在退出前调用，确保 shutdown_event 中的
        ring_log / sse_manager / Redis / DB / ChromaDB 资源正常释放。
        """
        logger.info("[shutdown] received graceful shutdown request from sidecar host")
        # 异步触发关闭，不阻塞响应
        # P0-2 修复：保存 task 引用并添加 done_callback，防止关闭流程异常被静默丢弃。
        # 原实现 asyncio.create_task 未保存引用，若 _async_shutdown 内部抛出异常，
        # Python 会在 GC 回收 task 时打印 "Task exception was never retrieved" 警告，
        # 但关闭失败的信息无法被结构化日志捕获，运维无法感知关闭流程是否正常完成。
        shutdown_task = asyncio.create_task(_async_shutdown())

        def _on_shutdown_done(t: asyncio.Task) -> None:
            if t.cancelled():
                logger.warning("[shutdown] graceful shutdown task was cancelled")
                return
            if t.exception() is not None:
                logger.error(
                    "[shutdown] graceful shutdown task failed: %s",
                    t.exception(),
                    exc_info=t.exception(),
                )
            else:
                logger.info("[shutdown] graceful shutdown task completed")

        shutdown_task.add_done_callback(_on_shutdown_done)
        return {"code": 0, "message": "shutdown scheduled"}

    async def _async_shutdown():
        """延迟触发关闭，确保 HTTP 响应已发送。"""
        # P2-5-2 修复：使用命名常量替代魔法数字 0.2
        await asyncio.sleep(SHUTDOWN_DELAY_SECONDS)
        shutdown_handler._handle_shutdown_signal(signal.SIGTERM, None)


# 健康检查端点 - Rust 端通过此端点判断后端是否就绪
@app.get("/api/health/ping")
async def health_ping():
    return {"status": "ok"}


@app.get("/api/v1/logs/stats")
async def get_log_stats():
    return {
        "code": 0,
        "message": "OK",
        "data": ring_log.stats(),
        "request_id": get_request_id(),
    }


@app.get("/api/v1/logs/{buffer_type}")
async def query_logs(
    buffer_type: str,
    since: str | None = None,
    until: str | None = None,
    level: str | None = None,
    limit: int = 100,
    offset: int = 0,
):
    if buffer_type not in BUFFER_TYPES:
        return JSONResponse(
            content={
                "code": 1002,
                "message": f"Invalid buffer type: {buffer_type}",
                "request_id": get_request_id(),
                "detail": {"valid_types": list(BUFFER_TYPES)},
            },
            status_code=400,
        )
    result = ring_log.query(
        buffer_type=buffer_type,
        since=since,
        until=until,
        level=level,
        limit=limit,
        offset=offset,
    )
    return {"code": 0, "message": "OK", "data": result, "request_id": get_request_id()}


if _TORCH_AVAILABLE:
    app.include_router(lnn.router)
app.include_router(lnn_uncertain.router)
app.include_router(wear_prediction.router)
app.include_router(user_sovereignty.router)
app.include_router(agent_gateway.router)
# P0-8 修复：注册 agent_state 路由（/api/agents/*）
app.include_router(agent_state_routes.router)
app.include_router(jobs.router)
app.include_router(rag_routes.router)
if _OLLAMA_AVAILABLE:
    app.include_router(ollama_routes.router)
app.include_router(simulation_api.router)
app.include_router(chatter_api.router)
app.include_router(cutting_force_api.router)
app.include_router(project_routes.router)
app.include_router(step_import_api.router)
app.include_router(rules_router)
app.include_router(process_understanding_routes.router)
app.include_router(health.router)
# 标准化健康检查端点（公开访问，无认证）:
#   - GET /api/health       — 主健康检查
#   - GET /api/health/ping  — 轻量级存活探测（Docker HEALTHCHECK 使用）
# 两个端点均已在 unified_auth.PUBLIC_PATHS 中登记为公开路径，
# 不应用任何认证装饰器或中间件。旧路径 /health 已彻底移除。
app.include_router(health.simple_health_router)
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(skills.router)
app.include_router(cost_budget.router)
app.include_router(governance.router)
app.include_router(goal_alignment.router)
app.include_router(heartbeat.router)
app.include_router(task_checkout.router)
app.include_router(template_ab.router)
app.include_router(template_branches.router)
app.include_router(template_evolution.router)
app.include_router(template_updates.router)
app.include_router(pattern_engine.router)
app.include_router(flywheel.router)
app.include_router(knowledge_graph_routes.router)
app.include_router(status_routes.router)
app.include_router(dxf_pipeline_routes.router)
# Manufacturing UI APIs
app.include_router(materials.router)
app.include_router(equipment.router)
app.include_router(quality.router)
app.include_router(production.router)
app.include_router(process_routes.router)
app.include_router(documents.router)
# CAM APIs
app.include_router(collision_check.router)
app.include_router(tools.router)
# DNC 机床通信
app.include_router(dnc_routes.router)
# MES/ERP 集成
app.include_router(mes_api.router)
# 插件系统
app.include_router(plugins.router)
# 模板市场
app.include_router(template_market.router)
# NL-to-CAD 自然语言建模
from app.api.v1.nl2cad.routes import router as nl2cad_router
app.include_router(nl2cad_router)
# 工艺 / NC 代码对话式解释（LLM 驱动，含多轮会话）
from app.api.v1 import process_explainer as process_explainer_routes
app.include_router(process_explainer_routes.router)
# LLM Provider 网关（多后端 LLM 管理：Ollama/LMStudio/llama.cpp/vLLM 等 + 云端 API）
app.include_router(llm_providers.router)
# SHARP 三元组验证智能体（Schema-Hybrid Agent for Reliable Prediction）
app.include_router(sharp_routes.router)
# 刀路动态调参闭环（刀具磨损 ↔ 工艺规划：磨损 → 决策 → 限幅 → NC 改写）
app.include_router(dynamic_adjustment_routes.router)
# 多源信号融合知识库（振动/切削力/温度/声发射/电流 → 磨损/颤振关联检索）
app.include_router(signal_fusion_kb_routes.router)
# DAG 工作流编排（ADR-005 阶段 1：基于 networkx 的并行/串行/断点续跑）
app.include_router(workflows.router)
# 数据集 / 版本 / 血缘（ADR-005 阶段 2：内容寻址存储 + 血缘图可视化）
app.include_router(datasets.router)
# 实验快照 / 一键复现（ADR-005 阶段 2：git_sha + config + metrics 不可变快照）
app.include_router(snapshots.router)
# 工作流模板市场（ADR-010 阶段 6 p6-1：发布 / 列表 / 搜索 / 下载 / 评分 / 下架 / 多版本管理）
app.include_router(workflow_templates.router)
# 项目级 Git 同步（ADR-011 阶段 6 p6-2：可同步项目 + 资源引用 + commit/push/pull/clone + 同步记录）
app.include_router(project_sync.router)
# 资源卡片（ADR-012 阶段 6 p6-3：模型产物 + 数据集 README + 卡片聚合 + lineage 摘要）
app.include_router(resource_cards.router)
# 项目导入导出（ADR-015 阶段 6 p6-4：.lomo 包格式 + 导出/导入/校验/预览/下载）
app.include_router(project_packages.router)
# 可解释性可视化（ADR-016 阶段 7 p7：隐状态投影 + 门控动力学 + 反事实 + 置信度 + 对比）
app.include_router(explainability.router)
# 世界模型（ADR-017 阶段 8 p8：轨迹预测 + 版本管理）
app.include_router(world_model.router)
# RL Agent（ADR-017 阶段 8 p8：决策推理 + 训练控制）
app.include_router(rl_agent.router)

# 拍照重建模块（ADR-006 阶段 1：手机多角度拍照 → COLMAP SfM → OpenMVS 稠密化 → 标定块尺度归一化 mesh）
# 仅当依赖完整时注册；运行时还受 config.image_to_3d.enabled 开关控制
if _IMAGE_TO_3D_AVAILABLE and config.image_to_3d.enabled:
    app.include_router(image_to_3d_routes.router)

# 几何特征辅助提取模块（ADR-007 阶段 2：mesh → 平面/圆柱/孔检测 → 工程师审核 → 导出已确认特征集）
# 仅当依赖完整时注册；运行时还受 config.feature_extraction.enabled 开关控制
# 设计原则：mesh → 参数化 CAD 自动转换工业上未解决，本模块输出「算法建议特征」，
# 必须经工程师逐条审核（confirmed / rejected / edited）后才允许进入阶段 3 参数化 STEP 生成。
if _FEATURE_EXTRACTION_AVAILABLE and config.feature_extraction.enabled:
    app.include_router(feature_extraction_routes.router)

# 参数化几何输出模块（ADR-008 阶段 3：confirmed_features.json → B-rep → 装配 → STEP → 两轮审核 → 最终 STEP）
# 仅当依赖完整时注册；运行时还受 config.parametric_geometry.enabled 开关控制
# 设计原则（项目记忆硬约束）：
# - mesh → 参数化 CAD 自动转换工业上未解决，本模块输出「算法建议 STEP」
# - 工程师必须两轮审核（STEP_GENERATED + finalize）后才允许下载最终 STEP
# - 最终 STEP 必须经 CAM 软件（NX/PowerMill/PyCAM）二次校验后才允许上机床
# - 本系统定位为「工程师助手」，非「全自动生产线」
if _PARAMETRIC_GEOMETRY_AVAILABLE and config.parametric_geometry.enabled:
    app.include_router(parametric_geometry_routes.router)

# 切削参数推荐模块（ADR-009 阶段 4：STEP + confirmed_features.json + material_id → 推荐参数 → 审核 → ChatterParams）
# 仅当依赖完整时注册；运行时还受 config.cutting_parameters.enabled 开关控制
# 设计原则（项目记忆硬约束）：
# - 本模块是「工程师助手」，非「全自动切削参数生成器」
# - 推荐参数必须经工程师逐条审核后才允许导出 ChatterParams
# - ChatterParams 仅供阶段 5 LTC 颤振预测参考，实际加工必须经 CAM 软件二次校验
# - SUCCEEDED 状态禁止删除（阶段 5 颤振预测可能已引用其 ChatterParams）
# - HRC52 数据待自采校准，K_s 标记为 pending_calibration（影响阶段 5 颤振预测精度）
if _CUTTING_PARAMETERS_AVAILABLE and config.cutting_parameters.enabled:
    app.include_router(cutting_parameters_routes.router)

# ADR-010 阶段 5：颤振预测接入 LTC
# 双路径预测：路径 A Tlusty 解析法（工程默认）→ 路径 B LTC 神经网络（实验性，模型缺失时自动回退到解析法）→ 路径 C 兜底默认值
# 设计约束（项目记忆硬约束）：
# - HRC52 置信度强制降低至 PENDING_CALIBRATION_CONFIDENCE=0.5
# - SUCCEEDED 状态禁止删除（阶段 6 G 代码生成可能已引用其 ChatterReport）
# - cam_validation_required 始终 True，ChatterReport 仅供阶段 6 参考，实际加工必须经 CAM 软件二次校验
# - MC dropout 模式切换使用锁保护，推理路径禁止 fit_transform
if _CHATTER_PREDICTION_AVAILABLE and config.chatter_prediction.enabled:
    app.include_router(chatter_prediction_routes.router)

# ADR-014 阶段 6：G 代码生成接入
# 数据流：阶段 5 ChatterReport + 阶段 3 OperationPlan → GCodeGenerator → 工程师单轮审核 → G 代码文件 + 审核记录 JSON
# 设计约束（项目记忆硬约束）：
# - 系统定位「工程师助手」，非「全自动 G 代码生成器」
# - 复用现有 GCodeGenerator（212 测试覆盖），不重写核心逻辑
# - stable == False 的特征禁止生成 G 代码（强制回阶段 5）
# - SUCCEEDED 状态禁止删除（阶段 7 CAM 校验可能已引用 G 代码产物）
# - cam_validation_required 始终 True，G 代码必须经 CAM 软件二次校验后方可上机
# - 系统绝不直接接口 CNC 控制器
if _GCODE_GENERATION_AVAILABLE and config.gcode_generation.enabled:
    app.include_router(gcode_generation_routes.router)

# === CAM 校验模块路由注册（阶段 7，ADR-018）===
# 数据流：阶段 6 G 代码 + report.json → InternalValidator → CamAdapter → 工程师审核 → cam_report.json
# 设计约束（项目记忆硬约束）：
# - 系统定位「工程师助手」，非「全自动 CAM 仿真器」
# - 阶段 7 产物终止于「CAM 校验报告 JSON」，不触及物理机床
# - cam_validation_required 始终 True（不可关闭）
# - SUCCEEDED 状态禁止删除（cam_report.json 是链路最终产物）
# - 系统绝不直接接口 CNC 控制器
if _CAM_VALIDATION_AVAILABLE and config.cam_validation.enabled:
    app.include_router(cam_validation_routes.router)

register_exception_handlers(app)

logger.info("Application initialized with %d routes", len(app.routes))

if __name__ == "__main__":
    # P2-2 修复：reload 写死改为 config.server.debug 控制，避免生产环境意外开启热重载
    uvicorn.run(
        "app.main:app",
        host=config.server.host,
        port=config.server.port,
        reload=config.server.debug,
    )
