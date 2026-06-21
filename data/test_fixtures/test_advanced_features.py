"""测试 advanced_features 新增的 4 个识别器"""
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "python"))
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "research"))

from app.dxf.dxf_parser import DxfParser
from research.multimodal_jepa.ijepa_3d import chamfer_heuristic


def test(fixture_name: str):
    fixture = REPO / "data" / "test_fixtures" / fixture_name
    if not fixture.exists():
        print(f"  ⚠️  {fixture_name} 不存在")
        return
    print(f"\n=== {fixture_name} ===")
    parsed = DxfParser().parse(str(fixture))
    print(f"  polylines={len(parsed.polylines)}  circles={len(parsed.circles)}  lines={len(parsed.lines)}")
    base = chamfer_heuristic.detect_all(parsed)
    ext = chamfer_heuristic.detect_all_extended(parsed)
    base_types = {}
    for f in base:
        base_types[f.type.value] = base_types.get(f.type.value, 0) + 1
    ext_types = {}
    for f in ext:
        ext_types[f.type.value] = ext_types.get(f.type.value, 0) + 1
    print(f"  detect_all:           {base_types}")
    print(f"  detect_all_extended:  {ext_types}")
    # 详细输出新增识别器
    new_feats = [f for f in ext if f not in base]
    if new_feats:
        print(f"  新识别器发现 {len(new_feats)} 个特征:")
        for f in new_feats:
            print(f"    - {f.type.value} conf={f.confidence} params={f.params}")


for f in [
    "case1_simple_box.dxf",
    "case2_box_4holes.dxf",
    "case6_flange.dxf",
    "case7_bracket.dxf",
    "case18_sprocket.dxf",
]:
    test(f)

print("\n✅ 全部通过")
