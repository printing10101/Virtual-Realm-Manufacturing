"""
LNN性能基准测试模块

功能：
- 模型推理延迟测试
- 批量推理吞吐量测试
- 内存使用基准测试
- 任务路由器性能测试
- 结果融合性能测试
"""
import os
import gc
import time
import json
import logging
import tracemalloc
import numpy as np
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field

try:
    import torch
    HAS_TORCH = True
except ImportError:
    HAS_TORCH = False

logger = logging.getLogger(__name__)


@dataclass
class BenchmarkResult:
    """基准测试结果"""
    test_name: str
    total_time_ms: float = 0.0
    avg_time_ms: float = 0.0
    min_time_ms: float = 0.0
    max_time_ms: float = 0.0
    p50_time_ms: float = 0.0
    p95_time_ms: float = 0.0
    p99_time_ms: float = 0.0
    throughput_per_sec: float = 0.0
    memory_peak_mb: float = 0.0
    memory_current_mb: float = 0.0
    iterations: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "test_name": self.test_name,
            "total_time_ms": round(self.total_time_ms, 3),
            "avg_time_ms": round(self.avg_time_ms, 3),
            "min_time_ms": round(self.min_time_ms, 3),
            "max_time_ms": round(self.max_time_ms, 3),
            "p50_time_ms": round(self.p50_time_ms, 3),
            "p95_time_ms": round(self.p95_time_ms, 3),
            "p99_time_ms": round(self.p99_time_ms, 3),
            "throughput_per_sec": round(self.throughput_per_sec, 2),
            "memory_peak_mb": round(self.memory_peak_mb, 2),
            "memory_current_mb": round(self.memory_current_mb, 2),
            "iterations": self.iterations,
            "metadata": self.metadata,
        }


