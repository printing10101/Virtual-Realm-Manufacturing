"""8-step system test - self-contained with server management."""

import subprocess
import urllib.request
import urllib.error
import json
import time
import sys
import os
from pathlib import Path
from datetime import datetime

BASE = "http://127.0.0.1:8000"
PYTHON_DIR = Path(__file__).parent.resolve()
LOG_FILE = PYTHON_DIR / "test_8step_result.log"
UNIWEAR_CSV = r"C:\Users\Lenovo\AppData\Local\Temp\uniwear.csv"

token_path = Path(os.environ.get("LNN_TOKEN_FILE", str(PYTHON_DIR / ".lnn_token")))
if token_path.exists():
    TOKEN = token_path.read_text().strip()
else:
    TOKEN = "test-token"

HEADERS = {"Content-Type": "application/json", "Authorization": f"Bearer {TOKEN}"}
AUTH_ONLY = {"Authorization": f"Bearer {TOKEN}"}

log_lines = []
results = []


def log(msg):
    ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    line = f"[{ts}] {msg}"
    log_lines.append(line)
    print(line, flush=True)
    sys.stdout.flush()


def post(path, data, timeout=30):
    req = urllib.request.Request(
        f"{BASE}{path}", data=json.dumps(data).encode(), headers=HEADERS, method="POST"
    )
    try:
        r = urllib.request.urlopen(req, timeout=timeout)
        return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())
    except Exception as e:
        return 0, {"error": str(e)}


def delete_req(path, timeout=10):
    req = urllib.request.Request(f"{BASE}{path}", headers=AUTH_ONLY, method="DELETE")
    try:
        r = urllib.request.urlopen(req, timeout=timeout)
        return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())
    except Exception as e:
        return 0, {"error": str(e)}


def get_req(path, timeout=10):
    req = urllib.request.Request(f"{BASE}{path}", headers=AUTH_ONLY)
    try:
        r = urllib.request.urlopen(req, timeout=timeout)
        return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())
    except Exception as e:
        return 0, {"error": str(e)}


def get_stream(path, timeout=60):
    req = urllib.request.Request(f"{BASE}{path}", headers=AUTH_ONLY)
    try:
        r = urllib.request.urlopen(req, timeout=timeout)
        return r.status, r
    except urllib.error.HTTPError as e:
        return e.code, None
    except Exception:
        return 0, None


def check(name, passed, detail=""):
    status = "PASS" if passed else "FAIL"
    log(f"  [{status}] {name}: {detail}")
    results.append({"test": name, "passed": passed, "detail": detail})


def start_server():
    log("Starting server...")
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
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
        ],
        cwd=str(PYTHON_DIR),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    return proc


def wait_for_server(timeout=30):
    log("Waiting for server...")
    for i in range(timeout):
        try:
            req = urllib.request.Request("http://127.0.0.1:8000/api/health/ping")
            r = urllib.request.urlopen(req, timeout=2)
            if r.status == 200:
                log(f"Server ready after {i + 1}s")
                return True
        except Exception:
            pass
        time.sleep(1)
    return False


# ============================================================
log("=" * 60)
log("LingJing 8-Step System Test (Self-Contained)")
log("=" * 60)

proc = start_server()

if not wait_for_server(timeout=30):
    log("ERROR: Server failed to start")
    if proc:
        proc.terminate()
    sys.exit(1)

