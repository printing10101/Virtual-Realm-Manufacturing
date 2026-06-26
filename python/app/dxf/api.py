"""DXF文件处理API接口。

提供符合RESTful规范的DXF文件上传、解析、特征提取、
3D模型转换和端到端工艺规划接口。
"""

from __future__ import annotations

import logging
import uuid
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from app.core.response import success, error, ErrorCode
from app.core.safe_errors import safe_error_message
from app.utils.utils import get_output_dir, get_upload_dir, make_temp_path, cleanup_temp_file
from app.dxf.dxf_parser import DxfParser
from app.dxf.feature_extractor import FeatureExtractor
from app.dxf.dxf_to_model import DxfToModelConverter
from app.dxf.pipeline import DxfProcessPipeline
from app.process_planning.gcode_generator import GCodeGenerator
from app.xmaker_integration import XmakerIntegration

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/dxf", tags=["DXF Processing"])

OUTPUT_DIR = get_output_dir("dxf_import")
TEMP_DIR = get_upload_dir("dxf_import")

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
    except (ValueError, TypeError, AttributeError, OSError, OverflowError) as e:
        # DXF解析涉及文件I/O + 几何数据转换，异常类型有限
        logger.error("DXF 解析失败: %s", e, exc_info=True)
        safe = safe_error_message(e, context="dxf.parse")
        return error(
            code=ErrorCode.INTERNAL,
            message=safe["message"],
            detail={"error_id": safe.get("error_id")} if safe.get("detail") else None,
        )
    finally:
        try:
            temp_path.unlink(missing_ok=True)
        except OSError as cleanup_err:
            # 临时文件清理失败不应阻塞请求返回，记录以备后续排查
            logger.debug(
                "Failed to cleanup temp DXF upload %s: %s",
                temp_path,
                cleanup_err,
                exc_info=True,
            )


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
    except (ValueError, TypeError, KeyError, AttributeError, IndexError, OSError, RuntimeError) as e:
        # 特征提取涉及几何计算 + ezdxf 实体遍历，异常类型有限
        logger.error("DXF 特征提取失败: %s", e, exc_info=True)
        safe = safe_error_message(e, context="dxf.features")
        return error(
            code=ErrorCode.INTERNAL,
            message=safe["message"],
            detail={"error_id": safe.get("error_id")} if safe.get("detail") else None,
        )
    finally:
        try:
            temp_path.unlink(missing_ok=True)
        except OSError as cleanup_err:
            # 临时文件清理失败不应阻塞请求返回，记录以备后续排查
            logger.debug(
                "Failed to cleanup temp DXF upload %s: %s",
                temp_path,
                cleanup_err,
                exc_info=True,
            )


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
    except (ValueError, TypeError, KeyError, AttributeError, OSError, RuntimeError, TimeoutError) as e:
        # 管道处理涉及多阶段流程控制
        logger.error("DXF 管道处理失败: %s", e, exc_info=True)
        safe = safe_error_message(e, context="dxf.pipeline")
        return error(
            code=ErrorCode.INTERNAL,
            message=safe["message"],
            detail={"error_id": safe.get("error_id")} if safe.get("detail") else None,
        )
    finally:
        try:
            temp_path.unlink(missing_ok=True)
        except OSError as cleanup_err:
            # 临时文件清理失败不应阻塞请求返回，记录以备后续排查
            logger.debug(
                "Failed to cleanup temp DXF upload %s: %s",
                temp_path,
                cleanup_err,
                exc_info=True,
            )


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
    except (ValueError, TypeError, KeyError, AttributeError, OSError, RuntimeError, OverflowError) as e:
        # STL 转换依赖 cadquery + OCCT，涉及几何计算和文件 I/O
        logger.error("DXF 转 STL 模型失败: %s", e, exc_info=True)
        safe = safe_error_message(e, context="dxf.model.stl")
        return error(
            code=ErrorCode.INTERNAL,
            message=safe["message"],
            detail={"error_id": safe.get("error_id")} if safe.get("detail") else None,
        )
    finally:
        try:
            temp_path.unlink(missing_ok=True)
        except OSError as cleanup_err:
            # 临时文件清理失败不应阻塞请求返回，记录以备后续排查
            logger.debug(
                "Failed to cleanup temp DXF upload %s: %s",
                temp_path,
                cleanup_err,
                exc_info=True,
            )


