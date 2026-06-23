"""主动学习触发器模块

实现5类独立的触发场景检测器，用于识别需要人工干预的场景并生成标准化事件。

触发器类型:
1. 低置信度触发器 (LowConfidenceTrigger)
2. 知识缺失触发器 (KnowledgeGapTrigger)
3. 证据冲突触发器 (ConflictingEvidenceTrigger)
4. 新颖情境触发器 (NovelSituationTrigger)
5. 关键决策触发器 (CriticalDecisionTrigger)
"""

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field

from app.ai.active_learning.events import (
    TriggerEvent,
    EventFactory,
    EventType
)

logger = logging.getLogger(__name__)


@dataclass
class TriggerConfig:
    """触发器配置基类"""
    enabled: bool = True
    priority: int = 3
    
    def to_dict(self) -> Dict[str, Any]:
        return {"enabled": self.enabled, "priority": self.priority}
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TriggerConfig":
        return cls(
            enabled=data.get("enabled", True),
            priority=data.get("priority", 3)
        )


class BaseTrigger(ABC):
    """触发器基类，定义统一接口"""
    
    def __init__(self, config: Optional[TriggerConfig] = None):
        self.config = config or TriggerConfig()
        self._event_history: List[TriggerEvent] = []
    
    @property
    def event_type(self) -> str:
        """返回此触发器产生的事件类型"""
        raise NotImplementedError("子类必须实现 event_type 属性，返回触发器产生的事件类型标识符")
    
    @abstractmethod
    def check(self, **kwargs) -> Optional[TriggerEvent]:
        """检查是否满足触发条件
        
        Returns:
            如果满足触发条件，返回TriggerEvent；否则返回None
        """
        pass
    
    @property
    def event_history(self) -> List[TriggerEvent]:
        """获取历史触发事件列表"""
        return self._event_history.copy()
    
    def clear_history(self) -> None:
        """清空历史事件"""
        self._event_history.clear()
    
    def _record_event(self, event: TriggerEvent) -> TriggerEvent:
        """记录事件到历史并返回"""
        self._event_history.append(event)
        logger.info(f"触发器 {self.__class__.__name__} 触发事件: {event.type}")
        return event


# =============================================================================
# 1. 低置信度触发器
# =============================================================================

@dataclass
class LowConfidenceConfig(TriggerConfig):
    """低置信度触发器配置"""
    confidence_threshold: float = 0.5  # 置信度阈值
    min_samples_for_confidence: int = 10  # 计算置信度所需的最小样本数
    
    def to_dict(self) -> Dict[str, Any]:
        base = super().to_dict()
        base.update({
            "confidence_threshold": self.confidence_threshold,
            "min_samples_for_confidence": self.min_samples_for_confidence
        })
        return base
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LowConfidenceConfig":
        return cls(
            enabled=data.get("enabled", True),
            priority=data.get("priority", 3),
            confidence_threshold=data.get("confidence_threshold", 0.5),
            min_samples_for_confidence=data.get("min_samples_for_confidence", 10)
        )


class LowConfidenceTrigger(BaseTrigger):
    """低置信度触发器
    
    当模型预测的置信度低于设定阈值时触发，请求工艺师确认预测结果。
    
    触发条件:
        - confidence < confidence_threshold
        - sample_count >= min_samples_for_confidence (确保置信度计算有效)
    
    Example:
        >>> config = LowConfidenceConfig(confidence_threshold=0.6)
        >>> trigger = LowConfidenceTrigger(config)
        >>> event = trigger.check(confidence=0.4, context={"material": "titanium"})
    """
    
    def __init__(self, config: Optional[LowConfidenceConfig] = None):
        super().__init__(config)
        self.config: LowConfidenceConfig = config or LowConfidenceConfig()
    
    @property
    def event_type(self) -> str:
        return EventType.LOW_CONFIDENCE.value
    
    def check(
        self,
        confidence: float,
        context: Dict[str, Any],
        model_name: str = "unknown",
        sample_count: int = 100
    ) -> Optional[TriggerEvent]:
        """检查置信度是否低于阈值
        
        Args:
            confidence: 当前预测的置信度 (0-1)
            context: 预测上下文信息
            model_name: 产生预测的模型名称
            sample_count: 用于计算置信度的样本数
            
        Returns:
            如果置信度低于阈值，返回触发事件；否则返回None
        """
        if not self.config.enabled:
            return None
        
        # 验证输入
        if not 0 <= confidence <= 1:
            logger.warning(f"无效的置信度值: {confidence}")
            return None
        
        # 检查样本数是否足够
        if sample_count < self.config.min_samples_for_confidence:
            logger.debug(f"样本数不足: {sample_count} < {self.config.min_samples_for_confidence}")
            return None
        
        # 检查是否低于阈值
        if confidence < self.config.confidence_threshold:
            event = EventFactory.create_low_confidence_event(
                confidence=confidence,
                threshold=self.config.confidence_threshold,
                context=context,
                model_name=model_name
            )
            event.priority = self.config.priority
            return self._record_event(event)
        
        return None


