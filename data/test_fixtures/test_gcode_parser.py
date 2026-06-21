"""测试 G 代码反向解析器"""
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "python"))

from app.postprocessor.gcode_parser import parse_gcode, to_dxf_like_segments


# === 测试 1: 简单 G00 + G01 ===
g1 = """
%
O0001 (TEST 1)
G21 G17 G40 G49 G80 G90 G94
G00 G90 G54 X0. Y0. Z50.
T01 M06
M03 S3000
M08
G00 X10. Y10.
G01 Z-5. F100.
G01 X50. F200.
G01 Y50.
G02 X60. Y60. I10. J0.
G03 X40. Y80. I-10. J10.
G01 X10. Y10.
G00 Z50.
M09
M05
M30
%
"""

print("=== Test 1: 标准加工程序 ===")
r = parse_gcode(g1, "test1")
print(f"  lines_total={r.lines_total} parsed={r.lines_parsed} segments={len(r.segments)}")
print(f"  bbox={r.bounding_box}")
print(f"  tool_changes={r.tool_changes}")
print(f"  errors={r.errors}")
print(f"  warnings={r.warnings[:3]}")
assert r.lines_parsed >= 10
assert len(r.segments) >= 8
assert r.tool_changes == [(6, 1)]  # T01 M06 在第 6 行
assert r.bounding_box["min_x"] == 0.0
assert r.bounding_box["max_x"] >= 60.0
# 第一个 segment 应该是 G00
assert r.segments[0].motion == "G00"
# 应该有圆弧
arcs = [s for s in r.segments if s.motion in ("G02", "G03")]
assert len(arcs) == 2
print(f"  圆弧段数: {len(arcs)}")
print(f"  第一段圆弧: motion={arcs[0].motion} radius={arcs[0].radius:.2f} cw={arcs[0].clockwise}")
print("  ✅ PASS\n")

# === 测试 2: 增量模式 ===
g2 = """
G21 G90
G00 X0. Y0. Z10.
G91
G01 X10. Y0. F100
G01 X0. Y10.
G01 X-10. Y0.
G01 X0. Y-10.
G90
G00 Z50.
"""

print("=== Test 2: 增量模式 G91 ===")
r2 = parse_gcode(g2, "test2")
print(f"  segments={len(r2.segments)}")
print(f"  bbox={r2.bounding_box}")
# 矩形路径在 G91 模式下从 (10,10) 移动到 (10,10)
# X: 0+10, 10+0, 10-10, 10+0 = 10
# Y: 0+0, 0+10, 10+0, 10-10 = 0
# 最终位置应该是 (10, 10) 不是 (0, 0)
assert r2.bounding_box["min_x"] >= 0.0  # X 始终 >= 0
print(f"  终点 X: {r2.segments[-1].target[0]:.2f}, Y: {r2.segments[-1].target[1]:.2f}")
print("  ✅ PASS\n")

# === 测试 3: 圆弧 R 模式 ===
g3 = """
G21 G90
G00 X0. Y0.
G01 Z-1. F50
G01 X10. F100
G02 X20. Y0. R10.
G01 X30.
G03 X20. Y10. R10.
"""

print("=== Test 3: 圆弧 R 模式 ===")
r3 = parse_gcode(g3, "test3")
print(f"  segments={len(r3.segments)}")
arcs3 = [s for s in r3.segments if s.motion in ("G02", "G03")]
print(f"  圆弧段数: {len(arcs3)}")
for a in arcs3:
    print(f"    {a.motion} R={a.radius:.2f} center=({a.center[0]:.2f}, {a.center[1]:.2f}) cw={a.clockwise}")
assert len(arcs3) == 2
print("  ✅ PASS\n")

# === 测试 4: 注释 / 空行 / 大小写 ===
g4 = """
; 完整注释行
(块注释 1)
G21 G17
  ;  缩进注释
  G00 X0. Y0.  ; 行内注释
g01 x10. y0.  (小写也行)
G01 X10. Y20.
"""

print("=== Test 4: 注释和大小写 ===")
r4 = parse_gcode(g4, "test4")
print(f"  lines_total={r4.lines_total} parsed={r4.lines_parsed}")
print(f"  segments={len(r4.segments)}")
assert len(r4.segments) == 3  # G00 + 2 个 G01
print("  ✅ PASS\n")

# === 测试 5: 转换函数 ===
print("=== Test 5: to_dxf_like_segments ===")
items = to_dxf_like_segments(r.segments)
print(f"  items={len(items)}")
assert len(items) == len(r.segments)
for i, it in enumerate(items[:3]):
    print(f"    {i}: {it}")
print("  ✅ PASS\n")

print("🎉 全部 5 个 G 代码反向解析测试通过")
