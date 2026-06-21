"""CadQuery generator wrapper for CAD generation."""

from __future__ import annotations

import asyncio
import json
import logging
import struct
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

import cadquery as cq

from app.cad.advanced_features import AdvancedFeatureBuilder

logger = logging.getLogger(__name__)


class CadQueryError(Exception):
    """Base exception for CadQuery generation errors."""


class CadQueryScriptError(CadQueryError):
    """Raised when executing a CadQuery script fails."""


class CadQueryExportError(CadQueryError):
    """Raised when exporting a model file fails."""


class CadQueryGenerator:
    """CadQuery-based 3D model generator."""

    def __init__(self) -> None:
        self._initialized = True
        logger.info("CadQueryGenerator initialized")

    async def extract_geometry_params_from_views(
        self, views: dict[str, str]
    ) -> dict[str, Any]:
        """Extract geometry parameters from three-view image paths.

        Reads image dimensions from file headers (PNG/JPEG/GIF/BMP) to
        inform the default geometry.  Full computer-vision-based extraction
        of shape type and dimensions from engineering drawings requires a
        dedicated ML pipeline and is not yet implemented.
        """
        logger.info("Extracting geometry params from views: %s", list(views.keys()))

        await asyncio.sleep(0)

        image_sizes: dict[str, tuple[int, int]] = {}
        for view_name, view_path in views.items():
            view_file = Path(view_path)
            if not view_file.exists():
                logger.warning("View file not found: %s (%s)", view_name, view_path)
                continue
            try:
                width, height = _get_image_dimensions(view_file)
                image_sizes[view_name] = (width, height)
                logger.debug(
                    "View %s loaded: %s (%dx%d)",
                    view_name,
                    view_path,
                    width,
                    height,
                )
            except (OSError, ValueError) as e:
                logger.warning(
                    "Failed to read view %s (%s): %s", view_name, view_path, e
                )

        if not image_sizes:
            logger.warning(
                "Could not read any view images; using default geometry params"
            )

        length = 50.0
        width = 30.0
        height = 20.0
        if "front" in image_sizes:
            length = max(image_sizes["front"][0] / 10.0, 10.0)
            height = max(image_sizes["front"][1] / 10.0, 10.0)
        if "top" in image_sizes:
            width = max(image_sizes["top"][1] / 10.0, 10.0)
        if "left" in image_sizes:
            width = max(image_sizes["left"][0] / 10.0, 10.0)

        params: dict[str, Any] = {
            "shape_type": "box",
            "dimensions": {
                "length": round(length, 1),
                "width": round(width, 1),
                "height": round(height, 1),
            },
            "position": {"x": 0, "y": 0, "z": 0},
        }

        logger.info("Extracted params: %s", params)
        return params

    async def generate_script_from_params(
        self,
        params: dict[str, Any],
        library_matches: list[dict[str, Any]] | None = None,
    ) -> str:
        """Generate a CadQuery Python script from geometry parameters."""
        logger.info(
            "Generating script from params: shape=%s, matches=%d",
            params.get("shape_type", "unknown"),
            len(library_matches) if library_matches else 0,
        )

        await asyncio.sleep(0)

        if library_matches:
            best_match = library_matches[0]
            cached_script = best_match.get("cadquery_script", "")
            if cached_script:
                logger.info("Using cached script from model library")
                return cached_script

        if params.get("dimensions") is None:
            raise ValueError(
                "参数错误：dimensions 不能为 None。请确保传入的参数字典中包含有效的 dimensions 字段，"
                "例如 {'length': 50, 'width': 30, 'height': 20}。"
            )

        shape_type, dimensions, position = _unpack_generation_params(params)

        script = _build_shape_script(shape_type, dimensions, position)
        logger.info("Generated CadQuery script (%d chars)", len(script))
        return script

    async def execute_and_export(
        self, script: str, task_id: str, output_format: str
    ) -> str:
        """Execute a CadQuery script and export the resulting model."""
        logger.info(
            "Executing script for task %s (format=%s, script_len=%d)",
            task_id,
            output_format,
            len(script),
        )

        output_dir = Path(tempfile.gettempdir()) / "cadquery_output"
        output_dir.mkdir(parents=True, exist_ok=True)

        output_path = output_dir / f"{task_id}.{output_format}"
        export_func_map = {
            "stl": "cq.exporters.export",
            "obj": "cq.exporters.export",
            "gltf": "cq.exporters.export",
            "step": "cq.exporters.export",
        }

        if output_format not in export_func_map:
            supported = ", ".join(export_func_map.keys())
            raise CadQueryExportError(
                f"CAD 模型导出失败：不支持的输出格式 '{output_format}'。支持的格式包括：{supported}。请将 output_format 参数设置为支持的格式之一后重试。"
            )

        wrapped_script = _wrap_script(script, str(output_path), output_format)

        _run_cadquery_script(wrapped_script, task_id)

        if not output_path.exists():
            raise CadQueryExportError(
                f"Export failed: output file not created at {output_path}"
            )

        logger.info(
            "Model exported: %s (%d bytes)", output_path, output_path.stat().st_size
        )
        return str(output_path)

    def generate_3d_model(self, params: dict[str, Any]) -> str:
        """Generate a 3D model from parameters and return the model path."""
        logger.info("Generating 3D model with params: %s", params)

        shape_type, dimensions, position = _unpack_generation_params(params)

        try:
            result = _build_solid(shape_type, dimensions, position)
            output_dir = Path(tempfile.gettempdir()) / "cadquery_models"
            output_dir.mkdir(parents=True, exist_ok=True)
            output_path = output_dir / f"model_{shape_type}.stl"
            cq.exporters.export(result, str(output_path))
            logger.info("3D model exported to %s", output_path)
            return str(output_path)
        except Exception as e:
            logger.error("CAD 模型生成失败: %s", e)
            raise CadQueryScriptError(
                f"CAD 模型生成失败：执行 CadQuery 脚本时出现异常。错误详情: {e}。"
                "可能原因：1) 脚本语法错误；2) 几何参数无效；"
                "3) CadQuery 版本不兼容。"
                "请检查脚本内容和几何参数，或查看日志获取详细错误信息。"
            ) from e

    def generate_with_features(
        self,
        params: dict[str, Any],
        features: list[dict[str, Any]] | None = None,
        output_format: str = "stl",
    ) -> str:
        """带高级特征的 3D 模型生成。

        Args:
            params: 同 generate_3d_model
            features: 特征列表，每项 dict 包含 type 字段：
                - "chamfer": {length, angle?, edges_selector?}
                - "fillet": {radius, edges_selector?}
                - "step": {length?, width?, height?, offset_x?, offset_y?, offset_z?}
                - "slot": {center_x, center_y, length, width, depth, axis?, surface_z?}
            output_format: 输出格式（stl/step/obj/gltf）

        Returns:
            输出文件路径
        """
        logger.info("生成带特征的 3D 模型: params=%s features=%d", params, len(features or []))

        shape_type, dimensions, position = _unpack_generation_params(params)
        base = _build_solid(shape_type, dimensions, position)

        if features:
            builder = AdvancedFeatureBuilder()
            base = builder.apply_features(base, features)

        output_dir = Path(tempfile.gettempdir()) / "cadquery_models"
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"model_{shape_type}_with_features.{output_format}"
        cq.exporters.export(base, str(output_path))
        logger.info("带特征的 3D 模型已导出: %s", output_path)
        return str(output_path)

    def generate_from_views(self, front: str, top: str, side: str) -> str:
        """Generate 3D model from three-view drawing descriptions."""
        logger.info(
            "Generating 3D model from three-view drawings (front=%s, top=%s, side=%s)",
            front[:50],
            top[:50],
            side[:50],
        )
        params = {
            "shape_type": "box",
            "dimensions": {"length": 50, "width": 30, "height": 20},
            "position": {"x": 0, "y": 0, "z": 0},
            "views": {"front": front, "top": top, "side": side},
        }
        return self.generate_3d_model(params)


