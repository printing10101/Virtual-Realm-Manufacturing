"""检查 IJepa-3D 影子模式落盘的 shadow_diff.jsonl"""
import json
import sys
from collections import Counter
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
p = REPO_ROOT / "data" / "bridge" / "usage_logs" / "shadow_diff.jsonl"
print(f"REPO_ROOT={REPO_ROOT}")
print(f"shadow_diff path={p}")
print(f"exists={p.exists()}")
if not p.exists():
    print("shadow_diff.jsonl 还没产生")
    raise SystemExit(1)

lines = p.read_text(encoding="utf-8").strip().split("\n")
print(f"共 {len(lines)} 条影子模式记录")
by_dxf = {}
type_counter = Counter()
total_advanced = 0
total_latency = 0
for ln in lines:
    d = json.loads(ln)
    by_dxf[d["dxf"]] = d
    total_advanced += d.get("research_advanced_count", 0)
    total_latency += d.get("research_latency_ms", 0)
    for f in d.get("research_features_preview", []):
        type_counter[f["type"]] += 1
print(f"覆盖 fixture: {len(by_dxf)} 个")
print(f"研究轨识别到的高级特征总数: {total_advanced}")
print(f"研究轨总耗时: {total_latency}ms，平均: {total_latency // max(len(by_dxf), 1)}ms/fixture")
print(f"研究轨特征类型分布: {dict(type_counter)}")

# 按 research_advanced_count 降序列出
ranked = sorted(by_dxf.values(), key=lambda x: -x.get("research_advanced_count", 0))
print("\n按 research_advanced_count 排序前 10:")
for d in ranked[:10]:
    name = d["dxf"]
    print(f"  {name:40s} adv={d['research_advanced_count']:3d} total={d['research_total']:3d} latency={d['research_latency_ms']}ms")
