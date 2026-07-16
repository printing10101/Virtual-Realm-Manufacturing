"""``shared.constants`` —— 工程硬约束常量子包。

子模块：
- ``materials`` ``DEFAULT_CONFIDENCE`` / ``PENDING_CALIBRATION_CONFIDENCE`` / ``FALLBACK_CONFIDENCE`` / ``PENDING_CALIBRATION_MATERIALS`` / K_s 表
- ``precision`` ``PrecisionTier`` enum / ``SAFETY_MARGIN_RATIO``
- ``gates``     ``INDUSTRIAL_HARD_GATES`` 8 条 / ``REQUIRES_ENGINEER_REVIEW`` / ``REQUIRES_CAM_VALIDATION``

设计动机：HRC52 ``pending_calibration`` 标注、安全裕度 0.8、CAM 校验强制 True 等
项目记忆硬约束必须固化在契约层，避免工程侧与科研侧各自维护一份常量导致行为漂移。
"""

from shared.constants.gates import (
    INDUSTRIAL_HARD_GATES,
    REQUIRES_CAM_VALIDATION,
    REQUIRES_ENGINEER_REVIEW,
)
from shared.constants.materials import (
    CUTTING_FORCE_COEFF_TABLE,
    DEFAULT_CONFIDENCE,
    FALLBACK_CONFIDENCE,
    PENDING_CALIBRATION_CONFIDENCE,
    PENDING_CALIBRATION_MATERIALS,
)
from shared.constants.precision import (
    PRECISION_TIER_HIGH,
    PRECISION_TIER_STANDARD,
    PRECISION_TIER_COARSE,
    PrecisionTier,
    SAFETY_MARGIN_RATIO,
)

__all__ = [
    # materials
    "DEFAULT_CONFIDENCE",
    "PENDING_CALIBRATION_CONFIDENCE",
    "FALLBACK_CONFIDENCE",
    "PENDING_CALIBRATION_MATERIALS",
    "CUTTING_FORCE_COEFF_TABLE",
    # precision
    "PrecisionTier",
    "PRECISION_TIER_COARSE",
    "PRECISION_TIER_STANDARD",
    "PRECISION_TIER_HIGH",
    "SAFETY_MARGIN_RATIO",
    # gates
    "INDUSTRIAL_HARD_GATES",
    "REQUIRES_ENGINEER_REVIEW",
    "REQUIRES_CAM_VALIDATION",
]
