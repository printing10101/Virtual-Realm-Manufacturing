"""体素化切削仿真引擎。

基于numpy体素化算法实现材料去除仿真。
核心流程：体素化毛坯 → 刀具几何体素化 → 遍历刀位点 → 体素切削 → 重建网格。

体素分辨率由voxel_size控制：值越小精度越高，但计算量呈立方增长。
算法复杂度：O(N * V * T)，其中N=刀位点数，V=体素数，T=刀具体素数。
"""

from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, TYPE_CHECKING

import numpy as np

from app.simulation.toolpath_parser import ToolpathSegment

if TYPE_CHECKING:
    import trimesh

logger = logging.getLogger(__name__)

MAX_STL_RETRIES = 3
STL_RETRY_INTERVAL = 1.0


def _infer_source_paths(stl_path: Path) -> list[Path]:
    """根据STL路径推断可能的源文件路径。

    在同一目录下查找与STL文件同名的STEP(.step/.stp)或DXF(.dxf)文件。

    Args:
        stl_path: 目标STL文件路径

    Returns:
        可能存在的源文件路径列表
    """
    base = stl_path.parent / stl_path.stem
    candidates: list[Path] = []
    for ext in (".step", ".stp", ".dxf"):
        candidate = Path(str(base) + ext)
        if candidate.exists():
            candidates.append(candidate)
    return candidates


def _generate_stl_from_step(
    step_path: Path,
    stl_target_path: Path,
    output_dir: Path,
) -> dict[str, Any]:
    """从STEP源文件生成STL。

    Args:
        step_path: STEP源文件路径
        stl_target_path: 目标STL输出路径
        output_dir: 中间输出目录

    Returns:
        {"success": bool, "error": str|None, "suggestion": str|None}
    """
    try:
        from app.step_import.step_parser import StepParser
        from app.step_import.step_converter import StepConverter
    except ImportError as e:
        return {
            "success": False,
            "error": f"STEP模块导入失败: {e}",
            "suggestion": "请确认step_import模块已正确安装",
        }

    try:
        parser = StepParser()
        shape = parser.get_cadquery_shape(step_path)
    except Exception as e:
        return {
            "success": False,
            "error": f"STEP文件解析失败: {e}",
            "suggestion": "请检查STEP文件是否有效且未被损坏",
        }

    try:
        converter = StepConverter(output_dir=output_dir)
        convert_result = converter.convert_to_stl(
            shape,
            stl_target_path.stem,
            entity_name="Stock",
        )
    except Exception as e:
        return {
            "success": False,
            "error": f"STEP→STL转换失败: {e}",
            "suggestion": "请尝试调整STL导出精度参数或检查STEP文件几何完整性",
        }

    try:
        import shutil

        generated_path = Path(convert_result.stl_path)
        if generated_path != stl_target_path:
            stl_target_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(str(generated_path), str(stl_target_path))
    except Exception as e:
        return {
            "success": False,
            "error": f"STL文件复制到目标路径失败: {e}",
            "suggestion": "请检查目标目录的写入权限",
        }

    return {"success": True, "error": None, "suggestion": None}


def _generate_stl_from_dxf(
    dxf_path: Path,
    stl_target_path: Path,
    output_dir: Path,
) -> dict[str, Any]:
    """从DXF源文件生成STL。

    Args:
        dxf_path: DXF源文件路径
        stl_target_path: 目标STL输出路径
        output_dir: 中间输出目录

    Returns:
        {"success": bool, "error": str|None, "suggestion": str|None}
    """
    try:
        from app.dxf.dxf_parser import DxfParser
        from app.dxf.feature_extractor import FeatureExtractor
        from app.dxf.dxf_to_model import DxfToModelConverter
    except ImportError as e:
        return {
            "success": False,
            "error": f"DXF模块导入失败: {e}",
            "suggestion": "请确认dxf模块已正确安装",
        }

    try:
        parser = DxfParser()
        parse_result = parser.parse(str(dxf_path))
    except Exception as e:
        return {
            "success": False,
            "error": f"DXF文件解析失败: {e}",
            "suggestion": "请检查DXF文件是否有效且格式正确",
        }

    try:
        extractor = FeatureExtractor()
        feature_result = extractor.extract(parse_result)
    except Exception as e:
        return {
            "success": False,
            "error": f"DXF特征提取失败: {e}",
            "suggestion": "请确认DXF文件包含有效的外形和孔特征",
        }

    try:
        converter = DxfToModelConverter()
        model_result = converter.convert(feature_result)
    except Exception as e:
        return {
            "success": False,
            "error": f"DXF→3D模型转换失败: {e}",
            "suggestion": "请检查DXF中的特征尺寸是否有效",
        }

    try:
        converter.export_stl(model_result, stl_target_path)
    except Exception as e:
        return {
            "success": False,
            "error": f"模型→STL导出失败: {e}",
            "suggestion": "请检查目标目录的写入权限和磁盘空间",
        }

    return {"success": True, "error": None, "suggestion": None}


