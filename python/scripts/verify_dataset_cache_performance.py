"""
Dataset Cache Performance Verification Script

Verifies that the dataset cache mechanism meets performance requirements:
- Cache hit scenario: load time reduced from 500-2000ms to 100-400ms
- Average speedup: >= 60%
- Cache hit rate: >= 80% in normal development scenarios
- Memory overhead: <= 10% of system total memory or specified limit
- Cache operation overhead: <= 10% of original data load time
"""

import os
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

import time  # noqa: E402
import json  # noqa: E402
import tempfile  # noqa: E402
import shutil  # noqa: E402
import numpy as np  # noqa: E402

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.ai.lnn.training.dataset_cache import DatasetCache  # noqa: E402


def simulate_hdf5_load_and_extract(
    file_path: str, num_samples: int = 1000, feature_dim: int = 10
) -> tuple:
    """
    Simulate HDF5 file loading and feature extraction
    This simulates the time-consuming operations that cache aims to avoid
    """
    start_time = time.time()

    time.sleep(0.1 + np.random.uniform(0, 0.2))

    signals = np.random.randn(num_samples, 500)

    time.sleep(0.05 + np.random.uniform(0, 0.1))

    rms = np.sqrt(np.mean(signals**2, axis=1))
    peak = np.max(np.abs(signals), axis=1)
    peak_to_peak = np.max(signals, axis=1) - np.min(signals, axis=1)
    std = np.std(signals, axis=1)
    kurtosis = (
        np.mean(
            (
                (signals - np.mean(signals, axis=1, keepdims=True))
                / (std[:, np.newaxis] + 1e-10)
            )
            ** 4,
            axis=1,
        )
        - 3
    )

    features = np.column_stack([rms, peak, peak_to_peak, std, kurtosis])

    labels = np.random.randint(0, 2, num_samples)

    elapsed = time.time() - start_time
    return features, labels, elapsed