def _sanitize_filename(file_name: str) -> str:
    """严格净化文件名，防止路径遍历攻击。

    净化规则（任何一条不满足即视为无效输入，返回空字符串）：
    1. 输入必须为非空字符串；
    2. 禁止包含路径分隔符（/ 或 \\）；
    3. 禁止包含 ".." 序列（任意父目录引用均被拒绝）；
    4. 通过 pathlib.Path.name 提取纯文件名后不得为空。

    Args:
        file_name: 用户传入的原始文件名。

    Returns:
        净化后的纯文件名；无效输入返回空字符串。
    """
    # [路径遍历修复] 输入类型与空值检查
    if not file_name or not isinstance(file_name, str):
        return ""
    # [路径遍历修复] 明确拒绝包含路径分隔符的输入
    if "/" in file_name or "\\" in file_name:
        return ""
    # [路径遍历修复] 明确拒绝包含 ".." 序列的输入
    if ".." in file_name:
        return ""
    # [路径遍历修复] 防御性编程：使用 Path.name 提取纯文件名
    safe_name = Path(file_name).name
    if not safe_name:
        return ""
    return safe_name


@router.get("/model/download/{file_name}")
async def download_model(file_name: str):
    """下载生成的3D模型文件。

    [路径遍历修复] 增加了双重路径验证：
    1. 通过 _sanitize_filename 拒绝包含路径分隔符或 ".." 的输入；
    2. 通过 resolve() + is_relative_to() 确保最终路径严格位于 OUTPUT_DIR 内。
    """
    # [路径遍历修复] 第一层：用户输入净化
    safe_name = _sanitize_filename(file_name)
    if not safe_name:
        raise HTTPException(status_code=400, detail="无效的文件名")

    # [路径遍历修复] 第二层：解析为绝对路径并验证在允许目录内
    allowed_dir = OUTPUT_DIR.resolve()
    file_path = (OUTPUT_DIR / safe_name).resolve()
    if not file_path.is_relative_to(allowed_dir):
        raise HTTPException(status_code=400, detail="无效的文件路径")

    # 保留原有的文件存在性检查
    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"文件不存在: {safe_name}")

    # 保留原有的媒体类型判断逻辑
    media_type = "application/octet-stream"
    if safe_name.endswith(".stl"):
        media_type = "model/stl"
    elif safe_name.endswith(".step"):
        media_type = "model/step"

    # 保留原有的 FileResponse 返回机制
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
    except (ValueError, TypeError, KeyError, AttributeError, OSError) as e:
        # 校验端点对任何解析/几何异常均返回统一的"无效"响应
        logger.warning("DXF 校验失败: %s", e, exc_info=True)
        safe = safe_error_message(e, context="dxf.validate")
        return success(data={
            "valid": False,
            "issues": ["文件解析失败，请检查DXF格式是否正确"],
            "error_id": safe.get("error_id"),
        })
    finally:
        try:
            temp_path.unlink(missing_ok=True)
        except OSError as cleanup_err:
            # 临时文件清理失败不应阻塞请求返回，记录以备后续排查
            logger.debug(
                "Failed to cleanup temp DXF upload %s: %s",
                temp_path,
                cleanup_err,
                exc_info=True,
            )


# ==================== XM-100 五轴加工端点 ====================

_xmaker_client = XmakerIntegration()


@router.post("/xm100/generate", response_model=dict)
async def generate_xm100_gcode(
    file: UploadFile = File(...),
    material: str = Form(default="45#钢"),
    part_type: str = Form(default="general"),
    enable_five_axis: bool = Form(default=True),
    strategy: str = Form(default="lead_angle"),
):
    """为 XM-100 五轴机床生成 G 代码。

    上传 DXF 文件，使用 xmachine_xm100 后处理器生成五轴联动 G 代码。
    支持三种五轴策略：lead_angle（引导角）、tilt_angle（倾斜角）、interpolation（插值）。
    """
    _validate_dxf_file(file)
    temp_path = _save_upload(file)

    try:
        # 解析 DXF
        parse_result = _dxf_parser.parse(temp_path)
        feature_result = _feature_extractor.extract(parse_result)

        # 生成五轴 G 代码
        generator = GCodeGenerator(controller_type="xmachine_xm100")
        from app.process_planning.process_planner import ProcessPlanner

        planner = ProcessPlanner()
        plan_result = planner.plan(
            features=feature_result,
            material=material,
            part_type=part_type,
        )

        gcode_result = generator.generate(
            operation_plan=plan_result.operation_plan,
            material=material,
        )

        if not gcode_result.success:
            return error(
                code=ErrorCode.INTERNAL,
                message=f"G 代码生成失败: {'; '.join(gcode_result.errors)}",
            )

        # 保存 G 代码文件
        output_path = OUTPUT_DIR / f"{uuid.uuid4().hex}_xm100.gcode"
        output_path.write_text(gcode_result.program_text, encoding="utf-8")

        return success(data={
            "file_name": output_path.name,
            "file_size": output_path.stat().st_size,
            "controller_type": "xmachine_xm100",
            "five_axis_enabled": enable_five_axis,
            "strategy": strategy,
            "total_lines": gcode_result.total_lines,
            "estimated_time_min": gcode_result.estimated_cycle_time_min,
            "download_url": f"/api/dxf/model/download/{output_path.name}",
        })
    except (ValueError, TypeError, KeyError, AttributeError, OSError, RuntimeError) as e:
        # G代码生成涉及数据解析和流程控制
        logger.error("XM-100 G代码生成失败: %s", e, exc_info=True)
        safe = safe_error_message(e, context="dxf.xm100.generate")
        return error(
            code=ErrorCode.INTERNAL,
            message=safe["message"],
            detail={"error_id": safe.get("error_id")} if safe.get("detail") else None,
        )
    finally:
        try:
            temp_path.unlink(missing_ok=True)
        except OSError as cleanup_err:
            logger.debug(
                "Failed to cleanup temp DXF upload %s: %s",
                temp_path,
                cleanup_err,
                exc_info=True,
            )


