"""数据集规格契约（D-2 学术诚信硬约束）。

设计原则
========
本模块定义 ``DatasetSpec``，科研侧训练时必须生成对应的 dataset_spec.json，
与 ModelCard 的 ``dataset_spec_path`` 字段关联，形成完整溯源链：

    git_sha（代码） → data_hash（数据内容） → DatasetSpec（数据规格）
        → ModelCard（训练产物元数据） → model.onnx（推理产物）

D-2 学术诚信硬约束（项目记忆）：
- 实验元数据必须用 MLflow 跟踪（log params / metrics / models）
- DatasetSpec 是 MLflow 跟踪的结构化补充，记录数据集静态属性
- 任何字段变更需走 ADR 评审

零重依赖：仅使用 stdlib（dataclasses / typing），不依赖 torch / numpy / pydantic。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class DatasetSpec:
    """数据集规格（科研侧导出，工程侧加载校验）。

    字段说明：
    - ``name``           数据集名称（如 "uniwear_a2" / "phm2010_chatter"）
    - ``version``        数据集版本号（如 "1.0.0"）
    - ``hash``           数据集内容 SHA256 hash（保证数据可复现）
    - ``schema``         数据字段规格 dict，描述每个字段的名称/类型/范围/单位
    - ``path``           数据集根目录路径（相对科研侧仓库根或绝对路径）
    - ``created_at``     数据集创建时间戳（ISO 8601 字符串）
    - ``description``    自由文本描述（如「阶段二物理残差训练集，含 6061-T6 铣削数据」）
    - ``size``           样本总数
    - ``split_info``     训练/验证/测试分割信息 dict
    - ``format``         数据格式（如 "npy" / "csv" / "parquet"）
    - ``license``        数据许可证（如 "CC-BY-4.0" / "proprietary"）

    使用方式：
        # 科研侧导出
        spec = DatasetSpec(
            name="uniwear_a2",
            version="1.0.0",
            hash="sha256:abc123...",
            schema={
                "spindle_rpm": {"type": "float", "unit": "rpm", "range": [1000, 20000]},
                "axial_depth_mm": {"type": "float", "unit": "mm", "range": [0.1, 10.0]},
            },
            path="research/datasets/uniwear_a2/",
            created_at="2026-07-15T10:00:00+08:00",
            description="阶段二物理残差训练集",
        )
        spec.to_dict()  # → JSON 序列化

        # 工程侧加载校验
        spec = DatasetSpec.from_dict(json.loads(path.read_text()))
        if spec.hash != actual_hash:
            raise ValueError("数据集 hash 不匹配，可能被篡改")
    """

    name: str
    version: str
    hash: str  # SHA256 hash，格式 "sha256:<hex>"
    schema: dict[str, dict[str, Any]] = field(default_factory=dict)
    path: str = ""
    created_at: str = ""  # ISO 8601 时间戳
    description: str = ""
    size: int = 0
    split_info: dict[str, int] = field(
        default_factory=lambda: {"train": 0, "val": 0, "test": 0}
    )
    format: str = ""
    license: str = ""

    def __post_init__(self) -> None:
        """D-2 学术诚信硬约束校验。

        name / version / hash 三个字段必须填写，
        否则实验无法复现，工程侧加载时也会拒绝。
        """
        if not self.name:
            raise ValueError("DatasetSpec.name 不能为空（D-2 学术诚信硬约束）")
        if not self.version:
            raise ValueError("DatasetSpec.version 不能为空（D-2 学术诚信硬约束）")
        if not self.hash:
            raise ValueError("DatasetSpec.hash 不能为空（D-2 学术诚信硬约束：保证数据可复现）")
        if not self.hash.startswith("sha256:"):
            raise ValueError(
                f"DatasetSpec.hash 必须以 'sha256:' 前缀开头，当前值: {self.hash[:20]}..."
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "hash": self.hash,
            "schema": {k: dict(v) for k, v in self.schema.items()},
            "path": self.path,
            "created_at": self.created_at,
            "description": self.description,
            "size": self.size,
            "split_info": dict(self.split_info),
            "format": self.format,
            "license": self.license,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DatasetSpec":
        """从 dict 反序列化（加载 dataset_spec.json 时使用）。

        与 ModelCard.from_dict 一致，强制校验 D-2 硬约束字段。
        """
        return cls(
            name=str(data.get("name", "")),
            version=str(data.get("version", "")),
            hash=str(data.get("hash", "")),
            schema=dict(data.get("schema", {})),
            path=str(data.get("path", "")),
            created_at=str(data.get("created_at", "")),
            description=str(data.get("description", "")),
            size=int(data.get("size", 0)),
            split_info=dict(data.get("split_info", {"train": 0, "val": 0, "test": 0})),
            format=str(data.get("format", "")),
            license=str(data.get("license", "")),
        )
