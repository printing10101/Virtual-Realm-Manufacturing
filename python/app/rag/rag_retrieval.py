"""
RAG 检索规则引擎

实现多源知识库的分层检索策略：
1. 本地项目数据（Bosch CNC）优先
2. Uniwear 数据集其次
3. ChromaDB 向量库最终检索
"""

import logging
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class QueryIntent(Enum):
    MATERIAL_WEAR = "material_wear"
    CUTTING_PARAMS = "cutting_params"
    VIBRATION_WEAR = "vibration_wear"
    MATERIAL_COMPARE = "material_compare"
    CROSS_SOURCE = "cross_source"
    GENERAL = "general"


@dataclass
class RetrievalRule:
    intent: QueryIntent
    source_filters: list[str] = field(default_factory=list)
    metadata_filters: dict = field(default_factory=dict)
    keyword_boost: dict = field(default_factory=dict)
    n_results: int = 5
    priority: int = 1


RETRIEVAL_RULES: dict[QueryIntent, RetrievalRule] = {
    QueryIntent.MATERIAL_WEAR: RetrievalRule(
        intent=QueryIntent.MATERIAL_WEAR,
        source_filters=["uniwear-nuaa", "uniwear-phm2010", "uniwear"],
        metadata_filters={"category": "tool_wear"},
        keyword_boost={
            "TC4": 3.0,
            "钛合金": 3.0,
            "Ti-6Al-4V": 3.0,
            "HRC52": 3.0,
            "不锈钢": 2.5,
            "磨损": 2.0,
            "刀具": 1.5,
        },
        n_results=8,
        priority=1,
    ),
    QueryIntent.CUTTING_PARAMS: RetrievalRule(
        intent=QueryIntent.CUTTING_PARAMS,
        source_filters=["uniwear-phm2010", "bosch_cnc"],
        metadata_filters={"category": "tool_wear"},
        keyword_boost={
            "HRC52": 4.0,
            "不锈钢": 4.0,
            "切削参数": 3.0,
            "切削速度": 2.5,
            "进给量": 2.5,
            "切削深度": 2.5,
            "PHM2010": 3.0,
        },
        n_results=8,
        priority=1,
    ),
    QueryIntent.VIBRATION_WEAR: RetrievalRule(
        intent=QueryIntent.VIBRATION_WEAR,
        source_filters=["uniwear-nuaa", "uniwear-phm2010", "bosch_cnc", "uniwear"],
        metadata_filters={"has_vibration": True},
        keyword_boost={
            "振动": 4.0,
            "RMS": 3.0,
            "频域": 2.5,
            "声发射": 2.5,
            "磨损关联": 3.0,
            "信号分析": 2.0,
            "监测": 1.5,
        },
        n_results=10,
        priority=1,
    ),
    QueryIntent.MATERIAL_COMPARE: RetrievalRule(
        intent=QueryIntent.MATERIAL_COMPARE,
        source_filters=["uniwear", "uniwear-nuaa", "uniwear-phm2010"],
        metadata_filters={},
        keyword_boost={
            "TC4": 3.0,
            "HRC52": 3.0,
            "钛合金": 3.0,
            "不锈钢": 3.0,
            "对比": 2.5,
            "材料差异": 2.5,
            "工艺对比": 2.5,
        },
        n_results=10,
        priority=1,
    ),
    QueryIntent.CROSS_SOURCE: RetrievalRule(
        intent=QueryIntent.CROSS_SOURCE,
        source_filters=["bosch_cnc", "uniwear-nuaa", "uniwear-phm2010", "cross_source"],
        metadata_filters={},
        keyword_boost={
            "Bosch": 3.0,
            "Uniwear": 3.0,
            "多源": 3.0,
            "对比": 2.5,
            "交叉验证": 3.0,
            "联合分析": 2.5,
        },
        n_results=10,
        priority=1,
    ),
    QueryIntent.GENERAL: RetrievalRule(
        intent=QueryIntent.GENERAL,
        source_filters=[],
        metadata_filters={},
        keyword_boost={
            "刀具": 1.5,
            "磨损": 1.5,
            "加工": 1.2,
            "工艺": 1.2,
        },
        n_results=5,
        priority=3,
    ),
}

