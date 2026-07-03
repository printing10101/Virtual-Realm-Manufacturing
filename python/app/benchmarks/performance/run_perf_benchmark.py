"""自动化性能基准测试与回归检测框架。

提供：
- 性能基准测试主运行脚本
- 历史数据对比与回归检测
- Markdown/JSON格式报告生成
"""

from __future__ import annotations

import json
import logging
import os
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_THIS_DIR, "..", "..", ".."))

from app.benchmarks.performance.thresholds import (  # noqa: E402
    REGRESSION_THRESHOLDS,
    check_violations,
)
from app.benchmarks.performance.lnn_inference_bench import LNNPerfBenchmark  # noqa: E402
from app.benchmarks.performance.nc_generation_bench import NCGenerationBenchmark  # noqa: E402
from app.benchmarks.performance.drawing_parse_bench import DrawingParseBenchmark  # noqa: E402
from app.benchmarks.performance.api_bench import APIPerfBenchmark  # noqa: E402
from app.benchmarks.performance.database_bench import DatabasePerfBenchmark  # noqa: E402
from app.benchmarks.performance.business_logic_bench import BusinessLogicPerfBenchmark  # noqa: E402
from app.benchmarks.performance.concurrency_bench import ConcurrencyPerfBenchmark  # noqa: E402


@dataclass
class RegressionEntry:
    metric: str
    current: float
    previous: float
    change_pct: float
    status: str


@dataclass
class RegressionReport:
    timestamp: str = ""
    summary: str = ""
    entries: list[RegressionEntry] = field(default_factory=list)
    violations: list[dict[str, str]] = field(default_factory=list)
    has_regression: bool = False
    has_critical: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "summary": self.summary,
            "entries": [
                {
                    "metric": e.metric,
                    "current": e.current,
                    "previous": e.previous,
                    "change_pct": e.change_pct,
                    "status": e.status,
                }
                for e in self.entries
            ],
            "violations": self.violations,
            "has_regression": self.has_regression,
            "has_critical": self.has_critical,
        }

    def to_markdown(self) -> str:
        lines = [
            "# 性能基准测试报告",
            "",
            f"**生成时间**: {self.timestamp}",
            f"**状态**: {self.summary}",
            "",
            "## 回归检测结果",
            "",
            "| 指标 | 当前值 | 上次值 | 变化率 | 状态 |",
            "|------|--------|--------|--------|------|",
        ]
        for e in self.entries:
            status_icon = {
                "PASS": "[OK]",
                "WARNING": "[WARN]",
                "CRITICAL": "[CRIT]",
                "NEW": "[NEW]",
            }.get(e.status, "[?]")
            lines.append(
                f"| {e.metric} | {e.current:.3f} | {e.previous:.3f} | "
                f"{e.change_pct:+.1f}% | {status_icon} {e.status} |"
            )

        if self.violations:
            lines.append("")
            lines.append("## 阈值违规")
            lines.append("")
            for v in self.violations:
                lines.append(f"- [{v['status']}] **{v['metric']}**: {v['message']}")

        return "\n".join(lines)