# =============================================================================
# 2. 知识缺失触发器
# =============================================================================

@dataclass
class KnowledgeGapConfig(TriggerConfig):
    """知识缺失触发器配置"""
    required_knowledge_fields: List[str] = field(
        default_factory=lambda: ["material", "process_type", "tolerance"]
    )
    knowledge_completeness_threshold: float = 0.8  # 知识完整度阈值
    
    def to_dict(self) -> Dict[str, Any]:
        base = super().to_dict()
        base.update({
            "required_knowledge_fields": self.required_knowledge_fields,
            "knowledge_completeness_threshold": self.knowledge_completeness_threshold
        })
        return base
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "KnowledgeGapConfig":
        return cls(
            enabled=data.get("enabled", True),
            priority=data.get("priority", 3),
            required_knowledge_fields=data.get(
                "required_knowledge_fields", 
                ["material", "process_type", "tolerance"]
            ),
            knowledge_completeness_threshold=data.get(
                "knowledge_completeness_threshold", 
                0.8
            )
        )


class KnowledgeGapTrigger(BaseTrigger):
    """知识缺失触发器
    
    当任务所需的关键知识在知识图谱中缺失时触发，请求工艺师补充知识。
    
    触发条件:
        - 知识图谱中缺少required_knowledge_fields中的关键字段
        - 或者知识完整度低于阈值
    
    Example:
        >>> config = KnowledgeGapConfig(required_knowledge_fields=["material", "machine"])
        >>> trigger = KnowledgeGapTrigger(config)
        >>> event = trigger.check(
        ...     available_knowledge={"material": "steel"},
        ...     context={"task": "process_planning"}
        ... )
    """
    
    def __init__(self, config: Optional[KnowledgeGapConfig] = None):
        super().__init__(config)
        self.config: KnowledgeGapConfig = config or KnowledgeGapConfig()
    
    @property
    def event_type(self) -> str:
        return EventType.KNOWLEDGE_GAP.value
    
    def check(
        self,
        available_knowledge: Dict[str, Any],
        context: Dict[str, Any],
        task_description: str = ""
    ) -> Optional[TriggerEvent]:
        """检查是否存在知识缺失
        
        Args:
            available_knowledge: 当前可用的知识数据
            context: 任务上下文
            task_description: 任务描述
            
        Returns:
            如果检测到知识缺失，返回触发事件；否则返回None
        """
        if not self.config.enabled:
            return None
        
        # 检查缺失的关键字段
        missing_fields = []
        for field_name in self.config.required_knowledge_fields:
            if field_name not in available_knowledge or not available_knowledge[field_name]:
                missing_fields.append(field_name)
        
        # 计算知识完整度
        total_fields = len(self.config.required_knowledge_fields)
        if total_fields > 0:
            completeness = (total_fields - len(missing_fields)) / total_fields
        else:
            completeness = 1.0
        
        # 检查是否低于阈值
        if completeness < self.config.knowledge_completeness_threshold or missing_fields:
            event = EventFactory.create_knowledge_gap_event(
                missing_knowledge=missing_fields,
                context={
                    **context,
                    "available_knowledge": available_knowledge,
                    "completeness": completeness
                },
                task_description=task_description
            )
            event.priority = self.config.priority
            return self._record_event(event)
        
        return None


# =============================================================================
# 3. 证据冲突触发器
# =============================================================================

@dataclass
class ConflictingEvidenceConfig(TriggerConfig):
    """证据冲突触发器配置"""
    conflict_threshold: float = 0.3  # 冲突程度阈值 (0-1)
    min_evidence_count: int = 2  # 产生冲突所需的最小证据源数量
    
    def to_dict(self) -> Dict[str, Any]:
        base = super().to_dict()
        base.update({
            "conflict_threshold": self.conflict_threshold,
            "min_evidence_count": self.min_evidence_count
        })
        return base
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ConflictingEvidenceConfig":
        return cls(
            enabled=data.get("enabled", True),
            priority=data.get("priority", 3),
            conflict_threshold=data.get("conflict_threshold", 0.3),
            min_evidence_count=data.get("min_evidence_count", 2)
        )


