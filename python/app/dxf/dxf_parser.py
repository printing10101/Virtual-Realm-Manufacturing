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
from typing import Any, Optional

import ezdxf

from app.dxf.exceptions import DxfParseError, DxfFormatError

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


@dataclass
class DxfLine:
    """DXF直线实体。

    Attributes:
        start: 起点坐标 (x, y, z)
        end: 终点坐标 (x, y, z)
        layer: 图层名称
        color: 颜色索引号 (ACI)，0=BYBLOCK, 256=BYLAYER
        handle: 实体句柄
        lineweight: 线宽枚举值
    """
    start: tuple[float, float, float]
    end: tuple[float, float, float]
    layer: str = "0"
    color: int = 256
    handle: str = ""
    lineweight: int = -1


@dataclass
class DxfCircle:
    """DXF圆实体。

    Attributes:
        center: 圆心坐标 (x, y, z)
        radius: 半径
        layer: 图层名称
        color: 颜色索引号
        handle: 实体句柄
    """
    center: tuple[float, float, float]
    radius: float
    layer: str = "0"
    color: int = 256
    handle: str = ""


@dataclass
class DxfArc:
    """DXF圆弧实体。

    Attributes:
        center: 圆心坐标 (x, y, z)
        radius: 半径
        start_angle: 起始角度(度)
        end_angle: 终止角度(度)
        layer: 图层名称
        color: 颜色索引号
        handle: 实体句柄
    """
    center: tuple[float, float, float]
    radius: float
    start_angle: float
    end_angle: float
    layer: str = "0"
    color: int = 256
    handle: str = ""


@dataclass
class DxfText:
    """DXF文字实体。

    Attributes:
        content: 文本内容
        position: 插入点坐标 (x, y, z)
        height: 文字高度
        rotation: 旋转角度(度)
        layer: 图层名称
        color: 颜色索引号
        handle: 实体句柄
        entity_type: 实体类型 ("TEXT" 或 "MTEXT")
    """
    content: str
    position: tuple[float, float, float]
    height: float = 2.5
    rotation: float = 0.0
    layer: str = "0"
    color: int = 256
    handle: str = ""
    entity_type: str = "TEXT"


@dataclass
class DxfDimension:
    """DXF尺寸标注实体。

    Attributes:
        dim_type: 标注类型 (LINEAR/ALIGNED/ANGULAR/RADIUS/DIAMETER/ORDINATE)
        measurement: 测量值(图形单位)
        text: 标注文本内容(可能含公差)
        position: 标注文本位置 (x, y, z)
        layer: 图层名称
        color: 颜色索引号
        handle: 实体句柄
        associated_entities: 关联的实体句柄列表
    """
    dim_type: str
    measurement: float
    text: str = ""
    position: tuple[float, float, float] = (0.0, 0.0, 0.0)
    layer: str = "0"
    color: int = 256
    handle: str = ""
    associated_entities: list[str] = field(default_factory=list)


@dataclass
class DxfPolyline:
    """DXF多段线实体（POLYLINE / LWPOLYLINE）。

    Attributes:
        vertices: 顶点列表，每项为 (x, y) 或 (x, y, bulge)
                  bulge 是切线凸度，用于表示圆弧段（LWPOLYLINE 专用）：
                  bulge = tan(arc_angle / 4)
                  bulge > 0 表示逆时针，< 0 表示顺时针
        is_closed: 是否闭合
        is_3d: 是否是 3D 多段线
        layer: 图层名称
        color: 颜色索引号
        handle: 实体句柄
        entity_type: "POLYLINE" 或 "LWPOLYLINE"
    """
    vertices: list[tuple[float, ...]]
    is_closed: bool = False
    is_3d: bool = False
    layer: str = "0"
    color: int = 256
    handle: str = ""
    entity_type: str = "LWPOLYLINE"

    @property
    def vertex_count(self) -> int:
        return len(self.vertices)

    def to_dict(self) -> dict[str, Any]:
        return {
            "entity_type": self.entity_type,
            "is_closed": self.is_closed,
            "is_3d": self.is_3d,
            "layer": self.layer,
            "color": self.color,
            "handle": self.handle,
            "vertex_count": self.vertex_count,
            "vertices": [list(v) for v in self.vertices],
        }

    def bbox(self) -> tuple[float, float, float, float]:
        """计算包围盒 (min_x, min_y, max_x, max_y)。"""
        if not self.vertices:
            return (0.0, 0.0, 0.0, 0.0)
        xs = [v[0] for v in self.vertices]
        ys = [v[1] for v in self.vertices]
        return (min(xs), min(ys), max(xs), max(ys))


