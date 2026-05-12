"""Compact test - starts server, runs predict + train, reports results."""
import subprocess, sys, time, os, json, urllib.request, urllib.error

UNIWEAR = r"C:\Users\Lenovo\AppData\Local\Temp\uniwear.csv"
ROOT = r"c:\Users\Lenovo\Desktop\灵境制造（上线版）"
BASE = "http://localhost:8001"
PASS = 0
FAIL = 0

def log(msg, ok=None):
    global PASS, FAIL
    s = "PASS" if ok else ("FAIL" if ok is False else "INFO")
    if ok: PASS += 1
    if ok is False: FAIL += 1
    print(f"[{s}] {msg}", flush=True)

def http(method, path, data=None, timeout=30):
    url = f"{BASE}{path}"
    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(url, data=body, method=method)
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode())
    except Exception as e:
        return 0, {"error": str(e)}

def wait_server(sec=20):
    for i in range(sec):
        try:
            s, d = http("GET", "/api/v1/lnn/models")
            if s == 200:
                print(f"Server ready after {i+1}s", flush=True)
                return True
        except Exception:
            pass
        time.sleep(1)
    return False

# Kill all python
print("Killing old processes...", flush=True)
os.system('taskkill /F /IM python.exe 2>nul')
os.system('taskkill /F /IM pythonw.exe 2>nul')
time.sleep(2)

# Start server
print("Starting server...", flush=True)
env = os.environ.copy()
env["LNN_AUTH_ENABLED"] = "false"
proc = subprocess.Popen(
    [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"],
    cwd=os.path.join(ROOT, "python"),
    env=env,
    stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL,
)
print(f"Server PID={proc.pid}", flush=True)

if not wait_server():
    log("Server startup FAILED", False)
    proc.terminate()
    sys.exit(1)
log("Server started", True)

# Test 1: Predict with 5 features
print("\n--- Test 1: Predict cutting_force (5 features) ---", flush=True)
status, data = http("POST", "/api/v1/lnn/predict",
    {"model_name": "cutting_force", "input_data": [120.5, 85.3, 65.1, 12000.0, 0.15]})
code = data.get("code", "")
val = data.get("data", {}).get("value", "?")
log(f"Predict cutting_force: code={code}, value={val}", code == 200)

# Test 2: Predict with 2 features
print("\n--- Test 2: Predict wear_prediction (2 features) ---", flush=True)
status, data = http("POST", "/api/v1/lnn/predict",
    {"model_name": "wear_prediction", "input_data": [12.5, 45.0]})
code = data.get("code", "")
val = data.get("data", {}).get("value", "?")
log(f"Predict wear_prediction: code={code}, value={val}", code == 200)

# Test 3: Train
print("\n--- Test 3: Start training ---", flush=True)
t0 = time.time()
status, data = http("POST", "/api/v1/lnn/train", {
    "model_name": "cutting_force",
    "data_path": UNIWEAR,
    "hyperparameters": {"epochs": 5, "batch_size": 32, "learning_rate": 0.001, "optimizer": "adam"},
    "device": "cpu"
})
elapsed = time.time() - t0
job_id = data.get("data", {}).get("job_id", "")
log(f"Train start: job_id={job_id}, {elapsed:.2f}s", bool(job_id) and elapsed < 5)

# Test 4: SSE connection
if job_id:
    print("\n--- Test 4: SSE connection ---", flush=True)
    t0 = time.time()
    try:
        req = urllib.request.Request(f"{BASE}/api/v1/jobs/{job_id}/stream")
        req.add_header("Accept", "text/event-stream")
        with urllib.request.urlopen(req, timeout=10) as r:
            elapsed = time.time() - t0
            log(f"SSE connect: {r.status}, {elapsed:.2f}s", r.status == 200 and elapsed < 5)
    except Exception as e:
        log(f"SSE connect: {e}", False)

# Summary
print("\n" + "=" * 50, flush=True)
print(f"Results: {PASS} PASS, {FAIL} FAIL, {PASS+FAIL} tests", flush=True)

# Cleanup
print("Stopping server...", flush=True)
proc.terminate()
proc.wait(timeout=10)
print("Done.", flush=True)
sys.exit(0 if FAIL == 0 else 1)
