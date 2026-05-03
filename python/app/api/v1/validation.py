from fastapi import APIRouter, UploadFile, File, Form
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
import asyncio
import csv
import io
import json
import os

from app.core.response import success, error, ErrorCode
from app.core.container import container
from app.core.task_manager import TaskManager

router = APIRouter(prefix="/api/v1/validation", tags=["Simulation Validation"])


class RunValidationRequest(BaseModel):
    task_id: str
    validation_type: str = Field(default="comprehensive", description="online / offline / comprehensive")
    datasets: List[str] = Field(default_factory=list, description="Dataset names for offline validation")
    params: Dict[str, Any] = Field(default_factory=dict, description="Cutting parameters: v_c, f, a_p, material, etc.")
    thresholds: Optional[Dict[str, float]] = Field(
        default=None,
        description="Custom error thresholds: cutting_force, tool_life, surface_roughness"
    )


class ImportDatasetRequest(BaseModel):
    name: str
    mapping: Optional[Dict[str, str]] = Field(
        default=None,
        description="Column mapping: {'v_c': 'cutting_speed', 'f': 'feed_rate', ...}"
    )


@router.post("/run")
async def run_validation(request: RunValidationRequest):
    task_manager = container.get_service("task_manager")
    
    existing_task = task_manager.get_task(request.task_id)
    if not existing_task:
        return error(code=ErrorCode.PARAM_ERROR, message=f"Task {request.task_id} not found")
    
    task_manager.update_progress(request.task_id, 0, "Starting validation...")
    
    asyncio.create_task(
        _execute_validation(request.task_id, request.validation_type, request.datasets, request.params, request.thresholds)
    )
    
    return success(data={"task_id": request.task_id}, message="Validation task started")


@router.get("/datasets")
async def list_datasets():
    dataset_manager = container.get_service("dataset_manager")
    datasets = dataset_manager.list_datasets()
    return success(data={"datasets": datasets})


@router.post("/datasets/import")
async def import_dataset(
    file: UploadFile = File(...),
    name: str = Form(...),
    mapping: Optional[str] = Form(default=None)
):
    dataset_manager = container.get_service("dataset_manager")
    
    try:
        content = await file.read()
        content_str = content.decode("utf-8")
        
        csv_mapping = json.loads(mapping) if mapping else None
        
        import_path = os.path.join("app", "data", "datasets", f"{name}.csv")
        os.makedirs(os.path.dirname(import_path), exist_ok=True)
        
        with open(import_path, "w", encoding="utf-8", newline="") as f:
            f.write(content_str)
        
        manifest_path = os.path.join("app", "data", "datasets", "manifest.json")
        manifest = {}
        if os.path.exists(manifest_path):
            with open(manifest_path, "r", encoding="utf-8") as f:
                manifest = json.load(f)
        
        import csv
        reader = csv.DictReader(io.StringIO(content_str))
        row_count = sum(1 for _ in reader)
        
        manifest[name] = {
            "name": name,
            "source": "user_import",
            "samples": row_count,
            "materials": [],
            "operations": [],
            "description": f"User imported dataset: {name}"
        }
        
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2, ensure_ascii=False)
        
        return success(data={"name": name, "samples": row_count}, message="Dataset imported successfully")
    except Exception as e:
        return error(code=ErrorCode.INTERNAL_ERROR, message=f"Failed to import dataset: {str(e)}")


@router.get("/results/{task_id}")
async def get_validation_results(task_id: str):
    task_manager = container.get_service("task_manager")
    
    task = task_manager.get_task(task_id)
    if not task:
        return error(code=ErrorCode.NOT_FOUND, message=f"Task {task_id} not found")
    
    if task.status != TaskManager.TaskStatus.SUCCESS:
        return error(code=ErrorCode.INVALID_REQUEST, message=f"Task {task_id} is not completed (status: {task.status.value})")
    
    return success(data=task.result)


