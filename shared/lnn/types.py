"""``shared.lnn.types`` —— 颤振预测核心类型契约。

本模块定义工程侧与科研侧共享的颤振预测类型：
- ``FeatureChatterResult``            单个特征的颤振预测结果
- ``PredictionMethod``                预测方法枚举（analytical / neural_network / fallback）
- ``ChatterReviewStatus``             工程师审核状态枚举
- ``ChatterPredictionTaskStatus``     任务状态机枚举

字段定义与现有 ``python/app/chatter_prediction/chatter_store.py`` 完全一致。
阶段 2 迁移后，``chatter_store.py`` 将 ``from shared.lnn.types import ...`` 替代本地定义，
工程侧与科研侧共享同一份类型契约，避免 schema 漂移。

D-2 学术诚信硬约束保护：
- 科研侧训练目标的输入/输出 schema 必须与 ``FeatureChatterResult`` 对齐
- 任何字段变更需走 ADR 评审，并在 ``main`` 分支打 tag 冻结
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


# =============================================================================
# 枚举：任务状态 / 审核状态 / 预测方法
# =============================================================================


class ChatterPredictionTaskStatus(str, Enum):
    """颤振预测任务状态机（单轮审核，与阶段 4 一致）。

    状态转移图::

        PENDING → RUNNING → PREDICTED → REVIEWED → SUCCEEDED
                             ↘ FAILED
                             ↘ CANCELLED

    - PENDING    : 任务已创建，等待触发执行
    - RUNNING    : 正在执行 ChatterParams 加载 + 双路径预测
    - PREDICTED  : 预测结果已生成，等待工程师审核
    - REVIEWED   : 工程师已审核全部特征预测结果
    - SUCCEEDED  : ChatterReport JSON 已导出，可供阶段 6 使用
    - FAILED     : 执行失败（ChatterParams 加载失败 / 预测异常 等）
    - CANCELLED  : 用户主动取消

    与阶段 4 区别：单轮审核（阶段 3 是两轮审核）。
    阶段 5 输出的是 JSON 报告（非 STEP），不会直接进入 CAM 软件，因此单轮审核足够。
    """

    PENDING = "pending"
    RUNNING = "running"
    PREDICTED = "predicted"
    REVIEWED = "reviewed"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ChatterReviewStatus(str, Enum):
    """工程师审核单个特征颤振预测结果的状态。

    - PENDING   : 待审核
    - CONFIRMED : 工程师确认预测结果（稳定性判断 + 极限切深）
    - REJECTED  : 工程师拒绝该特征（不进入最终 ChatterReport）
    - EDITED    : 工程师编辑了参数（如调整极限切深、强制改判稳定性）
    """

    PENDING = "pending"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"
    EDITED = "edited"


class PredictionMethod(str, Enum):
    """颤振预测方法。

    - ANALYTICAL     : Tlusty 解析法（compute_stability_limit，工程可用，默认路径）
    - NEURAL_NETWORK : LTC 神经网络（实验性，chatter_model.pt/.onnx 存在时启用）
    - FALLBACK       : 解析法与神经网络均失败时的兜底（返回保守默认值）
    """

    ANALYTICAL = "analytical"
    NEURAL_NETWORK = "neural_network"
    FALLBACK = "fallback"


# =============================================================================
# 单特征预测结果数据类
# =============================================================================


@dataclass
class FeatureChatterResult:
    """单个特征的颤振预测结果（工程侧与科研侧共享契约）。

    所有数值单位：
    - ``limit_depth_mm``    : mm（极限切削深度，Tlusty 公式计算）
    - ``axial_depth_mm``    : mm（实际轴向切深，来自阶段 4 ChatterParams）
    - ``stability_margin``  : 无量纲（实际切深 / 极限切深，<1 稳定，>1 不稳定）
    - ``confidence``        : [0, 1]（置信度，HRC52 pending_calibration 时强制降低）
    - ``cutting_force_coeff``: N/mm²（K_s，来自阶段 4，不二次拟合）

    字段与 ``chatter_store.py`` 中定义保持一致，阶段 2 迁移后由本模块单一来源。
    """

    # 识别字段
    feature_id: str
    feature_type: str  # plane / cylinder / hole / boss
    material_id: str
    # 工况字段
    spindle_rpm: float
    axial_depth_mm: float  # 实际切深（来自阶段 4）
    # 预测结果
    limit_depth_mm: float  # 极限切深（预测结果）
    stable: bool  # 稳定性判断
    stability_margin: float  # axial_depth / limit_depth
    # 方法标记
    method: str  # analytical / neural_network / fallback
    ltc_active: bool  # LTC 是否真正参与预测
    # 置信度
    confidence: float = 0.8  # 默认置信度
    inference_time_ms: float = 0.0
    warnings: list[str] = field(default_factory=list)
    # HRC52 标定状态注入
    material_calibration_status: str = "calibrated"  # calibrated / pending_calibration
    # 工程师审核
    review_status: str = ChatterReviewStatus.PENDING.value
    edited_params: dict[str, float] = field(default_factory=dict)
    reviewed_by: str = ""
    reviewed_at: float = 0.0
    engineer_notes: str = ""
    # 来源追溯
    source_cutting_params_task_id: str = ""
    machine_id: str = ""
    tool_id: str = ""
    cutting_force_coeff: float = 0.0  # K_s (N/mm²)

    def effective_result(self) -> dict[str, float]:
        """获取生效结果（edited 时用 ``edited_params`` 覆盖，否则用预测值）。

        与阶段 2/3/4 的 ``effective_*()`` 契约一致：
        - ``review_status == edited`` 且 ``edited_params`` 非空 → 用编辑值
        - 否则 → 用预测值副本

        可编辑字段：``limit_depth_mm`` / ``axial_depth_mm`` / ``stable``
        （``stable`` 用 0/1 表示，与 ``chatter_store.py:164`` 实现一致，
        便于 JSON 序列化与阶段 6 数值比较）。

        Returns:
            dict 包含三个键：``limit_depth_mm`` / ``axial_depth_mm`` / ``stable``。
            ``stable`` 始终为 ``float`` 类型（1.0 或 0.0）。
        """
        base: dict[str, float] = {
            "limit_depth_mm": self.limit_depth_mm,
            "axial_depth_mm": self.axial_depth_mm,
            "stable": 1.0 if self.stable else 0.0,
        }
        if self.review_status == ChatterReviewStatus.EDITED.value and self.edited_params:
            result = dict(base)
            result.update(self.edited_params)
            return result
        return base

    def to_dict(self) -> dict[str, Any]:
        """序列化为 dict（用于 JSON 导出 / API 响应）。

        与 ``chatter_store.py`` 中 ``to_dict`` 字段集合完全一致，
        阶段 2 迁移后由本方法替代工程侧实现。
        """
        return {
            "feature_id": self.feature_id,
            "feature_type": self.feature_type,
            "material_id": self.material_id,
            "spindle_rpm": self.spindle_rpm,
            "axial_depth_mm": self.axial_depth_mm,
            "limit_depth_mm": self.limit_depth_mm,
            "stable": self.stable,
            "stability_margin": self.stability_margin,
            "method": self.method,
            "ltc_active": self.ltc_active,
            "confidence": self.confidence,
            "inference_time_ms": self.inference_time_ms,
            "warnings": list(self.warnings),
            "material_calibration_status": self.material_calibration_status,
            "review_status": self.review_status,
            "edited_params": dict(self.edited_params),
            "reviewed_by": self.reviewed_by,
            "reviewed_at": self.reviewed_at,
            "engineer_notes": self.engineer_notes,
            "source_cutting_params_task_id": self.source_cutting_params_task_id,
            "machine_id": self.machine_id,
            "tool_id": self.tool_id,
            "cutting_force_coeff": self.cutting_force_coeff,
        }


__all__ = [
    "ChatterPredictionTaskStatus",
    "ChatterReviewStatus",
    "PredictionMethod",
    "FeatureChatterResult",
]
