"""检索效果评估体系。

包含评估数据集、准确率计算、性能目标验证和评估报告生成功能。
"""

import json
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path


@dataclass
class EvaluationQuery:
    query_id: str
    query_text: str
    expected_doc_ids: list[str]
    category: str
    difficulty: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class EvaluationResult:
    query_id: str
    query_text: str
    expected_doc_ids: list[str]
    retrieved_doc_ids: list[str]
    top_k: int
    hits: int
    precision: float
    recall: float
    f1_score: float
    mrr: float
    ndcg: float
    retrieval_time_ms: float

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class EvaluationReport:
    report_id: str
    evaluation_time: str
    total_queries: int
    top_k: int
    avg_precision: float
    avg_recall: float
    avg_f1_score: float
    avg_mrr: float
    avg_ndcg: float
    top3_accuracy: float
    top5_accuracy: float
    category_performance: dict[str, dict]
    query_results: list[dict]
    performance_target_met: bool
    target_accuracy: float

    def to_dict(self) -> dict:
        return asdict(self)


class EvaluationDataset:
    def __init__(self):
        self.queries: list[EvaluationQuery] = []
        self._load_default_dataset()

    def _load_default_dataset(self):
        self.queries = [
            EvaluationQuery(
                "EQ001",
                "45钢车削参数",
                ["KB0001", "KB0002", "ext_proc_turn_003"],
                "切削参数",
                "easy",
            ),
            EvaluationQuery(
                "EQ002",
                "不锈钢铣削刀具选择",
                ["ext_mat_ss_007", "ext_mat_ss_006"],
                "刀具选择",
                "medium",
            ),
            EvaluationQuery(
                "EQ003",
                "铝合金钻孔工艺",
                ["ext_mat_al_001", "ext_proc_drill_003"],
                "钻孔工艺",
                "easy",
            ),
            EvaluationQuery(
                "EQ004", "铜合金焊接方法", ["ext_mat_cu_010"], "焊接工艺", "medium"
            ),
            EvaluationQuery(
                "EQ005",
                "磨削烧伤防止措施",
                ["ext_proc_grind_006"],
                "磨削工艺",
                "medium",
            ),
            EvaluationQuery(
                "EQ006",
                "电火花线切割参数",
                ["ext_proc_edm_003"],
                "电火花加工",
                "medium",
            ),
            EvaluationQuery(
                "EQ007", "PTFE塑料加工特性", ["ext_mat_pl_001"], "工程塑料", "easy"
            ),
            EvaluationQuery(
                "EQ008", "CBN刀具适用范围", ["ext_tool_005"], "刀具选择", "medium"
            ),
            EvaluationQuery(
                "EQ009", "细长轴车削工艺", ["ext_proc_turn_010"], "车削工艺", "hard"
            ),
            EvaluationQuery(
                "EQ010", "高速铣削技术要点", ["ext_proc_mill_005"], "铣削工艺", "hard"
            ),
            EvaluationQuery(
                "EQ011", "304不锈钢材料参数", ["ext_mat_ss_001"], "材料参数", "easy"
            ),
            EvaluationQuery(
                "EQ012", "6061铝合金参数", ["ext_mat_al_002"], "材料参数", "easy"
            ),
            EvaluationQuery(
                "EQ013", "螺纹车削方法", ["ext_proc_turn_005"], "车削工艺", "medium"
            ),
            EvaluationQuery(
                "EQ014", "深孔钻孔工艺", ["ext_proc_drill_004"], "钻孔工艺", "hard"
            ),
            EvaluationQuery(
                "EQ015", "无心磨削加工", ["ext_proc_grind_008"], "磨削工艺", "medium"
            ),
            EvaluationQuery(
                "EQ016", "内圆磨削特点", ["ext_proc_grind_005"], "磨削工艺", "medium"
            ),
            EvaluationQuery(
                "EQ017", "PCD刀具加工铝", ["ext_tool_006"], "刀具选择", "medium"
            ),
            EvaluationQuery(
                "EQ018", "陶瓷刀具应用", ["ext_tool_004"], "刀具选择", "medium"
            ),
            EvaluationQuery(
                "EQ019", "切削液选择指南", ["ext_tool_017"], "切削液", "medium"
            ),
            EvaluationQuery(
                "EQ020", "刀具磨损形式", ["ext_tool_008"], "刀具磨损", "medium"
            ),
            EvaluationQuery(
                "EQ021", "G代码编程基础", ["ext_proc_turn_007"], "数控编程", "easy"
            ),
            EvaluationQuery(
                "EQ022", "型腔铣削策略", ["ext_proc_mill_012"], "铣削工艺", "hard"
            ),
            EvaluationQuery(
                "EQ023", "五轴铣削加工", ["ext_proc_mill_014"], "铣削工艺", "hard"
            ),
            EvaluationQuery(
                "EQ024", "铰孔加工精度", ["ext_proc_drill_007"], "钻孔工艺", "medium"
            ),
            EvaluationQuery(
                "EQ025", "表面粗糙度等级", ["ext_proc_turn_008"], "质量控制", "easy"
            ),
            EvaluationQuery(
                "EQ026", "公差配合选择", ["ext_tool_018"], "精度公差", "medium"
            ),
            EvaluationQuery(
                "EQ027", "转位刀片型号识别", ["ext_tool_015"], "刀具管理", "medium"
            ),
            EvaluationQuery(
                "EQ028", "模具铣削加工", ["ext_proc_mill_007"], "铣削工艺", "hard"
            ),
            EvaluationQuery(
                "EQ029", "薄壁件车削工艺", ["ext_proc_turn_011"], "车削工艺", "hard"
            ),
            EvaluationQuery(
                "EQ030", "振动控制方法", ["ext_proc_mill_004"], "铣削工艺", "hard"
            ),
            EvaluationQuery(
                "EQ031", "黄铜加工特性", ["ext_mat_cu_001"], "材料特性", "easy"
            ),
            EvaluationQuery(
                "EQ032", "紫铜加工难点", ["ext_mat_cu_006"], "材料特性", "medium"
            ),
            EvaluationQuery(
                "EQ033", "铍青铜材料参数", ["ext_mat_cu_005"], "材料参数", "medium"
            ),
            EvaluationQuery(
                "EQ034", "铝青铜应用", ["ext_mat_cu_008"], "材料应用", "medium"
            ),
            EvaluationQuery(
                "EQ035", "白铜耐腐蚀性", ["ext_mat_cu_009"], "材料特性", "easy"
            ),
            EvaluationQuery(
                "EQ036", "POM塑料加工", ["ext_mat_pl_003"], "工程塑料", "easy"
            ),
            EvaluationQuery(
                "EQ037", "PEEK材料特性", ["ext_mat_pl_005"], "工程塑料", "medium"
            ),
            EvaluationQuery(
                "EQ038", "有机玻璃加工", ["ext_mat_pl_006"], "工程塑料", "easy"
            ),
            EvaluationQuery(
                "EQ039", "ABS塑料切削", ["ext_mat_pl_007"], "工程塑料", "easy"
            ),
            EvaluationQuery(
                "EQ040", "PC聚碳酸酯加工", ["ext_mat_pl_008"], "工程塑料", "medium"
            ),
            EvaluationQuery(
                "EQ041", "增强塑料加工", ["ext_mat_pl_010"], "工程塑料", "hard"
            ),
            EvaluationQuery(
                "EQ042", "面铣刀加工参数", ["ext_proc_mill_003"], "铣削工艺", "medium"
            ),
            EvaluationQuery(
                "EQ043", "立铣刀选择", ["ext_proc_mill_002"], "铣削工艺", "medium"
            ),
            EvaluationQuery(
                "EQ044", "顺铣逆铣区别", ["ext_proc_mill_001"], "铣削工艺", "easy"
            ),
            EvaluationQuery(
                "EQ045", "钻头刃磨技术", ["ext_tool_011"], "刀具维护", "medium"
            ),
            EvaluationQuery(
                "EQ046", "中心钻定心", ["ext_proc_drill_006"], "钻孔工艺", "easy"
            ),
            EvaluationQuery(
                "EQ047", "数控钻孔循环", ["ext_proc_drill_009"], "数控编程", "medium"
            ),
            EvaluationQuery(
                "EQ048", "砂轮选择要素", ["ext_proc_grind_002"], "磨削工艺", "medium"
            ),
            EvaluationQuery(
                "EQ049", "砂轮修整技术", ["ext_proc_grind_007"], "磨削工艺", "hard"
            ),
            EvaluationQuery(
                "EQ050", "超精密磨削", ["ext_proc_grind_009"], "磨削工艺", "hard"
            ),
            EvaluationQuery(
                "EQ051", "成形电火花工艺", ["ext_proc_edm_002"], "电火花加工", "hard"
            ),
            EvaluationQuery(
                "EQ052", "小孔电火花加工", ["ext_proc_edm_007"], "电火花加工", "hard"
            ),
            EvaluationQuery(
                "EQ053", "电极设计要点", ["ext_proc_edm_005"], "电火花加工", "hard"
            ),
            EvaluationQuery(
                "EQ054", "车削效率提升", ["ext_proc_turn_015"], "车削工艺", "medium"
            ),
            EvaluationQuery(
                "EQ055", "铣削效率优化", ["ext_proc_mill_015"], "铣削工艺", "medium"
            ),
            EvaluationQuery(
                "EQ056", "904L超级不锈钢", ["ext_mat_ss_011"], "材料参数", "hard"
            ),
            EvaluationQuery(
                "EQ057", "2205双相不锈钢", ["ext_mat_ss_005"], "材料参数", "hard"
            ),
            EvaluationQuery(
                "EQ058", "17-4PH不锈钢", ["ext_mat_ss_012"], "材料参数", "hard"
            ),
            EvaluationQuery(
                "EQ059", "不锈钢攻丝工艺", ["ext_mat_ss_010"], "不锈钢加工", "hard"
            ),
            EvaluationQuery(
                "EQ060", "不锈钢表面处理", ["ext_mat_ss_014"], "不锈钢加工", "medium"
            ),
        ]

    def get_queries(
        self, category: str | None = None, difficulty: str | None = None
    ) -> list[EvaluationQuery]:
        queries = self.queries
        if category:
            queries = [q for q in queries if q.category == category]
        if difficulty:
            queries = [q for q in queries if q.difficulty == difficulty]
        return queries

    def get_query_by_id(self, query_id: str) -> EvaluationQuery | None:
        for q in self.queries:
            if q.query_id == query_id:
                return q
        return None

    def get_stats(self) -> dict:
        categories = {}
        difficulties = {}

        for q in self.queries:
            categories[q.category] = categories.get(q.category, 0) + 1
            difficulties[q.difficulty] = difficulties.get(q.difficulty, 0) + 1

        return {
            "total_queries": len(self.queries),
            "categories": categories,
            "difficulties": difficulties,
        }


