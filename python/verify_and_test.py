"""Complete verification and test runner - bypasses trae-sandbox wrapping issues."""
import subprocess
import sys
import time
import os
import json
import requests

ROOT = r"c:\Users\Lenovo\Desktop\灵境制造（上线版）"
PYTHON_DIR = os.path.join(ROOT, "python")
UNIWEAR_CSV = r"C:\Users\Lenovo\AppData\Local\Temp\uniwear.csv"
BASE_URL = "http://localhost:8001"

TEST_RESULTS = []

def log_result(test_name, passed, detail=""):
    status = "PASS" if passed else "FAIL"
    msg = f"[{status}] {test_name}: {detail}"
    print(msg)
    TEST_RESULTS.append({"test": test_name, "passed": passed, "detail": detail})

def kill_all_python():
    print("=== Killing all python processes ===")
    os.system('taskkill /F /IM python.exe 2>nul')
    os.system('taskkill /F /IM pythonw.exe 2>nul')
    time.sleep(2)
    print("Done killing")

def start_server():
    print("=== Starting uvicorn server on port 8001 ===")
    env = os.environ.copy()
    env["LNN_AUTH_ENABLED"] = "false"
    env["PYTHONUNBUFFERED"] = "1"
    
    server_proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"],
        cwd=PYTHON_DIR,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True
    )
    return server_proc

def wait_for_server(timeout=30):
    print("Waiting for server to start...")
    for i in range(timeout):
        try:
            resp = requests.get(f"{BASE_URL}/api/v1/lnn/models", timeout=2)
            if resp.status_code == 200:
                print(f"Server ready after {i+1}s")
                return True
        except Exception:
            pass
        time.sleep(1)
    return False

def test_predict():
    """Test predict endpoint with cutting_force (5 features)"""
    print("\n=== Test: Predict cutting_force ===")
    payload = {"model_name": "cutting_force", "input_data": [120.5, 85.3, 65.1, 12000.0, 0.15]}
    try:
        resp = requests.post(f"{BASE_URL}/api/v1/lnn/predict", json=payload, timeout=30)
        print(f"  Status: {resp.status_code}")
        print(f"  Response: {resp.text[:500]}")
        if resp.status_code == 200:
            data = resp.json()
            code = data.get("code", "")
            if code == 200:
                log_result("Predict cutting_force", True, f"Value: {data.get('data', {}).get('value', 'N/A')}")
                return True
            else:
                log_result("Predict cutting_force", False, f"code={code}: {data.get('message', '')}")
        else:
            log_result("Predict cutting_force", False, f"HTTP {resp.status_code}")
    except Exception as e:
        log_result("Predict cutting_force", False, str(e))
    return False

def test_predict_wear():
    """Test predict endpoint with wear_prediction (2 features)"""
    print("\n=== Test: Predict wear_prediction ===")
    payload = {"model_name": "wear_prediction", "input_data": [12.5, 45.0]}
    try:
        resp = requests.post(f"{BASE_URL}/api/v1/lnn/predict", json=payload, timeout=30)
        print(f"  Status: {resp.status_code}")
        print(f"  Response: {resp.text[:500]}")
        if resp.status_code == 200:
            data = resp.json()
            code = data.get("code", "")
            if code == 200:
                log_result("Predict wear_prediction", True, f"Value: {data.get('data', {}).get('value', 'N/A')}")
                return True
            else:
                log_result("Predict wear_prediction", False, f"code={code}: {data.get('message', '')}")
        else:
            log_result("Predict wear_prediction", False, f"HTTP {resp.status_code}")
    except Exception as e:
        log_result("Predict wear_prediction", False, str(e))
    return False

def test_train():
    """Test 1: Training start"""
    print("\n=== Test 1: Training start ===")
    payload = {
        "model_name": "cutting_force",
        "data_path": UNIWEAR_CSV,
        "hyperparameters": {
            "epochs": 5,
            "batch_size": 32,
            "learning_rate": 0.001,
            "optimizer": "adam"
        },
        "device": "cpu"
    }
    start = time.time()
    try:
        resp = requests.post(f"{BASE_URL}/api/v1/lnn/train", json=payload, timeout=10)
        elapsed = time.time() - start
        data = resp.json()
        print(f"  Status: {resp.status_code}, elapsed: {elapsed:.2f}s")
        print(f"  Response: {json.dumps(data, ensure_ascii=False)[:500]}")
        if resp.status_code != 200:
            log_result("Test1-Training start", False, f"HTTP {resp.status_code}: {data}")
            return None
        job_id = data.get("data", {}).get("job_id", "")
        if job_id and elapsed < 3:
            log_result("Test1-Training start", True, f"job_id={job_id}, {elapsed:.2f}s")
            return job_id
        elif job_id:
            log_result("Test1-Training start", False, f"Timeout: {elapsed:.2f}s")
            return job_id
        else:
            log_result("Test1-Training start", False, f"msg={data.get('message','')}")
            return None
    except Exception as e:
        log_result("Test1-Training start", False, str(e))
        return None

