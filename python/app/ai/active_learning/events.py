"""主动学习事件定义模块

定义主动学习系统中使用的标准化事件结构，用于触发器与工艺师之间的通信。
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List
from enum import Enum
import time
import uuid


class EventType(str, Enum):
    """事件类型枚举"""
    LOW_CONFIDENCE = "low_confidence"
    KNOWLEDGE_GAP = "knowledge_gap"
    CONFLICTING_EVIDENCE = "conflicting_evidence"
    NOVEL_SITUATION = "novel_situation"
    CRITICAL_DECISION = "critical_decision"


@dataclass
class TriggerEvent:
    """触发事件标准结构
    
    Attributes:
        type: 事件类型，标识触发场景
        reason: 触发原因的自然语言描述
        context: 触发时的上下文信息，包含相关数据和状态
        suggested_action: 建议的后续操作
        event_id: 事件唯一标识符
        timestamp: 事件生成时间戳
        priority: 事件优先级 (1-5, 1为最高)
        metadata: 额外的元数据信息
    """
    type: str
    reason: str
    context: Dict[str, Any]
    suggested_action: str
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: float = field(default_factory=time.time)
    priority: int = 3
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "type": self.type,
            "reason": self.reason,
            "context": self.context,
            "suggested_action": self.suggested_action,
            "event_id": self.event_id,
            "timestamp": self.timestamp,
            "priority": self.priority,
            "metadata": self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TriggerEvent":
        """从字典创建事件"""
        return cls(
            type=data["type"],
            reason=data["reason"],
            context=data["context"],
            suggested_action=data["suggested_action"],
            event_id=data.get("event_id", str(uuid.uuid4())),
            timestamp=data.get("timestamp", time.time()),
            priority=data.get("priority", 3),
            metadata=data.get("metadata", {})
        )
    
    def validate(self) -> bool:
        """验证事件格式是否完整"""
        required_fields = ["type", "reason", "context", "suggested_action"]
        return all(hasattr(self, f) and getattr(self, f) for f in required_fields)


class EventFactory:
    """事件工厂类，用于生成标准化的触发事件"""
    
    @staticmethod
    def create_low_confidence_event(
        confidence: float,
        threshold: float,
        context: Dict[str, Any],
        model_name: str = "unknown"
    ) -> TriggerEvent:
        """创建低置信度事件"""
        return TriggerEvent(
            type=EventType.LOW_CONFIDENCE.value,
            reason=f"模型预测置信度({confidence:.2%})低于阈值({threshold:.2%})",
            context={
                **context,
                "confidence": confidence,
                "threshold": threshold,
                "model_name": model_name
            },
            suggested_action="请工艺师确认预测结果的准确性，并提供专家判断",
            priority=2 if confidence < 0.3 else 3
        )
    
    @staticmethod
    def create_knowledge_gap_event(
        missing_knowledge: List[str],
        context: Dict[str, Any],
        task_description: str = ""
    ) -> TriggerEvent:
        """创建知识缺失事件"""
        return TriggerEvent(
            type=EventType.KNOWLEDGE_GAP.value,
            reason=f"知识图谱中缺少关键信息: {', '.join(missing_knowledge)}",
            context={
                **context,
                "missing_knowledge": missing_knowledge,
                "task_description": task_description
            },
            suggested_action="请工艺师补充缺失的工艺知识，或提供替代方案",
            priority=2
        )
    
    @staticmethod
    def create_conflicting_evidence_event(
        evidence_sources: List[str],
        conflict_description: str,
        context: Dict[str, Any]
    ) -> TriggerEvent:
        """创建证据冲突事件"""
        return TriggerEvent(
            type=EventType.CONFLICTING_EVIDENCE.value,
            reason=f"检测到相互矛盾的信息: {conflict_description}",
            context={
                **context,
                "evidence_sources": evidence_sources,
                "conflict_description": conflict_description
            },
            suggested_action="请工艺师评估冲突证据的可靠性，并做出最终判断",
            priority=2
        )
    
    @staticmethod
    def create_novel_situation_event(
        situation_features: Dict[str, Any],
        similarity_score: float,
        context: Dict[str, Any]
    ) -> TriggerEvent:
        """创建新颖情境事件"""
        return TriggerEvent(
            type=EventType.NOVEL_SITUATION.value,
            reason=f"检测到与历史案例相似度极低的新情境(相似度: {similarity_score:.2%})",
            context={
                **context,
                "situation_features": situation_features,
                "similarity_score": similarity_score
            },
            suggested_action="请工艺师评估此新情境，提供处理建议和经验指导",
            priority=3
        )
    
    @staticmethod
    def create_critical_decision_event(
        decision_description: str,
        impact_assessment: str,
        context: Dict[str, Any]
    ) -> TriggerEvent:
        """创建关键决策事件"""
        return TriggerEvent(
            type=EventType.CRITICAL_DECISION.value,
            reason=f"需要人工确认的关键决策: {decision_description}",
            context={
                **context,
                "decision_description": decision_description,
                "impact_assessment": impact_assessment
            },
            suggested_action="请工艺师审核并确认此关键决策",
            priority=1
        )