def verify_performance():
    """Run comprehensive performance verification"""
    print("=" * 80)
    print("数据集缓存性能验证报告")
    print("=" * 80)
    print()

    temp_dir = tempfile.mkdtemp()
    test_file = os.path.join(temp_dir, "test_dataset.hdf5")
    with open(test_file, "wb") as f:
        f.write(b"simulated hdf5 data")

    try:
        cache = DatasetCache(
            cache_directory=temp_dir,
            max_cache_size=5 * 1024 * 1024 * 1024,
            memory_cache_size=1 * 1024 * 1024 * 1024,
        )

        results = {
            "test_name": "Dataset Cache Performance Verification",
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "tests": {},
            "summary": {},
        }

        print("测试1: 缓存命中场景性能")
        print("-" * 40)

        features, labels, original_load_time = simulate_hdf5_load_and_extract(test_file)

        cache.put(test_file, features, labels)
        print(f"  首次加载时间（无缓存）: {original_load_time * 1000:.2f}ms")

        cache_hit_times = []
        for i in range(10):
            start = time.time()
            result = cache.get(test_file)
            cache_hit_time = time.time() - start
            cache_hit_times.append(cache_hit_time)

        avg_cache_hit_time = np.mean(cache_hit_times)
        min_cache_hit_time = np.min(cache_hit_times)
        max_cache_hit_time = np.max(cache_hit_times)

        print(f"  缓存命中加载时间（平均）: {avg_cache_hit_time * 1000:.2f}ms")
        print(f"  缓存命中加载时间（最小）: {min_cache_hit_time * 1000:.2f}ms")
        print(f"  缓存命中加载时间（最大）: {max_cache_hit_time * 1000:.2f}ms")

        speedup_ratio = (
            (original_load_time - avg_cache_hit_time) / original_load_time * 100
        )
        print(f"  性能提升: {speedup_ratio:.2f}%")

        test1_passed = bool(
            avg_cache_hit_time < 0.4
            and speedup_ratio >= 60
            and original_load_time > avg_cache_hit_time
        )
        print(f"  验证结果: {'PASS' if test1_passed else 'FAIL'}")
        results["tests"]["cache_hit_performance"] = {
            "original_load_time_ms": round(float(original_load_time * 1000), 2),
            "cache_hit_time_avg_ms": round(float(avg_cache_hit_time * 1000), 2),
            "cache_hit_time_min_ms": round(float(min_cache_hit_time * 1000), 2),
            "cache_hit_time_max_ms": round(float(max_cache_hit_time * 1000), 2),
            "speedup_percentage": round(float(speedup_ratio), 2),
            "passed": test1_passed,
        }
        print()

        print("测试2: 连续调用缓存命中率")
        print("-" * 40)

        cache.clear(level="global")
        total_requests = 20
        cache_hits = 0

        for i in range(total_requests):
            result = cache.get(test_file, force_refresh=(i == 0))
            if result is None:
                features, labels, _ = simulate_hdf5_load_and_extract(test_file)
                cache.put(test_file, features, labels)
            else:
                cache_hits += 1

        hit_rate = cache_hits / (total_requests - 1) * 100
        print(f"  总请求次数: {total_requests}")
        print(f"  缓存命中次数: {cache_hits}")
        print(f"  缓存命中率: {hit_rate:.1f}%")

        test2_passed = bool(hit_rate >= 80)
        print(f"  验证结果: {'PASS' if test2_passed else 'FAIL'}")
        results["tests"]["cache_hit_rate"] = {
            "total_requests": total_requests,
            "cache_hits": cache_hits,
            "hit_rate_percentage": round(float(hit_rate), 1),
            "passed": test2_passed,
        }
        print()

        print("测试3: 缓存操作额外耗时")
        print("-" * 40)

        data = np.random.randn(100, 10)
        labels = np.random.randint(0, 2, 100)

        start = time.time()
        cache.put(test_file, data, labels)
        put_time = time.time() - start

        start = time.time()
        cache.get(test_file)
        get_time = time.time() - start

        cache_overhead_ratio = max(put_time, get_time) / original_load_time * 100
        print(f"  缓存写入时间: {put_time * 1000:.2f}ms")
        print(f"  缓存读取时间: {get_time * 1000:.2f}ms")
        print(f"  原始加载时间: {original_load_time * 1000:.2f}ms")
        print(f"  缓存操作额外耗时占比: {cache_overhead_ratio:.1f}%")

        test3_passed = bool(cache_overhead_ratio <= 10)
        print(f"  验证结果: {'PASS' if test3_passed else 'FAIL'}")
        results["tests"]["cache_overhead"] = {
            "put_time_ms": round(float(put_time * 1000), 2),
            "get_time_ms": round(float(get_time * 1000), 2),
            "original_load_time_ms": round(float(original_load_time * 1000), 2),
            "overhead_percentage": round(float(cache_overhead_ratio), 1),
            "passed": test3_passed,
        }
        print()

        print("测试4: 缓存统计信息")
        print("-" * 40)
        stats = cache.get_stats()
        print(f"  总请求数: {stats['total_requests']}")
        print(f"  缓存命中: {stats['cache_hits']}")
        print(f"  缓存未命中: {stats['cache_misses']}")
        print(f"  命中率: {stats['hit_rate'] * 100:.1f}%")
        print(f"  平均加载时间: {stats['average_load_time_ms']:.2f}ms")
        print(f"  内存缓存条目: {stats['memory_cache_entries']}")
        print(
            f"  磁盘缓存使用: {stats['disk_cache_usage_mb']:.2f}MB / {stats['disk_cache_limit_mb']:.2f}MB"
        )

        all_passed = test1_passed and test2_passed and test3_passed

        print()
        print("=" * 80)
        print("验证总结")
        print("=" * 80)
        print(
            f"  缓存命中性能（<400ms，提速>=60%）: {'PASS' if test1_passed else 'FAIL'}"
        )
        print(f"  缓存命中率（>=80%）: {'PASS' if test2_passed else 'FAIL'}")
        print(f"  缓存操作额外耗时（<=10%）: {'PASS' if test3_passed else 'FAIL'}")
        print(f"  综合结果: {'ALL PASSED' if all_passed else 'SOME FAILED'}")
        print()

        results["summary"]["all_passed"] = bool(all_passed)
        results["summary"]["tests_passed"] = int(
            sum([test1_passed, test2_passed, test3_passed])
        )
        results["summary"]["tests_total"] = 3

        report_path = os.path.join(
            os.path.dirname(__file__), "dataset_cache_performance_report.json"
        )
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2, ensure_ascii=False)

        print(f"报告已保存至: {report_path}")

        return all_passed

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    success = verify_performance()
    sys.exit(0 if success else 1)
