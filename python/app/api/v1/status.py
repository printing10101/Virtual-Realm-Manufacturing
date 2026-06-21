"""系统状态端点。

包含：
    - GET /api/v1/status
        系统健康、模块版本、研究/产品开关、桥接层日志大小
    - GET /api/v1/status/postprocessors
        列出已注册的后处理器（覆盖 GSK / HNC / KND）
    - GET /api/v1/status/knowledge-graph
        知识图谱规模
    - GET /api/v1/status/research-bridge
        桥接层日志与 feature flag
"""
from __future__ import annotations

import logging
import os
from typing import Any

from fastapi import APIRouter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/status", tags=["status"])


@router.get("")
def get_status() -> dict[str, Any]:
    """总体系统状态。"""
    out: dict[str, Any] = {
        "service": "lingjing-factory",
        "components": {},
    }
    # 1. 桥接层
    try:
        from app.research_bridge import UsageDataCollector

        out["components"]["research_bridge"] = UsageDataCollector.get_instance().health_check()
    except Exception as e:  # noqa: BLE001
        out["components"]["research_bridge"] = {"error": repr(e)}

    # 2. feature flags
    try:
        from app.research_bridge.feature_flags import (
            is_shadow_mode,
            ROLLOUT_CONFIG,
        )

        out["components"]["feature_flags"] = {
            "shadow_mode_master": is_shadow_mode(),
            "rollout": {
                name.value: {
                    "status": cfg["status"].value
                    if hasattr(cfg["status"], "value")
                    else str(cfg["status"]),
                    "whitelist": cfg.get("whitelist", []),
                    "rollout_pct": cfg.get("rollout_pct", 0.0),
                }
                for name, cfg in ROLLOUT_CONFIG.items()
            },
        }
    except Exception as e:  # noqa: BLE001
        out["components"]["feature_flags"] = {"error": repr(e)}

    # 3. postprocessors
    try:
        from app.postprocessor.registry import PostProcessorRegistry

        regs = PostProcessorRegistry()
        out["components"]["postprocessors"] = {
            "registered": regs.list_controllers(),
        }
    except Exception as e:  # noqa: BLE001
        out["components"]["postprocessors"] = {"error": repr(e)}

    # 4. knowledge graph
    try:
        from app.knowledge_graph import KnowledgeGraphQueryAPI, GraphStore

        api = KnowledgeGraphQueryAPI(GraphStore(auto_load=False))
        out["components"]["knowledge_graph"] = api.stats()
    except Exception as e:  # noqa: BLE001
        out["components"]["knowledge_graph"] = {"error": repr(e)}

    # 5. environment flags
    out["env"] = {
        "shadow_mode_master": os.environ.get("SHADOW_MODE_MASTER", "0"),
        "research_flag": os.environ.get("ENABLE_RESEARCH", "0"),
    }
    return out


@router.get("/postprocessors")
def get_postprocessors() -> dict[str, Any]:
    """列出已注册的后处理器。"""
    try:
        from app.postprocessor.registry import PostProcessorRegistry

        regs = PostProcessorRegistry()
        return {
            "count": len(regs.list_controllers()),
            "controllers": regs.list_controllers(),
        }
    except Exception as e:  # noqa: BLE001
        return {"error": repr(e)}


@router.get("/research-bridge")
def get_bridge() -> dict[str, Any]:
    """桥接层详情。"""
    try:
        from app.research_bridge import UsageDataCollector

        c = UsageDataCollector.get_instance()
        return {"health": c.health_check(), "summary": c.summary()}
    except Exception as e:  # noqa: BLE001
        return {"error": repr(e)}


__all__ = ["router"]
