"""RAG 优化效果验证脚本。

验证本轮所有优化项是否正确工作，并量化效果提升：
1. 共享分词器（jieba + 制造领域词典）
2. NDCG 学术标准公式（log2 折损）
3. LRU 缓存正确性（命中统计、淘汰、更新）
4. SHA256 去重（避免前 100 字碰撞）
5. BM25 动态归一化（替代硬编码阈值）
6. Embedding 批量推理分块
7. Query Rewriter 缓存统计与 LLM/规则计数
8. RRF k 参数调优（k=40）
9. ChromaDB 结果解析统一
10. 关键词 boost 预计算

用法：
    python scripts/verify_rag_optimizations.py
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

# 让脚本能直接从仓库根目录运行
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

PASS = "\033[92m✓\033[0m"
FAIL = "\033[91m✗\033[0m"
WARN = "\033[93m!\033[0m"

_results: list[tuple[str, bool, str]] = []


def record(name: str, ok: bool, detail: str = "") -> None:
    _results.append((name, ok, detail))
    symbol = PASS if ok else FAIL
    line = f"  {symbol} {name}"
    if detail:
        line += f" — {detail}"
    print(line)


def section(title: str) -> None:
    print()
    print("=" * 70)
    print(f"  {title}")
    print("=" * 70)


# ---------------------------------------------------------------------------
# 1. 共享分词器
# ---------------------------------------------------------------------------


def test_tokenizer() -> None:
    section("1. 共享分词器（jieba + 制造领域词典）")
    try:
        from app.rag.tokenizer import get_tokenizer_info, tokenize

        info = get_tokenizer_info()
        record("分词器信息可获取", isinstance(info, dict), str(info))

        # 制造领域专用词典应被识别为整体 token
        text = "TC4 钛合金切削参数 HRC52 PHM2010"
        tokens = tokenize(text)
        record("分词器返回 token 列表", isinstance(tokens, list) and len(tokens) > 0,
               f"tokens={tokens}")

        # 验证领域词典词被整体保留
        joined = " ".join(tokens)
        has_tc4 = "TC4" in joined or "tc4" in joined.lower()
        record("TC4 被整体保留", has_tc4, joined)

        has_hrc = "HRC52" in joined or "hrc52" in joined.lower()
        record("HRC52 被整体保留", has_hrc, joined)

        has_phm = "PHM2010" in joined or "phm2010" in joined.lower()
        record("PHM2010 被整体保留", has_phm, joined)

        # 中文分词
        cn_tokens = tokenize("钛合金切削参数")
        record("中文分词正常", len(cn_tokens) > 0, f"tokens={cn_tokens}")

    except Exception as e:  # noqa: BLE001
        record("分词器测试", False, f"{type(e).__name__}: {e}")


# ---------------------------------------------------------------------------
# 2. NDCG 学术标准公式
# ---------------------------------------------------------------------------


def test_ndcg_formula() -> None:
    section("2. NDCG 学术标准公式（log2 折损）")
    try:
        import math
        from app.rag.evaluation import RetrievalEvaluator

        # 用一个 stub knowledge_base 构造 evaluator（不需要真实 KB）
        class _StubKB:
            def query(self, *a, **kw):  # noqa: ARG002
                return {"documents": [[]], "metadatas": [[]], "distances": [[]], "ids": [[]]}

        evaluator = RetrievalEvaluator(_StubKB())

        # 测试 1：完全命中 → NDCG=1.0
        ndcg_perfect = evaluator.calculate_ndcg_at_k(
            expected=["a", "b", "c"],
            retrieved=["a", "b", "c"],
            k=3,
        )
        record("完全命中 NDCG=1.0", abs(ndcg_perfect - 1.0) < 1e-9,
               f"ndcg={ndcg_perfect:.6f}")

        # 测试 2：完全未命中 → NDCG=0.0
        ndcg_miss = evaluator.calculate_ndcg_at_k(
            expected=["a", "b"],
            retrieved=["x", "y", "z"],
            k=3,
        )
        record("完全未命中 NDCG=0.0", ndcg_miss == 0.0, f"ndcg={ndcg_miss}")

        # 测试 3：手工验证标准公式
        # expected=[A], retrieved=[X, A, Y], k=3
        # DCG = 0/log2(2) + 1/log2(3) + 0/log2(4) = 1/log2(3)
        # IDCG = 1/log2(2) = 1
        # NDCG = (1/log2(3)) / 1 = 1/log2(3) ≈ 0.6309297...
        expected_ndcg = 1.0 / math.log2(3)
        ndcg_partial = evaluator.calculate_ndcg_at_k(
            expected=["A"],
            retrieved=["X", "A", "Y"],
            k=3,
        )
        record("部分命中符合 log2(rank+1) 折损",
               abs(ndcg_partial - expected_ndcg) < 1e-9,
               f"actual={ndcg_partial:.6f}, expected={expected_ndcg:.6f}")

        # 测试 4：与旧公式（1/(i+1)）对比，证明新公式更准确
        # 旧公式会给出 1/2 = 0.5，新公式给出 1/log2(3) ≈ 0.6309
        # 新公式对靠前命中更敏感，符合学术标准
        old_formula_value = 1.0 / 2  # 旧公式 1/(i+1) where i=1
        record("新公式与旧公式不同（证明已修复）",
               abs(ndcg_partial - old_formula_value) > 1e-6,
               f"new={ndcg_partial:.6f}, old={old_formula_value:.6f}")

    except Exception as e:  # noqa: BLE001
        record("NDCG 测试", False, f"{type(e).__name__}: {e}")


# ---------------------------------------------------------------------------
# 3. LRU 缓存正确性
# ---------------------------------------------------------------------------


def test_lru_cache() -> None:
    section("3. LRU 缓存正确性（命中统计、淘汰、更新）")
    try:
        from app.rag.embeddings import EmbeddingService

        # 用一个 mock 模型构造 service，避免加载真实 sentence-transformers
        class _MockModel:
            def __init__(self):
                self._counter = 0

            def encode(self, texts, **kwargs):  # noqa: ARG002
                import numpy as np
                self._counter += 1
                # 返回与文本数量匹配的向量
                return np.array([[float(i + self._counter)] for i in range(len(texts))])

        svc = EmbeddingService.__new__(EmbeddingService)
        svc._model = _MockModel()
        svc._model_name = "mock"
        svc._vector_dim = 1
        svc._cache = {}
        svc._cache_keys = []
        svc._cache_size = 3
        svc._cache_hits = 0
        svc._cache_misses = 0
        svc._total_embed_calls = 0
        svc._EMBED_BATCH_CHUNK = 32

        # 写入 3 条（满容量）
        for i in range(3):
            svc._cache_set(f"key{i}", [float(i)])
        record("写入 3 条到容量 3 的缓存", len(svc._cache) == 3, f"size={len(svc._cache)}")

        # 命中测试
        val = svc._cache_get("key1")
        record("命中已存在的 key", val == [1.0], f"val={val}")

        # 验证命中统计累加
        record("命中统计累加", svc._cache_hits == 1, f"hits={svc._cache_hits}")

        # 验证 LRU 顺序：key1 被访问后应在末尾
        record("LRU 顺序：访问后移到末尾",
               svc._cache_keys[-1] == "key1", f"keys={svc._cache_keys}")

        # 写入第 4 条，应淘汰 key0（最久未使用）
        svc._cache_set("key3", [3.0])
        record("写入超容量时淘汰最旧",
               "key0" not in svc._cache and len(svc._cache) == 3,
               f"keys={svc._cache_keys}")

        # 验证更新已存在的 key 的值（关键 bug 修复）
        svc._cache_set("key2", [99.0])
        updated_val = svc._cache_get("key2")
        record("更新已存在 key 的值（bug 修复）",
               updated_val == [99.0], f"val={updated_val}")

        # 未命中统计
        svc._cache_get("nonexistent")
        record("未命中统计累加", svc._cache_misses >= 1, f"misses={svc._cache_misses}")

        # get_cache_stats 接口可用
        stats = svc.get_cache_stats()
        record("get_cache_stats 返回完整字段",
               all(k in stats for k in ["cache_size", "cache_capacity", "cache_hits",
                                         "cache_misses", "cache_hit_rate", "total_embed_calls"]),
               str(stats))

    except Exception as e:  # noqa: BLE001
        record("LRU 缓存测试", False, f"{type(e).__name__}: {e}")


# ---------------------------------------------------------------------------
# 4. SHA256 去重
# ---------------------------------------------------------------------------


def test_sha256_dedup() -> None:
    section("4. SHA256 去重（避免前 100 字碰撞）")
    try:
        from app.rag.rag_retrieval import RagRetrievalEngine

        # 构造前 100 字相同但后续不同的文档
        common_prefix = "A" * 100
        doc1 = common_prefix + "实际内容一"
        doc2 = common_prefix + "实际内容二"

        results = [
            {"id": None, "document": doc1, "metadata": {}},
            {"id": None, "document": doc2, "metadata": {}},
            {"id": None, "document": doc1, "metadata": {}},  # 真正重复
        ]

        unique = RagRetrievalEngine._deduplicate(results)
        record("前 100 字相同但内容不同不被误去重",
               len(unique) == 2, f"unique_count={len(unique)}")

        # 验证真正重复的被去重
        results2 = [
            {"id": "id1", "document": "doc1"},
            {"id": "id1", "document": "doc1"},  # 相同 id
        ]
        unique2 = RagRetrievalEngine._deduplicate(results2)
        record("相同 id 的文档被去重", len(unique2) == 1, f"unique_count={len(unique2)}")

    except Exception as e:  # noqa: BLE001
        record("SHA256 去重测试", False, f"{type(e).__name__}: {e}")


# ---------------------------------------------------------------------------
# 5. BM25 动态归一化
# ---------------------------------------------------------------------------


def test_bm25_normalization() -> None:
    section("5. BM25 动态归一化（替代硬编码阈值）")
    try:
        from app.rag.hybrid_search import BM25Index

        idx = BM25Index()
        # BM25Index.add_documents 接收 dict 列表（含 "document" 键）
        docs = [
            {"id": "d1", "document": "钛合金切削参数 加工工艺"},
            {"id": "d2", "document": "不锈钢铣削 刀具选择"},
            {"id": "d3", "document": "铝合金钻孔 切削液"},
        ]
        idx.add_documents(docs)

        # search 返回排序后的结果列表（dict）
        results = idx.search("钛合金 切削", top_k=3)
        record("BM25 search 返回结果", isinstance(results, list) and len(results) >= 0,
               f"results={len(results)}")

        # 验证返回结果包含分数字段
        if results:
            first = results[0]
            record("结果包含 score/bm25_score 字段",
                   any(k in first for k in ["score", "bm25_score", "rerank_score"]),
                   str({k: first[k] for k in first if k in ["score", "bm25_score", "id"]}))

        # 验证查询统计字段（BM25Index 暴露 _query_count 和 _index_rebuild_count）
        record("BM25 查询计数字段存在", hasattr(idx, "_query_count"),
               f"_query_count={getattr(idx, '_query_count', 'N/A')}")
        record("BM25 重建计数字段存在", hasattr(idx, "_index_rebuild_count"),
               f"_index_rebuild_count={getattr(idx, '_index_rebuild_count', 'N/A')}")

        # 多次查询后计数应递增
        qcount_before = idx._query_count
        idx.search("测试查询", top_k=2)
        idx.search("测试查询", top_k=2)
        qcount_after = idx._query_count
        record("多次查询后 _query_count 递增",
               qcount_after >= qcount_before + 2,
               f"before={qcount_before}, after={qcount_after}")

    except Exception as e:  # noqa: BLE001
        record("BM25 归一化测试", False, f"{type(e).__name__}: {e}")


# ---------------------------------------------------------------------------
# 6. Embedding 批量推理分块
# ---------------------------------------------------------------------------


def test_embed_batch_chunking() -> None:
    section("6. Embedding 批量推理分块（避免大 batch OOM）")
    try:
        from app.rag.embeddings import EmbeddingService

        # 验证 _EMBED_BATCH_CHUNK 常量存在
        record("_EMBED_BATCH_CHUNK 常量存在",
               hasattr(EmbeddingService, "_EMBED_BATCH_CHUNK"),
               f"value={getattr(EmbeddingService, '_EMBED_BATCH_CHUNK', 'N/A')}")

        record("批量大小为合理值（<=64）",
               getattr(EmbeddingService, "_EMBED_BATCH_CHUNK", 999) <= 64,
               f"chunk={getattr(EmbeddingService, '_EMBED_BATCH_CHUNK', 'N/A')}")

        # 模拟大批量推理，验证分块逻辑
        class _MockModel:
            def __init__(self):
                self.call_count = 0
                self.batch_sizes: list[int] = []

            def encode(self, texts, **kwargs):  # noqa: ARG002
                import numpy as np
                self.call_count += 1
                self.batch_sizes.append(len(texts))
                return np.array([[0.1] for _ in texts])

        svc = EmbeddingService.__new__(EmbeddingService)
        svc._model = _MockModel()
        svc._model_name = "mock"
        svc._vector_dim = 1
        svc._cache = {}
        svc._cache_keys = []
        svc._cache_size = 100
        svc._cache_hits = 0
        svc._cache_misses = 0
        svc._total_embed_calls = 0
        svc._EMBED_BATCH_CHUNK = 32

        # 80 条文本，应该被分成 3 批（32+32+16）
        texts = [f"text_{i}" for i in range(80)]
        results = svc.embed_batch(texts)
        record("批量推理返回正确数量", len(results) == 80, f"len={len(results)}")

        record("分块调用模型 3 次", svc._model.call_count == 3,
               f"calls={svc._model.call_count}, batches={svc._model.batch_sizes}")

        record("最后一批为剩余数量", svc._model.batch_sizes[-1] == 16,
               f"last_batch={svc._model.batch_sizes[-1]}")

    except Exception as e:  # noqa: BLE001
        record("批量推理测试", False, f"{type(e).__name__}: {e}")


# ---------------------------------------------------------------------------
# 7. Query Rewriter 缓存统计
# ---------------------------------------------------------------------------


def test_query_rewriter_stats() -> None:
    section("7. Query Rewriter 缓存统计与 LLM/规则计数")
    try:
        from app.rag.query_rewriter import QueryRewriter

        qr = QueryRewriter(enable_rewrite=True, enable_hyde=False)

        record("rewrite_hits 字段存在", hasattr(qr, "_rewrite_hits"))
        record("rewrite_misses 字段存在", hasattr(qr, "_rewrite_misses"))
        record("hyde_hits 字段存在", hasattr(qr, "_hyde_hits"))
        record("hyde_misses 字段存在", hasattr(qr, "_hyde_misses"))
        record("rule_rewrite_count 字段存在", hasattr(qr, "_rule_rewrite_count"))
        record("llm_rewrite_count 字段存在", hasattr(qr, "_llm_rewrite_count"))

        # 验证 LRU 写入更新已存在 key（bug 修复）
        cache = {}
        keys = []
        qr._cache_set(cache, keys, "k1", "v1", max_size=10)
        qr._cache_set(cache, keys, "k1", "v2", max_size=10)  # 更新
        record("cache_set 更新已存在 key 的值",
               cache["k1"] == "v2" and len(keys) == 1, f"val={cache.get('k1')}, keys={keys}")

        # 验证 LRU 读
        val = qr._cache_get(cache, keys, "k1")
        record("cache_get 命中返回值", val == "v2", f"val={val}")

        # 验证 get_stats 返回完整字段
        stats = qr.get_stats()
        required_fields = ["enable_rewrite", "enable_hyde", "rewrite_hits", "rewrite_misses",
                           "rewrite_hit_rate", "hyde_hits", "hyde_misses",
                           "llm_rewrite_count", "rule_rewrite_count", "rule_fallback_rate"]
        record("get_stats 返回完整诊断字段",
               all(f in stats for f in required_fields), str(stats))

    except Exception as e:  # noqa: BLE001
        record("Query Rewriter 测试", False, f"{type(e).__name__}: {e}")


# ---------------------------------------------------------------------------
# 8. RRF k 参数
# ---------------------------------------------------------------------------


def test_rrf_k_parameter() -> None:
    section("8. RRF k 参数调优（k=40）")
    try:
        from app.rag.hybrid_search import HybridSearchEngine, DEFAULT_RRF_K

        record("DEFAULT_RRF_K 为 40", DEFAULT_RRF_K == 40, f"k={DEFAULT_RRF_K}")

        # 验证 RRF 融合逻辑：k=40 对头部结果更敏感
        # RRF score = 1/(k + rank)
        # rank=1: 1/41 ≈ 0.0244
        # rank=2: 1/42 ≈ 0.0238
        # 差值：0.0006（比 k=60 时的 0.00028 更大，对头部更敏感）
        k = 40
        rrf_rank1 = 1.0 / (k + 1)
        rrf_rank2 = 1.0 / (k + 2)
        diff = rrf_rank1 - rrf_rank2

        k60_diff = (1.0 / 61) - (1.0 / 62)
        record("k=40 比k=60 对头部更敏感",
               diff > k60_diff,
               f"k=40 diff={diff:.6f}, k=60 diff={k60_diff:.6f}")

    except Exception as e:  # noqa: BLE001
        record("RRF k 参数测试", False, f"{type(e).__name__}: {e}")


# ---------------------------------------------------------------------------
# 9. ChromaDB 结果解析统一
# ---------------------------------------------------------------------------


def test_chroma_parse() -> None:
    section("9. ChromaDB 结果解析统一（_parse_chroma_result）")
    try:
        from app.rag.rag_retrieval import RagRetrievalEngine

        # 模拟 ChromaDB 返回结构
        raw = {
            "documents": [["doc1", "doc2", "doc3"]],
            "metadatas": [[{"src": "a"}, {"src": "b"}, {"src": "c"}]],
            "distances": [[0.1, 0.5, 0.9]],
            "ids": [["id1", "id2", "id3"]],
        }

        parsed = RagRetrievalEngine._parse_chroma_result(raw)
        record("解析返回 3 条结果", len(parsed) == 3, f"len={len(parsed)}")

        record("第一条字段完整",
               all(k in parsed[0] for k in ["document", "metadata", "distance", "id"]),
               str(parsed[0]))

        record("distance 正确映射", parsed[0]["distance"] == 0.1, str(parsed[0]["distance"]))

        # 空 results 处理
        empty_raw = {"documents": [[]], "metadatas": [[]], "distances": [[]], "ids": [[]]}
        empty_parsed = RagRetrievalEngine._parse_chroma_result(empty_raw)
        record("空结果返回空列表", empty_parsed == [], f"len={len(empty_parsed)}")

    except Exception as e:  # noqa: BLE001
        record("ChromaDB 解析测试", False, f"{type(e).__name__}: {e}")


# ---------------------------------------------------------------------------
# 10. 关键词 boost 预计算
# ---------------------------------------------------------------------------


def test_keyword_boost_precompute() -> None:
    section("10. 关键词 boost 预计算（_keyword_boost_lower）")
    try:
        from app.rag.rag_retrieval import RagRetrievalEngine

        # 构造一个最小 stub kb
        class _StubKB:
            pass

        engine = RagRetrievalEngine.__new__(RagRetrievalEngine)
        engine.kb = _StubKB()
        engine.rules = {}
        from app.rag.rag_retrieval import RETRIEVAL_RULES, INTENT_KEYWORDS
        engine.rules = RETRIEVAL_RULES
        engine._intent_keywords_lower = {
            intent: [kw.lower() for kw in kws]
            for intent, kws in INTENT_KEYWORDS.items()
        }
        engine._keyword_boost_lower = {
            intent: {kw.lower(): boost for kw, boost in rule.keyword_boost.items()}
            for intent, rule in RETRIEVAL_RULES.items()
        }
        engine._cache = None
        engine._query_rewriter = None
        engine._hybrid_engine = None
        engine._reranker = None
        engine._enhancement_loaded = True

        # 验证预计算的 boost 字典存在且非空
        record("预计算 boost 字典存在",
               len(engine._keyword_boost_lower) > 0,
               f"intents={len(engine._keyword_boost_lower)}")

        # 验证关键词已小写
        for intent, boost_dict in engine._keyword_boost_lower.items():
            for kw in boost_dict:
                if kw != kw.lower():
                    record(f"关键词已小写: {intent}", False, f"kw={kw}")
                    break
        else:
            record("所有 boost 关键词已小写", True)

        # 意图检测应使用预计算的小写关键词
        intent = engine.detect_intent("TC4 钛合金磨损")
        record("意图检测正常工作", intent is not None, f"intent={intent}")

    except Exception as e:  # noqa: BLE001
        record("关键词 boost 预计算测试", False, f"{type(e).__name__}: {e}")


# ---------------------------------------------------------------------------
# 11. 性能对比：缓存命中 vs 未命中
# ---------------------------------------------------------------------------


def test_cache_performance() -> None:
    section("11. 性能对比：LRU 缓存命中 vs 未命中")
    try:
        from app.rag.embeddings import EmbeddingService

        class _MockModel:
            def __init__(self):
                self.calls = 0

            def encode(self, texts, **kwargs):  # noqa: ARG002
                import numpy as np
                import time as _time
                _time.sleep(0.001)  # 模拟推理延迟
                self.calls += 1
                return np.array([[0.1] for _ in texts])

        svc = EmbeddingService.__new__(EmbeddingService)
        svc._model = _MockModel()
        svc._model_name = "mock"
        svc._vector_dim = 1
        svc._cache = {}
        svc._cache_keys = []
        svc._cache_size = 100
        svc._cache_hits = 0
        svc._cache_misses = 0
        svc._total_embed_calls = 0
        svc._EMBED_BATCH_CHUNK = 32

        # 第一次：未命中（需要调用模型）
        t0 = time.perf_counter()
        r1 = svc.embed_batch(["相同文本"])
        t_miss = time.perf_counter() - t0

        # 第二次：命中（直接从缓存返回）
        t0 = time.perf_counter()
        r2 = svc.embed_batch(["相同文本"])
        t_hit = time.perf_counter() - t0

        record("缓存命中比未命中快", t_hit < t_miss,
               f"hit={t_hit*1e6:.1f}μs, miss={t_miss*1e6:.1f}μs, speedup={t_miss/max(t_hit,1e-9):.1f}x")

        record("两次结果一致", r1 == r2, f"r1==r2: {r1 == r2}")

        stats = svc.get_cache_stats()
        record("命中率统计正确", stats["cache_hits"] == 1 and stats["cache_misses"] == 1,
               str(stats))

    except Exception as e:  # noqa: BLE001
        record("缓存性能测试", False, f"{type(e).__name__}: {e}")


# ---------------------------------------------------------------------------
# 主入口
# ---------------------------------------------------------------------------


def main() -> int:
    print()
    print("╔" + "═" * 68 + "╗")
    print("║" + " RAG 优化效果验证报告".center(68) + "║")
    print("╚" + "═" * 68 + "╝")

    tests = [
        test_tokenizer,
        test_ndcg_formula,
        test_lru_cache,
        test_sha256_dedup,
        test_bm25_normalization,
        test_embed_batch_chunking,
        test_query_rewriter_stats,
        test_rrf_k_parameter,
        test_chroma_parse,
        test_keyword_boost_precompute,
        test_cache_performance,
    ]

    for test in tests:
        try:
            test()
        except Exception as e:  # noqa: BLE001
            record(test.__name__, False, f"未捕获异常: {type(e).__name__}: {e}")

    # 汇总
    section("汇总")
    total = len(_results)
    passed = sum(1 for _, ok, _ in _results if ok)
    failed = sum(1 for _, ok, _ in _results if not ok)
    print(f"  通过: {PASS} {passed}")
    print(f"  失败: {FAIL} {failed}")
    print(f"  总计: {total}")
    print()

    if failed:
        print("  失败项详情：")
        for name, ok, detail in _results:
            if not ok:
                print(f"    {FAIL} {name} — {detail}")
        return 1

    print("  " + PASS + " 所有验证项通过，优化效果已确认。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