INTENT_KEYWORDS = {
    QueryIntent.MATERIAL_WEAR: [
        "TC4",
        "Ti-6Al-4V",
        "钛合金",
        "titanium",
        "HRC52",
        "不锈钢加工磨损",
        "磨损特征",
        "NUAA",
        "PHM2010",
    ],
    QueryIntent.CUTTING_PARAMS: [
        "HRC52",
        "不锈钢",
        "切削参数",
        "切削速度",
        "进给量",
        "背吃刀量",
        "转速",
        "PHM2010",
        "参数建议",
        "推荐参数",
    ],
    QueryIntent.VIBRATION_WEAR: [
        "振动",
        "vibration",
        "RMS",
        "声发射",
        "acoustic",
        "信号",
        "频域",
        "频谱",
        "振动与磨损",
        "磨损关联",
        "监测",
    ],
    QueryIntent.MATERIAL_COMPARE: [
        "多材料",
        "对比",
        "比较",
        "TC4",
        "HRC52",
        "钛合金",
        "不锈钢",
        "工艺对比",
        "材料差异",
        "不同材料",
    ],
    QueryIntent.CROSS_SOURCE: [
        "Bosch",
        "Uniwear",
        "多源",
        "对比",
        "交叉验证",
        "联合",
        "标定",
        "两个数据集",
        "不同数据源",
    ],
}


