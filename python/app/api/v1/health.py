"""System health check API endpoints."""

from __future__ import annotations

import datetime
import logging
import platform
import sys
import time
from typing import Any

import httpx
from fastapi import APIRouter

from app.config import config
from app.version import VERSION as PY_VERSION

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/health", tags=["Health Check"])
simple_health_router = APIRouter(tags=["Health Check"])

APP_START = time.time()


def _get_python_info() -> dict[str, Any]:
    return {
        "version": platform.python_version(),
        "implementation": platform.python_implementation(),
        "executable": sys.executable,
        "platform": platform.platform(),
        "arch": platform.machine(),
        "app_version": PY_VERSION,
    }


def _get_package_versions() -> dict[str, str]:
    packages = ["fastapi", "httpx", "pydantic", "uvicorn", "numpy", "torch"]
    versions: dict[str, str] = {}
    for pkg in packages:
        try:
            mod = __import__(pkg)
            versions[pkg] = getattr(mod, "__version__", "unknown")
        except ImportError:
            versions[pkg] = "not installed"
    return versions


async def _get_ollama_status() -> dict[str, Any]:
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            response = await client.get(f"{config.ai.ollama_base_url}/api/tags")
            if response.status_code == 200:
                data = response.json()
                models = data.get("models", [])
                return {
                    "running": True,
                    "base_url": config.ai.ollama_base_url,
                    "model_count": len(models),
                    "models": [
                        {
                            "name": m.get("name", "unknown"),
                            "size_mb": round(m.get("size", 0) / 1_048_576, 1),
                        }
                        for m in models
                    ],
                }
            return {"running": False, "error": f"HTTP {response.status_code}"}
    except httpx.ConnectError:
        return {"running": False, "error": "Connection refused — Ollama is not running"}
    except httpx.TimeoutException:
        return {"running": False, "error": "Connection timeout"}
    except Exception as e:
        # 兜底捕获：HTTP 请求可能抛出网络层/序列化层未预期的异常
        # 健康检查端点应始终返回结构化数据，不应向上抛 5xx
        # 修复：仅返回异常类型名，避免泄露内部路径/库版本等敏感信息
        logger.debug("Ollama健康检查异常: %s", e, exc_info=True)
        return {"running": False, "error": f"unhealthy: {type(e).__name__}"}


def _get_disk_info() -> dict[str, Any]:
    try:
        import shutil
        usage = shutil.disk_usage("/")
        return {
            "total_gb": round(usage.total / 1_073_741_824, 1),
            "used_gb": round(usage.used / 1_073_741_824, 1),
            "free_gb": round(usage.free / 1_073_741_824, 1),
            "used_percent": round((usage.used / usage.total) * 100, 1) if usage.total > 0 else 0,
        }
    except Exception as e:
        # 兜底捕获：磁盘信息读取可能因 OSError/权限错误失败
        # 修复：仅返回异常类型名
        logger.warning("Failed to get disk info: %s", e, exc_info=True)
        return {"error": f"unavailable: {type(e).__name__}"}


def _get_memory_info() -> dict[str, Any]:
    try:
        import psutil
        mem = psutil.virtual_memory()
        return {
            "total_mb": round(mem.total / 1_048_576, 1),
            "available_mb": round(mem.available / 1_048_576, 1),
            "used_percent": mem.percent,
        }
    except ImportError:
        return {"error": "psutil not installed"}
    except Exception as e:
        # 兜底捕获：psutil 内部可能因 /proc 不可读抛出 OSError
        # 修复：仅返回异常类型名
        logger.warning("Failed to get memory info: %s", e, exc_info=True)
        return {"error": f"unavailable: {type(e).__name__}"}


