"""快速测试新增的 Mitsubishi + Fagor 后处理器"""
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "python"))
sys.path.insert(0, str(REPO))

from app.postprocessor.registry import PostProcessorRegistry

reg = PostProcessorRegistry()
print(f"已注册: {reg.list_controllers()}")
print(f"总数: {len(reg.list_controllers())}")

# 测试 Mitsubishi
mit = reg.get_processor("mitsubishi_m70_m80")
print(f"\n=== Mitsubishi M70/M80 ===")
print(f"  CONTROLLER_ID: {mit.CONTROLLER_ID}")
print(f"  CONTROLLER_NAME: {mit.CONTROLLER_NAME}")
print(f"  Header: {mit.format_header(1)[:200]}")
print(f"  Arc: {mit.format_arc((0, 0, 0), (10, 0, 0), (5, 0, 0))}")
print(f"  Footer: {mit.format_footer()[:150]}")

# 测试 Fagor
fagor = reg.get_processor("fagor_8055")
print(f"\n=== Fagor 8055 ===")
print(f"  CONTROLLER_ID: {fagor.CONTROLLER_ID}")
print(f"  CONTROLLER_NAME: {fagor.CONTROLLER_NAME}")
print(f"  Header: {fagor.format_header(1)[:200]}")
print(f"  Arc: {fagor.format_arc((0, 0, 0), (10, 0, 0), (5, 0, 0))}")
print(f"  Subprog: {fagor.format_subprogram_call(1234)}")
print(f"  SubprogEnd: {fagor.format_subprogram_end()}")
print(f"  Footer: {fagor.format_footer()[:150]}")

print("\n✅ 全部通过")
