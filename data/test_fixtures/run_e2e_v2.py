"""对 20 个 fixture 跑 8 后处理器端到端（v2 - 升级到全 8 个后处理器）。

postprocessors:
  1. fanuc_0i            2. siemens_840d     3. heidenhain_tnc
  4. gsk_980_25i         5. hnc_848_22       6. knd_1000_2000_3000
  7. mitsubishi_m70_m80  8. fagor_8055

结果落盘到 data/outputs/e2e_v2/e2e_v2_summary.json
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "python"))
sys.path.insert(0, str(REPO_ROOT))

from app.dxf.process_service import DxfProcessService

POSTPROCESSORS = [
    "fanuc_0i",
    "siemens_840d",
    "heidenhain_tnc",
    "gsk_980_25i",
    "hnc_848_22",
    "knd_1000_2000_3000",
    "mitsubishi_m70_m80",
    "fagor_8055",
]


def main() -> int:
    fixture_dir = REPO_ROOT / "data" / "test_fixtures"
    output_root = REPO_ROOT / "data" / "outputs" / "e2e_v2"
    output_root.mkdir(parents=True, exist_ok=True)

    fixtures = sorted(fixture_dir.glob("case*.dxf"))
    print(f"找到 {len(fixtures)} 个 fixture")
    print(f"后处理器: {len(POSTPROCESSORS)} 个")

    svc = DxfProcessService()
    summary: dict = {
        "started_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "fixture_count": len(fixtures),
        "postprocessor_count": len(POSTPROCESSORS),
        "postprocessors": POSTPROCESSORS,
        "fixtures": [],
        "totals": {},
    }
    totals = {
        "total": 0,
        "success": 0,
        "parse_ok": 0,
        "features_ok": 0,
        "model3d_ok": 0,
        "gcode_ok": 0,
    }
    for ctl in POSTPROCESSORS:
        totals[f"gcode_ok_{ctl}"] = 0
        totals[f"latency_ms_{ctl}_sum"] = 0.0

    t_overall = time.time()
    for dxf in fixtures:
        fixture_record: dict = {
            "name": dxf.name,
            "results_by_controller": {},
        }
        first_ctl = POSTPROCESSORS[0]
        out_dir_first = output_root / first_ctl / dxf.stem
        r_first = svc.process(
            dxf,
            output_dir=out_dir_first,
            postprocessor=first_ctl,
            user_id="e2e_v2",
        )
        parse_ok_first = r_first.parse and r_first.parse.success
        features_ok_first = r_first.features and r_first.features.success
        model3d_ok_first = r_first.model3d and r_first.model3d.success
        if parse_ok_first:
            totals["parse_ok"] += 1
        if features_ok_first:
            totals["features_ok"] += 1
        if model3d_ok_first:
            totals["model3d_ok"] += 1

        for ctl in POSTPROCESSORS:
            out_dir = output_root / ctl / dxf.stem
            r = svc.process(
                dxf,
                output_dir=out_dir,
                postprocessor=ctl,
                user_id="e2e_v2",
            )
            totals["total"] += 1
            if r.success:
                totals["success"] += 1
            if r.gcode and r.gcode.success:
                totals["gcode_ok"] += 1
                totals[f"gcode_ok_{ctl}"] += 1
            totals[f"latency_ms_{ctl}_sum"] += r.total_latency_ms

            fixture_record["results_by_controller"][ctl] = {
                "success": r.success,
                "parse_ok": parse_ok_first,
                "features_ok": features_ok_first,
                "model3d_ok": model3d_ok_first,
                "gcode_ok": r.gcode.success if r.gcode else False,
                "total_latency_ms": round(r.total_latency_ms, 2),
            }
            status = "OK" if r.success else "FAIL"
            print(
                f"  [{status}] {dxf.name:35s} {ctl:25s} "
                f"{r.total_latency_ms:7.1f}ms"
            )
        summary["fixtures"].append(fixture_record)

    summary["totals"] = totals
    summary["wall_clock_seconds"] = round(
        time.time() - t_overall, 2
    )
    summary["success_rate"] = round(
        totals["success"] / max(totals["total"], 1) * 100, 1
    )
    summary["parse_rate"] = round(
        totals["parse_ok"] / len(fixtures) * 100, 1
    )
    summary["features_rate"] = round(
        totals["features_ok"] / len(fixtures) * 100, 1
    )
    summary["model3d_rate"] = round(
        totals["model3d_ok"] / len(fixtures) * 100, 1
    )
    summary["gcode_rate"] = round(
        totals["gcode_ok"] / max(totals["total"], 1) * 100, 1
    )
    for ctl in POSTPROCESSORS:
        summary[f"gcode_rate_{ctl}"] = round(
            totals[f"gcode_ok_{ctl}"] / len(fixtures) * 100, 1
        )
        summary[f"latency_ms_{ctl}_avg"] = round(
            totals[f"latency_ms_{ctl}_sum"] / len(fixtures), 2
        )
    summary["ended_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")

    summary_path = output_root / "e2e_v2_summary.json"
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"\n=== E2E v2 汇总 ===")
    print(f"  Fixture 数量    : {len(fixtures)}")
    print(f"  后处理器        : {len(POSTPROCESSORS)} 个")
    print(
        f"  总调用次数      : {totals['total']}"
        f" ({len(fixtures)} x {len(POSTPROCESSORS)})"
    )
    print(f"  总体成功率      : {summary['success_rate']}%")
    print(f"  解析成功率      : {summary['parse_rate']}%")
    print(f"  特征成功率      : {summary['features_rate']}%")
    print(f"  3D 成功率       : {summary['model3d_rate']}%")
    print(f"  G代码总成功率   : {summary['gcode_rate']}%")
    for ctl in POSTPROCESSORS:
        print(
            f"    {ctl:25s}: G代码 "
            f"{summary[f'gcode_rate_{ctl}']}%  "
            f"avg {summary[f'latency_ms_{ctl}_avg']}ms"
        )
    print(f"  Wall Clock      : {summary['wall_clock_seconds']}s")
    print(f"\n结果落盘: {summary_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