@router.post("/xm100/upload", response_model=dict)
async def upload_to_xmaker(
    file: UploadFile = File(...),
    job_name: str = Form(default=""),
):
    """上传 G 代码到 Xmaker 平台。

    上传 G 代码文件到 Xmaker 云平台，返回文件 ID 和下载链接。
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="文件名不能为空")

    ext = Path(file.filename).suffix.lower()
    if ext not in {".gcode", ".nc", ".tap"}:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的文件格式: {ext}。请上传 .gcode/.nc/.tap 格式文件。",
        )

    # 文件大小校验（50MB）
    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"文件大小({len(content) / 1024 / 1024:.1f}MB)超过限制({MAX_FILE_SIZE / 1024 / 1024:.0f}MB)。",
        )
    if len(content) == 0:
        raise HTTPException(status_code=400, detail="文件内容为空")

    # 写入临时文件
    temp_path = TEMP_DIR / f"{uuid.uuid4().hex}_{file.filename}"
    temp_path.write_bytes(content)

    try:
        upload_result = _xmaker_client.upload_gcode(
            file_path=temp_path,
            job_name=job_name or temp_path.stem,
        )

        if not upload_result.success:
            return error(
                code=ErrorCode.INTERNAL,
                message=f"上传失败: {upload_result.error_message}",
            )

        return success(data={
            "file_id": upload_result.file_id,
            "file_url": upload_result.file_url,
            "upload_time_ms": upload_result.upload_time_ms,
        })
    except (OSError, RuntimeError, TimeoutError, ValueError, TypeError) as e:
        # 上传涉及文件 I/O 和网络请求
        logger.error("XM-100 上传失败: %s", e, exc_info=True)
        safe = safe_error_message(e, context="dxf.xm100.upload")
        return error(
            code=ErrorCode.INTERNAL,
            message=safe["message"],
            detail={"error_id": safe.get("error_id")} if safe.get("detail") else None,
        )
    finally:
        try:
            temp_path.unlink(missing_ok=True)
        except OSError as cleanup_err:
            logger.debug(
                "Failed to cleanup temp upload %s: %s",
                temp_path,
                cleanup_err,
                exc_info=True,
            )


@router.get("/xm100/status", response_model=dict)
async def get_xm100_status(machine_id: str = "default"):
    """获取 XM-100 机床状态。

    查询指定机床的实时状态，包括加工进度、剩余时间、错误信息等。
    """
    try:
        status_info = _xmaker_client.get_machine_status(machine_id)

        return success(data={
            "machine_id": machine_id,
            "status": status_info.status.value,
            "current_job_id": status_info.current_job_id,
            "progress_percent": status_info.progress_percent,
            "elapsed_time_sec": status_info.elapsed_time_sec,
            "remaining_time_sec": status_info.remaining_time_sec,
            "current_line": status_info.current_line,
            "total_lines": status_info.total_lines,
            "error_code": status_info.error_code,
            "error_message": status_info.error_message,
        })
    except (OSError, RuntimeError, TimeoutError, ValueError, TypeError, KeyError, AttributeError) as e:
        # 获取机床状态涉及网络请求和数据解析
        logger.error("获取 XM-100 机床状态失败: %s", e, exc_info=True)
        safe = safe_error_message(e, context="dxf.xm100.status")
        return error(
            code=ErrorCode.INTERNAL,
            message=safe["message"],
            detail={"error_id": safe.get("error_id")} if safe.get("detail") else None,
        )
