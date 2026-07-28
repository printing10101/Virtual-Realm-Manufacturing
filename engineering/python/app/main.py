"""FastAPI application entry point.

职责（阶段 1 装配拆分后）：
- 创建 FastAPI 应用实例
- 注册生命周期事件（startup / shutdown）
- 装配中间件链（委托给 ``app.middleware_stack.register_middleware_stack``）
- 注册 API 路由（委托给 ``app.router_registry.register_routers``）
- 注册异常处理器
- 提供少量内联端点（version / health / logs / sidecar shutdown）

非职责：
- 具体路由的导入与 ``include_router`` 调用 -> ``router_registry.py``
- 中间件的 ``add_middleware`` 调用与顺序控制 -> ``middleware_stack.py``
- 条件导入标志位的定义 -> ``router_registry.py``（本文件仅重新导出以保持向后兼容）
"""

from __future__ import annotations

import asyncio
import logging
import logging.config
import os
import signal
import sys
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from starlette.responses import JSONResponse

from app.api.v1.sse import sse_manager
from app.middleware.cors_config import (
    cors_settings,
    enforce_startup_security,
    validate_cors_config,
    CorsConfigError,
)
from app.core.exception_handlers import register_exception_handlers
from app.core.request_id import get_request_id
from app.core.logging_config import configure_logging
from app.utils.utils import get_metrics_collector
from app.sidecar.sidecar_lifecycle import GracefulShutdownHandler
from app.utils.ring_buffer import get_ring_log_buffer, BUFFER_TYPES
from app.config import config
from app.config.limits import LOG_MAX_BYTES
from app.startup_hooks import (
    run_alembic_upgrade,
    verify_critical_dependencies,
)
from app.version import get_version_info, VERSION as PY_VERSION

# =============================================================================
# 阶段 1 装配拆分：路由注册与中间件装配已迁移至独立模块
# =============================================================================
# - router_registry.register_routers: 集中管理 60+ 个 include_router 调用
# - middleware_stack.register_middleware_stack: 集中管理 6 个中间件的注册顺序
# - 条件导入标志位（_OLLAMA_AVAILABLE 等）在 router_registry 中定义，
#   此处重新导出以保持向后兼容（部分测试文件直接 from app.main import _FLAG）
from app.router_registry import (
    register_routers,
    _OLLAMA_AVAILABLE,
    _IMAGE_TO_3D_AVAILABLE,
    _FEATURE_EXTRACTION_AVAILABLE,
    _PARAMETRIC_GEOMETRY_AVAILABLE,
    _CUTTING_PARAMETERS_AVAILABLE,
    _CHATTER_PREDICTION_AVAILABLE,
    _GCODE_GENERATION_AVAILABLE,
    _CAM_VALIDATION_AVAILABLE,
)
from app.middleware_stack import register_middleware_stack

__all__ = [
    # 应用实例
    "app",
    # 装配函数（供测试与 sidecar_main 显式调用）
    "register_routers",
    "register_middleware_stack",
    # 条件导入标志位（向后兼容：测试文件仍可 from app.main import _FLAG）
    "_OLLAMA_AVAILABLE",
    "_IMAGE_TO_3D_AVAILABLE",
    "_FEATURE_EXTRACTION_AVAILABLE",
    "_PARAMETRIC_GEOMETRY_AVAILABLE",
    "_CUTTING_PARAMETERS_AVAILABLE",
    "_CHATTER_PREDICTION_AVAILABLE",
    "_GCODE_GENERATION_AVAILABLE",
    "_CAM_VALIDATION_AVAILABLE",
]

# P2-5-2 修复：提取日志配置魔法数字为命名常量，便于统一管理
# LOG_MAX_BYTES 由 ``app.config.limits`` 集中管理（50 MB），与
# ``core/logging_config.py`` / ``config/logging_config.py`` 共享同一基准值。
LOG_RETENTION_DAYS: int = 30
# 优雅关闭延迟（秒）：等待 HTTP 响应发送完成后再触发 shutdown
SHUTDOWN_DELAY_SECONDS: float = 0.2
# Alembic 迁移日志截断长度已迁移至 ``app.startup_hooks`` 模块

_log_root = os.environ.get("LNN_LOG_DIR", str(Path(config.paths.gstack_dir).parent / "logs"))
configure_logging(
    level=logging.INFO,
    log_root=_log_root,
    module_name="python",
    max_bytes=LOG_MAX_BYTES,
    retention_days=LOG_RETENTION_DAYS,
)
logger = logging.getLogger(__name__)


# =============================================================================
# 运行期共享对象（metrics / ring_log / state_file_path）
# =============================================================================
# 这些对象在 startup 之前就需要存在（中间件装配依赖），因此放在模块级初始化。
metrics = get_metrics_collector()
ring_log = get_ring_log_buffer(base_dir=config.paths.gstack_dir)

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


# =============================================================================
# 应用实例创建
# =============================================================================
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