def _unpack_generation_params(
    params: dict[str, Any],
) -> tuple[str, dict[str, float], dict[str, float]]:
    shape_type = params.get("shape_type", "box")
    dimensions = params.get("dimensions") or {}
    position = params.get("position", {"x": 0, "y": 0, "z": 0})
    return shape_type, dimensions, position


def _build_shape_params(
    shape_type: str,
    dimensions: dict[str, float],
) -> dict[str, Any]:
    length = dimensions.get("length", 50)
    width = dimensions.get("width", 30)
    height = dimensions.get("height", 20)

    if shape_type == "box":
        return {"method_name": "box", "method_args": [length, width, height]}
    if shape_type == "sphere":
        radius = max(length, width, height) / 2
        return {"method_name": "sphere", "method_args": [radius]}
    if shape_type == "cylinder":
        return {"method_name": "cylinder", "method_args": [height, width / 2]}
    if shape_type == "cone":
        return {"method_name": "cone", "method_args": [height, width, length]}

    logger.warning("Unknown shape type '%s', falling back to box", shape_type)
    return {"method_name": "box", "method_args": [length, width, height]}


def _build_shape_script(
    shape_type: str,
    dimensions: dict[str, float],
    position: dict[str, float],
) -> str:
    params = _build_shape_params(shape_type, dimensions)
    method_name = params["method_name"]
    args_str = ", ".join(str(a) for a in params["method_args"])
    return (
        f"result = cq.Workplane('XY').{method_name}({args_str})"
        f".translate(("
        f"{position.get('x', 0)}, "
        f"{position.get('y', 0)}, "
        f"{position.get('z', 0)}"
        f"))"
    )


