"""Diagnosis v3 - capture server stderr."""

import subprocess
import sys
import time
import json
import urllib.request
import urllib.error
import threading
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
        "--log-level",
        "info",
    ],
    cwd=str(PYTHON_DIR),
    env=env,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True,
)

# Background reader for stderr
server_logs = []


def read_stderr():
    for line in iter(proc.stderr.readline, ""):
        server_logs.append(line.strip())


t = threading.Thread(target=read_stderr, daemon=True)
t.start()

# Wait for server
for i in range(30):
    try:
        r = urllib.request.urlopen("http://127.0.0.1:8000/api/health/ping", timeout=2)
        if r.status == 200:
            print(f"Server ready after {i + 1}s")
            break
    except:
        pass
    if proc.poll() is not None:
        print(f"SERVER DIED! Exit: {proc.poll()}")
        print("Server logs:")
        for l in server_logs[-50:]:
            print(f"  {l}")
        sys.exit(1)
    time.sleep(1)

# Test train
print("\n=== Sending train request ===")
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
    r = urllib.request.urlopen(req, timeout=15)
    print(f"Status: {r.status}, {time.time() - t0:.2f}s")
    print(f"Body: {r.read().decode()[:500]}")
except Exception as e:
    elapsed = time.time() - t0
    print(f"ERROR after {elapsed:.2f}s: {e}")

time.sleep(1)

# Show server debug logs
print("\n=== Server debug logs (filtered) ===")
for l in server_logs:
    if (
        "DEBUG-TRAIN" in l
        or "ERROR" in l.upper()
        or "Exception" in l
        or "Traceback" in l
    ):
        print(f"  {l}")

# Check if handler was reached
reached = any("DEBUG-TRAIN" in l for l in server_logs)
print(f"\nHandler reached: {reached}")

print(f"\nAlive: {proc.poll() is None}")
proc.terminate()
try:
    proc.wait(timeout=5)
except:
    proc.kill()
print("Done.")
