"""切削力 PINN 仿真模块。

提供基于物理约束神经网络 (PINN) 的切削力预测能力，
结合 Kienzle 解析公式与残差学习网络。

子模块:
    - kienzle: Kienzle 切削力解析计算
    - pinn: PINN 模型架构与损失函数
    - trainer: 模型训练逻辑
    - predictor: 推理接口
"""

from __future__ import annotations

from app.simulation.cutting_force.kienzle import (
    KienzleParams,
    compute_cutting_force_fz,
    compute_cutting_forces,
    compute_specific_cutting_force,
    get_kienzle_coefficients,
    DEFAULT_MATERIAL_COEFFICIENTS,
)
from app.simulation.cutting_force.pinn import (
    CuttingForcePINN,
    PINNLoss,
    ResidualBlock,
)
from app.simulation.cutting_force.predictor import (
    predict_cutting_force,
    predict_cutting_force_batch,
)

__all__ = [
    "KienzleParams",
    "compute_cutting_force_fz",
    "compute_cutting_forces",
    "compute_specific_cutting_force",
    "get_kienzle_coefficients",
    "DEFAULT_MATERIAL_COEFFICIENTS",
    "CuttingForcePINN",
    "PINNLoss",
    "ResidualBlock",
    "predict_cutting_force",
    "predict_cutting_force_batch",
]
