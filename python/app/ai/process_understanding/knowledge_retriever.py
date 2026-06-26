"""
知识检索模块

实现混合检索（向量检索 + 关键词检索）+ 智能重排序。
根据任务类型动态调整检索权重和策略。
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from app.ai.process_understanding.task_classifier import TaskType

logger = logging.getLogger(__name__)


class RetrievalStrategy(Enum):
    VECTOR = "vector"
    KEYWORD = "keyword"
    HYBRID = "hybrid"


@dataclass
class RetrievalDocument:
    """检索文档"""

    id: str = ""
    content: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    vector_score: float = 0.0
    keyword_score: float = 0.0
    final_score: float = 0.0
    source: str = "unknown"


@dataclass
class HybridRetrievalResult:
    """混合检索结果"""

    query: str
    task_type: TaskType
    strategy: RetrievalStrategy
    documents: list[RetrievalDocument] = field(default_factory=list)
    total_candidates: int = 0
    latency_ms: float = 0.0


# ---------------------------------------------------------------------------
# 任务类型 -> 检索权重配置
# ---------------------------------------------------------------------------

RETRIEVAL_WEIGHTS: dict[TaskType, dict[str, float]] = {
    TaskType.PROCESS_CONSULT: {
        "vector_weight": 0.4,
        "keyword_weight": 0.6,
        "top_k": 5,
        "min_relevance": 0.3,
    },
    TaskType.FAULT_DIAGNOSIS: {
        "vector_weight": 0.5,
        "keyword_weight": 0.5,
        "top_k": 5,
        "min_relevance": 0.3,
    },
    TaskType.SOLUTION_GENERATION: {
        "vector_weight": 0.3,
        "keyword_weight": 0.7,
        "top_k": 8,
        "min_relevance": 0.2,
    },
    TaskType.KNOWLEDGE_QUERY: {
        "vector_weight": 0.6,
        "keyword_weight": 0.4,
        "top_k": 5,
        "min_relevance": 0.3,
    },
    TaskType.CHITCHAT: {
        "vector_weight": 0.5,
        "keyword_weight": 0.5,
        "top_k": 3,
        "min_relevance": 0.4,
    },
}

# 任务类型 -> 知识来源优先级
SOURCE_PRIORITY: dict[TaskType, list[str]] = {
    TaskType.PROCESS_CONSULT: ["default", "bosch_cnc", "uniwear-phm2010"],
    TaskType.FAULT_DIAGNOSIS: ["bosch_cnc", "uniwear", "uniwear-nuaa"],
    TaskType.SOLUTION_GENERATION: ["default", "bosch_cnc"],
    TaskType.KNOWLEDGE_QUERY: ["default", "bosch_cnc", "uniwear"],
    TaskType.CHITCHAT: ["default"],
}


class KnowledgeRetriever:
    """混合检索器：向量检索 + 关键词检索 + 智能重排序。

    检索策略：
    1. 向量检索：基于语义相似度从ChromaDB获取候选
    2. 关键词检索：基于TF-IDF关键词匹配
    3. 重排序：综合语义相关性、关键词匹配、知识来源权威性、时效性
    """

    def __init__(self):
        self._kb: Any = None
        self._reranker: Any = None
        self._total_queries = 0
        self._total_latency_ms = 0.0

    async def _get_knowledge_base(self) -> Any:
        if self._kb is None:
            from app.rag.knowledge_base import get_knowledge_base

            self._kb = get_knowledge_base()
        return self._kb

    def _get_reranker(self) -> Any:
        if self._reranker is None:
            from app.rag.reranker import RerankerService

            self._reranker = RerankerService()
        return self._reranker

    async def retrieve(
        self,
        query: str,
        task_type: TaskType = TaskType.KNOWLEDGE_QUERY,
        top_k: int | None = None,
    ) -> HybridRetrievalResult:
        """执行混合检索。

        Args:
            query: 检索查询文本
            task_type: 任务类型（用于调整检索权重）
            top_k: 返回文档数量上限

        Returns:
            HybridRetrievalResult 包含检索到的文档列表
        """
        start_time = time.perf_counter()
        self._total_queries += 1

        weights = RETRIEVAL_WEIGHTS.get(task_type, RETRIEVAL_WEIGHTS[TaskType.KNOWLEDGE_QUERY])
        actual_top_k = top_k or weights["top_k"]
        vector_weight = weights["vector_weight"]
        keyword_weight = weights["keyword_weight"]

        kb = await self._get_knowledge_base()

        # 1. 向量检索
        vector_docs = await self._vector_search(kb, query, task_type, actual_top_k * 2)

        # 2. 关键词检索
        keyword_docs = await self._keyword_search(kb, query, task_type, actual_top_k * 2)

        # 3. 合并与去重
        merged = self._merge_results(
            vector_docs, keyword_docs, vector_weight, keyword_weight
        )

        # 4. 重排序
        reranked = self._apply_reranking(merged, query, task_type)

        # 5. 截取 Top-K
        final_docs = reranked[:actual_top_k]

        elapsed = (time.perf_counter() - start_time) * 1000
        self._total_latency_ms += elapsed

        logger.info(
            "检索完成: query='%s', task=%s, candidates=%d, results=%d, %.1fms",
            query[:50],
            task_type.label,
            len(merged),
            len(final_docs),
            elapsed,
        )

        return HybridRetrievalResult(
            query=query,
            task_type=task_type,
            strategy=RetrievalStrategy.HYBRID,
            documents=final_docs,
            total_candidates=len(merged),
            latency_ms=elapsed,
        )

    async def _vector_search(
        self,
        kb: Any,
        query: str,
        task_type: TaskType,
        n_results: int,
    ) -> list[RetrievalDocument]:
        """执行向量语义检索。"""
        try:
            result = kb.query(query_text=query, n_results=n_results)
            documents_raw = result.get("documents", [])
            if not documents_raw:
                return []

            docs: list[RetrievalDocument] = []
            for i, doc in enumerate(documents_raw):
                doc_content = doc.get("document", "") if isinstance(doc, dict) else str(doc)
                meta = doc.get("metadata", {}) if isinstance(doc, dict) else {}
                doc_id = doc.get("id", "") if isinstance(doc, dict) else ""
                dist = doc.get("distance", 0.5) if isinstance(doc, dict) else 0.5
                vector_score = 1.0 - min(float(dist), 1.0)

                docs.append(RetrievalDocument(
                    id=str(doc_id),
                    content=doc_content,
                    metadata=meta,
                    vector_score=vector_score,
                    source=meta.get("source", "unknown"),
                ))
            return docs
        except (KeyError, ValueError, TypeError, OSError) as e:
            logger.warning("向量检索失败: %s", e, exc_info=True)
            return []

    async def _keyword_search(
        self,
        kb: Any,
        query: str,
        task_type: TaskType,
        n_results: int,
    ) -> list[RetrievalDocument]:
        """执行关键词检索。

        使用改进的TF-IDF风格评分：将查询分解为关键词，
        在每个文档中计算词频匹配度。
        """
        try:
            result = kb.query(query_text=query, n_results=n_results)
            documents_raw = result.get("documents", [])
            if not documents_raw:
                return []

            # 提取查询关键词（移除常见停用词）
            stop_words = {
                "的", "了", "是", "在", "和", "与", "或", "不", "也", "都",
                "要", "会", "可以", "需要", "能够", "应该", "如何", "怎么",
                "什么", "一个", "这个", "那个", "哪些", "为什么",
            }
            query_terms = [
                t for t in query.lower().split()
                if len(t) > 1 and t not in stop_words
            ]

            docs: list[RetrievalDocument] = []
            for doc in documents_raw:
                doc_content = doc.get("document", "") if isinstance(doc, dict) else str(doc)
                meta = doc.get("metadata", {}) if isinstance(doc, dict) else {}
                doc_id = doc.get("id", "") if isinstance(doc, dict) else ""

                # TF-IDF风格评分
                doc_lower = doc_content.lower()
                keyword_score = 0.0
                if query_terms:
                    matches = sum(1 for t in query_terms if t in doc_lower)
                    keyword_score = matches / len(query_terms)

                # 元数据匹配加分
                meta_str = str(meta).lower()
                meta_matches = sum(1 for t in query_terms if t in meta_str)
                keyword_score += meta_matches * 0.1

                keyword_score = min(1.0, keyword_score)

                docs.append(RetrievalDocument(
                    id=str(doc_id),
                    content=doc_content,
                    metadata=meta,
                    keyword_score=keyword_score,
                    source=meta.get("source", "unknown"),
                ))
            return docs
        except (KeyError, ValueError, TypeError, OSError) as e:
            logger.warning("关键词检索失败: %s", e, exc_info=True)
            return []

    @staticmethod
    def _merge_results(
        vector_docs: list[RetrievalDocument],
        keyword_docs: list[RetrievalDocument],
        vector_weight: float,
        keyword_weight: float,
    ) -> list[RetrievalDocument]:
        """合并向量检索和关键词检索结果，去重并计算综合得分。"""
        merged: dict[str, RetrievalDocument] = {}

        for doc in vector_docs:
            key = doc.id or doc.content[:100]
            merged[key] = RetrievalDocument(
                id=doc.id,
                content=doc.content,
                metadata=doc.metadata,
                vector_score=doc.vector_score,
                keyword_score=doc.keyword_score,
                source=doc.source,
            )

        for doc in keyword_docs:
            key = doc.id or doc.content[:100]
            if key in merged:
                existing = merged[key]
                existing.keyword_score = max(existing.keyword_score, doc.keyword_score)
            else:
                merged[key] = doc

        # 计算最终得分
        for doc in merged.values():
            doc.final_score = (
                doc.vector_score * vector_weight
                + doc.keyword_score * keyword_weight
            )

        return list(merged.values())

    @staticmethod
    def _apply_reranking(
        docs: list[RetrievalDocument],
        query: str,
        task_type: TaskType,
    ) -> list[RetrievalDocument]:
        """应用重排序逻辑。

        排序因子：
        1. 综合得分（向量 + 关键词）: 权重 0.5
        2. 知识来源权威性: 权重 0.3
        3. 知识时效性: 权重 0.1
        4. 查询关键词精确匹配: 权重 0.1
        """
        source_priorities = SOURCE_PRIORITY.get(task_type, ["default"])
        source_rank = {s: 1.0 - i * 0.15 for i, s in enumerate(source_priorities)}

        query_lower = query.lower()
        query_terms = set(query_lower.split())

        for doc in docs:
            # 来源权威性
            source_weight = source_rank.get(doc.source, 0.3)

            # 时效性（更新越近越好）
            updated_at = doc.metadata.get("updated_at", 0)
            recency = min(1.0, float(updated_at) / (time.time() + 1))

            # 精确关键词匹配
            doc_terms = set(doc.content.lower().split())
            exact_match = len(query_terms & doc_terms) / max(len(query_terms), 1)

            # 综合重排序得分
            doc.final_score = (
                doc.final_score * 0.5
                + source_weight * 0.3
                + recency * 0.1
                + exact_match * 0.1
            )

        docs.sort(key=lambda d: d.final_score, reverse=True)
        return docs

    def get_stats(self) -> dict[str, Any]:
        """获取检索器性能统计。"""
        return {
            "total_queries": self._total_queries,
            "avg_latency_ms": (
                self._total_latency_ms / self._total_queries
                if self._total_queries > 0
                else 0.0
            ),
        }