class ConflictingEvidenceTrigger(BaseTrigger):
    """证据冲突触发器
    
    当来自不同来源的证据相互矛盾时触发，请求工艺师评估并做出判断。
    
    触发条件:
        - 多个证据源给出的结论不一致
        - 冲突程度超过阈值
    
    Example:
        >>> trigger = ConflictingEvidenceTrigger()
        >>> event = trigger.check(
        ...     evidence_list=[
        ...         {"source": "model_a", "conclusion": "use_milling", "confidence": 0.8},
        ...         {"source": "model_b", "conclusion": "use_turning", "confidence": 0.7}
        ...     ],
        ...     context={"task": "process_selection"}
        ... )
    """
    
    def __init__(self, config: Optional[ConflictingEvidenceConfig] = None):
        super().__init__(config)
        self.config: ConflictingEvidenceConfig = config or ConflictingEvidenceConfig()
    
    @property
    def event_type(self) -> str:
        return EventType.CONFLICTING_EVIDENCE.value
    
    def check(
        self,
        evidence_list: List[Dict[str, Any]],
        context: Dict[str, Any]
    ) -> Optional[TriggerEvent]:
        """检查是否存在证据冲突
        
        Args:
            evidence_list: 证据列表，每个证据包含source, conclusion, confidence等字段
            context: 上下文信息
            
        Returns:
            如果检测到证据冲突，返回触发事件；否则返回None
        """
        if not self.config.enabled:
            return None
        
        # 检查证据数量
        if len(evidence_list) < self.config.min_evidence_count:
            return None
        
        # 提取结论
        conclusions = [e.get("conclusion") for e in evidence_list if e.get("conclusion")]
        
        if len(conclusions) < 2:
            return None
        
        # 检查是否有不同的结论
        unique_conclusions = set(conclusions)
        if len(unique_conclusions) <= 1:
            return None
        
        # 计算冲突程度 (基于不同结论的比例)
        conflict_degree = (len(unique_conclusions) - 1) / len(unique_conclusions)
        
        # 检查是否超过阈值
        if conflict_degree >= self.config.conflict_threshold:
            sources = [e.get("source", "unknown") for e in evidence_list]
            conflict_desc = f"来自{', '.join(sources)}的证据给出不同结论: {', '.join(unique_conclusions)}"
            
            event = EventFactory.create_conflicting_evidence_event(
                evidence_sources=sources,
                conflict_description=conflict_desc,
                context={
                    **context,
                    "evidence_list": evidence_list,
                    "conflict_degree": conflict_degree
                }
            )
            event.priority = self.config.priority
            return self._record_event(event)
        
        return None


# =============================================================================
# 4. 新颖情境触发器
# =============================================================================

@dataclass
class NovelSituationConfig(TriggerConfig):
    """新颖情境触发器配置"""
    similarity_threshold: float = 0.4  # 相似度阈值 (低于此值视为新颖)
    min_feature_count: int = 3  # 用于相似度计算的最小特征数
    
    def to_dict(self) -> Dict[str, Any]:
        base = super().to_dict()
        base.update({
            "similarity_threshold": self.similarity_threshold,
            "min_feature_count": self.min_feature_count
        })
        return base
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "NovelSituationConfig":
        return cls(
            enabled=data.get("enabled", True),
            priority=data.get("priority", 3),
            similarity_threshold=data.get("similarity_threshold", 0.4),
            min_feature_count=data.get("min_feature_count", 3)
        )


class NovelSituationTrigger(BaseTrigger):
    """新颖情境触发器
    
    当检测到与历史案例差异很大的新情境时触发，请求工艺师提供指导。
    
    触发条件:
        - 当前情境与最近似的历史案例相似度低于阈值
        - 特征数量足够进行有效比较
    
    Example:
        >>> trigger = NovelSituationTrigger()
        >>> event = trigger.check(
        ...     situation_features={"material": "inconel", "hardness": 70, "geometry": "complex"},
        ...     similarity_score=0.25,
        ...     context={"task": "machining"}
        ... )
    """
    
    def __init__(self, config: Optional[NovelSituationConfig] = None):
        super().__init__(config)
        self.config: NovelSituationConfig = config or NovelSituationConfig()
    
    @property
    def event_type(self) -> str:
        return EventType.NOVEL_SITUATION.value
    
    def check(
        self,
        situation_features: Dict[str, Any],
        similarity_score: float,
        context: Dict[str, Any]
    ) -> Optional[TriggerEvent]:
        """检查是否为新颖情境
        
        Args:
            situation_features: 当前情境的特征描述
            similarity_score: 与最近似历史案例的相似度 (0-1)
            context: 上下文信息
            
        Returns:
            如果判定为新颖情境，返回触发事件；否则返回None
        """
        if not self.config.enabled:
            return None
        
        # 验证特征数量
        if len(situation_features) < self.config.min_feature_count:
            logger.debug(f"特征数量不足: {len(situation_features)} < {self.config.min_feature_count}")
            return None
        
        # 验证相似度范围
        if not 0 <= similarity_score <= 1:
            logger.warning(f"无效的相似度值: {similarity_score}")
            return None
        
        # 检查是否低于相似度阈值
        if similarity_score < self.config.similarity_threshold:
            event = EventFactory.create_novel_situation_event(
                situation_features=situation_features,
                similarity_score=similarity_score,
                context=context
            )
            event.priority = self.config.priority
            return self._record_event(event)
        
        return None