@router.get("/system")
async def system_health():
    """Full system health check — returns status of all components."""
    ollama = await _get_ollama_status()
    disk = _get_disk_info()
    memory = _get_memory_info()
    python_info = _get_python_info()
    packages = _get_package_versions()

    items = []

    items.append({
        "component": "python",
        "name": "Python 运行环境",
        "status": "ok",
        "version": python_info["version"],
        "details": python_info,
    })

    if ollama["running"]:
        items.append({
            "component": "ollama",
            "name": "Ollama AI 服务",
            "status": "ok",
            "version": ollama.get("base_url", ""),
            "details": ollama,
        })
    else:
        items.append({
            "component": "ollama",
            "name": "Ollama AI 服务",
            "status": "error",
            "version": None,
            "details": ollama,
        })

    if ollama.get("model_count", 0) > 0:
        items.append({
            "component": "models",
            "name": "AI 模型文件",
            "status": "ok",
            "version": str(ollama["model_count"]),
            "details": ollama.get("models", []),
        })
    elif ollama["running"]:
        items.append({
            "component": "models",
            "name": "AI 模型文件",
            "status": "error",
            "version": "0",
            "details": {"models": [], "suggestion": "run: ollama pull qwen2.5:7b"},
        })
    else:
        items.append({
            "component": "models",
            "name": "AI 模型文件",
            "status": "warning",
            "version": None,
            "details": {"models": [], "note": "Ollama not running, cannot check models"},
        })

    if disk.get("error") is None:
        free_gb = disk.get("free_gb", 0)
        status = "ok" if free_gb > 5 else ("warning" if free_gb > 1 else "error")
        items.append({
            "component": "disk",
            "name": "系统磁盘空间",
            "status": status,
            "version": None,
            "details": disk,
        })
    else:
        items.append({
            "component": "disk",
            "name": "系统磁盘空间",
            "status": "warning",
            "version": None,
            "details": disk,
        })

    if memory.get("error") is None:
        used_pct = memory.get("used_percent", 0)
        status = "ok" if used_pct < 80 else ("warning" if used_pct < 95 else "error")
        items.append({
            "component": "memory",
            "name": "系统内存",
            "status": status,
            "version": None,
            "details": memory,
        })
    else:
        items.append({
            "component": "memory",
            "name": "系统内存",
            "status": "warning",
            "version": None,
            "details": memory,
        })

    items.append({
        "component": "packages",
        "name": "Python 依赖包",
        "status": "ok",
        "version": None,
        "details": packages,
    })

    overall_status = "ok"
    for item in items:
        if item["status"] == "error":
            overall_status = "error"
            break
        elif item["status"] == "warning":
            overall_status = "warning"

    return {
        "status": overall_status,
        "timestamp": time.time(),
        "app_version": PY_VERSION,
        "uptime_seconds": round(time.time() - APP_START, 1),
        "items": items,
    }


@router.get("/quick")
async def quick_health():
    """Quick health check — returns a simple OK/ERROR status."""
    return {"status": "ok", "version": PY_VERSION, "uptime": round(time.time() - APP_START, 1)}


# =============================================================================
# 标准化健康检查端点（容器/探针专用）
# =============================================================================
# 标准化端点设计：
#   - GET /api/health       — 主健康检查，返回标准 JSON（status/version/timestamp）
#   - GET /api/health/ping  — 轻量级存活探测，仅返回 {"ping": true}，
#                            用于 Docker HEALTHCHECK 等高频探活场景
# 两个端点均为公开访问路径（unified_auth 的 PUBLIC_PATHS 中已注册），
# 不需要任何身份验证或授权校验。
# 旧的根路径 /health 已在主程序中彻底移除，避免端点重复和潜在混淆。
# =============================================================================


@simple_health_router.get(
    "/api/health",
    summary="标准化主健康检查",
    description="返回标准格式：{\"status\": \"ok\", \"version\": \"x.x.x\", \"timestamp\": \"<ISO 8601>\"}",
)
async def main_health():
    """主健康检查端点 — 返回统一格式的健康状态。

    返回格式: {"status": "ok", "version": "x.x.x", "timestamp": "..."}
    - status: 固定为 "ok"，表示服务进程已就绪
    - version: 动态获取的应用版本号（来自 app.version）
    - timestamp: ISO 8601 格式（UTC）的当前时间戳
    """
    return {
        "status": "ok",
        "version": PY_VERSION,
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }


@simple_health_router.get(
    "/api/health/ping",
    summary="轻量级健康探针",
    description="轻量级存活探测，严格返回 {\"ping\": true}，用于 Docker HEALTHCHECK",
)
async def ping():
    """轻量级 ping 检查端点 — 返回简单的存活状态。

    用于 Docker HEALTHCHECK 等轻量级健康探测场景。
    返回格式: {"ping": true}
    """
    return {"ping": True}
