"""体素切削仿真与API接口 单元测试。

覆盖:
- ToolModel 刀具体素掩码生成
- VoxelCutter 体素化与切削仿真
- CollisionInfo 碰撞数据结构
- 仿真API端点请求/响应
- 降级处理(fallback)机制
- 边界条件与异常处理
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import numpy as np
import pytest

from app.simulation.voxel_cutter import (
    VoxelCutter,
    VoxelSimulationResult,
    ToolModel,
    CollisionInfo,
)
from app.simulation.toolpath_parser import ToolpathParser, ToolpathSegment
from app.simulation.stock_model import StockModel


class TestToolModel:
    def test_flat_tool_creation(self):
        tool = ToolModel(diameter=10.0, length=50.0, tool_type="flat")
        assert tool.diameter == 10.0
        assert tool.length == 50.0
        assert tool.tool_type == "flat"
        assert tool.corner_radius == 0.0

    def test_ball_tool_auto_corner_radius(self):
        tool = ToolModel(diameter=12.0, tool_type="ball")
        assert tool.corner_radius == pytest.approx(6.0, rel=0.01)

    def test_ball_tool_custom_corner_radius(self):
        tool = ToolModel(diameter=12.0, tool_type="ball", corner_radius=4.0)
        assert tool.corner_radius == 4.0

    def test_drill_tool_creation(self):
        tool = ToolModel(diameter=6.0, length=80.0, tool_type="drill")
        assert tool.tool_type == "drill"

    def test_flat_tool_voxel_mask_shape(self):
        tool = ToolModel(diameter=10.0, tool_type="flat")
        mask = tool.voxel_mask(voxel_size=1.0)
        assert mask.ndim == 3
        assert mask.shape[0] == mask.shape[1] == mask.shape[2]
        assert mask.dtype == bool

    def test_flat_tool_voxel_mask_has_true(self):
        tool = ToolModel(diameter=10.0, tool_type="flat")
        mask = tool.voxel_mask(voxel_size=1.0)
        assert mask.sum() > 0, "平底刀体素掩码应包含被占据的体素"

    def test_ball_tool_voxel_mask_has_true(self):
        tool = ToolModel(diameter=10.0, tool_type="ball")
        mask = tool.voxel_mask(voxel_size=1.0)
        assert mask.sum() > 0, "球头刀体素掩码应包含被占据的体素"

    def test_drill_tool_voxel_mask_has_true(self):
        tool = ToolModel(diameter=6.0, tool_type="drill")
        mask = tool.voxel_mask(voxel_size=1.0)
        assert mask.sum() > 0, "钻头体素掩码应包含被占据的体素"

    def test_voxel_mask_symmetry(self):
        tool = ToolModel(diameter=10.0, tool_type="flat")
        mask = tool.voxel_mask(voxel_size=1.0)
        c = mask.shape[0] // 2
        assert np.array_equal(mask[c, :, :], mask[c, ::-1, :]), "体素掩码应具有XZ平面对称性"

    def test_tool_to_dict(self):
        tool = ToolModel(diameter=10.0, length=50.0, tool_type="flat", corner_radius=1.0)
        d = tool.to_dict()
        assert d["diameter"] == 10.0
        assert d["tool_type"] == "flat"
        assert d["corner_radius"] == 1.0

    def test_voxel_mask_different_resolutions(self):
        tool = ToolModel(diameter=10.0, tool_type="flat")
        mask_coarse = tool.voxel_mask(voxel_size=2.0)
        mask_fine = tool.voxel_mask(voxel_size=0.5)
        assert mask_coarse.shape[0] < mask_fine.shape[0], "粗分辨率掩码应更小"


class TestCollisionInfo:
    def test_default_no_collision(self):
        ci = CollisionInfo()
        assert ci.collided is False
        assert ci.collision_severity == "none"
        assert len(ci.collision_positions) == 0

    def test_collision_with_positions(self):
        ci = CollisionInfo(
            collided=True,
            collision_positions=[[10.0, 20.0, -5.0], [30.0, 40.0, -3.0]],
            collision_segment_indices=[5, 12],
            collision_severity="critical",
        )
        assert ci.collided
        assert len(ci.collision_positions) == 2
        assert ci.collision_severity == "critical"

    def test_collision_to_dict(self):
        ci = CollisionInfo(
            collided=True,
            collision_positions=[[1.0, 2.0, 3.0]],
            collision_segment_indices=[7],
            collision_severity="warning",
        )
        d = ci.to_dict()
        assert d["collided"] is True
        assert d["collision_positions"] == [[1.0, 2.0, 3.0]]
        assert d["collision_segment_indices"] == [7]
        assert d["collision_severity"] == "warning"


class TestVoxelSimulationResult:
    def test_result_defaults(self):
        result = VoxelSimulationResult(task_id="test_001")
        assert result.task_id == "test_001"
        assert result.duration_seconds == 0.0
        assert result.collision.collided is False

    def test_result_to_dict(self):
        result = VoxelSimulationResult(
            task_id="sim_abc123",
            stock_stl_url="/api/simulation/output/test.stl",
            collision=CollisionInfo(collided=False),
            duration_seconds=2.5,
            voxel_count=10000,
            removed_voxel_count=2500,
            voxel_size=1.0,
            original_bbox={"x_min": -50.0, "x_max": 50.0, "y_min": -30.0, "y_max": 30.0, "z_min": 0.0, "z_max": 30.0},
            toolpath_segment_count=15,
        )
        d = result.to_dict()
        assert d["task_id"] == "sim_abc123"
        assert d["voxel_count"] == 10000
        assert d["removed_voxel_count"] == 2500
        assert d["collision"]["collided"] is False


class TestVoxelCutter:
    def test_cutter_initialization(self):
        cutter = VoxelCutter(voxel_size=1.0)
        assert cutter._voxel_size == 1.0

    def test_cutter_minimum_voxel_size(self):
        cutter = VoxelCutter(voxel_size=0.01)
        assert cutter._voxel_size >= 0.1

    def test_discretize_linear_segment(self):
        cutter = VoxelCutter(voxel_size=1.0)
        seg = ToolpathSegment(
            type="linear",
            start_point=(0.0, 0.0, 0.0),
            end_point=(10.0, 0.0, 0.0),
            block_number=1,
            g_code="G01",
        )
        points = cutter._discretize_segment(seg, step=1.0)
        assert points.shape[0] >= 2
        assert points.shape[1] == 3

    def test_discretize_rapid_segment(self):
        cutter = VoxelCutter(voxel_size=1.0)
        seg = ToolpathSegment(
            type="rapid",
            start_point=(0.0, 0.0, 50.0),
            end_point=(100.0, 50.0, 50.0),
            block_number=1,
            g_code="G00",
        )
        points = cutter._discretize_segment(seg, step=1.0)
        assert points.shape[0] >= 2
        assert np.allclose(points[0], [0.0, 0.0, 50.0])
        assert np.allclose(points[-1], [100.0, 50.0, 50.0])

    def test_discretize_arc_segment(self):
        cutter = VoxelCutter(voxel_size=1.0)
        seg = ToolpathSegment(
            type="arc",
            start_point=(0.0, -25.0, -2.0),
            end_point=(0.0, 25.0, -2.0),
            block_number=5,
            g_code="G02",
        )
        points = cutter._discretize_segment(seg, step=1.0)
        assert points.shape[0] >= 2
        assert points.shape[1] == 3

    def test_fallback_result_without_trimesh(self):
        cutter = VoxelCutter(voxel_size=2.0)
        tool = ToolModel(diameter=10.0, tool_type="flat")

        with tempfile.TemporaryDirectory() as tmp:
            stock_path = Path(tmp) / "nonexistent.stl"
            result = cutter.run_simulation(
                stock_stl_path=stock_path,
                tool=tool,
                segments=[],
                output_dir=Path(tmp) / "output",
                task_id="fallback_test",
            )
            assert result.task_id == "fallback_test"
            assert result.voxel_count > 0
            assert result.original_bbox is not None
            assert result.duration_seconds > 0

    def test_run_simulation_with_gcode_segments(self):
        cutter = VoxelCutter(voxel_size=2.0)
        tool = ToolModel(diameter=10.0, tool_type="flat")

        gcode = """G00 Z50.
