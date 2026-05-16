"""
Task Router Module

Implements hybrid rule-based and machine learning decision algorithm for
automatic optimal inference engine selection based on task characteristics.
"""

import json
import time
import yaml
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass

from app.ai.lnn.core import (
    EngineType,
    ModelType,
    TaskInput,
    RoutingDecision,
)


@dataclass
class TaskFeatures:
    """任务特征向量"""

    complexity_score: float = 0.0
    computation_intensity: float = 0.0
    logic_depth: float = 0.0
    time_sensitivity: float = 0.0
    data_structure_ratio: float = 0.0
    precision_requirement: float = 0.0
    input_size: float = 0.0
    has_temporal_component: bool = False
    has_multimodal_input: bool = False
    requires_explainability: bool = False


class ScoringModel:
    """
    轻量级评分模型，用于辅助路由决策

    使用加权评分机制模拟ML决策，可根据实际训练数据优化权重
    支持从配置文件加载权重，也支持运行时动态更新
    """

    DEFAULT_WEIGHTS: Dict[str, Dict[EngineType, float]] = {
        "complexity_score": {
            EngineType.LNN: 0.3,
            EngineType.LLM: 0.7,
            EngineType.HYBRID: 0.5,
            EngineType.RULE: 0.1,
        },
        "computation_intensity": {
            EngineType.LNN: 0.8,
            EngineType.LLM: 0.2,
            EngineType.HYBRID: 0.6,
            EngineType.RULE: 0.9,
        },
        "logic_depth": {
            EngineType.LNN: 0.6,
            EngineType.LLM: 0.8,
            EngineType.HYBRID: 0.7,
            EngineType.RULE: 0.4,
        },
        "time_sensitivity": {
            EngineType.LNN: 0.9,
            EngineType.LLM: 0.3,
            EngineType.HYBRID: 0.5,
            EngineType.RULE: 0.8,
        },
        "data_structure_ratio": {
            EngineType.LNN: 0.7,
            EngineType.LLM: 0.2,
            EngineType.HYBRID: 0.6,
            EngineType.RULE: 0.8,
        },
        "precision_requirement": {
            EngineType.LNN: 0.5,
            EngineType.LLM: 0.6,
            EngineType.HYBRID: 0.8,
            EngineType.RULE: 0.4,
        },
        "has_temporal_component": {
            EngineType.LNN: 0.9,
            EngineType.LLM: 0.4,
            EngineType.HYBRID: 0.6,
            EngineType.RULE: 0.2,
        },
        "has_multimodal_input": {
            EngineType.LNN: 0.3,
            EngineType.LLM: 0.5,
            EngineType.HYBRID: 0.9,
            EngineType.RULE: 0.1,
        },
        "requires_explainability": {
            EngineType.LNN: 0.8,
            EngineType.LLM: 0.5,
            EngineType.HYBRID: 0.7,
            EngineType.RULE: 0.9,
        },
    }

    DEFAULT_FEATURE_IMPORTANCE = {
        "complexity_score": 0.15,
        "computation_intensity": 0.12,
        "logic_depth": 0.15,
        "time_sensitivity": 0.15,
        "data_structure_ratio": 0.10,
        "precision_requirement": 0.10,
        "has_temporal_component": 0.08,
        "has_multimodal_input": 0.08,
        "requires_explainability": 0.07,
    }

    def __init__(self, config_path: Optional[str] = None):
        """
        初始化评分模型

        Args:
            config_path: 可选，权重配置文件路径 (YAML/JSON)
        """
        self.weights: Dict[str, Dict[EngineType, float]] = {}
        self.feature_importance: Dict[str, float] = {}

        if config_path:
            self.weights = self._load_weights_from_config(config_path)
        else:
            self.weights = {k: dict(v) for k, v in self.DEFAULT_WEIGHTS.items()}

        self.feature_importance = dict(self.DEFAULT_FEATURE_IMPORTANCE)

    def _load_weights_from_config(
        self, config_path: str
    ) -> Dict[str, Dict[EngineType, float]]:
        """从配置文件加载权重"""
        path = Path(config_path)
        if not path.exists():
            raise FileNotFoundError(
                f"任务路由配置失败：找不到权重配置文件 '{config_path}'。可能原因：1) 配置文件路径错误；2) 配置文件尚未创建。请检查路由配置中的路径设置，或创建新的权重配置文件（JSON/YAML 格式）。"
            )

        with open(path, "r", encoding="utf-8") as f:
            if path.suffix in (".yaml", ".yml"):
                raw = yaml.safe_load(f)
            elif path.suffix == ".json":
                raw = json.load(f)
            else:
                raise ValueError(
                    f"任务路由配置失败：不支持的配置文件格式 '{path.suffix}'。支持的配置文件格式包括：'.json'（JSON 格式）、'.yaml'/.yml（YAML 格式）。请将配置转换为支持的格式，或检查文件扩展名是否正确。"
                )

        if "weights" not in raw:
            raise KeyError(
                '任务路由配置解析失败：配置文件中缺少必需的 \'weights\' 字段。\'weights\' 字段定义各引擎（LNN、规则引擎、ML 模型）的权重分配，格式为 {"lnn": 0.6, "rule": 0.3, "ml": 0.1}。请检查并补充配置文件。'
            )

        weights: Dict[str, Dict[EngineType, float]] = {}
        for feature_name, engine_weights_raw in raw["weights"].items():
            engine_weights: Dict[EngineType, float] = {}
            for engine_str, weight_val in engine_weights_raw.items():
                try:
                    engine = EngineType(engine_str)
                    engine_weights[engine] = float(weight_val)
                except ValueError:
                    raise ValueError(f"无效的引擎类型: {engine_str}")
            weights[feature_name] = engine_weights

        if "feature_importance" in raw:
            self.feature_importance = {
                k: float(v) for k, v in raw["feature_importance"].items()
            }

        return weights

    def update_weights(self, feature: str, engine: EngineType, weight: float) -> None:
        """
        运行时更新单个权重值

        Args:
            feature: 特征名称
            engine: 引擎类型
            weight: 新权重值
        """
        if feature not in self.weights:
            raise KeyError(f"无效的特征名称: {feature}")
        if engine not in self.weights[feature]:
            raise KeyError(
                f"引擎路由映射失败：无效的引擎类型 '{engine}'。支持的引擎类型可通过 task_router.AVAILABLE_ENGINES 查看。请检查配置中的 engine 参数。"
            )
        self.weights[feature][engine] = float(weight)

    def save_config(self, config_path: str) -> None:
        """
        将当前权重配置保存到文件

        Args:
            config_path: 保存路径 (YAML/JSON)
        """
        path = Path(config_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        serializable_weights = {
            feature: {engine.value: weight for engine, weight in engines.items()}
            for feature, engines in self.weights.items()
        }
        data = {
            "weights": serializable_weights,
            "feature_importance": self.feature_importance,
        }

        with open(path, "w", encoding="utf-8") as f:
            if path.suffix in (".yaml", ".yml"):
                yaml.dump(data, f, default_flow_style=False, allow_unicode=True)
            elif path.suffix == ".json":
                json.dump(data, f, indent=2, ensure_ascii=False)
            else:
                raise ValueError(
                    f"任务路由配置保存失败：不支持的配置文件格式 '{path.suffix}'。支持的配置文件格式包括：'.json'（JSON 格式）、'.yaml'/.yml（YAML 格式）。请更改文件扩展名为支持的格式后重试。"
                )

    def predict_scores(self, features: TaskFeatures) -> Dict[EngineType, float]:
        """
        预测各引擎的适配分数

        Args:
            features: 任务特征

        Returns:
            各引擎的分数
        """
        scores = {engine: 0.0 for engine in EngineType}

        feature_dict = {
            "complexity_score": features.complexity_score,
            "computation_intensity": features.computation_intensity,
            "logic_depth": features.logic_depth,
            "time_sensitivity": features.time_sensitivity,
            "data_structure_ratio": features.data_structure_ratio,
            "precision_requirement": features.precision_requirement,
            "has_temporal_component": float(features.has_temporal_component),
            "has_multimodal_input": float(features.has_multimodal_input),
            "requires_explainability": float(features.requires_explainability),
        }

        for feature_name, feature_value in feature_dict.items():
            importance = self.feature_importance.get(feature_name, 0.1)
            for engine in EngineType:
                weight = self.weights[feature_name].get(engine, 0.0)
                scores[engine] += feature_value * weight * importance

        # 归一化
        total = sum(scores.values())
        if total > 0:
            scores = {k: v / total for k, v in scores.items()}

        return scores


class TaskRouter:
    """
    任务路由器

    实现基于规则与机器学习的混合决策算法，根据任务特征自动选择最优推理引擎
    """

    # 规则引擎关键词映射
    RULE_KEYWORDS = [
        "if",
        "then",
        "else",
        "rule",
        "条件",
        "规则",
        "判断",
        "阈值",
        "threshold",
        "validation",
        "验证",
        "check",
        "检查",
    ]

    # LLM任务关键词映射
    LLM_KEYWORDS = [
        "explain",
        "解释",
        "summarize",
        "总结",
        "translate",
        "翻译",
        "generate",
        "生成",
        "write",
        "写",
        "analyze sentiment",
        "情感分析",
        "conversation",
        "对话",
        "chat",
        "问答",
        "question",
        "问题",
    ]

    # 时序任务关键词
    TEMPORAL_KEYWORDS = [
        "time series",
        "时序",
        "predict",
        "预测",
        "forecast",
        "预报",
        "trend",
        "趋势",
        "sequence",
        "序列",
        "temporal",
        "时间",
        "history",
        "历史",
        "future",
        "未来",
    ]

    # 多模态任务关键词
    MULTIMODAL_KEYWORDS = [
        "image",
        "图像",
        "vision",
        "视觉",
        "multimodal",
        "多模态",
        "picture",
        "图片",
        "photo",
        "照片",
        "combined",
        "组合",
    ]

    def __init__(
        self,
        rule_weight: float = 0.4,
        ml_weight: float = 0.6,
        confidence_threshold: float = 0.7,
        enable_fallback: bool = True,
    ):
        """
        初始化任务路由器

        Args:
            rule_weight: 规则决策权重
            ml_weight: ML决策权重
            confidence_threshold: 置信度阈值
            enable_fallback: 是否启用降级策略
        """
        self.rule_weight = rule_weight
        self.ml_weight = ml_weight
        self.confidence_threshold = confidence_threshold
        self.enable_fallback = enable_fallback
        self.scoring_model = ScoringModel()
        self.decision_history: List[RoutingDecision] = []

    def route(self, task: TaskInput) -> RoutingDecision:
        """
        路由决策主入口

        Args:
            task: 任务输入

        Returns:
            RoutingDecision 路由决策结果
        """
        try:
            # 1. 解析任务特征
            features = self._extract_features(task)

            # 2. 规则引擎评分
            rule_scores = self._rule_based_scoring(task, features)

            # 3. ML模型评分
            ml_scores = self.scoring_model.predict_scores(features)

            # 4. 混合决策
            combined_scores = self._combine_scores(rule_scores, ml_scores)

            # 5. 选择最优引擎
            selected_engine = max(combined_scores, key=combined_scores.get)
            confidence = combined_scores[selected_engine]

            # 6. 确定具体模型
            selected_model = self._select_model(selected_engine, features)

            # 7. 降级检查
            if confidence < self.confidence_threshold and self.enable_fallback:
                selected_engine, confidence = self._apply_fallback(
                    selected_engine, confidence, combined_scores
                )

            # 8. 生成决策依据
            reasoning = self._generate_reasoning(
                selected_engine, features, rule_scores, ml_scores, combined_scores
            )

            decision = RoutingDecision(
                selected_engine=selected_engine,
                selected_model=selected_model,
                confidence=confidence,
                reasoning=reasoning,
                decision_factors=combined_scores,
                alternatives=self._get_alternatives(combined_scores, selected_engine),
                timestamp=time.perf_counter(),
            )

            self.decision_history.append(decision)
            return decision

        except Exception as e:
            # 异常处理：降级到规则引擎
            if self.enable_fallback:
                return RoutingDecision(
                    selected_engine=EngineType.RULE,
                    confidence=0.5,
                    reasoning=f"Error during routing: {str(e)}. Fallback to Rule engine.",
                    timestamp=time.perf_counter(),
                )
            raise

    def _extract_features(self, task: TaskInput) -> TaskFeatures:
        """
        从任务描述中提取特征

        Args:
            task: 任务输入

        Returns:
            TaskFeatures 任务特征
        """
        description = task.task_description.lower()

        features = TaskFeatures()

        # 计算复杂度（基于描述长度和关键词密度）
        word_count = len(description.split())
        features.complexity_score = min(1.0, word_count / 100)

        # 计算逻辑深度（基于逻辑关键词）
        logic_keywords = ["if", "then", "and", "or", "not", "逻辑", "条件", "规则"]
        logic_count = sum(1 for kw in logic_keywords if kw in description)
        features.logic_depth = min(1.0, logic_count / 10)

        # 时间敏感性
        features.time_sensitivity = task.time_sensitivity
        if (
            "real-time" in description
            or "实时" in description
            or "urgent" in description
        ):
            features.time_sensitivity = max(features.time_sensitivity, 0.9)

        # 数据结构化程度
        features.data_structure_ratio = self._estimate_structure_ratio(description)

        # 精度要求
        features.precision_requirement = task.precision_requirement

        # 计算密集度
        features.computation_intensity = self._estimate_computation_intensity(
            description
        )

        # 时序成分检测
        features.has_temporal_component = any(
            kw in description for kw in self.TEMPORAL_KEYWORDS
        )

        # 多模态检测
        features.has_multimodal_input = any(
            kw in description for kw in self.MULTIMODAL_KEYWORDS
        )

        # 可解释性需求
        features.requires_explainability = any(
            kw in description
            for kw in ["explain", "解释", "why", "为什么", "reason", "原因"]
        )

        return features

    def _rule_based_scoring(
        self, task: TaskInput, features: TaskFeatures
    ) -> Dict[EngineType, float]:
        """
        基于规则的评分

        Args:
            task: 任务输入
            features: 任务特征

        Returns:
            各引擎的规则评分
        """
        scores = {engine: 0.0 for engine in EngineType}
        description = task.task_description.lower()

        # 规则引擎判定
        rule_score = 0.0
        if any(kw in description for kw in self.RULE_KEYWORDS):
            rule_score += 0.5
        if features.logic_depth > 0.5:
            rule_score += 0.2
        if task.max_latency_ms < 50:
            rule_score += 0.3
        scores[EngineType.RULE] = min(1.0, rule_score)

        # LLM判定
        llm_score = 0.0
        if any(kw in description for kw in self.LLM_KEYWORDS):
            llm_score += 0.5
        if features.complexity_score > 0.6:
            llm_score += 0.2
        if features.requires_explainability:
            llm_score += 0.1
        scores[EngineType.LLM] = min(1.0, llm_score)

        # LNN判定
        lnn_score = 0.0
        if features.has_temporal_component:
            lnn_score += 0.4
        if task.max_latency_ms < 100:
            lnn_score += 0.3
        if features.data_structure_ratio > 0.7:
            lnn_score += 0.2
        scores[EngineType.LNN] = min(1.0, lnn_score)

        # Hybrid判定
        hybrid_score = 0.0
        if features.has_multimodal_input:
            hybrid_score += 0.5
        if features.precision_requirement > 0.9:
            hybrid_score += 0.2
        if features.complexity_score > 0.4 and features.data_structure_ratio > 0.4:
            hybrid_score += 0.2
        scores[EngineType.HYBRID] = min(1.0, hybrid_score)

        # 归一化
        total = sum(scores.values())
        if total > 0:
            scores = {k: v / total for k, v in scores.items()}

        return scores

    def _combine_scores(
        self,
        rule_scores: Dict[EngineType, float],
        ml_scores: Dict[EngineType, float],
    ) -> Dict[EngineType, float]:
        """
        混合规则与ML评分

        Args:
            rule_scores: 规则评分
            ml_scores: ML评分

        Returns:
            综合评分
        """
        combined = {}
        for engine in EngineType:
            combined[engine] = self.rule_weight * rule_scores.get(
                engine, 0
            ) + self.ml_weight * ml_scores.get(engine, 0)

        # 归一化
        total = sum(combined.values())
        if total > 0:
            combined = {k: v / total for k, v in combined.items()}

        return combined

    def _select_model(
        self, engine: EngineType, features: TaskFeatures
    ) -> Optional[str]:
        if engine == EngineType.LNN:
            return (
                ModelType.LTC.value
                if features.has_temporal_component
                else ModelType.CFC.value
            )
        elif engine == EngineType.HYBRID:
            return ModelType.HYBRID_LNN.value
        elif engine == EngineType.LLM:
            return "LLM-GPT"
        elif engine == EngineType.RULE:
            return "RuleEngine-v1"
        return None

    def _apply_fallback(
        self,
        selected: EngineType,
        confidence: float,
        scores: Dict[EngineType, float],
    ) -> Tuple[EngineType, float]:
        """
        降级策略

        Args:
            selected: 当前选择的引擎
            confidence: 当前置信度
            scores: 各引擎评分

        Returns:
            (降级后的引擎, 新置信度)
        """
        # 如果置信度太低，选择评分第二高的引擎
        sorted_engines = sorted(scores.items(), key=lambda x: x[1], reverse=True)

        if len(sorted_engines) > 1:
            second_best = sorted_engines[1]
            if second_best[1] > confidence * 0.8:
                return second_best[0], second_best[1]

        return selected, confidence

    def _generate_reasoning(
        self,
        selected: EngineType,
        features: TaskFeatures,
        rule_scores: Dict[EngineType, float],
        ml_scores: Dict[EngineType, float],
        combined_scores: Dict[EngineType, float],
    ) -> str:
        """
        生成决策依据

        Args:
            selected: 选中的引擎
            features: 任务特征
            rule_scores: 规则评分
            ml_scores: ML评分
            combined_scores: 综合评分

        Returns:
            决策依据文本
        """
        reasons = []

        if features.time_sensitivity > 0.7:
            reasons.append(f"高时间敏感性 ({features.time_sensitivity:.2f})")

        if features.has_temporal_component:
            reasons.append("包含时序成分")

        if features.has_multimodal_input:
            reasons.append("多模态输入")

        if features.precision_requirement > 0.9:
            reasons.append(f"高精度要求 ({features.precision_requirement:.2f})")

        reasons.append(f"规则评分: {rule_scores[selected]:.3f}")
        reasons.append(f"ML评分: {ml_scores[selected]:.3f}")

        return f"选择{selected.value}: {'; '.join(reasons)}"

    def _get_alternatives(
        self, scores: Dict[EngineType, float], selected: EngineType
    ) -> List[Dict[str, Any]]:
        """
        获取备选方案

        Args:
            scores: 各引擎评分
            selected: 选中的引擎

        Returns:
            备选方案列表
        """
        alternatives = []
        for engine, score in sorted(scores.items(), key=lambda x: x[1], reverse=True):
            if engine != selected:
                alternatives.append(
                    {
                        "engine": engine.value,
                        "score": round(score, 4),
                    }
                )
        return alternatives[:2]  # 最多返回2个备选

    def _estimate_structure_ratio(self, description: str) -> float:
        """估计数据的结构化程度"""
        structure_indicators = [
            "table",
            "csv",
            "json",
            "database",
            "column",
            "row",
            "表格",
            "结构化",
            "字段",
        ]
        indicator_count = sum(
            1 for kw in structure_indicators if kw in description.lower()
        )
        return min(1.0, indicator_count / 5)

    def _estimate_computation_intensity(self, description: str) -> float:
        """估计计算密集度"""
        high_compute_keywords = [
            "complex",
            "计算",
            "intensive",
            "optimization",
            "优化",
            "simulation",
            "模拟",
            "large-scale",
            "大规模",
        ]
        keyword_count = sum(
            1 for kw in high_compute_keywords if kw in description.lower()
        )
        return min(1.0, keyword_count / 4)

    def get_decision_stats(self) -> Dict[str, Any]:
        """获取决策统计信息"""
        if not self.decision_history:
            return {"total_decisions": 0}

        engine_counts = {}
        avg_confidence = 0.0

        for decision in self.decision_history:
            engine = decision.selected_engine.value
            engine_counts[engine] = engine_counts.get(engine, 0) + 1
            avg_confidence += decision.confidence

        avg_confidence /= len(self.decision_history)

        return {
            "total_decisions": len(self.decision_history),
            "engine_distribution": engine_counts,
            "average_confidence": round(avg_confidence, 4),
        }

    def reset_history(self) -> None:
        """重置决策历史"""
        self.decision_history.clear()