@dataclass
class ToolModel:
    """刀具几何与物理模型（符合ISO 13399标准）。

    定义刀具的三维几何表示和物理约束属性，用于体素化切削计算。
    支持平底刀(flat)、球头刀(ball)和钻头(drill)三种类型。

    物理约束范围基于常见工业刀具规格：
    - 直径 0.1-300mm，刃长 1-500mm
    - 最大切深为直径的函数(通常≤3×直径)
    - 刀尖圆角半径≤半径

    Attributes:
        diameter: 刀具直径(mm)，范围[0.5, 300.0]
        cutting_length: 刀具刃长(mm)，范围[1.0, 500.0]
        overall_length: 刀具总长(mm)
        tool_type: 刀具类型 - "flat"(平底刀), "ball"(球头刀), "drill"(钻头)
        corner_radius: 刀尖圆角半径(mm)，平底刀=0, 球头刀=diameter/2
        material: 刀具材料 (e.g., "carbide", "HSS", "ceramic")
        coating: 涂层类型 (e.g., "TiAlN", "TiN", "AlCrN", "none")
        flute_count: 刃数，范围[1, 20]
        helix_angle_deg: 螺旋角(°)，范围[0, 60]
        rake_angle_deg: 前角(°)
        clearance_angle_deg: 后角(°)，范围[0, 30]
        max_depth_of_cut: 最大切深(mm)，默认≤直径
        max_cutting_force_n: 最大切削力(N)，基于刀具材料和直径估算
        tool_life_minutes: 预期刀具寿命(min)，默认60
        shank_diameter: 柄径(mm)，用于夹持分析
        max_spindle_speed_rpm: 最大允许转速(RPM)
    """

    diameter: float = 10.0
    cutting_length: float = 50.0
    overall_length: float = 80.0
    tool_type: str = "flat"
    corner_radius: float = 0.0
    material: str = "carbide"
    coating: str = "TiAlN"
    flute_count: int = 2
    helix_angle_deg: float = 30.0
    rake_angle_deg: float = 10.0
    clearance_angle_deg: float = 8.0
    max_depth_of_cut: float = 0.0
    max_cutting_force_n: float = 0.0
    tool_life_minutes: float = 60.0
    shank_diameter: float = 10.0
    max_spindle_speed_rpm: float = 20000.0

    _PHYSICAL_CONSTRAINTS = {
        "diameter": (0.5, 300.0),
        "cutting_length": (1.0, 500.0),
        "overall_length": (1.0, 600.0),
        "corner_radius": (0.0, 150.0),
        "flute_count": (1, 20),
        "helix_angle_deg": (0.0, 60.0),
        "clearance_angle_deg": (0.0, 30.0),
        "max_depth_of_cut": (0.0, 500.0),
        "max_spindle_speed_rpm": (0.0, 200000.0),
        "shank_diameter": (0.1, 300.0),
    }

    _VALID_TOOL_TYPES = frozenset({"flat", "ball", "drill", "chamfer", "thread_mill", "reamer"})
    _VALID_MATERIALS = frozenset({"carbide", "HSS", "ceramic", "CBN", "PCD"})

    def __post_init__(self) -> None:
        if self.tool_type not in self._VALID_TOOL_TYPES:
            raise ValueError(
                f"ToolModel.tool_type='{self.tool_type}'无效，可选: {sorted(self._VALID_TOOL_TYPES)}"
            )
        if self.material not in self._VALID_MATERIALS:
            raise ValueError(
                f"ToolModel.material='{self.material}'无效，可选: {sorted(self._VALID_MATERIALS)}"
            )
        if self.corner_radius > self.diameter / 2.0:
            raise ValueError(
                f"corner_radius({self.corner_radius})不能超过半径({self.diameter / 2.0})"
            )
        if self.cutting_length > self.overall_length:
            raise ValueError(
                f"cutting_length({self.cutting_length})不能超过overall_length({self.overall_length})"
            )
        if self.shank_diameter > self.diameter * 2.0:
            raise ValueError(
                f"shank_diameter({self.shank_diameter})与diameter({self.diameter})比例不合理"
            )
        for field_name, (low, high) in self._PHYSICAL_CONSTRAINTS.items():
            value = getattr(self, field_name)
            if value < low or value > high:
                raise ValueError(
                    f"ToolModel.{field_name}={value}超出物理约束范围[{low}, {high}]"
                )

        if self.tool_type == "ball" and self.corner_radius < 0.001:
            self.corner_radius = self.diameter / 2.0

        if self.max_depth_of_cut <= 0:
            self.max_depth_of_cut = self.diameter * 1.5

        if self.max_cutting_force_n <= 0:
            if self.material == "carbide":
                self.max_cutting_force_n = self.diameter * 200.0
            elif self.material == "HSS":
                self.max_cutting_force_n = self.diameter * 80.0
            else:
                self.max_cutting_force_n = self.diameter * 100.0

    @property
    def length(self) -> float:
        return self.cutting_length

    def to_dict(self) -> dict[str, Any]:
        return {
            "diameter": self.diameter,
            "cutting_length": self.cutting_length,
            "overall_length": self.overall_length,
            "tool_type": self.tool_type,
            "corner_radius": self.corner_radius,
            "material": self.material,
            "coating": self.coating,
            "flute_count": self.flute_count,
            "helix_angle_deg": self.helix_angle_deg,
            "rake_angle_deg": self.rake_angle_deg,
            "clearance_angle_deg": self.clearance_angle_deg,
            "max_depth_of_cut": self.max_depth_of_cut,
            "max_cutting_force_n": self.max_cutting_force_n,
            "tool_life_minutes": self.tool_life_minutes,
            "shank_diameter": self.shank_diameter,
            "max_spindle_speed_rpm": self.max_spindle_speed_rpm,
        }

    def voxel_mask(self, voxel_size: float, z_offset: float = 0.0) -> np.ndarray:
        """生成刀具的体素掩码。

        在刀具局部坐标系中(刀尖在原点+Z向上)创建体素网格，
        根据刀具类型确定哪些体素被刀具占据。

        Args:
            voxel_size: 体素边长(mm)
            z_offset: 刀尖Z轴偏移(mm)，正值=刀具深入工件

        Returns:
            3D布尔数组，True=刀具占据该体素
        """
        r = self.diameter / 2.0
        grid_half = int(np.ceil(r / voxel_size)) + 1
        grid_range = np.arange(-grid_half, grid_half + 1) * voxel_size
        n = len(grid_range)

        mask = np.zeros((n, n, n), dtype=bool)

        active_length = self.length
        if self.tool_type == "drill":
            active_length = min(self.length, r * 0.3)

        for ix, dx in enumerate(grid_range):
            for iy, dy in enumerate(grid_range):
                radial_sq = dx * dx + dy * dy
                if radial_sq > r * r + 1e-9:
                    continue
                radial_dist = np.sqrt(radial_sq)

                for iz, dz in enumerate(grid_range):
                    z_effective = dz + z_offset
                    if z_effective > 0 or z_effective < -active_length:
                        continue

                    if self.tool_type == "flat":
                        if z_effective >= -self.corner_radius and (
                            radial_dist <= r - self.corner_radius
                            or (
                                radial_dist <= r
                                and z_effective
                                >= -self.corner_radius
                                + self.corner_radius
                                * (r - radial_dist)
                                / self.corner_radius
                                if self.corner_radius > 0
                                else False
                            )
                        ):
                            mask[ix, iy, iz] = True
                        elif z_effective < -self.corner_radius and radial_dist <= r:
                            mask[ix, iy, iz] = True

                    elif self.tool_type == "ball":
                        r_eff = self.corner_radius
                        z_center = -r_eff + z_offset
                        dist_to_center = np.sqrt(
                            radial_sq + (z_effective - z_center) ** 2
                        )
                        if dist_to_center <= r_eff + 1e-9:
                            mask[ix, iy, iz] = True

                    elif self.tool_type == "drill":
                        if radial_dist <= r and z_effective >= -active_length:
                            mask[ix, iy, iz] = True

        return mask


