"""主动学习触发器单元测试

测试5类触发场景检测器的功能和事件生成逻辑。
"""

import pytest
from app.ai.active_learning import (
    ActiveLearningTrigger,
    LowConfidenceTrigger,
    KnowledgeGapTrigger,
    ConflictingEvidenceTrigger,
    NovelSituationTrigger,
    CriticalDecisionTrigger,
    LowConfidenceConfig,
    KnowledgeGapConfig,
    ConflictingEvidenceConfig,
    NovelSituationConfig,
    CriticalDecisionConfig,
    EventType,
)


class TestLowConfidenceTrigger:
    """低置信度触发器测试"""
    
    def test_trigger_on_low_confidence(self):
        """测试低置信度时触发"""
        trigger = LowConfidenceTrigger()
        event = trigger.check(
            confidence=0.3,
            context={"material": "titanium"},
            model_name="test_model"
        )
        
        assert event is not None
        assert event.type == EventType.LOW_CONFIDENCE.value
        assert event.context["confidence"] == 0.3
        assert "titanium" in str(event.context)
    
    def test_no_trigger_on_high_confidence(self):
        """测试高置信度时不触发"""
        trigger = LowConfidenceTrigger()
        event = trigger.check(
            confidence=0.8,
            context={"material": "steel"}
        )
        
        assert event is None
    
    def test_custom_threshold(self):
        """测试自定义阈值"""
        config = LowConfidenceConfig(confidence_threshold=0.7)
        trigger = LowConfidenceTrigger(config)
        
        # 0.6应该触发（低于0.7）
        event = trigger.check(confidence=0.6, context={})
        assert event is not None
        
        # 0.8不应该触发（高于0.7）
        event = trigger.check(confidence=0.8, context={})
        assert event is None
    
    def test_invalid_confidence(self):
        """测试无效置信度值"""
        trigger = LowConfidenceTrigger()
        
        # 负数
        event = trigger.check(confidence=-0.1, context={})
        assert event is None
        
        # 大于1
        event = trigger.check(confidence=1.5, context={})
        assert event is None
    
    def test_disabled_trigger(self):
        """测试禁用的触发器"""
        config = LowConfidenceConfig(enabled=False)
        trigger = LowConfidenceTrigger(config)
        
        event = trigger.check(confidence=0.1, context={})
        assert event is None


class TestKnowledgeGapTrigger:
    """知识缺失触发器测试"""
    
    def test_trigger_on_missing_knowledge(self):
        """测试知识缺失时触发"""
        trigger = KnowledgeGapTrigger()
        event = trigger.check(
            available_knowledge={"material": "steel"},  # 缺少process_type和tolerance
            context={"task": "process_planning"}
        )
        
        assert event is not None
        assert event.type == EventType.KNOWLEDGE_GAP.value
        assert "process_type" in event.context["missing_knowledge"]
    
    def test_no_trigger_on_complete_knowledge(self):
        """测试知识完整时不触发"""
        trigger = KnowledgeGapTrigger()
        event = trigger.check(
            available_knowledge={
                "material": "steel",
                "process_type": "milling",
                "tolerance": "0.01mm"
            },
            context={}
        )
        
        assert event is None
    
    def test_custom_required_fields(self):
        """测试自定义必需字段"""
        config = KnowledgeGapConfig(
            required_knowledge_fields=["machine", "tool"]
        )
        trigger = KnowledgeGapTrigger(config)
        
        # 缺少machine和tool
        event = trigger.check(
            available_knowledge={"material": "steel"},
            context={}
        )
        assert event is not None
        assert "machine" in event.context["missing_knowledge"]
    
    def test_disabled_trigger(self):
        """测试禁用的触发器"""
        config = KnowledgeGapConfig(enabled=False)
        trigger = KnowledgeGapTrigger(config)
        
        event = trigger.check(
            available_knowledge={},
            context={}
        )
        assert event is None


