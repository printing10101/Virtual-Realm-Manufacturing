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
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

if __package__ in (None, ""):
    import _bootstrap  # noqa: F401  # 脚本直跑时引导 engineering/python 入 sys.path

from app.benchmarks.performance.thresholds import (
    REGRESSION_THRESHOLDS,
    check_violations,
)
from app.benchmarks.performance.lnn_inference_bench import LNNPerfBenchmark
from app.benchmarks.performance.nc_generation_bench import NCGenerationBenchmark
from app.benchmarks.performance.drawing_parse_bench import DrawingParseBenchmark
from app.benchmarks.performance.api_bench import APIPerfBenchmark
from app.benchmarks.performance.database_bench import DatabasePerfBenchmark

# 阶段2 解耦改造：business_logic_bench 模块已迁移到 research/，
# 工程侧运行时若需调用完整业务逻辑基准测试，请在 research/ 环境中执行。
# 这里通过 try/except 提供降级保护，避免 import 失败导致整个基准测试框架不可用。
try:
    from app.benchmarks.performance.business_logic_bench import (
        BusinessLogicPerfBenchmark,
    )

    _HAS_BUSINESS_LOGIC_BENCH = True
except ImportError:
    BusinessLogicPerfBenchmark = None
    _HAS_BUSINESS_LOGIC_BENCH = False
