"""``shared.lnn.artifact`` —— 模型产物规格契约。

定义「模型文件即契约」的物理结构（见 spec 第 4 节）::

    research/checkpoints/chatter_model_<timestamp>/
    ├── model.onnx                # ONNX 推理图
    ├── model_card.json           # git SHA + 数据 hash + 超参 + 评估指标
    ├── preprocessor.pkl          # sklearn Pipeline（transform only，禁 fit_transform）
    ├── input_schema.json         # 输入字段名/类型/范围
    └── output_schema.json        # 输出字段名/类型/范围

工程侧通过 ``ModelArtifactSpec`` 加载这 5 个文件，完全不依赖 torch。
``ModelArtifactSpec`` 是 ``ModelLoaderProtocol.load()`` 的输入。

设计动机：
- 科研侧训练产物以文件形式发布，工程侧通过路径加载
- 文件即接口，科研侧可自由更换训练框架（torch → jax → flax），
  只要导出符合本规格的 ONNX + model_card + preprocessor + schema
- 工程侧 ``requirements.txt`` 仅需 ``onnxruntime`` + ``scikit-learn`` + ``numpy``
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ModelArtifactSpec:
    """模型产物规格（科研侧导出 / 工程侧加载的契约边界）。

    所有路径均为相对路径（相对于 ``research/checkpoints/<model_dir>/``）或绝对路径。
    工程侧加载时会校验所有文件存在性。

    字段说明：
    - ``onnx_path``           ONNX 推理图路径（``model.onnx``）
    - ``model_card_path``     模型卡 JSON 路径（``model_card.json``）
    - ``preprocessor_path``   sklearn Pipeline 序列化路径（``preprocessor.pkl``）
    - ``input_schema_path``   输入 schema JSON 路径（``input_schema.json``）
    - ``output_schema_path``  输出 schema JSON 路径（``output_schema.json``）
    - ``version``             模型版本（如 ``"v1.0.0-20260715"``）
    - ``name``                模型名称（如 ``"chatter_ltc_v1"``）

    硬约束（项目记忆）：
    - ``preprocessor.pkl`` 反序列化后只能调 ``transform``，禁止 ``fit_transform``（防数据泄露）
    - 工程侧加载 ``preprocessor.pkl`` 需要 ``scikit-learn`` 依赖
    - 长期可换 ``skops`` 安全格式彻底消除 sklearn 依赖
    """

    onnx_path: str
    model_card_path: str
    preprocessor_path: str
    input_schema_path: str
    output_schema_path: str
    version: str = ""
    name: str = "chatter_ltc"

    def to_dict(self) -> dict[str, str]:
        """序列化为 dict（用于 ``ModelLoaderProtocol`` 实现的日志记录）。"""
        return {
            "onnx_path": self.onnx_path,
            "model_card_path": self.model_card_path,
            "preprocessor_path": self.preprocessor_path,
            "input_schema_path": self.input_schema_path,
            "output_schema_path": self.output_schema_path,
            "version": self.version,
            "name": self.name,
        }


__all__ = ["ModelArtifactSpec"]