class RetrievalEvaluator:
    def __init__(self, knowledge_base, reranker_service=None):
        self.knowledge_base = knowledge_base
        self.reranker_service = reranker_service
        self.dataset = EvaluationDataset()

    def calculate_precision_at_k(
        self, expected: list[str], retrieved: list[str], k: int
    ) -> float:
        if k == 0 or not retrieved:
            return 0.0

        relevant_retrieved = [doc_id for doc_id in retrieved[:k] if doc_id in expected]
        return len(relevant_retrieved) / k

    def calculate_recall_at_k(
        self, expected: list[str], retrieved: list[str], k: int
    ) -> float:
        if not expected:
            return 0.0

        relevant_retrieved = [doc_id for doc_id in retrieved[:k] if doc_id in expected]
        return len(relevant_retrieved) / len(expected)

    def calculate_f1_score(self, precision: float, recall: float) -> float:
        if precision + recall == 0:
            return 0.0
        return 2 * (precision * recall) / (precision + recall)

    def calculate_mrr(self, expected: list[str], retrieved: list[str]) -> float:
        for i, doc_id in enumerate(retrieved):
            if doc_id in expected:
                return 1.0 / (i + 1)
        return 0.0

    def calculate_ndcg_at_k(
        self, expected: list[str], retrieved: list[str], k: int
    ) -> float:
        if k == 0 or not retrieved:
            return 0.0

        relevance_scores = []
        for doc_id in retrieved[:k]:
            if doc_id in expected:
                relevance_scores.append(1.0)
            else:
                relevance_scores.append(0.0)

        dcg = 0.0
        for i, rel in enumerate(relevance_scores):
            dcg += rel / (i + 1)

        ideal_relevance = sorted(
            [1.0] * min(len(expected), k) + [0.0] * max(0, k - len(expected)),
            reverse=True,
        )
        idcg = 0.0
        for i, rel in enumerate(ideal_relevance):
            idcg += rel / (i + 1)

        if idcg == 0:
            return 0.0
        return dcg / idcg

    def evaluate_single_query(
        self, query: EvaluationQuery, top_k: int = 3
    ) -> EvaluationResult:
        start_time = time.time()

        raw_results = self.knowledge_base.query(
            query_text=query.query_text, n_results=top_k * 2
        )

        if self.reranker_service and raw_results.get("documents"):
            formatted_results = []
            docs = (
                raw_results["documents"][0]
                if raw_results["documents"]
                and isinstance(raw_results["documents"][0], list)
                else raw_results["documents"]
            )
            metas = (
                raw_results["metadatas"][0]
                if raw_results["metadatas"]
                and isinstance(raw_results["metadatas"][0], list)
                else raw_results["metadatas"]
            )
            dists = (
                raw_results["distances"][0]
                if raw_results["distances"]
                and isinstance(raw_results["distances"][0], list)
                else raw_results["distances"]
            )
            ids = (
                raw_results["ids"][0]
                if raw_results["ids"] and isinstance(raw_results["ids"][0], list)
                else raw_results["ids"]
            )

            for i, doc in enumerate(docs):
                formatted_results.append(
                    {
                        "id": ids[i],
                        "document": doc,
                        "metadata": metas[i],
                        "distance": dists[i],
                    }
                )

            reranked_results = self.reranker_service.rerank(
                query=query.query_text, results=formatted_results
            )

            retrieved_ids = [r["doc_id"] for r in reranked_results[:top_k]]
        else:
            retrieved_ids = raw_results["ids"][:top_k]

        elapsed_time = (time.time() - start_time) * 1000

        precision = self.calculate_precision_at_k(
            query.expected_doc_ids, retrieved_ids, top_k
        )
        recall = self.calculate_recall_at_k(
            query.expected_doc_ids, retrieved_ids, top_k
        )
        f1 = self.calculate_f1_score(precision, recall)
        mrr = self.calculate_mrr(query.expected_doc_ids, retrieved_ids)
        ndcg = self.calculate_ndcg_at_k(query.expected_doc_ids, retrieved_ids, top_k)

        hits = len(
            [doc_id for doc_id in retrieved_ids if doc_id in query.expected_doc_ids]
        )

        return EvaluationResult(
            query_id=query.query_id,
            query_text=query.query_text,
            expected_doc_ids=query.expected_doc_ids,
            retrieved_doc_ids=retrieved_ids,
            top_k=top_k,
            hits=hits,
            precision=precision,
            recall=recall,
            f1_score=f1,
            mrr=mrr,
            ndcg=ndcg,
            retrieval_time_ms=round(elapsed_time, 2),
        )

    def evaluate_all(
        self, top_k: int = 3, category: str | None = None, difficulty: str | None = None
    ) -> EvaluationReport:
        queries = self.dataset.get_queries(category=category, difficulty=difficulty)

        results = []
        for query in queries:
            result = self.evaluate_single_query(query, top_k=top_k)
            results.append(result)

        avg_precision = (
            sum(r.precision for r in results) / len(results) if results else 0.0
        )
        avg_recall = sum(r.recall for r in results) / len(results) if results else 0.0
        avg_f1 = sum(r.f1_score for r in results) / len(results) if results else 0.0
        avg_mrr = sum(r.mrr for r in results) / len(results) if results else 0.0
        avg_ndcg = sum(r.ndcg for r in results) / len(results) if results else 0.0

        top3_correct = sum(1 for r in results if r.hits > 0)
        top3_accuracy = top3_correct / len(results) if results else 0.0

        category_perf = {}
        for r in results:
            query = self.dataset.get_query_by_id(r.query_id)
            if query:
                cat = query.category
                if cat not in category_perf:
                    category_perf[cat] = {"total": 0, "correct": 0}
                category_perf[cat]["total"] += 1
                if r.hits > 0:
                    category_perf[cat]["correct"] += 1

        for cat in category_perf:
            total = category_perf[cat]["total"]
            correct = category_perf[cat]["correct"]
            category_perf[cat]["accuracy"] = (
                round(correct / total, 4) if total > 0 else 0.0
            )

        target_accuracy = 0.80
        performance_target_met = top3_accuracy >= target_accuracy

        report = EvaluationReport(
            report_id=f"ER_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            evaluation_time=datetime.now().isoformat(),
            total_queries=len(results),
            top_k=top_k,
            avg_precision=round(avg_precision, 4),
            avg_recall=round(avg_recall, 4),
            avg_f1_score=round(avg_f1, 4),
            avg_mrr=round(avg_mrr, 4),
            avg_ndcg=round(avg_ndcg, 4),
            top3_accuracy=round(top3_accuracy, 4),
            top5_accuracy=round(top3_accuracy, 4),
            category_performance=category_perf,
            query_results=[r.to_dict() for r in results],
            performance_target_met=performance_target_met,
            target_accuracy=target_accuracy,
        )

        return report

    def generate_report(
        self, report: EvaluationReport, output_path: str | None = None
    ) -> str:
        report_content = {
            "report_id": report.report_id,
            "evaluation_time": report.evaluation_time,
            "summary": {
                "total_queries": report.total_queries,
                "top_k": report.top_k,
                "avg_precision": report.avg_precision,
                "avg_recall": report.avg_recall,
                "avg_f1_score": report.avg_f1_score,
                "avg_mrr": report.avg_mrr,
                "avg_ndcg": report.avg_ndcg,
                "top3_accuracy": report.top3_accuracy,
                "performance_target_met": report.performance_target_met,
                "target_accuracy": report.target_accuracy,
            },
            "category_performance": report.category_performance,
            "query_results": report.query_results,
        }

        if output_path:
            output_path_obj = Path(output_path)
            output_path_obj.parent.mkdir(parents=True, exist_ok=True)

            with open(output_path_obj, "w", encoding="utf-8") as f:
                json.dump(report_content, f, ensure_ascii=False, indent=2)

            return f"评估报告已保存至: {output_path}"

        return json.dumps(report_content, ensure_ascii=False, indent=2)