class RagRetrievalEngine:
    """RAG 检索规则引擎

    根据用户查询意图，自动选择检索策略，按优先级分层检索
    """

    def __init__(self, knowledge_base):
        self.kb = knowledge_base
        self.rules = RETRIEVAL_RULES

    def detect_intent(self, query: str) -> QueryIntent:
        query_lower = query.lower()

        scored_intents: dict[QueryIntent, int] = {}
        for intent, keywords in INTENT_KEYWORDS.items():
            score = sum(1 for kw in keywords if kw.lower() in query_lower)
            if score > 0:
                scored_intents[intent] = score

        if not scored_intents:
            return QueryIntent.GENERAL

        return max(scored_intents, key=scored_intents.get)

    def retrieve(
        self,
        query: str,
        intent: QueryIntent | None = None,
        n_results: int = 5,
        override_source: str | None = None,
    ) -> dict:
        if intent is None:
            intent = self.detect_intent(query)

        rule = self.rules.get(intent, self.rules[QueryIntent.GENERAL])
        actual_n = rule.n_results or n_results

        if override_source:
            rule.source_filters = [override_source]

        results: list[dict] = []

        if rule.source_filters:
            for source in rule.source_filters:
                try:
                    source_results = self._query_source(
                        query=query,
                        source=source,
                        n_results=actual_n,
                    )
                    for r in source_results:
                        r["_retrieval_source_filter"] = source
                    results.extend(source_results)
                except Exception as e:
                    logger.warning("Source query failed for %s: %s", source, e)

        if not results or len(results) < 3:
            fallback = self._query_general(query, n_results=actual_n)
            for r in fallback:
                r["_retrieval_source_filter"] = "fallback"
            results.extend(fallback)

        deduplicated = self._deduplicate(results)[:actual_n]
        reranked = self._rerank_by_keywords(deduplicated, query, rule.keyword_boost)

        return {
            "query": query,
            "detected_intent": intent.value,
            "rule_priority": rule.priority,
            "source_filters_applied": rule.source_filters,
            "total_found": len(results),
            "results_returned": len(reranked),
            "results": reranked,
        }

    def retrieve_by_material(
        self, material: str, query: str, n_results: int = 5
    ) -> dict:
        if material.upper() == "TC4" or "钛" in material:
            intent = QueryIntent.MATERIAL_WEAR
            override = "uniwear-nuaa"
        elif "HRC52" in material.upper() or "不锈钢" in material:
            intent = QueryIntent.CUTTING_PARAMS
            override = "uniwear-phm2010"
        else:
            intent = QueryIntent.GENERAL
            override = None

        return self.retrieve(
            query=query, intent=intent, n_results=n_results, override_source=override
        )

    def retrieve_by_signal_type(
        self, signal_type: str, query: str, n_results: int = 5
    ) -> dict:
        if "vibration" in signal_type.lower() or "振动" in signal_type:
            intent = QueryIntent.VIBRATION_WEAR
        else:
            intent = QueryIntent.GENERAL

        return self.retrieve(query=query, intent=intent, n_results=n_results)

    def retrieve_cross_source(
        self,
        query: str,
        sources: list[str] | None = None,
        n_results: int = 10,
    ) -> dict:
        if sources is None:
            sources = ["bosch_cnc", "uniwear-nuaa", "uniwear-phm2010"]

        all_results: list[dict] = []
        for source in sources:
            try:
                source_results = self._query_source(
                    query=query, source=source, n_results=n_results
                )
                for r in source_results:
                    r["_retrieval_source_filter"] = source
                all_results.extend(source_results)
            except Exception as e:
                logger.warning("Cross-source query failed for %s: %s", source, e)

        deduplicated = self._deduplicate(all_results)[:n_results]

        return {
            "query": query,
            "sources_queried": sources,
            "total_found": len(all_results),
            "results_returned": len(deduplicated),
            "results": deduplicated,
        }

    def _query_source(self, query: str, source: str, n_results: int) -> list[dict]:
        try:
            raw = self.kb.query_by_source(
                source=source, query=query, n_results=n_results
            )
        except Exception:
            return self._query_general(query, n_results)

        results: list[dict] = []
        if raw.get("documents") and raw["documents"][0]:
            for i, doc in enumerate(raw["documents"][0]):
                item = {"document": doc}
                if raw.get("metadatas") and raw["metadatas"][0]:
                    item["metadata"] = (
                        raw["metadatas"][0][i] if i < len(raw["metadatas"][0]) else {}
                    )
                if raw.get("distances") and raw["distances"][0]:
                    item["distance"] = (
                        raw["distances"][0][i] if i < len(raw["distances"][0]) else None
                    )
                if raw.get("ids") and raw["ids"][0]:
                    item["id"] = raw["ids"][0][i] if i < len(raw["ids"][0]) else None
                results.append(item)
        return results

    def _query_general(self, query: str, n_results: int = 5) -> list[dict]:
        try:
            raw = self.kb.query(query_text=query, n_results=n_results)
        except Exception:
            return []

        results: list[dict] = []
        if raw.get("documents") and raw["documents"][0]:
            for i, doc in enumerate(raw["documents"][0]):
                item = {"document": doc}
                if raw.get("metadatas") and raw["metadatas"][0]:
                    item["metadata"] = (
                        raw["metadatas"][0][i] if i < len(raw["metadatas"][0]) else {}
                    )
                if raw.get("distances") and raw["distances"][0]:
                    item["distance"] = (
                        raw["distances"][0][i] if i < len(raw["distances"][0]) else None
                    )
                if raw.get("ids") and raw["ids"][0]:
                    item["id"] = raw["ids"][0][i] if i < len(raw["ids"][0]) else None
                results.append(item)
        return results

    @staticmethod
    def _deduplicate(results: list[dict]) -> list[dict]:
        seen: set = set()
        unique: list[dict] = []
        for r in results:
            key = r.get("id") or r.get("document", "")[:100]
            if key not in seen:
                seen.add(key)
                unique.append(r)
        return unique

    @staticmethod
    def _rerank_by_keywords(
        results: list[dict],
        query: str,
        keyword_boost: dict,
    ) -> list[dict]:
        query_lower = query.lower()
        scored: list[tuple[dict, float]] = []

        for r in results:
            distance = r.get("distance", 1.0) or 1.0
            semantic_score = 1.0 - min(distance, 1.0)
            score = semantic_score
            doc = r.get("document", "").lower()
            meta = r.get("metadata", {})

            for kw, boost in keyword_boost.items():
                if kw.lower() in query_lower:
                    if kw.lower() in doc:
                        score += boost * 0.05
                    meta_str = str(meta).lower()
                    if kw.lower() in meta_str:
                        score += boost * 0.03

            scored.append((r, score))

        scored.sort(key=lambda x: x[1], reverse=True)
        return [item for item, _ in scored]
