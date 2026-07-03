"""集成测试运行器。

自动发现并执行所有集成测试，生成完整的测试报告。

用法：
    python tests/run_integration_tests.py              # 运行所有集成测试
    python tests/run_integration_tests.py --scenario 1 # 仅运行场景1
    python tests/run_integration_tests.py --quick       # 快速模式（减少迭代次数）
    python tests/run_integration_tests.py --report      # 生成HTML报告
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

# 添加项目根目录到Python路径
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
PYTHON_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PYTHON_DIR))

# 输出目录
REPORT_DIR = PROJECT_ROOT / "test-reports"
REPORT_DIR.mkdir(parents=True, exist_ok=True)


def run_test_suite(
    test_paths: list[str],
    markers: list[str] | None = None,
    extra_args: list[str] | None = None,
    html_report: str | None = None,
) -> tuple[int, str, float]:
    """执行测试套件并返回(退出码, 输出, 耗时).

    Args:
        test_paths: 测试文件路径列表
        markers: pytest标记过滤
        extra_args: 额外的pytest参数
        html_report: HTML报告路径
    """
    cmd = [sys.executable, "-m", "pytest"]
    cmd.extend(test_paths)

    if markers:
        marker_expr = " or ".join(markers)
        cmd.extend(["-m", marker_expr])

    cmd.extend(["-v", "--tb=short", "--durations=10"])
    cmd.append("--no-header")

    # 禁用覆盖率以避免性能开销
    cmd.extend(["-p", "no:cacheprovider"])

    if html_report:
        cmd.extend(["--html", html_report, "--self-contained-html"])

    if extra_args:
        cmd.extend(extra_args)

    start = time.time()
    try:
        result = subprocess.run(
            cmd,
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            timeout=600,  # 10分钟超时
        )
        elapsed = time.time() - start
        return result.returncode, result.stdout, elapsed
    except subprocess.TimeoutExpired:
        elapsed = time.time() - start
        return -1, "测试执行超时（>10分钟）", elapsed


def generate_summary_report(results: list[dict]) -> str:
    """生成Markdown格式的测试摘要报告."""
    lines = [
        "# 灵境制造 - 集成测试报告",
        "",
        f"**生成时间**: {time.strftime('%Y-%m-%d %H:%M:%S')}",
        f"**测试环境**: Python {sys.version.split()[0]}",
        "",
        "---",
        "",
        "## 测试结果汇总",
        "",
    ]

    total_tests = sum(r.get("total", 0) for r in results)
    total_passed = sum(r.get("passed", 0) for r in results)
    total_failed = sum(r.get("failed", 0) for r in results)
    total_errors = sum(r.get("errors", 0) for r in results)

    pass_rate = (total_passed / total_tests * 100) if total_tests > 0 else 0

    lines.append("| 指标 | 数值 |")
    lines.append("|------|------|")
    lines.append(f"| 测试总数 | {total_tests} |")
    lines.append(f"| 通过 | {total_passed} |")
    lines.append(f"| 失败 | {total_failed} |")
    lines.append(f"| 错误 | {total_errors} |")
    lines.append(f"| 通过率 | {pass_rate:.1f}% |")
    lines.append("")

    # 通过标准检查
    lines.append("## 通过标准检查")
    lines.append("")
    checks = {
        "测试通过率 >= 95%": pass_rate >= 95.0,
        "无严重错误": total_errors == 0,
    }
    for check, result in checks.items():
        status = ":white_check_mark: 通过" if result else ":x: 未通过"
        lines.append(f"- {check}: {status}")
    lines.append("")

    # 各场景结果
    lines.append("## 各场景测试结果")
    lines.append("")
    for r in results:
        name = r.get("name", "未知场景")
        pct = r.get("pass_rate", 0)
        status = ":white_check_mark:" if pct >= 95 else ":warning:" if pct >= 80 else ":x:"
        lines.append(f"- {status} **{name}**: {r.get('passed', 0)}/{r.get('total', 0)} ({pct:.1f}%)")
    lines.append("")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="灵境制造集成测试运行器")
    parser.add_argument("--scenario", "-s", type=int, choices=[1, 2, 3], help="仅运行指定场景")
    parser.add_argument("--quick", "-q", action="store_true", help="快速模式（减少迭代次数）")
    parser.add_argument("--report", "-r", action="store_true", help="生成HTML测试报告")
    parser.add_argument("--markers", "-m", nargs="+", help="按pytest标记过滤")
    args = parser.parse_args()

    test_dir = PYTHON_DIR / "tests" / "integration"

    # 确定测试文件
    if args.scenario == 1:
        test_files = [str(test_dir / "test_scenario1_3view_to_nc.py")]
    elif args.scenario == 2:
        test_files = [str(test_dir / "test_scenario2_realtime_monitoring.py")]
    elif args.scenario == 3:
        test_files = [str(test_dir / "test_scenario3_process_consultation.py")]
    else:
        test_files = [
            str(test_dir / "test_scenario1_3view_to_nc.py"),
            str(test_dir / "test_scenario2_realtime_monitoring.py"),
            str(test_dir / "test_scenario3_process_consultation.py"),
            str(test_dir / "test_e2e_latency.py"),
            str(test_dir / "test_success_rate.py"),
            str(test_dir / "test_fault_recovery.py"),
            str(test_dir / "test_resource_usage.py"),
        ]

    markers = args.markers or ["integration"]

    extra_args = []
    if args.quick:
        extra_args.append("-x")  # 首次失败即停止

    html_report = None
    if args.report:
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        html_report = str(REPORT_DIR / f"integration_test_report_{timestamp}.html")

    print("=" * 72)
    print("  灵境制造 - 集成测试执行")
    print("=" * 72)
    print(f"测试文件: {len(test_files)} 个")
    print(f"标记过滤: {markers}")
    print(f"HTML报告: {html_report or '不生成'}")
    print("=" * 72)
    print()

    # 执行测试
    exit_code, output, elapsed = run_test_suite(
        test_paths=test_files,
        markers=markers,
        extra_args=extra_args,
        html_report=html_report,
    )

    # 输出结果
    print(output)

    print("-" * 72)
    print(f"执行耗时: {elapsed:.1f}秒")
    print(f"退出码: {exit_code}")

    # 生成摘要报告
    # 解析输出获取统计
    import re
    match = re.search(r"(\d+)\s+passed", output)
    passed = int(match.group(1)) if match else 0
    match = re.search(r"(\d+)\s+failed", output)
    failed = int(match.group(1)) if match else 0
    match = re.search(r"(\d+)\s+errors?", output)
    errors = int(match.group(1)) if match else 0

    results = [{
        "name": "集成测试",
        "total": passed + failed + errors,
        "passed": passed,
        "failed": failed,
        "errors": errors,
        "pass_rate": (passed / (passed + failed + errors) * 100) if (passed + failed + errors) > 0 else 0,
    }]

    summary = generate_summary_report(results)
    summary_path = REPORT_DIR / "integration_test_summary.md"
    summary_path.write_text(summary, encoding="utf-8")

    print()
    print(f"摘要报告已生成: {summary_path}")
    if html_report:
        print(f"HTML报告已生成: {html_report}")

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
