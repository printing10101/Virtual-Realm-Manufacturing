"""FastAPI application entry point."""

from __future__ import annotations

import logging.config
import os
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
)
from app.integrations.mes import api as mes_api

# torch 相关模块：桌面版可能没有 torch，条件导入
_TORCH_AVAILABLE = False
try:
    from app.api.v1 import lnn
    _TORCH_AVAILABLE = True
except ImportError as e:
    import logging
    logging.warning(
        f"torch 模块导入失败: {e}。"
        "影响: LNN 神经网络相关功能将不可用。"
        "修复: 请安装 PyTorch，运行 'pip install torch torchvision torchaudio'"
    )
from app.rag import routes as rag_routes
from app.ai.process_understanding import routes as process_understanding_routes

# ollama 相关模块：桌面版可能没有 ollama，条件导入
_OLLAMA_AVAILABLE = False
try:
    from app.ai import ollama_routes
    _OLLAMA_AVAILABLE = True
except ImportError as e:
    import logging
    logging.warning(
        f"ollama 模块导入失败: {e}。"
        "影响: Ollama AI 模型集成功能将不可用。"
        "修复: 请安装 ollama Python 包，运行 'pip install ollama'"
    )

from app.simulation import api as simulation_api
from app.projects import project_api as project_routes
from app.step_import import api as step_import_api
from app.rules import router as rules_router

_log_root = os.environ.get("LNN_LOG_DIR", str(Path(config.paths.gstack_dir).parent / "logs"))
configure_logging(
    level=logging.INFO,
    log_root=_log_root,
    module_name="python",
    max_bytes=50 * 1024 * 1024,
    retention_days=30,
)
logger = logging.getLogger(__name__)

metrics = get_metrics_collector()
ring_log = get_ring_log_buffer(base_dir=config.paths.gstack_dir)

auth_enabled = config.security.auth_enabled
permission_enforced = config.security.permission_enforced

STATE_FILE_PATH = str(Path(config.paths.gstack_dir) / "sidecar.json")


def get_state_file_path() -> str:
    return STATE_FILE_PATH


app = FastAPI(
    title="灵境制造 API",
    version="2.3.0",
    description="Lingjing Manufacturing - NC Machining AI Platform",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

shutdown_handler = GracefulShutdownHandler(app=app, state_file_path=STATE_FILE_PATH)

# Ensure state file directory exists
Path(STATE_FILE_PATH).parent.mkdir(parents=True, exist_ok=True)

# IdleAutoShutdownMiddleware configuration
IDLE_TIMEOUT_SECONDS = 1800


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
    import os as _os

    # --- Step 1: Set DB_URL for async SQLAlchemy ---
    if not _os.environ.get("DB_URL"):
        db_path = Path(__file__).parent.parent / "data" / "app.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)
        _os.environ["DB_URL"] = f"sqlite+aiosqlite:///{db_path}"
        logger.info("[startup] DB_URL not set, using default: %s", _os.environ["DB_URL"])

    # --- Step 2: Initialize async DB tables + seed RBAC ---
    # (init_db uses Base.metadata.create_all, which handles fresh DB creation)
    logger.info("[startup] Calling init_db() ...")
    await init_db()
    logger.info("[startup] init_db() done")

    # --- Step 3: Redis (optional, returns None if not configured) ---
    logger.info("[startup] Calling get_redis() ...")
    await get_redis()
    logger.info("[startup] get_redis() done")

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

    task_mgr = AsyncTaskManager()
    await task_mgr.shutdown()
    await close_redis()
    await close_db()

    logger.info("FastAPI shutdown event completed")


# Middleware registration order (outermost first):
#   RequestIdMiddleware  -> generates X-Request-ID
#   SecurityHeadersMiddleware -> pure ASGI, adds security headers
#   CORSMiddleware
#   MetricsMiddleware -> records request metrics (BaseHTTPMiddleware)
#   UnifiedAuthMiddleware -> pure ASGI, merged LNN+JWT+Agent auth
#   IdleAutoShutdownMiddleware -> tracks idle time (BaseHTTPMiddleware)
#
# Only 2 BaseHTTPMiddleware remain: MetricsMiddleware, IdleAutoShutdownMiddleware

app.add_middleware(RequestIdMiddleware)

# Pure ASGI SecurityHeadersMiddleware (no body buffering)
app.add_middleware(SecurityHeadersMiddleware)

# IdleAutoShutdownMiddleware - tracks idle time and auto-shutdown (BaseHTTPMiddleware)
app.add_middleware(
    IdleAutoShutdownMiddleware,
    idle_timeout=IDLE_TIMEOUT_SECONDS,
    state_file_path=STATE_FILE_PATH,
)

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


class MetricsMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start = time.perf_counter()
        response = await call_next(request)
        elapsed = time.perf_counter() - start
        metrics.record(request.url.path, elapsed)
        ring_log.append(
            "request",
            level="INFO",
            source=request.url.path,
            message=f"{request.method} {request.url.path}",
            data={
                "method": request.method,
                "path": request.url.path,
                "status": response.status_code,
                "elapsed_ms": round(elapsed * 1000, 3),
            },
        )
        return response


app.add_middleware(MetricsMiddleware)

# Unified ASGI auth middleware (merges AuthMiddleware, JwtAuthMiddleware, AgentAuthMiddleware)
jwt_auth_enabled = os.environ.get("LNN_JWT_AUTH_ENABLED", "true").lower() == "true"
app.add_middleware(
    UnifiedAuthMiddleware,
    lnn_auth_enabled=auth_enabled,
    lnn_permission_enforced=permission_enforced,
    jwt_auth_enabled=jwt_auth_enabled,
    agent_auth_enabled=config.security.agent_auth_enabled,
)

# =============================================================================
# Rate limiting with slowapi
# =============================================================================
if config.security.rate_limit_enabled:
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, rate_limit_handler)
    logger.info("Rate limiting enabled (default: 100 req/min per IP, per-endpoint overrides apply)")
else:
    logger.info("Rate limiting is disabled via config")


@app.get("/api/metrics")
async def get_metrics():
    return Response(content=metrics.export(), media_type="text/plain; charset=utf-8")


@app.get("/api/v1/version")
async def get_version():
    return get_version_info()


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
app.include_router(jobs.router)
app.include_router(rag_routes.router)
if _OLLAMA_AVAILABLE:
    app.include_router(ollama_routes.router)
app.include_router(simulation_api.router)
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

register_exception_handlers(app)

logger.info("Application initialized with %d routes", len(app.routes))

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=config.server.port, reload=True)
