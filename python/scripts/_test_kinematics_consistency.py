"""临时测试：逆解数学正确性验证。

验证逻辑（工作台型五轴）：
  给定任意刀轴方向 axis（可含X分量）→ 逆解得 A/C
  → 验证1：R_z(-C)·axis 的X分量 ≈ 0（C轴消除了X分量）
  → 验证2：R_x(-A)·[0,0,-1] == R_z(-C)·axis（A角实现了旋转后的方向）

工作台型五轴运动学：
  - 刀轴在机床坐标系恒为 [0,0,-1]
  - 刀轴在工件坐标系 = R_x(-A)·R_z(-C)·[0,0,-1] = R_x(-A)·[0,0,-1] = [0,-sin(A),-cos(A)]
  - X分量始终=0，所以用户给定的X分量≠0的刀轴方向需要C轴旋转工件来"消除"
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import numpy as np
from app.simulation.kinematics import XM100Kinematics, XM100Limits, rot_x, rot_z

kin = XM100Kinematics(XM100Limits())

print("=== 逆解数学正确性验证（工作台型五轴）===")
print("验证：R_z(-C)·axis 的X分量≈0 且 R_x(-A)·[0,0,-1]==R_z(-C)·axis")
print()

# 测试用例：各种刀轴方向（单位向量）
test_cases = [
    (0.0, 0.0, -1.0, "垂直向下"),
    (0.0, -0.5, -0.866, "A=30° 侧铣"),
    (0.0, -0.707, -0.707, "A=45° 侧铣"),
    (0.0, -1.0, 0.0, "A=90° 水平"),
    (0.5, -0.5, -0.707, "复合方向1"),
    (-0.5, 0.5, -0.707, "复合方向2"),
    (0.707, 0.0, -0.707, "XZ平面倾斜"),
    (0.0, 0.5, -0.866, "A=-30° 反向"),
    (0.3, -0.4, -0.866, "任意方向1"),
    (-0.6, -0.5, -0.624, "任意方向2"),
]

success = 0
total = 0
for i, j, k, desc in test_cases:
    total += 1
    axis = np.array([i, j, k])
    axis = axis / np.linalg.norm(axis)
    target = [50.0, 50.0, 50.0]
    inv = kin.inverse(target, axis)
    if inv is not None:
        a_out = inv["a"]
        c_out = inv["c"]
        # 验证1：R_z(-C)·axis 的X分量≈0
        R_neg_c = rot_z(-c_out)
        axis_rotated = R_neg_c @ axis
        x_check = abs(axis_rotated[0])
        # 验证2：R_x(-A)·[0,0,-1] == axis_rotated
        R_neg_a = rot_x(-a_out)
        tool_axis_calc = R_neg_a @ np.array([0.0, 0.0, -1.0])
        diff = np.linalg.norm(tool_axis_calc - axis_rotated)
        if x_check < 0.01 and diff < 0.01:
            success += 1
            status = "✓"
        else:
            status = "✗"
        print(f"  {desc:20s} axis=({i:.3f},{j:.3f},{k:.3f}) -> A={a_out:6.1f} C={c_out:6.1f} "
              f"X_check={x_check:.4f} diff={diff:.4f} {status}")
    else:
        print(f"  {desc:20s} axis=({i:.3f},{j:.3f},{k:.3f}) -> 不可行（A/C或线性轴超限）")

print(f"\n逆解数学正确性: {success}/{total} 通过")
print(f"成功率: {success/total*100:.1f}%")
