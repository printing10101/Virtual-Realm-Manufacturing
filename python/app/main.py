"""FastAPI application entry point."""
from __future__ import annotations

import logging.config
import time

import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from app.api.v1.sse import sse_manager
from app.core.cors_config import cors_settings
from app.core.exception_handlers import register_exception_handlers
from app.core.utils import get_metrics_collector

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s:%(lineno)d - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

metrics = get_metrics_collector()


app = FastAPI(
    title="灵境制造 API",
    version="1.0.0",
    description="Lingjing Manufacturing - NC Machining AI Platform",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_settings.get_origins(),
    allow_origin_regex=cors_settings.allow_origin_regex,
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
        return response


app.add_middleware(MetricsMiddleware)
app.add_middleware(SecurityHeadersMiddleware)


@app.on_event("shutdown")
async def shutdown_event():
    await sse_manager.shutdown()


@app.get("/api/metrics")
async def get_metrics():
    return Response(content=metrics.export(), media_type="text/plain; charset=utf-8")


@app.get("/api/health")
async def health_check():
    return {"status": "ok", "version": "1.0.0"}


@app.get("/api/health/ping")
async def ping():
    return {"ping": True}


from app.api.v1 import lnn, wear_prediction
from app.rag import routes as rag_routes
from app.ai import ollama_routes

app.include_router(lnn.router)
app.include_router(wear_prediction.router)
app.include_router(rag_routes.router)
app.include_router(ollama_routes.router)

register_exception_handlers(app)

logger.info("Application initialized with %d routes", len(app.routes))

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)