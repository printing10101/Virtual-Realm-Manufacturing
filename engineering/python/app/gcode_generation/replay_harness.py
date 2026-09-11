"""灰度重放工具（Phase 0 自进化 · M5）。

把「基线 → 改动 → 回归门控」固化成可复用操作闭环：

1. ``prepare``：在指定目录生成确定性种子输入集（3 例：稳定成功 /
   不稳定特征失败 / ChatterReport 拒载失败），作为重放基准输入；
2. ``run``：对固定输入集重放真实 pipeline（真 ChatterReportLoader →
   真 GeneratorAdapter/GCodeGenerator → 真 SafetyValidator），案例库
   指向隔离的灰度 DB（``FAILURE_CASES_DB``），产出该轮 stats 报表；
3. ``gate``：取基线库与候选库两份 stats，调用 ``regression_gate``
   出门控判定。

适用对象：任何会影响生成结果的改动——LLM 提示词（未来接入参数
推荐时）、切削参数表、安全校验规则、后处理器逻辑等。当前生成链路
为模板化生成（无 LLM 提示词），本工具先行固化流程与积累样本机制。

诚实边界：
- 样本 < ``GateThresholds.min_samples`` 时门控判 inconclusive，
  不武断放行/拦截；
- 种子输入集是「合成但真实合法」的输入（真实走完整管道），非生产
  流量；生产流量积累后应以真实任务分布替换/扩充种子集。

CLI（在 engineering/python 目录下运行）::

    python -m app.gcode_generation.replay_harness prepare <dir>
    python -m app.gcode_generation.replay_harness run <dir> <db> [--work-dir <dir>]
    python -m app.gcode_generation.replay_harness gate <baseline_db> <candidate_db>
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.config.gcode_generation import GCodeGenerationConfig
from app.gcode_generation.failure_case_store import (
    FailureCaseStore,
    reset_failure_case_store,
)
from app.gcode_generation.pipeline import GCodeGenerationPipeline
from app.gcode_generation.regression_gate import (
    GateResult,
    GateThresholds,
    evaluate_regression,
)

logger = logging.getLogger(__name__)

__all__ = [
    "ReplayCase",
    "write_seed_input_set",
    "run_replay",
    "gate_from_dbs",
    "main",
]

_CONTROLLER = "fanuc_0i"
_MATERIAL = "45#钢"


@dataclass(frozen=True)
class ReplayCase:
    """一个重放案例（ChatterReport + OperationPlan JSON 对）。"""

    case_id: str
    chatter_path: Path
    plan_path: Path
    expected_outcome: str  # success / failure（注释性预期，不参与判定）
    expected_hint: str  # 预期失败来源/错误码（便于人工核对）


# ----------------------------------------------------------------------
# 种子输入集（确定性）
# ----------------------------------------------------------------------

_PLANE_FEATURE = {
    "feature_id": "plane_top",
    "feature_type": "plane",
    "material_id": "steel_45",
    "spindle_rpm": 1800.0,
    "axial_depth_mm": 1.0,
    "limit_depth_mm": 5.0,
    "stable": True,
    "stability_margin": 0.8,
    "method": "analytical",
    "ltc_active": False,
    "confidence": 0.9,
}

_HOLE_FEATURE_STABLE = {
    "feature_id": "hole_d10",
    "feature_type": "hole",
    "material_id": "steel_45",
    "spindle_rpm": 1200.0,
    "axial_depth_mm": 12.0,
    "limit_depth_mm": 20.0,
    "stable": True,
    "stability_margin": 0.6,
    "method": "analytical",
    "ltc_active": False,
    "confidence": 0.85,
}

_HOLE_FEATURE_UNSTABLE = {
    **_HOLE_FEATURE_STABLE,
    "feature_id": "hole_d20",
    "axial_depth_mm": 22.0,
    "limit_depth_mm": 15.0,
    "stable": False,
    "stability_margin": -0.4,
    "confidence": 0.3,
}

_PLANE_OP = {
    "seq": 1,
    "name": "面铣顶面",
    "feature_name": "plane_top",
    "machining_method": "平面铣削",
    "surface": "top",
    "tolerance_grade": "IT8",
    "tool_type": "endmill_d50",
    "cutting_params": {
        "material": "steel",
        "tool_diameter": 50.0,
        "recommended_feed": "0.15 mm/r",
        "recommended_speed": "120 m/min",
        "geometry": {"x": 0.0, "y": 0.0, "z_depth": 1.0, "length": 100.0, "width": 80.0},
    },
    "estimated_time_min": 2.0,
    "notes": "replay seed op",
}

_HOLE_OP = {
    "seq": 2,
    "name": "钻孔",
    "feature_name": "hole_d10",
    "machining_method": "钻孔",
    "surface": "top",
    "tolerance_grade": "IT9",
    "tool_type": "drill_d10",
    "cutting_params": {
        "material": "steel",
        "tool_diameter": 10.0,
        "recommended_feed": "0.12 mm/r",
        "recommended_speed": "80 m/min",
        "geometry": {"x": 30.0, "y": 30.0, "z_depth": 12.0},
    },
    "estimated_time_min": 1.0,
    "notes": "replay seed op",
}

_HOLE_D20_OP = {
    **_HOLE_OP,
    "seq": 1,
    "name": "钻孔深孔",
    "feature_name": "hole_d20",
    "tool_type": "drill_d20",
    "cutting_params": {
        **_HOLE_OP["cutting_params"],
        "tool_diameter": 20.0,
        "geometry": {"x": 50.0, "y": 50.0, "z_depth": 22.0},
    },
}

_SETUPS = [{"name": "平口钳装夹", "surface": "top", "fixture_type": "vise"}]


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def write_seed_input_set(target_dir: Path) -> list[ReplayCase]:
    """生成确定性种子输入集（3 例），返回案例清单。

    - case_a_stable：全稳定（铣平面 + 钻孔）→ 预期 success；
    - case_b_unstable：hole_d20 切深超限（stable=False）→ 预期
      UNSTABLE_FEATURES 失败；
    - case_c_rejected：ChatterReport task_status != SUCCEEDED → 预期
      ChatterReportLoadError 失败。
    """
    target_dir = Path(target_dir)
    cases: list[ReplayCase] = []

    # case A：全稳定 → success
    _write_json(
        target_dir / "case_a_stable" / "chatter_report.json",
        {
            "task_id": "replay-case-a",
            "task_status": "succeeded",
            "material_id": "steel_45",
            "prediction_method": "analytical",
            "feature_results": [_PLANE_FEATURE, _HOLE_FEATURE_STABLE],
        },
    )
    _write_json(
        target_dir / "case_a_stable" / "operation_plan.json",
        {"operations": [_PLANE_OP, _HOLE_OP], "setups": _SETUPS},
    )
    cases.append(
        ReplayCase(
            case_id="case_a_stable",
            chatter_path=target_dir / "case_a_stable" / "chatter_report.json",
            plan_path=target_dir / "case_a_stable" / "operation_plan.json",
            expected_outcome="success",
            expected_hint="-",
        )
    )

    # case B：不稳定特征 → UNSTABLE_FEATURES
    _write_json(
        target_dir / "case_b_unstable" / "chatter_report.json",
        {
            "task_id": "replay-case-b",
            "task_status": "succeeded",
            "material_id": "steel_45",
            "prediction_method": "analytical",
            "feature_results": [_PLANE_FEATURE, _HOLE_FEATURE_UNSTABLE],
        },
    )
    _write_json(
        target_dir / "case_b_unstable" / "operation_plan.json",
        {"operations": [_PLANE_OP, _HOLE_D20_OP], "setups": _SETUPS},
    )
    cases.append(
        ReplayCase(
            case_id="case_b_unstable",
            chatter_path=target_dir / "case_b_unstable" / "chatter_report.json",
            plan_path=target_dir / "case_b_unstable" / "operation_plan.json",
            expected_outcome="failure",
            expected_hint="UNSTABLE_FEATURES",
        )
    )

    # case C：阶段 5 未审核通过 → ChatterReportLoadError
    _write_json(
        target_dir / "case_c_rejected" / "chatter_report.json",
        {
            "task_id": "replay-case-c",
            "task_status": "PENDING_REVIEW",  # 非 SUCCEEDED，拒绝加载
            "material_id": "steel_45",
            "prediction_method": "analytical",
            "feature_results": [_PLANE_FEATURE],
        },
    )
    _write_json(
        target_dir / "case_c_rejected" / "operation_plan.json",
        {"operations": [_PLANE_OP], "setups": _SETUPS},
    )
    cases.append(
        ReplayCase(
            case_id="case_c_rejected",
            chatter_path=target_dir / "case_c_rejected" / "chatter_report.json",
            plan_path=target_dir / "case_c_rejected" / "operation_plan.json",
            expected_outcome="failure",
            expected_hint="ChatterReportLoadError",
        )
    )

    return cases


# ----------------------------------------------------------------------
# 重放与门控
# ----------------------------------------------------------------------


def run_replay(
    input_dir: Path,
    replay_db: Path,
    work_dir: Path | None = None,
) -> dict[str, Any]:
    """对输入集重放真实 pipeline，案例写入隔离灰度库。

    Args:
        input_dir: ``write_seed_input_set`` 产出的输入集目录。
        replay_db: 灰度案例库路径（与生产库物理隔离）。
        work_dir: 任务 workspace 根目录（None 用系统临时目录）。

    Returns:
        {per_case: [{case_id, actual_outcome, error_codes}],
        stats: store.stats() 报表}
    """
    input_dir = Path(input_dir)
    replay_db = Path(replay_db)
    work_dir = Path(work_dir) if work_dir else Path(
        os.path.join(os.path.expanduser("~"), ".lnn_replay_workspace")
    )
    work_dir.mkdir(parents=True, exist_ok=True)

    # 发现输入集（按目录名排序保证确定性）
    case_dirs = sorted(p for p in input_dir.iterdir() if p.is_dir())
    if not case_dirs:
        raise FileNotFoundError(f"输入集目录为空: {input_dir}")

    # 隔离灰度库：重放案例绝不混入生产库
    old_env = os.environ.get("FAILURE_CASES_DB")
    os.environ["FAILURE_CASES_DB"] = str(replay_db)
    reset_failure_case_store()
    try:
        # 清空旧重放库，保证 stats 只反映本轮
        if replay_db.exists():
            replay_db.unlink()

        cfg = GCodeGenerationConfig(output_dir=str(work_dir / "gcode"))
        pipeline = GCodeGenerationPipeline(cfg=cfg)
        store = FailureCaseStore(db_path=replay_db)

        per_case: list[dict[str, Any]] = []
        for case_dir in case_dirs:
            chatter = case_dir / "chatter_report.json"
            plan = case_dir / "operation_plan.json"
            task = pipeline.create_task(
                source_chatter_report_path=str(chatter),
                source_operation_plan_path=str(plan),
                controller_type=_CONTROLLER,
                material_name=_MATERIAL,
            )
            result = asyncio.run(pipeline.run_pipeline(task.task_id))
            actual = result.status
            # 案例库在本轮 run 中应恰好新增 1 条该任务案例
            case_cases = [c for c in store.list_cases(limit=100) if c.task_id == task.task_id]
            per_case.append(
                {
                    "case_id": case_dir.name,
                    "actual_outcome": actual,
                    "error_codes": case_cases[0].error_codes if case_cases else [],
                }
            )

        return {"per_case": per_case, "stats": store.stats()}
    finally:
        # 恢复环境，避免污染同进程后续的生产库路由
        if old_env is None:
            os.environ.pop("FAILURE_CASES_DB", None)
        else:
            os.environ["FAILURE_CASES_DB"] = old_env
        reset_failure_case_store()


def gate_from_dbs(
    baseline_db: Path,
    candidate_db: Path,
    thresholds: GateThresholds | None = None,
) -> GateResult:
    """从两个灰度库取 stats 做回归门控判定。"""
    base_stats = FailureCaseStore(db_path=Path(baseline_db)).stats()
    cur_stats = FailureCaseStore(db_path=Path(candidate_db)).stats()
    return evaluate_regression(base_stats, cur_stats, thresholds)


# ----------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    """CLI 入口：prepare / run / gate 三个子命令。"""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    args = list(sys.argv[1:] if argv is None else argv)
    if not args:
        print(__doc__)
        return 2
    cmd, rest = args[0], args[1:]

    if cmd == "prepare" and rest:
        cases = write_seed_input_set(Path(rest[0]))
        for c in cases:
            print(f"{c.case_id}: expected={c.expected_outcome} ({c.expected_hint})")
        return 0

    if cmd == "run" and len(rest) >= 2:
        work_dir = Path(rest[3]) if len(rest) >= 4 and rest[2] == "--work-dir" else None
        report = run_replay(Path(rest[0]), Path(rest[1]), work_dir=work_dir)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0

    if cmd == "gate" and len(rest) >= 2:
        gate = gate_from_dbs(Path(rest[0]), Path(rest[1]))
        print(json.dumps(gate.to_dict(), ensure_ascii=False, indent=2))
        return 0 if gate.passed else 1

    print(__doc__)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
