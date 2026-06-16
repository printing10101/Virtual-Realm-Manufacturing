import json

data = json.load(open('coverage-reports/coverage.json'))
files = data.get('files', {})
lnn_file = [k for k in files.keys() if 'lnn_uncertain.py' in k and 'test' not in k]
print('=== lnn_uncertain.py Coverage ===')
for k in lnn_file:
    pct = files[k].get('summary', {}).get('percent_covered', 0)
    print(f'{k}: {pct:.1f}%')