class TestConflictingEvidenceTrigger:
    """证据冲突触发器测试"""
    
    def test_trigger_on_conflicting_evidence(self):
        """测试证据冲突时触发"""
        trigger = ConflictingEvidenceTrigger()
        event = trigger.check(
            evidence_list=[
                {"source": "model_a", "conclusion": "use_milling", "confidence": 0.8},
                {"source": "model_b", "conclusion": "use_turning", "confidence": 0.7}
            ],
            context={"task": "process_selection"}
        )
        
        assert event is not None
        assert event.type == EventType.CONFLICTING_EVIDENCE.value
        assert len(event.context["evidence_list"]) == 2
    
    def test_no_trigger_on_consistent_evidence(self):
        """测试证据一致时不触发"""
        trigger = ConflictingEvidenceTrigger()
        event = trigger.check(
            evidence_list=[
                {"source": "model_a", "conclusion": "use_milling", "confidence": 0.8},
                {"source": "model_b", "conclusion": "use_milling", "confidence": 0.7}
            ],
            context={}
        )
        
        assert event is None
    
    def test_no_trigger_on_insufficient_evidence(self):
        """测试证据数量不足时不触发"""
        trigger = ConflictingEvidenceTrigger()
        event = trigger.check(
            evidence_list=[
                {"source": "model_a", "conclusion": "use_milling", "confidence": 0.8}
            ],
            context={}
        )
        
        assert event is None
    
    def test_disabled_trigger(self):
        """测试禁用的触发器"""
        config = ConflictingEvidenceConfig(enabled=False)
        trigger = ConflictingEvidenceTrigger(config)
        
        event = trigger.check(
            evidence_list=[
                {"source": "a", "conclusion": "x"},
                {"source": "b", "conclusion": "y"}
            ],
            context={}
        )
        assert event is None


class TestNovelSituationTrigger:
    """新颖情境触发器测试"""
    
    def test_trigger_on_novel_situation(self):
        """测试新颖情境时触发"""
        trigger = NovelSituationTrigger()
        event = trigger.check(
            situation_features={
                "material": "inconel",
                "hardness": 70,
                "geometry": "complex"
            },
            similarity_score=0.25,
            context={"task": "machining"}
        )
        
        assert event is not None
        assert event.type == EventType.NOVEL_SITUATION.value
        assert event.context["similarity_score"] == 0.25
    
    def test_no_trigger_on_familiar_situation(self):
        """测试熟悉情境时不触发"""
        trigger = NovelSituationTrigger()
        event = trigger.check(
            situation_features={
                "material": "steel",
                "hardness": 40,
                "geometry": "simple"
            },
            similarity_score=0.8,
            context={}
        )
        
        assert event is None
    
    def test_custom_similarity_threshold(self):
        """测试自定义相似度阈值"""
        config = NovelSituationConfig(similarity_threshold=0.6)
        trigger = NovelSituationTrigger(config)
        
        # 0.5应该触发（低于0.6）
        event = trigger.check(
            situation_features={"a": 1, "b": 2, "c": 3},
            similarity_score=0.5,
            context={}
        )
        assert event is not None
        
        # 0.7不应该触发（高于0.6）
        event = trigger.check(
            situation_features={"a": 1, "b": 2, "c": 3},
            similarity_score=0.7,
            context={}
        )
        assert event is None
    
    def test_invalid_similarity_score(self):
        """测试无效相似度值"""
        trigger = NovelSituationTrigger()
        
        # 负数
        event = trigger.check(
            situation_features={"a": 1, "b": 2, "c": 3},
            similarity_score=-0.1,
            context={}
        )
        assert event is None
        
        # 大于1
        event = trigger.check(
            situation_features={"a": 1, "b": 2, "c": 3},
            similarity_score=1.5,
            context={}
        )
        assert event is None
    
    def test_disabled_trigger(self):
        """测试禁用的触发器"""
        config = NovelSituationConfig(enabled=False)
        trigger = NovelSituationTrigger(config)
        
        event = trigger.check(
            situation_features={"a": 1, "b": 2, "c": 3},
            similarity_score=0.1,
            context={}
        )
        assert event is None


class TestCriticalDecisionTrigger:
    """关键决策触发器测试"""
    
    def test_trigger_on_high_risk(self):
        """测试高风险时触发"""
        trigger = CriticalDecisionTrigger()
        event = trigger.check(
            decision_description="选择热处理工艺参数",
            context={"part": "turbine_blade"},
            risk_score=0.85
        )
        
        assert event is not None
        assert event.type == EventType.CRITICAL_DECISION.value
        assert event.context["risk_score"] == 0.85
    
    def test_trigger_on_high_cost(self):
        """测试高成本时触发"""
        trigger = CriticalDecisionTrigger()
        event = trigger.check(
            decision_description="采购新设备",
            context={},
            estimated_cost=50000
        )
        
        assert event is not None
        assert "高成本" in event.context["impact_assessment"]
    
    def test_trigger_on_safety_related(self):
        """测试安全相关时触发"""
        trigger = CriticalDecisionTrigger()
        event = trigger.check(
            decision_description="选择安全关键参数",
            context={},
            is_safety_related=True
        )
        
        assert event is not None
        assert "安全" in event.context["impact_assessment"]
    
    def test_trigger_on_keywords(self):
        """测试关键词触发"""
        trigger = CriticalDecisionTrigger()
        event = trigger.check(
            decision_description="这是一个critical决策",
            context={}
        )
        
        assert event is not None
        assert "critical" in event.context["impact_assessment"].lower()
    
    def test_no_trigger_on_low_risk(self):
        """测试低风险时不触发"""
        trigger = CriticalDecisionTrigger()
        event = trigger.check(
            decision_description="普通决策",
            context={},
            risk_score=0.3,
            estimated_cost=100
        )
        
        assert event is None
    
    def test_disabled_trigger(self):
        """测试禁用的触发器"""
        config = CriticalDecisionConfig(enabled=False)
        trigger = CriticalDecisionTrigger(config)
        
        event = trigger.check(
            decision_description="测试",
            context={},
            risk_score=0.9
        )
        assert event is None


