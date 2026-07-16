"""工业硬门槛与强制审核常量（项目记忆硬约束）。

8 条工业硬门槛（与 ADR-007 / ADR-008 / ADR-009 / ADR-013 / ADR-018 一致并补充 LTC 实验性条款）：
所有 chatter_prediction / gcode_generation / cam_validation API 响应必须携带此列表，
强制前端展示给工程师。

强制审核常量：
- ``REQUIRES_ENGINEER_REVIEW``  始终 True，颤振预测结果必须经工程师审核
- ``REQUIRES_CAM_VALIDATION``    始终 True，G 代码必须经 CAM 软件二次校验后才允许上机床
"""

from __future__ import annotations


# =============================================================================
# 8 条工业硬门槛
# =============================================================================
#
# 顺序有意义：从「预测方法」到「良品率」到「公差」到「操作员资质」到「CAM 校验」
# 到「系统定位」到「LTC 实验性」最后到「保险与导师签字」。
INDUSTRIAL_HARD_GATES: list[str] = [
    "颤振预测基于 Tlusty 解析法 + LTC 神经网络（实验性），稳定性判断必须经工程师审核",
    "良品率要求 0 缺陷容忍，极限切深为理论值，实际加工必须留 20% 安全裕度",
    "工业级配合面公差 0.01mm，颤振预测无法直接达到，需精加工工序",
    "CNC 机床操作需持证操作员，本系统输出的预测结果仅供工艺参考",
    "实际加工需导师签字 + 保险，大一独立项目不可独立完成机床执行环节",
    "CAM 二次校验强制：生成的切削参数必须经 NX/PowerMill/PyCAM 校验后才允许上机床",
    "系统定位「工程师助手」，非「全自动颤振预测器」，最终决策权在工程师",
    "LTC 神经网络路径为实验性，chatter_model.pt 不存在时自动回退到 Tlusty 解析法",
]


# =============================================================================
# 强制审核常量
# =============================================================================
#
# 这两个常量始终为 True，不可通过环境变量关闭（项目记忆硬约束）：
# - REQUIRES_ENGINEER_REVIEW: 颤振预测结果必须经工程师单轮审核（confirmed/rejected/edited）
# - REQUIRES_CAM_VALIDATION:   G 代码必须经 CAM 软件二次校验后才允许上机床
REQUIRES_ENGINEER_REVIEW: bool = True
REQUIRES_CAM_VALIDATION: bool = True


__all__ = [
    "INDUSTRIAL_HARD_GATES",
    "REQUIRES_ENGINEER_REVIEW",
    "REQUIRES_CAM_VALIDATION",
]
