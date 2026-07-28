"""Core data models and type definitions for the Liquid Neural Network (LNN) system.

This module provides the foundational data structures, enumerations, and dataclasses
used throughout the LNN hybrid inference pipeline. It defines standardized input/output
formats, routing decisions, model configurations, and fusion results.

Key components:
    - EngineType, ModelType, DataType, TaskCategory: Enumerations for categorizing
      engines, models, data types, and task categories.
    - TaskInput: Standardized task input with metadata and requirements.
    - RoutingDecision: Router output containing engine selection and reasoning.
    - InferenceResult: Standardized inference output with confidence and metadata.
    - FusionResult: Fused multi-engine result with explainability reports.
    - ModelConfig: Model configuration for loading and execution.
    - PreprocessingResult: Output from the data preprocessing pipeline.

Example:
    >>> from app.ai.lnn.core import TaskInput, EngineType, TaskCategory
    >>> task = TaskInput(
    ...     task_description="Predict tool wear",
    ...     input_data=[1.0, 2.0, 3.0],
    ...     task_category=TaskCategory.REGRESSION,
    ... )
    >>> print(task.task_category)
    TaskCategory.REGRESSION
"""

from enum import Enum
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
import numpy as np


class EngineType(str, Enum):
    """Enumeration of available inference engine types.

    Used by the task router to select the appropriate engine for a given task.

    Attributes:
        LNN: Liquid Neural Network engine for fast, efficient inference.
        LLM: Large Language Model engine for complex reasoning tasks.
        HYBRID: Combined engine that integrates multiple inference approaches.
        RULE: Rule-based engine for deterministic process rule evaluation.

    Example:
        >>> EngineType.LNN.value
        'LNN'
    """

    LNN = "LNN"
    LLM = "LLM"
    HYBRID = "Hybrid"
    RULE = "Rule"


class ModelType(str, Enum):
    """Enumeration of Liquid Neural Network model architectures.

    Attributes:
        CFC: Closed-form Continuous-time model for efficient ODE approximation.
        LTC: Liquid Time-Constant model with adaptive time constants.
        HYBRID_LNN: Hybrid LNN combining multiple architectures.

    Example:
        >>> ModelType.CFC.value
        'CFC'
    """

    CFC = "CFC"
    LTC = "LTC"
    HYBRID_LNN = "HybridLNN"


class DataType(str, Enum):
    """Enumeration of supported data types.

    Attributes:
        STRUCTURED: Tabular or relational data with fixed schema.
        UNSTRUCTURED: Free-form data such as text or raw sensor streams.
        SEMI_STRUCTURED: Data with partial structure (e.g., JSON, XML).
        MULTIMODAL: Data combining multiple modalities (text, image, numeric).

    Example:
        >>> DataType.STRUCTURED.value
        'structured'
    """

    STRUCTURED = "structured"
    UNSTRUCTURED = "unstructured"
    SEMI_STRUCTURED = "semi_structured"
    MULTIMODAL = "multimodal"


class TaskCategory(str, Enum):
    """Enumeration of task categories for routing and model selection.

    Attributes:
        CLASSIFICATION: Categorical prediction tasks.
        REGRESSION: Continuous value prediction tasks.
        TIME_SERIES: Sequential data with temporal dependencies.
        NLP: Natural language processing tasks.
        VISION: Image or visual data processing tasks.
        LOGIC_REASONING: Logical inference and deduction tasks.
        RULE_BASED: Tasks driven by deterministic process rules.

    Example:
        >>> TaskCategory.TIME_SERIES.value
        'time_series'
    """

    CLASSIFICATION = "classification"
    REGRESSION = "regression"
    TIME_SERIES = "time_series"
    NLP = "nlp"
    VISION = "vision"
    LOGIC_REASONING = "logic_reasoning"
    RULE_BASED = "rule_based"