class LNNAccelerationBenchmark:
    """LNN性能基准测试"""

    def __init__(self, output_dir: str = "benchmarks"):
        self.output_dir = output_dir
        self.results: List[BenchmarkResult] = []

    def run_all_benchmarks(self) -> List[BenchmarkResult]:
        """运行所有基准测试"""
        logger.info("Starting LNN benchmark suite...")

        self.benchmark_model_inference_latency()
        self.benchmark_batch_throughput()
        self.benchmark_memory_usage()
        self.benchmark_routing_performance()
        self.benchmark_fusion_performance()

        logger.info(f"Benchmark suite completed. {len(self.results)} tests executed.")

        self._save_results()

        return self.results

    def benchmark_model_inference_latency(
        self,
        model_types: Optional[List[str]] = None,
        iterations: int = 1000,
    ) -> BenchmarkResult:
        """基准测试：模型推理延迟"""
        if not HAS_TORCH:
            logger.warning("PyTorch not available, skipping inference latency benchmark")
            return None

        model_types = model_types or ["cfc", "ltc"]

        from app.ai.lnn.models.torch_cfc_model import CFCModel, LNNConfig as CFCConfig
        from app.ai.lnn.models.torch_ltc_model import LTCModel, LNNConfig as LTCConfig

        all_times = []

        for model_type in model_types:
            if model_type == "cfc":
                config = CFCConfig(input_size=20, hidden_size=64, output_size=1)
                model = CFCModel(config).eval()
            else:
                config = LTCConfig(input_size=20, hidden_size=64, output_size=1, num_layers=2)
                model = LTCModel(config).eval()

            x = torch.randn(1, 20)
            times = []

            for _ in range(iterations):
                start = time.perf_counter()
                with torch.no_grad():
                    _ = model(x, dt=0.1)
                elapsed = (time.perf_counter() - start) * 1000
                times.append(elapsed)

            all_times.extend(times)

        result = self._compute_stats("Model Inference Latency", all_times, iterations * len(model_types))
        result.metadata["model_types"] = model_types
        self.results.append(result)

        logger.info(f"Inference Latency: avg={result.avg_time_ms:.3f}ms, p95={result.p95_time_ms:.3f}ms")
        return result

    def benchmark_batch_throughput(
        self,
        batch_sizes: Optional[List[int]] = None,
        iterations: int = 100,
    ) -> BenchmarkResult:
        """基准测试：批量推理吞吐量"""
        if not HAS_TORCH:
            logger.warning("PyTorch not available, skipping batch throughput benchmark")
            return None

        from app.ai.lnn.models.torch_cfc_model import CFCModel, LNNConfig as CFCConfig

        config = CFCConfig(input_size=20, hidden_size=64, output_size=1)
        model = CFCModel(config).eval()

        batch_sizes = batch_sizes or [1, 8, 16, 32, 64, 128]
        all_times = []

        for bs in batch_sizes:
            x = torch.randn(bs, 20)
            times = []

            for _ in range(iterations):
                start = time.perf_counter()
                with torch.no_grad():
                    _ = model(x, dt=0.1)
                elapsed = (time.perf_counter() - start) * 1000
                times.append(elapsed)

            all_times.extend(times)

        result = self._compute_stats("Batch Throughput", all_times, iterations * len(batch_sizes))
        result.metadata["batch_sizes"] = batch_sizes
        result.throughput_per_sec = sum(batch_sizes) * iterations / (result.total_time_ms / 1000)
        self.results.append(result)

        logger.info(f"Batch Throughput: {result.throughput_per_sec:.2f} samples/sec")
        return result

    def benchmark_memory_usage(
        self,
        iterations: int = 500,
    ) -> BenchmarkResult:
        """基准测试：内存使用"""
        if not HAS_TORCH:
            logger.warning("PyTorch not available, skipping memory benchmark")
            return None

        from app.ai.lnn.models.torch_cfc_model import CFCModel, LNNConfig as CFCConfig
        from app.ai.lnn.models.torch_ltc_model import LTCModel, LNNConfig as LTCConfig

        tracemalloc.start()

        cfc_config = CFCConfig(input_size=20, hidden_size=64, output_size=1)
        cfc_model = CFCModel(cfc_config).eval()

        ltc_config = LTCConfig(input_size=20, hidden_size=64, output_size=1, num_layers=2)
        ltc_model = LTCModel(ltc_config).eval()

        x = torch.randn(32, 20)
        times = []

        for _ in range(iterations):
            gc.collect()
            start = time.perf_counter()
            with torch.no_grad():
                _ = cfc_model(x, dt=0.1)
                _ = ltc_model(x, dt=0.1)
            elapsed = (time.perf_counter() - start) * 1000
            times.append(elapsed)

        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        result = self._compute_stats("Memory Usage", times, iterations)
        result.memory_peak_mb = peak / (1024 * 1024)
        result.memory_current_mb = current / (1024 * 1024)
        self.results.append(result)

        logger.info(f"Memory: peak={result.memory_peak_mb:.2f}MB, current={result.memory_current_mb:.2f}MB")
        return result

    def benchmark_routing_performance(
        self,
        iterations: int = 1000,
    ) -> BenchmarkResult:
        """基准测试：任务路由器性能"""
        from app.ai.lnn.router.task_router import TaskRouter
        from app.ai.lnn.core import TaskInput

        router = TaskRouter()
        times = []

        task_descriptions = [
            "预测未来24小时的销售数据",
            "Check if the input meets quality standards",
            "分析用户评论的情感倾向",
            "预测设备故障概率",
            "分类产品质量等级",
        ]

        for i in range(iterations):
            desc = task_descriptions[i % len(task_descriptions)]
            task = TaskInput(
                task_description=desc,
                input_data=np.random.randn(10, 5),
            )

            start = time.perf_counter()
            _ = router.route(task)
            elapsed = (time.perf_counter() - start) * 1000
            times.append(elapsed)

        result = self._compute_stats("Task Router Performance", times, iterations)
        self.results.append(result)

        logger.info(f"Router: avg={result.avg_time_ms:.3f}ms, p95={result.p95_time_ms:.3f}ms")
        return result

    def benchmark_fusion_performance(
        self,
        iterations: int = 500,
    ) -> BenchmarkResult:
        """基准测试：结果融合性能"""
        from app.ai.lnn.fusion import DempsterShaferFusion
        from app.ai.lnn.core import InferenceResult, EngineType

        fusion = DempsterShaferFusion()
        times = []

        for _ in range(iterations):
            results = [
                InferenceResult(
                    prediction=np.random.randn(1)[0],
                    confidence=0.8 + np.random.rand() * 0.2,
                    engine_used=EngineType.LNN,
                    processing_time_ms=10.0,
                ),
                InferenceResult(
                    prediction=np.random.randn(1)[0],
                    confidence=0.7 + np.random.rand() * 0.3,
                    engine_used=EngineType.RULE,
                    processing_time_ms=5.0,
                ),
            ]

            start = time.perf_counter()
            _ = fusion.fuse(results)
            elapsed = (time.perf_counter() - start) * 1000
            times.append(elapsed)

        result = self._compute_stats("Fusion Performance", times, iterations)
        self.results.append(result)

        logger.info(f"Fusion: avg={result.avg_time_ms:.3f}ms")
        return result

    def _compute_stats(self, name: str, times: List[float], iterations: int) -> BenchmarkResult:
        """计算统计指标"""
        times_array = np.array(times)
        return BenchmarkResult(
            test_name=name,
            total_time_ms=float(np.sum(times_array)),
            avg_time_ms=float(np.mean(times_array)),
            min_time_ms=float(np.min(times_array)),
            max_time_ms=float(np.max(times_array)),
            p50_time_ms=float(np.percentile(times_array, 50)),
            p95_time_ms=float(np.percentile(times_array, 95)),
            p99_time_ms=float(np.percentile(times_array, 99)),
            throughput_per_sec=iterations / (np.sum(times_array) / 1000),
            iterations=iterations,
        )

    def _save_results(self) -> None:
        """保存基准测试结果"""
        os.makedirs(self.output_dir, exist_ok=True)

        timestamp = time.strftime("%Y%m%d_%H%M%S")
        output_path = os.path.join(self.output_dir, f"benchmark_{timestamp}.json")

        results_dict = [r.to_dict() for r in self.results]

        summary = {
            "timestamp": timestamp,
            "total_tests": len(results_dict),
            "results": results_dict,
        }

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)

        logger.info(f"Benchmark results saved to {output_path}")

    def print_summary(self) -> None:
        """打印基准测试摘要"""
        print("\n" + "=" * 80)
        print("LNN PERFORMANCE BENCHMARK SUMMARY")
        print("=" * 80)

        for result in self.results:
            print(f"\n[{result.test_name}]")
            print(f"  Avg: {result.avg_time_ms:.3f}ms | P50: {result.p50_time_ms:.3f}ms | P95: {result.p95_time_ms:.3f}ms | P99: {result.p99_time_ms:.3f}ms")
            print(f"  Throughput: {result.throughput_per_sec:.2f} samples/sec")
            if result.memory_peak_mb > 0:
                print(f"  Memory: peak={result.memory_peak_mb:.2f}MB, current={result.memory_current_mb:.2f}MB")

        print("\n" + "=" * 80)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    benchmark = LNNAccelerationBenchmark(output_dir="benchmarks")
    benchmark.run_all_benchmarks()
    benchmark.print_summary()
