import os
import asyncio
import json
from pathlib import Path
from typing import Optional
from datetime import datetime

import aiofiles
from fastapi import APIRouter, UploadFile, File, Form
from fastapi.responses import FileResponse

from app.core.response import success, error, ErrorCode
from app.core.exceptions import CADGenerationError
from app.models.schemas import TaskStatus, ThreeViewTaskRequest, CadQueryRequest
from app.cad.task_db import task_db
from app.cad.cadquery_gen import CadQueryGenerator
from app.config import config

router = APIRouter(prefix="/api/cad", tags=["CAD"])

UPLOAD_DIR = Path(config.storage.output_dir) / "uploads"
MODEL_DIR = Path(config.storage.output_dir) / "models"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
MODEL_DIR.mkdir(parents=True, exist_ok=True)

cadquery_gen = CadQueryGenerator()


@router.post("/three-view-to-3d")
async def three_view_to_3d(
    front_view: UploadFile = File(..., description="正视图"),
    top_view: UploadFile = File(..., description="俯视图"),
    left_view: UploadFile = File(..., description="左视图"),
    output_format: str = Form(default="stl", description="输出格式")
):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    front_path = UPLOAD_DIR / f"{timestamp}_front.{front_view.filename.split('.')[-1]}"
    top_path = UPLOAD_DIR / f"{timestamp}_top.{top_view.filename.split('.')[-1]}"
    left_path = UPLOAD_DIR / f"{timestamp}_left.{left_view.filename.split('.')[-1]}"
    
    async with aiofiles.open(front_path, 'wb') as f:
        await f.write(await front_view.read())
    async with aiofiles.open(top_path, 'wb') as f:
        await f.write(await top_view.read())
    async with aiofiles.open(left_path, 'wb') as f:
        await f.write(await left_view.read())
    
    views = {
        'front': str(front_path),
        'top': str(top_path),
        'left': str(left_path)
    }
    
    task_id = task_db.create_task("three_view", views)
    
    asyncio.create_task(process_three_view_task(task_id, views, output_format))
    
    return success(
        data={
            "task_id": task_id,
            "status": TaskStatus.PENDING,
            "message": "三视图转3D任务已创建"
        }
    )


@router.post("/cadquery")
async def cadquery_generate(request: CadQueryRequest):
    task_id = task_db.create_task("cadquery", {})
    
    task_db.update_task_status(
        task_id, 
        status='running',
        progress=10.0,
        cadquery_script=request.script
    )
    
    asyncio.create_task(process_cadquery_task(task_id, request.script, request.output_format))
    
    return success(
        data={
            "task_id": task_id,
            "status": TaskStatus.PENDING,
            "message": "CadQuery 生成已加入队列"
        }
    )


@router.get("/tasks/{task_id}")
async def get_task_status(task_id: str):
    task = task_db.get_task(task_id)
    if not task:
        return error(
            code=ErrorCode.FILE_NOT_FOUND,
            message="任务不存在",
            detail=f"Task ID: {task_id}"
        )
    
    return success(data={
        "task_id": task['task_id'],
        "status": task['status'],
        "progress": task['progress'],
        "task_type": task['task_type'],
        "model_path": task.get('model_path'),
        "model_format": task.get('model_format'),
        "error_message": task.get('error_message'),
        "created_at": task['created_at'],
        "completed_at": task.get('completed_at')
    })


@router.get("/tasks")
async def list_tasks(limit: int = 50):
    tasks = task_db.list_tasks(limit)
    return success(data={
        "tasks": [
            {
                "task_id": t['task_id'],
                "status": t['status'],
                "progress": t['progress'],
                "task_type": t['task_type'],
                "created_at": t['created_at']
            }
            for t in tasks
        ]
    })


@router.get("/models/{task_id}/download")
async def download_model(task_id: str):
    task = task_db.get_task(task_id)
    if not task:
        return error(
            code=ErrorCode.FILE_NOT_FOUND,
            message="任务不存在",
            detail=f"Task ID: {task_id}"
        )
    
    if task['status'] != 'completed' or not task.get('model_path'):
        return error(
            code=ErrorCode.CAD_GENERATION_ERROR,
            message="模型尚未生成完成",
            detail=f"当前状态: {task['status']}"
        )
    
    model_path = task['model_path']
    if not Path(model_path).exists():
        return error(
            code=ErrorCode.FILE_NOT_FOUND,
            message="模型文件不存在",
            detail=f"Path: {model_path}"
        )
    
    return FileResponse(
        path=model_path,
        media_type="application/octet-stream",
        filename=Path(model_path).name
    )


async def process_three_view_task(task_id: str, views: dict, output_format: str):
    try:
        task_db.update_task_status(task_id, status='running', progress=10.0)
        
        await asyncio.sleep(0.5)
        task_db.update_task_status(task_id, status='running', progress=20.0)
        
        params = await cadquery_gen.extract_geometry_params_from_views(views)
        
        task_db.update_task_status(
            task_id,
            status='running',
            progress=40.0,
            extracted_params=json.dumps(params, ensure_ascii=False)
        )
        
        await asyncio.sleep(0.5)
        task_db.update_task_status(task_id, status='running', progress=50.0)
        
        library_matches = task_db.search_model_library(params.get('shape_type', 'unknown'))
        
        script = await cadquery_gen.generate_script_from_params(params, library_matches)
        
        task_db.update_task_status(
            task_id,
            status='running',
            progress=70.0,
            cadquery_script=script
        )
        
        await asyncio.sleep(0.5)
        task_db.update_task_status(task_id, status='running', progress=80.0)
        
        model_path = await cadquery_gen.execute_and_export(script, task_id, output_format)
        
        task_db.add_to_model_library(
            shape_type=params.get('shape_type', 'unknown'),
            parameters=json.dumps(params, ensure_ascii=False),
            cadquery_script=script
        )
        
        task_db.update_task_status(
            task_id,
            status='completed',
            progress=100.0,
            model_path=str(model_path),
            model_format=output_format
        )
        
    except Exception as e:
        task_db.update_task_status(
            task_id,
            status='failed',
            progress=0.0,
            error_message=str(e)
        )


async def process_cadquery_task(task_id: str, script: str, output_format: str):
    try:
        task_db.update_task_status(task_id, status='running', progress=50.0)
        
        await asyncio.sleep(0.5)
        task_db.update_task_status(task_id, status='running', progress=70.0)
        
        model_path = await cadquery_gen.execute_and_export(script, task_id, output_format)
        
        task_db.update_task_status(
            task_id,
            status='completed',
            progress=100.0,
            model_path=str(model_path),
            model_format=output_format
        )
        
    except Exception as e:
        task_db.update_task_status(
            task_id,
            status='failed',
            progress=0.0,
            error_message=str(e)
        )
