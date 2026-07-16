"""``shared`` —— 工程侧与科研侧共享的薄契约层。

设计目标（见 ``docs/superpowers/specs/2026-07-15-research-engineering-decoupling-design.md``）：

- **零重依赖**：仅允许 ``stdlib`` + ``typing_extensions``，严禁 torch / numpy / pydantic / scikit-learn
- **唯一共享入口**：科研与工程两侧共享代码的唯一入口，避免 schema 漂移
- **契约即文档**：所有类型/常量/协议均带 docstring，工程侧与科研侧双向 ``pip install -e .``
- **ADR 治理**：契约变更需走 ADR 评审（与 ADR-005 一致）

子包结构：
- ``shared.lnn``       颤振预测契约（protocols / artifact / model_card / types）
- ``shared.data``      数据契约（ChatterParams / ChatterReport / DatasetSpec）
- ``shared.constants`` 工程硬约束常量（materials / precision / gates）

使用示例::

    from shared.lnn.protocols import ChatterPredictorProtocol
    from shared.lnn.types import FeatureChatterResult
    from shared.data.contracts import ChatterParams
    from shared.constants.materials import DEFAULT_CONFIDENCE

版本号与主项目 ``VERSION`` 文件保持一致，由 ADR 评审控制变更。
"""

__all__ = ["__version__"]

__version__ = "0.1.0"