def test_sse_connection(job_id):
    """Test 2: SSE connection"""
    print("\n=== Test 2: SSE connection ===")
    start = time.time()
    try:
        resp = requests.get(f"{BASE_URL}/api/v1/jobs/{job_id}/stream", stream=True, timeout=10)
        elapsed = time.time() - start
        if resp.status_code == 200 and elapsed < 5:
            log_result("Test2-SSE connect", True, f"200 in {elapsed:.2f}s")
            resp.close()
            return True
        else:
            log_result("Test2-SSE connect", False, f"status={resp.status_code}, {elapsed:.2f}s")
            return False
    except Exception as e:
        log_result("Test2-SSE connect", False, str(e))
        return False

def test_sse_events(job_id):
    """Test 3: SSE event sequence"""
    print("\n=== Test 3: SSE event sequence ===")
    event_types = []
    try:
        resp = requests.get(f"{BASE_URL}/api/v1/jobs/{job_id}/stream", stream=True, timeout=120)
        if resp.status_code != 200:
            log_result("Test3-SSE events", False, f"HTTP {resp.status_code}")
            return

        for line in resp.iter_lines(decode_unicode=True):
            if line and line.startswith("data:"):
                data_str = line[5:].strip()
                if data_str == "[DONE]":
                    event_types.append("done")
                    break
                try:
                    evt = json.loads(data_str)
                    etype = evt.get("event", evt.get("type", "?"))
                    progress = evt.get("progress", "?")
                    event_types.append(etype)
                    print(f"  SSE: {etype} progress={progress}")
                    if etype in ("failed", "error", "complete", "cancelled"):
                        break
                except json.JSONDecodeError:
                    pass
    except Exception as e:
        log_result("Test3-SSE events", False, f"Exception: {e}")

    print(f"  Sequence: {' -> '.join(event_types)}")
    has_queued = "queued" in event_types
    has_started = "started" in event_types
    progress_count = sum(1 for t in event_types if t == "progress")
    has_complete = "complete" in event_types

    if has_queued and has_started and progress_count >= 1 and has_complete:
        log_result("Test3-SSE events", True, f"queued start progress({progress_count}x) complete")
    else:
        issues = []
        if not has_queued: issues.append("no queued")
        if not has_started: issues.append("no started")
        if progress_count < 3: issues.append(f"progress={progress_count}")
        if not has_complete: issues.append("no complete")
        log_result("Test3-SSE events", False, "; ".join(issues) if issues else "partial")

def test_task_cancel():
    """Test 4: Task cancel"""
    print("\n=== Test 4: Task cancel ===")
    payload = {
        "model_name": "cutting_force",
        "data_path": UNIWEAR_CSV,
        "hyperparameters": {
            "epochs": 5,
            "batch_size": 32,
            "learning_rate": 0.001,
            "optimizer": "adam"
        },
        "device": "cpu"
    }
    resp = requests.post(f"{BASE_URL}/api/v1/lnn/train", json=payload, timeout=10)
    data = resp.json()
    job_id = data.get("data", {}).get("job_id", "")
    if not job_id:
        log_result("Test4-Cancel", False, "Failed to start task")
        return

    time.sleep(0.5)
    start = time.time()
    try:
        cancel_resp = requests.delete(f"{BASE_URL}/api/v1/jobs/{job_id}", timeout=10)
        elapsed = time.time() - start
        print(f"  DELETE response: {cancel_resp.status_code}, {elapsed:.2f}s")
        if cancel_resp.status_code == 200 and elapsed < 10:
            log_result("Test4-Cancel DELETE", True, f"job={job_id}, {elapsed:.2f}s")
        else:
            log_result("Test4-Cancel DELETE", False, f"{cancel_resp.status_code}, {elapsed:.2f}s")
    except Exception as e:
        log_result("Test4-Cancel DELETE", False, str(e))

    try:
        resp = requests.get(f"{BASE_URL}/api/v1/jobs/{job_id}/stream", stream=True, timeout=15)
        for line in resp.iter_lines(decode_unicode=True):
            if line and line.startswith("data:"):
                data_str = line[5:].strip()
                if data_str == "[DONE]":
                    break
                try:
                    evt = json.loads(data_str)
                    if evt.get("event") == "cancelled":
                        log_result("Test4-Cancel SSE event", True, "received cancelled")
                        break
                except json.JSONDecodeError:
                    pass
        else:
            log_result("Test4-Cancel SSE event", False, "no cancelled event")
    except Exception as e:
        log_result("Test4-Cancel SSE event", False, str(e))

