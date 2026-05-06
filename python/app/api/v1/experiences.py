import logging

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.core.response import ErrorCode, error, success
from app.services.experience_extractor import ExperienceExtractor
from app.services.experience_store import ExperienceStore

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/experiences", tags=["Experience Replay"])

experience_store = ExperienceStore()
experience_extractor = ExperienceExtractor()


class SaveExperienceRequest(BaseModel):
    task_id: str = Field(..., description="任务 ID")
    process: str = Field(..., description="工序标识")
    parameters: dict = Field(default_factory=dict, description="工艺参数")
    metrics: dict = Field(default_factory=dict, description="指标数据")
    validation_result: dict = Field(default_factory=dict, description="验证结果")
    metadata: dict = Field(default_factory=dict, description="元数据")


class SearchExperienceRequest(BaseModel):
    process: str | None = Field(default=None, description="工序筛选")
    machine: str | None = Field(default=None, description="机床筛选")
    parameters: dict | None = Field(default=None, description="参数匹配")
    metrics: dict | None = Field(default=None, description="指标匹配")
    vibration_features: dict | None = Field(default=None, description="振动特征")
    top_k: int = Field(default=5, description="返回数量")


class ReliabilityResponse(BaseModel):
    experience_id: str = Field(..., description="经验 ID")


@router.get("/summary")
async def get_summary():
    try:
        experiences = experience_store.list_experiences(limit=1000)
        total = len(experiences)

        process_counts = {}
        for exp in experiences:
            process = exp.get("process", "unknown")
            process_counts[process] = process_counts.get(process, 0) + 1

        return success(
            data={
                "total_experiences": total,
                "process_distribution": process_counts,
            },
            message="Experience summary retrieved successfully",
        )
    except Exception as e:
        logger.error("Failed to get experience summary: %s", e)
        return error(code=ErrorCode.INTERNAL_ERROR, message=f"Failed to get summary: {e!s}")


@router.post("/save")
async def save_experience(request: SaveExperienceRequest):
    try:
        experience = {
            "parameters": request.parameters,
            "metrics": request.metrics,
            "validation_result": request.validation_result,
            "metadata": request.metadata,
        }

        result = experience_store.save_experience(
            task_id=request.task_id,
            experience=experience,
            process=request.process,
        )

        return success(data=result, message="Experience saved successfully")
    except Exception as e:
        logger.error("Failed to save experience: %s", e)
        return error(code=ErrorCode.INTERNAL_ERROR, message=f"Failed to save experience: {e!s}")


@router.post("/search")
async def search_experiences(request: SearchExperienceRequest):
    try:
        query = {}
        if request.process:
            query["process"] = request.process
        if request.parameters:
            query["parameters"] = request.parameters
        if request.metrics:
            query["metrics"] = request.metrics
        if request.vibration_features:
            query["vibration_features"] = request.vibration_features
        if request.machine:
            query["machine"] = request.machine

        result = experience_store.search_with_ground_truth(
            query=query,
            top_k=request.top_k,
            include_ground_truth=True,
        )

        return success(data=result, message="Search completed")
    except Exception as e:
        logger.error("Failed to search experiences: %s", e)
        return error(code=ErrorCode.INTERNAL_ERROR, message=f"Search failed: {e!s}")


@router.get("/{experience_id}/reliability")
async def get_experience_reliability(experience_id: str):
    try:
        reliability = experience_store.get_experience_reliability(experience_id)
        reliability["experience_id"] = experience_id

        return success(data=reliability, message="Reliability retrieved successfully")
    except Exception as e:
        logger.error("Failed to get reliability: %s", e)
        return error(code=ErrorCode.INTERNAL_ERROR, message=f"Failed to get reliability: {e!s}")


@router.get("/{experience_id}")
async def get_experience(experience_id: str):
    try:
        exp = experience_store.get_experience(experience_id)
        if not exp:
            return error(code=ErrorCode.NOT_FOUND, message="Experience not found")

        from app.services.experience_extractor import asdict_experience as exp_to_dict
        if hasattr(exp, '__dataclass_fields__'):
            from dataclasses import asdict
            exp_dict = asdict(exp)
        else:
            exp_dict = exp

        return success(data=exp_dict, message="Experience retrieved successfully")
    except Exception as e:
        logger.error("Failed to get experience: %s", e)
        return error(code=ErrorCode.INTERNAL_ERROR, message=f"Failed to get experience: {e!s}")
