"""材料置信度与切削力系数 K_s 表（项目记忆硬约束）。

硬约束（与 ADR-013 一致）：
- HRC52 淬火钢 K_s = 2800 N/mm² 为工程估算值，必须标注 ``pending_calibration``
- HRC52 不可使用纯文献数据，必须通过自采工业数据校准后才允许进入正式 ChatterReport
- 6061-T6 / TC4 等 K_s 已校准，可使用默认置信度
- K_s 直接从阶段 4 ChatterParams 传递到阶段 5，不二次拟合（避免引入额外误差）

置信度三档：
- ``DEFAULT_CONFIDENCE``             = 0.8  已校准材料的默认置信度
- ``PENDING_CALIBRATION_CONFIDENCE`` = 0.5  HRC52 等待校准材料的强制置信度
- ``FALLBACK_CONFIDENCE``            = 0.3  解析法 + LTC 均失败时的兜底置信度
"""

from __future__ import annotations


# =============================================================================
# 置信度三档
# =============================================================================


# 默认置信度（已校准材料）
DEFAULT_CONFIDENCE: float = 0.8

# pending_calibration 时强制置信度（HRC52 等）
PENDING_CALIBRATION_CONFIDENCE: float = 0.5

# 兜底路径置信度（解析法 + LTC 均失败时）
FALLBACK_CONFIDENCE: float = 0.3


# =============================================================================
# HRC52 待校准材料 ID 集合
# =============================================================================


# 命中此集合的 material_id 触发：
#   1. material_calibration_status = "pending_calibration"
#   2. confidence 强制降低到 PENDING_CALIBRATION_CONFIDENCE (0.5)
#   3. warning_message 拼接「HRC52 材料待校准」片段
#
# 与 predictor_adapter.py 中定义保持一致，阶段2迁移后由 shared/ 单一来源。
PENDING_CALIBRATION_MATERIALS: frozenset[str] = frozenset({
    "steel_hrc52",
    "hrc52",
    "hrc_52",
    "hardened_steel_hrc52",
})


# =============================================================================
# 切削力系数 K_s 表（N/mm²）
# =============================================================================
#
# 工程估算值，仅作为参考。实际使用时 K_s 直接取自阶段 4 ChatterParams 的
# ``tool.cutting_force_coeff`` 字段，不从此表查询（项目记忆硬约束：K_s 不二次拟合）。
#
# 本表的存在意义：
#   1. 提供「合理范围」校验，避免 ChatterParams 中 K_s 离谱时被静默接受
#   2. 文档化常见材料的典型 K_s 范围，供工程师审核时参考
#   3. 标注哪些材料已校准 / 待校准
CUTTING_FORCE_COEFF_TABLE: dict[str, dict[str, object]] = {
    "aluminum_6061_t6": {
        "ks_n_mm2": 800.0,
        "calibrated": True,
        "source": "已校准，工程可用",
    },
    "titanium_tc4": {
        "ks_n_mm2": 1600.0,
        "calibrated": True,
        "source": "已校准，工程可用",
    },
    "steel_45": {
        "ks_n_mm2": 2000.0,
        "calibrated": True,
        "source": "已校准，工程可用",
    },
    "steel_hrc52": {
        "ks_n_mm2": 2800.0,
        "calibrated": False,
        "source": "工程估算值，pending_calibration，不可使用纯文献数据",
    },
}


__all__ = [
    "DEFAULT_CONFIDENCE",
    "PENDING_CALIBRATION_CONFIDENCE",
    "FALLBACK_CONFIDENCE",
    "PENDING_CALIBRATION_MATERIALS",
    "CUTTING_FORCE_COEFF_TABLE",
]
