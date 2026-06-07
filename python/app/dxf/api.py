"""DXF文件处理API接口。

提供符合RESTful规范的DXF文件上传、解析、特征提取、
3D模型转换和端到端工艺规划接口。
"""

from __future__ import annotations

import logging
import uuid
from pathlib import Path, PurePosixPath

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from app.core.response import success, error, ErrorCode
from app.dxf.dxf_parser import DxfParser
from app.dxf.feature_extractor import FeatureExtractor
from app.dxf.dxf_to_model import DxfToModelConverter
from app.dxf.pipeline import DxfProcessPipeline

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/dxf", tags=["DXF Processing"])

OUTPUT_DIR = Path(__file__).resolve().parent.parent.parent / "output" / "dxf_import"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
TEMP_DIR = OUTPUT_DIR / "_uploads"
TEMP_DIR.mkdir(parents=True, exist_ok=True)

MAX_FILE_SIZE = 50 * 1024 * 1024
ALLOWED_EXTENSIONS = {".dxf"}

_dxf_parser = DxfParser()
_feature_extractor = FeatureExtractor()
_model_converter = DxfToModelConverter()
_pipeline = DxfProcessPipeline()


class DxfParseResponse(BaseModel):
    file_name: str = ""
    file_size: int = 0
    dxf_version: str = ""
    parse_time_ms: float = 0.0
    entity_counts: dict[str, int] = Field(default_factory=dict)
    total_entities: int = 0
    lines_count: int = 0
    circles_count: int = 0
    arcs_count: int = 0
    texts_count: int = 0
    dimensions_count: int = 0
    extents: dict[str, float] = Field(default_factory=dict)
    lines: list[dict] = Field(default_factory=list)
    circles: list[dict] = Field(default_factory=list)
    dimensions: list[dict] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class DxfFeatureResponse(BaseModel):
    hole_count: int = 0
    plane_count: int = 0
    overall_length: float = 0.0
    overall_width: float = 0.0
    overall_height: float = 10.0
    height_inferred: bool = True
    holes: list[dict] = Field(default_factory=list)
    planes: list[dict] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class DxfPipelineResponse(BaseModel):
    success: bool = False
    parse_result: dict = Field(default_factory=dict)
    feature_result: dict = Field(default_factory=dict)
    model_result: dict = Field(default_factory=dict)
    process_result: dict = Field(default_factory=dict)
    total_duration_ms: float = 0.0
    summary: str = ""
    stages: list[dict] = Field(default_factory=list)


def _validate_dxf_file(file: UploadFile) -> None:
    """验证上传的DXF文件格式和大小。"""
    if not file.filename:
        raise HTTPException(status_code=400, detail="文件名不能为空")

    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的文件格式: {ext}。请上传 .dxf 格式的DXF文件。",
        )


def _save_upload(file: UploadFile) -> Path:
    """保存上传文件到临时目录并返回路径。"""
    content = file.file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"文件大小({len(content) / 1024 / 1024:.1f}MB)"
                   f"超过限制({MAX_FILE_SIZE / 1024 / 1024:.0f}MB)。",
        )

    temp_path = TEMP_DIR / f"{uuid.uuid4().hex}_{file.filename}"
    temp_path.write_bytes(content)
    return temp_path


@router.post("/parse", response_model=dict)
async def parse_dxf(file: UploadFile = File(...)):
    """解析DXF文件，提取几何实体和尺寸标注。

    上传DXF文件，返回提取的直线、圆、圆弧、文字和尺寸标注列表。
    支持AutoCAD R12至2021版本的DXF格式。
    """
    _validate_dxf_file(file)
    temp_path = _save_upload(file)

    try:
        result = _dxf_parser.parse(temp_path)
        lines_data = [
            {
                "start": list(line.start),
                "end": list(line.end),
                "layer": line.layer,
                "color": line.color,
                "handle": line.handle,
            }
            for line in result.lines
        ]
        circles_data = [
            {
                "center": list(c.center),
                "radius": c.radius,
                "layer": c.layer,
                "color": c.color,
                "handle": c.handle,
            }
            for c in result.circles
        ]
        dims_data = [
            {
                "dim_type": d.dim_type,
                "measurement": d.measurement,
                "text": d.text,
                "position": list(d.position),
                "layer": d.layer,
            }
            for d in result.dimensions
        ]

        return success(data={
            "file_name": result.file_name,
            "file_size": result.file_size,
            "dxf_version": result.dxf_version,
            "parse_time_ms": round(result.parse_time_ms, 2),
            "entity_counts": result.entity_counts,
            "total_entities": result.total_entities,
            "lines_count": len(result.lines),
            "circles_count": len(result.circles),
            "arcs_count": len(result.arcs),
            "texts_count": len(result.texts),
            "dimensions_count": len(result.dimensions),
            "extents": result.extents,
            "lines": lines_data[:200],
            "circles": circles_data[:200],
            "dimensions": dims_data[:100],
            "warnings": result.warnings,
        })
    except Exception as e:
        logger.error("DXF解析失败: %s", e)
        return error(code=ErrorCode.INTERNAL, message=str(e))
    finally:
        try:
            temp_path.unlink(missing_ok=True)
        except OSError:
            pass