@router.get("/results/{task_id}/export")
async def export_validation_results(task_id: str):
    task_manager = container.get_service("task_manager")
    
    task = task_manager.get_task(task_id)
    if not task:
        return error(code=ErrorCode.NOT_FOUND, message=f"Task {task_id} not found")
    
    if task.status != TaskManager.TaskStatus.SUCCESS:
        return error(code=ErrorCode.INVALID_REQUEST, message=f"Task {task_id} is not completed")
    
    result = task.result
    
    output = io.StringIO()
    writer = csv.writer(output)
    
    writer.writerow(["Validation Report", task_id])
    writer.writerow([])
    
    writer.writerow(["Overall Metrics"])
    writer.writerow(["Metric", "Value"])
    writer.writerow(["MAPE", f"{result.get('overall_mape', 0):.2f}%"])
    writer.writerow(["RMSE", f"{result.get('overall_rmse', 0):.4f}"])
    writer.writerow(["R²", f"{result.get('overall_r_squared', 0):.4f}"])
    writer.writerow(["Total Samples", result.get('total_samples', 0)])
    writer.writerow(["Pass Count", result.get('pass_count', 0)])
    writer.writerow(["Fail Count", result.get('fail_count', 0)])
    writer.writerow([])
    
    if "dataset_reports" in result:
        for ds_report in result["dataset_reports"]:
            writer.writerow([f"Dataset: {ds_report.get('dataset_name', 'Unknown')}"])
            writer.writerow(["Metric", "Predicted", "Actual", "Error", "Error %", "Status", "Threshold"])
            
            details = ds_report.get("details", [])
            for detail in details:
                writer.writerow([
                    detail.get("metric_name", ""),
                    detail.get("predicted_value", ""),
                    detail.get("actual_value", ""),
                    f"{detail.get('error', 0):.4f}",
                    f"{detail.get('error_percent', 0):.2f}%",
                    detail.get("status", ""),
                    detail.get("threshold", "")
                ])
            writer.writerow([])
    
    output.seek(0)
    
    from fastapi.responses import StreamingResponse
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=validation_report_{task_id}.csv"}
    )


async def _execute_validation(task_id: str, validation_type: str, datasets: List[str],
                               params: Dict[str, Any], thresholds: Optional[Dict[str, float]] = None):
    task_manager = container.get_service("task_manager")
    validation_engine = container.get_service("validation_engine")
    
    try:
        task_manager.update_progress(task_id, 10, "Initializing validation engine...")
        
        if thresholds:
            validation_engine.set_thresholds(thresholds)
        
        result = {}
        
        if validation_type in ("online", "comprehensive"):
            task_manager.update_progress(task_id, 20, "Running online formula validation...")
            online_result = await validation_engine.run_online_validation(task_id, params)
            result["online_validation"] = online_result
        
        if validation_type in ("offline", "comprehensive"):
            if not datasets:
                datasets = ["nasa_milling_sample", "phm2010_sample", "qit_cemc_sample"]
            
            task_manager.update_progress(task_id, 40, f"Loading {len(datasets)} datasets...")
            
            dataset_reports = []
            for i, ds_name in enumerate(datasets):
                progress = 40 + int((i + 1) / len(datasets) * 40)
                task_manager.update_progress(task_id, progress, f"Validating against {ds_name}...")
                
                report = await validation_engine.run_dataset_validation(task_id, ds_name, params)
                dataset_reports.append(report)
            
            result["dataset_reports"] = dataset_reports
        
        if validation_type == "comprehensive":
            task_manager.update_progress(task_id, 85, "Generating comprehensive report...")
            
            combined_report = await validation_engine.run_comprehensive_validation(
                task_id, datasets if datasets else ["nasa_milling_sample", "phm2010_sample", "qit_cemc_sample"],
                params
            )
            result["comprehensive"] = combined_report
        
        task_manager.update_progress(task_id, 100, "Validation completed successfully")
        await task_manager.complete_task(task_id, result)
        
    except Exception as e:
        await task_manager.fail_task(task_id, f"Validation failed: {str(e)}")
