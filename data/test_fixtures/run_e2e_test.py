"""对 20 个 fixture 跑端到端测试，验证产品轨可用性。

跑 3 轮：
  - 轮 1：fanuc_0i（基线）
  - 轮 2：gsk_980_25i
  - 轮 3：hnc_848_22
  - 轮 4：knd_1000_2000_3000

每个 fixture 走完整流水线：parse → features → 3D → G 代码
结果落盘到 data/outputs/e2e/<fixture>/
统计落盘到 data/outputs/e2e_summary.json
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
    "gsk_980_25i",
    "hnc_848_22",
    "knd_1000_2000_3000",
]


def main() -> int:
    fixture_dir = REPO_ROOT / "data" / "test_fixtures"
    output_root = REPO_ROOT / "data" / "outputs" / "e2e"
    output_root.mkdir(parents=True, exist_ok=True)

    fixtures = sorted(fixture_dir.glob("case*.dxf"))
    print(f"找到 {len(fixtures)} 个 fixture")

    svc = DxfProcessService()
    summary: dict = {
        "started_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "fixture_count": len(fixtures),
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

    for dxf in fixtures:
        fixture_record: dict = {
            "name": dxf.name,
            "results_by_controller": {},
        }
        # 每个 fixture 的 parse/features/model3d 结果是文件级，与后处理器无关
        # 只在第一次循环时算一次
        first_ctl = POSTPROCESSORS[0]
        out_dir_first = output_root / first_ctl / dxf.stem
        r_first = svc.process(
            dxf,
            output_dir=out_dir_first,
            postprocessor=first_ctl,
            user_id="e2e_test",
        )
        parse_ok_first = r_first.parse and r_first.parse.success
        features_ok_first = r_first.features and r_first.features.success
        model3d_ok_first = r_first.model3d and r_first.model3d.success

        for ctl in POSTPROCESSORS:
            out_dir = output_root / ctl / dxf.stem
            r = svc.process(
                dxf,
                output_dir=out_dir,
                postprocessor=ctl,
                user_id="e2e_test",
            )
            totals["total"] += 1
            if r.success:
                totals["success"] += 1
            # 文件级阶段（只在第一次循环累加）
            if ctl == first_ctl:
                if parse_ok_first:
                    totals["parse_ok"] += 1
                if features_ok_first:
                    totals["features_ok"] += 1
                if model3d_ok_first:
                    totals["model3d_ok"] += 1
            if r.gcode and r.gcode.success:
                totals["gcode_ok"] += 1
                totals[f"gcode_ok_{ctl}"] += 1

            fixture_record["results_by_controller"][ctl] = {
                "success": r.success,
                "parse_ok": parse_ok_first,
                "features_ok": features_ok_first,
                "model3d_ok": model3d_ok_first,
                "gcode_ok": r.gcode.success if r.gcode else False,
                "total_latency_ms": round(r.total_latency_ms, 2),
                "output_files": r.output_files,
                "errors": r.errors,
                "warnings": r.warnings,
            }
            status = "OK" if r.success else "FAIL"
            print(f"  [{status}] {dxf.name:35s} {ctl:25s} {r.total_latency_ms:7.1f}ms")
        summary["fixtures"].append(fixture_record)

    summary["totals"] = totals
    summary["success_rate"] = round(totals["success"] / max(totals["total"], 1) * 100, 1)
    summary["parse_rate"] = round(totals["parse_ok"] / len(fixtures) * 100, 1)
    summary["features_rate"] = round(totals["features_ok"] / len(fixtures) * 100, 1)
    summary["model3d_rate"] = round(totals["model3d_ok"] / len(fixtures) * 100, 1)
    for ctl in POSTPROCESSORS:
        summary[f"gcode_rate_{ctl}"] = round(
            totals[f"gcode_ok_{ctl}"] / len(fixtures) * 100, 1
        )
    summary["ended_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")

    summary_path = output_root / "e2e_summary.json"
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"\n=== E2E 汇总 ===")
    print(f"  Fixture 数量 : {len(fixtures)}")
    print(f"  总调用次数   : {totals['total']}")
    print(f"  总体成功率   : {summary['success_rate']}%")
    print(f"  解析成功率   : {summary['parse_rate']}%")
    print(f"  特征成功率   : {summary['features_rate']}%")
    print(f"  3D 成功率    : {summary['model3d_rate']}%")
    for ctl in POSTPROCESSORS:
        print(f"  G代码 {ctl:25s}: {summary[f'gcode_rate_{ctl}']}%")
    print(f"\n结果落盘: {summary_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
