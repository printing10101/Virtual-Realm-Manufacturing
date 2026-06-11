"""Survey broader patterns that might be related to globals."""
import os
import re

ROOT = r'c:\Users\Lenovo\Desktop\灵境制造（上线版）\python\app'
patterns_to_check = {
    '_instance = None': [],
    'module-level _xxx = None': [],
    'lru_cache': [],
    'Singleton pattern': [],
    'class with _instance': [],
    '@lru_cache': [],
    'get_singleton': [],
    'get_instance': [],
    '@singleton': [],
    'get_default': [],
}

count = {}
for root, dirs, fs in os.walk(ROOT):
    if '__pycache__' in root:
        continue
    for f in fs:
        if not f.endswith('.py'):
            continue
        p = os.path.join(root, f)
        with open(p, 'r', encoding='utf-8', errors='ignore') as fp:
            for i, line in enumerate(fp, 1):
                # Module-level _xxx = None (only top of file)
                if re.match(r'^_\w+.*=\s*None\s*$', line):
                    patterns_to_check['module-level _xxx = None'].append((p, i, line.rstrip()))
                # _instance = None pattern
                if re.search(r'_instance\s*=\s*None', line):
                    patterns_to_check['_instance = None'].append((p, i, line.rstrip()))
                # lru_cache
                if '@lru_cache' in line:
                    patterns_to_check['@lru_cache'].append((p, i, line.rstrip()))

for name, lines in patterns_to_check.items():
    if lines:
        print(f'\n=== {name} ({len(lines)} matches) ===')
        for p, i, l in lines[:20]:
            print(f'  {p}:{i}: {l}')
        if len(lines) > 20:
            print(f'  ... and {len(lines) - 20} more')
