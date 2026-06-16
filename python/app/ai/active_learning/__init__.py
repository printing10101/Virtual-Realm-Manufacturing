"""主动学习模块

提供主动学习触发器系统，用于识别需要人工干预的场景并生成标准化事件。

主要组件:
- events: 事件结构定义及生成逻辑
- triggers: 5类触发场景检测器实现

使用示例:
    >>> from app.ai.active_learning import ActiveLearningTrigger
    >>> trigger = ActiveLearningTrigger()
    >>> event = trigger.check_uncertainty(confidence=0.3, context={"material": "titanium"})
    >>> if event:
    ...     print(f"触发事件: {event['type']}")
"""

from app.ai.active_learning.events import (
    TriggerEvent,
    EventFactory,
    EventType,
)

from app.ai.active_learning.triggers import (
    # 配置类
    TriggerConfig,
    LowConfidenceConfig,
    KnowledgeGapConfig,
    ConflictingEvidenceConfig,
    NovelSituationConfig,
    CriticalDecisionConfig,
    # 触发器类
    BaseTrigger,
    LowConfidenceTrigger,
    KnowledgeGapTrigger,
    ConflictingEvidenceTrigger,
    NovelSituationTrigger,
    CriticalDecisionTrigger,
    # 管理器
    ActiveLearningTrigger,
)

__all__ = [
    # 事件相关
    "TriggerEvent",
    "EventFactory",
    "EventType",
    # 配置相关
    "TriggerConfig",
    "LowConfidenceConfig",
    "KnowledgeGapConfig",
    "ConflictingEvidenceConfig",
    "NovelSituationConfig",
    "CriticalDecisionConfig",
    # 触发器相关
    "BaseTrigger",
    "LowConfidenceTrigger",
    "KnowledgeGapTrigger",
    "ConflictingEvidenceTrigger",
    "NovelSituationTrigger",
    "CriticalDecisionTrigger",
    # 管理器
    "ActiveLearningTrigger",
]

__version__ = "1.0.0"
