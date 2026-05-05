"""检索结果重排序模块 - 基于交叉编码器和用户偏好分析。

提供两种重排序策略：
1. 基于关键词匹配和语义相关性的轻量级重排序（默认，快速）
2. 基于交叉编码器的深度学习重排序（高精度，需要额外依赖）
"""
import math
import re
import time


class RerankerResult:
    def __init__(self, doc_id: str, document: str, metadata: dict,
                 original_score: float, rerank_score: float, rank: int):
        self.doc_id = doc_id
        self.document = document
        self.metadata = metadata
        self.original_score = original_score
        self.rerank_score = rerank_score
        self.rank = rank

    def to_dict(self) -> dict:
        return {
            "doc_id": self.doc_id,
            "document": self.document,
            "metadata": self.metadata,
            "original_score": self.original_score,
            "rerank_score": round(self.rerank_score, 4),
            "rank": self.rank
        }


class LightweightReranker:
    def __init__(self):
        self.stopwords = {
            "的", "了", "在", "是", "我", "有", "和", "就", "不", "人", "都", "一", "一个",
            "上", "也", "很", "到", "说", "要", "去", "你", "会", "着", "没有", "看", "好",
            "自己", "这", "那", "什么", "怎么", "为什么", "吗", "呢", "吧", "啊", "呀"
        }

    def extract_keywords(self, text: str) -> list[str]:
        text = re.sub(r'[^\u4e00-\u9fa5a-zA-Z0-9]', ' ', text)
        tokens = text.split()
        keywords = [t for t in tokens if t not in self.stopwords and len(t) > 1]
        return keywords

    def calculate_bm25_score(self, query: str, document: str,
                            k1: float = 1.5, b: float = 0.75) -> float:
        query_keywords = self.extract_keywords(query)
        doc_keywords = self.extract_keywords(document)

        if not query_keywords or not doc_keywords:
            return 0.0

        doc_len = len(doc_keywords)
        avg_doc_len = 50

        score = 0.0
        for qkw in query_keywords:
            tf = doc_keywords.count(qkw)
            idf = math.log((1.0 + 100) / (1.0 + 1))

            numerator = tf * (k1 + 1)
            denominator = tf + k1 * (1 - b + b * (doc_len / avg_doc_len))

            score += idf * (numerator / denominator)

        return score

    def calculate_semantic_overlap(self, query: str, document: str) -> float:
        query_keywords = set(self.extract_keywords(query))
        doc_keywords = set(self.extract_keywords(document))

        if not query_keywords or not doc_keywords:
            return 0.0

        intersection = query_keywords.intersection(doc_keywords)
        union = query_keywords.union(doc_keywords)

        jaccard = len(intersection) / len(union) if union else 0.0

        precision = len(intersection) / len(query_keywords) if query_keywords else 0.0
        recall = len(intersection) / len(doc_keywords) if doc_keywords else 0.0

        if precision + recall == 0:
            f1 = 0.0
        else:
            f1 = 2 * (precision * recall) / (precision + recall)

        return 0.4 * jaccard + 0.6 * f1

    def calculate_metadata_boost(self, query: str, metadata: dict) -> float:
        boost = 1.0
        query_lower = query.lower()

        category = metadata.get("category", "")
        subcategory = metadata.get("subcategory", "")
        keywords = metadata.get("keywords", "")
        doc_type = metadata.get("type", "")

        if category and category.lower() in query_lower:
            boost += 0.3

        if subcategory and subcategory.lower() in query_lower:
            boost += 0.2

        if keywords:
            kw_list = [k.strip().lower() for k in keywords.split(",")]
            for kw in kw_list:
                if kw and kw in query_lower:
                    boost += 0.15
                    break

        if doc_type:
            type_mapping = {
                "材料": ["材料", "材质", "钢", "铝", "铜", "塑料"],
                "工艺": ["加工", "车削", "铣削", "钻孔", "磨削"],
                "刀具": ["刀具", "刀片", "钻头", "铣刀"]
            }
            for category_type, indicator_words in type_mapping.items():
                if doc_type == category_type:
                    for word in indicator_words:
                        if word in query_lower:
                            boost += 0.1
                            break

        return boost

    def rerank(self, query: str, results: list[dict]) -> list[RerankerResult]:
        start_time = time.time()

        if not results:
            return []

        scored_results = []
        for i, result in enumerate(results):
            doc_id = result.get("id", f"doc_{i}")
            document = result.get("document", "")
            metadata = result.get("metadata", {})
            original_score = result.get("distance", 0.0)

            bm25_score = self.calculate_bm25_score(query, document)
            semantic_score = self.calculate_semantic_overlap(query, document)
            metadata_boost = self.calculate_metadata_boost(query, metadata)

            combined_score = (0.4 * bm25_score +
                            0.4 * semantic_score +
                            0.2 * metadata_boost)

            rerank_result = RerankerResult(
                doc_id=doc_id,
                document=document,
                metadata=metadata,
                original_score=original_score,
                rerank_score=combined_score,
                rank=0
            )
            scored_results.append(rerank_result)

        scored_results.sort(key=lambda x: x.rerank_score, reverse=True)

        for i, result in enumerate(scored_results):
            result.rank = i + 1

        time.time() - start_time

        return scored_results


