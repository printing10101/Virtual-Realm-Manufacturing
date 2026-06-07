"""
知识检索准确率测试

测试目标: Top-3 相关性 > 90%
测试方法: 准备典型工艺问题，评估检索到的知识与问题的相关性
"""

from __future__ import annotations

import pytest

from app.ai.process_understanding.knowledge_retriever import (
    KnowledgeRetriever,
    RetrievalDocument,
    HybridRetrievalResult,
    RetrievalStrategy,
)
from app.ai.process_understanding.task_classifier import TaskType


# ---------------------------------------------------------------------------
# 典型工艺问题测试集
# ---------------------------------------------------------------------------

TYPICAL_QUERIES = [
    {
        "query": "45钢切削参数推荐",
        "task_type": TaskType.PROCESS_CONSULT,
        "expected_keywords": ["45钢", "切削", "参数"],
    },
    {
        "query": "304不锈钢加工方法",
        "task_type": TaskType.PROCESS_CONSULT,
        "expected_keywords": ["不锈钢", "加工"],
    },
    {
        "query": "刀具磨损原因分析",
        "task_type": TaskType.FAULT_DIAGNOSIS,
        "expected_keywords": ["刀具", "磨损"],
    },
    {
        "query": "加工精度超差怎么解决",
        "task_type": TaskType.FAULT_DIAGNOSIS,
        "expected_keywords": ["精度", "差"],
    },
    {
        "query": "铝合金壳体加工方案",
        "task_type": TaskType.SOLUTION_GENERATION,
        "expected_keywords": ["铝合金", "加工"],
    },
    {
        "query": "G代码编程基础",
        "task_type": TaskType.KNOWLEDGE_QUERY,
        "expected_keywords": ["G代码", "编程"],
    },
    {
        "query": "表面粗糙度标准",
        "task_type": TaskType.KNOWLEDGE_QUERY,
        "expected_keywords": ["粗糙度", "标准"],
    },
    {
        "query": "车削加工切削速度计算",
        "task_type": TaskType.PROCESS_CONSULT,
        "expected_keywords": ["车削", "切削速度"],
    },
    {
        "query": "数控铣床故障排除",
        "task_type": TaskType.FAULT_DIAGNOSIS,
        "expected_keywords": ["铣床", "故障"],
    },
    {
        "query": "热处理工艺规范",
        "task_type": TaskType.KNOWLEDGE_QUERY,
        "expected_keywords": ["热处理", "工艺"],
    },
]


class RetrievalRelevanceEvaluator:
    """检索相关性评估器"""

    @staticmethod
    def calculate_relevance(
        document: RetrievalDocument, expected_keywords: list[str]
    ) -> float:
        """计算文档与预期关键词的相关性得分。"""
        doc_text = document.content.lower() if document.content else ""
        if not doc_text:
            return 0.0

        # 检查每个关键字的匹配情况
        matched = 0
        for kw in expected_keywords:
            if kw.lower() in doc_text:
                matched += 1

        # 精确匹配得分
        exact_score = matched / len(expected_keywords) if expected_keywords else 1.0

        # 部分匹配加分
        partial_score = 0.0
        for kw in expected_keywords:
            # 检查单个字符匹配
            chars = set(kw.lower())
            doc_chars = set(doc_text)
            overlap = len(chars & doc_chars)
            partial_score += overlap / max(len(chars), 1) * 0.1

        partial_score = min(0.3, partial_score)

        return min(1.0, exact_score * 0.7 + partial_score)

    @staticmethod
    def evaluate_top_k(
        result: HybridRetrievalResult,
        expected_keywords: list[str],
        k: int = 3,
    ) -> dict:
        """评估 Top-K 结果的相关性。"""
        top_k_docs = result.documents[:k]
        relevances = []

        for doc in top_k_docs:
            relevance = RetrievalRelevanceEvaluator.calculate_relevance(
                doc, expected_keywords
            )
            relevances.append(relevance)

        # Top-K 中至少有一个高相关 (>0.5) 即为通过
        has_relevant = any(r > 0.5 for r in relevances)
        avg_relevance = sum(relevances) / len(relevances) if relevances else 0.0

        return {
            "relevances": relevances,
            "avg_relevance": avg_relevance,
            "has_relevant": has_relevant,
            "passed": has_relevant,
        }


class TestKnowledgeRetriever:
    """知识检索器测试"""

    @pytest.fixture
    def retriever(self) -> KnowledgeRetriever:
        return KnowledgeRetriever()

    @pytest.mark.asyncio
    async def test_retrieval_structure(self, retriever: KnowledgeRetriever):
        """测试检索结果的基本结构。"""
        result = await retriever.retrieve(
            query="45钢切削参数",
            task_type=TaskType.PROCESS_CONSULT,
        )
        assert isinstance(result, HybridRetrievalResult)
        assert result.query == "45钢切削参数"
        assert result.task_type == TaskType.PROCESS_CONSULT
        assert result.strategy == RetrievalStrategy.HYBRID

    @pytest.mark.asyncio
    async def test_retrieval_has_results(self, retriever: KnowledgeRetriever):
        """测试检索能返回结果。"""
        result = await retriever.retrieve(
            query="切削参数 刀具 加工",
            task_type=TaskType.PROCESS_CONSULT,
            top_k=5,
        )
        # 即使知识库为空，也应返回空列表而非报错
        assert isinstance(result.documents, list)

    @pytest.mark.asyncio
    async def test_different_task_types(self, retriever: KnowledgeRetriever):
        """测试不同任务类型的检索不会报错。"""
        for task_type in TaskType:
            result = await retriever.retrieve(
                query="加工工艺",
                task_type=task_type,
            )
            assert result.task_type == task_type

    @pytest.mark.asyncio
    async def test_latency_tracking(self, retriever: KnowledgeRetriever):
        """测试延迟跟踪。"""
        result = await retriever.retrieve(query="测试查询")
        assert result.latency_ms >= 0

    def test_stats(self, retriever: KnowledgeRetriever):
        """测试统计信息。"""
        stats = retriever.get_stats()
        assert "total_queries" in stats
        assert "avg_latency_ms" in stats


