import urllib.request
import json

body = json.dumps(
    {"model_name": "cutting_force", "input_data": [120.5, 85.3, 65.1, 12000.0, 0.15]}
)
req = urllib.request.Request(
    "http://localhost:8001/api/v1/lnn/predict",
    data=body.encode(),
    headers={"Content-Type": "application/json"},
)
try:
    resp = urllib.request.urlopen(req, timeout=60)
    print("Status:", resp.status)
    print("Response:", resp.read().decode())
except urllib.error.HTTPError as e:
    print("HTTP Error:", e.code)
    print("Response:", e.read().decode())
except Exception as e:
    print("Error:", type(e).__name__, str(e))