# =============================================================================
# 生命周期事件
# =============================================================================
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
    # 实现已迁移至 ``app.startup_hooks.run_alembic_upgrade``，便于独立测试
    await run_alembic_upgrade(logger)

    # --- Step 3: Redis (optional, returns None if not configured) ---
    logger.info("[startup] Calling get_redis() ...")
    await get_redis()
    logger.info("[startup] get_redis() done")

    # --- Step 3b: 关键依赖连通性自检（P1-15 修复）---
    # 启动后立即验证 DB / Redis 可达性，失败仅 warning 不阻断启动
    # （保持与 Alembic 迁移相同的容错策略：桌面开发模式可能未配置全部依赖）。
    # 避免应用以"僵尸态"启动——进程存活但所有请求因依赖不可达而 500。
    # 实现已迁移至 ``app.startup_hooks.verify_critical_dependencies``，便于独立测试
    await verify_critical_dependencies(logger)

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

    # ---- 关闭顺序设计（P2-3 优化） ----
    # 关闭顺序遵循"调度层先停 → 执行层停 → 业务模块停 → 基础设施停"原则：
    #   1) HeartbeatScheduler（调度层）：停止提交新任务到 AsyncTaskManager
    #   2) AsyncTaskManager（执行层）：取消已运行任务，拒绝新任务
    #   3) 业务模块（Budget/Cost/Rule/Goal/Audit）：归还 SQLite 连接
    #   4) Redis / HTTP Client（外部依赖）：关闭网络连接
    #   5) DB / VectorStore（持久化层）：关闭文件句柄
    #   6) Logging（最底层）：最后关闭
    # 这样可避免调度器在执行层关闭后仍提交新任务（虽 P2-2 已加 _shutdown
    # 标志位保护，但语义上仍应调度层先停）。

    # 1) HeartbeatScheduler：取消心跳 asyncio.Task 并关闭 WakeupQueue 连接
    try:
        from app.heartbeat.heartbeat import get_scheduler
        await get_scheduler().stop()
    except (OSError, RuntimeError, ValueError, AttributeError,
            ImportError, TypeError) as e:
        logger.warning("HeartbeatScheduler stop failed during shutdown: %s", e)

    # 2) AsyncTaskManager：取消所有运行中任务，清空订阅者与 cancel events
    task_mgr = AsyncTaskManager()
    await task_mgr.shutdown()

    # 3) 业务模块：归还 SQLite 连接池连接，避免连接泄漏与 Windows 文件句柄锁定。
    #    各模块独立 try/except，避免一处失败影响其他资源的释放。
    try:
        from app.budget.budget import get_budget_manager
        get_budget_manager().close()
    except (OSError, RuntimeError, ValueError, AttributeError,
            ImportError, TypeError) as e:
        logger.warning("BudgetManager close failed during shutdown: %s", e)

    try:
        from app.budget.cost_tracker import get_cost_tracker
        get_cost_tracker().close()
    except (OSError, RuntimeError, ValueError, AttributeError,
            ImportError, TypeError) as e:
        logger.warning("CostTracker close failed during shutdown: %s", e)

    try:
        from app.database.rule_db import get_rule_db
        get_rule_db().close()
    except (OSError, RuntimeError, ValueError, AttributeError,
            ImportError, TypeError) as e:
        logger.warning("RuleDatabase close failed during shutdown: %s", e)

    try:
        from app.goals.goal_chain_store import get_goal_chain_store
        get_goal_chain_store().close()
    except (OSError, RuntimeError, ValueError, AttributeError,
            ImportError, TypeError) as e:
        logger.warning("GoalChainStore close failed during shutdown: %s", e)

    # AgentAuditLog：关闭审计日志文件句柄
    # P2-1 修复：``app.auth.audit`` 已改为 re-export shim，
    # 全进程只有 ``app.agent.middleware`` 创建一个实例，
    # ``get_agent_audit_log()`` 返回同一实例，close 一次即可。
    try:
        from app.agent.middleware import get_agent_audit_log
        get_agent_audit_log().close()
    except (OSError, ValueError, AttributeError, ImportError) as e:
        logger.warning("AgentAuditLog close failed: %s", e)

    # 4) 外部依赖：Redis / HTTP Client
    await close_redis()
    await close_shared_http_client()

    # 5) 持久化层：DB / VectorStore
    await close_db()

    # 显式关闭 ChromaDB PersistentClient，释放底层 SQLite/DuckDB 资源，
    # 避免 Windows 文件句柄锁定导致下次启动失败。
    try:
        from app.rag.vector_store import get_vector_store
        get_vector_store().close()
    except (OSError, RuntimeError, ValueError, AttributeError,
            ImportError, TypeError) as e:
        # Q1 修复：收窄为可预期的关闭阶段异常。OSError 覆盖文件句柄/SQLite
        # 关闭错误；ImportError 覆盖 vector_store 模块缺失场景。
        logger.warning("VectorStore close failed during shutdown: %s", e)

    # 6) 最底层：Logging
    shutdown_logging()

    logger.info("FastAPI shutdown event completed")


# =============================================================================
# 中间件链装配（委托给 middleware_stack.py）
# =============================================================================
# 注册顺序与期望执行顺序的对应关系、CORS 与 UnifiedAuth 的位置约束等
# 关键设计决策均在 ``app.middleware_stack`` 模块顶部注释中详细说明。
register_middleware_stack(
    app,
    metrics=metrics,
    ring_log=ring_log,
    state_file_path=STATE_FILE_PATH,
    idle_auto_shutdown_enabled=_IDLE_AUTO_SHUTDOWN_ENABLED,
    idle_timeout_seconds=IDLE_TIMEOUT_SECONDS,
)


# =============================================================================
# 内联端点（生命周期相关 / 简单查询，不归属于任何业务域）
# =============================================================================
@app.get("/api/v1/version")
async def get_version():
    return get_version_info()


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


# =============================================================================
# 路由注册（委托给 router_registry.py）
# =============================================================================
# 所有 60+ 个 include_router 调用集中在此处，按域分组（LNN / RAG / 模拟 /
# 制造 / CAM / DNC / MES / 插件 / ADR 阶段 1-8）。条件路由（依赖可选库）
# 最后注册，失败仅告警不阻断启动。
register_routers(app)

# 异常处理器注册
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
