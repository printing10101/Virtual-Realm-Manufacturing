"""DXF到3D模型转换模块。

基于CadQuery库将DXF提取的2D几何特征转换为3D实体模型。
通过创建基础外形并使用布尔运算添加孔特征，
生成可用于后续工艺规划的完整三维模型。

转换流程：
    平面特征(外形尺寸) ──▶ box() ──▶ 基础立方体
    孔特征列表 ────────▶ cylinder() + cut() ──▶ 带孔实体模型
"""

from __future__ import annotations

import logging
import math
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import cadquery as cq

from app.dxf.feature_extractor import (
    FeatureExtractionResult,
    HoleFeatureInfo,
    PlaneFeatureInfo,
)
from app.dxf.exceptions import DxfModelError

logger = logging.getLogger(__name__)


@dataclass
class ModelConversionResult:
    """模型转换结果。

    Attributes:
        workplane: CadQuery Workplane对象(包含完整3D模型)
        length: 模型长度(X方向)
        width: 模型宽度(Y方向)
        height: 模型高度(Z方向)
        hole_count: 孔数量
        warnings: 转换过程中的警告
        errors: 转换过程中的错误
    """
    workplane: Any = None
    length: float = 0.0
    width: float = 0.0
    height: float = 10.0
    hole_count: int = 0
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def success(self) -> bool:
        return len(self.errors) == 0 and self.workplane is not None


