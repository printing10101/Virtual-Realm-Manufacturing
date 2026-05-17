"""Quick diagnosis v2 - compare predict vs train."""

import subprocess
import sys
import time
import json
import urllib.request
import urllib.error
from pathlib import Path

PYTHON_DIR = Path(__file__).parent.resolve()
TOKEN_FILE = PYTHON_DIR / ".lnn_token"
TOKEN = TOKEN_FILE.read_text().strip() if TOKEN_FILE.exists() else "test-token"
BASE = "http://127.0.0.1:8000"
HEADERS = {"Content-Type": "application/json", "Authorization": f"Bearer {TOKEN}"}

print("=" * 60)
print("Starting server...")
env = {**__import__("os").environ, "PYTHONUNBUFFERED": "1"}
proc = subprocess.Popen(
    [
        sys.executable,
        "-m",
        "uvicorn",
        "app.main:app",
        "--host",
        "127.0.0.1",
        "--port",
        "8000",
    ],
    cwd=str(PYTHON_DIR),
    env=env,
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
    text=True,
)

for i in range(30):
    try:
        r = urllib.request.urlopen("http://127.0.0.1:8000/api/health/ping", timeout=2)
        if r.status == 200:
            print(f"Server ready after {i + 1}s")
            break
    except Exception:
        pass
    if proc.poll() is not None:
        print(f"SERVER DIED! Exit: {proc.poll()}")
        print(proc.stdout.read()[:2000])
        sys.exit(1)
    time.sleep(1)

# Test predict (was working)
print("\nTest: POST /api/v1/lnn/predict")
t0 = time.time()
try:
    req = urllib.request.Request(
        f"{BASE}/api/v1/lnn/predict",
        data=json.dumps(
            {
                "model_name": "cutting_force",
                "input_data": [120.5, 85.3, 65.1, 12000.0, 0.15],
            }
        ).encode(),
        headers=HEADERS,
        method="POST",
    )
    r = urllib.request.urlopen(req, timeout=10)
    print(f"  Status: {r.status}, {time.time() - t0:.2f}s")
    print(f"  Body: {r.read().decode()[:300]}")
except Exception as e:
    print(f"  ERROR: {e}")

# Test predict with model_name from list
print("\nTest: GET /api/v1/lnn/models")
t0 = time.time()
try:
    req = urllib.request.Request(
        f"{BASE}/api/v1/lnn/models", headers={"Authorization": f"Bearer {TOKEN}"}
    )
    r = urllib.request.urlopen(req, timeout=10)
    print(f"  Status: {r.status}, {time.time() - t0:.2f}s")
    print(f"  Body: {r.read().decode()[:300]}")
except Exception as e:
    print(f"  ERROR: {e}")

# Test train with minimal data
print("\nTest: POST /api/v1/lnn/train")
t0 = time.time()
try:
    payload = {
        "model_name": "cutting_force",
        "data_path": r"C:\Users\Lenovo\AppData\Local\Temp\uniwear.csv",
        "hyperparameters": {
            "epochs": 2,
            "batch_size": 32,
            "learning_rate": 0.001,
            "optimizer": "adam",
        },
        "device": "cpu",
    }
    req = urllib.request.Request(
        f"{BASE}/api/v1/lnn/train",
        data=json.dumps(payload).encode(),
        headers=HEADERS,
        method="POST",
    )
    r = urllib.request.urlopen(req, timeout=10)
    print(f"  Status: {r.status}, {time.time() - t0:.2f}s")
    print(f"  Body: {r.read().decode()[:500]}")
except Exception as e:
    print(f"  ERROR after {time.time() - t0:.2f}s: {e}")

print("\nAlive:", proc.poll() is None)
proc.terminate()
proc.wait(timeout=5)
print("Done.")
