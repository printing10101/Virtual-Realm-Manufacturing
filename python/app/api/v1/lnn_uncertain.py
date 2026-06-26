"""LNN Uncertainty Quantization API endpoint.

Provides /api/v1/lnn/predict-uncertain endpoint that returns prediction
with uncertainty (std) and confidence metrics from Bayesian LNN models.
"""

import logging
import numpy as np
from fastapi import APIRouter
from app.core.response import ErrorCode, error, success
from app.core.safe_errors import safe_error_message
from app.models.schemas import LNNPredictRequest, UncertaintyResponse
from app.ai.lnn.inference.predictor import LNNPredictor, PredictionResult
from app.services.model_registry_service import get_model_registry_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/lnn", tags=["LNN Models"])

registry_service = get_model_registry_service()
model_registry = registry_service.model_registry
model_cache = registry_service.model_cache


@router.post("/predict-uncertain")
async def predict_uncertain(body: LNNPredictRequest):
    """Predict with uncertainty quantification using Bayesian LNN.

    Returns prediction value, uncertainty (standard deviation), and confidence.
    Confidence is calculated as: 1 - (std / mean).clamp(0, 1).
    """
    try:
        entry = model_registry.registry.get(body.model_name)
        if not entry:
            return error(
                code=ErrorCode.NOT_FOUND,
                message=f"Model '{body.model_name}' not found",
            )

        if not body.input_data:
            return error(
                code=ErrorCode.INVALID_REQUEST,
                message="输入数据必须为非空列表",
            )

        if any(not isinstance(x, (int, float)) for x in body.input_data):
            return error(
                code=ErrorCode.INVALID_REQUEST,
                message="输入数据必须为数值类型",
            )

        model_info = entry.info
        expected_dim = (
            len(model_info.input_features) if model_info.input_features else None
        )
        if expected_dim:
            input_len = len(body.input_data)
            if input_len != expected_dim and input_len % expected_dim != 0:
                return error(
                    code=ErrorCode.INVALID_REQUEST,
                    message=f"输入维度不匹配: 期望{expected_dim}维或其倍数，实际{input_len}维",
                )

        predictor = model_cache.get(body.model_name)
        if predictor is None:
            predictor = LNNPredictor.from_registry(
                registry=model_registry,
                model_name=body.model_name,
                use_amp=True,
                auto_device=True,
            )
            model_cache.put(body.model_name, predictor)

        try:
            result = predictor.predict(
                input_data=body.input_data,
                return_confidence=True,
            )
        except (ValueError, KeyError, TypeError, OSError, RuntimeError, AttributeError) as model_err:
            safe = safe_error_message(
                model_err,
                context=f"lnn.predict_uncertain_inference[{body.model_name}]",
            )
            logger.error(
                "Model inference error | model=%s | error_id=%s | exc=%s",
                body.model_name,
                safe.get("error_id"),
                model_err,
                exc_info=True,
            )
            return error(
                code=ErrorCode.INTERNAL_ERROR,
                message=safe["message"],
                detail=safe.get("detail"),
            )

        if not isinstance(result, PredictionResult):
            result = PredictionResult(
                value=result,
                confidence=0.0,
                inference_time=0.0,
            )

        value = result.value
        if hasattr(value, "tolist"):
            value = value.tolist()
        if isinstance(value, list) and len(value) == 1:
            value = value[0]

        if isinstance(value, list):
            prediction = float(np.mean(value))
            std = float(np.std(value))
        else:
            prediction = float(value)
            std = float(result.confidence) if result.confidence is not None else 0.0

        mean = abs(prediction) if prediction != 0 else 1.0
        ratio = std / mean
        clamped_ratio = min(max(ratio, 0.0), 1.0)
        confidence = 1.0 - clamped_ratio

        response = UncertaintyResponse(
            prediction=prediction,
            uncertainty=std,
            confidence=confidence,
        )

        return success(
            data=response.model_dump(),
            message="Uncertainty prediction completed successfully",
        )

    except KeyError:
        return error(
            code=ErrorCode.NOT_FOUND,
            message=f"Model '{body.model_name}' not found in registry",
        )
    except (ValueError, KeyError, TypeError, OSError, RuntimeError, AttributeError) as e:
        safe = safe_error_message(
            e,
            context=f"lnn.predict_uncertain[{body.model_name}]",
        )
        return error(
            code=ErrorCode.INTERNAL_ERROR,
            message=safe["message"],
            detail=safe.get("detail"),
        )
