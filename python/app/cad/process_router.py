"""Process router for CAD-related process management."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException

from app.core.response import success, error, ErrorCode
from app.core.safe_errors import safe_error_message

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/process", tags=["Process"])


@router.get("/info")
async def get_process_info() -> dict[str, Any]:
    """Get process service information."""
    return success(data={
        "status": "active",
        "version": "1.0.0",
        "capabilities": [
            "process_plan_generation",
            "parameter_recommendation",
            "feature_recognition",
            "tool_path_optimization",
        ],
    })


@router.post("/plan")
async def generate_process_plan(body: dict[str, Any]) -> dict[str, Any]:
    """Generate a machining process plan from part description.

    Accepts a JSON body with part features, material, and constraints.
    Returns a structured process plan with operations and parameters.
    """
    try:
        from app.process_planning.pipeline import ProcessPlanningPipeline

        pipeline = ProcessPlanningPipeline()
        result = pipeline.run(body)

        return success(data={
            "plan": result.get("operations", []),
            "parameters": result.get("parameters", {}),
            "confidence": result.get("confidence", 0.0),
        })

    except ImportError:
        logger.warning("Process planning module not available")
        return error(
            code=ErrorCode.SERVICE_UNAVAILABLE,
            message="Process planning module is not available",
        )
    except Exception as exc:
        logger.error("Process plan generation failed: %s", exc)
        safe = safe_error_message(exc, context="process.plan")
        return error(
            code=ErrorCode.INTERNAL_ERROR,
            message=safe["message"],
            detail=safe.get("detail"),
        )


@router.post("/features/recognize")
async def recognize_features(body: dict[str, Any]) -> dict[str, Any]:
    """Recognize machining features from part geometry data.

    Accepts geometry data (e.g., from DXF parsing) and returns
    recognized features with type, dimensions, and machining hints.
    """
    try:
        from app.dxf.feature_extractor import FeatureExtractor

        extractor = FeatureExtractor()
        features = extractor.extract(body)

        return success(data={
            "features": features,
            "count": len(features),
        })

    except ImportError:
        logger.warning("Feature extraction module not available")
        return error(
            code=ErrorCode.SERVICE_UNAVAILABLE,
            message="Feature extraction module is not available",
        )
    except Exception as exc:
        logger.error("Feature recognition failed: %s", exc)
        safe = safe_error_message(exc, context="process.features")
        return error(
            code=ErrorCode.INTERNAL_ERROR,
            message=safe["message"],
            detail=safe.get("detail"),
        )


@router.post("/parameters/recommend")
async def recommend_parameters(body: dict[str, Any]) -> dict[str, Any]:
    """Recommend machining parameters for given features and material.

    Accepts feature descriptions and material info, returns optimal
    cutting parameters (speed, feed, depth of cut, etc.).
    """
    try:
        from app.process_planning.tool_param_matcher import ToolParamMatcher

        matcher = ToolParamMatcher()
        params = matcher.match(body)

        return success(data={
            "parameters": params,
            "source": "rule_based",
        })

    except ImportError:
        logger.warning("Parameter recommendation module not available")
        return error(
            code=ErrorCode.SERVICE_UNAVAILABLE,
            message="Parameter recommendation module is not available",
        )
    except Exception as exc:
        logger.error("Parameter recommendation failed: %s", exc)
        safe = safe_error_message(exc, context="process.parameters")
        return error(
            code=ErrorCode.INTERNAL_ERROR,
            message=safe["message"],
            detail=safe.get("detail"),
        )
