"""FastAPI 依赖注入基础设施.

集中管理应用中可复用的"单例式"资源依赖（数据库会话、Redis 客户端、
向量存储、嵌入服务、KnowledgeBase 等），以替代原 ``global _`` 单例模式。

设计原则：
1. **线程安全**：所有依赖工厂在并发请求下安全；底层资源构造仍由各自
   模块的 ``lru_cache`` / 锁机制保证（见各资源模块）。
2. **作用域**：默认使用 FastAPI 的"请求级"缓存（``use_cache=True``）；
   对真正需要应用级单例的资源，工厂内部仍返回单例实例。
3. **优雅降级**：保留原模块对"未配置 / 连接失败"等情况的降级逻辑，
   调用方拿到的可能是 ``None``（由各资源自己决定），与重构前行为一致。
4. **可测试**：每个依赖都是纯函数，可在测试中通过 ``app.dependency_overrides``
   注入 mock。

依赖项：
- :func:`get_db` - 异步数据库会话
- :func:`get_db_sessionmaker` - 异步 sessionmaker
- :func:`get_db_engine` - 异步 SQLAlchemy 引擎
- :func:`get_redis` - Redis 异步客户端
- :func:`get_vector_store` - ChromaDB 向量存储
- :func:`get_embedding_service` - 嵌入服务
- :func:`get_embedding_space` - 统一嵌入空间
- :func:`get_knowledge_base` - RAG 知识库
- :func:`get_user_store` - 用户存储
- :func:`get_resolver` - 工作空间解析器
- :func:`get_ring_log_buffer` - 环形日志缓冲
- :func:`get_rule_db` - 规则数据库
- :func:`get_token_ban_list` - JWT 撤销列表
- :func:`get_step_cache` - STEP 缓存
- :func:`get_persistence` / :func:`get_recovery` - 智能体状态管理

用法::

    from fastapi import Depends
    from app.dependencies import get_db, get_redis, get_vector_store

    @router.get("/items")
    async def list_items(
        session: AsyncSession = Depends(get_db),
        redis: Any = Depends(get_redis),
    ):
        ...
"""

from __future__ import annotations

from typing import Any, Optional

# 重新导出各依赖函数，保持与重构前调用 ``get_xxx()`` 兼容
from app.database.connection import (  # noqa: F401
    get_db,
    get_db_engine,
    get_db_sessionmaker,
)
from app.database.rule_db import get_rule_db  # noqa: F401
from app.rag.vector_store import get_vector_store  # noqa: F401
from app.services.redis_client import get_redis  # noqa: F401
from app.rag.embeddings import get_embedding_service  # noqa: F401
from app.ai.unified_embedding.space import get_embedding_space  # noqa: F401
from app.rag.knowledge_base import get_knowledge_base  # noqa: F401
from app.models.user import get_user_store  # noqa: F401
from app.workspace.workspace import get_resolver  # noqa: F401
from app.utils.ring_buffer import get_ring_log_buffer  # noqa: F401
from app.auth.security import get_token_ban_list  # noqa: F401
from app.step_import.step_cache import get_step_cache  # noqa: F401
from app.api.v1.agent_state import (  # noqa: F401
    get_persistence,
    get_recovery,
)


# 显式 ``__all__`` 便于静态检查
__all__ = [
    "get_db",
    "get_db_engine",
    "get_db_sessionmaker",
    "get_redis",
    "get_vector_store",
    "get_embedding_service",
    "get_embedding_space",
    "get_knowledge_base",
    "get_user_store",
    "get_resolver",
    "get_ring_log_buffer",
    "get_rule_db",
    "get_token_ban_list",
    "get_step_cache",
    "get_persistence",
    "get_recovery",
]


# 类型别名（仅用于类型注解，运行时无开销）
RedisDependency = Optional[Any]
VectorStoreDependency = Any
EmbeddingServiceDependency = Any
KnowledgeBaseDependency = Any
