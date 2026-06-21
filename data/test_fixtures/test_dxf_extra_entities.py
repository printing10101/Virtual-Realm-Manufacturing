"""合成 DXF 测试 HATCH/BLOCK INSERT/SPLINE 提取"""
import os
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "python"))

import ezdxf

from app.dxf.dxf_parser import DxfParser


def make_test_dxf(path: str) -> None:
    """创建带 HATCH/INSERT/SPLINE 的 DXF"""
    doc = ezdxf.new(setup=True)
    doc.dxfversion = "R2010"
    msp = doc.modelspace()

    # 1) 一个 100x100 矩形作为外框
    msp.add_lwpolyline(
        [(0, 0), (100, 0), (100, 100), (0, 100)], dxfattribs={"closed": True}
    )

    # 2) 一个 HATCH（用 SOLID 填充）— 模拟填充区
    hatch = msp.add_hatch(dxfattribs={"layer": "HATCH_LAYER"})
    hatch.set_pattern_fill("SOLID")
    # 边界：20x20 矩形
    boundary = [(20, 20), (80, 20), (80, 80), (20, 80)]
    hatch.paths.add_polyline_path(
        [ezdxf.math.Vec2(x, y) for x, y in boundary]
    )

    # 3) 一个 INSERT — 引用一个未定义的块（仅测解析）
    ins = msp.add_blockref(
        "STD_BOLT",
        insert=(50, 50),
        dxfattribs={"layer": "INSERT_LAYER"},
    )
    ins.add_attrib(tag="DIA", text="M10")

    # 4) 一个 SPLINE — 三次贝塞尔
    fit_points = [
        (0, 50, 0),
        (20, 80, 0),
        (50, 60, 0),
        (80, 80, 0),
        (100, 50, 0),
    ]
    msp.add_spline(
        fit_points=fit_points,
        degree=3,
        dxfattribs={"layer": "SPLINE_LAYER"},
    )

    doc.saveas(path)
    print(f"  生成测试 DXF: {path}")


def main() -> int:
    with tempfile.NamedTemporaryFile(
        suffix=".dxf", delete=False, mode="wb"
    ) as f:
        tmp = f.name
    try:
        make_test_dxf(tmp)
        print("\n=== 解析结果 ===")
        result = DxfParser().parse(tmp)
        print(f"  LWPOLYLINE: {len(result.polylines)}")
        print(f"  HATCH:      {len(result.hatches)}")
        print(f"  INSERT:     {len(result.inserts)}")
        print(f"  SPLINE:     {len(result.splines)}")
        print(f"  warnings:   {result.warnings}")
        print(f"  errors:     {result.errors}")
        print(f"  extents:    {result.extents}")
        print(f"  entity_counts: {result.entity_counts}")
        # 验证
        assert len(result.hatches) == 1, f"预期 1 个 HATCH，实际 {len(result.hatches)}"
        assert len(result.hatches[0].boundary_paths) >= 1
        print(f"  HATCH 边界: {result.hatches[0].boundary_paths[0][:3]}...")
        assert len(result.inserts) == 1, f"预期 1 个 INSERT，实际 {len(result.inserts)}"
        assert result.inserts[0].block_name == "STD_BOLT"
        assert result.inserts[0].position == (50, 50, 0.0)
        assert len(result.splines) == 1, f"预期 1 个 SPLINE，实际 {len(result.splines)}"
        assert result.splines[0].degree == 3
        # control_points 可能用 fit_points 兜底，所以只断言有点
        assert (
            len(result.splines[0].control_points) > 0
            or len(result.splines[0].fit_points) > 0
        ), "SPLINE 应至少有 control_points 或 fit_points"
        print(f"  SPLINE control_points: {len(result.splines[0].control_points)}")
        print(f"  SPLINE fit_points:    {len(result.splines[0].fit_points)}")
        print("  ✅ 全部通过")
        return 0
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


if __name__ == "__main__":
    raise SystemExit(main())
