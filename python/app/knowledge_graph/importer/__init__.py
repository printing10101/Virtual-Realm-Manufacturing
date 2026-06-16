"""知识图谱 JSON 导入工具链（M1.3）

模块划分：
    - :mod:`app.knowledge_graph.importer.json_importer`
        主导入逻辑：包含 4 个专用 ``import_<file>`` 函数与 ``import_all``
        协调器；处理 JSON → 节点 / 关系 → 内存图 → 数据库的完整链路。
    - :mod:`app.knowledge_graph.importer.rule_parser`
        规则解析模块：解析 ``process_rules.json`` 中的 ``IF-THEN`` 语义，
        抽取涉及的 Feature 实体并生成 Process 与 Feature / Tool 之间的关系。

设计目标：
    - 4 个 JSON 文件独立导入：每个文件有专属的 ``import_<file>`` 函数，
      实体映射规则相互独立、互不耦合。
    - 差异化去重：Material 基于 ``name``、Tool 基于 ``series+diameter_mm``、
      Machine 基于 ``id``、Process 基于 ``id``。
    - 事务原子性 + 至少 3 次失败重试：保证导入的可靠性。
    - 不依赖通用 JSON 解析器：所有解析逻辑针对具体文件结构定制。
"""

from app.knowledge_graph.importer.json_importer import (
    ImportReport,
    ImportStats,
    import_all,
    import_machines,
    import_materials,
    import_process_rules,
    import_tools,
    load_graph_from_repository,
)
from app.knowledge_graph.importer.rule_parser import (
    ParsedRule,
    RuleParser,
    parse_process_rules,
)

__all__ = [
    # 主入口
    "import_all",
    "import_materials",
    "import_tools",
    "import_machines",
    "import_process_rules",
    "load_graph_from_repository",
    # 数据类
    "ImportReport",
    "ImportStats",
    # 规则解析
    "RuleParser",
    "parse_process_rules",
    "ParsedRule",
]