from app.benchmarks.performance.concurrency_bench import ConcurrencyPerfBenchmark
from app.benchmarks.performance.world_model_bench import WorldModelPerfBenchmark
from app.benchmarks.performance.rl_agent_bench import RLAgentPerfBenchmark
from app.benchmarks.performance.closed_loop_bench import ClosedLoopPerfBenchmark


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
                f"| {e.metric} | {e.current:.3f} | {e.previous:.3f} | {e.change_pct:+.1f}% | {status_icon} {e.status} |"
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

        # [1/10] LNN推理性能测试
        logger.info("\n[1/10] LNN推理性能测试...")
        lnn = LNNPerfBenchmark()
        lnn.setup()
        single = lnn.run_single_inference()
        for k, v in single.items():
            current_results[k] = v
            logger.info("  %s: %s", k, v)

        batch10 = lnn.run_batch_10_inference()
        for k, v in batch10.items():
            current_results[k] = v
            logger.info("  %s: %s", k, v)

        batch50 = lnn.run_batch_50_inference()
        for k, v in batch50.items():
            current_results[k] = v
            logger.info("  %s: %s", k, v)

        batch100 = lnn.run_batch_100_inference()
        for k, v in batch100.items():
            current_results[k] = v
            logger.info("  %s: %s", k, v)

        gpu = lnn.run_gpu_single_inference()
        if gpu:
            for k, v in gpu.items():
                current_results[k] = v
                logger.info("  %s: %s", k, v)
        else:
            logger.info("  GPU: 不可用（跳过）")

        lnn_path = str(self.output_dir / f"lnn_inference_{timestamp}.json")
        lnn.save_results(lnn_path)
        logger.info("  -> %s", lnn_path)

        # [2/10] NC代码生成全流程测试
        logger.info("\n[2/10] NC代码生成全流程测试...")
        nc = NCGenerationBenchmark()
        nc.setup()
        pipeline = nc.run_full_pipeline(n_parts=3)
        for k, v in pipeline.items():
            if isinstance(v, (int, float)):
                current_results[k] = v
                logger.info("  %s: %s", k, v)
            elif k == "bottlenecks" and v:
                logger.info("  瓶颈分析: %s", v)
            elif k == "threshold_violations" and v:
                logger.info("  违规: %s", v)

        nc_path = str(self.output_dir / f"nc_generation_{timestamp}.json")
        nc.save_results(nc_path)
        logger.info("  -> %s", nc_path)

        # [3/10] 三视图解析性能测试
        logger.info("\n[3/10] 三视图解析性能测试...")
        dp = DrawingParseBenchmark()
        dp.setup()
        parse_results = dp.run_parse(n_iterations=5)
        for k, v in parse_results.items():
            if isinstance(v, (int, float)):
                current_results[k] = v
                logger.info("  %s: %s", k, v)

        dp_path = str(self.output_dir / f"drawing_parse_{timestamp}.json")
        dp.save_results(dp_path)
        logger.info("  -> %s", dp_path)

        # [4/10] API接口性能测试
        logger.info("\n[4/10] API接口性能测试...")
        api = APIPerfBenchmark()
        api_results = api.run_all()
        for k, v in api_results.items():
            if isinstance(v, (int, float)):
                current_results[k] = v
                logger.info("  %s: %s", k, v)

        api_path = str(self.output_dir / f"api_performance_{timestamp}.json")
        api.save_results(api_path)
        logger.info("  -> %s", api_path)

        # [5/10] 数据库性能测试
        logger.info("\n[5/10] 数据库性能测试...")
        db = DatabasePerfBenchmark()
        db_results = db.run_all()
        for k, v in db_results.items():
            if isinstance(v, (int, float)):
                current_results[k] = v
                logger.info("  %s: %s", k, v)

        db_path = str(self.output_dir / f"database_performance_{timestamp}.json")
        db.save_results(db_path)
        logger.info("  -> %s", db_path)

        # [6/10] 业务逻辑性能测试
        # 阶段2 解耦改造：business_logic_bench 已迁移到 research/，
        # 工程侧无此模块时跳过此基准测试项，不影响其他项的执行。
        if _HAS_BUSINESS_LOGIC_BENCH:
            logger.info("\n[6/10] 业务逻辑性能测试...")
            biz = BusinessLogicPerfBenchmark()
            biz_results = biz.run_all()
            for k, v in biz_results.items():
                if isinstance(v, (int, float)):
                    current_results[k] = v
                    logger.info("  %s: %s", k, v)

            biz_path = str(self.output_dir / f"business_logic_performance_{timestamp}.json")
            biz.save_results(biz_path)
            logger.info("  -> %s", biz_path)
        else:
            logger.info("\n[6/10] 业务逻辑性能测试... 跳过（business_logic_bench 已迁移到 research/）")

        # [7/10] 并发与压力测试
        logger.info("\n[7/10] 并发与压力测试...")
        conc = ConcurrencyPerfBenchmark()
        conc_results = conc.run_all()
        for k, v in conc_results.items():
            if isinstance(v, (int, float)):
                current_results[k] = v
                logger.info("  %s: %s", k, v)

        conc_path = str(self.output_dir / f"concurrency_performance_{timestamp}.json")
        conc.save_results(conc_path)
        logger.info("  -> %s", conc_path)

        # [8/10] 世界模型轨迹预测性能测试（阶段 8 新增）
        logger.info("\n[8/10] 世界模型轨迹预测性能测试...")
        wm = WorldModelPerfBenchmark()
        wm.setup()
        wm_single = wm.run_single_prediction()
        for k, v in wm_single.items():
            if isinstance(v, (int, float)):
                current_results[k] = v
                logger.info("  %s: %s", k, v)

        wm_horizon = wm.run_horizon_scaling()
        for k, v in wm_horizon.items():
            if isinstance(v, (int, float)):
                current_results[k] = v
                logger.info("  %s: %s", k, v)

        wm_batch = wm.run_batch_prediction()
        for k, v in wm_batch.items():
            if isinstance(v, (int, float)):
                current_results[k] = v
                logger.info("  %s: %s", k, v)

        wm_plugin = wm.run_plugin_execute()
        for k, v in wm_plugin.items():
            if isinstance(v, (int, float)):
                current_results[k] = v
                logger.info("  %s: %s", k, v)

        wm_cache = wm.run_model_cache_hit()
        for k, v in wm_cache.items():
            if isinstance(v, (int, float)):
                current_results[k] = v
                logger.info("  %s: %s", k, v)

        wm_path = str(self.output_dir / f"world_model_{timestamp}.json")
        wm.save_results(wm_path)
        logger.info("  -> %s", wm_path)

        # [9/10] RL agent 决策 + SafetyShield 性能测试（阶段 8 新增）
        logger.info("\n[9/10] RL agent 决策 + SafetyShield 性能测试...")
        rl = RLAgentPerfBenchmark()
        rl.setup()
        rl_single = rl.run_single_decision()
        for k, v in rl_single.items():
            if isinstance(v, (int, float)):
                current_results[k] = v
                logger.info("  %s: %s", k, v)

        rl_shield = rl.run_safety_shield_filter()
        for k, v in rl_shield.items():
            if isinstance(v, (int, float)):
                current_results[k] = v
                logger.info("  %s: %s", k, v)

        rl_batch = rl.run_batch_decisions()
        for k, v in rl_batch.items():
            if isinstance(v, (int, float)):
                current_results[k] = v
                logger.info("  %s: %s", k, v)

        rl_cache = rl.run_policy_cache_hit()
        for k, v in rl_cache.items():
            if isinstance(v, (int, float)):
                current_results[k] = v
                logger.info("  %s: %s", k, v)

        rl_violation = rl.run_safety_violation_rate()
        for k, v in rl_violation.items():
            if isinstance(v, (int, float)):
                current_results[k] = v
                logger.info("  %s: %s", k, v)

        rl_path = str(self.output_dir / f"rl_agent_{timestamp}.json")
        rl.save_results(rl_path)
        logger.info("  -> %s", rl_path)

        # [10/10] 闭环加工优化工作流端到端性能测试（阶段 8 新增）
        logger.info("\n[10/10] 闭环加工优化工作流端到端性能测试...")
        cl = ClosedLoopPerfBenchmark()
        cl.setup()
        cl_pipeline = cl.run_full_pipeline()
        for k, v in cl_pipeline.items():
            if isinstance(v, (int, float)):
                current_results[k] = v
                logger.info("  %s: %s", k, v)
            elif k == "cl_bottlenecks" and v:
                logger.info("  闭环瓶颈: %s", v)
            elif k == "cl_threshold_violations" and v:
                logger.info("  闭环违规: %s", v)

        cl_breakdown = cl.run_node_breakdown()
        for k, v in cl_breakdown.items():
            if isinstance(v, (int, float)):
                current_results[k] = v
                logger.info("  %s: %s", k, v)

        cl_throughput = cl.run_throughput()
        for k, v in cl_throughput.items():
            if isinstance(v, (int, float)):
                current_results[k] = v
                logger.info("  %s: %s", k, v)

        cl_path = str(self.output_dir / f"closed_loop_{timestamp}.json")
        cl.save_results(cl_path)
        logger.info("  -> %s", cl_path)

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
        logger.info("\n报告已保存: %s", report_path)

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
            logger.warning("读取历史性能数据失败: %s，使用空数据", e)
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