# =============================================================================
# 5. 关键决策触发器
# =============================================================================

@dataclass
class CriticalDecisionConfig(TriggerConfig):
    """关键决策触发器配置"""
    risk_threshold: float = 0.7  # 风险阈值
    cost_threshold: float = 10000.0  # 成本阈值 (元)
    safety_critical_keywords: List[str] = field(
        default_factory=lambda: ["安全", "safety", "critical", "关键", "危险"]
    )
    
    def to_dict(self) -> Dict[str, Any]:
        base = super().to_dict()
        base.update({
            "risk_threshold": self.risk_threshold,
            "cost_threshold": self.cost_threshold,
            "safety_critical_keywords": self.safety_critical_keywords
        })
        return base
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CriticalDecisionConfig":
        return cls(
            enabled=data.get("enabled", True),
            priority=data.get("priority", 3),
            risk_threshold=data.get("risk_threshold", 0.7),
            cost_threshold=data.get("cost_threshold", 10000.0),
            safety_critical_keywords=data.get(
                "safety_critical_keywords",
                ["安全", "safety", "critical", "关键", "危险"]
            )
        )


class CriticalDecisionTrigger(BaseTrigger):
    """关键决策触发器
    
    当面临高风险、高成本或安全关键的决策时触发，请求工艺师确认。
    
    触发条件 (满足任一):
        - 决策风险评分超过阈值
        - 决策涉及成本超过阈值
        - 决策描述包含安全关键关键词
    
    Example:
        >>> trigger = CriticalDecisionTrigger()
        >>> event = trigger.check(
        ...     decision_description="选择热处理工艺参数",
        ...     risk_score=0.85,
        ...     estimated_cost=50000,
        ...     context={"part": "turbine_blade"}
        ... )
    """
    
    def __init__(self, config: Optional[CriticalDecisionConfig] = None):
        super().__init__(config)
        self.config: CriticalDecisionConfig = config or CriticalDecisionConfig()
    
    @property
    def event_type(self) -> str:
        return EventType.CRITICAL_DECISION.value
    
    def check(
        self,
        decision_description: str,
        context: Dict[str, Any],
        risk_score: float = 0.0,
        estimated_cost: float = 0.0,
        is_safety_related: bool = False
    ) -> Optional[TriggerEvent]:
        """检查是否需要关键决策确认
        
        Args:
            decision_description: 决策描述
            context: 上下文信息
            risk_score: 风险评分 (0-1)
            estimated_cost: 预估成本
            is_safety_related: 是否涉及安全
            
        Returns:
            如果需要关键决策确认，返回触发事件；否则返回None
        """
        if not self.config.enabled:
            return None
        
        trigger_reasons = []
        
        # 检查风险评分
        if risk_score >= self.config.risk_threshold:
            trigger_reasons.append(f"高风险评分({risk_score:.2%})")
        
        # 检查成本
        if estimated_cost >= self.config.cost_threshold:
            trigger_reasons.append(f"高成本(¥{estimated_cost:,.0f})")
        
        # 检查安全相关
        if is_safety_related:
            trigger_reasons.append("涉及安全关键因素")
        
        # 检查关键词
        decision_lower = decision_description.lower()
        for keyword in self.config.safety_critical_keywords:
            if keyword.lower() in decision_lower:
                trigger_reasons.append(f"包含关键术语'{keyword}'")
                break
        
        # 如果有任何触发原因，生成事件
        if trigger_reasons:
            impact = "; ".join(trigger_reasons)
            event = EventFactory.create_critical_decision_event(
                decision_description=decision_description,
                impact_assessment=impact,
                context={
                    **context,
                    "risk_score": risk_score,
                    "estimated_cost": estimated_cost,
                    "is_safety_related": is_safety_related,
                    "trigger_reasons": trigger_reasons
                }
            )
            event.priority = self.config.priority
            return self._record_event(event)
        
        return None


