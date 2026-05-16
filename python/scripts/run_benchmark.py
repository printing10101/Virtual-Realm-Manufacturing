"""
运行LNN基准测试 - 便捷启动脚本

使用方法：
    cd python
    python scripts/run_benchmark.py

或直接：
    python python/scripts/run_benchmark.py
"""

import os
import sys
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

# 切换到项目根目录
os.chdir(project_root)

print(f"Project root: {project_root}")
print(f"Python path: {sys.path[0]}")
print("=" * 60)

# 运行基准测试
from app.ai.lnn.tests.benchmark_lnn import LNNAccelerationBenchmark

if __name__ == "__main__":
    import logging

    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
    )

    benchmark = LNNAccelerationBenchmark(output_dir="benchmarks")
    benchmark.run_all_benchmarks()
    benchmark.print_summary()