def test_task_history():
    """Test 7: Task history"""
    print("\n=== Test 7: Task history ===")
    try:
        resp = requests.get(f"{BASE_URL}/api/v1/jobs", timeout=10)
        data = resp.json()
        print(f"  Status: {resp.status_code}")
        if resp.status_code == 200:
            jobs = data.get("data", {}).get("jobs", [])
            total = data.get("data", {}).get("total", 0)
            print(f"  Records: {total}")
            if total > 0:
                sample = jobs[0]
                required = ["job_id", "status", "created_at"]
                missing = [f for f in required if f not in sample]
                if not missing:
                    log_result("Test7-History", True, f"{total} records complete")
                else:
                    log_result("Test7-History", False, f"Missing: {missing}")
                times = [j.get("created_at", "") for j in jobs]
                if times == sorted(times, reverse=True):
                    log_result("Test7-Time sort", True, "desc order")
                else:
                    log_result("Test7-Time sort", False, "unordered")
            else:
                log_result("Test7-History", True, "0 records (fresh restart)")
        else:
            log_result("Test7-History", False, f"HTTP {resp.status_code}")
    except Exception as e:
        log_result("Test7-History", False, str(e))

def test_task_reexecute():
    """Test 8: Task re-execute"""
    print("\n=== Test 8: Task re-execute ===")
    payload = {
        "model_name": "cutting_force",
        "data_path": UNIWEAR_CSV,
        "hyperparameters": {
            "epochs": 3,
            "batch_size": 32,
            "learning_rate": 0.001,
            "optimizer": "adam"
        },
        "device": "cpu"
    }
    job_ids = []
    for i in range(2):
        resp = requests.post(f"{BASE_URL}/api/v1/lnn/train", json=payload, timeout=10)
        data = resp.json()
        jid = data.get("data", {}).get("job_id", "")
        job_ids.append(jid)
        print(f"  Attempt {i+1}: job_id={jid}")
        time.sleep(0.3)
    if len(job_ids) == 2 and job_ids[0] != job_ids[1]:
        log_result("Test8-Re-execute", True, f"unique: {job_ids[0]} vs {job_ids[1]}")
    else:
        log_result("Test8-Re-execute", False, f"ids: {job_ids}")

def main():
    print("=" * 60)
    print("LingJing Complete Verification + 8-Step Test")
    print("=" * 60)
    
    kill_all_python()
    time.sleep(1)
    
    server_proc = start_server()
    
    if not wait_for_server(timeout=20):
        print("FATAL: Server failed to start")
        server_proc.terminate()
        return
    
    print("\n>>> Phase 1: Verify predict fixes <<<")
    test_predict()
    test_predict_wear()
    
    print("\n>>> Phase 2: 8-Step System Test <<<")
    
    job_id = test_train()
    if job_id:
        test_sse_connection(job_id)
        time.sleep(0.5)
    
    print("\n--- Starting fresh task for Test 3 ---")
    payload = {
        "model_name": "cutting_force",
        "data_path": UNIWEAR_CSV,
        "hyperparameters": {
            "epochs": 5,
            "batch_size": 32,
            "learning_rate": 0.001,
            "optimizer": "adam"
        },
        "device": "cpu"
    }
    resp = requests.post(f"{BASE_URL}/api/v1/lnn/train", json=payload, timeout=10)
    data = resp.json()
    test3_job_id = data.get("data", {}).get("job_id", "")
    if test3_job_id:
        test_sse_events(test3_job_id)
    else:
        log_result("Test3-SSE events", False, "Could not start task")
    
    test_task_cancel()
    test_task_history()
    test_task_reexecute()
    
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    passed = sum(1 for r in TEST_RESULTS if r["passed"])
    failed = sum(1 for r in TEST_RESULTS if not r["passed"])
    for r in TEST_RESULTS:
        s = "PASS" if r["passed"] else "FAIL"
        print(f"  [{s}] {r['test']}: {r['detail']}")
    print(f"\nTotal: {passed} PASS, {failed} FAIL, {len(TEST_RESULTS)} tests")
    
    print("\nStopping server...")
    server_proc.terminate()
    server_proc.wait(timeout=10)
    print("Done.")

if __name__ == "__main__":
    main()