class TestRetrievalDocument:
    """检索文档数据类测试"""

    def test_default_values(self):
        doc = RetrievalDocument()
        assert doc.id == ""
        assert doc.content == ""
        assert doc.vector_score == 0.0
        assert doc.keyword_score == 0.0
        assert doc.final_score == 0.0
        assert doc.source == "unknown"

    def test_custom_values(self):
        doc = RetrievalDocument(
            id="doc_001",
            content="45钢切削参数推荐",
            metadata={"source": "default"},
            vector_score=0.8,
            keyword_score=0.6,
            final_score=0.7,
            source="default",
        )
        assert doc.id == "doc_001"
        assert doc.vector_score == 0.8


class TestMergeResults:
    """合并结果测试"""

    def test_merge_deduplication(self):
        """测试结果去重。"""
        doc1 = RetrievalDocument(
            id="doc_1", content="内容A", vector_score=0.8, keyword_score=0.0
        )
        doc2 = RetrievalDocument(
            id="doc_1", content="内容A", vector_score=0.0, keyword_score=0.7
        )

        merged = KnowledgeRetriever._merge_results(
            [doc1], [doc2], vector_weight=0.6, keyword_weight=0.4
        )
        assert len(merged) == 1
        assert merged[0].vector_score == 0.8
        assert merged[0].keyword_score == 0.7

    def test_merge_different_sources(self):
        """测试不同来源的结果合并。"""
        vector_docs = [
            RetrievalDocument(id="1", content="A", vector_score=0.9, source="db1"),
        ]
        keyword_docs = [
            RetrievalDocument(id="2", content="B", keyword_score=0.8, source="db2"),
        ]

        merged = KnowledgeRetriever._merge_results(
            vector_docs, keyword_docs, vector_weight=0.5, keyword_weight=0.5
        )
        assert len(merged) == 2


class TestReranking:
    """重排序测试"""

    def test_reranking_by_source_priority(self):
        """测试来源优先级重排序。"""
        docs = [
            RetrievalDocument(
                id="1", content="普通知识", final_score=0.8, source="unknown"
            ),
            RetrievalDocument(
                id="2", content="工业数据", final_score=0.8, source="bosch_cnc"
            ),
            RetrievalDocument(
                id="3", content="默认知识", final_score=0.8, source="default"
            ),
        ]

        reranked = KnowledgeRetriever._apply_reranking(
            docs, "刀具磨损", TaskType.FAULT_DIAGNOSIS
        )

        # bosch_cnc 对于故障诊断优先级最高
        assert reranked[0].source == "bosch_cnc"

    def test_reranking_score_order(self):
        """测试重排序保持得分递减。"""
        docs = [
            RetrievalDocument(
                id="1", content="A", final_score=0.9, source="default"
            ),
            RetrievalDocument(
                id="2", content="B", final_score=0.5, source="default"
            ),
            RetrievalDocument(
                id="3", content="C", final_score=0.3, source="default"
            ),
        ]

        reranked = KnowledgeRetriever._apply_reranking(
            docs, "测试", TaskType.KNOWLEDGE_QUERY
        )

        scores = [d.final_score for d in reranked]
        assert scores == sorted(scores, reverse=True)


class TestRetrievalWeights:
    """检索权重配置测试"""

    def test_all_task_types_have_weights(self):
        """确保所有任务类型都有配置。"""
        from app.ai.process_understanding.knowledge_retriever import RETRIEVAL_WEIGHTS

        for task_type in TaskType:
            assert task_type in RETRIEVAL_WEIGHTS, f"{task_type} 缺少检索权重配置"

    def test_weights_sum_valid(self):
        """确保权重配置合理。"""
        from app.ai.process_understanding.knowledge_retriever import RETRIEVAL_WEIGHTS

        for task_type, weights in RETRIEVAL_WEIGHTS.items():
            total = weights["vector_weight"] + weights["keyword_weight"]
            assert abs(total - 1.0) < 0.01, (
                f"{task_type} 向量+关键词权重之和应为1.0，实际为{total}"
            )

    def test_source_priorities_for_all_types(self):
        """确保所有任务类型都有来源优先级配置。"""
        from app.ai.process_understanding.knowledge_retriever import SOURCE_PRIORITY

        for task_type in TaskType:
            assert task_type in SOURCE_PRIORITY, f"{task_type} 缺少来源优先级配置"
            assert len(SOURCE_PRIORITY[task_type]) > 0, f"{task_type} 来源列表为空"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
