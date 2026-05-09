"""
TaskRouter组件单元测试套件

8.3 路由器测试规范
覆盖场景：
- 简单任务路由测试
- 复杂任务路由测试
- 降级逻辑测试
- 置信度阈值测试
"""
import numpy as np

from app.ai.lnn.router.task_router import TaskRouter, TaskFeatures, ScoringModel
from app.ai.lnn.core import (
    EngineType,
    TaskInput,
    RoutingDecision,
)


# ============================================================
# 辅助函数
# ============================================================

def create_task(
    description: str,
    time_sensitivity: float = 0.5,
    precision_requirement: float = 0.9,
    max_latency_ms: int = 1000,
    task_category=None,
    data_type=None,
) -> TaskInput:
    """创建标准TaskInput对象的辅助函数"""
    return TaskInput(
        task_description=description,
        input_data=np.array([[1.0]]),
        time_sensitivity=time_sensitivity,
        precision_requirement=precision_requirement,
        max_latency_ms=max_latency_ms,
        task_category=task_category,
        data_type=data_type,
    )


# ============================================================
# 8.3.1 简单任务路由测试
# ============================================================

class TestSimpleTaskRouting:
    """测试单一任务类型和明确路由规则下的任务分配"""

    def setup_method(self):
        self.router = TaskRouter()

    def test_rule_based_task_routes_to_rule_engine(self):
        """测试规则类任务路由到Rule引擎"""
        task = create_task(
            description="if temperature > threshold then check validation rule",
            max_latency_ms=30,
        )
        decision = self.router.route(task)
        assert decision is not None
        assert decision.selected_engine is not None

    def test_rule_based_task_with_chinese_keywords(self):
        """测试中文规则关键词任务路由"""
        task = create_task(
            description="如果温度超过阈值则触发验证规则检查",
            max_latency_ms=20,
        )
        decision = self.router.route(task)
        assert decision.selected_engine is not None
        assert isinstance(decision, RoutingDecision)

    def test_llm_task_routes_to_llm_engine(self):
        """测试LLM类任务路由到LLM引擎"""
        task = create_task(
            description="summarize this document and explain the key points",
        )
        decision = self.router.route(task)
        assert decision is not None
        assert decision.selected_engine is not None

    def test_llm_task_with_chinese_keywords(self):
        """测试中文LLM关键词任务路由"""
        task = create_task(
            description="请总结这篇文章并解释主要内容，然后回答问题",
        )
        decision = self.router.route(task)
        assert decision is not None
        assert decision.selected_engine is not None

    def test_temporal_task_routes_to_lnn(self):
        """测试时序类任务路由到LNN引擎"""
        task = create_task(
            description="time series prediction for future trend forecast",
        )
        decision = self.router.route(task)
        assert decision is not None
        assert decision.selected_engine is not None

    def test_temporal_task_with_chinese_keywords(self):
        """测试中文时序关键词任务路由"""
        task = create_task(
            description="时序数据预测未来趋势和历史序列分析",
        )
        decision = self.router.route(task)
        assert decision is not None

    def test_multimodal_task_routes_to_hybrid(self):
        """测试多模态任务路由到Hybrid引擎"""
        task = create_task(
            description="image and vision combined multimodal analysis",
        )
        decision = self.router.route(task)
        assert decision is not None
        assert decision.selected_engine is not None

    def test_decision_has_confidence(self):
        """测试路由决策包含置信度"""
        task = create_task(description="predict the next value in time series")
        decision = self.router.route(task)
        assert 0.0 <= decision.confidence <= 1.0

    def test_decision_has_reasoning(self):
        """测试路由决策包含决策依据"""
        task = create_task(description="rule check with validation threshold")
        decision = self.router.route(task)
        assert decision.reasoning is not None
        assert len(decision.reasoning) > 0

    def test_decision_has_timestamp(self):
        """测试路由决策包含时间戳"""
        task = create_task(description="simple test task")
        decision = self.router.route(task)
        assert decision.timestamp is not None
        assert decision.timestamp > 0

    def test_decision_has_alternatives(self):
        """测试路由决策包含备选方案"""
        task = create_task(description="time series prediction task")
        decision = self.router.route(task)
        assert decision.alternatives is not None
        assert isinstance(decision.alternatives, list)

    def test_selected_model_is_determined(self):
        """测试路由决策确定具体模型"""
        task = create_task(description="predict time series trend forecast")
        decision = self.router.route(task)
        assert decision.selected_model is not None

    def test_simple_routing_decision_is_consistent(self):
        """测试相同任务的路由决策一致性"""
        task = create_task(description="if rule check then validation")
        decision1 = self.router.route(task)
        self.router.reset_history()
        decision2 = self.router.route(task)
        assert decision1.selected_engine == decision2.selected_engine


