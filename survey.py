"""Survey script: find remaining 'global _' patterns and current Depends() usage."""
import os
import re

ROOT = r'c:\Users\Lenovo\Desktop\灵境制造（上线版）\python\app'
global_underscore_files = []
global_decl_lines = []
module_level_none_lines = []
depends_lines = []

for root, dirs, fs in os.walk(ROOT):
    if '__pycache__' in root:
        continue
    for f in fs:
        if not f.endswith('.py'):
            continue
        p = os.path.join(root, f)
        with open(p, 'r', encoding='utf-8', errors='ignore') as fp:
            for i, line in enumerate(fp, 1):
                if re.search(r'\bglobal\s+_\w+', line):
                    global_decl_lines.append((p, i, line.rstrip()))
                if re.match(r'^_\w+.*=\s*None\s*$', line):
                    module_level_none_lines.append((p, i, line.rstrip()))
                if 'Depends(' in line:
                    depends_lines.append((p, i))

print('=== Module-level _xxx = None patterns (potential global _ var) ===')
for p, i, l in module_level_none_lines:
    print(f'{p}:{i}: {l}')
print(f'TOTAL module-level _xxx = None: {len(module_level_none_lines)}')

print('\n=== "global _xxx" declarations ===')
for p, i, l in global_decl_lines:
    print(f'{p}:{i}: {l}')
print(f'TOTAL global _xxx declarations: {len(global_decl_lines)}')

print(f'\nTOTAL Depends() references: {len(depends_lines)}')
print(f'Unique files using Depends: {len(set(p for p, _ in depends_lines))}')
