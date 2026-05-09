"""
Core data models and type definitions for the LNN system.
"""
from enum import Enum
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
import numpy as np


class EngineType(str, Enum):
    """推理引擎类型"""
    LNN = "LNN"
    LLM = "LLM"
    HYBRID = "Hybrid"
    RULE = "Rule"


class ModelType(str, Enum):
    """LNN模型类型"""
    CFC = "CFC"
    LTC = "LTC"
    HYBRID_LNN = "HybridLNN"


class DataType(str, Enum):
    """数据类型"""
    STRUCTURED = "structured"
    UNSTRUCTURED = "unstructured"
    SEMI_STRUCTURED = "semi_structured"
    MULTIMODAL = "multimodal"


class TaskCategory(str, Enum):
    """任务类别"""
    CLASSIFICATION = "classification"
    REGRESSION = "regression"
    TIME_SERIES = "time_series"
    NLP = "nlp"
    VISION = "vision"
    LOGIC_REASONING = "logic_reasoning"
    RULE_BASED = "rule_based"


@dataclass
class TaskInput:
    """标准化任务输入"""
    task_description: str
    input_data: Any
    context: Optional[Dict[str, Any]] = None
    task_category: Optional[TaskCategory] = None
    data_type: Optional[DataType] = None
    precision_requirement: float = 0.9
    time_sensitivity: float = 0.5
    max_latency_ms: int = 1000
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class RoutingDecision:
    """路由决策结果"""
    selected_engine: EngineType
    selected_model: Optional[str] = None
    confidence: float = 0.0
    reasoning: str = ""
    decision_factors: Optional[Dict[str, float]] = None
    alternatives: Optional[List[Dict[str, Any]]] = None
    timestamp: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "selected_engine": self.selected_engine.value,
            "selected_model": self.selected_model,
            "confidence": self.confidence,
            "reasoning": self.reasoning,
            "decision_factors": self.decision_factors or {},
            "alternatives": self.alternatives or [],
            "timestamp": self.timestamp,
        }


@dataclass
class InferenceResult:
    """推理结果"""
    prediction: Any
    confidence: float = 0.0
    engine_used: Optional[EngineType] = None
    model_used: Optional[str] = None
    processing_time_ms: float = 0.0
    metadata: Optional[Dict[str, Any]] = None
    evidence: Optional[List[Dict[str, Any]]] = None
    uncertainty: Optional[Dict[str, float]] = None

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "prediction": self.prediction,
            "confidence": self.confidence,
            "engine_used": self.engine_used.value if self.engine_used else None,
            "model_used": self.model_used,
            "processing_time_ms": self.processing_time_ms,
            "metadata": self.metadata or {},
            "evidence": self.evidence or [],
            "uncertainty": self.uncertainty or {},
        }


@dataclass
class FusionResult:
    """融合后的最终结果"""
    final_prediction: Any
    confidence: float = 0.0
    contributing_engines: List[Dict[str, Any]] = field(default_factory=list)
    fusion_method: str = "dempster_shafer"
    reasoning_path: Optional[List[str]] = None
    explainability_report: Optional[str] = None
    quality_metrics: Optional[Dict[str, float]] = None

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "final_prediction": self.final_prediction,
            "confidence": self.confidence,
            "contributing_engines": self.contributing_engines,
            "fusion_method": self.fusion_method,
            "reasoning_path": self.reasoning_path or [],
            "explainability_report": self.explainability_report,
            "quality_metrics": self.quality_metrics or {},
        }


@dataclass
class ModelConfig:
    """模型配置"""
    model_type: ModelType
    model_name: str
    model_path: Optional[str] = None
    hyperparameters: Optional[Dict[str, Any]] = None
    device: str = "cpu"
    batch_size: int = 32
    version: str = "1.0.0"
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class PreprocessingResult:
    """预处理结果"""
    features: np.ndarray
    feature_names: Optional[List[str]] = None
    normalization_method: str = "z_score"
    outliers_detected: int = 0
    missing_values_filled: int = 0
    metadata: Optional[Dict[str, Any]] = None
