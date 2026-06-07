"""
Hybrid Architecture Data Pipeline System

支持多源异构数据融合处理的管道架构，兼容图像、时序数据、文本信息及3D模型等多种数据类型。
提供标准化、可配置的数据预处理流程，优化数据流在各处理层之间的传输效率。

Core Components:
- datatypes: 数据类型定义和数据结构
- sources: 数据源连接器
- preprocessors: 各类数据预处理器
- features: 特征提取模块
- sliding_window: 滑动窗口处理
- fusion: 多模态数据融合
- pipeline: 主管道 orchestration
- config: 配置管理
- validation: 数据质量验证
- monitoring: 性能监控

Example:
    >>> from app.data.pipeline import create_pipeline, DataPipeline
    >>> pipeline = create_pipeline("config/data_pipeline.yaml")
    >>> result = pipeline.process(raw_input)
    >>> fused_features = result.fused_features
"""

from app.data.pipeline.datatypes import (
    DataSourceType,
    ProcessedData,
    PipelineResult,
    DataQualityMetrics,
    RawInput,
    ImageInput,
    TimeSeriesInput,
    TextInput,
    ToolStateInput,
    GCodeInput,
)
from app.data.pipeline.config import (
    PipelineConfig,
    load_config,
    get_default_config,
)
from app.data.pipeline.pipeline import DataPipeline, create_pipeline
from app.data.pipeline.preprocessors import (
    ImagePreprocessor,
    TimeSeriesPreprocessor,
    TextPreprocessor,
    ToolStatePreprocessor,
    GCodePreprocessor,
)
from app.data.pipeline.features import (
    CNNFeatureExtractor,
    TimeSeriesFeatureEngineer,
    BGEEmbedder,
    GCodeEmbedder,
)
from app.data.pipeline.fusion import MultiModalFusion, CrossModalAttentionFusion
from app.data.pipeline.sliding_window import SlidingWindowConfig, SlidingWindowProcessor
from app.data.pipeline.loader import (
    ParallelDataLoader,
    BatchConfig,
    CachedDataset,
)
from app.data.pipeline.validation import DataValidator, QualityChecker
from app.data.pipeline.monitoring import PipelineMonitor, PerformanceMetrics

__all__ = [
    DataSourceType,
    ProcessedData,
    PipelineResult,
    DataQualityMetrics,
    RawInput,
    ImageInput,
    TimeSeriesInput,
    TextInput,
    ToolStateInput,
    GCodeInput,
    PipelineConfig,
    load_config,
    get_default_config,
    DataPipeline,
    create_pipeline,
    ImagePreprocessor,
    TimeSeriesPreprocessor,
    TextPreprocessor,
    ToolStatePreprocessor,
    GCodePreprocessor,
    CNNFeatureExtractor,
    TimeSeriesFeatureEngineer,
    BGEEmbedder,
    GCodeEmbedder,
    MultiModalFusion,
    CrossModalAttentionFusion,
    SlidingWindowConfig,
    SlidingWindowProcessor,
    ParallelDataLoader,
    BatchConfig,
    CachedDataset,
    DataValidator,
    QualityChecker,
    PipelineMonitor,
    PerformanceMetrics,
]
