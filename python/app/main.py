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
from app.core.exception_handlers import register_exception_handlers
from app.core.utils import get_metrics_collector
from app.core.sidecar_lifecycle import IdleAutoShutdownMiddleware, GracefulShutdownHandler
from app.core.ring_buffer import get_ring_log_buffer, BUFFER_TYPES
from app.version import get_version_info, VERSION as PY_VERSION
from app.agent.middleware import AgentAuthMiddleware
from app.api.v1 import lnn, wear_prediction, user_sovereignty, agent_gateway, jobs
from app.rag import routes as rag_routes
from app.ai import ollama_routes

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s:%(lineno)d - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

metrics = get_metrics_collector()
ring_log = get_ring_log_buffer(base_dir=os.environ.get("LNN_GSTACK_DIR", ".lingjing/.gstack"))

auth_enabled = os.environ.get("LNN_AUTH_ENABLED", "true").lower() == "true"
permission_enforced = os.environ.get("LNN_PERMISSION_ENFORCED", "false").lower() == "true"

STATE_FILE_PATH = str(Path(os.environ.get("LNN_GSTACK_DIR", ".lingjing/.gstack")) / "sidecar.json")

APP_START_TIME = time.time()


def get_state_file_path() -> str:
    return STATE_FILE_PATH


app = FastAPI(
    title="灵境制造 API",
    version="1.7.0",
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
    ring_log.append("system_event", level="INFO", source="startup",
                    message="Application started", data={"version": PY_VERSION})
    logger.info("Graceful shutdown handler and signal processors registered")
    logger.info("Idle auto-shutdown middleware registered (timeout: 1800s)")
    logger.info("State file path: %s", STATE_FILE_PATH)


@app.on_event("shutdown")
async def shutdown_event():
    ring_log.append("system_event", level="INFO", source="shutdown",
                    message="Application shutting down")
    await ring_log.stop()
    await sse_manager.shutdown()
    logger.info("FastAPI shutdown event completed")


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
        ring_log.append("request", level="INFO", source=request.url.path,
                        message=f"{request.method} {request.url.path}",
                        data={"method": request.method, "path": request.url.path,
                              "status": response.status_code,
                              "elapsed_ms": round(elapsed * 1000, 3)})
        return response


app.add_middleware(MetricsMiddleware)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(AuthMiddleware, enabled=auth_enabled, permission_enforced=permission_enforced)


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
    return {"status": "ok", "version": "1.7.0"}


@app.get("/api/health/ping")
async def ping():
    return {"ping": True}


@app.get("/api/v1/version")
async def get_version():
    return get_version_info()


@app.get("/api/v1/logs/stats")
async def get_log_stats():
    return {"code": "SUCCESS", "message": "OK", "data": ring_log.stats()}


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
            content={"code": "INVALID_REQUEST", "message": f"Invalid buffer type: {buffer_type}",
                     "data": None, "detail": {"valid_types": list(BUFFER_TYPES)}},
            status_code=400,
        )
    result = ring_log.query(buffer_type=buffer_type, since=since, until=until,
                            level=level, limit=limit, offset=offset)
    return {"code": "SUCCESS", "message": "OK", "data": result}


agent_auth_enabled = os.environ.get("AGENT_AUTH_ENABLED", "true").lower() == "true"
app.add_middleware(AgentAuthMiddleware, enabled=agent_auth_enabled)

app.include_router(lnn.router)
app.include_router(wear_prediction.router)
app.include_router(user_sovereignty.router)
app.include_router(agent_gateway.router)
app.include_router(jobs.router)
app.include_router(rag_routes.router)
app.include_router(ollama_routes.router)

register_exception_handlers(app)

logger.info("Application initialized with %d routes", len(app.routes))

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)