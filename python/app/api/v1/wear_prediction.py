from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.core.response import ErrorCode, error, success
from app.services.tool_wear_predictor import ToolWearPredictor

router = APIRouter(prefix="/api/v1/wear", tags=["Tool Wear Prediction"])

predictor = ToolWearPredictor()


class WearPredictRequest(BaseModel):
    cutting_speed: float = Field(default=150.0, description="切削速度 (m/min)")
    feed_rate: float = Field(default=0.2, description="进给量 (mm/rev)")
    depth_of_cut: float = Field(default=1.5, description="切削深度 (mm)")
    material_type: str = Field(default="steel_45", description="材料类型")
    tool_type: str = Field(default="carbide", description="刀具类型")
    current_wear: float = Field(default=0.0, description="当前磨损量 (mm)")
    time_step: float = Field(default=1.0, description="时间步长 (min)")
    max_time: float = Field(default=300.0, description="最大预测时间 (min)")


class RemainingLifeRequest(BaseModel):
    current_wear: float = Field(default=0.1, description="当前磨损量 (mm)")
    cutting_speed: float = Field(default=150.0, description="切削速度 (m/min)")
    feed_rate: float = Field(default=0.2, description="进给量 (mm/rev)")
    depth_of_cut: float = Field(default=1.5, description="切削深度 (mm)")
    material_type: str = Field(default="steel_45", description="材料类型")
    tool_type: str = Field(default="carbide", description="刀具类型")


class SuggestRequest(BaseModel):
    current_wear: float = Field(default=0.15, description="当前磨损量 (mm)")
    remaining_life: float = Field(default=50.0, description="剩余寿命 (min)")
    cutting_speed: float = Field(default=150.0, description="切削速度 (m/min)")
    feed_rate: float = Field(default=0.2, description="进给量 (mm/rev)")
    depth_of_cut: float = Field(default=1.5, description="切削深度 (mm)")
    coolant_flow: float = Field(default=10.0, description="冷却液流量 (L/min)")
    material_type: str = Field(default="steel_45", description="材料类型")
    tool_type: str = Field(default="carbide", description="刀具类型")


class CalibrateRequest(BaseModel):
    measured_wear: float = Field(default=0.1, description="实测磨损量 (mm)")
    elapsed_time: float = Field(default=30.0, description="已加工时间 (min)")
    cutting_speed: float = Field(default=150.0, description="切削速度 (m/min)")
    feed_rate: float = Field(default=0.2, description="进给量 (mm/rev)")
    depth_of_cut: float = Field(default=1.5, description="切削深度 (mm)")
    material_type: str = Field(default="steel_45", description="材料类型")
    tool_type: str = Field(default="carbide", description="刀具类型")


@router.post("/predict")
async def predict_wear(request: WearPredictRequest):
    try:
        params = {
            "cutting_speed": request.cutting_speed,
            "feed_rate": request.feed_rate,
            "depth_of_cut": request.depth_of_cut,
            "material_type": request.material_type,
            "tool_type": request.tool_type,
            "current_wear": request.current_wear,
            "time_step": request.time_step,
            "max_time": request.max_time,
        }
        curve = predictor.predict_wear_curve(params)
        return success(
            data=curve.to_dict(), message="Wear curve predicted successfully"
        )
    except Exception as e:
        return error(code=ErrorCode.INTERNAL_ERROR, message=f"Prediction failed: {e!s}")


@router.post("/remaining-life")
async def predict_remaining_life(request: RemainingLifeRequest):
    try:
        params = {
            "cutting_speed": request.cutting_speed,
            "feed_rate": request.feed_rate,
            "depth_of_cut": request.depth_of_cut,
            "material_type": request.material_type,
            "tool_type": request.tool_type,
        }
        remaining = predictor.predict_remaining_life(request.current_wear, params)
        threshold = predictor.get_replacement_threshold(request.material_type)
        return success(
            data={
                "remaining_life": remaining,
                "current_wear": request.current_wear,
                "replacement_threshold": threshold,
            },
            message="Remaining life predicted successfully",
        )
    except Exception as e:
        return error(code=ErrorCode.INTERNAL_ERROR, message=f"Prediction failed: {e!s}")


