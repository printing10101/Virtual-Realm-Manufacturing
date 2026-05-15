import json
import re

PROJECT_ROOT = "."

with open(f"{PROJECT_ROOT}/VERSION") as f:
    expected = f.read().strip()
    print(f"VERSION: {expected} (source of truth)")

with open(f"{PROJECT_ROOT}/package.json", encoding="utf-8") as f:
    ver = json.load(f)["version"]
    print(f"package.json: {ver}")
    assert ver == expected, f"package.json mismatch: expected {expected}, got {ver}"

with open(f"{PROJECT_ROOT}/src-tauri/tauri.conf.json", encoding="utf-8") as f:
    ver = json.load(f)["version"]
    print(f"tauri.conf.json: {ver}")
    assert ver == expected, f"tauri.conf.json mismatch: expected {expected}, got {ver}"

with open(f"{PROJECT_ROOT}/docs/api/openapi.json", encoding="utf-8") as f:
    ver = json.load(f)["info"]["version"]
    print(f"openapi.json: {ver}")
    assert ver == expected, f"openapi.json mismatch: expected {expected}, got {ver}"

with open(f"{PROJECT_ROOT}/python/app/main.py", encoding="utf-8") as f:
    content = f.read()
    versions = re.findall(r'version="([\d.]+)"', content)
    print(f"main.py versions: {versions}")
    for v in versions:
        assert v == expected, f"main.py version mismatch: expected {expected}, got {v}"

with open(f"{PROJECT_ROOT}/python/app/config.py", encoding="utf-8") as f:
    content = f.read()
    match = re.search(r'APP_VERSION", "([\d.]+)"', content)
    ver = match.group(1) if match else "not found"
    print(f"config.py: {ver}")
    assert ver == expected, f"config.py mismatch: expected {expected}, got {ver}"

with open(f"{PROJECT_ROOT}/src-tauri/Cargo.toml", encoding="utf-8") as f:
    content = f.read()
    match = re.search(r'version = "([\d.]+)"', content)
    ver = match.group(1) if match else "not found"
    print(f"Cargo.toml: {ver}")
    assert ver == expected, f"Cargo.toml mismatch: expected {expected}, got {ver}"

print(f"\n All version checks passed! All versions are {expected}")