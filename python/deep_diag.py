import requests
import json
import sys
import time

BASE_URL = "http://localhost:8000"
UNIWEAR_CSV = "C:\\Users\\Lenovo\\AppData\\Local\\Temp\\uniwear.csv"

print("=== Deep Diagnostic ===")

# Test 1: Server health
try:
    r = requests.get(f"{BASE_URL}/api/v1/lnn/models", timeout=5)
    print(f"1. Models endpoint: {r.status_code} OK")
except Exception as e:
    print(f"1. Models endpoint: FAIL - {e}")

# Test 2: Jobs list (uses AsyncTaskManager)
try:
    r = requests.get(f"{BASE_URL}/api/v1/jobs", timeout=10)
    print(f"2. Jobs list: {r.status_code} - {r.text[:200]}")
except requests.exceptions.Timeout:
    print("2. Jobs list: TIMEOUT")
except Exception as e:
    print(f"2. Jobs list: {type(e).__name__}: {e}")

# Test 3: Job stats (uses AsyncTaskManager)
try:
    r = requests.get(f"{BASE_URL}/api/v1/jobs/stats", timeout=10)
    print(f"3. Job stats: {r.status_code} - {r.text[:200]}")
except requests.exceptions.Timeout:
    print("3. Job stats: TIMEOUT")
except Exception as e:
    print(f"3. Job stats: {type(e).__name__}: {e}")

# Test 4: Simple train with very short timeout and raw response
print("\n4. Train endpoint test (raw socket approach)...")
import socket
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.settimeout(5)
try:
    s.connect(("localhost", 8000))
    body = json.dumps({
        "model_name": "cutting_force",
        "data_path": UNIWEAR_CSV,
        "hyperparameters": {
            "epochs": 1,
            "batch_size": 4,
            "learning_rate": 0.001,
            "optimizer": "adam"
        },
        "device": "cpu"
    })
    request = (
        f"POST /api/v1/lnn/train HTTP/1.1\r\n"
        f"Host: localhost:8000\r\n"
        f"Content-Type: application/json\r\n"
        f"Content-Length: {len(body.encode())}\r\n"
        f"Connection: close\r\n"
        f"\r\n"
        f"{body}"
    )
    s.sendall(request.encode())
    
    response = b""
    while True:
        try:
            chunk = s.recv(4096)
            if not chunk:
                break
            response += chunk
        except socket.timeout:
            break
    
    print(f"4. Raw response ({len(response)} bytes):")
    print(response.decode('utf-8', errors='replace')[:1000])
except Exception as e:
    print(f"4. Raw socket: {type(e).__name__}: {e}")
finally:
    s.close()

# Test 5: Try a NON-training endpoint that also uses POST
print("\n5. Testing inference endpoint...")
try:
    r = requests.post(f"{BASE_URL}/api/v1/lnn/predict", json={
        "model_name": "cutting_force",
        "data_path": UNIWEAR_CSV,
        "device": "cpu"
    }, timeout=10)
    print(f"5. Predict: {r.status_code} - {r.text[:300]}")
except requests.exceptions.Timeout:
    print("5. Predict: TIMEOUT")
except Exception as e:
    print(f"5. Predict: {type(e).__name__}: {e}")
