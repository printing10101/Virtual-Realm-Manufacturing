"""切削力推理接口。

提供简洁的切削力预测 API，封装 PINN 模型推理逻辑。

用法:
    from app.simulation.cutting_force.predictor import predict_cutting_force

    result = predict_cutting_force(
        material='45steel',
        tool='endmill_d10',
        params={'speed': 3500, 'feed': 1200, 'depth': 1.5}
    )
    # result = {'Fx': ..., 'Fy': ..., 'Fz': ..., 'method': 'pinn'}
"""

from __future__ import annotations

import os
import time
import logging
from typing import Dict, Optional

import torch

from app.simulation.cutting_force.kienzle import (
    compute_cutting_forces,
    DEFAULT_MATERIAL_COEFFICIENTS,
)
from app.simulation.cutting_force.pinn import CuttingForcePINN

logger = logging.getLogger(__name__)

# 全局模型缓存
_model_cache: Dict[str, CuttingForcePINN] = {}
_model_dir = os.path.join(os.path.dirname(__file__), "checkpoints")


def _load_model(device: str = "cpu") -> CuttingForcePINN:
    """加载训练好的 PINN 模型。

    若检查点不存在，则创建默认模型（推理时使用 Kienzle 解析解回退）。
    """
    cache_key = device
    if cache_key in _model_cache:
        return _model_cache[cache_key]

    model = CuttingForcePINN()
    checkpoint_path = os.path.join(_model_dir, "best_model.pt")

    if os.path.exists(checkpoint_path):
        checkpoint = torch.load(checkpoint_path, map_location=device, weights_only=False)
        model.load_state_dict(checkpoint["model_state_dict"])
        logger.info(f"已加载模型检查点: {checkpoint_path}")
    else:
        logger.warning(
            f"未找到模型检查点: {checkpoint_path}。"
            "请先运行训练脚本，或使用 Kienzle 解析解。"
        )

    model.to(device)
    model.eval()
    _model_cache[cache_key] = model
    return model


def predict_cutting_force(
    material: str = "45steel",
    tool: str = "endmill_d10",
    params: Optional[Dict] = None,
    use_pinn: bool = True,
) -> Dict[str, float]:
    """预测切削力。

    Args:
        material: 材料名称 (如 '45steel', 'aluminum_6061')
        tool: 刀具标识 (当前仅用于接口兼容，不影响计算)
        params: 切削参数字典，包含:
            - speed: 主轴转速 (rpm)
            - feed: 进给量 (mm/min)
            - depth: 切深 (mm)
        use_pinn: 是否使用 PINN 模型。False 时仅使用 Kienzle 解析解。

    Returns:
        包含以下键的字典:
        - Fx: 进给力 (N)
        - Fy: 径向力 (N)
        - Fz: 主切削力 (N)
        - method: 预测方法 ('pinn' 或 'kienzle')
        - confidence: 置信度 (0.0-1.0)，PINN 模型为 0.85，Kienzle 为 0.60
        - model_version: 模型版本标识
    """
    if params is None:
        params = {"speed": 3500, "feed": 1200, "depth": 1.5}

    speed = params.get("speed", 3500)
    feed = params.get("feed", 1200)
    depth = params.get("depth", 1.5)

    # Kienzle 解析解计算
    # 映射: 切屑厚度 h = depth * 0.1, 切削宽度 b = depth
    chip_thickness = max(depth * 0.1, 0.001)
    width = max(depth, 0.01)

    kienzle_result = compute_cutting_forces(
        material=material,
        width=width,
        chip_thickness=chip_thickness,
    )

    if not use_pinn:
        return {
            "Fx": kienzle_result["Fx"],
            "Fy": kienzle_result["Fy"],
            "Fz": kienzle_result["Fz"],
            "method": "kienzle",
            "confidence": 0.60,  # 解析解置信度较低
            "model_version": "kienzle_v1.0",
        }

    # PINN 推理
    try:
        device = "cpu"
        model = _load_model(device)

        with torch.no_grad():
            x_norm = CuttingForcePINN.normalize_params(speed, feed, depth)
            pred = model(x_norm)
            forces = pred[0].numpy()

        # 若模型未经训练（输出接近零），回退到 Kienzle
        if forces.sum() < 1.0:
            logger.warning("PINN 输出异常，回退到 Kienzle 解析解")
            return {
                "Fx": kienzle_result["Fx"],
                "Fy": kienzle_result["Fy"],
                "Fz": kienzle_result["Fz"],
                "method": "kienzle_fallback",  # 明确标注为回退
                "confidence": 0.50,  # 回退模式置信度更低
                "model_version": "kienzle_v1.0_fallback",
                "warning": "PINN 模型未训练或输出异常，已回退到解析解",
            }

        return {
            "Fx": float(forces[0]),
            "Fy": float(forces[1]),
            "Fz": float(forces[2]),
            "method": "pinn",
            "confidence": 0.85,  # PINN 模型置信度较高
            "model_version": "pinn_v1.0",
        }
    except (RuntimeError, ValueError, TypeError) as e:
        logger.warning(f"PINN 推理失败 ({e})，回退到 Kienzle 解析解")
        return {
            "Fx": kienzle_result["Fx"],
            "Fy": kienzle_result["Fy"],
            "Fz": kienzle_result["Fz"],
            "method": "kienzle_fallback",
            "confidence": 0.50,
            "model_version": "kienzle_v1.0_fallback",
            "warning": f"PINN 推理失败: {str(e)}，已回退到解析解",
        }


def predict_cutting_force_batch(
    material: str,
    params_list: list,
    use_pinn: bool = True,
) -> list:
    """批量预测切削力。

    Args:
        material: 材料名称
        params_list: 切削参数列表，每个元素为参数字典
        use_pinn: 是否使用 PINN

    Returns:
        预测结果列表
    """
    return [
        predict_cutting_force(material=material, params=p, use_pinn=use_pinn)
        for p in params_list
    ]
