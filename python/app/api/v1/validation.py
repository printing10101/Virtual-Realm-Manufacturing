import logging

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from app.core.response import ErrorCode, error, success
from app.services.validation_calibrator import ValidationCalibrator
from app.services.validation_engine import ValidationEngine

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/validation", tags=["Process Validation"])

engine = ValidationEngine()
calibrator = ValidationCalibrator()


class CalibrateRequest(BaseModel):
    process: str | None = Field(default=None, description="Single process to calibrate (all if omitted)")
    machine: str | None = Field(default=None, description="Single machine to calibrate (all if omitted)")
    warning_k: float = Field(default=2.0, description="Standard deviation multiplier for warning threshold", ge=1.0, le=5.0)
    critical_k: float = Field(default=3.0, description="Standard deviation multiplier for critical threshold", ge=1.0, le=5.0)


class ApplyCalibrationRequest(BaseModel):
    confirmed: bool = Field(default=False, description="Confirm applying calibrated rules")


class ValidateBoschRequest(BaseModel):
    process: str = Field(..., description="Process identifier (e.g. OP03)")
    machine: str = Field(default="M01", description="Machine identifier")
    vibration_features: dict = Field(..., description="Extracted vibration features")


class ValidateTheoreticalRequest(BaseModel):
    vibration_rms: float = Field(..., description="Overall vibration RMS value (g)")
    frequency_shift_percent: float = Field(default=0.0, description="Dominant frequency shift percentage")


@router.post("/calibrate")
async def calibrate_thresholds(request: CalibrateRequest):
    """Execute threshold calibration using Bosch CNC data."""
    try:
        cal = ValidationCalibrator(
            warning_k=request.warning_k,
            critical_k=request.critical_k,
        )

        if request.process:
            result = cal.calibrate_vibration_thresholds(
                process=request.process,
                machine=request.machine,
            )
            return success(
                data=result,
                message=f"Calibration completed for {request.process}",
            )
        else:
            all_results = cal.calibrate_all_processes()
            return success(
                data=all_results,
                message=f"Calibration completed for {len(all_results)} processes",
            )
    except ValueError as e:
        logger.warning("Calibration request invalid: %s", e)
        return error(code=ErrorCode.INVALID_REQUEST, message=str(e))
    except Exception as e:
        logger.error("Calibration failed: %s", e)
        return error(code=ErrorCode.INTERNAL_ERROR, message=f"Calibration failed: {e!s}")


@router.get("/calibration/status")
async def get_calibration_status():
    """View overall calibration status."""
    try:
        rules = engine.rules
        bosch = rules.get("bosch_calibrated", {})
        process_thresholds = bosch.get("process_thresholds", {})

        status = {
            "calibration_status": bosch.get("calibration_status", "none"),
            "last_calibrated": bosch.get("last_calibrated", "never"),
            "citation": bosch.get("citation", ""),
            "process_count": len(process_thresholds),
            "processes": list(process_thresholds.keys()),
        }
        return success(data=status, message="Calibration status retrieved")
    except Exception as e:
        logger.error("Failed to get calibration status: %s", e)
        return error(code=ErrorCode.INTERNAL_ERROR, message=str(e))


@router.get("/calibration/{process}")
async def get_process_calibration(
    process: str,
    machine: str = Query(default="M01", description="Machine identifier"),
):
    """View calibration result for a specific process."""
    try:
        cal = ValidationCalibrator()
        result = cal.calibrate_vibration_thresholds(process=process, machine=machine)
        return success(data=result, message=f"Calibration data for {process}")
    except ValueError as e:
        logger.warning("Process %s not found: %s", process, e)
        return error(code=ErrorCode.NOT_FOUND, message=str(e))
    except Exception as e:
        logger.error("Failed to get calibration for %s: %s", process, e)
        return error(code=ErrorCode.INTERNAL_ERROR, message=str(e))


@router.post("/compare-rules")
async def compare_rules():
    """Compare calibrated rules with current theoretical rules."""
    try:
        cal = ValidationCalibrator()
        comparison = cal.compare_with_current_rules()
        return success(data=comparison, message="Rule comparison completed")
    except Exception as e:
        logger.error("Rule comparison failed: %s", e)
        return error(code=ErrorCode.INTERNAL_ERROR, message=str(e))


@router.post("/apply-calibration")
async def apply_calibration(request: ApplyCalibrationRequest):
    """Apply calibrated rules to the validation engine (requires confirmation)."""
    try:
        cal = ValidationCalibrator()
        result = cal.apply_calibration(confirmed=request.confirmed)
        if result["status"] == "cancelled":
            return error(
                code=ErrorCode.INVALID_REQUEST,
                message=result["message"],
            )
        return success(
            data=result,
            message=f"Calibration applied to {result['process_count']} processes",
        )
    except Exception as e:
        logger.error("Failed to apply calibration: %s", e)
        return error(code=ErrorCode.INTERNAL_ERROR, message=str(e))


@router.post("/validate-bosch")
async def validate_with_bosch(request: ValidateBoschRequest):
    """Validate using Bosch-calibrated baselines."""
    try:
        result = engine.validate_with_bosch_baseline(
            process=request.process,
            vibration_features=request.vibration_features,
            machine=request.machine,
        )
        return success(data=result, message="Bosch validation completed")
    except Exception as e:
        logger.error("Bosch validation failed: %s", e)
        return error(code=ErrorCode.INTERNAL_ERROR, message=str(e))


@router.post("/validate-theoretical")
async def validate_theoretical(request: ValidateTheoreticalRequest):
    """Validate using theoretical thresholds."""
    try:
        result = engine.validate_with_theoretical(
            vibration_rms=request.vibration_rms,
            frequency_shift_percent=request.frequency_shift_percent,
        )
        return success(data=result, message="Theoretical validation completed")
    except Exception as e:
        logger.error("Theoretical validation failed: %s", e)
        return error(code=ErrorCode.INTERNAL_ERROR, message=str(e))


@router.get("/rules")
async def get_rules():
    """Get current validation rules."""
    try:
        return success(data=engine.rules, message="Validation rules retrieved")
    except Exception as e:
        logger.error("Failed to get rules: %s", e)
        return error(code=ErrorCode.INTERNAL_ERROR, message=str(e))


@router.get("/calibration/process-status/{process}")
async def get_process_calibration_status(process: str):
    """Get calibration status and data sufficiency for a specific process."""
    try:
        status = engine.get_process_calibration_status(process)
        return success(data=status, message=f"Calibration status for {process}")
    except Exception as e:
        logger.error("Failed to get process calibration status: %s", e)
        return error(code=ErrorCode.INTERNAL_ERROR, message=str(e))