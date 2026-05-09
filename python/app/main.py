"""
LNN Manufacturing AI Service - FastAPI Application

This is the main entry point for the LNN manufacturing AI service.
"""
import logging
import time
from threading import Lock

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.lnn import router as lnn_router
from app.api.v1.wear_prediction import router as wear_prediction_router
from app.ai.ollama_routes import router as ollama_router
from app.rag.routes import router as rag_router
from app.config import config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

APP_VERSION = "1.4.0"

app = FastAPI(
    title="灵境制造 LNN AI API",
    description="基于神经逻辑网络(LNN)的智能制造AI推理与训练API服务",
    version=APP_VERSION,
)

cors_origins = config.security.cors_origins
allow_all = len(cors_origins) == 1 and cors_origins[0] == "*"

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if allow_all else cors_origins,
    allow_credentials=not allow_all,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(lnn_router)
app.include_router(wear_prediction_router)
app.include_router(ollama_router)
app.include_router(rag_router)

_request_count = 0
_request_latency: dict[str, list[float]] = {}
_latency_lock = Lock()
_start_time = time.time()


@app.middleware("http")
async def track_metrics(request, call_next):
    global _request_count
    start = time.time()
    response = await call_next(request)
    elapsed = time.time() - start
    with _latency_lock:
        _request_count += 1
        path = request.url.path
        _request_latency.setdefault(path, []).append(elapsed)
    return response


@app.get("/metrics")
async def metrics():
    lines = [
        "# HELP app_uptime_seconds Application uptime in seconds",
        "# TYPE app_uptime_seconds counter",
        f"app_uptime_seconds {time.time() - _start_time:.0f}",
        "",
        "# HELP http_requests_total Total number of HTTP requests",
        "# TYPE http_requests_total counter",
        f'http_requests_total{{method="total"}} {_request_count}',
        "",
        "# HELP http_request_duration_seconds HTTP request duration in seconds",
        "# TYPE http_request_duration_seconds histogram",
    ]
    with _latency_lock:
        for path, latencies in _request_latency.items():
            avg = sum(latencies) / len(latencies) if latencies else 0
            lines.append(f'http_request_duration_seconds_bucket{{path="{path}",le="+Inf"}} {avg:.4f}')
    return "\n".join(lines)


@app.get("/api/v1/health")
async def health_check():
    return {"status": "ok", "version": APP_VERSION}