@dataclass
class TaskInput:
    """Standardized task input for the LNN inference pipeline.

    Encapsulates all information needed to process a single inference task,
    including the raw input data, task description, quality requirements,
    and performance constraints.

    Attributes:
        task_description: Human-readable description of the task.
        input_data: Raw input data (numeric arrays, dicts, or other formats).
        context: Optional contextual information for routing and inference.
        task_category: The category of task (auto-detected if None).
        data_type: The type of input data (auto-detected if None).
        precision_requirement: Minimum required prediction accuracy (0.0-1.0).
        time_sensitivity: How time-critical the task is (0.0-1.0).
        max_latency_ms: Maximum acceptable inference latency in milliseconds.
        metadata: Optional additional metadata for tracking and debugging.

    Example:
        >>> task = TaskInput(
        ...     task_description="Predict surface roughness",
        ...     input_data={"cutting_speed": 200, "feed_rate": 0.2},
        ...     precision_requirement=0.95,
        ...     max_latency_ms=500,
        ... )
    """

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
    """Result of the task routing decision process.

    Contains the selected engine, model, and reasoning for why a particular
    inference path was chosen. Used by the hybrid inference engine to
    dispatch tasks to the appropriate subsystem.

    Attributes:
        selected_engine: The engine type chosen by the router.
        selected_model: Specific model name within the selected engine.
        confidence: Confidence in the routing decision (0.0-1.0).
        reasoning: Human-readable explanation for the routing decision.
        decision_factors: Scores for each factor considered in routing.
        alternatives: List of alternative engine/model combinations.
        timestamp: Unix timestamp when the decision was made.

    Example:
        >>> decision = RoutingDecision(
        ...     selected_engine=EngineType.LNN,
        ...     selected_model="CFC-Fast",
        ...     confidence=0.85,
        ...     reasoning="Numeric input with low latency requirement",
        ... )
        >>> decision.to_dict()["selected_engine"]
        'LNN'
    """

    selected_engine: EngineType
    selected_model: Optional[str] = None
    confidence: float = 0.0
    reasoning: str = ""
    decision_factors: Optional[Dict[str, float]] = None
    alternatives: Optional[List[Dict[str, Any]]] = None
    timestamp: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert routing decision to a serializable dictionary.

        Returns:
            Dictionary containing all routing decision fields with
            enum values converted to strings.
        """
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
    """Standardized output from a single inference engine.

    Wraps the prediction along with metadata about how it was produced,
    including confidence scores, processing time, and uncertainty estimates.

    Attributes:
        prediction: The model's prediction (scalar, array, or structured output).
        confidence: Confidence score for the prediction (0.0-1.0).
        engine_used: The engine that produced this result.
        model_used: Specific model name within the engine.
        processing_time_ms: Time taken to produce the result in milliseconds.
        metadata: Additional metadata such as timestamps, shapes, and flags.
        evidence: List of supporting evidence for the prediction.
        uncertainty: Dictionary of uncertainty metrics (entropy, variance, etc.).

    Example:
        >>> result = InferenceResult(
        ...     prediction=[0.8, 0.15, 0.05],
        ...     confidence=0.85,
        ...     engine_used=EngineType.LNN,
        ...     model_used="CFC-Fast",
        ...     processing_time_ms=12.5,
        ... )
        >>> result.to_dict()["confidence"]
        0.85
    """

    prediction: Any
    confidence: float = 0.0
    engine_used: Optional[EngineType] = None
    model_used: Optional[str] = None
    processing_time_ms: float = 0.0
    metadata: Optional[Dict[str, Any]] = None
    evidence: Optional[List[Dict[str, Any]]] = None
    uncertainty: Optional[Dict[str, float]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert inference result to a serializable dictionary.

        Returns:
            Dictionary containing all inference result fields with
            enum values converted to strings and None defaults replaced
            with empty containers.
        """
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
    """Fused result from combining multiple inference engine outputs.

    Produced by the Dempster-Shafer fusion layer when multiple engine results
    need to be integrated into a single prediction with aggregated confidence.

    Attributes:
        final_prediction: The fused prediction after combining all engines.
        confidence: Aggregated confidence from the fusion process (0.0-1.0).
        contributing_engines: List of engines that contributed to the fusion.
        fusion_method: Name of the fusion method used (default: "dempster_shafer").
        reasoning_path: Step-by-step trace of the fusion reasoning.
        explainability_report: Human-readable report explaining the fusion.
        quality_metrics: Dictionary of quality assessment metrics.

    Example:
        >>> fusion = FusionResult(
        ...     final_prediction=[0.75, 0.2, 0.05],
        ...     confidence=0.88,
        ...     fusion_method="dempster_shafer",
        ... )
        >>> fusion.to_dict()["fusion_method"]
        'dempster_shafer'
    """

    final_prediction: Any
    confidence: float = 0.0
    contributing_engines: List[Dict[str, Any]] = field(default_factory=list)
    fusion_method: str = "dempster_shafer"
    reasoning_path: Optional[List[str]] = None
    explainability_report: Optional[str] = None
    quality_metrics: Optional[Dict[str, float]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert fusion result to a serializable dictionary.

        Returns:
            Dictionary containing all fusion result fields with None
            defaults replaced with empty containers.
        """
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
    """Configuration for loading and running an LNN model.

    Contains all parameters needed to instantiate a model, including
    architecture type, file path, device placement, and hyperparameters.

    Attributes:
        model_type: The architecture type (CFC, LTC, or HybridLNN).
        model_name: Human-readable name for the model.
        model_path: File path to saved model weights (None for newly built models).
        hyperparameters: Model-specific hyperparameters dictionary.
        device: Computation device ("cpu", "cuda", etc.).
        batch_size: Default batch size for inference.
        version: Semantic version string for the model.
        metadata: Optional additional metadata (training date, dataset, etc.).

    Example:
        >>> config = ModelConfig(
        ...     model_type=ModelType.CFC,
        ...     model_name="CFC-Fast",
        ...     model_path="/models/cfc_v1.pt",
        ...     device="cuda",
        ... )
    """

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
    """Output from the data preprocessing pipeline.

    Contains the processed feature matrix along with metadata about the
    transformations applied during preprocessing.

    Attributes:
        features: Preprocessed feature matrix (n_samples, n_features).
        feature_names: List of feature column names.
        normalization_method: Method used for normalization ("z_score", "min_max").
        outliers_detected: Number of outliers detected and handled.
        missing_values_filled: Number of missing values that were imputed.
        metadata: Additional metadata such as mean, std, and original shape.

    Example:
        >>> result = PreprocessingResult(
        ...     features=np.array([[0.5, -0.3], [1.2, 0.8]]),
        ...     feature_names=["speed", "feed"],
        ...     normalization_method="z_score",
        ... )
    """

    features: np.ndarray
    feature_names: Optional[List[str]] = None
    normalization_method: str = "z_score"
    outliers_detected: int = 0
    missing_values_filled: int = 0
    metadata: Optional[Dict[str, Any]] = None
