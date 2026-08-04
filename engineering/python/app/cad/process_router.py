"""Process router for CAD-related process management."""

import logging
from typing import Any, Optional

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict, Field

from app.core.response import success, error, ErrorCode
from app.core.safe_errors import safe_error_message

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/process", tags=["Process"])


# ---------------------------------------------------------------------------
# Pydantic 请求模型：替代 dict[str, Any]，提供参数校验与 OpenAPI 文档
# 使用 extra="allow" 保持对灵活输入的向后兼容（part features / geometry 等）
# ---------------------------------------------------------------------------


class ProcessPlanRequest(BaseModel):
    """工艺规划请求体。

    接受零件特征、材料和约束条件，返回结构化工艺路线。
    额外字段允许透传给下游 pipeline.run()。
    """

    model_config = ConfigDict(extra="allow")

    material: Optional[str] = Field(None, description="材料名称或牌号")
    part_name: Optional[str] = Field(None, description="零件名称")
    constraints: Optional[dict[str, Any]] = Field(None, description="加工约束条件")


class FeatureRecognitionRequest(BaseModel):
    """特征识别请求体。

    接受几何数据（如 DXF 解析结果），返回识别到的加工特征。
    额外字段允许透传给下游 extractor.extract()。
    """

    model_config = ConfigDict(extra="allow")

    geometry: Optional[dict[str, Any]] = Field(None, description="几何数据")
    source: Optional[str] = Field(None, description="数据来源（如 dxf / step）")


class ParameterRecommendationRequest(BaseModel):
    """参数推荐请求体。

    接受特征描述和材料信息，返回推荐切削参数。
    额外字段允许透传给下游 matcher.match()。
    """

    model_config = ConfigDict(extra="allow")

    material: Optional[str] = Field(None, description="材料名称或牌号")
    features: Optional[list[dict[str, Any]]] = Field(None, description="加工特征列表")


@router.get("/info")
async def get_process_info() -> dict[str, Any]:
    """Get process service information."""
    return success(
        data={
            "status": "active",
            "version": "1.0.0",
            "capabilities": [
                "process_plan_generation",
                "parameter_recommendation",
                "feature_recognition",
                "tool_path_optimization",
            ],
        }
    )


@router.post("/plan")
async def generate_process_plan(body: ProcessPlanRequest) -> dict[str, Any]:
    """Generate a machining process plan from part description.

    Accepts a JSON body with part features, material, and constraints.
    Returns a structured process plan with operations and parameters.
    """
    try:
        from app.process_planning.pipeline import ProcessPlanningPipeline

        pipeline = ProcessPlanningPipeline()
        result = pipeline.run(body.model_dump())

        return success(
            data={
                "plan": result.get("operations", []),
                "parameters": result.get("parameters", {}),
                "confidence": result.get("confidence", 0.0),
            }
        )

    except ImportError:
        logger.warning("Process planning module not available")
        return error(
            code=ErrorCode.SERVICE_UNAVAILABLE,
            message="Process planning module is not available",
        )
    except (ValueError, KeyError, TypeError, OSError, RuntimeError) as exc:
        logger.error("Process plan generation failed: %s", exc, exc_info=True)
        safe = safe_error_message(exc, context="process.plan")
        return error(
            code=ErrorCode.INTERNAL_ERROR,
            message=safe["message"],
            detail=safe.get("detail"),
        )


@router.post("/features/recognize")
async def recognize_features(body: FeatureRecognitionRequest) -> dict[str, Any]:
    """Recognize machining features from part geometry data.

    Accepts geometry data (e.g., from DXF parsing) and returns
    recognized features with type, dimensions, and machining hints.
    """
    try:
        from app.dxf.feature_extractor import FeatureExtractor

        extractor = FeatureExtractor()
        features = extractor.extract(body.model_dump())

        return success(
            data={
                "features": features,
                "count": len(features),
            }
        )

    except ImportError:
        logger.warning("Feature extraction module not available")
        return error(
            code=ErrorCode.SERVICE_UNAVAILABLE,
            message="Feature extraction module is not available",
        )
    except (ValueError, KeyError, TypeError, OSError, RuntimeError) as exc:
        logger.error("Feature recognition failed: %s", exc, exc_info=True)
        safe = safe_error_message(exc, context="process.features")
        return error(
            code=ErrorCode.INTERNAL_ERROR,
            message=safe["message"],
            detail=safe.get("detail"),
        )


@router.post("/parameters/recommend")
async def recommend_parameters(body: ParameterRecommendationRequest) -> dict[str, Any]:
    """Recommend machining parameters for given features and material.

    Accepts feature descriptions and material info, returns optimal
    cutting parameters (speed, feed, depth of cut, etc.).
    """
    try:
        from app.process_planning.tool_param_matcher import ToolParamMatcher

        matcher = ToolParamMatcher()
        params = matcher.match(body.model_dump())

        return success(
            data={
                "parameters": params,
                "source": "rule_based",
            }
        )

    except ImportError:
        logger.warning("Parameter recommendation module not available")
        return error(
            code=ErrorCode.SERVICE_UNAVAILABLE,
            message="Parameter recommendation module is not available",
        )
    except (ValueError, KeyError, TypeError, OSError, RuntimeError, AttributeError) as exc:
        logger.error("Parameter recommendation failed: %s", exc, exc_info=True)
        safe = safe_error_message(exc, context="process.parameters")
        return error(
            code=ErrorCode.INTERNAL_ERROR,
            message=safe["message"],
            detail=safe.get("detail"),
        )
