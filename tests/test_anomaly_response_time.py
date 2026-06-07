"""响应时间测试。

测试方法：模拟各类异常场景，记录从异常发生到系统告警的时间间隔。

性能目标：
- 平均响应时间 < 1秒（1000ms）
- 95%场景响应时间 < 1.2秒（1200ms）

测试脚本：tests/test_anomaly_response_time.py
"""

import sys
import os
import unittest
import time
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "python"))

import torch
from app.ai.vjepa_machining.config import VJEPAMachiningConfig
from app.ai.vjepa_machining.model import VJEPAMachiningModel
from app.ai.vjepa_machining.inference import VJEPAInference


class TestAnomalyResponseTime(unittest.TestCase):
    """异常检测响应时间测试套件。"""

    @classmethod
    def setUpClass(cls):
        cls.config = VJEPAMachiningConfig()
        cls.model = VJEPAMachiningModel(cls.config)
        cls.device = "cuda" if torch.cuda.is_available() else "cpu"
        cls.model = cls.model.to(cls.device)
        cls.model.eval()
        cls.inference = VJEPAInference(cls.model, cls.config, cls.device)

    def test_01_inference_latency(self):
        """测试单次推理延迟。"""
        print(f"\n单次推理延迟测试 (device={self.device}):")

        video = torch.randn(1, 3, self.config.num_frames,
                            *self.config.frame_size, device=self.device)
        action = torch.zeros(1, dtype=torch.long, device=self.device)

        # 预热
        for _ in range(5):
            _ = self.inference.infer_clip(video, 0)

        # 测量
        num_tests = 50
        times = []
        for _ in range(num_tests):
            start = time.perf_counter()
            _ = self.inference.infer_clip(video, 0)
            if self.device == "cuda":
                torch.cuda.synchronize()
            times.append((time.perf_counter() - start) * 1000)

        avg_time = np.mean(times)
        std_time = np.std(times)
        p50_time = np.percentile(times, 50)
        p95_time = np.percentile(times, 95)
        p99_time = np.percentile(times, 99)
        max_time = np.max(times)
        min_time = np.min(times)

        print(f"  样本数: {num_tests}")
        print(f"  平均延迟: {avg_time:.2f}ms (目标: < 1000ms)")
        print(f"  标准差: {std_time:.2f}ms")
        print(f"  P50: {p50_time:.2f}ms")
        print(f"  P95: {p95_time:.2f}ms (目标: < 1200ms)")
        print(f"  P99: {p99_time:.2f}ms")
        print(f"  Min: {min_time:.2f}ms")
        print(f"  Max: {max_time:.2f}ms")

        self.assertLess(avg_time, 1000, f"平均延迟 {avg_time:.2f}ms 超过 1000ms 阈值")
        self.assertLess(p95_time, 1200, f"P95延迟 {p95_time:.2f}ms 超过 1200ms 阈值")

    def test_02_end_to_end_response_time(self):
        """测试端到端响应时间（从异常发生到告警输出）。"""
        print(f"\n端到端响应时间测试:")

        # 模拟：从视频帧进入缓冲区到异常检测结果输出
        num_frames = 16
        frame_size = (224, 224)
        num_tests = 30

        response_times = []
        for _ in range(num_tests):
            # 模拟16帧视频
            video = torch.randn(1, 3, num_frames, *frame_size, device=self.device)
            action = torch.zeros(1, dtype=torch.long, device=self.device)

            start = time.perf_counter()
            result = self.inference.infer_clip(video, 0)

            # 模拟告警处理
            anomaly_prob = float(result["anomaly_prob"].squeeze())
            severity = "normal" if anomaly_prob < 0.5 else "anomaly"

            if self.device == "cuda":
                torch.cuda.synchronize()

            elapsed = (time.perf_counter() - start) * 1000
            response_times.append(elapsed)

        avg_response = np.mean(response_times)
        p95_response = np.percentile(response_times, 95)

        print(f"  样本数: {num_tests}")
        print(f"  平均端到端响应: {avg_response:.2f}ms")
        print(f"  P95端到端响应: {p95_response:.2f}ms")

        self.assertLess(avg_response, 1000,
                        f"平均端到端响应 {avg_response:.2f}ms 超过 1000ms")

    def test_03_throughput(self):
        """测试推理吞吐量。"""
        print(f"\n推理吞吐量测试:")

        num_samples = 50
        batch_sizes = [1, 4, 8]

        for bs in batch_sizes:
            video = torch.randn(bs, 3, self.config.num_frames,
                                *self.config.frame_size, device=self.device)
            action = torch.zeros(bs, dtype=torch.long, device=self.device)

            # 预热
            for _ in range(5):
                _ = self.model.infer(video, action)

            # 计时
            if self.device == "cuda":
                torch.cuda.synchronize()

            times = []
            for _ in range(num_samples):
                start = time.perf_counter()
                _ = self.model.infer(video, action)
                if self.device == "cuda":
                    torch.cuda.synchronize()
                times.append((time.perf_counter() - start) * 1000)

            avg = np.mean(times)
            per_sample = avg / bs
            throughput = 1000.0 / per_sample

            print(f"  Batch {bs:2d}: avg={avg:.2f}ms, per_sample={per_sample:.2f}ms, "
                  f"throughput={throughput:.1f} samples/s")

            if bs == 1:
                self.assertLess(per_sample, 1000,
                                f"单样本推理时间 {per_sample:.2f}ms 超过 1000ms")


if __name__ == "__main__":
    unittest.main(verbosity=2)