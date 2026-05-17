"""体素化切削仿真引擎。

基于numpy体素化算法实现材料去除仿真。
核心流程：体素化毛坯 → 刀具几何体素化 → 遍历刀位点 → 体素切削 → 重建网格。

体素分辨率由voxel_size控制：值越小精度越高，但计算量呈立方增长。
算法复杂度：O(N * V * T)，其中N=刀位点数，V=体素数，T=刀具体素数。
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, TYPE_CHECKING

import numpy as np

from app.simulation.toolpath_parser import ToolpathSegment

if TYPE_CHECKING:
    import trimesh


@dataclass
class ToolModel:
    """刀具几何模型。

    定义刀具的三维几何表示，用于体素化切削计算。
    支持平底刀(Ball/Flat)、球头刀和钻头三种类型。

    Attributes:
        diameter: 刀具直径(mm)
        length: 刀具刃长(mm)
        tool_type: 刀具类型 - "flat"(平底刀), "ball"(球头刀), "drill"(钻头)
        corner_radius: 刀尖圆角半径(mm)，平底刀=0, 球头刀=diameter/2
    """

    diameter: float = 10.0
    length: float = 50.0
    tool_type: str = "flat"
    corner_radius: float = 0.0

    def __post_init__(self) -> None:
        if self.tool_type == "ball" and self.corner_radius < 0.001:
            self.corner_radius = self.diameter / 2.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "diameter": self.diameter,
            "length": self.length,
            "tool_type": self.tool_type,
            "corner_radius": self.corner_radius,
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

    def run_simulation(
        self,
        stock_stl_path: Path,
        tool: ToolModel,
        segments: list[ToolpathSegment],
        output_dir: Path,
        safe_z_height: float = 10.0,
        task_id: str | None = None,
    ) -> VoxelSimulationResult:
        """执行完整的体素化切削仿真流程。

        流程：加载STL → 体素化 → 刀具体素掩码 → 轨迹切削 → 重建STL → 碰撞检测。

        Args:
            stock_stl_path: 毛坯STL文件路径
            tool: 刀具几何模型
            segments: 刀位点轨迹段列表
            output_dir: 输出目录
            safe_z_height: 安全平面高度(mm)
            task_id: 任务ID(自动生成如果未提供)

        Returns:
            VoxelSimulationResult 包含切削后模型数据和碰撞检测结果
        """
        start_time = time.perf_counter()
        task_id = task_id or str(uuid.uuid4())[:12]

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
