"""``shared.lnn`` —— 颤振预测（LTC/LNN）契约子包。

子模块：
- ``protocols``  ``ChatterPredictorProtocol`` / ``ModelLoaderProtocol``（typing.Protocol）
- ``artifact``   ``ModelArtifactSpec``（模型文件即契约：ONNX + model_card + preprocessor + schema）
- ``model_card`` ``ModelCard``（git SHA / 数据 hash / 训练超参 / 评估指标）
- ``types``      ``FeatureChatterResult`` / ``PredictionMethod`` / ``ChatterReviewStatus`` / ``ChatterPredictionTaskStatus``

设计动机：工程侧 ONNX Runtime 加载与科研侧 torch 训练通过本子包的类型/协议解耦，
两端共享同一份 ``FeatureChatterResult`` 契约，避免 schema 漂移导致 D-2 学术诚信硬约束被破坏。
"""

from shared.lnn.artifact import ModelArtifactSpec
from shared.lnn.model_card import ModelCard
from shared.lnn.protocols import ChatterPredictorProtocol, ModelLoaderProtocol
from shared.lnn.types import (
    ChatterPredictionTaskStatus,
    ChatterReviewStatus,
    FeatureChatterResult,
    PredictionMethod,
)

__all__ = [
    "ChatterPredictorProtocol",
    "ModelLoaderProtocol",
    "ModelArtifactSpec",
    "ModelCard",
    "FeatureChatterResult",
    "PredictionMethod",
    "ChatterReviewStatus",
    "ChatterPredictionTaskStatus",
]
