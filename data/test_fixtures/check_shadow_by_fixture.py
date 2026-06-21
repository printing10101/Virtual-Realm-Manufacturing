import json
from pathlib import Path
lines = Path('c:/Users/Lenovo/Desktop/灵境制造（上线版）/data/bridge/usage_logs/shadow_diff.jsonl').read_text(encoding='utf-8').splitlines()
by_fixture = {}
for ln in lines:
    r = json.loads(ln)
    by_fixture[r['dxf']] = by_fixture.get(r['dxf'], 0) + (r.get('research_advanced_count') or 0)
print('各 fixture 高级特征数:')
for k, v in sorted(by_fixture.items()):
    print(f'  {k}: {v}')
print()
print('总记录:', len(lines))
print('有高级特征的记录:', sum(1 for ln in lines if (json.loads(ln).get('research_advanced_count') or 0) > 0))
