"""Quick diagnosis - test server connectivity and basic endpoints."""

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
print("Starting server subprocess...")
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
print(f"Server PID: {proc.pid}")

# Wait for server
print("Waiting for server...")
for i in range(30):
    try:
        r = urllib.request.urlopen("http://127.0.0.1:8000/api/health/ping", timeout=2)
        if r.status == 200:
            print(f"Server ready after {i + 1}s")
            break
    except Exception:
        pass
    if proc.poll() is not None:
        print(f"SERVER DIED! Exit code: {proc.poll()}")
        out = proc.stdout.read()
        print(f"SERVER OUTPUT:\n{out[:2000]}")
        sys.exit(1)
    time.sleep(1)
else:
    print("Server did not start")
    sys.exit(1)

# Test 1: GET /api/v1/jobs
print("\nTest 1: GET /api/v1/jobs")
try:
    req = urllib.request.Request(
        f"{BASE}/api/v1/jobs", headers={"Authorization": f"Bearer {TOKEN}"}
    )
    r = urllib.request.urlopen(req, timeout=10)
    print(f"  Status: {r.status}")
    print(f"  Body: {r.read().decode()[:300]}")
except Exception as e:
    print(f"  ERROR: {e}")

# Test 2: POST /api/v1/lnn/train
print("\nTest 2: POST /api/v1/lnn/train")
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
try:
    req = urllib.request.Request(
        f"{BASE}/api/v1/lnn/train",
        data=json.dumps(payload).encode(),
        headers=HEADERS,
        method="POST",
    )
    t0 = time.time()
    r = urllib.request.urlopen(req, timeout=30)
    elapsed = time.time() - t0
    print(f"  Status: {r.status}, {elapsed:.2f}s")
    print(f"  Body: {r.read().decode()[:500]}")
except Exception as e:
    print(f"  ERROR after {time.time() - t0:.2f}s: {e}")

# Read any server output
time.sleep(0.5)
print("\n--- Server process info ---")
print(f"Alive: {proc.poll() is None}")
if proc.poll() is not None:
    print(f"Exit code: {proc.poll()}")
    out = proc.stdout.read()
    print(f"Output:\n{out[:3000] if out else '(none)'}")

# Stop server
print("\nStopping server...")
proc.terminate()
try:
    proc.wait(timeout=5)
except subprocess.TimeoutExpired:
    proc.kill()
print("Done.")
