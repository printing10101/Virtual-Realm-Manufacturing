"""``shared.lnn.protocols`` —— 颤振预测器与模型加载器协议。

定义工程侧与科研侧共享的 ``typing.Protocol``：
- ``ChatterPredictorProtocol``  颤振预测器协议（``predict_feature`` 签名）
- ``ModelLoaderProtocol``        模型加载器协议（``load`` / ``is_available`` 签名）

工程侧实现：
- ``ChatterPredictorAdapter``（``engineering/python/app/chatter_prediction/predictor_adapter.py``）
  实现 ``ChatterPredictorProtocol``，路径 B 改为 ONNX 加载
- ``OnnxModelLoader``（``engineering/python/app/ai/lnn/inference/onnx_predictor.py``）
  实现 ``ModelLoaderProtocol``，通过 ``onnxruntime.InferenceSession`` 推理

科研侧：
- 训练目标必须能产出符合 ``ChatterPredictorProtocol`` 的输出（``FeatureChatterResult``）
- 训练完成后导出符合 ``ModelArtifactSpec`` 的产物

``typing.Protocol`` 选择 ``runtime_checkable`` 装饰，允许工程侧在加载时
``isinstance(obj, ChatterPredictorProtocol)`` 运行时检查（鸭子类型）。
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from shared.lnn.artifact import ModelArtifactSpec
from shared.lnn.types import FeatureChatterResult


@runtime_checkable
class ChatterPredictorProtocol(Protocol):
    """颤振预测器协议（工程侧实现 / 科研侧训练目标对齐）。

    工程侧 ``ChatterPredictorAdapter`` 必须实现本协议。
    科研侧训练目标的输入/输出 schema 必须与 ``FeatureChatterResult`` 对齐。

    方法签名与现有 ``predictor_adapter.py`` 中 ``ChatterPredictorAdapter.predict_feature``
    完全一致，保证阶段 2 迁移时工程侧行为不变。

    K_s 契约（项目记忆硬约束）：
    - ``chatter_params_dict["tool"]["cutting_force_coeff"]`` 直接读取
    - 不二次拟合（避免引入额外误差）
    - 仅作为追溯字段记录到 ``FeatureChatterResult.cutting_force_coeff``

    HRC52 检测：
    - ``material_id`` 命中 ``PENDING_CALIBRATION_MATERIALS`` 时强制降低置信度
    """

    def predict_feature(
        self,
        feature_id: str,
        feature_type: str,
        material_id: str,
        chatter_params_dict: dict[str, Any],
        source_cutting_params_task_id: str = "",
    ) -> FeatureChatterResult:
        """预测单个特征的颤振稳定性。

        Args:
            feature_id: 特征 ID（如 ``"feature_001"``）
            feature_type: 特征类型（``"plane"`` / ``"cylinder"`` / ``"hole"`` / ``"boss"``）
            material_id: 材料 ID（如 ``"aluminum_6061_t6"`` / ``"steel_hrc52"``）
            chatter_params_dict: 阶段 4 输出的 ChatterParams dict（含 spindle_rpm / machine / tool / axial_depth）
            source_cutting_params_task_id: 来源阶段 4 任务 ID（追溯用）

        Returns:
            ``FeatureChatterResult`` 单个特征的颤振预测结果
        """
        ...


@runtime_checkable
class ModelLoaderProtocol(Protocol):
    """模型加载器协议（工程侧实现）。

    工程侧 ``OnnxModelLoader`` 必须实现本协议。
    科研侧不实现本协议（科研侧直接用 torch 加载 .pt 训练，不通过本协议）。

    设计动机：
    - 工程侧通过 ``ModelArtifactSpec`` 加载科研侧导出的 ONNX + model_card + preprocessor
    - ``is_available()`` 用于 ``check_ltc_model_available()`` 探测（路径 B 是否启用）
    - ``load()`` 返回 ONNX session 或类似推理句柄
    """

    def is_available(self) -> bool:
        """检查模型文件是否存在（不加载模型，避免启动时开销）。

        Returns:
            ``True`` 如果 ``ModelArtifactSpec`` 中所有路径都存在
        """
        ...

    def load(self, spec: ModelArtifactSpec) -> Any:
        """加载模型产物。

        Args:
            spec: ``ModelArtifactSpec`` 模型产物规格

        Returns:
            推理句柄（如 ``onnxruntime.InferenceSession``）

        Raises:
            ``FileNotFoundError``: 任一文件缺失
            ``ValueError``: model_card.json 缺少 git_sha / data_hash 字段
        """
        ...


__all__ = [
    "ChatterPredictorProtocol",
    "ModelLoaderProtocol",
]
