"""导出工具函数。

提供 CAD 模型导出到各种格式的通用工具。
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def export_to_stl(
    geometry: Any,
    output_path: Path | str,
    tolerance: float = 0.1,
    angular_tolerance: float = 0.1,
) -> bool:
    """导出几何体到 STL 格式。

    Args:
        geometry: CadQuery Workplane 或类似对象
        output_path: 输出文件路径
        tolerance: 线性公差
        angular_tolerance: 角度公差

    Returns:
        导出是否成功
    """
    try:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # 尝试使用 CadQuery 导出
        try:
            import cadquery as cq
            if hasattr(geometry, 'val'):
                # CadQuery Workplane 对象
                cq.exporters.export(geometry.val(), str(output_path), cq.exporters.ExportTypes.STL, tolerance=tolerance)
            else:
                # 假设是 OCP 对象
                cq.exporters.export(geometry, str(output_path), cq.exporters.ExportTypes.STL, tolerance=tolerance)
            logger.info(f"STL 导出成功: {output_path}")
            return True
        except ImportError:
            logger.warning("CadQuery 不可用，尝试使用简化 STL 导出")
            # 简化的 STL 导出（仅支持基本形状）
            return _export_stl_fallback(geometry, output_path)

    except (OSError, ValueError, TypeError, RuntimeError) as e:
        logger.error("STL 导出失败: %s", e, exc_info=True)
        return False


def _export_stl_fallback(geometry: Any, output_path: Path) -> bool:
    """简化的 STL 导出回退方案。"""
    try:
        # 检查是否有 to_stl 方法
        if hasattr(geometry, 'to_stl'):
            stl_content = geometry.to_stl()
            output_path.write_text(stl_content, encoding='utf-8')
            return True
        
        # 检查是否有 mesh 属性
        if hasattr(geometry, 'mesh'):
            mesh = geometry.mesh()
            if hasattr(mesh, 'to_stl'):
                stl_content = mesh.to_stl()
                output_path.write_text(stl_content, encoding='utf-8')
                return True
        
        logger.warning("无法导出 STL：几何体对象不支持 STL 导出")
        return False
    except Exception as e:
        logger.error("STL 回退导出失败: %s", e)
        return False


def export_to_step(
    geometry: Any,
    output_path: Path | str,
) -> bool:
    """导出几何体到 STEP 格式。

    Args:
        geometry: CadQuery Workplane 或类似对象
        output_path: 输出文件路径

    Returns:
        导出是否成功
    """
    try:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # 尝试使用 CadQuery 导出
        try:
            import cadquery as cq
            if hasattr(geometry, 'val'):
                # CadQuery Workplane 对象
                cq.exporters.export(geometry.val(), str(output_path), cq.exporters.ExportTypes.STEP)
            else:
                # 假设是 OCP 对象
                cq.exporters.export(geometry, str(output_path), cq.exporters.ExportTypes.STEP)
            logger.info(f"STEP 导出成功: {output_path}")
            return True
        except ImportError:
            logger.warning("CadQuery 不可用，尝试使用简化 STEP 导出")
            return _export_step_fallback(geometry, output_path)

    except (OSError, ValueError, TypeError, RuntimeError) as e:
        logger.error("STEP 导出失败: %s", e, exc_info=True)
        return False


def _export_step_fallback(geometry: Any, output_path: Path) -> bool:
    """简化的 STEP 导出回退方案。"""
    try:
        # 检查是否有 to_step 方法
        if hasattr(geometry, 'to_step'):
            step_content = geometry.to_step()
            output_path.write_text(step_content, encoding='utf-8')
            return True
        
        # 检查是否有 mesh 属性
        if hasattr(geometry, 'mesh'):
            mesh = geometry.mesh()
            if hasattr(mesh, 'to_step'):
                step_content = mesh.to_step()
                output_path.write_text(step_content, encoding='utf-8')
                return True
        
        logger.warning("无法导出 STEP：几何体对象不支持 STEP 导出")
        return False
    except Exception as e:
        logger.error("STEP 回退导出失败: %s", e)
        return False


def export_to_svg(
    geometry: Any,
    output_path: Path | str,
    projection_dir: tuple[float, float, float] = (0.0, 0.0, 1.0),
) -> bool:
    """导出几何体到 SVG 格式（2D 投影）。

    Args:
        geometry: CadQuery Workplane 或类似对象
        output_path: 输出文件路径
        projection_dir: 投影方向向量

    Returns:
        导出是否成功
    """
    try:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # 尝试使用 CadQuery 导出
        try:
            import cadquery as cq
            # CadQuery SVG 导出需要投影方向
            if hasattr(geometry, 'val'):
                cq.exporters.export(
                    geometry.val(),
                    str(output_path),
                    cq.exporters.ExportTypes.SVG,
                    opt={
                        "projectionDir": projection_dir,
                        "width": 800,
                        "height": 600,
                        "showAxes": False,
                    }
                )
            else:
                cq.exporters.export(
                    geometry,
                    str(output_path),
                    cq.exporters.ExportTypes.SVG,
                    opt={
                        "projectionDir": projection_dir,
                        "width": 800,
                        "height": 600,
                        "showAxes": False,
                    }
                )
            logger.info(f"SVG 导出成功: {output_path}")
            return True
        except ImportError:
            logger.warning("CadQuery 不可用，尝试使用简化 SVG 导出")
            return _export_svg_fallback(geometry, output_path, projection_dir)

    except (OSError, ValueError, TypeError, RuntimeError) as e:
        logger.error("SVG 导出失败: %s", e, exc_info=True)
        return False


def _export_svg_fallback(
    geometry: Any,
    output_path: Path,
    projection_dir: tuple[float, float, float] = (0.0, 0.0, 1.0),
) -> bool:
    """简化的 SVG 导出回退方案。"""
    try:
        # 检查是否有 to_svg 方法
        if hasattr(geometry, 'to_svg'):
            svg_content = geometry.to_svg(projection_dir=projection_dir)
            output_path.write_text(svg_content, encoding='utf-8')
            return True
        
        # 检查是否有 mesh 属性
        if hasattr(geometry, 'mesh'):
            mesh = geometry.mesh()
            if hasattr(mesh, 'to_svg'):
                svg_content = mesh.to_svg(projection_dir=projection_dir)
                output_path.write_text(svg_content, encoding='utf-8')
                return True
        
        logger.warning("无法导出 SVG：几何体对象不支持 SVG 导出")
        return False
    except Exception as e:
        logger.error("SVG 回退导出失败: %s", e)
        return False


def get_export_formats() -> list[str]:
    """获取支持的导出格式列表。

    Returns:
        支持的格式列表
    """
    return ["stl", "step", "svg"]
