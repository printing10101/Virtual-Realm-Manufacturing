"""Quick diagnostic for TestClient."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.resolve()))

print("Importing app...")
from app.main import app

print(f"App has {len(app.routes)} routes")

print("\nCreating TestClient...")
from fastapi.testclient import TestClient

client = TestClient(app, raise_server_exceptions=False)
print("TestClient ready")

print("\nTest1: Train endpoint...")
import time
import json

UNIWEAR_CSV = r"C:\Users\Lenovo\AppData\Local\Temp\uniwear.csv"
token_path = Path(__file__).parent / ".lnn_token"
TOKEN = token_path.read_text().strip()
HEADERS = {"Content-Type": "application/json", "Authorization": f"Bearer {TOKEN}"}

payload = {
    "model_name": "cutting_force",
    "data_path": UNIWEAR_CSV,
    "hyperparameters": {
        "epochs": 3,
        "batch_size": 32,
        "learning_rate": 0.001,
        "optimizer": "adam",
    },
    "device": "cpu",
}
t0 = time.time()
resp = client.post("/api/v1/lnn/train", json=payload, headers=HEADERS, timeout=30)
elapsed = time.time() - t0
data = resp.json()
print(f"  Status: {resp.status_code}, time: {elapsed:.2f}s")
print(f"  Data: {json.dumps(data, indent=2)}")

job_id = data.get("data", {}).get("job_id", "")
if not job_id:
    print("FAIL: No job_id")
    sys.exit(1)

print(f"\nTest2: SSE stream for {job_id}...")
AUTH = {"Authorization": f"Bearer {TOKEN}"}
t0 = time.time()
try:
    with client.stream(
        "GET", f"/api/v1/jobs/{job_id}/stream", headers=AUTH, timeout=60
    ) as r:
        print(f"  Stream status: {r.status_code}, elapsed: {time.time() - t0:.2f}s")
        event_count = 0
        for line in r.iter_lines():
            line = line.strip()
            if line.startswith("event:") or line.startswith("data:"):
                event_count += 1
                print(f"  Event {event_count}: {line[:80]}")
            if event_count > 10:
                print("  (stopping after 10 events)")
                break
except Exception as e:
    print(f"  Stream error: {e}")

print("\nTest7: Jobs list...")
resp7 = client.get("/api/v1/jobs", headers=AUTH, timeout=10)
if resp7.status_code == 200:
    jobs = resp7.json().get("data", {}).get("jobs", [])
    print(f"  {len(jobs)} jobs found")
else:
    print(f"  HTTP {resp7.status_code}")

print("\nDone!")