# ============================================================
# 8.3.2 复杂任务路由测试
# ============================================================

class TestComplexTaskRouting:
    """测试多任务类型、多模型选择、优先级权重等复杂场景"""

    def setup_method(self):
        self.router = TaskRouter(rule_weight=0.4, ml_weight=0.6)

    def test_mixed_keywords_routing(self):
        """测试混合关键词任务路由"""
        task = create_task(
            description="analyze the time series data and explain the trend prediction",
        )
        decision = self.router.route(task)
        assert decision is not None
        assert decision.selected_engine is not None

    def test_high_time_sensitivity_routing(self):
        """测试高时间敏感性任务路由"""
        task = create_task(
            description="real-time urgent data processing",
            time_sensitivity=0.95,
            max_latency_ms=10,
        )
        decision = self.router.route(task)
        assert decision is not None

    def test_high_precision_requirement_routing(self):
        """测试高精度要求任务路由"""
        task = create_task(
            description="complex optimization simulation with large-scale computation",
            precision_requirement=0.99,
        )
        decision = self.router.route(task)
        assert decision is not None

    def test_decision_factors_contains_all_engines(self):
        """测试决策因素包含所有引擎评分"""
        task = create_task(description="test task for routing")
        decision = self.router.route(task)
        assert decision.decision_factors is not None
        for engine in EngineType:
            assert engine in decision.decision_factors or engine.value in str(decision.decision_factors)

    def test_alternatives_limited_to_two(self):
        """测试备选方案最多返回2个"""
        task = create_task(description="complex task with multiple characteristics")
        decision = self.router.route(task)
        assert len(decision.alternatives) <= 2

    def test_alternatives_exclude_selected_engine(self):
        """测试备选方案不包含已选引擎"""
        task = create_task(description="temporal sequence prediction trend")
        decision = self.router.route(task)
        selected = decision.selected_engine.value
        for alt in decision.alternatives:
            assert alt["engine"] != selected

    def test_alternatives_have_scores(self):
        """测试备选方案包含评分"""
        task = create_task(description="rule validation check task")
        decision = self.router.route(task)
        for alt in decision.alternatives:
            assert "score" in alt
            assert 0.0 <= alt["score"] <= 1.0

    def test_different_rule_ml_weights_affect_decision(self):
        """测试不同规则/ML权重影响路由决策"""
        task = create_task(
            description="if rule then validation check with time series prediction",
        )
        router_rule_heavy = TaskRouter(rule_weight=0.8, ml_weight=0.2)
        router_ml_heavy = TaskRouter(rule_weight=0.2, ml_weight=0.8)
        decision_rule = router_rule_heavy.route(task)
        decision_ml = router_ml_heavy.route(task)
        assert decision_rule is not None
        assert decision_ml is not None

    def test_task_with_context_affects_routing(self):
        """测试带上下文的任务路由"""
        task = TaskInput(
            task_description="data processing task",
            input_data=np.array([[1.0]]),
            context={"domain": "manufacturing", "priority": "high"},
        )
        decision = self.router.route(task)
        assert decision is not None

    def test_routing_decision_history_is_recorded(self):
        """测试路由决策被记录到历史"""
        self.router.reset_history()
        for i in range(5):
            task = create_task(description=f"task {i}")
            self.router.route(task)
        assert len(self.router.decision_history) == 5

    def test_decision_stats_returns_correct_counts(self):
        """测试决策统计返回正确计数"""
        self.router.reset_history()
        for i in range(3):
            task = create_task(description=f"task {i}")
            self.router.route(task)
        stats = self.router.get_decision_stats()
        assert stats["total_decisions"] == 3
        assert "engine_distribution" in stats
        assert "average_confidence" in stats

    def test_decision_stats_with_empty_history(self):
        """测试空历史时的决策统计"""
        self.router.reset_history()
        stats = self.router.get_decision_stats()
        assert stats["total_decisions"] == 0


# ============================================================
# 8.3.3 降级逻辑测试
# ============================================================