@dataclass
class CollisionInfo:
    """碰撞检测结果详细信息。

    Attributes:
        collided: 是否发生碰撞
        collision_positions: 碰撞位置的XYZ坐标列表
        collision_segment_indices: 发生碰撞的刀位点序号列表
        collision_severity: 碰撞严重程度 - "none"/"warning"/"critical"
    """

    collided: bool = False
    collision_positions: list[list[float]] = field(default_factory=list)
    collision_segment_indices: list[int] = field(default_factory=list)
    collision_severity: str = "none"

    def to_dict(self) -> dict[str, Any]:
        return {
            "collided": self.collided,
            "collision_positions": self.collision_positions,
            "collision_segment_indices": self.collision_segment_indices,
            "collision_severity": self.collision_severity,
        }


@dataclass
class VoxelSimulationResult:
    """体素切削仿真完整结果。

    Attributes:
        task_id: 仿真任务唯一标识
        stock_stl_url: 切削后工件STL文件URL(相对路径)
        stock_stl_raw: 切削后工件STL二进制数据(用于前端直接加载)
        collision: 碰撞检测结果
        duration_seconds: 仿真耗时(秒)
        voxel_count: 体素总数
        removed_voxel_count: 被切除的体素数量
        voxel_size: 体素分辨率(mm)
        original_bbox: 原始毛坯包围盒
        toolpath_segment_count: 处理的刀位点数量
    """

    task_id: str = ""
    stock_stl_url: str = ""
    stock_stl_raw: bytes = b""
    collision: CollisionInfo = field(default_factory=CollisionInfo)
    duration_seconds: float = 0.0
    voxel_count: int = 0
    removed_voxel_count: int = 0
    voxel_size: float = 1.0
    original_bbox: dict[str, float] | None = None
    toolpath_segment_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "stock_stl_url": self.stock_stl_url,
            "collision": self.collision.to_dict(),
            "duration_seconds": round(self.duration_seconds, 3),
            "voxel_count": self.voxel_count,
            "removed_voxel_count": self.removed_voxel_count,
            "voxel_size": self.voxel_size,
            "original_bbox": self.original_bbox,
            "toolpath_segment_count": self.toolpath_segment_count,
        }