@router.post("/features", response_model=dict)
async def extract_features(file: UploadFile = File(...)):
    """从DXF文件中提取加工特征。

    上传DXF文件，返回孔特征和平面特征列表。
    包含孔径、位置、深度等参数信息。
    """
    _validate_dxf_file(file)
    temp_path = _save_upload(file)

    try:
        parse_result = _dxf_parser.parse(temp_path)
        feature_result = _feature_extractor.extract(parse_result)
        return success(data=feature_result.to_dict())
    except Exception as e:
        logger.error("特征提取失败: %s", e)
        return error(code=ErrorCode.INTERNAL, message=str(e))
    finally:
        try:
            temp_path.unlink(missing_ok=True)
        except OSError:
            pass


@router.post("/pipeline", response_model=dict)
async def run_dxf_pipeline(
    file: UploadFile = File(...),
    material: str = Form(default="45#钢"),
    controller_type: str = Form(default="fanuc_0i"),
    part_type: str = Form(default="general"),
    safe_z: float = Form(default=50.0),
):
    """执行完整的DXF端到端处理流水线。

    上传DXF文件，自动完成解析→特征提取→3D模型转换→工艺规划→G代码生成。
    返回包含G代码的完整处理结果。
    """
    _validate_dxf_file(file)
    temp_path = _save_upload(file)

    try:
        result = _pipeline.run(
            file_path=temp_path,
            material=material,
            controller_type=controller_type,
            part_type=part_type,
            safe_z=safe_z,
        )
        return success(data=result.to_dict())
    except Exception as e:
        logger.error("DXF流水线执行失败: %s", e)
        return error(code=ErrorCode.INTERNAL, message=str(e))
    finally:
        try:
            temp_path.unlink(missing_ok=True)
        except OSError:
            pass


@router.post("/model/stl", response_model=dict)
async def convert_to_stl(
    file: UploadFile = File(...),
):
    """将DXF文件转换为STL 3D模型。

    上传DXF文件，返回生成的STL模型文件。
    """
    _validate_dxf_file(file)
    temp_path = _save_upload(file)

    try:
        parse_result = _dxf_parser.parse(temp_path)
        feature_result = _feature_extractor.extract(parse_result)
        model_result = _model_converter.convert(feature_result)

        if not model_result.success:
            return error(
                code=ErrorCode.INTERNAL,
                message=f"模型转换失败: {'; '.join(model_result.errors)}",
            )

        output_path = OUTPUT_DIR / f"{uuid.uuid4().hex}.stl"
        _model_converter.export_stl(model_result, output_path)

        return success(data={
            "file_name": output_path.name,
            "file_size": output_path.stat().st_size,
            "download_url": f"/api/dxf/model/download/{output_path.name}",
        })
    except Exception as e:
        logger.error("STL转换失败: %s", e)
        return error(code=ErrorCode.INTERNAL, message=str(e))
    finally:
        try:
            temp_path.unlink(missing_ok=True)
        except OSError:
            pass


@router.get("/model/download/{file_name}")
async def download_model(file_name: str):
    """下载生成的3D模型文件。"""
    safe_name = PurePosixPath(file_name).name
    file_path = (OUTPUT_DIR / safe_name).resolve()
    if not file_path.is_relative_to(OUTPUT_DIR.resolve()):
        raise HTTPException(status_code=400, detail="无效的文件路径")
    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"文件不存在: {safe_name}")

    media_type = "application/octet-stream"
    if safe_name.endswith(".stl"):
        media_type = "model/stl"
    elif safe_name.endswith(".step"):
        media_type = "model/step"

    return FileResponse(
        path=str(file_path),
        media_type=media_type,
        filename=safe_name,
    )


@router.post("/validate", response_model=dict)
async def validate_dxf(file: UploadFile = File(...)):
    """验证DXF文件格式和内容。"""
    _validate_dxf_file(file)
    temp_path = _save_upload(file)

    try:
        result = _dxf_parser.parse(temp_path)
        issues = []

        if result.total_entities == 0:
            issues.append("DXF文件中未发现几何实体")

        if len(result.circles) == 0:
            issues.append("未发现圆实体，可能无法识别孔特征")

        if len(result.dimensions) == 0:
            issues.append("未发现尺寸标注，特征参数将使用默认值")

        if len(result.lines) == 0 and len(result.circles) == 0:
            issues.append("文件中无线条或圆，可能为空文件或仅含文字")

        return success(data={
            "valid": len(issues) == 0 or all("可能" in i or "建议" in i for i in issues),
            "dxf_version": result.dxf_version,
            "entity_counts": result.entity_counts,
            "total_entities": result.total_entities,
            "issues": issues,
        })
    except Exception as e:
        return success(data={
            "valid": False,
            "issues": [str(e)],
        })
    finally:
        try:
            temp_path.unlink(missing_ok=True)
        except OSError:
            pass
