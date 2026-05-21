"""STEP文件导入API接口。

提供符合RESTful规范的STEP文件上传、解析和格式转换接口。
支持标准HTTP文件上传协议、分块上传、格式验证和错误处理。
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from app.core.response import success, error, ErrorCode
from app.step_import.step_parser import StepParser, StepParseError
from app.step_import.step_converter import (
    StepConverter,
)
from app.step_import.step_cache import get_step_cache

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/import/step", tags=["STEP Import"])

OUTPUT_DIR = Path(__file__).resolve().parent.parent.parent / "output" / "step_import"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
TEMP_DIR = OUTPUT_DIR / "_uploads"
TEMP_DIR.mkdir(parents=True, exist_ok=True)

MAX_FILE_SIZE = 50 * 1024 * 1024
ALLOWED_EXTENSIONS = {".step", ".stp"}

_step_parser = StepParser()
_step_converter = StepConverter(output_dir=OUTPUT_DIR)


class StepImportResponse(BaseModel):
    file_name: str = ""
    file_size: int = 0
    parse_time_ms: float = 0.0
    conversion_time_ms: float = 0.0
    model_info: dict = Field(default_factory=dict)
    entities: list[dict] = Field(default_factory=list)
    is_assembly: bool = False
    stl_files: list[dict] = Field(default_factory=list)
    brep_files: list[dict] = Field(default_factory=list)
    status: dict = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    cached: bool = False
    import_id: str = ""
    format: str = ""


def _validate_step_file(file: UploadFile) -> None:
    """验证上传的STEP文件格式和大小。"""
    if not file.filename:
        raise HTTPException(status_code=400, detail="文件名不能为空")

    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的文件格式: {ext}。请上传 .step 或 .stp 格式的STEP文件。",
        )


def _read_file_content(file: UploadFile) -> bytes:
    """同步读取上传文件内容。"""
    content = file.file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail=(
                f"文件大小({len(content) / 1024 / 1024:.1f}MB)"
                f"超过限制({MAX_FILE_SIZE / 1024 / 1024:.0f}MB)。"
                "请压缩模型或分割为多个文件后重试。"
            ),
        )
    return content


def _save_temp_file(content: bytes, original_name: str) -> Path:
    """将上传内容保存到临时文件。"""
    unique_id = uuid.uuid4().hex[:12]
    ext = Path(original_name).suffix.lower()
    temp_path = TEMP_DIR / f"step_{unique_id}{ext}"
    temp_path.write_bytes(content)
    return temp_path


def _parse_and_convert(
    temp_path: Path,
    file_name: str,
    file_size: int,
    output_format: str = "stl",
    precision: str = "medium",
    use_cache: bool = True,
) -> dict:
    """执行STEP解析和格式转换(在线程池中运行)。"""
    cache = get_step_cache()

    if use_cache:
        cached = cache.get(temp_path)
        if cached and cached.parse_result_data:
            logger.info("使用缓存结果: %s", file_name)
            data = dict(cached.parse_result_data)
            data["cached"] = True
            return data

    parse_result = _step_parser.parse(temp_path)
    shape = _step_parser.get_cadquery_shape(temp_path)

    batch_result = _step_converter.convert_all_entities(
        shape=shape,
        file_name=file_name,
        parse_result=parse_result,
        output_format=output_format,
        precision=precision,
    )

    conversion_ms = batch_result.total_time_ms

    status = {
        "success": batch_result.success,
        "message": "解析和转换完成" if batch_result.success else "部分转换失败",
        "entity_count": parse_result.model_info.entity_count,
        "face_count": parse_result.model_info.face_count,
        "vertex_count": parse_result.model_info.vertex_count,
        "errors": batch_result.errors,
    }

    stl_files = []
    brep_files = []
    for f in batch_result.files:
        file_info = {
            "file_name": f.file_name,
            "stl_url": f.stl_url,
            "stl_path": f.stl_path,
            "format": f.format,
            "face_count": f.face_count,
            "vertex_count": f.vertex_count,
            "file_size": f.file_size,
            "entity_index": f.entity_index,
            "entity_name": f.entity_name,
            "precision_used": f.precision_used,
        }
        if f.format == "brep":
            brep_files.append(file_info)
        else:
            stl_files.append(file_info)

    model_info_dict = {
        "volume": parse_result.model_info.volume,
        "surface_area": parse_result.model_info.surface_area,
        "bounding_box": {
            "length": parse_result.model_info.bounding_box.length,
            "width": parse_result.model_info.bounding_box.width,
            "height": parse_result.model_info.bounding_box.height,
            "min_point": list(parse_result.model_info.bounding_box.min_point),
            "max_point": list(parse_result.model_info.bounding_box.max_point),
        },
        "center_of_mass": {
            "x": parse_result.model_info.center_of_mass[0],
            "y": parse_result.model_info.center_of_mass[1],
            "z": parse_result.model_info.center_of_mass[2],
        },
        "entity_count": parse_result.model_info.entity_count,
        "face_count": parse_result.model_info.face_count,
        "vertex_count": parse_result.model_info.vertex_count,
        "edge_count": parse_result.model_info.edge_count,
        "shell_count": parse_result.model_info.shell_count,
        "solid_count": parse_result.model_info.solid_count,
    }

    entities_list = []
    for ent in parse_result.entities:
        entities_list.append(
            {
                "name": ent.name,
                "entity_index": ent.entity_index,
                "volume": ent.volume,
                "surface_area": ent.surface_area,
                "bounding_box": {
                    "length": ent.bounding_box.length,
                    "width": ent.bounding_box.width,
                    "height": ent.bounding_box.height,
                    "min_point": list(ent.bounding_box.min_point),
                    "max_point": list(ent.bounding_box.max_point),
                },
                "center_of_mass": list(ent.center_of_mass),
                "face_count": ent.face_count,
                "vertex_count": ent.vertex_count,
            }
        )

    import_id = uuid.uuid4().hex[:12]

    data = {
        "file_name": file_name,
        "file_size": file_size,
        "parse_time_ms": parse_result.parse_time_ms,
        "conversion_time_ms": conversion_ms,
        "model_info": model_info_dict,
        "entities": entities_list,
        "is_assembly": parse_result.is_assembly,
        "stl_files": stl_files,
        "brep_files": brep_files,
        "status": status,
        "warnings": parse_result.warnings,
        "cached": False,
        "import_id": import_id,
        "format": output_format,
    }

    if use_cache:
        cache.put(
            file_path=temp_path,
            stl_files=[f["file_name"] for f in stl_files],
            brep_files=[f["file_name"] for f in brep_files],
            parse_result_data=data,
        )

    return data


@router.post("")
@router.post("/")
async def import_step_file(
    request: Request,
    file: UploadFile = File(..., description="STEP文件(.step/.stp)"),
    output_format: str = Form(default="stl", description="输出格式: stl 或 brep"),
    precision: str = Form(default="medium", description="精度级别: low/medium/high"),
    use_cache: bool = Form(default=True, description="是否使用缓存"),
) -> dict:
    """导入STEP文件并进行解析和格式转换。

    接受STEP格式的CAD文件，解析几何数据并转换为系统兼容格式。

    Args:
        file: STEP文件(.step/.stp)
        output_format: 输出格式(stl/brep)
        precision: 精度级别(low/medium/high)
        use_cache: 是否启用缓存

    Returns:
        标准API响应，data中包含模型信息和STL文件URL
    """
    try:
        _validate_step_file(file)
    except HTTPException as e:
        return error(code=ErrorCode.INVALID_REQUEST, message=e.detail, detail=e.detail)

    try:
        content = await asyncio.to_thread(_read_file_content, file)
    except HTTPException as e:
        return error(code=ErrorCode.INVALID_REQUEST, message=e.detail)
    except Exception as e:
        logger.exception("文件读取失败")
        return error(code=ErrorCode.INTERNAL_ERROR, message=f"文件读取失败: {e}")

    temp_path = None
    try:
        temp_path = await asyncio.to_thread(
            _save_temp_file, content, file.filename or "unknown.step"
        )

        result_data = await asyncio.to_thread(
            _parse_and_convert,
            temp_path,
            file.filename or "unknown.step",
            len(content),
            output_format,
            precision,
            use_cache,
        )

        return success(data=result_data, message="STEP文件导入成功")

    except StepParseError as e:
        logger.exception("STEP解析失败")
        return error(
            code=ErrorCode.INVALID_REQUEST,
            message=f"STEP文件解析失败: {e}",
            suggestion="请确认文件为有效的STEP格式(AP203/AP214/AP242)，且未被损坏。",
        )
    except MemoryError:
        logger.exception("内存不足")
        return error(
            code=ErrorCode.INTERNAL_ERROR,
            message="服务器内存不足，无法处理该文件。请尝试降低精度设置或使用更小的文件。",
            recoverable=True,
        )
    except Exception as e:
        logger.exception("STEP导入未预期错误")
        return error(
            code=ErrorCode.INTERNAL_ERROR,
            message=f"导入过程中发生错误: {e}",
        )


@router.get("/output/{file_name}")
async def get_output_file(file_name: str) -> FileResponse:
    """获取转换后的输出文件(STL/BREP)。

    Args:
        file_name: 输出文件名

    Returns:
        FileResponse: 文件流
    """
    file_path = OUTPUT_DIR / file_name
    if not file_path.exists():
        return error(
            code=ErrorCode.FILE_NOT_FOUND, message=f"输出文件未找到: {file_name}"
        )

    media_type = (
        "application/sla" if file_name.endswith(".stl") else "application/octet-stream"
    )
    return FileResponse(
        path=str(file_path),
        media_type=media_type,
        filename=file_name,
    )


@router.get("/cache/stats")
async def get_cache_stats() -> dict:
    """获取STEP解析缓存统计信息。

    Returns:
        标准API响应，data中包含缓存命中率等统计
    """
    cache = get_step_cache()
    return success(data=cache.stats, message="缓存统计获取成功")


@router.delete("/cache")
async def clear_cache() -> dict:
    """清空STEP解析缓存。

    Returns:
        标准API响应
    """
    cache = get_step_cache()
    prev_size = cache.size
    cache.clear()
    return success(
        data={"cleared_entries": prev_size},
        message=f"缓存已清空，移除 {prev_size} 个条目",
    )


@router.get("/history")
async def get_import_history(limit: int = Query(default=20, ge=1, le=100)) -> dict:
    """获取STEP导入历史记录。

    扫描输出目录中的STL文件，按时间倒序返回最近导入的记录。

    Args:
        limit: 返回记录数量限制

    Returns:
        标准API响应，data中包含导入历史列表
    """

    history = []
    try:
        stl_files = sorted(
            OUTPUT_DIR.glob("*.stl"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        brep_files = {p.stem: p for p in OUTPUT_DIR.glob("*.brep")}

        seen = set()
        for stl_path in stl_files[:limit]:
            try:
                stat = stl_path.stat()
                base = stl_path.stem
                parts = base.rsplit("_", 1)
                original_name = parts[0] if len(parts) >= 2 else base

                entry = {
                    "file_name": stl_path.name,
                    "original_name": original_name,
                    "file_size": stat.st_size,
                    "created_at": stat.st_mtime,
                    "stl_url": f"/api/import/step/output/{stl_path.name}",
                    "has_brep": base in brep_files,
                }

                if base not in seen:
                    seen.add(base)
                    history.append(entry)
            except Exception:
                continue

    except Exception as e:
        logger.warning("获取导入历史失败: %s", e)

    return success(
        data={"history": history, "total": len(history)}, message="导入历史获取成功"
    )


@router.delete("/history/{file_name}")
async def delete_import_file(file_name: str) -> dict:
    """删除指定导入文件。

    Args:
        file_name: 要删除的文件名

    Returns:
        标准API响应
    """
    file_path = OUTPUT_DIR / file_name
    if not file_path.exists():
        return error(code=ErrorCode.FILE_NOT_FOUND, message=f"文件未找到: {file_name}")

    try:
        file_path.unlink()
        base = file_path.stem

        for related in OUTPUT_DIR.glob(f"{base}*"):
            try:
                related.unlink()
            except Exception:
                pass

        cache = get_step_cache()
        cache.clear()

        return success(message=f"文件 {file_name} 已删除")
    except Exception as e:
        return error(code=ErrorCode.INTERNAL_ERROR, message=f"删除失败: {e}")
