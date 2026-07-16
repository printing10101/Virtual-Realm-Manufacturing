"""数据契约：颤振预测链路的核心数据结构。

设计原则
========
本模块是 shared/ 薄契约层的数据契约定义，被 engineering/ 和 research/ 双向依赖。

- **字段一致性**：所有字段与现有实现完全一致，避免 schema 漂移
- **零重依赖**：仅使用 stdlib（dataclasses / typing），不依赖 torch / numpy / pydantic
- **契约边界**：本模块只定义数据结构，不包含业务逻辑
- **D-2 学术诚信**：ChatterReport 包含 task_status + prediction_method 字段，
  供阶段 6 加载器校验契约完整性

字段来源映射
============
- MachineParams     ← python/app/simulation/chatter/stability.py
- ToolParams        ← python/app/simulation/chatter/stability.py
- ChatterParams     ← python/app/simulation/chatter/stability.py
- MaterialParams    ← python/app/cutting_parameters/material_resolver.py
- CuttingParams     ← python/app/cutting_parameters/cutting_store.py::RecommendedCuttingParams
- ChatterReport     ← python/app/chatter_prediction/pipeline.py::export_chatter_report JSON 结构

工程优先硬约束（项目记忆）：
- K_s（cutting_force_coeff）直接传递，不二次拟合
- HRC52 pending_calibration 时强制降低置信度
- cam_validation_required 始终为 True
- ChatterReport 仅供阶段 6 G 代码生成参考，不可直接用于机床
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


# =============================================================================
# 机床动态参数
# =============================================================================


@dataclass
class MachineParams:
    """机床动态参数。

    字段来源：python/app/simulation/chatter/stability.py::MachineParams
    用于 Tlusty 解析法计算稳定性极限切深。

    所有刚度单位：N/m
    """

    machine_id: str = "vmc_850"
    stiffness_x: float = 1.5e7   # X向刚度 (N/m)
    stiffness_y: float = 1.5e7   # Y向刚度 (N/m)
    stiffness_z: float = 2.0e8   # Z向刚度 (N/m)
    damping_ratio: float = 0.05  # 阻尼比
    natural_freq: float = 100.0  # 固有频率 (Hz)
    modal_mass: float = 50.0    # 模态质量 (kg)

    def __post_init__(self) -> None:
        if self.stiffness_x <= 0 or self.stiffness_y <= 0 or self.stiffness_z <= 0:
            raise ValueError("刚度必须为正数")
        if self.damping_ratio <= 0 or self.damping_ratio >= 1:
            raise ValueError(f"阻尼比必须在 (0, 1) 范围内，当前值: {self.damping_ratio}")
        if self.natural_freq <= 0:
            raise ValueError(f"固有频率必须为正数，当前值: {self.natural_freq}")
        if self.modal_mass <= 0:
            raise ValueError(f"模态质量必须为正数，当前值: {self.modal_mass}")

    def to_dict(self) -> dict[str, Any]:
        return {
            "machine_id": self.machine_id,
            "stiffness_x": self.stiffness_x,
            "stiffness_y": self.stiffness_y,
            "stiffness_z": self.stiffness_z,
            "damping_ratio": self.damping_ratio,
            "natural_freq": self.natural_freq,
            "modal_mass": self.modal_mass,
        }


# =============================================================================
# 刀具参数
# =============================================================================


@dataclass
class ToolParams:
    """刀具参数。

    字段来源：python/app/simulation/chatter/stability.py::ToolParams
    cutting_force_coeff 即 K_s，直接传递不二次拟合（项目记忆硬约束）。
    """

    tool_id: str = "endmill_d10"
    diameter: float = 10.0       # 刀具直径 (mm)
    num_flutes: int = 4          # 齿数
    helix_angle: float = 30.0    # 螺旋角 (度)
    cutting_force_coeff: float = 2000.0  # 切削力系数 K_s (N/mm²)

    def __post_init__(self) -> None:
        if self.diameter <= 0:
            raise ValueError(f"刀具直径必须为正数，当前值: {self.diameter}")
        if self.num_flutes <= 0:
            raise ValueError(f"齿数必须为正整数，当前值: {self.num_flutes}")
        if self.helix_angle < 0 or self.helix_angle > 90:
            raise ValueError(f"螺旋角必须在 [0, 90] 范围内，当前值: {self.helix_angle}")
        if self.cutting_force_coeff <= 0:
            raise ValueError(f"切削力系数必须为正数，当前值: {self.cutting_force_coeff}")

    def to_dict(self) -> dict[str, Any]:
        return {
            "tool_id": self.tool_id,
            "diameter": self.diameter,
            "num_flutes": self.num_flutes,
            "helix_angle": self.helix_angle,
            "cutting_force_coeff": self.cutting_force_coeff,
        }


# =============================================================================
# 颤振稳定性计算参数
# =============================================================================


@dataclass
class ChatterParams:
    """颤振稳定性计算参数。

    字段来源：python/app/simulation/chatter/stability.py::ChatterParams
    阶段 4 输出 → 阶段 5 输入的核心数据结构。

    axial_depth 为 None 时计算极限切深，非 None 时判断稳定性。
    """

    spindle_rpm: float = 8000.0  # 主轴转速 (rpm)
    machine: MachineParams = field(default_factory=MachineParams)
    tool: ToolParams = field(default_factory=ToolParams)
    axial_depth: Optional[float] = None  # 轴向切深 (mm)，None 时计算极限切深

    def __post_init__(self) -> None:
        if self.spindle_rpm <= 0:
            raise ValueError(f"主轴转速必须为正数，当前值: {self.spindle_rpm}")
        if self.axial_depth is not None and self.axial_depth <= 0:
            raise ValueError(f"轴向切深必须为正数，当前值: {self.axial_depth}")

    def to_dict(self) -> dict[str, Any]:
        return {
            "spindle_rpm": self.spindle_rpm,
            "machine": self.machine.to_dict(),
            "tool": self.tool.to_dict(),
            "axial_depth": self.axial_depth,
        }


# =============================================================================
# 材料切削参数基线
# =============================================================================


@dataclass
class MaterialParams:
    """材料切削参数基线。

    字段来源：python/app/cutting_parameters/material_resolver.py::MaterialParams
    specific_cutting_force 即 K_s，用于阶段 5 颤振预测（直接传递，不二次拟合）。

    所有切削参数范围均为 [min, max] 二元组，单位：
    - cutting_speed_range: m/min（米/分钟）
    - feed_range: mm/tooth（毫米/齿）
    - depth_of_cut_range: mm（毫米）
    - specific_cutting_force: N/mm²（即 K_s）
    """

    id: str
    name: str
    category: str
    hardness_hb: float
    tensile_strength_mpa: float
    thermal_conductivity: float  # W/(m·K)
    density_gcm3: float
    specific_cutting_force: float  # K_s (N/mm²)
    cutting_speed_range: dict[str, list[float]]  # {roughing: [min,max], finishing: [min,max]}
    feed_range: dict[str, list[float]]
    depth_of_cut_range: dict[str, list[float]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "category": self.category,
            "hardness_hb": self.hardness_hb,
            "tensile_strength_mpa": self.tensile_strength_mpa,
            "thermal_conductivity": self.thermal_conductivity,
            "density_gcm3": self.density_gcm3,
            "specific_cutting_force": self.specific_cutting_force,
            "cutting_speed_range": {k: list(v) for k, v in self.cutting_speed_range.items()},
            "feed_range": {k: list(v) for k, v in self.feed_range.items()},
            "depth_of_cut_range": {k: list(v) for k, v in self.depth_of_cut_range.items()},
        }


# =============================================================================
# 推荐切削参数（阶段 4 输出）
# =============================================================================


@dataclass
class CuttingParams:
    """单个特征的推荐切削参数。

    字段来源：python/app/cutting_parameters/cutting_store.py::RecommendedCuttingParams
    契约名简写为 CuttingParams，实现类名为 RecommendedCuttingParams。

    所有数值单位：
    - spindle_speed_rpm: RPM（主轴转速）
    - feed_rate_mm_per_min: mm/min（进给速度）
    - feed_per_tooth_mm: mm/tooth（每齿进给量）
    - cutting_speed_m_per_min: m/min（切削速度，线速度）
    - axial_depth_mm: mm（轴向切深，ap）
    - radial_depth_mm: mm（径向切深，ae，铣削专用）
    """

    feature_id: str
    feature_type: str  # plane / cylinder / hole / boss
    operation: str  # roughing / finishing
    spindle_speed_rpm: float
    feed_rate_mm_per_min: float
    feed_per_tooth_mm: float
    cutting_speed_m_per_min: float
    axial_depth_mm: float
    radial_depth_mm: float = 0.0
    estimated_cutting_time_s: float = 0.0
    tool_life_estimate_min: float = 0.0
    warnings: list[str] = field(default_factory=list)
    # 工程师审核
    review_status: str = "pending"  # pending / confirmed / rejected / edited
    edited_params: dict[str, float] = field(default_factory=dict)
    reviewed_by: str = ""
    reviewed_at: float = 0.0
    engineer_notes: str = ""
    # 来源追溯
    material_id: str = ""
    tool_diameter_mm: float = 0.0
    num_flutes: int = 0

    def effective_params(self) -> dict[str, float]:
        """获取生效参数（edited 时用 edited_params 覆盖，否则用推荐值）。

        与阶段 2/3/4 的 effective_params() 契约一致：
        - review_status == edited 且 edited_params 非空 → 用编辑值
        - 否则 → 用推荐值副本
        """
        base = {
            "spindle_speed_rpm": self.spindle_speed_rpm,
            "feed_rate_mm_per_min": self.feed_rate_mm_per_min,
            "feed_per_tooth_mm": self.feed_per_tooth_mm,
            "cutting_speed_m_per_min": self.cutting_speed_m_per_min,
            "axial_depth_mm": self.axial_depth_mm,
            "radial_depth_mm": self.radial_depth_mm,
        }
        if self.review_status == "edited" and self.edited_params:
            result = dict(base)
            result.update(self.edited_params)
            return result
        return base

    def to_dict(self) -> dict[str, Any]:
        return {
            "feature_id": self.feature_id,
            "feature_type": self.feature_type,
            "operation": self.operation,
            "spindle_speed_rpm": self.spindle_speed_rpm,
            "feed_rate_mm_per_min": self.feed_rate_mm_per_min,
            "feed_per_tooth_mm": self.feed_per_tooth_mm,
            "cutting_speed_m_per_min": self.cutting_speed_m_per_min,
            "axial_depth_mm": self.axial_depth_mm,
            "radial_depth_mm": self.radial_depth_mm,
            "estimated_cutting_time_s": self.estimated_cutting_time_s,
            "tool_life_estimate_min": self.tool_life_estimate_min,
            "warnings": list(self.warnings),
            "review_status": self.review_status,
            "edited_params": dict(self.edited_params),
            "reviewed_by": self.reviewed_by,
            "reviewed_at": self.reviewed_at,
            "engineer_notes": self.engineer_notes,
            "material_id": self.material_id,
            "tool_diameter_mm": self.tool_diameter_mm,
            "num_flutes": self.num_flutes,
        }


# =============================================================================
# ChatterReport（阶段 5 输出 → 阶段 6 输入）
# =============================================================================


@dataclass
class ChatterReport:
    """颤振预测报告 JSON 契约。

    字段来源：python/app/chatter_prediction/pipeline.py::export_chatter_report
    阶段 5 导出 → 阶段 6 G 代码生成加载。

    工程硬约束（项目记忆）：
    - cam_validation_required 始终为 True
    - ChatterReport 仅供阶段 6 G 代码生成参考，不可直接用于机床
    - 实际加工必须经 CAM 软件二次校验 + 工程师审核 + 持证操作员 + 导师签字
    - 极限切深为理论值，实际加工必须留 20% 安全裕度
    """

    task_id: str
    task_status: str  # 始终 "succeeded"（仅 reviewed 任务可导出）
    prediction_method: str  # analytical / neural_network / mixed / fallback
    source_cutting_parameters_task_id: str
    material_id: str
    precision_tier: str  # coarse / standard / high
    mesh_calibrated: bool
    machine_type: str
    cam_validation_required: bool = True  # 始终 True（项目记忆硬约束）
    ltc_model_available: bool = False
    exported_at: float = 0.0
    feature_count: int = 0
    method_statistics: dict[str, int] = field(
        default_factory=lambda: {"analytical": 0, "neural_network": 0, "fallback": 0}
    )
    feature_results: list[dict[str, Any]] = field(default_factory=list)
    industrial_hard_gates_note: str = (
        "本 ChatterReport 仅供阶段 6 G 代码生成参考，"
        "实际加工必须经 CAM 软件二次校验 + 工程师审核 + 持证操作员 + 导师签字。"
        "极限切深为理论值，实际加工必须留 20% 安全裕度。"
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "task_status": self.task_status,
            "prediction_method": self.prediction_method,
            "source_cutting_parameters_task_id": self.source_cutting_parameters_task_id,
            "material_id": self.material_id,
            "precision_tier": self.precision_tier,
            "mesh_calibrated": self.mesh_calibrated,
            "machine_type": self.machine_type,
            "cam_validation_required": self.cam_validation_required,
            "ltc_model_available": self.ltc_model_available,
            "exported_at": self.exported_at,
            "feature_count": self.feature_count,
            "method_statistics": dict(self.method_statistics),
            "feature_results": list(self.feature_results),
            "industrial_hard_gates_note": self.industrial_hard_gates_note,
        }
