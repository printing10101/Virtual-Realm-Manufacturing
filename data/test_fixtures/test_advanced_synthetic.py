"""合成数据测试 advanced_features（不依赖真实 DXF）"""
import os
import sys
from pathlib import Path
from dataclasses import dataclass, field

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "python"))
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "research"))

from research.multimodal_jepa.ijepa_3d.advanced_features import (
    detect_multi_cavity,
    detect_island,
    detect_long_cavity,
    detect_hole_array,
)


@dataclass
class FakePoly:
    vertices: list = field(default_factory=list)
    layer: str = "0"
    is_closed: bool = True


@dataclass
class FakeCircle:
    center: tuple = (0.0, 0.0, 0.0)
    radius: float = 5.0
    layer: str = "0"


# 测试 1: 多型腔（3 个相同尺寸矩形）
print("=== Test 1: 多型腔 ===")
pls = [
    FakePoly([(0, 0), (10, 0), (10, 10), (0, 10)], layer="cavity"),
    FakePoly([(20, 0), (30, 0), (30, 10), (20, 10)], layer="cavity"),
    FakePoly([(40, 0), (50, 0), (50, 10), (40, 10)], layer="cavity"),
]
feats = detect_multi_cavity(pls)
print(f"  检测到 {len(feats)} 个")
for f in feats:
    print(f"    {f.type.value}  cavity_count={f.params.get('cavity_count')}  area={f.params.get('cavity_area_mm2')}")
assert len(feats) == 1, f"预期 1，实际 {len(feats)}"
assert feats[0].params["cavity_count"] == 3
print("  ✅ PASS\n")

# 测试 2: 岛屿
print("=== Test 2: 岛屿 ===")
pls = [
    FakePoly([(0, 0), (100, 0), (100, 100), (0, 100)], layer="pocket"),  # 外型腔 100x100
    FakePoly([(40, 40), (60, 40), (60, 60), (40, 60)], layer="island"),  # 内岛屿 20x20
]
feats = detect_island(pls)
print(f"  检测到 {len(feats)} 个")
for f in feats:
    print(f"    {f.type.value}  fill_ratio={f.params.get('fill_ratio')}")
assert len(feats) == 1, f"预期 1，实际 {len(feats)}"
print("  ✅ PASS\n")

# 测试 3: 长型腔（两个：10:1 和 5:1）
print("=== Test 3: 长型腔 ===")
pls = [
    FakePoly([(0, 0), (100, 0), (100, 10), (0, 10)]),  # 长宽比 10:1
    FakePoly([(0, 20), (50, 20), (50, 30), (0, 30)]),  # 5:1
    FakePoly([(0, 40), (50, 40), (50, 60), (0, 60)]),  # 5:6 不算
]
feats = detect_long_cavity(pls)
print(f"  检测到 {len(feats)} 个")
for f in feats:
    print(f"    {f.type.value}  aspect={f.params.get('aspect_ratio')}  orientation={f.params.get('orientation')}")
assert len(feats) == 2, f"预期 2，实际 {len(feats)}"
print("  ✅ PASS\n")

# 测试 4: 孔阵列（6 个等距圆）
print("=== Test 4: 孔阵列 ===")
cs = [FakeCircle(center=(i * 20.0, 0.0, 0.0), radius=5.0) for i in range(6)]
feats = detect_hole_array(cs)
print(f"  检测到 {len(feats)} 个")
for f in feats:
    print(f"    {f.type.value}  count={f.params.get('hole_count')}  pitch={f.params.get('pitch_mm')}  nn_cv={f.params.get('nearest_neighbor_cv')}")
assert len(feats) == 1, f"预期 1，实际 {len(feats)}"
assert feats[0].params["hole_count"] == 6
print("  ✅ PASS\n")

# 测试 5: 乱序孔（CV 过高，不应该识别为阵列）
print("=== Test 5: 非均匀孔（负样本）===")
cs = [
    FakeCircle(center=(0, 0, 0), radius=5),
    FakeCircle(center=(20, 0, 0), radius=5),
    FakeCircle(center=(100, 0, 0), radius=5),
]
feats = detect_hole_array(cs)
print(f"  检测到 {len(feats)} 个（预期 0）")
assert len(feats) == 0, f"预期 0，实际 {len(feats)}"
print("  ✅ PASS\n")

print("🎉 全部 5 个测试通过")