@dataclass
class DxfHatch:
    """DXF 填充（HATCH）实体。

    Attributes:
        pattern_name: 填充图案名（如 ANSI31、SOLID）
        solid_fill: 是否为实心填充
        boundary_paths: 边界路径（每个是顶点列表）
        layer: 图层
        color: 颜色
        handle: 实体句柄
    """
    pattern_name: str = ""
    solid_fill: bool = False
    boundary_paths: list[list[tuple[float, float, float]]] = field(
        default_factory=list
    )
    layer: str = "0"
    color: int = 256
    handle: str = ""


@dataclass
class DxfInsert:
    """DXF 块插入（INSERT）实体 — 即 Block 引用。

    Attributes:
        block_name: 被引用的块名
        position: 插入点
        scale: X/Y/Z 缩放因子
        rotation: 旋转角度（度）
        layer: 图层
        handle: 实体句柄
    """
    block_name: str = ""
    position: tuple[float, float, float] = (0.0, 0.0, 0.0)
    scale: tuple[float, float, float] = (1.0, 1.0, 1.0)
    rotation: float = 0.0
    layer: str = "0"
    handle: str = ""


@dataclass
class DxfSpline:
    """DXF 样条曲线（SPLINE）实体。

    Attributes:
        degree: 阶数（3=三次 B-Spline）
        control_points: 控制点
        fit_points: 拟合点（可能为空）
        knots: 节点向量
        closed: 是否闭合
        layer: 图层
        handle: 实体句柄
    """
    degree: int = 3
    control_points: list[tuple[float, float, float]] = field(
        default_factory=list
    )
    fit_points: list[tuple[float, float, float]] = field(
        default_factory=list
    )
    knots: list[float] = field(default_factory=list)
    closed: bool = False
    layer: str = "0"
    handle: str = ""


@dataclass
class DxfParseResult:
    """DXF解析结果。

    Attributes:
        file_name: 源文件名
        file_size: 文件大小(字节)
        dxf_version: DXF版本字符串
        parse_time_ms: 解析耗时(毫秒)
        lines: 直线列表
        circles: 圆列表
        arcs: 圆弧列表
        texts: 文字列表
        dimensions: 尺寸标注列表
        polylines: 多段线列表
        entity_counts: 各类型实体数量统计
        warnings: 解析过程中的警告
        errors: 解析过程中的错误
        extents: 图形范围 (min_x, min_y, max_x, max_y)
    """
    file_name: str = ""
    file_size: int = 0
    dxf_version: str = ""
    parse_time_ms: float = 0.0
    lines: list[DxfLine] = field(default_factory=list)
    circles: list[DxfCircle] = field(default_factory=list)
    arcs: list[DxfArc] = field(default_factory=list)
    texts: list[DxfText] = field(default_factory=list)
    dimensions: list[DxfDimension] = field(default_factory=list)
    polylines: list[DxfPolyline] = field(default_factory=list)
    # 高级实体类型（HATCH/BLOCK INSERT/SPLINE）
    hatches: list[DxfHatch] = field(default_factory=list)
    inserts: list[DxfInsert] = field(default_factory=list)
    splines: list[DxfSpline] = field(default_factory=list)
    entity_counts: dict[str, int] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    extents: dict[str, float] = field(default_factory=dict)

    @property
    def success(self) -> bool:
        return len(self.errors) == 0

    @property
    def total_entities(self) -> int:
        return sum(self.entity_counts.values())

    def to_dict(self) -> dict[str, Any]:
        return {
            "file_name": self.file_name,
            "file_size": self.file_size,
            "dxf_version": self.dxf_version,
            "parse_time_ms": round(self.parse_time_ms, 2),
            "entity_counts": self.entity_counts,
            "total_entities": self.total_entities,
            "lines_count": len(self.lines),
            "circles_count": len(self.circles),
            "arcs_count": len(self.arcs),
            "texts_count": len(self.texts),
            "dimensions_count": len(self.dimensions),
            "polylines_count": len(self.polylines),
            "hatches_count": len(self.hatches),
            "inserts_count": len(self.inserts),
            "splines_count": len(self.splines),
            "extents": self.extents,
            "warnings": self.warnings,
            "errors": self.errors,
            "success": self.success,
        }


