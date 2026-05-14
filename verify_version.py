import json
import re

# 验证VERSION文件
with open('VERSION') as f:
    ver = f.read().strip()
    print(f'VERSION: {ver}')
    assert ver == '1.7.0', f'VERSION mismatch: expected 1.7.0, got {ver}'

# 验证package.json
with open('package.json', encoding='utf-8') as f:
    ver = json.load(f)['version']
    print(f'package.json: {ver}')
    assert ver == '1.7.0', f'package.json mismatch: expected 1.7.0, got {ver}'

# 验证tauri.conf.json
with open('src-tauri/tauri.conf.json', encoding='utf-8') as f:
    ver = json.load(f)['version']
    print(f'tauri.conf.json: {ver}')
    assert ver == '1.7.0', f'tauri.conf.json mismatch: expected 1.7.0, got {ver}'

# 验证openapi.json
with open('docs/api/openapi.json', encoding='utf-8') as f:
    ver = json.load(f)['info']['version']
    print(f'openapi.json: {ver}')
    assert ver == '1.7.0', f'openapi.json mismatch: expected 1.7.0, got {ver}'

# 验证main.py
with open('python/app/main.py', encoding='utf-8') as f:
    content = f.read()
    versions = re.findall(r'version="([\d.]+)"', content)
    print(f'main.py versions: {versions}')
    for v in versions:
        assert v == '1.7.0', f'main.py version mismatch: expected 1.7.0, got {v}'

# 验证config.py
with open('python/app/config.py', encoding='utf-8') as f:
    content = f.read()
    match = re.search(r'APP_VERSION", "([\d.]+)"', content)
    ver = match.group(1) if match else 'not found'
    print(f'config.py: {ver}')
    assert ver == '1.7.0', f'config.py mismatch: expected 1.7.0, got {ver}'

# 验证Cargo.toml
with open('src-tauri/Cargo.toml', encoding='utf-8') as f:
    content = f.read()
    match = re.search(r'version = "([\d.]+)"', content)
    ver = match.group(1) if match else 'not found'
    print(f'Cargo.toml: {ver}')
    assert ver == '1.7.0', f'Cargo.toml mismatch: expected 1.7.0, got {ver}'

print('\n All version checks passed! All versions are 1.7.0')
