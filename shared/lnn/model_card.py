"""``shared.lnn.model_card`` —— 模型卡契约。

科研侧训练完成后必须生成 ``model_card.json``，与 ONNX 模型一同发布。
工程侧通过 ``ModelArtifactSpec.model_card_path`` 加载本契约，作为模型溯源依据。

D-2 学术诚信硬约束保护：
- ``git_sha`` 与 ``data_hash`` 必须填写，保证实验可复现
- ``training_hyperparams`` 完整记录训练超参
- ``eval_metrics`` 完整记录评估指标
- 任何字段变更需走 ADR 评审

与 MLflow tracking 的关系：
- MLflow 记录训练过程中的实时指标（每 epoch）
- ``ModelCard`` 记录训练完成后的最终快照（git SHA + 数据 hash + 最佳指标）
- 两者互补，MLflow 是过程，``ModelCard`` 是产物
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ModelCard:
    """模型卡（科研侧训练产物，工程侧加载依据）。

    所有字段在科研侧导出时必须填写，工程侧加载时会校验完整性。

    字段说明：
    - ``git_sha``               训练时的 git commit SHA（保证代码可复现）
    - ``data_hash``              训练数据集的 SHA256 hash（保证数据可复现）
    - ``training_hyperparams``  训练超参 dict（学习率 / batch_size / num_epochs / weight_decay 等）
    - ``eval_metrics``           评估指标 dict（MAE / RMSE / R² / PCC 等）
    - ``trained_at``             训练完成时间戳（ISO 8601 字符串）
    - ``training_device``        训练设备描述（如 "cuda:0 / NVIDIA RTX 4060" 或 "cpu"）
    - ``framework_version``     框架版本 dict（如 ``{"torch": "2.1.0", "onnx": "1.16.0"}``）
    - ``dataset_spec_path``     数据集规格文件路径（指向 ``DatasetSpec`` 的 JSON）
    - ``notes``                  自由文本备注（如「阶段二物理残差微调最佳 checkpoint」）
    """

    git_sha: str
    data_hash: str
    training_hyperparams: dict[str, Any] = field(default_factory=dict)
    eval_metrics: dict[str, float] = field(default_factory=dict)
    trained_at: str = ""  # ISO 8601 时间戳
    training_device: str = ""
    framework_version: dict[str, str] = field(default_factory=dict)
    dataset_spec_path: str = ""
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        """序列化为 dict（用于写入 ``model_card.json``）。"""
        return {
            "git_sha": self.git_sha,
            "data_hash": self.data_hash,
            "training_hyperparams": dict(self.training_hyperparams),
            "eval_metrics": dict(self.eval_metrics),
            "trained_at": self.trained_at,
            "training_device": self.training_device,
            "framework_version": dict(self.framework_version),
            "dataset_spec_path": self.dataset_spec_path,
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ModelCard":
        """从 dict 反序列化（用于工程侧加载 ``model_card.json``）。

        容忍缺失字段（向前兼容旧模型卡），但 ``git_sha`` 与 ``data_hash`` 必须存在。
        """
        if "git_sha" not in data or "data_hash" not in data:
            raise ValueError(
                "ModelCard.from_dict: git_sha 与 data_hash 字段必须存在，"
                "保证模型可溯源（D-2 学术诚信硬约束）"
            )
        return cls(
            git_sha=str(data["git_sha"]),
            data_hash=str(data["data_hash"]),
            training_hyperparams=dict(data.get("training_hyperparams", {})),
            eval_metrics=dict(data.get("eval_metrics", {})),
            trained_at=str(data.get("trained_at", "")),
            training_device=str(data.get("training_device", "")),
            framework_version=dict(data.get("framework_version", {})),
            dataset_spec_path=str(data.get("dataset_spec_path", "")),
            notes=str(data.get("notes", "")),
        )


__all__ = ["ModelCard"]