class PerformanceBenchmarkRunner:
    """性能基准测试主运行器。"""

    def __init__(
        self,
        history_dir: str | None = None,
        output_dir: str | None = None,
    ) -> None:
        if history_dir is None:
            history_dir = os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                "history",
            )
        if output_dir is None:
            output_dir = os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                "history",
            )

        self.history_dir = Path(history_dir)
        self.output_dir = Path(output_dir)
        self.history_dir.mkdir(parents=True, exist_ok=True)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def run_all(self) -> RegressionReport:
        timestamp = time.strftime("%Y%m%d_%H%M%S")

        current_results: dict[str, float] = {}

        logger.info("=" * 60)
        logger.info("性能基准测试")
        logger.info("=" * 60)

        # [1/7] LNN推理性能测试
        logger.info("\n[1/7] LNN推理性能测试...")
        lnn = LNNPerfBenchmark()
        lnn.setup()
        single = lnn.run_single_inference()
        for k, v in single.items():
            current_results[k] = v
            logger.info(f"  {k}: {v}")

        batch10 = lnn.run_batch_10_inference()
        for k, v in batch10.items():
            current_results[k] = v
            logger.info(f"  {k}: {v}")

        batch50 = lnn.run_batch_50_inference()
        for k, v in batch50.items():
            current_results[k] = v
            logger.info(f"  {k}: {v}")

        batch100 = lnn.run_batch_100_inference()
        for k, v in batch100.items():
            current_results[k] = v
            logger.info(f"  {k}: {v}")

        gpu = lnn.run_gpu_single_inference()
        if gpu:
            for k, v in gpu.items():
                current_results[k] = v
                logger.info(f"  {k}: {v}")
        else:
            logger.info("  GPU: 不可用（跳过）")

        lnn_path = str(self.output_dir / f"lnn_inference_{timestamp}.json")
        lnn.save_results(lnn_path)
        logger.info(f"  -> {lnn_path}")

        # [2/7] NC代码生成全流程测试
        logger.info("\n[2/7] NC代码生成全流程测试...")
        nc = NCGenerationBenchmark()
        nc.setup()
        pipeline = nc.run_full_pipeline(n_parts=3)
        for k, v in pipeline.items():
            if isinstance(v, (int, float)):
                current_results[k] = v
                logger.info(f"  {k}: {v}")
            elif k == "bottlenecks" and v:
                logger.info(f"  瓶颈分析: {v}")
            elif k == "threshold_violations" and v:
                logger.info(f"  违规: {v}")

        nc_path = str(self.output_dir / f"nc_generation_{timestamp}.json")
        nc.save_results(nc_path)
        logger.info(f"  -> {nc_path}")

        # [3/7] 三视图解析性能测试
        logger.info("\n[3/7] 三视图解析性能测试...")
        dp = DrawingParseBenchmark()
        dp.setup()
        parse_results = dp.run_parse(n_iterations=5)
        for k, v in parse_results.items():
            if isinstance(v, (int, float)):
                current_results[k] = v
                logger.info(f"  {k}: {v}")

        dp_path = str(self.output_dir / f"drawing_parse_{timestamp}.json")
        dp.save_results(dp_path)
        logger.info(f"  -> {dp_path}")

        # [4/7] API接口性能测试
        logger.info("\n[4/7] API接口性能测试...")
        api = APIPerfBenchmark()
        api_results = api.run_all()
        for k, v in api_results.items():
            if isinstance(v, (int, float)):
                current_results[k] = v
                logger.info(f"  {k}: {v}")

        api_path = str(self.output_dir / f"api_performance_{timestamp}.json")
        api.save_results(api_path)
        logger.info(f"  -> {api_path}")

        # [5/7] 数据库性能测试
        logger.info("\n[5/7] 数据库性能测试...")
        db = DatabasePerfBenchmark()
        db_results = db.run_all()
        for k, v in db_results.items():
            if isinstance(v, (int, float)):
                current_results[k] = v
                logger.info(f"  {k}: {v}")

        db_path = str(self.output_dir / f"database_performance_{timestamp}.json")
        db.save_results(db_path)
        logger.info(f"  -> {db_path}")

        # [6/7] 业务逻辑性能测试
        logger.info("\n[6/7] 业务逻辑性能测试...")
        biz = BusinessLogicPerfBenchmark()
        biz_results = biz.run_all()
        for k, v in biz_results.items():
            if isinstance(v, (int, float)):
                current_results[k] = v
                logger.info(f"  {k}: {v}")

        biz_path = str(self.output_dir / f"business_logic_performance_{timestamp}.json")
        biz.save_results(biz_path)
        logger.info(f"  -> {biz_path}")

        # [7/7] 并发与压力测试
        logger.info("\n[7/7] 并发与压力测试...")
        conc = ConcurrencyPerfBenchmark()
        conc_results = conc.run_all()
        for k, v in conc_results.items():
            if isinstance(v, (int, float)):
                current_results[k] = v
                logger.info(f"  {k}: {v}")

        conc_path = str(self.output_dir / f"concurrency_performance_{timestamp}.json")
        conc.save_results(conc_path)
        logger.info(f"  -> {conc_path}")

        # Save current results
        current_path = self.output_dir / f"current_results_{timestamp}.json"
        with open(current_path, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
                    "results": current_results,
                },
                f,
                indent=2,
                ensure_ascii=False,
            )

        # Run regression check
        logger.info("\n" + "=" * 60)
        logger.info("回归检测")
        logger.info("=" * 60)

        report = check_regression(current_results, str(self.history_dir))

        report.timestamp = time.strftime("%Y-%m-%d %H:%M:%S")

        # Save report
        report_path = self.output_dir / f"regression_report_{timestamp}.md"
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(report.to_markdown())
        logger.info(f"\n报告已保存: {report_path}")

        report_json_path = self.output_dir / f"regression_report_{timestamp}.json"
        with open(report_json_path, "w", encoding="utf-8") as f:
            json.dump(report.to_dict(), f, indent=2, ensure_ascii=False)

        return report