# =============================================================================
# 统一触发器管理器
# =============================================================================

class ActiveLearningTrigger:
    """主动学习触发器统一管理类
    
    整合所有触发器，提供统一的检查和事件分发接口。
    
    Example:
        >>> trigger = ActiveLearningTrigger()
        >>> event = trigger.check_uncertainty(confidence=0.3, context={"material": "titanium"})
        >>> if event:
        ...     print(f"触发事件: {event['type']}")
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """初始化触发器管理器
        
        Args:
            config: 可选的配置字典，用于配置各触发器
        """
        config = config or {}
        
        # 初始化各触发器
        self.low_confidence_trigger = LowConfidenceTrigger(
            LowConfidenceConfig.from_dict(config.get("low_confidence", {}))
        )
        self.knowledge_gap_trigger = KnowledgeGapTrigger(
            KnowledgeGapConfig.from_dict(config.get("knowledge_gap", {}))
        )
        self.conflicting_evidence_trigger = ConflictingEvidenceTrigger(
            ConflictingEvidenceConfig.from_dict(config.get("conflicting_evidence", {}))
        )
        self.novel_situation_trigger = NovelSituationTrigger(
            NovelSituationConfig.from_dict(config.get("novel_situation", {}))
        )
        self.critical_decision_trigger = CriticalDecisionTrigger(
            CriticalDecisionConfig.from_dict(config.get("critical_decision", {}))
        )
        
        self._triggers = [
            self.low_confidence_trigger,
            self.knowledge_gap_trigger,
            self.conflicting_evidence_trigger,
            self.novel_situation_trigger,
            self.critical_decision_trigger
        ]
    
    def check_uncertainty(
        self,
        confidence: float,
        context: Dict[str, Any],
        model_name: str = "unknown"
    ) -> Optional[Dict[str, Any]]:
        """检查低置信度场景 (便捷方法)
        
        Args:
            confidence: 预测置信度
            context: 上下文信息
            model_name: 模型名称
            
        Returns:
            触发事件字典，或None
        """
        event = self.low_confidence_trigger.check(
            confidence=confidence,
            context=context,
            model_name=model_name
        )
        return event.to_dict() if event else None
    
    def check_knowledge_gap(
        self,
        available_knowledge: Dict[str, Any],
        context: Dict[str, Any],
        task_description: str = ""
    ) -> Optional[Dict[str, Any]]:
        """检查知识缺失场景 (便捷方法)"""
        event = self.knowledge_gap_trigger.check(
            available_knowledge=available_knowledge,
            context=context,
            task_description=task_description
        )
        return event.to_dict() if event else None
    
    def check_conflicting_evidence(
        self,
        evidence_list: List[Dict[str, Any]],
        context: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """检查证据冲突场景 (便捷方法)"""
        event = self.conflicting_evidence_trigger.check(
            evidence_list=evidence_list,
            context=context
        )
        return event.to_dict() if event else None
    
    def check_novel_situation(
        self,
        situation_features: Dict[str, Any],
        similarity_score: float,
        context: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """检查新颖情境场景 (便捷方法)"""
        event = self.novel_situation_trigger.check(
            situation_features=situation_features,
            similarity_score=similarity_score,
            context=context
        )
        return event.to_dict() if event else None
    
    def check_critical_decision(
        self,
        decision_description: str,
        context: Dict[str, Any],
        risk_score: float = 0.0,
        estimated_cost: float = 0.0,
        is_safety_related: bool = False
    ) -> Optional[Dict[str, Any]]:
        """检查关键决策场景 (便捷方法)"""
        event = self.critical_decision_trigger.check(
            decision_description=decision_description,
            context=context,
            risk_score=risk_score,
            estimated_cost=estimated_cost,
            is_safety_related=is_safety_related
        )
        return event.to_dict() if event else None
    
    def get_all_events(self) -> List[Dict[str, Any]]:
        """获取所有触发器的历史事件"""
        events = []
        for trigger in self._triggers:
            events.extend([e.to_dict() for e in trigger.event_history])
        return sorted(events, key=lambda e: e.get("timestamp", 0))
    
    def clear_all_history(self) -> None:
        """清空所有触发器的历史事件"""
        for trigger in self._triggers:
            trigger.clear_history()
    
    def get_status(self) -> Dict[str, Any]:
        """获取所有触发器的状态"""
        return {
            trigger.__class__.__name__: {
                "enabled": trigger.config.enabled,
                "event_count": len(trigger.event_history),
                "config": trigger.config.to_dict()
            }
            for trigger in self._triggers
        }
