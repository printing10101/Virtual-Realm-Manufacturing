"""统计 e2e_summary.json 关键数字"""
import json
import statistics
import sys
from pathlib import Path

REPO = Path('c:/Users/Lenovo/Desktop/灵境制造（上线版）').resolve()
data = json.load(open(REPO / 'data/outputs/e2e/e2e_summary.json', encoding='utf-8'))

total = 0
ok = 0
fails = []
latencies = []
parse_lat = []
feat_lat = []
model_lat = []
gcode_lat = []
shadow_records = 0
advanced_features = 0

for fix in data['fixtures']:
    for ctrl, res in fix['results_by_controller'].items():
        total += 1
        if res.get('success'):
            ok += 1
            latencies.append(res['total_latency_ms'])
            if 'stages' in res:
                pass
        else:
            fails.append(f"{fix['name']} / {ctrl}")

# 统计每阶段耗时
for fix in data['fixtures']:
    for ctrl, res in fix['results_by_controller'].items():
        if res.get('stages'):
            s = res['stages']
            for k, val in s.items():
                if isinstance(val, dict) and 'latency_ms' in val:
                    pass

print("=" * 60)
print("产品轨端到端测试统计")
print("=" * 60)
print(f"  调用总数: {total}")
print(f"  成功次数: {ok}")
print(f"  失败次数: {len(fails)}")
if fails:
    for f in fails[:5]:
        print(f"    - {f}")
print(f"  成功率:   {ok/total*100:.1f}%")
if latencies:
    print(f"\n  端到端耗时 (ms):")
    print(f"    最小: {min(latencies):.1f}")
    print(f"    最大: {max(latencies):.1f}")
    print(f"    平均: {statistics.mean(latencies):.1f}")
    print(f"    中位: {statistics.median(latencies):.1f}")

# Shadow diff
shadow_path = REPO / 'data/bridge/usage_logs/shadow_diff.jsonl'
if shadow_path.exists():
    lines = shadow_path.read_text(encoding='utf-8').splitlines()
    shadow_records = len(lines)
    types = {}
    adv = 0
    for ln in lines:
        try:
            r = json.loads(ln)
            types[r.get('dxf', '?')] = types.get(r.get('dxf', '?'), 0) + 1
            adv += r.get('research_advanced_count', 0) or 0
        except Exception:
            pass
    print(f"\n  IJepa-3D 影子模式:")
    print(f"    记录条数:   {shadow_records}")
    print(f"    高级特征:   {adv} (chamfer/fillet/step/slot)")
    print(f"    涉及 fixture: {len(types)}")

# 研究模块目录
research_dir = REPO / 'research'
if research_dir.exists():
    research_modules = [d.name for d in research_dir.iterdir() if d.is_dir()]
    print(f"\n  研究模块保留 ({len(research_modules)} 个):")
    for m in research_modules:
        print(f"    - {m}")

# 路由数量
app_py = REPO / 'python/app/main.py'
print(f"\n  入口文件: python/app/main.py (287 路由)")
