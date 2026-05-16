import http.client
import subprocess
import sys
import time
import os
from pathlib import Path

PYTHON_DIR = Path(r"c:\Users\Lenovo\Desktop\灵境制造（上线版）\python")

print("Starting server...")
env = os.environ.copy()
env["PYTHONUNBUFFERED"] = "1"
proc = subprocess.Popen(
    [
        sys.executable,
        "-m",
        "uvicorn",
        "app.main:app",
        "--host",
        "0.0.0.0",
        "--port",
        "8000",
        "--log-level",
        "info",
    ],
    cwd=str(PYTHON_DIR),
    env=env,
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
    text=True,
)

print("Waiting for server...")
for i in range(30):
    try:
        conn = http.client.HTTPConnection("127.0.0.1", 8000, timeout=5)
        conn.request("GET", "/api/health/ping")
        r = conn.getresponse()
        print(f"Server ready! status={r.status}")
        conn.close()
        break
    except Exception as e:
        print(f"  Attempt {i + 1}: {e}")
        time.sleep(1)
else:
    print("Server failed to start")
    proc.terminate()
    sys.exit(1)

print("Training...")
import json

token_path = PYTHON_DIR / ".lnn_token"
TOKEN = token_path.read_text().strip() if token_path.exists() else "test"

body = json.dumps(
    {
        "model_name": "cutting_force",
        "data_path": r"C:\Users\Lenovo\AppData\Local\Temp\uniwear.csv",
        "hyperparameters": {
            "epochs": 3,
            "batch_size": 32,
            "learning_rate": 0.001,
            "optimizer": "adam",
        },
        "device": "cpu",
    }
).encode()

try:
    conn = http.client.HTTPConnection("127.0.0.1", 8000, timeout=30)
    conn.request(
        "POST",
        "/api/v1/lnn/train",
        body=body,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {TOKEN}",
        },
    )
    r = conn.getresponse()
    data = json.loads(r.read().decode())
    print(f"Train response: {r.status} {data}")
    conn.close()
except Exception as e:
    print(f"Train failed: {e}")

proc.terminate()
print("Done.")
