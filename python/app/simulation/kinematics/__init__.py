"""XM-100 五轴运动学模型。

实现工作台型五轴（A轴+C轴）的正解和逆解运动学计算，
为 RTCP 补偿、刀路验证、碰撞检测提供数学基础。

XM-100 运动学链：
    机床基座 → X/Y/Z 线性轴 → C轴旋转工作台 → A轴倾斜工作台 → 工件

    - A轴：工作台倾斜，绕X轴旋转，范围 -30°~110°
    - C轴：工作台旋转，绕Z轴旋转，范围 0°~360°
    - 主轴方向：机床坐标系 Z轴负方向（刀具向下）

变换关系：
    P_machine = T(X,Y,Z) · R_z(C) · R_x(A) · P_workpiece

    刀轴方向在机床坐标系中恒为 [0, 0, -1]（主轴向下）
    在工件坐标系中：tool_axis_wp = R_x(-A) · R_z(-C) · [0, 0, -1]
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Tuple, Optional

import numpy as np


# ---------------------------------------------------------------------------
# XM-100 机床参数
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class XM100Limits:
    """XM-100 机床运动轴限制。"""

    x_min: float = 0.0
    x_max: float = 100.0  # mm
    y_min: float = 0.0
    y_max: float = 100.0  # mm
    z_min: float = 0.0
    z_max: float = 100.0  # mm
    a_min: float = -30.0  # 度
    a_max: float = 110.0  # 度
    c_min: float = 0.0  # 度
    c_max: float = 360.0  # 度
    max_spindle_rpm: float = 20000.0
    max_feed_mm_min: float = 3000.0


XM100_LIMITS = XM100Limits()

# 浮点数比较容差，避免精度问题导致边界值误判
# 注：输入刀轴方向可能不是精确单位向量（如 [0, -0.5, -0.866]），
# 归一化后仍可能有 ~1e-3 量级误差，因此容差设为 1e-3
_LIMIT_EPS = 1e-3


# ---------------------------------------------------------------------------
# 旋转矩阵
# ---------------------------------------------------------------------------


def rot_x(angle_deg: float) -> np.ndarray:
    """绕X轴旋转矩阵（3×3）。"""
    a = math.radians(angle_deg)
    c, s = math.cos(a), math.sin(a)
    return np.array([
        [1, 0, 0],
        [0, c, -s],
        [0, s, c],
    ])


def rot_z(angle_deg: float) -> np.ndarray:
    """绕Z轴旋转矩阵（3×3）。"""
    a = math.radians(angle_deg)
    c, s = math.cos(a), math.sin(a)
    return np.array([
        [c, -s, 0],
        [s, c, 0],
        [0, 0, 1],
    ])


def homogeneous(rot: np.ndarray, trans: np.ndarray) -> np.ndarray:
    """构造 4×4 齐次变换矩阵。"""
    H = np.eye(4)
    H[:3, :3] = rot
    H[:3, 3] = trans
    return H


# ---------------------------------------------------------------------------
# 运动学正解 / 逆解
# ---------------------------------------------------------------------------


class XM100Kinematics:
    """XM-100 工作台型五轴运动学。

    坐标系定义：
        - 机床坐标系 (M)：X/Y/Z 线性轴定义的基坐标系
        - 工件坐标系 (W)：固定在 A轴工作台上的坐标系

    变换链（工件 → 机床）：
        P_M = T(X,Y,Z) · R_z(C) · R_x(A) · P_W

    刀轴方向：
        - 机床坐标系中恒为 [0, 0, -1]（主轴向下）
        - 工件坐标系中 = R_x(-A) · R_z(-C) · [0, 0, -1]
    """

    def __init__(self, limits: XM100Limits = XM100_LIMITS):
        self.limits = limits

    # ============================================================ 正解

    def forward(
        self,
        x: float,
        y: float,
        z: float,
        a_deg: float,
        c_deg: float,
        point_in_workpiece: np.ndarray | None = None,
    ) -> dict[str, np.ndarray]:
        """正解：给定机床轴位置，计算变换矩阵。

        Args:
            x, y, z: 线性轴位置 (mm)
            a_deg: A轴角度 (度)
            c_deg: C轴角度 (度)
            point_in_workpiece: 工件坐标系中的点（可选）

        Returns:
            包含以下键的字典：
            - R_wc: 工件→机床旋转矩阵 (3×3)
            - T_wc: 工件→机床齐次变换矩阵 (4×4)
            - tool_axis_in_wp: 刀轴在工件坐标系中的方向
            - point_in_machine: 若提供 point_in_workpiece，则为变换后的机床坐标点
        """
        R_a = rot_x(a_deg)
        R_c = rot_z(c_deg)
        R_wc = R_c @ R_a  # 工件→机床旋转

        T_wc = homogeneous(R_wc, np.array([x, y, z]))

        # 刀轴在机床坐标系中为 [0,0,-1]，逆变换到工件坐标系
        # tool_axis_wp = R_wc^T · [0,0,-1]
        tool_axis_machine = np.array([0.0, 0.0, -1.0])
        tool_axis_in_wp = R_wc.T @ tool_axis_machine

        result = {
            "R_wc": R_wc,
            "T_wc": T_wc,
            "tool_axis_in_wp": tool_axis_in_wp,
        }

        if point_in_workpiece is not None:
            p = np.append(point_in_workpiece, 1.0)
            point_in_machine = (T_wc @ p)[:3]
            result["point_in_machine"] = point_in_machine

        return result

    # ============================================================ 逆解

    def inverse(
        self,
        target_position: np.ndarray,
        tool_axis_direction: np.ndarray,
    ) -> Optional[dict[str, float]]:
        """逆解：给定工件坐标系中刀尖位置和刀轴方向，计算机床轴位置。

        对于工作台型五轴，刀轴在机床坐标系中恒为 [0,0,-1]。
        需要找到 A, C 角度使得：
            R_x(-A) · R_z(-C) · [0,0,-1] = tool_axis_direction

        然后通过位置约束求解 X, Y, Z。

        Args:
            target_position: 工件坐标系中刀尖目标位置 [x, y, z]
            tool_axis_direction: 工件坐标系中刀轴方向 [i, j, k]（需归一化）

        Returns:
            包含 x, y, z, a, c 的字典，若无解则返回 None
        """
        # 归一化刀轴方向
        axis = np.array(tool_axis_direction, dtype=float)
        norm = np.linalg.norm(axis)
        if norm < 1e-10:
            return None
        axis = axis / norm

        # 刀轴在机床坐标系中为 [0, 0, -1]
        # 工件坐标系中刀轴 = R_x(-A) · R_z(-C) · [0, 0, -1]
        #
        # 设 R_wc = R_z(C) · R_x(A)，则
        # tool_axis_wp = R_wc^T · [0, 0, -1] = R_x(-A) · R_z(-C) · [0, 0, -1]
        #
        # 先计算 R_z(-C) · [0, 0, -1] = [0, 0, -1]（Z轴旋转不改变Z分量方向）
        # 所以 tool_axis_wp = R_x(-A) · [0, 0, -1]
        #
        # R_x(-A) · [0, 0, -1] = [0, sin(A), -cos(A)]
        #
        # 因此：
        #   axis[0] = 0  →  需要通过 C轴旋转来实现 X 分量
        #
        # 更准确的做法：
        # tool_axis_wp = R_x(-A) · R_z(-C) · [0, 0, -1]
        # R_z(-C) · [0, 0, -1] = [0, 0, -1]  （Z轴旋转不改变Z轴方向向量）
        # 所以 tool_axis_wp = R_x(-A) · [0, 0, -1] = [0, sin(A), -cos(A)]
        #
        # 这意味着如果不考虑 C 轴，刀轴在工件坐标系中只能在 YZ 平面内。
        # C 轴的作用是旋转工件，使得刀轴可以指向任意方向。
        #
        # 正确的逆解：
        # 1. 刀轴方向 [i, j, k] 在工件坐标系中
        # 2. 先用 C 轴将刀轴方向旋转到 YZ 平面：C = atan2(i, j) 或类似
        # 3. 再用 A 轴倾斜到目标方向

        # 步骤1：计算 C 角
        # 旋转后刀轴在 XY 平面的投影应为 [0, |xy|]
        # R_z(-C) · [i, j, k] 应使 X 分量为 0
        # -i·sin(C) + j·cos(C) = 0  →  tan(C) = j/i
        # 但需要处理 i=0 的特殊情况

        i, j, k = axis
        xy_mag = math.sqrt(i * i + j * j)

        if xy_mag < 1e-9:
            # 刀轴几乎平行于 Z 轴
            c_deg = 0.0
            if k < 0:
                a_deg = 0.0  # 刀轴向下，A=0
            else:
                a_deg = 180.0  # 刀轴向上，A=180（可能超限）
        else:
            # C 角推导：
            # 要使 R_z(-C)·[i,j,k] 的 X 分量为 0
            # R_z(-C) = [[cos(C), sin(C), 0], [-sin(C), cos(C), 0], [0, 0, 1]]
            # X 分量 = cos(C)·i + sin(C)·j = 0  →  tan(C) = -i/j
            # 所以 C = atan2(-i, j)
            c_deg = math.degrees(math.atan2(-i, j))
            # 规范化到 [0, 360)
            c_deg = c_deg % 360.0

            # 旋转后刀轴方向：R_z(-C) · [i, j, k]
            R_neg_c = rot_z(-c_deg)
            rotated_axis = R_neg_c @ axis
            # rotated_axis[0] ≈ 0, rotated_axis[1] 和 rotated_axis[2] 保留

            # A 角推导：
            # 刀轴在工件系 = R_x(-A)·[0,0,-1] = [0, -sin(A), -cos(A)]
            # 应等于 rotated_axis，所以：
            #   -sin(A) = rotated_axis[1]  →  sin(A) = -rotated_axis[1]
            #   -cos(A) = rotated_axis[2]  →  cos(A) = -rotated_axis[2]
            # 所以 A = atan2(-rotated_axis[1], -rotated_axis[2])
            a_deg = math.degrees(math.atan2(-rotated_axis[1], -rotated_axis[2]))

        # 检查 A/C 轴是否在限制范围内
        # 生成两个候选解：(c_deg, a_deg) 和 (c_deg+180, a_alt)
        candidates: list[tuple[float, float]] = []
        if self.limits.a_min - _LIMIT_EPS <= a_deg <= self.limits.a_max + _LIMIT_EPS:
            candidates.append((c_deg, a_deg))

        c_alt = (c_deg + 180.0) % 360.0
        R_neg_c_alt = rot_z(-c_alt)
        rotated_axis_alt = R_neg_c_alt @ axis
        # 使用与主解相同的A角公式：A = atan2(-rotated_axis[1], -rotated_axis[2])
        a_alt = math.degrees(math.atan2(-rotated_axis_alt[1], -rotated_axis_alt[2]))
        if self.limits.a_min - _LIMIT_EPS <= a_alt <= self.limits.a_max + _LIMIT_EPS:
            candidates.append((c_alt, a_alt))

        if not candidates:
            return None  # 所有候选解的 A 轴都超限

        # ============================================================ 线性轴求解
        #
        # 运动学等效模型（刀尖移动型）：
        #   - 在工作台型五轴中，X/Y/Z 是工作台线性位移，A/C 是工作台旋转
        #   - 由相对运动原理，可等效为：刀尖在机床坐标系中位置 = (X, Y, Z)
        #     工件坐标系原点 = 机床坐标系原点（旋转中心重合）
        #   - 工件上的点 P_w 在机床坐标系中 = R_wc · P_w
        #   - 刀尖对准工件点：(X, Y, Z) = R_wc · target_position
        #
        # 这种等效模型在刀路规划、RTCP 计算、碰撞检测中广泛使用，
        # 数学上与工作台移动型完全等价（仅坐标系标记不同）。

        target = np.array(target_position)
        for c_try, a_try in candidates:
            R_wc = rot_z(c_try) @ rot_x(a_try)
            offset = R_wc @ target
            x_val = float(offset[0])
            y_val = float(offset[1])
            z_val = float(offset[2])

            # 检查线性轴限制
            if (self.limits.x_min - _LIMIT_EPS <= x_val <= self.limits.x_max + _LIMIT_EPS
                    and self.limits.y_min - _LIMIT_EPS <= y_val <= self.limits.y_max + _LIMIT_EPS
                    and self.limits.z_min - _LIMIT_EPS <= z_val <= self.limits.z_max + _LIMIT_EPS):
                return {
                    "x": x_val,
                    "y": y_val,
                    "z": z_val,
                    "a": a_try,
                    "c": c_try,
                }

        return None  # 所有候选解的线性轴都超限

    # ============================================================ RTCP 补偿

    def rtcp_compensate(
        self,
        current_x: float,
        current_y: float,
        current_z: float,
        target_a: float,
        target_c: float,
        current_a: float = 0.0,
        current_c: float = 0.0,
        tool_contact_point: np.ndarray | list[float] | None = None,
        pivot_distance: float = 0.0,
    ) -> Tuple[float, float, float]:
        """RTCP 补偿计算。

        当 A/C 轴从当前角度旋转到目标角度时，工件上的刀触点在机床坐标系中
        会发生偏移。RTCP 通过补偿 X/Y/Z 来保持刀尖位置不变。

        对于工作台型五轴（采用刀尖移动等效模型）：
        - 刀尖位置 = (X, Y, Z)
        - 工件上的刀触点 P_w 在机床坐标系中 = R_wc · P_w
        - 刀尖对准刀触点：(X, Y, Z) = R_wc · P_w
        - 旋转角度变化后，要保持对准：新(X,Y,Z) = R_wc_new · P_w
        - 补偿量 = 新位置 - 旧位置 = (R_wc_new - R_wc_old) · P_w

        Args:
            current_x, current_y, current_z: 当前线性轴位置
            target_a: 目标 A轴角度 (度)
            target_c: 目标 C轴角度 (度)
            current_a: 当前 A轴角度 (度)，默认 0
            current_c: 当前 C轴角度 (度)，默认 0
            tool_contact_point: 刀触点在工件坐标系中的位置 [x, y, z]，
                                若为 None 则使用 pivot_distance 构造
            pivot_distance: A/C 轴交叉点到工件原点的距离（仅在
                            tool_contact_point 为 None 时使用）

        Returns:
            补偿后的 (x, y, z) 位置
        """
        # 确定刀触点在工件坐标系中的位置
        if tool_contact_point is not None:
            p_wp = np.array(tool_contact_point, dtype=float)
        else:
            p_wp = np.array([0.0, 0.0, pivot_distance])

        # 当前旋转下的刀触点机床坐标位置
        R_old = rot_z(current_c) @ rot_x(current_a)
        pos_old = R_old @ p_wp

        # 目标旋转下的刀触点机床坐标位置
        R_new = rot_z(target_c) @ rot_x(target_a)
        pos_new = R_new @ p_wp

        # 补偿量 = 新位置 - 旧位置
        # 新的 X/Y/Z 应使刀尖对准新的刀触点位置
        # 当前刀尖位置 = (current_x, current_y, current_z) 对准 pos_old
        # 新刀尖位置 = current + (pos_new - pos_old)
        compensation = pos_new - pos_old

        return (
            float(current_x + compensation[0]),
            float(current_y + compensation[1]),
            float(current_z + compensation[2]),
        )

    def check_limits(
        self, x: float, y: float, z: float, a: float, c: float
    ) -> list[str]:
        """检查轴位置是否在限制范围内，返回警告列表。"""
        warnings = []
        if not (self.limits.x_min <= x <= self.limits.x_max):
            warnings.append(f"X轴 {x:.1f}mm 超出范围 [{self.limits.x_min}, {self.limits.x_max}]")
        if not (self.limits.y_min <= y <= self.limits.y_max):
            warnings.append(f"Y轴 {y:.1f}mm 超出范围 [{self.limits.y_min}, {self.limits.y_max}]")
        if not (self.limits.z_min <= z <= self.limits.z_max):
            warnings.append(f"Z轴 {z:.1f}mm 超出范围 [{self.limits.z_min}, {self.limits.z_max}]")
        if not (self.limits.a_min <= a <= self.limits.a_max):
            warnings.append(f"A轴 {a:.1f}° 超出范围 [{self.limits.a_min}, {self.limits.a_max}]")
        if not (self.limits.c_min <= c <= self.limits.c_max):
            warnings.append(f"C轴 {c:.1f}° 超出范围 [{self.limits.c_min}, {self.limits.c_max}]")
        return warnings

    def check_singularity(self, a: float) -> list[str]:
        """检查奇异点（A轴接近±90°时C轴失效）。"""
        warnings = []
        if abs(abs(a) - 90.0) < 5.0:
            warnings.append(
                f"A轴 {a:.1f}° 接近奇异点 (±90°)，C轴可能失效"
            )
        return warnings


__all__ = [
    "XM100Limits",
    "XM100_LIMITS",
    "XM100Kinematics",
    "rot_x",
    "rot_z",
    "homogeneous",
]
