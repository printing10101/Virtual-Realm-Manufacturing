import logging

import numpy as np
from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.core.response import ErrorCode, error, success
from app.services.ground_truth_adapter import BoschGroundTruthAdapter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/ground-truth", tags=["Ground Truth"])

ground_truth_adapter = BoschGroundTruthAdapter()


class SimilarCasesRequest(BaseModel):
    vibration_features: dict = Field(..., description="振动特征向量")
    top_k: int = Field(default=5, description="返回相似案例数量")


class ValidateExperienceRequest(BaseModel):
    experience: dict = Field(..., description="经验数据")
    process: str = Field(..., description="工序标识")


@router.get("/summary")
async def get_ground_truth_summary():
    try:
        records = ground_truth_adapter.load_ground_truth()
        statistics = ground_truth_adapter.get_statistics()

        return success(
            data=statistics,
            message="Ground truth summary retrieved successfully",
        )
    except Exception as e:
        logger.error("Failed to get ground truth summary: %s", e)
        return error(
            code=ErrorCode.INTERNAL_ERROR,
            message=f"Failed to get ground truth summary: {e!s}",
        )


@router.get("/process/{process}")
async def get_process_summary(process: str, machine: str | None = None, timeframe: str | None = None):
    try:
        result = ground_truth_adapter.get_process_success_rate(
            process=process,
            machine=machine,
            timeframe=timeframe,
        )

        return success(data=result, message="Process success rate retrieved successfully")
    except Exception as e:
        logger.error("Failed to get process summary: %s", e)
        return error(
            code=ErrorCode.INTERNAL_ERROR,
            message=f"Failed to get process summary: {e!s}",
        )


@router.get("/trend/{process}")
async def get_process_trend(process: str, machine: str = "M01"):
    try:
        trend = ground_truth_adapter.get_time_trend(
            process=process,
            machine=machine,
        )

        return success(data=trend, message="Process trend retrieved successfully")
    except Exception as e:
        logger.error("Failed to get process trend: %s", e)
        return error(
            code=ErrorCode.INTERNAL_ERROR,
            message=f"Failed to get process trend: {e!s}",
        )


@router.post("/similar")
async def find_similar_cases(request: SimilarCasesRequest):
    try:
        results = ground_truth_adapter.find_similar_cases(
            query_features=request.vibration_features,
            top_k=request.top_k,
        )

        return success(data=results, message="Similar cases found successfully")
    except Exception as e:
        logger.error("Failed to find similar cases: %s", e)
        return error(
            code=ErrorCode.INTERNAL_ERROR,
            message=f"Failed to find similar cases: {e!s}",
        )


@router.post("/validate")
async def validate_experience(request: ValidateExperienceRequest):
    try:
        result = ground_truth_adapter.validate_experience(
            experience=request.experience,
            process=request.process,
        )

        return success(data=result, message="Validation completed successfully")
    except Exception as e:
        logger.error("Failed to validate experience: %s", e)
        return error(
            code=ErrorCode.INTERNAL_ERROR,
            message=f"Failed to validate experience: {e!s}",
        )