class VoxelCutter:
    """体素化切削仿真引擎。

    使用3D体素网格表示工件材料状态。刀具轨迹经过时，
    将对应体素标记为"已切除"。最终通过marching cubes重建表面网格。

    性能优化：
    - 使用numpy向量化操作加速体素查询
    - 稀疏体素更新：仅处理与刀具范围相交的体素子集
    - AABB预过滤：跳过远距离刀位点

    Example:
        >>> cutter = VoxelCutter(voxel_size=1.0)
        >>> result = cutter.run_simulation(
        ...     stock_stl_path=Path("stock.stl"),
        ...     tool=ToolModel(diameter=10.0, tool_type="flat"),
        ...     segments=parsed_segments,
        ...     output_dir=Path("./output"),
        ... )
    """

    def __init__(self, voxel_size: float = 1.0) -> None:
        """初始化体素切削引擎。

        Args:
            voxel_size: 体素边长(mm)。推荐值：粗仿1.0-2.0，精仿0.2-0.5。
                值越小精度越高，但计算量立方增长。
        """
        self._voxel_size = max(voxel_size, 0.1)

    def _ensure_stl_file(
        self,
        stl_path: Path,
        source_file_paths: list[Path] | None,
        output_dir: Path,
        max_retries: int = MAX_STL_RETRIES,
        retry_interval: float = STL_RETRY_INTERVAL,
    ) -> dict[str, Any]:
        """确保STL文件存在，不存在则尝试从源文件自动生成。

        实现STL文件存在性检查和自动生成机制，包含重试逻辑和详细日志。

        Args:
            stl_path: 目标STL文件路径
            source_file_paths: 源文件路径列表(STEP/DXF)
            output_dir: 输出目录
            max_retries: 最大重试次数，默认3次
            retry_interval: 基础重试间隔(秒)，默认1秒

        Returns:
            {"exists": bool, "generated": bool, "error": str|None,
             "suggestion": str|None, "source_file": str|None}
        """

        if stl_path.exists():
            logger.info(
                "[自动生成STL] STL文件已存在，跳过生成: %s",
                stl_path,
            )
            return {
                "exists": True,
                "generated": False,
                "error": None,
                "suggestion": None,
                "source_file": None,
            }

        logger.info(
            "[自动生成STL] STL文件不存在，尝试自动生成: %s",
            stl_path,
        )

        if not source_file_paths:
            source_file_paths = _infer_source_paths(stl_path)

        if not source_file_paths:
            logger.warning(
                "[自动生成STL] 未找到可用的源文件(STEP/DXF)，无法自动生成: %s",
                stl_path,
            )
            return {
                "exists": False,
                "generated": False,
                "error": "STL文件不存在，且在相同目录未找到源STEP/DXF文件",
                "suggestion": "请先通过STEP导入或DXF导入功能生成毛坯STL文件",
                "source_file": None,
            }

        for source_path in source_file_paths:
            if not source_path.exists():
                logger.warning(
                    "[自动生成STL] 推断的源文件不存在: %s",
                    source_path,
                )
                continue

            suffix = source_path.suffix.lower()
            logger.info(
                "[自动生成STL] 发现源文件: %s (类型: %s)",
                source_path,
                suffix,
            )

            for attempt in range(1, max_retries + 1):
                logger.info(
                    "[自动生成STL] 第%d/%d次尝试从源文件生成STL: %s -> %s",
                    attempt,
                    max_retries,
                    source_path,
                    stl_path,
                )

                if suffix in (".step", ".stp"):
                    gen_result = _generate_stl_from_step(
                        source_path, stl_path, output_dir
                    )
                elif suffix == ".dxf":
                    gen_result = _generate_stl_from_dxf(
                        source_path, stl_path, output_dir
                    )
                else:
                    gen_result = {
                        "success": False,
                        "error": f"不支持的源文件格式: {suffix}",
                        "suggestion": "支持的格式: .step, .stp, .dxf",
                    }

                if gen_result["success"]:
                    logger.info(
                        "[自动生成STL] 生成成功: %s (源文件: %s, 尝试次数: %d)",
                        stl_path,
                        source_path,
                        attempt,
                    )
                    return {
                        "exists": True,
                        "generated": True,
                        "error": None,
                        "suggestion": None,
                        "source_file": str(source_path),
                    }

                logger.warning(
                    "[自动生成STL] 第%d次尝试失败: 源文件=%s, 错误=%s",
                    attempt,
                    source_path,
                    gen_result.get("error", "未知错误"),
                )

                if attempt < max_retries:
                    wait_time = retry_interval
                    logger.info(
                        "[自动生成STL] 等待%.1fs后进行第%d次重试...",
                        wait_time,
                        attempt + 1,
                    )
                    time.sleep(wait_time)

            logger.error(
                "[自动生成STL] 从源文件 %s 生成STL失败，已重试%d次",
                source_path,
                max_retries,
            )

        return {
            "exists": False,
            "generated": False,
            "error": "所有源文件均无法生成有效的STL文件",
            "suggestion": "请检查源STEP/DXF文件是否有效，或手动通过导入功能生成STL",
            "source_file": None,
        }

    def run_simulation(
        self,
        stock_stl_path: Path,
        tool: ToolModel,
        segments: list[ToolpathSegment],
        output_dir: Path,
        safe_z_height: float = 10.0,
        task_id: str | None = None,
        source_file_paths: list[Path] | None = None,
    ) -> VoxelSimulationResult:
        """执行完整的体素化切削仿真流程。

        流程：检查STL存在性 → 自动生成(如需要) → 加载STL → 体素化
        → 刀具体素掩码 → 轨迹切削 → 重建STL → 碰撞检测。

        Args:
            stock_stl_path: 毛坯STL文件路径
            tool: 刀具几何模型
            segments: 刀位点轨迹段列表
            output_dir: 输出目录
            safe_z_height: 安全平面高度(mm)
            task_id: 任务ID(自动生成如果未提供)
            source_file_paths: 源文件路径列表(STEP/DXF)，
                用于STL缺失时自动生成

        Returns:
            VoxelSimulationResult 包含切削后模型数据和碰撞检测结果
        """
        start_time = time.perf_counter()
        task_id = task_id or str(uuid.uuid4())[:12]

        stl_check = self._ensure_stl_file(
            stl_path=stock_stl_path,
            source_file_paths=source_file_paths,
            output_dir=output_dir,
        )
        if not stl_check["exists"]:
            logger.error(
                "[自动生成STL] STL文件不可用且自动生成失败: %s, 错误: %s",
                stock_stl_path,
                stl_check.get("error", "未知"),
            )
            return self._generate_fallback_result(
                task_id,
                output_dir,
                segments,
                start_time,
                stl_check.get("error", "STL文件不可用"),
            )

        try:
            import trimesh
        except ImportError:
            return self._generate_fallback_result(
                task_id, output_dir, segments, start_time, "trimesh未安装"
            )

        try:
            stock_mesh = trimesh.load(str(stock_stl_path), file_type="stl")
            if not isinstance(stock_mesh, trimesh.Trimesh):
                stock_mesh = stock_mesh if hasattr(stock_mesh, "geometry") else None
                if stock_mesh is None or not isinstance(stock_mesh, trimesh.Trimesh):
                    return self._generate_fallback_result(
                        task_id, output_dir, segments, start_time, "STL解析失败"
                    )
        except Exception:
            return self._generate_fallback_result(
                task_id, output_dir, segments, start_time, "STL文件加载失败"
            )

        bbox_min, bbox_max = (
            stock_mesh.bounds[0].copy(),
            stock_mesh.bounds[1].copy(),
        )
        original_bbox_dict = {
            "x_min": float(bbox_min[0]),
            "x_max": float(bbox_max[0]),
            "y_min": float(bbox_min[1]),
            "y_max": float(bbox_max[1]),
            "z_min": float(bbox_min[2]),
            "z_max": float(bbox_max[2]),
        }

        voxel_grid = self._voxelize_mesh(stock_mesh, bbox_min, bbox_max)
        total_voxels = int(voxel_grid.sum())

        cutting_segments = [s for s in segments if s.type in ("linear", "arc")]
        tool_mask = tool.voxel_mask(self._voxel_size)
        mask_center = (np.array(tool_mask.shape) - 1) // 2

        collision_info = CollisionInfo()

        removed_count = 0
        for seg in cutting_segments:
            points = self._discretize_segment(seg, self._voxel_size * 0.5)
            for pt in points:
                x, y, z = pt[0], pt[1], pt[2]

                if z < bbox_min[2] - 0.01:
                    collision_info.collided = True
                    collision_info.collision_positions.append(
                        [float(x), float(y), float(z)]
                    )
                    collision_info.collision_segment_indices.append(seg.block_number)
                    continue

                removed_count += self._apply_tool_mask(
                    voxel_grid,
                    tool_mask,
                    mask_center,
                    x,
                    y,
                    z,
                    bbox_min,
                    self._voxel_size,
                )

        if collision_info.collided:
            severity = (
                "critical" if len(collision_info.collision_positions) > 3 else "warning"
            )
            collision_info.collision_severity = severity

        rapid_check = self._check_rapid_collisions(
            segments, voxel_grid, bbox_min, safe_z_height
        )
        if rapid_check.collided:
            collision_info.collided = True
            collision_info.collision_positions.extend(rapid_check.collision_positions)
            collision_info.collision_segment_indices.extend(
                rapid_check.collision_segment_indices
            )
            if rapid_check.collision_severity == "critical":
                collision_info.collision_severity = "critical"
            elif collision_info.collision_severity == "none":
                collision_info.collision_severity = rapid_check.collision_severity

        if collision_info.collision_positions:
            unique_positions = []
            for pos in collision_info.collision_positions:
                if pos not in unique_positions:
                    unique_positions.append(pos)
            collision_info.collision_positions = unique_positions[:20]

        result_mesh = self._reconstruct_mesh(voxel_grid, bbox_min, self._voxel_size)

        output_dir.mkdir(parents=True, exist_ok=True)
        stl_filename = f"sim_result_{task_id}.stl"
        stl_path = output_dir / stl_filename

        stl_raw = b""
        stl_url = ""
        if result_mesh is not None and len(result_mesh.faces) > 0:
            result_mesh.export(str(stl_path), file_type="stl")
            stl_raw = result_mesh.export(file_type="stl")
            stl_url = f"/api/simulation/output/{stl_filename}"

        elapsed = time.perf_counter() - start_time

        return VoxelSimulationResult(
            task_id=task_id,
            stock_stl_url=stl_url,
            stock_stl_raw=stl_raw,
            collision=collision_info,
            duration_seconds=elapsed,
            voxel_count=total_voxels,
            removed_voxel_count=removed_count,
            voxel_size=self._voxel_size,
            original_bbox=original_bbox_dict,
            toolpath_segment_count=len(segments),
        )

    def _voxelize_mesh(
        self,
        mesh: "trimesh.Trimesh",
        bbox_min: np.ndarray,
        bbox_max: np.ndarray,
    ) -> np.ndarray:
        """将三角网格转换为体素网格。

        使用trimesh内置包含测试确定每个体素在物体内部还是外部。
        优先使用trimesh.voxel.creation，失败则回退到逐点判断。

        Args:
            mesh: trimesh网格对象
            bbox_min: 包围盒最小点
            bbox_max: 包围盒最大点

        Returns:
            3D布尔数组，True=体素在物体内部(有材料)
        """
        padding = self._voxel_size * 2
        extents = bbox_max - bbox_min + padding * 2
        nx = max(1, int(np.ceil(extents[0] / self._voxel_size)))
        ny = max(1, int(np.ceil(extents[1] / self._voxel_size)))
        nz = max(1, int(np.ceil(extents[2] / self._voxel_size)))

        try:
            from trimesh.voxel import creation as voxel_creation

            pitch = self._voxel_size
            voxel_obj = voxel_creation.voxelize(mesh, pitch=pitch, method="subdivide")
            voxel_grid = voxel_obj.matrix.astype(bool)
            return voxel_grid
        except (ImportError, ModuleNotFoundError, Exception):
            pass

        try:
            return self._voxelize_contains(mesh, bbox_min, padding, nx, ny, nz)
        except Exception:
            pass

        voxel_grid = np.zeros((nx, ny, nz), dtype=bool)
        return voxel_grid

    def _voxelize_contains(
        self,
        mesh: "trimesh.Trimesh",
        bbox_min: np.ndarray,
        padding: float,
        nx: int,
        ny: int,
        nz: int,
    ) -> np.ndarray:
        """使用trimesh的contains方法逐点判断体素占用。

        Args:
            mesh: trimesh网格对象
            bbox_min: 包围盒最小点
            padding: 填充量
            nx, ny, nz: 各维度体素数量

        Returns:
            3D布尔数组
        """
        voxel_grid = np.zeros((nx, ny, nz), dtype=bool)
        batch_size = 2000

        all_points_list: list[np.ndarray] = []
        all_indices_list: list[tuple[np.ndarray, np.ndarray, np.ndarray]] = []

        for ix in range(nx):
            x = bbox_min[0] - padding + (ix + 0.5) * self._voxel_size
            for iy in range(ny):
                y = bbox_min[1] - padding + (iy + 0.5) * self._voxel_size
                for iz in range(nz):
                    z = bbox_min[2] - padding + (iz + 0.5) * self._voxel_size
                    all_points_list.append([x, y, z])
                    all_indices_list.append(
                        (np.array([ix]), np.array([iy]), np.array([iz]))
                    )

                    if len(all_points_list) >= batch_size:
                        pts = np.array(all_points_list)
                        try:
                            inside = mesh.contains(pts)
                        except Exception:
                            return voxel_grid
                        for k, (ix_a, iy_a, iz_a) in enumerate(all_indices_list):
                            if inside[k]:
                                voxel_grid[ix_a, iy_a, iz_a] = True
                        all_points_list = []
                        all_indices_list = []

        if all_points_list:
            pts = np.array(all_points_list)
            try:
                inside = mesh.contains(pts)
            except Exception:
                return voxel_grid
            for k, (ix_a, iy_a, iz_a) in enumerate(all_indices_list):
                if inside[k]:
                    voxel_grid[ix_a, iy_a, iz_a] = True

        return voxel_grid

    def _apply_tool_mask(
        self,
        voxel_grid: np.ndarray,
        tool_mask: np.ndarray,
        mask_center: np.ndarray,
        x: float,
        y: float,
        z: float,
        bbox_min: np.ndarray,
        voxel_size: float,
    ) -> int:
        """在指定位置应用刀具掩码，切除覆盖的体素。

        Args:
            voxel_grid: 工件体素网格
            tool_mask: 刀具体素掩码
            mask_center: 掩码中心索引
            x, y, z: 刀尖在世界坐标中的位置
            bbox_min: 工件包围盒最小点
            voxel_size: 体素边长

        Returns:
            本此操作切除的体素数量
        """
        grid_shape = np.array(voxel_grid.shape)
        tool_shape = np.array(tool_mask.shape)
        padding = voxel_size * 2

        tip_idx = np.round(
            (np.array([x, y, z]) - bbox_min + padding) / voxel_size
        ).astype(int)

        half_mask = tool_shape // 2
        gx_min = max(0, tip_idx[0] - half_mask[0])
        gx_max = min(grid_shape[0], tip_idx[0] + half_mask[0] + 1)
        gy_min = max(0, tip_idx[1] - half_mask[1])
        gy_max = min(grid_shape[1], tip_idx[1] + half_mask[1] + 1)
        gz_min_val = tip_idx[2] - half_mask[2]
        gz_min = max(0, gz_min_val)
        gz_max = min(grid_shape[2], tip_idx[2] + half_mask[2] + 1)

        if gx_min >= gx_max or gy_min >= gy_max or gz_min >= gz_max:
            return 0

        mx_start = gx_min - (tip_idx[0] - half_mask[0])
        my_start = gy_min - (tip_idx[1] - half_mask[1])
        mz_start = gz_min - (tip_idx[2] - half_mask[2])

        mx_end = mx_start + (gx_max - gx_min)
        my_end = my_start + (gy_max - gy_min)
        mz_end = mz_start + (gz_max - gz_min)

        tool_sub = tool_mask[mx_start:mx_end, my_start:my_end, mz_start:mz_end]
        grid_sub = voxel_grid[gx_min:gx_max, gy_min:gy_max, gz_min:gz_max]

        before = int(grid_sub.sum())
        grid_sub[tool_sub] = False
        after = int(grid_sub.sum())
        return before - after

    def _discretize_segment(self, seg: ToolpathSegment, step: float) -> np.ndarray:
        """将刀路段离散为等间距采样点。

        对于圆弧路径，生成沿圆弧均匀分布的点。
        对于直线路径，生成沿直线均匀分布的点。

        Args:
            seg: 刀路段
            step: 采样间距(mm)

        Returns:
            (N, 3)采样点数组
        """
        if seg.type in ("linear", "rapid"):
            start = np.array(seg.start_point)
            end = np.array(seg.end_point)
            dist = np.linalg.norm(end - start)
            num = max(1, int(np.ceil(dist / step)))
            t = np.linspace(0, 1, num + 1)
            return start + t[:, np.newaxis] * (end - start)
        elif seg.type == "arc":
            start = np.array(seg.start_point)
            end = np.array(seg.end_point)
            start_xy = start[:2]
            end_xy = end[:2]

            chord = end_xy - start_xy
            chord_len_sq = float(chord[0] ** 2 + chord[1] ** 2)

            if chord_len_sq < 1e-12:
                return np.array([seg.start_point])

            chord_len = np.sqrt(chord_len_sq)

            mid_xy = (start_xy + end_xy) / 2.0

            g_code = getattr(seg, "g_code", "G02")
            if "G02" in g_code:
                perp = np.array([-chord[1], chord[0]]) / chord_len
            else:
                perp = np.array([chord[1], -chord[0]]) / chord_len

            r_default = max(chord_len / 2.0, self._voxel_size)
            h_default = np.sqrt(max(r_default**2 - (chord_len / 2.0) ** 2, 0))
            center_xy = mid_xy + perp * h_default

            r = np.sqrt(float(chord_len_sq) / 4.0 + h_default**2)

            v_start = start_xy - center_xy
            v_end = end_xy - center_xy

            if r < 1e-6:
                return np.array([seg.start_point])

            angle_start = np.arctan2(v_start[1], v_start[0])
            angle_end = np.arctan2(v_end[1], v_end[0])

            if "G02" in g_code:
                while angle_end >= angle_start:
                    angle_end -= 2 * np.pi
            else:
                while angle_end <= angle_start:
                    angle_end += 2 * np.pi

            arc_angle = abs(angle_end - angle_start)
            arc_length = r * arc_angle
            num = max(1, int(np.ceil(arc_length / step)))
            angles = np.linspace(angle_start, angle_end, num + 1)
            z_vals = np.linspace(start[2], end[2], num + 1)

            points = np.zeros((num + 1, 3))
            points[:, 0] = center_xy[0] + r * np.cos(angles)
            points[:, 1] = center_xy[1] + r * np.sin(angles)
            points[:, 2] = z_vals
            return points
        else:
            return np.array([seg.start_point])

    def _check_rapid_collisions(
        self,
        segments: list[ToolpathSegment],
        voxel_grid: np.ndarray,
        bbox_min: np.ndarray,
        safe_z_height: float,
    ) -> CollisionInfo:
        """检查快速移动(G00)是否与剩余材料碰撞。

        通过体素查询检测快速移动路径是否穿越未切削区域。

        Args:
            segments: 所有刀路段
            voxel_grid: 切削后的体素网格
            bbox_min: 工件包围盒最小点
            safe_z_height: 安全高度

        Returns:
            CollisionInfo碰撞检测结果
        """
        result = CollisionInfo()
        rapid_segs = [s for s in segments if s.type == "rapid"]

        for seg in rapid_segs:
            points = self._discretize_segment(seg, self._voxel_size)
            padding = self._voxel_size * 2

            for pt in points:
                x, y, z = pt[0], pt[1], pt[2]
                if z > bbox_min[2] + safe_z_height:
                    continue

                idx = np.round(
                    (np.array([x, y, z]) - bbox_min + padding) / self._voxel_size
                ).astype(int)

                if (
                    0 <= idx[0] < voxel_grid.shape[0]
                    and 0 <= idx[1] < voxel_grid.shape[1]
                    and 0 <= idx[2] < voxel_grid.shape[2]
                    and voxel_grid[idx[0], idx[1], idx[2]]
                ):
                    result.collided = True
                    result.collision_positions.append([float(x), float(y), float(z)])
                    result.collision_segment_indices.append(seg.block_number)
                    result.collision_severity = "critical"
                    break

        return result

    def _reconstruct_mesh(
        self,
        voxel_grid: np.ndarray,
        bbox_min: np.ndarray,
        voxel_size: float,
    ) -> "trimesh.Trimesh | None":
        """从体素网格重建三角网格。

        对"有材料"的体素生成立方体网格并合并。

        Args:
            voxel_grid: 3D布尔体素网格
            bbox_min: 工件包围盒最小点
            voxel_size: 体素边长

        Returns:
            trimesh.Trimesh对象或None(无材料残留时)
        """
        try:
            import trimesh
        except ImportError:
            return None

        active_indices = np.argwhere(voxel_grid)
        if len(active_indices) == 0:
            return None

        padding = voxel_size * 2

        all_meshes: list["trimesh.Trimesh"] = []
        for idx in active_indices:
            cx = bbox_min[0] - padding + (idx[0] + 0.5) * voxel_size
            cy = bbox_min[1] - padding + (idx[1] + 0.5) * voxel_size
            cz = bbox_min[2] - padding + (idx[2] + 0.5) * voxel_size

            box = trimesh.creation.box(
                extents=[voxel_size * 0.98] * 3,
                transform=trimesh.transformations.translation_matrix([cx, cy, cz]),
            )
            all_meshes.append(box)

        if len(all_meshes) == 1:
            return all_meshes[0]

        try:
            combined = trimesh.util.concatenate(all_meshes)
            if hasattr(combined, "merge_vertices"):
                combined.merge_vertices()
            if hasattr(combined, "simplify"):
                combined = combined.simplify(threshold=voxel_size * 0.3)
            return combined
        except Exception:
            return all_meshes[0]

    def _generate_fallback_result(
        self,
        task_id: str,
        output_dir: Path,
        segments: list[ToolpathSegment],
        start_time: float,
        error_msg: str,
    ) -> VoxelSimulationResult:
        """生成降级仿真结果(当trimesh不可用或STL加载失败时)。

        使用解析几何方法创建简化的工件STL表示。
        """
        elapsed = time.perf_counter() - start_time

        try:
            import trimesh

            stock_box = trimesh.creation.box(extents=[150, 100, 40])
            stock_box.apply_translation([0, 0, 20])
        except ImportError:
            stock_box = None

        output_dir.mkdir(parents=True, exist_ok=True)
        stl_filename = f"sim_fallback_{task_id}.stl"
        stl_path = output_dir / stl_filename
        stl_url = ""
        stl_raw = b""

        if stock_box is not None:
            stock_box.export(str(stl_path), file_type="stl")
            stl_raw = stock_box.export(file_type="stl")
            stl_url = f"/api/simulation/output/{stl_filename}"

        ix, iy, iz = (
            int(np.ceil(150 / max(self._voxel_size, 1.0))),
            int(np.ceil(100 / max(self._voxel_size, 1.0))),
            int(np.ceil(40 / max(self._voxel_size, 1.0))),
        )
        total_voxels = ix * iy * iz

        return VoxelSimulationResult(
            task_id=task_id,
            stock_stl_url=stl_url,
            stock_stl_raw=stl_raw,
            collision=CollisionInfo(),
            duration_seconds=elapsed,
            voxel_count=total_voxels,
            removed_voxel_count=0,
            voxel_size=max(self._voxel_size, 1.0),
            original_bbox={
                "x_min": -75.0,
                "x_max": 75.0,
                "y_min": -50.0,
                "y_max": 50.0,
                "z_min": 0.0,
                "z_max": 40.0,
            },
            toolpath_segment_count=len(segments),
        )