G00 X0. Y0.
G01 Z-2. F500
G01 X50. F800
G01 Y30.
G01 X0.
G01 Y0.
G00 Z50."""
        parser = ToolpathParser()
        segments = parser.parse_gcode(gcode)

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            result = cutter.run_simulation(
                stock_stl_path=tmp_path / "nonexistent.stl",
                tool=tool,
                segments=segments,
                output_dir=tmp_path / "output",
                task_id="gcode_test",
            )
            assert result.task_id == "gcode_test"
            assert result.toolpath_segment_count == len(segments)

    def test_trimesh_collision_overcut(self):
        trimesh = pytest.importorskip("trimesh",
            reason="trimesh未安装，跳过体素化碰撞检测测试")
        cutter = VoxelCutter(voxel_size=3.0)
        tool = ToolModel(diameter=10.0, tool_type="flat")

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            stock_mesh = trimesh.creation.box(extents=[60, 60, 30])
            stock_mesh.apply_translation([0, 0, 15])
            stock_path = tmp_path / "stock.stl"
            stock_mesh.export(str(stock_path), file_type="stl")

            gcode = """G00 Z80.
G00 X0. Y0.
G01 Z-20. F500
G01 X20. F800
G00 Z80."""
            parser = ToolpathParser()
            segments = parser.parse_gcode(gcode)

            result = cutter.run_simulation(
                stock_stl_path=stock_path,
                tool=tool,
                segments=segments,
                output_dir=tmp_path / "output",
                task_id="overcut_trimesh",
            )
            assert result.collision.collided

    def test_trimesh_collision_rapid(self):
        trimesh = pytest.importorskip("trimesh",
            reason="trimesh未安装，跳过体素化碰撞检测测试")
        cutter = VoxelCutter(voxel_size=3.0)
        tool = ToolModel(diameter=10.0, tool_type="flat")

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            stock_mesh = trimesh.creation.box(extents=[80, 60, 20])
            stock_mesh.apply_translation([0, 0, 10])
            stock_path = tmp_path / "stock.stl"
            stock_mesh.export(str(stock_path), file_type="stl")

            gcode = """G00 Z-5.