try:
    # ====== Test 1: Training start ======
    log("\n--- Test 1: Training start ---")
    payload = {
        "model_name": "cutting_force",
        "data_path": UNIWEAR_CSV,
        "hyperparameters": {
            "epochs": 5,
            "batch_size": 32,
            "learning_rate": 0.001,
            "optimizer": "adam",
        },
        "device": "cpu",
    }
    t0 = time.time()
    code, data = post("/api/v1/lnn/train", payload, timeout=10)
    elapsed = time.time() - t0
    log(f"  HTTP {code}, {elapsed:.2f}s")

    job_id = None
    if code == 200:
        inner = data.get("data", {})
        job_id = inner.get("job_id", "")
        if job_id and elapsed < 3:
            check(
                "Test1: Train returns job_id <3s",
                True,
                f"job_id={job_id[:12]}..., {elapsed:.2f}s",
            )
        elif job_id:
            check("Test1: Train returns job_id <3s", False, f"Slow: {elapsed:.2f}s")
        else:
            check(
                "Test1: Train returns job_id <3s",
                False,
                f"No job_id: {data.get('message', '')}",
            )
    else:
        check(
            "Test1: Train returns job_id <3s",
            False,
            f"HTTP {code}: {json.dumps(data, ensure_ascii=False)[:200]}",
        )

    # ====== Test 2: SSE connection ======
    log("\n--- Test 2: SSE connection ---")
    if job_id:
        t0 = time.time()
        code, stream = get_stream(f"/api/v1/jobs/{job_id}/stream", timeout=10)
        elapsed = time.time() - t0
        if code == 200 and elapsed < 5:
            check("Test2: SSE connects <5s", True, f"200 in {elapsed:.2f}s")
        else:
            check("Test2: SSE connects <5s", False, f"code={code}, {elapsed:.2f}s")
        if stream:
            stream.close()
    else:
        check("Test2: SSE connects <5s", False, "No job_id from Test1")

    # ====== Test 3: SSE event sequence ======
    log("\n--- Test 3: SSE event sequence ---")
    payload2 = {
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
    code, data2 = post("/api/v1/lnn/train", payload2, timeout=10)
    test3_job_id = data2.get("data", {}).get("job_id", "") if code == 200 else ""

    if test3_job_id:
        code, stream = get_stream(f"/api/v1/jobs/{test3_job_id}/stream", timeout=120)
        event_types = []
        if code == 200 and stream:
            try:
                current_event = None
                for line in stream:
                    line_str = line.decode("utf-8", errors="replace").strip()
                    if line_str.startswith("event:"):
                        current_event = line_str[6:].strip()
                    elif line_str.startswith("data:"):
                        data_str = line_str[5:].strip()
                        if data_str == "[DONE]":
                            event_types.append("done")
                            break
                        try:
                            evt = json.loads(data_str)
                            etype = current_event or evt.get(
                                "event", evt.get("type", "?")
                            )
                            progress = evt.get("progress", "?")
                            event_types.append(etype)
                            log(f"  SSE: {etype} progress={progress}")
                            if etype in ("failed", "error", "complete", "cancelled"):
                                break
                        except json.JSONDecodeError:
                            pass
                stream.close()
            except Exception as e:
                log(f"  Stream error: {e}")

        log(f"  Sequence: {' -> '.join(event_types)}")
        has_queued = "queued" in event_types
        has_started = "started" in event_types
        progress_count = sum(1 for t in event_types if t == "progress")
        has_complete = "complete" in event_types

        if has_queued and has_started and progress_count >= 1 and has_complete:
            check(
                "Test3: SSE event sequence",
                True,
                f"queued start progress({progress_count}x) complete",
            )
        else:
            issues = []
            if not has_queued:
                issues.append("no queued")
            if not has_started:
                issues.append("no started")
            if progress_count < 1:
                issues.append(f"progress={progress_count}")
            if not has_complete:
                issues.append("no complete")
            check(
                "Test3: SSE event sequence",
                False,
                "; ".join(issues) if issues else "partial",
            )
    else:
        check("Test3: SSE event sequence", False, "Could not start training task")

    # ====== Test 4: Task cancel ======
    log("\n--- Test 4: Task cancel ---")
    code, data3 = post("/api/v1/lnn/train", payload2, timeout=10)
    cancel_job_id = data3.get("data", {}).get("job_id", "") if code == 200 else ""

    if cancel_job_id:
        time.sleep(0.5)
        code, stream = get_stream(f"/api/v1/jobs/{cancel_job_id}/stream", timeout=15)

        t0 = time.time()
        code2, del_data = delete_req(f"/api/v1/jobs/{cancel_job_id}", timeout=10)
        elapsed = time.time() - t0
        if code2 == 200 and elapsed < 10:
            check("Test4: Cancel response", True, f"200 in {elapsed:.2f}s")
        else:
            check("Test4: Cancel response", False, f"code={code2}, {elapsed:.2f}s")

        got_cancelled = False
        if code == 200 and stream:
            try:
                current_event = None
                for line in stream:
                    line_str = line.decode("utf-8", errors="replace").strip()
                    if line_str.startswith("event:"):
                        current_event = line_str[6:].strip()
                    elif line_str.startswith("data:"):
                        data_str = line_str[5:].strip()
                        if data_str == "[DONE]":
                            break
                        try:
                            evt = json.loads(data_str)
                            etype = current_event or evt.get("event", "")
                            if etype == "cancelled":
                                got_cancelled = True
                                check("Test4: SSE cancelled event", True, "received")
                                break
                        except json.JSONDecodeError:
                            pass
                stream.close()
            except Exception as e:
                log(f"  Stream error: {e}")
        if not got_cancelled:
            check("Test4: SSE cancelled event", False, "Not received")
    else:
        check("Test4: Cancel response", False, "Could not start task")
        check("Test4: SSE cancelled event", False, "Skipped")

    # ====== Test 5: Job progress info ======
    log("\n--- Test 5: Job progress info ---")
    if test3_job_id:
        code, data5 = get_req(f"/api/v1/jobs/{test3_job_id}", timeout=10)
        if code == 200:
            job_info = data5.get("data", {})
            has_progress = "progress" in job_info
            has_status = "status" in job_info
            if has_progress and has_status:
                check(
                    "Test5: Job progress info",
                    True,
                    f"status={job_info.get('status')}, progress={job_info.get('progress')}",
                )
            else:
                check(
                    "Test5: Job progress info",
                    False,
                    f"Fields: {list(job_info.keys())[:5]}",
                )
        else:
            check("Test5: Job progress info", False, f"HTTP {code}")
    else:
        check("Test5: Job progress info", False, "Skipped (no job)")

    # ====== Test 6: SSE reconnect ======
    log("\n--- Test 6: SSE reconnect basic ---")
    if job_id:
        code1, s1 = get_stream(f"/api/v1/jobs/{job_id}/stream", timeout=10)
        code2, s2 = get_stream(f"/api/v1/jobs/{job_id}/stream", timeout=10)
        if code1 == 200 and code2 == 200:
            check("Test6: SSE reconnect", True, "Two connections both 200")
        else:
            check("Test6: SSE reconnect", False, f"conn1={code1}, conn2={code2}")
        if s1:
            s1.close()
        if s2:
            s2.close()
    else:
        check("Test6: SSE reconnect", False, "Skipped")

    # ====== Test 7: Task history ======
    log("\n--- Test 7: Task history ---")
    code, data7 = get_req("/api/v1/jobs", timeout=10)
    if code == 200:
        jobs = data7.get("data", {}).get("jobs", [])
        total = data7.get("data", {}).get("total", len(jobs))
        log(f"  Records: {total}")
        if total > 0:
            sample = jobs[0]
            required = ["job_id", "status", "created_at"]
            missing = [f for f in required if f not in sample]
            if not missing:
                check("Test7: History records", True, f"{total} records, fields OK")
            else:
                check("Test7: History records", False, f"Missing: {missing}")
            times = [j.get("created_at", "") for j in jobs]
            if times == sorted(times, reverse=True):
                check("Test7: Time sorting", True, "Latest first")
            else:
                check("Test7: Time sorting", False, "Not sorted")
        else:
            check("Test7: History records", True, "0 records (no tasks run)")
    else:
        check(
            "Test7: History records",
            False,
            f"HTTP {code}: {json.dumps(data7, ensure_ascii=False)[:200]}",
        )

    # ====== Test 8: Task re-execute ======
    log("\n--- Test 8: Task re-execute ---")
    job_ids = []
    for i in range(2):
        code, data8 = post("/api/v1/lnn/train", payload2, timeout=10)
        jid = data8.get("data", {}).get("job_id", "") if code == 200 else ""
        job_ids.append(jid)
        log(f"  Attempt {i + 1}: job_id={jid[:20] if jid else 'N/A'}...")
        time.sleep(0.3)
    if len(job_ids) == 2 and job_ids[0] and job_ids[1] and job_ids[0] != job_ids[1]:
        check("Test8: Re-execute unique IDs", True, "Two different IDs")
    else:
        check("Test8: Re-execute unique IDs", False, f"ids: {job_ids}")

    # ====== Summary ======
    log("\n" + "=" * 60)
    log("TEST SUMMARY")
    log("=" * 60)
    passed = sum(1 for r in results if r["passed"])
    failed = sum(1 for r in results if not r["passed"])
    for r in results:
        s = "PASS" if r["passed"] else "FAIL"
        log(f"  [{s}] {r['test']}: {r['detail']}")
    log(f"\nTotal: {passed} PASS, {failed} FAIL, {len(results)} tests")

finally:
    log("\nStopping server...")
    if proc:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
    log("Done.")

# Write log file
LOG_FILE.write_text("\n".join(log_lines), encoding="utf-8")
log(f"\nLog written to: {LOG_FILE}")
print(f"LOG_FILE={LOG_FILE}", flush=True)
