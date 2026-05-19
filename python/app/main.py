"""FastAPI application entry point."""

from __future__ import annotations

import logging.config
import os
import time
from pathlib import Path

import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response, JSONResponse

from app.api.v1.sse import sse_manager
from app.core.cors_config import cors_settings
from app.core.auth import AuthMiddleware
from app.core.jwt_auth import JwtAuthMiddleware
from app.core.exception_handlers import register_exception_handlers
from app.core.request_id import RequestIdMiddleware, get_request_id
from app.core.logging_config import configure_logging
from app.core.utils import get_metrics_collector
from app.core.sidecar_lifecycle import (
    IdleAutoShutdownMiddleware,
    GracefulShutdownHandler,
)
from app.core.ring_buffer import get_ring_log_buffer, BUFFER_TYPES
from app.config import config
from app.version import get_version_info, VERSION as PY_VERSION
from app.agent.middleware import AgentAuthMiddleware
from app.api.v1 import lnn, wear_prediction, user_sovereignty, agent_gateway, jobs, health, auth, users
from app.rag import routes as rag_routes
from app.ai import ollama_routes
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

APP_START_TIME = time.time()


def get_state_file_path() -> str:
    return STATE_FILE_PATH


app = FastAPI(
    title="灵境制造 API",
    version="1.9.0",
    description="Lingjing Manufacturing - NC Machining AI Platform",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

shutdown_handler = GracefulShutdownHandler(app=app, state_file_path=STATE_FILE_PATH)
idle_middleware = IdleAutoShutdownMiddleware(
    app=app,
    idle_timeout=1800,
    state_file_path=STATE_FILE_PATH,
)


@app.on_event("startup")
async def startup_event():
    shutdown_handler.setup()
    await ring_log.start()
    await idle_middleware.start_idle_checker()

    from app.database.models import init_db
    from app.core.task_system import AsyncTaskManager
    from app.services.redis_client import get_redis

    await init_db()
    await get_redis()

    task_mgr = AsyncTaskManager()
    await task_mgr.initialize(max_concurrent=config.tasks.max_concurrent)

    ring_log.append(
        "system_event",
        level="INFO",
        source="startup",
        message="Application started",
        data={"version": PY_VERSION},
    )
    logger.info("Graceful shutdown handler and signal processors registered")
    logger.info("Idle auto-shutdown middleware registered (timeout: 1800s)")
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

    from app.core.task_system import AsyncTaskManager
    from app.database.connection import close_db
    from app.services.redis_client import close_redis

    task_mgr = AsyncTaskManager()
    await task_mgr.shutdown()
    await close_redis()
    await close_db()

    logger.info("FastAPI shutdown event completed")


app.add_middleware(RequestIdMiddleware)

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


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response: Response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Permissions-Policy"] = (
            "camera=(), microphone=(), geolocation=()"
        )
        return response


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
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(
    AuthMiddleware, enabled=auth_enabled, permission_enforced=permission_enforced
)

jwt_auth_enabled = os.environ.get("LNN_JWT_AUTH_ENABLED", "true").lower() == "true"
app.add_middleware(JwtAuthMiddleware, enabled=jwt_auth_enabled)


@app.get("/api/metrics")
async def get_metrics():
    return Response(content=metrics.export(), media_type="text/plain; charset=utf-8")


@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "timestamp": time.time(),
        "version": PY_VERSION,
        "uptime": time.time() - APP_START_TIME,
    }


@app.get("/api/health")
async def api_health_check():
    return {"status": "ok", "version": "1.9.0"}


@app.get("/api/health/ping")
async def ping():
    return {"ping": True}


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


agent_auth_enabled = config.security.agent_auth_enabled
app.add_middleware(AgentAuthMiddleware, enabled=agent_auth_enabled)

app.include_router(lnn.router)
app.include_router(wear_prediction.router)
app.include_router(user_sovereignty.router)
app.include_router(agent_gateway.router)
app.include_router(jobs.router)
app.include_router(rag_routes.router)
app.include_router(ollama_routes.router)
app.include_router(simulation_api.router)
app.include_router(project_routes.router)
app.include_router(step_import_api.router)
app.include_router(rules_router)
app.include_router(health.router)
app.include_router(auth.router)
app.include_router(users.router)

register_exception_handlers(app)

logger.info("Application initialized with %d routes", len(app.routes))

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