G00 X0. Y0.
G00 X60. Y30."""
            parser = ToolpathParser()
            segments = parser.parse_gcode(gcode)

            result = cutter.run_simulation(
                stock_stl_path=stock_path,
                tool=tool,
                segments=segments,
                output_dir=tmp_path / "output",
                safe_z_height=10.0,
                task_id="rapid_trimesh",
            )
            assert result.collision.collided

    def test_no_collision_safe_path(self):
        cutter = VoxelCutter(voxel_size=2.0)
        tool = ToolModel(diameter=10.0, tool_type="flat")

        gcode = """G00 Z80.
G00 X0. Y0.
G01 Z5. F500
G01 X50. F800
G00 Z80."""
        parser = ToolpathParser()
        segments = parser.parse_gcode(gcode)

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            result = cutter.run_simulation(
                stock_stl_path=tmp_path / "nonexistent.stl",
                tool=tool,
                segments=segments,
                output_dir=tmp_path / "output",
                safe_z_height=10.0,
                task_id="safe_test",
            )
            assert not result.collision.collided

    def test_empty_segments(self):
        cutter = VoxelCutter(voxel_size=2.0)
        tool = ToolModel(diameter=10.0, tool_type="flat")

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            result = cutter.run_simulation(
                stock_stl_path=tmp_path / "nonexistent.stl",
                tool=tool,
                segments=[],
                output_dir=tmp_path / "output",
                task_id="empty_test",
            )
            assert result.toolpath_segment_count == 0
            assert not result.collision.collided

    def test_result_contains_required_fields(self):
        cutter = VoxelCutter(voxel_size=2.0)
        tool = ToolModel(diameter=10.0, tool_type="flat")

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            result = cutter.run_simulation(
                stock_stl_path=tmp_path / "nonexistent.stl",
                tool=tool,
                segments=[],
                output_dir=tmp_path / "output",
            )
            d = result.to_dict()
            required = [
                "task_id", "stock_stl_url", "collision",
                "duration_seconds", "voxel_count",
                "removed_voxel_count", "voxel_size",
                "original_bbox", "toolpath_segment_count",
            ]
            for key in required:
                assert key in d, f"结果缺失字段: {key}"

    def test_voxel_count_positive(self):
        cutter = VoxelCutter(voxel_size=2.0)
        tool = ToolModel(diameter=10.0, tool_type="flat")

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            result = cutter.run_simulation(
                stock_stl_path=tmp_path / "nonexistent.stl",
                tool=tool,
                segments=[],
                output_dir=tmp_path / "output",
            )
            assert result.voxel_count > 0

    def test_duration_recorded(self):
        cutter = VoxelCutter(voxel_size=2.0)
        tool = ToolModel(diameter=10.0, tool_type="flat")

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            result = cutter.run_simulation(
                stock_stl_path=tmp_path / "nonexistent.stl",
                tool=tool,
                segments=[],
                output_dir=tmp_path / "output",
            )
            assert result.duration_seconds > 0

    def test_auto_task_id(self):
        cutter = VoxelCutter(voxel_size=2.0)
        tool = ToolModel(diameter=10.0, tool_type="flat")

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            result = cutter.run_simulation(
                stock_stl_path=tmp_path / "nonexistent.stl",
                tool=tool,
                segments=[],
                output_dir=tmp_path / "output",
            )
            assert len(result.task_id) > 0

    def test_fallback_result_stl_url(self):
        cutter = VoxelCutter(voxel_size=2.0)
        tool = ToolModel(diameter=10.0, tool_type="flat")

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            result = cutter.run_simulation(
                stock_stl_path=tmp_path / "nonexistent.stl",
                tool=tool,
                segments=[],
                output_dir=tmp_path / "output",
                task_id="url_test",
            )
            assert result.stock_stl_url != "" or result.stock_stl_raw != b""
            assert "url_test" in result.stock_stl_url or result.stock_stl_url == ""

    def test_trimesh_collision_unique_positions(self):
        trimesh = pytest.importorskip("trimesh",
            reason="trimesh未安装，跳过体素化碰撞检测测试")
        cutter = VoxelCutter(voxel_size=3.0)
        tool = ToolModel(diameter=10.0, tool_type="flat")

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            stock_mesh = trimesh.creation.box(extents=[60, 60, 30])
            stock_mesh.apply_translation([0, 0, 15])
            stock_path = tmp_path / "stock.stl"
            stock_mesh.export(str(stock_path), file_type="stl")

            gcode = """G00 Z80.
