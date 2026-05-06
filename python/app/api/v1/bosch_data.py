import logging

import numpy as np
from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.core.response import ErrorCode, error, success
from app.data.bosch_cnc_loader import BoschCNCDataLoader
from app.services.dataset_manager import get_dataset_manager
from app.services.tool_wear_predictor import ToolWearPredictor

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/bosch-data", tags=["Bosch CNC Data"])

predictor = ToolWearPredictor()
dataset_manager = get_dataset_manager()


class LoadDatasetRequest(BaseModel):
    machines: list[str] | None = Field(default=None, description="机床筛选列表")
    processes: list[str] | None = Field(default=None, description="工序筛选列表")
    labels: list[str] | None = Field(default=None, description="标签筛选列表")
    timeframes: list[str] | None = Field(default=None, description="时间范围筛选列表")


class FeatureRequest(BaseModel):
    machines: list[str] | None = Field(default=None, description="机床筛选列表")
    processes: list[str] | None = Field(default=None, description="工序筛选列表")


class TrainRequest(BaseModel):
    data_dir: str = Field(default="python/data/datasets/bosch_cnc", description="数据集根目录")
    machines: list[str] | None = Field(default=None, description="机床筛选")
    processes: list[str] | None = Field(default=None, description="工序筛选")
    test_size: float = Field(default=0.2, description="测试集比例", ge=0.1, le=0.5)
    model_type: str = Field(default="random_forest", description="模型类型")


class PredictRequest(BaseModel):
    vibration_data: list[list[float]] = Field(..., description="三轴振动数据 [[x1,y1,z1], [x2,y2,z2], ...]")


@router.get("/summary")
async def get_summary():
    try:
        loader = BoschCNCDataLoader()
        summary = loader.get_dataset_summary()
        return success(data=summary, message="Dataset summary retrieved successfully")
    except Exception as e:
        logger.error("Failed to get dataset summary: %s", e)
        return error(code=ErrorCode.INTERNAL_ERROR, message=f"Failed to get summary: {e!s}")


@router.get("/machines")
async def get_machines():
    try:
        summary = dataset_manager.get_dataset_summary("bosch_cnc") or {}
        machines = summary.get("available_machines", [])
        return success(data=machines, message="Machine list retrieved")
    except Exception as e:
        logger.error("Failed to get machines: %s", e)
        return error(code=ErrorCode.INTERNAL_ERROR, message=f"Failed to get machines: {e!s}")


@router.get("/processes")
async def get_processes():
    try:
        summary = dataset_manager.get_dataset_summary("bosch_cnc") or {}
        processes = summary.get("available_processes", [])
        return success(data=processes, message="Process list retrieved")
    except Exception as e:
        logger.error("Failed to get processes: %s", e)
        return error(code=ErrorCode.INTERNAL_ERROR, message=f"Failed to get processes: {e!s}")


@router.post("/features")
async def extract_features(request: FeatureRequest):
    try:
        loader = BoschCNCDataLoader()
        samples = loader.load_dataset(
            machines=request.machines, processes=request.processes
        )

        if not samples:
            return error(code=ErrorCode.NOT_FOUND, message="No samples found matching the criteria")

        features_list: list[dict] = []
        for sample in samples[:50]:
            feats = loader.extract_features(sample["data"])
            features_list.append({
                "metadata": sample["metadata"],
                "features": {k: round(v, 6) for k, v in feats.items()},
            })

        return success(
            data={
                "sample_count": len(samples),
                "displayed_count": len(features_list),
                "results": features_list,
            },
            message="Features extracted successfully"
        )
    except Exception as e:
        logger.error("Failed to extract features: %s", e)
        return error(code=ErrorCode.INTERNAL_ERROR, message=f"Feature extraction failed: {e!s}")


@router.post("/train")
async def train_model(request: TrainRequest):
    try:
        result = predictor.train_with_bosch_data(
            data_dir=request.data_dir,
            machines=request.machines,
            processes=request.processes,
            test_size=request.test_size,
            model_type=request.model_type,
        )

        if "error" in result:
            return error(
                code=ErrorCode.INVALID_REQUEST,
                message=result["error"]
            )

        return success(data=result, message=f"Model trained successfully ({request.model_type})")
    except Exception as e:
        logger.error("Failed to train model: %s", e)
        return error(code=ErrorCode.INTERNAL_ERROR, message=f"Training failed: {e!s}")


@router.post("/predict")
async def predict_anomaly(request: PredictRequest):
    try:
        vibration_array = np.array(request.vibration_data, dtype=np.float64)

        if vibration_array.ndim == 1:
            vibration_array = vibration_array.reshape(-1, 1)
        elif vibration_array.ndim == 2 and vibration_array.shape[1] < 1:
            return error(
                code=ErrorCode.INVALID_REQUEST,
                message="Vibration data must have at least 1 channel"
            )

        result = predictor.predict_vibration_anomaly(vibration_array)
        return success(data=result, message="Prediction completed")
    except Exception as e:
        logger.error("Failed to predict anomaly: %s", e)
        return error(code=ErrorCode.INTERNAL_ERROR, message=f"Prediction failed: {e!s}")


@router.get("/baseline/{process}")
async def get_baseline(process: str, machine: str = "M01"):
    try:
        baseline = predictor.get_process_baseline(process=process, machine=machine)
        return success(data=baseline, message="Process baseline retrieved")
    except Exception as e:
        logger.error("Failed to get baseline: %s", e)
        return error(code=ErrorCode.INTERNAL_ERROR, message=f"Failed to get baseline: {e!s}")