def _build_solid(
    shape_type: str,
    dimensions: dict[str, float],
    position: dict[str, float],
) -> cq.Workplane:
    px = position.get("x", 0)
    py = position.get("y", 0)
    pz = position.get("z", 0)

    params = _build_shape_params(shape_type, dimensions)
    method_name = params["method_name"]
    method_args = params["method_args"]
    method = getattr(cq.Workplane("XY"), method_name)
    return method(*method_args).translate((px, py, pz))


def _wrap_script(script: str, output_path: str, output_format: str) -> str:
    export_method = {
        "stl": "exportStl",
        "obj": "exportObj",
        "gltf": "exportGltf",
        "step": "exportStep",
    }.get(output_format, "exportStl")

    return f"""
import cadquery as cq

{script}

cq.exporters.{export_method}(result, {json.dumps(output_path)})
"""


def _run_cadquery_script(script: str, task_id: str) -> None:
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".py", delete=False, encoding="utf-8"
    ) as f:
        f.write(script)
        script_path = f.name

    try:
        subprocess.run(
            [sys.executable, script_path],
            capture_output=True,
            text=True,
            check=True,
            timeout=300,
        )
        logger.debug("Script for task %s completed successfully", task_id)
    except subprocess.TimeoutExpired as e:
        raise CadQueryScriptError(
            f"Script execution timed out after {e.timeout}s (task {task_id})"
        ) from e
    except subprocess.CalledProcessError as e:
        raise CadQueryScriptError(
            f"Script execution failed (task {task_id}): {e.stderr}"
        ) from e
    finally:
        try:
            Path(script_path).unlink(missing_ok=True)
        except OSError as cleanup_err:
            # 临时脚本清理失败不应阻塞调用方，记录以便后续排查
            logger.debug(
                "Failed to cleanup cadquery script %s: %s",
                script_path,
                cleanup_err,
                exc_info=True,
            )


def _get_image_dimensions(filepath: Path) -> tuple[int, int]:
    """Return (width, height) by parsing image file headers (stdlib only).

    Supports PNG, JPEG, GIF, BMP.  Raises ValueError for unsupported formats.
    """
    with open(filepath, "rb") as f:
        header = f.read(32)

    if len(header) < 2:
        raise ValueError(
            "图像文件解析失败：文件大小不足以包含有效的图像文件头。正常图像文件至少需要 2 字节。请确认上传的是有效的图像文件（PNG/JPEG/GIF/BMP 格式），而非空文件或损坏文件。"
        )

    if header[:8] == b"\x89PNG\r\n\x1a\n":
        if len(header) < 24:
            raise ValueError(
                "PNG 图像解析失败：PNG 文件头不完整。"
                "可能原因：1) 文件传输过程中被截断；2) 文件已损坏。"
                "请确认 PNG 文件完整性（标准 PNG 文件头为 8 字节）。"
            )
        w = struct.unpack(">I", header[16:20])[0]
        h = struct.unpack(">I", header[20:24])[0]
        return w, h

    if header[:2] == b"\xff\xd8":
        f.seek(0)
        data = f.read()
        i = 2
        _iter = 0
        while i < len(data) - 9:
            _iter += 1
            if _iter > 1000:
                raise ValueError(
                    "JPEG 图像解析失败：解析循环超过最大迭代次数（1000），"
                    "可能存在损坏或恶意构造的数据。"
                )
            if data[i] != 0xFF:
                i += 1
                continue
            marker = data[i + 1]
            if 0xC0 <= marker <= 0xC2:
                h = struct.unpack(">H", data[i + 5 : i + 7])[0]
                w = struct.unpack(">H", data[i + 7 : i + 9])[0]
                return w, h
            seg_len = struct.unpack(">H", data[i + 2 : i + 4])[0]
            i += 2 + seg_len
        raise ValueError(
            "JPEG 图像解析失败：未找到 SOF（Start Of Frame）标记。"
            "可能原因：1) JPEG 文件已损坏或格式不正确；"
            "2) 文件为渐进式 JPEG 但不支持解析。"
            "请检查 JPEG 文件是否为标准基线格式，"
            "或使用图像编辑工具重新保存。"
        )

    if header[:6] in (b"GIF87a", b"GIF89a"):
        w = struct.unpack("<H", header[6:8])[0]
        h = struct.unpack("<H", header[8:10])[0]
        return w, h

    if header[:2] == b"BM":
        if len(header) < 26:
            raise ValueError(
                "BMP 图像解析失败：BMP 文件头不完整。可能原因：1) 文件传输过程中被截断；2) 文件已损坏。标准 BMP 文件头至少 26 字节。请确认 BMP 文件完整性。"
            )
        w = struct.unpack("<I", header[18:22])[0]
        h = struct.unpack("<I", header[22:26])[0]
        return w, h

    raise ValueError(
        f"图像格式解析失败：不支持的图像格式。"
        f"文件头标识: {header[:4]!r}。"
        "支持的图像格式包括：PNG、JPEG、BMP。"
        "请将图像转换为支持的格式后重试。"
    )