class DxfToModelConverter:
    """DXF特征到3D模型的转换器。

    基于CadQuery实现完整的2D→3D转换流程：
    1. 根据外形尺寸创建基准立方体
    2. 对每个孔特征进行布尔减运算
    3. 返回完整的Workplane对象供后续使用

    使用方式:
        converter = DxfToModelConverter()
        result = converter.convert(feature_result)
        if result.success:
            # 导出STL
            cq.exporters.export(result.workplane, "model.stl")
    """

    def __init__(self) -> None:
        logger.info("DxfToModelConverter初始化完成")

    def convert(
        self,
        feature_result: FeatureExtractionResult,
    ) -> ModelConversionResult:
        """将特征提取结果转换为3D CadQuery模型。

        Args:
            feature_result: FeatureExtractor的输出

        Returns:
            ModelConversionResult: 包含Workplane对象的转换结果

        Raises:
            DxfModelError: 特征数据无效或CadQuery操作失败
        """
        if feature_result is None:
            raise DxfModelError("特征提取结果为空，无法生成3D模型。"
                               "请先调用FeatureExtractor.extract()获取特征数据。")

        result = ModelConversionResult()
        length = feature_result.overall_length
        width = feature_result.overall_width
        height = feature_result.overall_height

        if length <= 0 or width <= 0:
            result.errors.append(
                f"零件外形尺寸无效(长={length}, 宽={width})，"
                f"无法创建3D模型"
            )
            return result

        if height <= 0:
            height = 10.0
            result.warnings.append(f"零件高度无效，使用默认值{height}mm")

        result.length = length
        result.width = width
        result.height = height

        try:
            base = self._create_base_solid(length, width, height)
        except Exception as e:
            raise DxfModelError(
                f"基础立方体创建失败(尺寸={length}x{width}x{height}mm): {e}"
            ) from e

        hole_count = 0
        for hole in feature_result.holes:
            try:
                base = self._add_hole(base, hole, height)
                hole_count += 1
            except Exception as e:
                result.warnings.append(
                    f"孔{hole.hole_id}创建失败(中心=({hole.center_x:.1f},{hole.center_y:.1f}), "
                    f"直径={hole.diameter:.2f}mm): {e}"
                )
                logger.warning("孔特征转换失败: %s", e)

        result.workplane = base
        result.hole_count = hole_count

        logger.info(
            "3D模型转换完成: 外形=%.1fx%.1fx%.1fmm, 孔=%d/%d",
            length, width, height,
            hole_count,
            feature_result.hole_count,
        )
        return result

    def _create_base_solid(
        self,
        length: float,
        width: float,
        height: float,
    ) -> cq.Workplane:
        """创建基准立方体。

        在XY平面上创建box，底部位于Z=0，高度沿Z轴正向。
        """
        base = (
            cq.Workplane("XY")
            .box(length, width, height, centered=(True, True, False))
        )
        logger.debug("基础立方体创建成功: %.1fx%.1fx%.1fmm", length, width, height)
        return base

    def _add_hole(
        self,
        workplane: cq.Workplane,
        hole: HoleFeatureInfo,
        base_height: float,
    ) -> cq.Workplane:
        """在模型上创建孔特征（布尔减运算）。

        Args:
            workplane: 当前Workplane对象
            hole: 孔特征信息
            base_height: 基础模型高度

        Returns:
            添加孔后的Workplane对象
        """
        hole_radius = hole.diameter / 2.0
        if hole_radius <= 0:
            logger.warning("孔%s半径为0，跳过", hole.hole_id)
            return workplane

        hole_depth = hole.depth
        if hole.hole_type == "through_hole" or hole_depth <= 0:
            hole_depth = base_height * 1.2
        hole_depth = min(hole_depth, base_height * 1.5)

        center_offset = (
            hole.center_x,
            hole.center_y,
        )

        hole_solid = (
            cq.Workplane("XY")
            .workplane(offset=-hole_depth * 0.1)
            .center(center_offset[0], center_offset[1])
            .circle(hole_radius)
            .extrude(hole_depth + hole_depth * 0.2)
        )

        result = workplane.cut(hole_solid)
        logger.debug(
            "孔%s: 中心=(%.1f,%.1f), 直径=%.2f, 深度=%.1f",
            hole.hole_id, hole.center_x, hole.center_y,
            hole.diameter, hole_depth,
        )
        return result

    def export_stl(
        self,
        conversion_result: ModelConversionResult,
        output_path: str | Path,
        tolerance: float = 0.001,
    ) -> Path:
        """将转换结果导出为STL文件。

        Args:
            conversion_result: 模型转换结果
            output_path: 输出文件路径
            tolerance: STL导出精度(mm)

        Returns:
            导出的STL文件路径

        Raises:
            DxfModelError: 模型无效或导出失败
        """
        if not conversion_result.success:
            raise DxfModelError("模型转换未成功，无法导出STL。"
                               f"错误: {'; '.join(conversion_result.errors)}")

        path = Path(output_path)
        try:
            cq.exporters.export(
                conversion_result.workplane,
                str(path),
                exportType="STL",
                tolerance=tolerance,
            )
            logger.info("STL导出: %s (%.1f KB)", path.name, path.stat().st_size / 1024)
            return path
        except Exception as e:
            raise DxfModelError(f"STL导出失败({path}): {e}") from e

    def export_step(
        self,
        conversion_result: ModelConversionResult,
        output_path: str | Path,
    ) -> Path:
        """将转换结果导出为STEP文件。

        Args:
            conversion_result: 模型转换结果
            output_path: 输出文件路径

        Returns:
            导出的STEP文件路径

        Raises:
            DxfModelError: 模型无效或导出失败
        """
        if not conversion_result.success:
            raise DxfModelError("模型转换未成功，无法导出STEP。"
                               f"错误: {'; '.join(conversion_result.errors)}")

        path = Path(output_path)
        try:
            cq.exporters.export(
                conversion_result.workplane,
                str(path),
                exportType="STEP",
            )
            logger.info("STEP导出: %s (%.1f KB)", path.name, path.stat().st_size / 1024)
            return path
        except Exception as e:
            raise DxfModelError(f"STEP导出失败({path}): {e}") from e

    def create_model_from_dimensions(
        self,
        length: float,
        width: float,
        height: float,
        holes: list[dict[str, float]] | None = None,
    ) -> cq.Workplane:
        """直接根据尺寸参数创建3D模型。

        Args:
            length: 长度(X方向)
            width: 宽度(Y方向)
            height: 高度(Z方向)
            holes: 孔参数列表 [{center_x, center_y, diameter, depth}, ...]

        Returns:
            CadQuery Workplane对象
        """
        try:
            model = self._create_base_solid(length, width, height)
        except Exception as e:
            raise DxfModelError(
                f"直接创建模型失败(尺寸={length}x{width}x{height}mm): {e}"
            ) from e

        if holes:
            for hole_params in holes:
                cx = hole_params.get("center_x", 0)
                cy = hole_params.get("center_y", 0)
                dia = hole_params.get("diameter", 10)
                dep = hole_params.get("depth", height)

                hole_info = HoleFeatureInfo(
                    hole_id=f"HOLE_{len(holes) + 1:03d}",
                    center_x=cx,
                    center_y=cy,
                    diameter=dia,
                    depth=dep,
                    depth_inferred=False,
                )
                try:
                    model = self._add_hole(model, hole_info, height)
                except Exception as e:
                    logger.warning("孔创建失败: %s", e)

        return model