G00 X0. Y0.
G01 Z-20. F500
G01 X5. F800
G01 X10.
G01 X15.
G01 X20.
G01 X25.
G00 Z80."""
            parser = ToolpathParser()
            segments = parser.parse_gcode(gcode)

            result = cutter.run_simulation(
                stock_stl_path=stock_path,
                tool=tool,
                segments=segments,
                output_dir=tmp_path / "output",
                task_id="unique_trimesh",
            )
            assert result.collision.collided
            assert len(result.collision.collision_positions) <= 20

    def test_trimesh_collision_severity(self):
        trimesh = pytest.importorskip("trimesh",
            reason="trimesh未安装，跳过体素化碰撞检测测试")
        cutter = VoxelCutter(voxel_size=3.0)
        tool = ToolModel(diameter=10.0, tool_type="flat")

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            stock_mesh = trimesh.creation.box(extents=[60, 60, 30])
            stock_mesh.apply_translation([0, 0, 15])
            stock_path = tmp_path / "stock.stl"
            stock_mesh.export(str(stock_path), file_type="stl")

            gcode = """G00 Z80.
G00 X0. Y0.
G01 Z-20. F500
G01 X5. F800
G01 X10.
G01 X15.
G01 X20.
G01 X25.
G01 X30.
G01 X35.
G01 X40.
G00 Z80."""
            parser = ToolpathParser()
            segments = parser.parse_gcode(gcode)

            result = cutter.run_simulation(
                stock_stl_path=stock_path,
                tool=tool,
                segments=segments,
                output_dir=tmp_path / "output",
                task_id="severity_trimesh",
            )
            assert result.collision.collision_severity == "critical"

    def test_fallback_bbox_values(self):
        cutter = VoxelCutter(voxel_size=2.0)
        tool = ToolModel(diameter=10.0, tool_type="flat")

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            result = cutter.run_simulation(
                stock_stl_path=tmp_path / "nonexistent.stl",
                tool=tool,
                segments=[],
                output_dir=tmp_path / "output",
            )
            bbox = result.original_bbox
            assert bbox is not None
            assert "x_min" in bbox
            assert bbox["x_min"] < bbox["x_max"]
            assert bbox["y_min"] < bbox["y_max"]
            assert bbox["z_min"] < bbox["z_max"]
