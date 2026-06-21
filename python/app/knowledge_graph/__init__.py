"""知识图谱存储层（M1.2）

封装 NetworkX 内存图模型，并提供与 PostgreSQL 数据库的双向同步能力。

模块划分：
    - :mod:`app.knowledge_graph.graph_store`
        高层图存储门面，封装节点 / 关系的 CRUD 与查询 API。
    - :mod:`app.knowledge_graph.persistence`
        内存图 ↔ PostgreSQL 同步逻辑（自定义序列化）。
    - :mod:`app.knowledge_graph.repository`
        数据访问层（Repository 模式），承担节点 / 关系表读写。
    - :mod:`app.knowledge_graph.models`
        SQLAlchemy ORM 模型（kg_nodes / kg_edges）。

设计目标（"先简单后扩展"）：
    - 节点 ID 统一为字符串，遵循 ``<type>-<slug>`` 格式。
    - 属性数据使用 JSONB 存储，避免频繁 ALTER TABLE。
    - 不依赖 NetworkX 自带持久化（其不支持事务）。
    - 提供同步 API，便于 pytest / 任务脚本直接调用。
"""

from app.knowledge_graph.graph_store import GraphStore
from app.knowledge_graph.models import Base, KGEdge, KGNode
from app.knowledge_graph.persistence import GraphPersistence
from app.knowledge_graph.query_api import KnowledgeGraphQueryAPI
from app.knowledge_graph.repository import KnowledgeGraphRepository
from app.knowledge_graph.material_tool_graph import MaterialToolGraph, ProcessRecommendation

__all__ = [
    "GraphStore",
    "KnowledgeGraphQueryAPI",
    "KnowledgeGraphRepository",
    "GraphPersistence",
    "MaterialToolGraph",
    "ProcessRecommendation",
    "Base",
    "KGNode",
    "KGEdge",
]
