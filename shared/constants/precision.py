"""精度档位与安全裕度常量（项目记忆硬约束）。

精度档位继承链：
    阶段 1 image_to_3d.precision_tier
      → 阶段 2 几何特征提取
        → 阶段 3 参数化几何（STEP）
          → 阶段 4 切削参数推荐（ChatterParams）
            → 阶段 5 颤振预测（ChatterReport，本模块）
              → 阶段 6 G 代码生成

各阶段不引入新档位，全程继承上游告知（与 ADR-007 / ADR-008 / ADR-009 / ADR-013 一致）。

精度档位影响置信度标注：
- ``coarse``   粗加工，大切深 + 低精度，稳定性裕度大
- ``standard`` 标准档位，平衡切深与精度，默认档位
- ``high``     精加工，小切深 + 高精度，配合面加工（0.01mm 公差）
"""

from __future__ import annotations

from enum import Enum


class PrecisionTier(str, Enum):
    """精度档位枚举（与 ADR-007 / ADR-008 / ADR-009 / ADR-013 完全一致）。

    继承 ``str, Enum`` 便于 JSON 序列化与跨阶段字符串比较。
    """

    COARSE = "coarse"
    STANDARD = "standard"
    HIGH = "high"


# 便捷常量（避免散落的字符串字面量）
PRECISION_TIER_COARSE = PrecisionTier.COARSE.value
PRECISION_TIER_STANDARD = PrecisionTier.STANDARD.value
PRECISION_TIER_HIGH = PrecisionTier.HIGH.value


# 安全裕度建议（极限切深的 80%）
#
# 项目记忆硬约束：极限切深为理论值，实际加工必须留 20% 安全裕度。
# 当实际切深超过极限切深 80% 时，predictor_adapter 会发出 warning。
SAFETY_MARGIN_RATIO: float = 0.8


__all__ = [
    "PrecisionTier",
    "PRECISION_TIER_COARSE",
    "PRECISION_TIER_STANDARD",
    "PRECISION_TIER_HIGH",
    "SAFETY_MARGIN_RATIO",
]
