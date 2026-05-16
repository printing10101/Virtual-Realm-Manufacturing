import urllib.request
import json
import time

token = open(".lnn_token").read().strip()

# Test 1: Simple ping
req = urllib.request.Request("http://127.0.0.1:8000/api/health/ping")
t0 = time.time()
try:
    r = urllib.request.urlopen(req, timeout=10)
    print(f"Test1-Ping: {r.status} in {time.time() - t0:.2f}s")
except Exception as e:
    print(f"Test1-Ping: FAIL after {time.time() - t0:.2f}s: {e}")

# Test 2: Train with very short timeout to see if it hangs
data = json.dumps(
    {
        "model_name": "cutting_force",
        "data_path": r"C:\Users\Lenovo\AppData\Local\Temp\uniwear.csv",
        "hyperparameters": {
            "epochs": 1,
            "batch_size": 32,
            "learning_rate": 0.001,
            "optimizer": "adam",
        },
        "device": "cpu",
    }
).encode()

req = urllib.request.Request(
    "http://127.0.0.1:8000/api/v1/lnn/train",
    data=data,
    headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"},
    method="POST",
)

t0 = time.time()
try:
    r = urllib.request.urlopen(req, timeout=5)
    print(f"Test2-Train: {r.status} in {time.time() - t0:.2f}s")
    print(r.read().decode()[:300])
except Exception as e:
    print(f"Test2-Train: FAIL after {time.time() - t0:.2f}s: {e}")
