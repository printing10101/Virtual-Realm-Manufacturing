"""``shared.data`` —— 数据契约子包。

子模块：
- ``contracts`` ``ChatterParams`` / ``ChatterReport`` / ``MaterialParams`` / ``CuttingParams`` / ``ToolParams`` / ``MachineParams``
- ``dataset``   ``DatasetSpec``（数据集 schema / 版本 / hash / 路径）

设计动机：阶段 4 输出 ``ChatterParams``、阶段 5 输出 ``ChatterReport``、阶段 6 消费 ``ChatterReport``，
跨阶段共享的数据结构必须集中在此处定义，避免任一阶段单边修改 schema 导致下游链路断裂。
"""

from shared.data.contracts import (
    ChatterParams,
    ChatterReport,
    CuttingParams,
    MachineParams,
    MaterialParams,
    ToolParams,
)
from shared.data.dataset import DatasetSpec

__all__ = [
    "ChatterParams",
    "ChatterReport",
    "MaterialParams",
    "CuttingParams",
    "ToolParams",
    "MachineParams",
    "DatasetSpec",
]