class DxfParser:
    """DXF文件解析器。

    基于ezdxf库解析DXF文件，提取几何实体和尺寸标注信息。
    支持AutoCAD R12至2021版本的DXF格式。

    使用方式:
        parser = DxfParser()
        result = parser.parse("path/to/part.dxf")
        for line in result.lines:
            print(f"直线: {line.start} -> {line.end}")
    """

    def __init__(self) -> None:
        logger.info("DxfParser初始化完成")

    def parse(
        self,
        file_path: str | Path,
        *,
        user_id: Optional[str] = None,
    ) -> DxfParseResult:
        """解析DXF文件并返回结构化数据。

        Args:
            file_path: DXF文件路径
            user_id: 可选的用户标识，仅用于桥接层数据收集，不影响解析逻辑

        Returns:
            DxfParseResult: 包含所有提取的几何实体和元数据

        Raises:
            DxfParseError: 文件不存在或读取失败
            DxfFormatError: DXF格式无效或版本不支持
        """
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
        except Exception as e:
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
            for err in result.errors:
                collector.record_error(
                    feature="dxf_parser",
                    error_type="parse_error",
                    error_message=err,
                    context={"file_path": str(path)},
                    user_id=user_id,
                )
        except Exception as e:  # noqa: BLE001
            logger.debug("bridge 数据收集失败（不影响主流程）: %s", e)

        return result

    def _extract_lines(
        self, modelspace, result: DxfParseResult
    ) -> None:
        """提取所有LINE实体。"""
        try:
            query = modelspace.query("LINE")
            for entity in query:
                try:
                    line = DxfLine(
                        start=(
                            float(entity.dxf.start.x),
                            float(entity.dxf.start.y),
                            float(entity.dxf.start.z) if entity.dxf.hasattr("start") and hasattr(entity.dxf.start, 'z') else 0.0,  # noqa: E501
                        ),
                        end=(
                            float(entity.dxf.end.x),
                            float(entity.dxf.end.y),
                            float(entity.dxf.end.z) if entity.dxf.hasattr("end") and hasattr(entity.dxf.end, 'z') else 0.0,  # noqa: E501
                        ),
                        layer=str(entity.dxf.layer),
                        color=self._safe_color(entity),
                        handle=str(entity.dxf.handle),
                    )
                    result.lines.append(line)
                except Exception as e:
                    logger.debug("LINE实体提取跳过(handle=%s): %s", entity.dxf.handle, e)
        except Exception as e:
            result.warnings.append(f"LINE实体查询异常: {e}")

    def _extract_circles(
        self, modelspace, result: DxfParseResult
    ) -> None:
        """提取所有CIRCLE实体。"""
        try:
            query = modelspace.query("CIRCLE")
            for entity in query:
                try:
                    circle = DxfCircle(
                        center=(
                            float(entity.dxf.center.x),
                            float(entity.dxf.center.y),
                            float(entity.dxf.center.z) if entity.dxf.hasattr("center") and hasattr(entity.dxf.center, 'z') else 0.0,  # noqa: E501
                        ),
                        radius=float(entity.dxf.radius),
                        layer=str(entity.dxf.layer),
                        color=self._safe_color(entity),
                        handle=str(entity.dxf.handle),
                    )
                    if circle.radius > 0:
                        result.circles.append(circle)
                except Exception as e:
                    logger.debug("CIRCLE实体提取跳过(handle=%s): %s", entity.dxf.handle, e)
        except Exception as e:
            result.warnings.append(f"CIRCLE实体查询异常: {e}")

    def _extract_arcs(
        self, modelspace, result: DxfParseResult
    ) -> None:
        """提取所有ARC实体。"""
        try:
            query = modelspace.query("ARC")
            for entity in query:
                try:
                    arc = DxfArc(
                        center=(
                            float(entity.dxf.center.x),
                            float(entity.dxf.center.y),
                            float(entity.dxf.center.z) if entity.dxf.hasattr("center") and hasattr(entity.dxf.center, 'z') else 0.0,  # noqa: E501
                        ),
                        radius=float(entity.dxf.radius),
                        start_angle=float(entity.dxf.start_angle),
                        end_angle=float(entity.dxf.end_angle),
                        layer=str(entity.dxf.layer),
                        color=self._safe_color(entity),
                        handle=str(entity.dxf.handle),
                    )
                    result.arcs.append(arc)
                except Exception as e:
                    logger.debug("ARC实体提取跳过(handle=%s): %s", entity.dxf.handle, e)
        except Exception as e:
            result.warnings.append(f"ARC实体查询异常: {e}")

    def _extract_texts(
        self, modelspace, result: DxfParseResult
    ) -> None:
        """提取所有TEXT和MTEXT实体。"""
        _extract_single_text = self._extract_text_entity
        _extract_single_mtext = self._extract_mtext_entity

        try:
            for entity in modelspace.query("TEXT"):
                try:
                    result.texts.append(_extract_single_text(entity))
                except Exception as e:
                    # 修复：保留诊断信息（handle + 原因），并通过 warnings 反馈
                    handle = getattr(entity.dxf, "handle", "<unknown>")
                    logger.debug("TEXT实体提取跳过(handle=%s): %s", handle, e)
                    result.warnings.append(
                        f"TEXT实体提取失败(handle={handle}): {e}"
                    )
        except Exception as e:
            result.warnings.append(f"TEXT实体查询异常: {e}")

        try:
            for entity in modelspace.query("MTEXT"):
                try:
                    result.texts.append(_extract_single_mtext(entity))
                except Exception as e:
                    handle = getattr(entity.dxf, "handle", "<unknown>")
                    logger.debug("MTEXT实体提取跳过(handle=%s): %s", handle, e)
                    result.warnings.append(
                        f"MTEXT实体提取失败(handle={handle}): {e}"
                    )
        except Exception as e:
            result.warnings.append(f"MTEXT实体查询异常: {e}")

    @staticmethod
    def _extract_text_entity(entity) -> DxfText:
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
    def _extract_mtext_entity(entity) -> DxfText:
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
        try:
            for entity in modelspace.query("DIMENSION"):
                try:
                    dim = self._extract_single_dimension(entity)
                    if dim is not None:
                        result.dimensions.append(dim)
                except Exception as e:
                    logger.debug("DIMENSION实体提取跳过(handle=%s): %s", entity.dxf.handle, e)
        except Exception as e:
            result.warnings.append(f"DIMENSION实体查询异常: {e}")

    def _extract_single_dimension(self, entity) -> Optional[DxfDimension]:
        """提取单个尺寸标注实体的完整信息。

        利用ezdxf的Dimension对象API获取标注的几何信息、
        测量值和关联实体，并安全包装所有属性访问以防数据缺失。
        """
        dim_type = self._get_dimension_type(entity)
        measurement = self._get_measurement(entity)
        text_content = self._get_dimension_text(entity)
        position = self._get_dimension_position(entity)

        associated = []
        try:
            if hasattr(entity.dxf, 'geometry'):
                geo_handle = entity.dxf.geometry
                if geo_handle:
                    associated.append(str(geo_handle))
        except (AttributeError, KeyError, TypeError, ValueError) as assoc_err:
            # 标注几何关联属性访问失败时不影响其他属性返回，记录以便排查
            logger.debug(
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
            color=self._safe_color(entity),
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
            logger.debug(
                "_get_dimtype 降级到 UNKNOWN | handle=%s | exc=%s: %s",
                getattr(entity.dxf, "handle", "?"),
                type(exc).__name__,
                exc,
            )
            return "UNKNOWN"

    @staticmethod
    def _get_measurement(entity) -> float:
        """安全获取标注的测量值。"""
        try:
            return float(entity.dxf.measurement)
        except Exception as e:  # noqa: BLE001
            logger.debug("无法从 entity.dxf.measurement 获取测量值 (handle=%s): %s",
                        getattr(entity.dxf, "handle", "?"), e)
            try:
                raw_text = DxfParser._get_dimension_text(entity)
                import re
                nums = re.findall(r'[\d.]+', raw_text)
                if nums:
                    return float(nums[0])
            except (AttributeError, TypeError, ValueError) as parse_err:
                # 备选策略：解析失败时使用 0.0 占位，记录以便后续排查
                logger.debug(
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
            logger.debug(
                "Failed to read DIMENSION text (handle=%s): %s",
                getattr(entity.dxf, "handle", "?"),
                text_err,
                exc_info=True,
            )
        try:
            return str(entity.dxf.measurement)
        except (AttributeError, TypeError, ValueError) as exc:
            # 修复：原代码用裸 except Exception 静默吞掉所有错误。
            logger.debug(
                "_get_dimension_text measurement 兜底失败 (handle=%s): %s",
                getattr(entity.dxf, "handle", "?"),
                exc,
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
            logger.debug(
                "_get_dimension_position: text_midpoint 缺失, 尝试 def_point (handle=%s): %s",
                getattr(entity.dxf, "handle", "?"),
                exc,
            )
            try:
                return (
                    float(entity.dxf.def_point.x),
                    float(entity.dxf.def_point.y),
                    float(entity.dxf.def_point.z) if hasattr(entity.dxf.def_point, 'z') else 0.0,
                )
            except (AttributeError, TypeError, ValueError) as exc2:
                logger.debug(
                    "_get_dimension_position: def_point 兜底失败 (handle=%s): %s",
                    getattr(entity.dxf, "handle", "?"),
                    exc2,
                )
                return (0.0, 0.0, 0.0)

    @staticmethod
    def _safe_color(entity) -> int:
        """安全获取实体颜色索引。"""
        try:
            return int(entity.dxf.color)
        except (AttributeError, TypeError, ValueError) as exc:
            # 修复：原代码用裸 except Exception 静默吞掉所有错误。
            logger.debug(
                "_safe_color 降级到 256 (handle=%s): %s",
                getattr(entity.dxf, "handle", "?"),
                exc,
            )
            return 256

    def _extract_polylines(
        self, modelspace, result: DxfParseResult
    ) -> None:
        """提取所有 POLYLINE 和 LWPOLYLINE 实体。

        LWPOLYLINE 顶点包含 bulge（凸度）信息，用于表示圆弧段。
        POLYLINE 子实体是 VERTEX，需要递归读取。
        """
        # 1. LWPOLYLINE
        try:
            for entity in modelspace.query("LWPOLYLINE"):
                try:
                    vertices: list[tuple[float, ...]] = []
                    # ezdxf 的 points() 方法返回带 bulge 的顶点
                    try:
                        points_with_bulge = entity.get_points(
                            format="xyseb"
                        )  # x, y, start_width, end_width, bulge
                    except Exception as e:  # noqa: BLE001
                        # 旧版 ezdxf 退路
                        logger.debug("LWPOLYLINE get_points(format='xyseb') 失败，尝试 vertices() (handle=%s): %s",
                                   str(entity.dxf.handle), e)
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
                    is_closed = bool(entity.closed)
                    polyline = DxfPolyline(
                        vertices=vertices,
                        is_closed=is_closed,
                        is_3d=False,
                        layer=str(entity.dxf.layer),
                        color=self._safe_color(entity),
                        handle=str(entity.dxf.handle),
                        entity_type="LWPOLYLINE",
                    )
                    result.polylines.append(polyline)
                except Exception as e:
                    logger.warning(
                        "LWPOLYLINE解析失败 handle=%s: %s",
                        getattr(entity.dxf, "handle", "?"),
                        e,
                    )
        except Exception as e:
            logger.warning("LWPOLYLINE query 失败: %s", e)

        # 2. POLYLINE（带 VERTEX 子实体）
        try:
            for entity in modelspace.query("POLYLINE"):
                try:
                    vertices: list[tuple[float, ...]] = []
                    is_3d = False
                    # 遍历子实体
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
                        except Exception as e:  # noqa: BLE001
                            logger.debug("POLYLINE 顶点解析失败，跳过 (handle=%s): %s",
                                       str(entity.dxf.handle), e)
                            continue
                    is_closed = bool(entity.is_closed)
                    polyline = DxfPolyline(
                        vertices=vertices,
                        is_closed=is_closed,
                        is_3d=is_3d,
                        layer=str(entity.dxf.layer),
                        color=self._safe_color(entity),
                        handle=str(entity.dxf.handle),
                        entity_type="POLYLINE",
                    )
                    result.polylines.append(polyline)
                except Exception as e:
                    logger.warning(
                        "POLYLINE解析失败 handle=%s: %s",
                        getattr(entity.dxf, "handle", "?"),
                        e,
                    )
        except Exception as e:
            logger.warning("POLYLINE query 失败: %s", e)

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
        try:
            query = modelspace.query("HATCH")
            for entity in query:
                try:
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
                            except Exception:  # noqa: BLE001
                                # 退化为遍历虚实体
                                try:
                                    for ve in path.virtual_entities():
                                        if ve.dxftype() in ("LINE", "ARC", "LWPOLYLINE", "SPLINE"):  # noqa: E501
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
                                except Exception as e_inner:  # noqa: BLE001
                                    logger.debug(
                                        "HATCH 边界路径点提取失败，跳过该路径: %s",
                                        e_inner,
                                    )
                            if pts:
                                boundary_paths.append(pts)
                    except Exception as e_outer:  # noqa: BLE001
                        # 极简兜底：边界抽取失败时记录日志，便于排查
                        logger.debug(
                            "HATCH 边界抽取失败(handle=%s): %s",
                            getattr(entity.dxf, "handle", "<unknown>"),
                            e_outer,
                        )
                    hatch = DxfHatch(
                        pattern_name=pattern_name,
                        solid_fill=solid_fill,
                        boundary_paths=boundary_paths,
                        layer=str(
                            getattr(entity.dxf, "layer", "0")
                        ),
                        color=self._safe_color(entity),
                        handle=str(entity.dxf.handle),
                    )
                    result.hatches.append(hatch)
                except Exception as e:  # noqa: BLE001
                    handle = getattr(
                        entity.dxf, "handle", "<unknown>"
                    )
                    logger.debug(
                        "HATCH实体提取跳过(handle=%s): %s", handle, e
                    )
        except Exception as e:
            result.warnings.append(f"HATCH实体查询异常: {e}")

    def _extract_inserts(
        self, modelspace, result: DxfParseResult
    ) -> None:
        """提取所有 INSERT 实体（Block 引用）。

        INSERT 表示"插入一个块"，是 DXF 复用的关键机制。
        工业场景中：标准件库（螺栓、键、键槽、孔标准件）通过 INSERT 引用。
        """
        try:
            query = modelspace.query("INSERT")
            for entity in query:
                try:
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
                    insert = DxfInsert(
                        block_name=block_name,
                        position=position,
                        scale=(sx, sy, sz),
                        rotation=rotation,
                        layer=str(
                            getattr(entity.dxf, "layer", "0")
                        ),
                        handle=str(entity.dxf.handle),
                    )
                    result.inserts.append(insert)
                except Exception as e:  # noqa: BLE001
                    handle = getattr(
                        entity.dxf, "handle", "<unknown>"
                    )
                    logger.debug(
                        "INSERT实体提取跳过(handle=%s): %s", handle, e
                    )
        except Exception as e:
            result.warnings.append(f"INSERT实体查询异常: {e}")

    def _extract_splines(
        self, modelspace, result: DxfParseResult
    ) -> None:
        """提取所有 SPLINE 实体（样条曲线）。

        SPLINE 在工业场景中：
        - 自由曲面（航空叶片、船体）
        - 模具型腔的复杂轮廓
        - 凸轮轮廓线
        """
        try:
            query = modelspace.query("SPLINE")
            for entity in query:
                try:
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
                    except Exception as e:  # noqa: BLE001
                        # 退化：基于 fit_points 估计
                        logger.debug("SPLINE control_points 解析失败，尝试 fit_points: %s", e)
                        try:
                            for f in entity.fit_points:
                                cp.append(
                                    (float(f[0]), float(f[1]), float(f[2]))
                                )
                        except Exception as e2:  # noqa: BLE001
                            logger.warning("SPLINE fit_points 也解析失败: %s", e2)
                    # fit points
                    fp: list[tuple[float, float, float]] = []
                    try:
                        for f in entity.fit_points:
                            fp.append(
                                (float(f[0]), float(f[1]), float(f[2]))
                            )
                    except Exception as e:  # noqa: BLE001
                        logger.debug("SPLINE fit_points 解析失败: %s", e)
                    # knots
                    knots: list[float] = []
                    try:
                        knots = [float(k) for k in entity.knots]
                    except Exception as e:  # noqa: BLE001
                        logger.debug("SPLINE knots 解析失败: %s", e)
                    # closed —— 显式取布尔值，避免 0/False 混淆
                    _closed_dxf = getattr(entity.dxf, "closed", 0)
                    _closed_attr = getattr(entity, "closed", False)
                    closed = bool(_closed_dxf) or bool(_closed_attr)
                    spline = DxfSpline(
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
                    result.splines.append(spline)
                except Exception as e:  # noqa: BLE001
                    handle = getattr(
                        entity.dxf, "handle", "<unknown>"
                    )
                    logger.debug(
                        "SPLINE实体提取跳过(handle=%s): %s", handle, e
                    )
        except Exception as e:
            result.warnings.append(f"SPLINE实体查询异常: {e}")

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
