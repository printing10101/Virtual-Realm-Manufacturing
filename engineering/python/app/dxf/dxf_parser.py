"""DXF文件解析模块。

基于ezdxf库实现DXF工程图文件的完整解析。
支持DXF R12、R14及AutoCAD 2000-2021版本（AC1009-AC1032）。

提取的实体类型：
- LINE: 直线段，含起点/终点坐标、图层、颜色
- CIRCLE: 圆，含圆心坐标、半径、图层、颜色
- ARC: 圆弧，含圆心坐标、半径、起止角度、图层、颜色
- TEXT/MTEXT: 文字标注，含内容、位置、高度、图层
- DIMENSION: 尺寸标注，含类型、测量值、关联实体、文本内容
- POLYLINE/LWPOLYLINE: 多段线，含顶点列表、闭合标志、图层

处理流程：
    DXF文件 ──▶ ezdxf.readfile() ──▶ 遍历modelspace ──▶ 结构化数据输出
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable, Optional

import ezdxf

from app.dxf.exceptions import DxfParseError, DxfFormatError
from app.utils.utils import safe_file_path

logger = logging.getLogger(__name__)

DXF_VERSION_MAP: dict[str, str] = {
    "AC1009": "R12",
    "AC1012": "R13",
    "AC1014": "R14",
    "AC1015": "2000",
    "AC1018": "2004",
    "AC1021": "2007",
    "AC1024": "2010",
    "AC1027": "2013",
    "AC1032": "2018",
}

SUPPORTED_VERSIONS = frozenset(DXF_VERSION_MAP.keys())


from ._entities import (
    DxfLine, DxfCircle, DxfArc, DxfText, DxfDimension,
    DxfPolyline, DxfHatch, DxfInsert, DxfSpline, DxfParseResult,
)

class DxfParser:
    """DXF文件解析器。

    基于ezdxf库解析DXF文件，提取几何实体和尺寸标注信息。
    支持AutoCAD R12至2021版本的DXF格式。

    使用方式:
        parser = DxfParser()
        result = parser.parse("path/to/part.dxf")
        for line in result.lines:
            logger.info("直线: %s -> %s", line.start, line.end)
    """

    def __init__(self) -> None:
        logger.info("DxfParser初始化完成")

    def parse(
        self,
        file_path: str | Path,
        *,
        user_id: Optional[str] = None,
        base_dir: Optional[str] = None,
    ) -> DxfParseResult:
        """解析DXF文件并返回结构化数据。

        Args:
            file_path: DXF文件路径
            user_id: 可选的用户标识，仅用于桥接层数据收集，不影响解析逻辑
            base_dir: 可选的基础目录，用于路径安全检查。如果提供，将验证 file_path 是否在 base_dir 内

        Returns:
            DxfParseResult: 包含所有提取的几何实体和元数据

        Raises:
            DxfParseError: 文件不存在或读取失败
            DxfFormatError: 格式无效或版本不支持
            ValueError: 路径安全检查失败（当提供 base_dir 时）
        """
        # 路径安全检查
        if base_dir is not None:
            try:
                path = safe_file_path(str(file_path), base_dir)
            except ValueError as e:
                raise DxfParseError(f"路径安全检查失败: {file_path}。错误: {e}") from e
        else:
            path = Path(file_path)
        
        start_time = time.time()
        result = DxfParseResult(file_name=path.name)

        if not path.exists():
            raise DxfParseError(f"DXF文件不存在: {file_path}。请检查文件路径是否正确，"
                                f"并确认文件未被移动或删除。")

        if not path.is_file():
            raise DxfParseError(f"路径不是有效的文件: {file_path}。"
                                f"请提供DXF文件的完整路径。")

        result.file_size = path.stat().st_size

        if result.file_size == 0:
            raise DxfParseError(f"DXF文件为空(0字节): {file_path}。"
                                f"请确认文件未被损坏。")

        if result.file_size > 100 * 1024 * 1024:
            result.warnings.append(
                f"DXF文件过大({result.file_size / 1024 / 1024:.1f}MB)，"
                f"解析可能需要较长时间"
            )

        try:
            doc = ezdxf.readfile(str(path))
        except ezdxf.DXFStructureError as e:
            raise DxfFormatError(
                f"DXF文件结构错误: {file_path}。文件可能已损坏或不完整。"
                f"技术详情: {e}"
            ) from e
        except ezdxf.DXFVersionError as e:
            raise DxfFormatError(
                f"DXF版本不兼容: {file_path}。支持的版本包括R12、R14、"
                f"AutoCAD 2000-2021。技术详情: {e}"
            ) from e
        except (OSError, IOError, PermissionError) as e:
            raise DxfParseError(
                f"DXF文件读取失败: {file_path}。错误: {e}"
            ) from e
        except (AttributeError, KeyError, TypeError, ValueError) as e:
            logger.error("DXF文件读取遇到未知异常: %s", file_path, exc_info=True)
            raise DxfParseError(
                f"DXF文件读取失败: {file_path}。错误: {e}"
            ) from e

        dxf_version = doc.dxfversion
        result.dxf_version = f"{dxf_version} ({DXF_VERSION_MAP.get(dxf_version, '未知')})"

        if dxf_version not in SUPPORTED_VERSIONS:
            result.warnings.append(
                f"DXF版本 {dxf_version} 不在明确支持的版本列表中，"
                f"解析可能不完全准确"
            )

        modelspace = doc.modelspace()
        self._extract_lines(modelspace, result)
        self._extract_circles(modelspace, result)
        self._extract_arcs(modelspace, result)
        self._extract_texts(modelspace, result)
        self._extract_dimensions(modelspace, result)
        self._extract_polylines(modelspace, result)
        # 高级实体（HATCH / BLOCK INSERT / SPLINE）
        self._extract_hatches(modelspace, result)
        self._extract_inserts(modelspace, result)
        self._extract_splines(modelspace, result)
        self._compute_extents(result)

        result.entity_counts = {
            "LINE": len(result.lines),
            "CIRCLE": len(result.circles),
            "ARC": len(result.arcs),
            "TEXT": len(result.texts),
            "DIMENSION": len(result.dimensions),
            "POLYLINE": len(result.polylines),
            "HATCH": len(result.hatches),
            "INSERT": len(result.inserts),
            "SPLINE": len(result.splines),
        }
        result.parse_time_ms = (time.time() - start_time) * 1000

        logger.info(
            "DXF解析完成: %s (版本=%s, 实体数=%d, 耗时=%.1fms)",
            path.name,
            dxf_version,
            result.total_entities,
            result.parse_time_ms,
        )

        if result.total_entities == 0:
            result.warnings.append("DXF文件中未发现任何可识别的几何实体")

        # 桥接层：把解析结果脱敏后落盘，供研究模块使用
        try:
            from app.research_bridge import UsageDataCollector

            collector = UsageDataCollector.get_instance()
            extra = {
                "polylines_count": len(result.polylines),
                "lines_count": len(result.lines),
                "circles_count": len(result.circles),
                "arcs_count": len(result.arcs),
                "texts_count": len(result.texts),
                "dimensions_count": len(result.dimensions),
            }
            collector.record_recognition(
                feature="dxf_parser",
                dxf_path=str(path),
                success=len(result.errors) == 0,
                latency_ms=int(result.parse_time_ms),
                user_id=user_id,
                extra=extra,
            )
            if result.errors:
                collector.record_batch_errors(
                    feature="dxf_parser",
                    error_type="parse_error",
                    error_messages=result.errors,
                    context={"file_path": str(path)},
                    user_id=user_id,
                )
        except (ImportError, AttributeError, KeyError, TypeError, ValueError) as e:
            logger.warning("bridge 数据收集失败（不影响主流程）: %s", e, exc_info=True)

        return result

    def _extract_entities(
        self,
        modelspace,
        entity_type: str,
        extractor: Callable[[Any], Any],
        target: list,
        result: DxfParseResult,
        *,
        warn_on_fail: bool = False,
        query_warn: bool = True,
    ) -> None:
        """通用实体提取模板。

        遍历 modelspace 中指定类型的实体，对每个实体调用 extractor
        进行转换；返回非 None 则追加到 target 列表。

        Args:
            modelspace: DXF modelspace 对象
            entity_type: 实体类型字符串（用于 query 与日志）
            extractor: 单个实体 → 对象 的转换函数；返回 None 表示跳过
            target: 提取结果追加到的列表
            result: 解析结果（用于添加 warnings）
            warn_on_fail: 单实体提取失败时是否往 result.warnings 添加消息
            query_warn: 查询本身异常时是否往 result.warnings 添加消息
                       （POLYLINE/LWPOLYLINE 原代码不添加，保留兼容）
        """
        try:
            for entity in modelspace.query(entity_type):
                try:
                    item = extractor(entity)
                    if item is not None:
                        target.append(item)
                except (AttributeError, KeyError, TypeError, ValueError) as e:
                    handle = getattr(entity.dxf, "handle", "<unknown>")
                    logger.warning(
                        "%s实体提取跳过(handle=%s): %s",
                        entity_type, handle, e, exc_info=True,
                    )
                    if warn_on_fail:
                        result.warnings.append(
                            f"{entity_type}实体提取失败(handle={handle}): {e}"
                        )
        except (AttributeError, TypeError) as e:
            logger.warning("%s实体查询异常: %s", entity_type, e, exc_info=True)
            if query_warn:
                result.warnings.append(f"{entity_type}实体查询异常: {e}")

    def _extract_lines(
        self, modelspace, result: DxfParseResult
    ) -> None:
        """提取所有LINE实体。"""
        self._extract_entities(
            modelspace, "LINE", DxfParser._line_to_obj, result.lines, result
        )

    @staticmethod
    def _line_to_obj(entity) -> DxfLine:
        """将单个 LINE 实体转换为 DxfLine。"""
        return DxfLine(
            start=(
                float(entity.dxf.start.x),
                float(entity.dxf.start.y),
                float(entity.dxf.start.z) if entity.dxf.hasattr("start") and hasattr(entity.dxf.start, 'z') else 0.0,
            ),
            end=(
                float(entity.dxf.end.x),
                float(entity.dxf.end.y),
                float(entity.dxf.end.z) if entity.dxf.hasattr("end") and hasattr(entity.dxf.end, 'z') else 0.0,
            ),
            layer=str(entity.dxf.layer),
            color=DxfParser._safe_color(entity),
            handle=str(entity.dxf.handle),
        )

    def _extract_circles(
        self, modelspace, result: DxfParseResult
    ) -> None:
        """提取所有CIRCLE实体。"""
        self._extract_entities(
            modelspace, "CIRCLE", DxfParser._circle_to_obj,
            result.circles, result,
        )

    @staticmethod
    def _circle_to_obj(entity) -> Optional[DxfCircle]:
        """将单个 CIRCLE 实体转换为 DxfCircle；radius<=0 返回 None。"""
        circle = DxfCircle(
            center=(
                float(entity.dxf.center.x),
                float(entity.dxf.center.y),
                float(entity.dxf.center.z) if entity.dxf.hasattr("center") and hasattr(entity.dxf.center, 'z') else 0.0,
            ),
            radius=float(entity.dxf.radius),
            layer=str(entity.dxf.layer),
            color=DxfParser._safe_color(entity),
            handle=str(entity.dxf.handle),
        )
        return circle if circle.radius > 0 else None

    def _extract_arcs(
        self, modelspace, result: DxfParseResult
    ) -> None:
        """提取所有ARC实体。"""
        self._extract_entities(
            modelspace, "ARC", DxfParser._arc_to_obj, result.arcs, result
        )

    @staticmethod
    def _arc_to_obj(entity) -> DxfArc:
        """将单个 ARC 实体转换为 DxfArc。"""
        return DxfArc(
            center=(
                float(entity.dxf.center.x),
                float(entity.dxf.center.y),
                float(entity.dxf.center.z) if entity.dxf.hasattr("center") and hasattr(entity.dxf.center, 'z') else 0.0,
            ),
            radius=float(entity.dxf.radius),
            start_angle=float(entity.dxf.start_angle),
            end_angle=float(entity.dxf.end_angle),
            layer=str(entity.dxf.layer),
            color=DxfParser._safe_color(entity),
            handle=str(entity.dxf.handle),
        )

    def _extract_texts(
        self, modelspace, result: DxfParseResult
    ) -> None:
        """提取所有TEXT和MTEXT实体。"""
        # TEXT/MTEXT 在单实体提取失败时需要往 warnings 写入诊断信息
        # （原有行为，与其它实体只 logger.warning 不同），通过 warn_on_fail=True 保留
        self._extract_entities(
            modelspace, "TEXT", DxfParser._text_to_obj,
            result.texts, result, warn_on_fail=True,
        )
        self._extract_entities(
            modelspace, "MTEXT", DxfParser._mtext_to_obj,
            result.texts, result, warn_on_fail=True,
        )

    @staticmethod
    def _text_to_obj(entity) -> DxfText:
        """将单个 TEXT 实体转换为 DxfText。"""
        return DxfText(
            content=str(entity.dxf.text),
            position=(
                float(entity.dxf.insert.x),
                float(entity.dxf.insert.y),
                float(entity.dxf.insert.z) if entity.dxf.hasattr("insert") and hasattr(entity.dxf.insert, 'z') else 0.0,
            ),
            height=float(entity.dxf.height) if entity.dxf.hasattr("height") else 2.5,
            rotation=float(entity.dxf.rotation) if entity.dxf.hasattr("rotation") else 0.0,
            layer=str(entity.dxf.layer),
            color=DxfParser._safe_color(entity),
            handle=str(entity.dxf.handle),
            entity_type="TEXT",
        )

    @staticmethod
    def _mtext_to_obj(entity) -> DxfText:
        """将单个 MTEXT 实体转换为 DxfText。"""
        raw_text = entity.plain_text() if hasattr(entity, 'plain_text') else str(entity.dxf.text)
        return DxfText(
            content=raw_text,
            position=(
                float(entity.dxf.insert.x),
                float(entity.dxf.insert.y),
                float(entity.dxf.insert.z) if entity.dxf.hasattr("insert") and hasattr(entity.dxf.insert, 'z') else 0.0,
            ),
            height=float(entity.dxf.char_height) if entity.dxf.hasattr("char_height") else 2.5,
            rotation=float(entity.dxf.rotation) if entity.dxf.hasattr("rotation") else 0.0,
            layer=str(entity.dxf.layer),
            color=DxfParser._safe_color(entity),
            handle=str(entity.dxf.handle),
            entity_type="MTEXT",
        )

    def _extract_dimensions(
        self, modelspace, result: DxfParseResult
    ) -> None:
        """提取所有DIMENSION实体。

        对每种标注类型（线性/对齐/角度/半径/直径）调用专门的提取方法。
        对于无法确定类型的标注，尝试从文本内容推断。
        """
        self._extract_entities(
            modelspace, "DIMENSION", DxfParser._dimension_to_obj,
            result.dimensions, result,
        )

    @staticmethod
    def _dimension_to_obj(entity) -> Optional[DxfDimension]:
        """提取单个尺寸标注实体的完整信息。

        利用ezdxf的Dimension对象API获取标注的几何信息、
        测量值和关联实体，并安全包装所有属性访问以防数据缺失。
        """
        dim_type = DxfParser._get_dimension_type(entity)
        measurement = DxfParser._get_measurement(entity)
        text_content = DxfParser._get_dimension_text(entity)
        position = DxfParser._get_dimension_position(entity)

        associated = []
        try:
            if hasattr(entity.dxf, 'geometry'):
                geo_handle = entity.dxf.geometry
                if geo_handle:
                    associated.append(str(geo_handle))
        except (AttributeError, KeyError, TypeError, ValueError) as assoc_err:
            # 标注几何关联属性访问失败时不影响其他属性返回，记录以便排查
            logger.warning(
                "Failed to read DIMENSION geometry handle (handle=%s): %s",
                getattr(entity.dxf, "handle", "?"),
                assoc_err,
                exc_info=True,
            )

        return DxfDimension(
            dim_type=dim_type,
            measurement=measurement,
            text=text_content,
            position=position,
            layer=str(entity.dxf.layer),
            color=DxfParser._safe_color(entity),
            handle=str(entity.dxf.handle),
            associated_entities=associated,
        )

    @staticmethod
    def _get_dimension_type(entity) -> str:
        """根据DXF组码70判断标注类型。"""
        dimtype_map = {
            0: "LINEAR_ROTATED",
            1: "ALIGNED",
            2: "ANGULAR",
            3: "DIAMETER",
            4: "RADIUS",
            5: "ANGULAR_3PT",
            6: "ORDINATE",
            32: "ORDINATE_X",
            64: "ORDINATE_Y",
            160: "ARC_LENGTH",
        }
        try:
            flag = entity.dxf.dimtype
            return dimtype_map.get(flag & 0x7F, f"UNKNOWN_{flag}")
        except (AttributeError, KeyError, TypeError) as exc:
            # 修复：原代码用裸 except Exception 静默吞掉所有错误，
            # 实际只可能是 DIMENSION 字段缺失/类型异常。
            logger.warning(
                "_get_dimtype 降级到 UNKNOWN | handle=%s | exc=%s: %s",
                getattr(entity.dxf, "handle", "?"),
                type(exc).__name__,
                exc,
                exc_info=True,
            )
            return "UNKNOWN"

    @staticmethod
    def _get_measurement(entity) -> float:
        """安全获取标注的测量值。"""
        try:
            return float(entity.dxf.measurement)
        except (AttributeError, TypeError, ValueError) as e:
            logger.warning("无法从 entity.dxf.measurement 获取测量值 (handle=%s): %s",
                        getattr(entity.dxf, "handle", "?"), e, exc_info=True)
            try:
                raw_text = DxfParser._get_dimension_text(entity)
                import re
                nums = re.findall(r'[\d.]+', raw_text)
                if nums:
                    return float(nums[0])
            except (AttributeError, TypeError, ValueError) as parse_err:
                # 备选策略：解析失败时使用 0.0 占位，记录以便后续排查
                logger.warning(
                    "Failed to parse measurement fallback from text (handle=%s): %s",
                    getattr(entity.dxf, "handle", "?"),
                    parse_err,
                    exc_info=True,
                )
            return 0.0

    @staticmethod
    def _get_dimension_text(entity) -> str:
        """安全获取标注文本。"""
        try:
            text = entity.dxf.text
            if text:
                return str(text).strip()
        except (AttributeError, TypeError, ValueError) as text_err:
            # 主路径读不到文本时，会回退到 measurement 占位，记录失败原因
            logger.warning(
                "Failed to read DIMENSION text (handle=%s): %s",
                getattr(entity.dxf, "handle", "?"),
                text_err,
                exc_info=True,
            )
        try:
            return str(entity.dxf.measurement)
        except (AttributeError, TypeError, ValueError) as exc:
            # 修复：原代码用裸 except Exception 静默吞掉所有错误。
            logger.warning(
                "_get_dimension_text measurement 兜底失败 (handle=%s): %s",
                getattr(entity.dxf, "handle", "?"),
                exc,
                exc_info=True,
            )
            return ""

    @staticmethod
    def _get_dimension_position(entity) -> tuple[float, float, float]:
        """安全获取标注文本位置。"""
        try:
            return (
                float(entity.dxf.text_midpoint.x),
                float(entity.dxf.text_midpoint.y),
                float(entity.dxf.text_midpoint.z) if hasattr(entity.dxf.text_midpoint, 'z') else 0.0,
            )
        except (AttributeError, TypeError, ValueError) as exc:
            # 修复：原代码用裸 except Exception 静默吞掉所有错误。
            logger.warning(
                "_get_dimension_position: text_midpoint 缺失, 尝试 def_point (handle=%s): %s",
                getattr(entity.dxf, "handle", "?"),
                exc,
                exc_info=True,
            )
            try:
                return (
                    float(entity.dxf.def_point.x),
                    float(entity.dxf.def_point.y),
                    float(entity.dxf.def_point.z) if hasattr(entity.dxf.def_point, 'z') else 0.0,
                )
            except (AttributeError, TypeError, ValueError) as exc2:
                logger.warning(
                    "_get_dimension_position: def_point 兜底失败 (handle=%s): %s",
                    getattr(entity.dxf, "handle", "?"),
                    exc2,
                    exc_info=True,
                )
                return (0.0, 0.0, 0.0)

    @staticmethod
    def _safe_color(entity) -> int:
        """安全获取实体颜色索引。"""
        try:
            return int(entity.dxf.color)
        except (AttributeError, TypeError, ValueError) as exc:
            # 修复：原代码用裸 except Exception 静默吞掉所有错误。
            logger.warning(
                "_safe_color 降级到 256 (handle=%s): %s",
                getattr(entity.dxf, "handle", "?"),
                exc,
                exc_info=True,
            )
            return 256

    def _extract_polylines(
        self, modelspace, result: DxfParseResult
    ) -> None:
        """提取所有 POLYLINE 和 LWPOLYLINE 实体。

        LWPOLYLINE 顶点包含 bulge（凸度）信息，用于表示圆弧段。
        POLYLINE 子实体是 VERTEX，需要递归读取。
        """
        # LWPOLYLINE/POLYLINE 原代码在 query 失败时不往 warnings 添加消息，
        # 通过 query_warn=False 保留该行为
        self._extract_entities(
            modelspace, "LWPOLYLINE", DxfParser._lwpolyline_to_obj,
            result.polylines, result, query_warn=False,
        )
        self._extract_entities(
            modelspace, "POLYLINE", DxfParser._polyline_to_obj,
            result.polylines, result, query_warn=False,
        )

    @staticmethod
    def _lwpolyline_to_obj(entity) -> DxfPolyline:
        """将单个 LWPOLYLINE 实体转换为 DxfPolyline。"""
        vertices: list[tuple[float, ...]] = []
        # ezdxf 的 points() 方法返回带 bulge 的顶点
        try:
            points_with_bulge = entity.get_points(
                format="xyseb"
            )  # x, y, start_width, end_width, bulge
        except (AttributeError, TypeError, ValueError) as e:
            # 旧版 ezdxf 退路
            logger.warning("LWPOLYLINE get_points(format='xyseb') 失败，尝试 vertices() (handle=%s): %s",
                       str(entity.dxf.handle), e, exc_info=True)
            points_with_bulge = [
                (p[0], p[1], 0.0, 0.0, p[2] if len(p) > 2 else 0.0)
                for p in entity.vertices()
            ]
        for pt in points_with_bulge:
            x = float(pt[0])
            y = float(pt[1])
            bulge = float(pt[4]) if len(pt) > 4 else 0.0
            if abs(bulge) > 1e-6:
                vertices.append((x, y, bulge))
            else:
                vertices.append((x, y))
        return DxfPolyline(
            vertices=vertices,
            is_closed=bool(entity.closed),
            is_3d=False,
            layer=str(entity.dxf.layer),
            color=DxfParser._safe_color(entity),
            handle=str(entity.dxf.handle),
            entity_type="LWPOLYLINE",
        )

    @staticmethod
    def _polyline_to_obj(entity) -> DxfPolyline:
        """将单个 POLYLINE 实体（带 VERTEX 子实体）转换为 DxfPolyline。"""
        vertices: list[tuple[float, ...]] = []
        is_3d = False
        # 遍历子实体（顶点级别容错：单个坏顶点跳过，不影响整体）
        for v in entity.virtual_entities():
            try:
                if v.dxftype() == "VERTEX":
                    loc = v.dxf.location
                    z = float(getattr(loc, "z", 0.0))
                    if abs(z) > 1e-6:
                        is_3d = True
                    bulge = float(getattr(v.dxf, "bulge", 0.0))
                    if abs(bulge) > 1e-6:
                        vertices.append(
                            (float(loc.x), float(loc.y), bulge)
                        )
                    else:
                        vertices.append((float(loc.x), float(loc.y), 0.0))
            except (AttributeError, KeyError, TypeError, ValueError) as e:
                logger.warning("POLYLINE 顶点解析失败，跳过 (handle=%s): %s",
                           str(entity.dxf.handle), e, exc_info=True)
                continue
        return DxfPolyline(
            vertices=vertices,
            is_closed=bool(entity.is_closed),
            is_3d=is_3d,
            layer=str(entity.dxf.layer),
            color=DxfParser._safe_color(entity),
            handle=str(entity.dxf.handle),
            entity_type="POLYLINE",
        )

    def _extract_hatches(
        self, modelspace, result: DxfParseResult
    ) -> None:
        """提取所有 HATCH 实体（填充图案）。

        HATCH 在工程图中常表示：
        - 剖面线（ANSI31 斜线）
        - 区域填色（SOLID 填充）
        - 截面区域
        - 文字背景
        """
        self._extract_entities(
            modelspace, "HATCH", DxfParser._hatch_to_obj,
            result.hatches, result,
        )

    @staticmethod
    def _hatch_to_obj(entity) -> DxfHatch:
        """将单个 HATCH 实体转换为 DxfHatch。"""
        pattern_name = str(
            getattr(entity.dxf, "pattern_name", "") or ""
        )
        solid_fill = bool(
            getattr(entity.dxf, "solid_fill", 0) or 0
        )
        # 提取边界路径
        boundary_paths: list[list[tuple[float, float, float]]] = []
        try:
            # 优先用 ezdxf.paths.make_path() 接口
            for path in entity.paths:
                pts: list[tuple[float, float, float]] = []
                try:
                    for v in path.vertices:
                        # v 通常是 (x, y) 或 (x, y, bulge)
                        x = float(v[0])
                        y = float(v[1])
                        pts.append((x, y, 0.0))
                except (AttributeError, TypeError, ValueError):
                    # 退化为遍历虚实体
                    try:
                        for ve in path.virtual_entities():
                            if ve.dxftype() in ("LINE", "ARC", "LWPOLYLINE", "SPLINE"):
                                start = getattr(ve.dxf, "start", None)
                                if start is not None:
                                    pts.append(
                                        (
                                            float(start[0]),
                                            float(start[1]),
                                            float(
                                                getattr(
                                                    start, "z", 0.0
                                                )
                                            ),
                                        )
                                    )
                            end = getattr(ve.dxf, "end", None)
                            if end is not None:
                                pts.append(
                                    (
                                        float(end[0]),
                                        float(end[1]),
                                        float(
                                            getattr(
                                                end, "z", 0.0
                                            )
                                        ),
                                    )
                                )
                    except (AttributeError, TypeError, ValueError) as e_inner:
                        logger.warning(
                            "HATCH 边界路径点提取失败，跳过该路径: %s",
                            e_inner,
                            exc_info=True,
                        )
                if pts:
                    boundary_paths.append(pts)
        except (AttributeError, TypeError, ValueError) as e_outer:
            # 极简兜底：边界抽取失败时记录日志，便于排查
            logger.warning(
                "HATCH 边界抽取失败(handle=%s): %s",
                getattr(entity.dxf, "handle", "<unknown>"),
                e_outer,
                exc_info=True,
            )
        return DxfHatch(
            pattern_name=pattern_name,
            solid_fill=solid_fill,
            boundary_paths=boundary_paths,
            layer=str(
                getattr(entity.dxf, "layer", "0")
            ),
            color=DxfParser._safe_color(entity),
            handle=str(entity.dxf.handle),
        )

    def _extract_inserts(
        self, modelspace, result: DxfParseResult
    ) -> None:
        """提取所有 INSERT 实体（Block 引用）。

        INSERT 表示"插入一个块"，是 DXF 复用的关键机制。
        工业场景中：标准件库（螺栓、键、键槽、孔标准件）通过 INSERT 引用。
        """
        self._extract_entities(
            modelspace, "INSERT", DxfParser._insert_to_obj,
            result.inserts, result,
        )

    @staticmethod
    def _insert_to_obj(entity) -> DxfInsert:
        """将单个 INSERT 实体转换为 DxfInsert。"""
        block_name = str(
            getattr(entity.dxf, "name", "") or ""
        )
        insert_point = getattr(entity.dxf, "insert", None)
        if insert_point is None:
            position: tuple[float, float, float] = (
                0.0, 0.0, 0.0
            )
        else:
            position = (
                float(insert_point.x),
                float(insert_point.y),
                float(getattr(insert_point, "z", 0.0)),
            )
        # scale (x, y, z) —— 显式 None 检查，避免 0.0 被错误覆盖
        _sx_raw = getattr(entity.dxf, "xscale", None)
        _sy_raw = getattr(entity.dxf, "yscale", None)
        _sz_raw = getattr(entity.dxf, "zscale", None)
        sx = float(_sx_raw) if _sx_raw is not None else 1.0
        sy = float(_sy_raw) if _sy_raw is not None else 1.0
        sz = float(_sz_raw) if _sz_raw is not None else 1.0
        # rotation —— 同样显式 None 检查
        _rot_raw = getattr(entity.dxf, "rotation", None)
        rotation = float(_rot_raw) if _rot_raw is not None else 0.0
        return DxfInsert(
            block_name=block_name,
            position=position,
            scale=(sx, sy, sz),
            rotation=rotation,
            layer=str(
                getattr(entity.dxf, "layer", "0")
            ),
            handle=str(entity.dxf.handle),
        )

    def _extract_splines(
        self, modelspace, result: DxfParseResult
    ) -> None:
        """提取所有 SPLINE 实体（样条曲线）。

        SPLINE 在工业场景中：
        - 自由曲面（航空叶片、船体）
        - 模具型腔的复杂轮廓
        - 凸轮轮廓线
        """
        self._extract_entities(
            modelspace, "SPLINE", DxfParser._spline_to_obj,
            result.splines, result,
        )

    @staticmethod
    def _spline_to_obj(entity) -> DxfSpline:
        """将单个 SPLINE 实体转换为 DxfSpline。"""
        # degree —— 显式 None 检查，避免 0 被错误覆盖为 3
        _deg_raw = getattr(entity.dxf, "degree", None)
        if _deg_raw is None:
            degree = 3
        else:
            degree = int(_deg_raw) if int(_deg_raw) > 0 else 3
        # control points（可能为空；fit_points 单独提取）
        cp: list[tuple[float, float, float]] = []
        try:
            # 部分 ezdxf 版本：从 control_points 获取
            for ctl in entity.control_points:
                cp.append(
                    (float(ctl[0]), float(ctl[1]), float(ctl[2]))
                )
        except (AttributeError, TypeError, ValueError) as e:
            # 退化：基于 fit_points 估计
            logger.warning("SPLINE control_points 解析失败，尝试 fit_points: %s", e, exc_info=True)
            try:
                for f in entity.fit_points:
                    cp.append(
                        (float(f[0]), float(f[1]), float(f[2]))
                    )
            except (AttributeError, TypeError, ValueError) as e2:
                logger.warning("SPLINE fit_points 也解析失败: %s", e2, exc_info=True)
        # fit points
        fp: list[tuple[float, float, float]] = []
        try:
            for f in entity.fit_points:
                fp.append(
                    (float(f[0]), float(f[1]), float(f[2]))
                )
        except (AttributeError, TypeError, ValueError) as e:
            logger.warning("SPLINE fit_points 解析失败: %s", e, exc_info=True)
        # knots
        knots: list[float] = []
        try:
            knots = [float(k) for k in entity.knots]
        except (AttributeError, TypeError, ValueError) as e:
            logger.warning("SPLINE knots 解析失败: %s", e, exc_info=True)
        # closed —— 显式取布尔值，避免 0/False 混淆
        _closed_dxf = getattr(entity.dxf, "closed", 0)
        _closed_attr = getattr(entity, "closed", False)
        closed = bool(_closed_dxf) or bool(_closed_attr)
        return DxfSpline(
            degree=degree,
            control_points=cp,
            fit_points=fp,
            knots=knots,
            closed=closed,
            layer=str(
                getattr(entity.dxf, "layer", "0")
            ),
            handle=str(entity.dxf.handle),
        )

    def _compute_extents(self, result: DxfParseResult) -> None:
        """计算图形范围。"""
        min_x = min_y = float("inf")
        max_x = max_y = float("-inf")

        for line in result.lines:
            min_x = min(min_x, line.start[0], line.end[0])
            max_x = max(max_x, line.start[0], line.end[0])
            min_y = min(min_y, line.start[1], line.end[1])
            max_y = max(max_y, line.start[1], line.end[1])

        for circle in result.circles:
            min_x = min(min_x, circle.center[0] - circle.radius)
            max_x = max(max_x, circle.center[0] + circle.radius)
            min_y = min(min_y, circle.center[1] - circle.radius)
            max_y = max(max_y, circle.center[1] + circle.radius)

        for arc in result.arcs:
            min_x = min(min_x, arc.center[0] - arc.radius)
            max_x = max(max_x, arc.center[0] + arc.radius)
            min_y = min(min_y, arc.center[1] - arc.radius)
            max_y = max(max_y, arc.center[1] + arc.radius)

        for polyline in result.polylines:
            for v in polyline.vertices:
                min_x = min(min_x, v[0])
                max_x = max(max_x, v[0])
                min_y = min(min_y, v[1])
                max_y = max(max_y, v[1])

        # HATCH 边界范围
        for hatch in result.hatches:
            for path in hatch.boundary_paths:
                for p in path:
                    min_x = min(min_x, p[0])
                    max_x = max(max_x, p[0])
                    min_y = min(min_y, p[1])
                    max_y = max(max_y, p[1])

        # INSERT 位置
        for ins in result.inserts:
            min_x = min(min_x, ins.position[0])
            max_x = max(max_x, ins.position[0])
            min_y = min(min_y, ins.position[1])
            max_y = max(max_y, ins.position[1])

        # SPLINE 控制点范围
        for sp in result.splines:
            for p in sp.control_points:
                min_x = min(min_x, p[0])
                max_x = max(max_x, p[0])
                min_y = min(min_y, p[1])
                max_y = max(max_y, p[1])

        if min_x == float("inf"):
            min_x = min_y = max_x = max_y = 0.0

        result.extents = {
            "min_x": round(min_x, 4),
            "min_y": round(min_y, 4),
            "max_x": round(max_x, 4),
            "max_y": round(max_y, 4),
            "width": round(max_x - min_x, 4),
            "height": round(max_y - min_y, 4),
        }