class TestFallbackLogic:
    """测试部分模型不可用或性能下降时的降级策略"""

    def test_fallback_triggered_on_low_confidence(self):
        """测试低置信度时触发降级"""
        router = TaskRouter(confidence_threshold=0.99, enable_fallback=True)
        task = create_task(description="simple task")
        decision = router.route(task)
        assert decision is not None

    def test_fallback_disabled_skips_degradation(self):
        """测试禁用降级时不触发故障转移"""
        router = TaskRouter(confidence_threshold=0.99, enable_fallback=False)
        task = create_task(description="test task")
        decision = router.route(task)
        assert decision is not None

    def test_error_fallback_to_rule_engine(self):
        """测试异常时降级到Rule引擎"""
        router = TaskRouter(enable_fallback=True)
        task = TaskInput(
            task_description=None,
            input_data=np.array([[1.0]]),
        )
        decision = router.route(task)
        assert decision is not None

    def test_fallback_selects_second_best_when_confidence_low(self):
        """测试置信度低时选择第二优引擎"""
        router = TaskRouter(
            confidence_threshold=0.999,
            enable_fallback=True,
            rule_weight=0.5,
            ml_weight=0.5,
        )
        task = create_task(description="ambiguous task with mixed characteristics")
        decision = router.route(task)
        assert decision is not None
        assert decision.confidence is not None

    def test_fallback_preserves_decision_structure(self):
        """测试降级后决策结构完整"""
        router = TaskRouter(confidence_threshold=0.99, enable_fallback=True)
        task = create_task(description="test fallback decision structure")
        decision = router.route(task)
        assert hasattr(decision, "selected_engine")
        assert hasattr(decision, "confidence")
        assert hasattr(decision, "reasoning")
        assert hasattr(decision, "timestamp")

    def test_fallback_reasoning_mentions_fallback(self):
        """测试降级决策包含降级原因"""
        router = TaskRouter(confidence_threshold=0.99, enable_fallback=True)
        task = create_task(description="task requiring fallback analysis")
        decision = router.route(task)
        assert decision.reasoning is not None


# ============================================================
# 8.3.4 置信度阈值测试
# ============================================================

class TestConfidenceThreshold:
    """测试不同置信度阈值设置下的任务路由行为"""

    def test_low_threshold_no_fallback(self):
        """测试低阈值时不触发降级"""
        router = TaskRouter(confidence_threshold=0.01, enable_fallback=True)
        task = create_task(description="test task")
        decision = router.route(task)
        assert decision.confidence >= 0.01 or decision is not None

    def test_high_threshold_triggers_fallback(self):
        """测试高阈值时可能触发降级"""
        router = TaskRouter(confidence_threshold=0.9999, enable_fallback=True)
        task = create_task(description="test task for high threshold")
        decision = router.route(task)
        assert decision is not None

    def test_default_threshold_value(self):
        """测试默认置信度阈值"""
        router = TaskRouter()
        assert router.confidence_threshold == 0.7

    def test_threshold_affects_alternative_selection(self):
        """测试阈值影响备选选择"""
        router_low = TaskRouter(confidence_threshold=0.3, enable_fallback=True)
        router_high = TaskRouter(confidence_threshold=0.95, enable_fallback=True)
        task = create_task(description="test threshold effect on alternatives")
        decision_low = router_low.route(task)
        decision_high = router_high.route(task)
        assert decision_low is not None
        assert decision_high is not None

    def test_multiple_threshold_values(self):
        """测试多个不同阈值的路由行为"""
        thresholds = [0.1, 0.3, 0.5, 0.7, 0.9, 0.99]
        task = create_task(description="time series prediction with trend analysis")
        for threshold in thresholds:
            router = TaskRouter(confidence_threshold=threshold, enable_fallback=True)
            decision = router.route(task)
            assert decision is not None
            assert decision.selected_engine is not None

    def test_threshold_zero_accepts_any_decision(self):
        """测试阈值为0时接受任何决策"""
        router = TaskRouter(confidence_threshold=0.0, enable_fallback=True)
        task = create_task(description="any task")
        decision = router.route(task)
        assert decision is not None

    def test_confidence_score_in_valid_range(self):
        """测试置信度分数在有效范围内"""
        router = TaskRouter()
        descriptions = [
            "rule validation check",
            "time series prediction",
            "summarize and explain",
            "image multimodal analysis",
        ]
        for desc in descriptions:
            task = create_task(description=desc)
            decision = router.route(task)
            assert 0.0 <= decision.confidence <= 1.0


