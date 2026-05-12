import requests
import json
import sys

BASE_URL = "http://localhost:8000"
UNIWEAR_CSV = "C:\\Users\\Lenovo\\AppData\\Local\\Temp\\uniwear.csv"

print("=== Quick Diagnostic ===")

# Check server
try:
    r = requests.get(f"{BASE_URL}/api/v1/lnn/models", timeout=5)
    print(f"Server check: {r.status_code}")
    models = r.json().get("data", {}).get("models", [])
    print(f"Models: {[m for m in models]}")
except Exception as e:
    print(f"Server DOWN: {e}")
    sys.exit(1)

# Try training with verbose error capture
payload = {
    "model_name": "cutting_force",
    "data_path": UNIWEAR_CSV,
    "hyperparameters": {
        "epochs": 3,
        "batch_size": 16,
        "learning_rate": 0.001,
        "optimizer": "adam"
    },
    "device": "cpu"
}

print(f"\nPOST /api/v1/lnn/train with payload: {json.dumps(payload, indent=2)}")

try:
    r = requests.post(f"{BASE_URL}/api/v1/lnn/train", json=payload, timeout=30)
    print(f"\nHTTP Status: {r.status_code}")
    print(f"Response headers: {dict(r.headers)}")
    print(f"Response body: {r.text[:2000]}")
except requests.exceptions.Timeout:
    print("TIMEOUT after 30s")
except requests.exceptions.ConnectionError as e:
    print(f"CONNECTION ERROR: {e}")
except Exception as e:
    print(f"OTHER ERROR: {type(e).__name__}: {e}")