class TestActiveLearningTrigger:
    """主动学习触发器管理器测试"""
    
    def test_check_uncertainty(self):
        """测试便捷方法：检查不确定性"""
        trigger = ActiveLearningTrigger()
        event = trigger.check_uncertainty(
            confidence=0.3,
            context={"material": "titanium"}
        )
        
        assert event is not None
        assert isinstance(event, dict)
        assert all(key in event for key in ["type", "reason", "context", "suggested_action"])
        assert event["type"] == EventType.LOW_CONFIDENCE.value
    
    def test_check_knowledge_gap(self):
        """测试便捷方法：检查知识缺失"""
        trigger = ActiveLearningTrigger()
        event = trigger.check_knowledge_gap(
            available_knowledge={"material": "steel"},
            context={}
        )
        
        assert event is not None
        assert event["type"] == EventType.KNOWLEDGE_GAP.value
    
    def test_check_conflicting_evidence(self):
        """测试便捷方法：检查证据冲突"""
        trigger = ActiveLearningTrigger()
        event = trigger.check_conflicting_evidence(
            evidence_list=[
                {"source": "a", "conclusion": "x"},
                {"source": "b", "conclusion": "y"}
            ],
            context={}
        )
        
        assert event is not None
        assert event["type"] == EventType.CONFLICTING_EVIDENCE.value
    
    def test_check_novel_situation(self):
        """测试便捷方法：检查新颖情境"""
        trigger = ActiveLearningTrigger()
        event = trigger.check_novel_situation(
            situation_features={"a": 1, "b": 2, "c": 3},
            similarity_score=0.2,
            context={}
        )
        
        assert event is not None
        assert event["type"] == EventType.NOVEL_SITUATION.value
    
    def test_check_critical_decision(self):
        """测试便捷方法：检查关键决策"""
        trigger = ActiveLearningTrigger()
        event = trigger.check_critical_decision(
            decision_description="关键决策",
            context={},
            risk_score=0.9
        )
        
        assert event is not None
        assert event["type"] == EventType.CRITICAL_DECISION.value
    
    def test_get_all_events(self):
        """测试获取所有事件"""
        trigger = ActiveLearningTrigger()
        
        # 触发多个事件
        trigger.check_uncertainty(confidence=0.3, context={})
        trigger.check_knowledge_gap(available_knowledge={}, context={})
        
        events = trigger.get_all_events()
        assert len(events) >= 2
    
    def test_clear_all_history(self):
        """测试清空历史"""
        trigger = ActiveLearningTrigger()
        
        # 触发事件
        trigger.check_uncertainty(confidence=0.3, context={})
        
        # 清空历史
        trigger.clear_all_history()
        
        events = trigger.get_all_events()
        assert len(events) == 0
    
    def test_get_status(self):
        """测试获取状态"""
        trigger = ActiveLearningTrigger()
        status = trigger.get_status()
        
        assert isinstance(status, dict)
        assert "LowConfidenceTrigger" in status
        assert "enabled" in status["LowConfidenceTrigger"]
    
    def test_custom_config(self):
        """测试自定义配置"""
        config = {
            "low_confidence": {
                "confidence_threshold": 0.7,
                "enabled": True
            }
        }
        trigger = ActiveLearningTrigger(config)
        
        # 0.6应该触发（低于0.7）
        event = trigger.check_uncertainty(confidence=0.6, context={})
        assert event is not None


class TestEventStructure:
    """事件结构测试"""
    
    def test_event_has_required_fields(self):
        """测试事件包含必需字段"""
        trigger = ActiveLearningTrigger()
        event = trigger.check_uncertainty(confidence=0.3, context={})
        
        assert event is not None
        assert "type" in event
        assert "reason" in event
        assert "context" in event
        assert "suggested_action" in event
    
    def test_event_has_metadata(self):
        """测试事件包含元数据"""
        trigger = ActiveLearningTrigger()
        event = trigger.check_uncertainty(confidence=0.3, context={})
        
        assert "event_id" in event
        assert "timestamp" in event
        assert "priority" in event


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