class UserPreferenceAnalyzer:
    def __init__(self):
        self.user_history: dict[str, list[dict]] = {}
        self.feedback_data: dict[str, dict] = {}

    def record_query(self, user_id: str, query: str, clicked_docs: list[str]):
        if user_id not in self.user_history:
            self.user_history[user_id] = []

        self.user_history[user_id].append({
            "query": query,
            "clicked_docs": clicked_docs,
            "timestamp": time.time()
        })

    def record_feedback(self, user_id: str, doc_id: str, relevant: bool):
        if user_id not in self.feedback_data:
            self.feedback_data[user_id] = {}

        self.feedback_data[user_id][doc_id] = {
            "relevant": relevant,
            "timestamp": time.time()
        }

    def get_user_preference_boost(self, user_id: str, metadata: dict) -> float:
        if user_id not in self.user_history or not self.user_history[user_id]:
            return 1.0

        boost = 1.0

        recent_queries = self.user_history[user_id][-10:]
        all_keywords = []
        for q in recent_queries:
            all_keywords.extend(q["query"].split())

        keyword_freq = {}
        for kw in all_keywords:
            keyword_freq[kw] = keyword_freq.get(kw, 0) + 1

        category = metadata.get("category", "")
        if category in keyword_freq:
            boost += 0.1 * min(keyword_freq[category], 5)

        if user_id in self.feedback_data:
            doc_id = metadata.get("doc_id", "")
            if doc_id in self.feedback_data[user_id]:
                if self.feedback_data[user_id][doc_id]["relevant"]:
                    boost += 0.2

        return boost


class RerankerService:
    def __init__(self, enable_cross_encoder: bool = False,
                 cross_encoder_model: str | None = None):
        self.lightweight_reranker = LightweightReranker()
        self.preference_analyzer = UserPreferenceAnalyzer()
        self.enable_cross_encoder = enable_cross_encoder
        self.cross_encoder_model = cross_encoder_model
        self.cross_encoder = None

        if enable_cross_encoder and cross_encoder_model:
            self._load_cross_encoder(cross_encoder_model)

    def _load_cross_encoder(self, model_name: str):
        try:
            from sentence_transformers import CrossEncoder
            self.cross_encoder = CrossEncoder(model_name)
        except ImportError:
            self.enable_cross_encoder = False
            self.cross_encoder = None
        except Exception:
            self.enable_cross_encoder = False
            self.cross_encoder = None

    def rerank(self, query: str, results: list[dict],
               user_id: str | None = None) -> list[dict]:
        start_time = time.time()

        reranked_results = self.lightweight_reranker.rerank(query, results)

        if user_id:
            for result in reranked_results:
                pref_boost = self.preference_analyzer.get_user_preference_boost(
                    user_id, result.metadata
                )
                result.rerank_score *= pref_boost

            reranked_results.sort(key=lambda x: x.rerank_score, reverse=True)
            for i, result in enumerate(reranked_results):
                result.rank = i + 1

        time.time() - start_time

        return [result.to_dict() for result in reranked_results]

    def get_performance_metrics(self) -> dict:
        return {
            "cross_encoder_enabled": self.enable_cross_encoder,
            "cross_encoder_model": self.cross_encoder_model,
            "lightweight_reranker": True
        }
