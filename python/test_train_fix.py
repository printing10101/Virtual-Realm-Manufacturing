import urllib.request
import json
import time

token = open(".lnn_token").read().strip()
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
    r = urllib.request.urlopen(req, timeout=15)
    print(f"OK: {r.status} in {time.time() - t0:.2f}s")
    print(r.read().decode()[:500])
except Exception as e:
    print(f"FAIL after {time.time() - t0:.2f}s: {e}")
