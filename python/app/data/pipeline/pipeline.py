"""
主数据管道 Orchestration

协调整个数据处理流程：
1. 数据源输入 -> 2. 类型分发 -> 3. 预处理 -> 4. 特征提取 -> 5. 数据融合 -> 6. 输出
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

import numpy as np

from app.data.pipeline.datatypes import (
    DataSourceType,
    ProcessedData,
    PipelineResult,
    RawInput,
)
from app.data.pipeline.config import (
    PipelineConfig,
    load_config,
    get_default_config,
)
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
from app.data.pipeline.fusion import (
    MultiModalFusion,
    CrossModalAttentionFusion,
)
from app.data.pipeline.loader import CachedDataset
from app.data.pipeline.validation import DataValidator, QualityChecker
from app.data.pipeline.monitoring import PipelineMonitor

logger = logging.getLogger(__name__)


def create_pipeline(
    config_path: Optional[str] = None,
    device: str = "cpu",
) -> DataPipeline:
    """
    创建数据管道

    Args:
        config_path: 配置文件路径，None则使用默认配置
        device: 计算设备 (cpu|cuda)

    Returns:
        数据管道实例
    """
    if config_path:
        config = load_config(config_path)
    else:
        config = get_default_config()
    return DataPipeline(config, device=device)


class DataPipeline:
    """
    混合架构数据管道主类

    协调整个多源异构数据融合处理流程。
    """

    def __init__(self, config: PipelineConfig, device: str = "cpu"):
        self.config = config
        self.device = device
        self._preprocessors: Dict[DataSourceType, Any] = {}
        self._feature_extractors: Dict[DataSourceType, Any] = {}
        self._fusion = None
        self._quality_checker = None
        self._validator = None
        self._cache = None
        self._monitor = None
        self._initialized = False

        self._init_components()

    def _init_components(self):
        """初始化所有组件"""
        self._preprocessors = {
            DataSourceType.IMAGE: ImagePreprocessor(self.config.image),
            DataSourceType.TIME_SERIES: TimeSeriesPreprocessor(self.config.time_series),
            DataSourceType.TEXT: TextPreprocessor(self.config.text),
            DataSourceType.TOOL_STATE: ToolStatePreprocessor(self.config.tool_state),
            DataSourceType.GCODE: GCodePreprocessor(self.config.gcode),
        }

        self._feature_extractors = {
            DataSourceType.IMAGE: CNNFeatureExtractor(
                self.config.image, device=self.device,
            ),
            DataSourceType.TIME_SERIES: TimeSeriesFeatureEngineer(
                self.config.time_series,
            ),
            DataSourceType.TEXT: BGEEmbedder(self.config.text),
            DataSourceType.TOOL_STATE: None,
            DataSourceType.GCODE: GCodeEmbedder(self.config.gcode),
        }

        if self.config.fusion.fusion_method == "weighted":
            self._fusion = MultiModalFusion(self.config.fusion)
        else:
            self._fusion = CrossModalAttentionFusion(self.config.fusion)

        self._quality_checker = QualityChecker(self.config)
        self._validator = DataValidator(self.config)

        cache_size_gb = int(float(self.config.memory_limit.replace("GB", "").strip())) * 1000
        self._cache = CachedDataset(max_cache_size=cache_size_gb)

        self._monitor = PipelineMonitor(self.config.monitoring)
        self._initialized = True

        logger.info(
            "数据管道初始化完成: 融合方法=%s, 监控=%s",
            self.config.fusion.fusion_method,
            self.config.monitoring.enabled,
        )

    def preprocess(self, raw_input: RawInput) -> ProcessedData:
        """单源数据预处理"""
        t0 = time.perf_counter()
        preprocessor = self._preprocessors.get(raw_input.source_type)
        if preprocessor is None:
            raise ValueError(f"不支持的数据类型: {raw_input.source_type}")

        result = preprocessor.preprocess(raw_input)
        delay = (time.perf_counter() - t0) * 1000

        if self._monitor:
            self._monitor.record_processing(delay, raw_input.source_type.value)

        return result

    def extract_features(self, processed: ProcessedData) -> Optional[np.ndarray]:
        """从预处理数据提取特征"""
        extractor = self._feature_extractors.get(processed.source_type)
        if extractor is None:
            return processed.processed_data.flatten()
        return extractor.extract(processed)

    def process(
        self,
        inputs: Dict[str, RawInput],
        expected_dims: Optional[Dict[str, int]] = None,
    ) -> PipelineResult:
        """
        处理多源输入，执行完整管道流程

        Args:
            inputs: {name: RawInput} 输入字典，支持任意组合的数据源
            expected_dims: 可选期望维度，用于验证

        Returns:
            融合后的最终结果
        """
        t_start = time.perf_counter()
        stage_timings: Dict[str, float] = {}

        processed_data: Dict[str, ProcessedData] = {}
        features: Dict[str, np.ndarray] = {}
        error_log: List[str] = []

        expected = expected_dims or self._get_expected_dims()

        t = time.perf_counter()
        for name, raw_input in inputs.items():
            try:
                processed = self.preprocess(raw_input)
                processed_data[name] = processed
                feat = self.extract_features(processed)
                if feat is not None:
                    features[name] = feat
            except Exception as e:
                logger.error("处理失败 %s: %s", name, e, exc_info=True)
                error_log.append(
                    f"{name} (preprocess/extract): {type(e).__name__}"
                )
        stage_timings["preprocess"] = (time.perf_counter() - t) * 1000

        t = time.perf_counter()
        quality_metrics = self._quality_checker.check_all(
            processed_data, expected,
        )
        stage_timings["quality_check"] = (time.perf_counter() - t) * 1000

        for name, metrics in quality_metrics.items():
            error_log.extend([f"{name}: {err}" for err in metrics.validation_errors])

        t = time.perf_counter()
        if not features:
            raise ValueError("没有成功处理任何特征")

        if self.config.fusion.fusion_method == "weighted" and isinstance(self._fusion, MultiModalFusion):
            fused_features = self._fusion.fuse(features)
        elif isinstance(self._fusion, CrossModalAttentionFusion):
            fused_features = self._fusion.fuse(features)
        else:
            raise ValueError("未知融合器类型")

        fusion_weights = (
            self._fusion.weights
            if hasattr(self._fusion, "weights")
            else {}
        )

        stage_timings["fusion"] = (time.perf_counter() - t) * 1000

        total_time = (time.perf_counter() - t_start) * 1000

        result = PipelineResult(
            fused_features=fused_features,
            individual_features=features,
            quality_metrics=quality_metrics,
            total_processing_time_ms=total_time,
            stage_timings=stage_timings,
            fusion_weights=fusion_weights,
            error_log=error_log,
        )

        return result

    def _get_expected_dims(self) -> Dict[str, int]:
        """获取预处理器输出的期望维度"""
        ws = self.config.time_series.window_size
        ss = self.config.image.image_size
        return {
            "image": ss * ss * 3,
            "time_series": ws * 1,
            "text": self.config.text.bge_embedding_dim,
            "tool_state": len(self.config.tool_state.state_fields),
            "gcode": 21,
        }

    def process_batch(
        self,
        batch_inputs: List[Dict[str, RawInput]],
    ) -> List[PipelineResult]:
        """批量处理多个样本"""
        results = []
        for inputs in batch_inputs:
            results.append(self.process(inputs))
        return results

    def get_cache(self) -> CachedDataset:
        """获取缓存"""
        return self._cache

    def get_monitor(self) -> PipelineMonitor:
        """获取监控器"""
        return self._monitor

    def get_stats(self) -> Dict[str, Any]:
        """获取管道统计"""
        return {
            "initialized": self._initialized,
            "config": self.config.to_dict(),
            "monitor": self._monitor.get_stats() if self._monitor else {},
            "cache_size": len(self._cache) if self._cache else 0,
        }