def check_regression(
    current_results: dict[str, float],
    history_dir: str,
) -> RegressionReport:
    entries: list[RegressionEntry] = []
    violations = check_violations(current_results)

    history_path = _find_latest_history(str(history_dir))
    previous_results: dict[str, float] = {}

    if history_path and os.path.exists(history_path):
        try:
            with open(history_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            previous_results = data.get("results", {})
        except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError) as e:
            logger.warning(f"读取历史性能数据失败: {e}，使用空数据")
            previous_results = {}

    warning_pct = REGRESSION_THRESHOLDS["warning_pct"]
    critical_pct = REGRESSION_THRESHOLDS["critical_pct"]
    has_regression = False
    has_critical = False

    for metric, current in sorted(current_results.items()):
        previous = previous_results.get(metric)

        if previous is None or previous == 0:
            entries.append(
                RegressionEntry(
                    metric=metric,
                    current=current,
                    previous=0,
                    change_pct=0,
                    status="NEW",
                )
            )
            continue

        change_pct = (current - previous) / previous * 100

        # For metrics where lower is better, regression means increase
        if change_pct > critical_pct:
            status = "CRITICAL"
            has_regression = True
            has_critical = True
        elif change_pct > warning_pct:
            status = "WARNING"
            has_regression = True
        elif change_pct < -critical_pct:
            status = "IMPROVED"
        else:
            status = "PASS"

        entries.append(
            RegressionEntry(
                metric=metric,
                current=round(current, 3),
                previous=round(previous, 3),
                change_pct=round(change_pct, 1),
                status=status,
            )
        )

    # Determine summary
    if has_critical:
        summary = f"[CRIT] 检测到 {sum(1 for e in entries if e.status == 'CRITICAL')} 项严重性能回退"
    elif has_regression:
        summary = f"[WARN] 检测到 {sum(1 for e in entries if e.status == 'WARNING')} 项性能回退"
    else:
        summary = "[PASS] 未检测到性能回退"

    return RegressionReport(
        entries=entries,
        violations=violations,
        summary=summary,
        has_regression=has_regression,
        has_critical=has_critical,
    )


def _find_latest_history(history_dir: str) -> str | None:
    candidates = list(Path(history_dir).glob("current_results_*.json"))
    if not candidates:
        return None
    candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return str(candidates[0])


def main() -> None:
    runner = PerformanceBenchmarkRunner()
    report = runner.run_all()
    logger.info("\n" + report.to_markdown())


if __name__ == "__main__":
    main()
