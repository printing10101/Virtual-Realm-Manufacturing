"""Quick test to verify predict dimension fix."""

import urllib.request
import json
import sys
import os
from pathlib import Path

BASE = "http://127.0.0.1:8000"

token_path = Path(os.environ.get("LNN_TOKEN_FILE", ".lnn_token"))
TOKEN = token_path.read_text().strip() if token_path.exists() else "test-token"


def post(path, data):
    req = urllib.request.Request(
        f"{BASE}{path}",
        data=json.dumps(data).encode(),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {TOKEN}",
        },
        method="POST",
    )
    try:
        r = urllib.request.urlopen(req, timeout=30)
        return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


def get(path):
    req = urllib.request.Request(
        f"{BASE}{path}", headers={"Authorization": f"Bearer {TOKEN}"}
    )
    r = urllib.request.urlopen(req, timeout=10)
    return r.status, json.loads(r.read())


print("=" * 60)
print("Test 1: cutting_force predict (5 features)")
code, resp = post(
    "/api/v1/lnn/predict",
    {"model_name": "cutting_force", "input_data": [120.5, 85.3, 65.1, 12000.0, 0.15]},
)
print(f"  Status: {code}")
print(
    f"  Response: {json.dumps(resp, indent=2, ensure_ascii=False) if isinstance(resp, dict) else resp[:300]}"
)
if code == 200:
    print("  PASS: cutting_force predict works!")
else:
    print("  FAIL: cutting_force predict failed")

print()
print("Test 2: wear_prediction predict (2 features)")
code, resp = post(
    "/api/v1/lnn/predict", {"model_name": "wear_prediction", "input_data": [85.3, 0.15]}
)
print(f"  Status: {code}")
print(
    f"  Response: {json.dumps(resp, indent=2, ensure_ascii=False) if isinstance(resp, dict) else resp[:300]}"
)
if code == 200:
    print("  PASS: wear_prediction predict works!")
else:
    print("  FAIL: wear_prediction predict failed")

print()
print("Test 3: surface_roughness predict (4 features)")
code, resp = post(
    "/api/v1/lnn/predict",
    {"model_name": "surface_roughness", "input_data": [120.5, 85.3, 65.1, 12000.0]},
)
print(f"  Status: {code}")
print(
    f"  Response: {json.dumps(resp, indent=2, ensure_ascii=False) if isinstance(resp, dict) else resp[:300]}"
)
if code == 200:
    print("  PASS: surface_roughness predict works!")
else:
    print("  FAIL: surface_roughness predict failed")

print()
print("=" * 60)
sys.stdout.flush()