@router.post("/suggest")
async def suggest_adjustment(request: SuggestRequest):
    try:
        current_params = {
            "cutting_speed": request.cutting_speed,
            "feed_rate": request.feed_rate,
            "depth_of_cut": request.depth_of_cut,
            "coolant_flow": request.coolant_flow,
            "material_type": request.material_type,
            "tool_type": request.tool_type,
        }
        suggestion = predictor.suggest_parameter_adjustment(
            request.current_wear, request.remaining_life, current_params
        )
        return success(
            data=suggestion.to_dict(), message="Adjustment suggestions generated"
        )
    except Exception as e:
        return error(code=ErrorCode.INTERNAL_ERROR, message=f"Suggestion failed: {e!s}")


@router.get("/models")
async def get_supported_models():
    try:
        models = predictor.get_supported_models()
        materials = {
            key: {
                "name": val.name,
                "taylor_n": val.taylor_n,
                "taylor_C": val.taylor_C,
                "hardness_factor": val.hardness_factor,
            }
            for key, val in predictor.material_params.items()
        }
        tools = dict(predictor.tool_params.items())
        return success(
            data={
                "models": models,
                "supported_materials": materials,
                "supported_tools": tools,
            },
            message="Supported models retrieved successfully",
        )
    except Exception as e:
        return error(
            code=ErrorCode.INTERNAL_ERROR, message=f"Failed to get models: {e!s}"
        )


@router.post("/threshold")
async def get_threshold(material_type: str = "default"):
    try:
        threshold = predictor.get_replacement_threshold(material_type)
        return success(
            data={"material_type": material_type, "threshold": threshold},
            message="Replacement threshold retrieved",
        )
    except Exception as e:
        return error(
            code=ErrorCode.INTERNAL_ERROR, message=f"Failed to get threshold: {e!s}"
        )


@router.post("/calibrate")
async def calibrate_prediction(request: CalibrateRequest):
    try:
        params = {
            "cutting_speed": request.cutting_speed,
            "feed_rate": request.feed_rate,
            "depth_of_cut": request.depth_of_cut,
            "material_type": request.material_type,
            "tool_type": request.tool_type,
        }
        result = predictor.calibrate_with_measurement(
            request.measured_wear, request.elapsed_time, params
        )
        return success(data=result, message="Prediction calibrated successfully")
    except Exception as e:
        return error(
            code=ErrorCode.INTERNAL_ERROR, message=f"Calibration failed: {e!s}"
        )


@router.post("/train-uniwear")
async def train_uniwear_model(
    data_dir: str = "python/data/uniwear",
    model_type: str = "random_forest",
):
    try:
        result = predictor.train_with_uniwear_data(
            data_dir=data_dir, model_type=model_type
        )
        return success(data=result, message="Uniwear model training completed")
    except Exception as e:
        return error(
            code=ErrorCode.INTERNAL_ERROR, message=f"Uniwear training failed: {e!s}"
        )


@router.post("/predict-from-signals")
async def predict_wear_from_signal_features(
    features: dict[str, float],
    material: str = "tc4",
):
    try:
        result = predictor.predict_wear_from_signals(
            signal_features=features, material=material
        )
        return success(data=result, message="Wear predicted from signal features")
    except Exception as e:
        return error(
            code=ErrorCode.INTERNAL_ERROR, message=f"Signal prediction failed: {e!s}"
        )


@router.get("/cross-dataset-analysis")
async def get_cross_dataset_analysis():
    try:
        analysis = predictor.cross_dataset_analysis()
        return success(data=analysis, message="Cross-dataset analysis completed")
    except Exception as e:
        return error(
            code=ErrorCode.INTERNAL_ERROR,
            message=f"Cross-dataset analysis failed: {e!s}",
        )


@router.get("/uniwear-materials")
async def get_uniwear_materials():
    try:
        materials = predictor.get_uniwear_material_params()
        return success(data=materials, message="Uniwear material parameters retrieved")
    except Exception as e:
        return error(
            code=ErrorCode.INTERNAL_ERROR,
            message=f"Failed to get uniwear materials: {e!s}",
        )
