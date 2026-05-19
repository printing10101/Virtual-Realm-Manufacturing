"""System health check API endpoints."""

from __future__ import annotations

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
        return {"running": False, "error": str(e)}


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
        logger.warning("Failed to get disk info: %s", e)
        return {"error": str(e)}


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
        logger.warning("Failed to get memory info: %s", e)
        return {"error": str(e)}


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