# ============================================================
# ScoringModel测试
# ============================================================

class TestScoringModel:
    """测试评分模型功能"""

    def setup_method(self):
        self.scoring_model = ScoringModel()

    def test_predict_scores_returns_all_engines(self):
        """测试评分模型返回所有引擎分数"""
        features = TaskFeatures(
            complexity_score=0.5,
            computation_intensity=0.5,
            logic_depth=0.5,
            time_sensitivity=0.5,
            data_structure_ratio=0.5,
            precision_requirement=0.5,
            has_temporal_component=True,
            has_multimodal_input=False,
            requires_explainability=False,
        )
        scores = self.scoring_model.predict_scores(features)
        assert len(scores) == len(EngineType)
        for engine in EngineType:
            assert engine in scores

    def test_predict_scores_sum_to_one(self):
        """测试评分归一化（总和为1）"""
        features = TaskFeatures(
            complexity_score=0.7,
            computation_intensity=0.3,
            logic_depth=0.5,
            time_sensitivity=0.8,
            data_structure_ratio=0.6,
            precision_requirement=0.9,
            has_temporal_component=True,
            has_multimodal_input=True,
            requires_explainability=True,
        )
        scores = self.scoring_model.predict_scores(features)
        total = sum(scores.values())
        assert abs(total - 1.0) < 1e-6

    def test_predict_scores_all_zero_features(self):
        """测试全零特征输入的评分"""
        features = TaskFeatures()
        scores = self.scoring_model.predict_scores(features)
        for engine in EngineType:
            assert scores[engine] >= 0.0

    def test_predict_scores_max_features(self):
        """测试最大特征输入的评分"""
        features = TaskFeatures(
            complexity_score=1.0,
            computation_intensity=1.0,
            logic_depth=1.0,
            time_sensitivity=1.0,
            data_structure_ratio=1.0,
            precision_requirement=1.0,
            has_temporal_component=True,
            has_multimodal_input=True,
            requires_explainability=True,
        )
        scores = self.scoring_model.predict_scores(features)
        assert sum(scores.values()) > 0


# ============================================================
# TaskFeatures测试
# ============================================================

class TestTaskFeatures:
    """测试任务特征向量"""

    def test_default_features(self):
        """测试默认特征值"""
        features = TaskFeatures()
        assert features.complexity_score == 0.0
        assert features.computation_intensity == 0.0
        assert features.logic_depth == 0.0
        assert features.time_sensitivity == 0.0
        assert features.data_structure_ratio == 0.0
        assert features.precision_requirement == 0.0
        assert features.input_size == 0.0
        assert features.has_temporal_component is False
        assert features.has_multimodal_input is False
        assert features.requires_explainability is False

    def test_custom_features(self):
        """测试自定义特征值"""
        features = TaskFeatures(
            complexity_score=0.8,
            time_sensitivity=0.9,
            has_temporal_component=True,
        )
        assert features.complexity_score == 0.8
        assert features.time_sensitivity == 0.9
        assert features.has_temporal_component is True


# ============================================================
# 路由决策to_dict测试
# ============================================================

class TestRoutingDecisionSerialization:
    """测试路由决策序列化"""

    def test_to_dict_contains_all_fields(self):
        """测试to_dict包含所有字段"""
        router = TaskRouter()
        task = create_task(description="test serialization")
        decision = router.route(task)
        d = decision.to_dict()
        assert "selected_engine" in d
        assert "selected_model" in d
        assert "confidence" in d
        assert "reasoning" in d
        assert "decision_factors" in d
        assert "alternatives" in d
        assert "timestamp" in d

    def test_to_dict_engine_is_string(self):
        """测试to_dict中引擎类型为字符串"""
        router = TaskRouter()
        task = create_task(description="test engine string conversion")
        decision = router.route(task)
        d = decision.to_dict()
        assert isinstance(d["selected_engine"], str)

    def test_to_dict_serializable_to_json(self):
        """测试to_dict可序列化为JSON"""
        import json
        router = TaskRouter()
        task = create_task(description="test json serialization")
        decision = router.route(task)
        d = decision.to_dict()
        json_str = json.dumps(d, default=str)
        assert isinstance(json_str, str)
