import asyncio
import json
import time

from app.ai.workflow import WorkflowOrchestrator
from app.ai.workflow_parallel import (
    DependencyAnalyzer,
    ParallelWorkflowOrchestrator,
    TaskComplexityEvaluator,
    WorkflowCache,
)


class PerformanceTester:
    def __init__(self):
        self.sequential_orchestrator = WorkflowOrchestrator(use_parallel=False)
        self.parallel_orchestrator = ParallelWorkflowOrchestrator()
        self.test_inputs = [
            {
                "input": "加工一根45钢的轴类零件，直径50mm，长度200mm",
                "description": "简单任务-45钢轴"
            },
            {
                "input": "精密加工钛合金齿轮，要求IT6公差等级，表面粗糙度Ra0.4",
                "description": "复杂任务-钛合金精密齿轮"
            },
            {
                "input": "加工6061铝合金盘类零件，直径120mm，厚度30mm",
                "description": "中等任务-铝合金盘"
            }
        ]

    async def test_dependency_analysis(self):
        print("\n=== 依赖关系分析测试 ===")

        is_valid = DependencyAnalyzer.validate_graph()
        print(f"依赖图有效性: {'✓ 有效' if is_valid else '✗ 无效'}")

        sequential_layers = [["understanding"], ["planning"], ["parameter"], ["nc_generation"], ["verification"], ["repair"]]
        print(f"串行执行层数: {len(sequential_layers)}")
        print(f"串行执行: {sequential_layers}")

        parallel_layers = DependencyAnalyzer.analyze(skip_verification=False, skip_repair=False)
        print(f"并行执行层数: {len(parallel_layers)}")
        for i, layer in enumerate(parallel_layers):
            is_parallel = len(layer) > 1
            print(f"  第{i+1}层: {layer} {'(并行)' if is_parallel else '(串行)'}")

        parallel_pairs = DependencyAnalyzer.get_parallelizable_agents()
        print(f"可并行Agent对: {parallel_pairs}")

        simple_layers = DependencyAnalyzer.analyze(skip_verification=True, skip_repair=True)
        print(f"简单模式执行层: {simple_layers}")

    async def test_complexity_evaluation(self):
        print("\n=== 任务复杂度评估测试 ===")

        test_cases = [
            ("加工一根45钢的轴", "简单任务"),
            ("精密加工钛合金齿轮，要求IT6公差", "复杂任务"),
            ("高精度铝合金壳体，表面粗糙度Ra0.4", "复杂任务"),
            ("6061铝盘类零件", "简单任务"),
            ("航空航天用钛合金零件，需要热处理", "复杂任务"),
        ]

        for input_text, expected in test_cases:
            is_complex, evaluation = TaskComplexityEvaluator.evaluate(input_text)
            actual = "复杂" if is_complex else "简单"
            match = "✓" if (is_complex and "复杂" in expected) or (not is_complex and "简单" in expected) else "✗"
            print(f"{match} {input_text[:20]}... -> {actual} (预期: {expected})")
            if evaluation["reasons"]:
                print(f"  原因: {', '.join(evaluation['reasons'])}")

    async def test_cache_system(self):
        print("\n=== 缓存系统测试 ===")
        cache = WorkflowCache()

        test_input = "45钢轴类零件"
        test_result = {"data": "test_result", "timestamp": time.time()}

        print(f"初始缓存统计: {cache.stats}")

        cache.set(test_input, test_result)
        print(f"写入缓存后: {cache.stats}")

        cached = cache.get(test_input)
        print(f"缓存命中: {'✓' if cached else '✗'}")

        cache.invalidate(test_input)
        print(f"失效清理后: {cache.stats}")

        cached = cache.get(test_input)
        print(f"失效后命中: {'✗ (正确)' if not cached else '✓ (错误)'}")

    async def run_performance_comparison(self, iterations: int = 3):
        print(f"\n=== 性能对比测试 ({iterations} 次迭代) ===")

        results = {
            "sequential": [],
            "parallel": [],
            "cache_hits": []
        }

        for test_case in self.test_inputs:
            print(f"\n测试用例: {test_case['description']}")
            print(f"输入: {test_case['input']}")

            sequential_times = []
            for i in range(iterations):
                start = time.time()
                try:
                    await self.sequential_orchestrator.execute_workflow(test_case["input"])
                except Exception as e:
                    print(f"  串行执行失败: {e}")
                elapsed = time.time() - start
                sequential_times.append(elapsed)
                print(f"  串行 #{i+1}: {elapsed:.2f}s")

            self.parallel_orchestrator.cache._cache.clear()
            parallel_times = []
            cache_hits = 0
            for i in range(iterations):
                start = time.time()
                try:
                    result = await self.parallel_orchestrator.execute_workflow(test_case["input"])
                    if result.get("cache_hit"):
                        cache_hits += 1
                except Exception as e:
                    print(f"  并行执行失败: {e}")
                elapsed = time.time() - start
                parallel_times.append(elapsed)
                cache_indicator = " (缓存命中)" if i > 0 else ""
                print(f"  并行 #{i+1}: {elapsed:.2f}s{cache_indicator}")

            avg_sequential = sum(sequential_times) / len(sequential_times)
            avg_parallel_first = parallel_times[0] if parallel_times else 0
            avg_parallel_cached = sum(parallel_times[1:]) / len(parallel_times[1:]) if len(parallel_times) > 1 else 0

            improvement_first = ((avg_sequential - avg_parallel_first) / avg_sequential * 100) if avg_sequential > 0 else 0
            improvement_cached = ((avg_sequential - avg_parallel_cached) / avg_sequential * 100) if avg_sequential > 0 else 0

            print("\n  结果汇总:")
            print(f"    串行平均: {avg_sequential:.2f}s")
            print(f"    并行首次: {avg_parallel_first:.2f}s (提升: {improvement_first:.1f}%)")
            print(f"    并行缓存: {avg_parallel_cached:.2f}s (提升: {improvement_cached:.1f}%)")
            print(f"    缓存命中: {cache_hits}/{iterations}")

            results["sequential"].append({
                "description": test_case["description"],
                "times": sequential_times,
                "avg": avg_sequential
            })
            results["parallel"].append({
                "description": test_case["description"],
                "times": parallel_times,
                "avg_first": avg_parallel_first,
                "avg_cached": avg_parallel_cached,
                "cache_hits": cache_hits
            })

        overall_sequential = sum(r["avg"] for r in results["sequential"]) / len(results["sequential"])
        overall_parallel = sum(r["avg_first"] for r in results["parallel"]) / len(results["parallel"])
        overall_cached = sum(r["avg_cached"] for r in results["parallel"]) / len(results["parallel"])

        overall_improvement_first = ((overall_sequential - overall_parallel) / overall_sequential * 100)
        overall_improvement_cached = ((overall_sequential - overall_cached) / overall_sequential * 100)

        print("\n=== 整体性能汇总 ===")
        print(f"串行平均: {overall_sequential:.2f}s")
        print(f"并行首次: {overall_parallel:.2f}s")
        print(f"并行缓存: {overall_cached:.2f}s")
        print(f"首次执行提升: {overall_improvement_first:.1f}%")
        print(f"缓存命中提升: {overall_improvement_cached:.1f}%")
        print(f"优化目标(30%): {'✓ 达成' if overall_improvement_first >= 30 else '✗ 未达成'}")

        return results

    async def run_all_tests(self):
        print("=" * 60)
        print("Agent工作流并行优化 - 性能测试报告")
        print("=" * 60)

        await self.test_dependency_analysis()
        await self.test_complexity_evaluation()
        await self.test_cache_system()
        results = await self.run_performance_comparison()

        print("\n" + "=" * 60)
        print("测试完成!")
        print("=" * 60)

        return results


async def main():
    tester = PerformanceTester()
    results = await tester.run_all_tests()

    with open("performance_test_results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print("\n测试结果已保存到: performance_test_results.json")


if __name__ == "__main__":
    asyncio.run(main())
