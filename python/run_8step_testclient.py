"""8-step system test using FastAPI TestClient (no network needed)."""

import json
import time
import sys
import os
from pathlib import Path
from datetime import datetime
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent.resolve()))
from app.main import app

PYTHON_DIR = Path(__file__).parent.resolve()
LOG_FILE = PYTHON_DIR / "test_8step_result.log"
UNIWEAR_CSV = r"C:\Users\Lenovo\AppData\Local\Temp\uniwear.csv"

token_path = Path(os.environ.get("LNN_TOKEN_FILE", str(PYTHON_DIR / ".lnn_token")))
TOKEN = token_path.read_text().strip() if token_path.exists() else "test-token"

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


def check(name, passed, detail=""):
    status = "PASS" if passed else "FAIL"
    log(f"  [{status}] {name}: {detail}")
    results.append({"test": name, "passed": passed, "detail": detail})


# ============================================================
log("=" * 60)
log("LingJing 8-Step System Test (TestClient)")
log("=" * 60)

client = TestClient(app, raise_server_exceptions=False)

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
resp = client.post("/api/v1/lnn/train", json=payload, headers=HEADERS, timeout=30)
elapsed = time.time() - t0
data = resp.json()
job_id = data.get("data", {}).get("job_id", "") if resp.status_code == 200 else ""
if resp.status_code == 200 and elapsed < 3 and job_id:
    check("Test1: Train returns job_id <3s", True, f"job_id={job_id}, {elapsed:.2f}s")
else:
    check(
        "Test1: Train returns job_id <3s",
        False,
        f"code={resp.status_code}, {elapsed:.2f}s, data={data}",
    )

# ====== Test 2: SSE connection ======
log("\n--- Test 2: SSE connection ---")
if job_id:
    t0 = time.time()
    with client.stream(
        "GET", f"/api/v1/jobs/{job_id}/stream", headers=AUTH_ONLY, timeout=30
    ) as r:
        elapsed = time.time() - t0
        if r.status_code == 200 and elapsed < 5:
            check("Test2: SSE connects <5s", True, f"200 in {elapsed:.2f}s")
        else:
            check(
                "Test2: SSE connects <5s",
                False,
                f"code={r.status_code}, {elapsed:.2f}s",
            )
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
t0 = time.time()
resp2 = client.post("/api/v1/lnn/train", json=payload2, headers=HEADERS, timeout=30)
test3_job_id = (
    resp2.json().get("data", {}).get("job_id", "") if resp2.status_code == 200 else ""
)

event_types = []
if test3_job_id:
    time.sleep(0.5)
    with client.stream(
        "GET", f"/api/v1/jobs/{test3_job_id}/stream", headers=AUTH_ONLY, timeout=120
    ) as r:
        if r.status_code == 200:
            current_event = None
            for line in r.iter_lines():
                line = line.strip()
                if line.startswith("event:"):
                    current_event = line[6:].strip()
                elif line.startswith("data:"):
                    data_str = line[5:].strip()
                    if data_str == "[DONE]":
                        event_types.append("done")
                        break
                    try:
                        evt = json.loads(data_str)
                        etype = current_event or evt.get("event", evt.get("type", "?"))
                        progress = evt.get("progress", "?")
                        event_types.append(etype)
                        log(f"  SSE: {etype} progress={progress}")
                        if etype in ("failed", "error", "complete", "cancelled"):
                            break
                    except json.JSONDecodeError:
                        pass

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
resp3 = client.post("/api/v1/lnn/train", json=payload2, headers=HEADERS, timeout=30)
cancel_job_id = (
    resp3.json().get("data", {}).get("job_id", "") if resp3.status_code == 200 else ""
)

if cancel_job_id:
    time.sleep(0.5)
    with client.stream(
        "GET", f"/api/v1/jobs/{cancel_job_id}/stream", headers=AUTH_ONLY, timeout=30
    ) as r:
        t0 = time.time()
        del_resp = client.delete(
            f"/api/v1/jobs/{cancel_job_id}", headers=AUTH_ONLY, timeout=10
        )
        elapsed = time.time() - t0
        if del_resp.status_code == 200 and elapsed < 10:
            check("Test4: Cancel response", True, f"200 in {elapsed:.2f}s")
        else:
            check(
                "Test4: Cancel response",
                False,
                f"code={del_resp.status_code}, {elapsed:.2f}s",
            )

        got_cancelled = False
        if r.status_code == 200:
            current_event = None
            for line in r.iter_lines():
                line = line.strip()
                if line.startswith("event:"):
                    current_event = line[6:].strip()
                elif line.startswith("data:"):
                    data_str = line[5:].strip()
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
        if not got_cancelled:
            check("Test4: SSE cancelled event", False, "Not received")
else:
    check("Test4: Cancel response", False, "Could not start task")
    check("Test4: SSE cancelled event", False, "Skipped")

# ====== Test 5: Job progress info ======
log("\n--- Test 5: Job progress info ---")
if test3_job_id:
    resp5 = client.get(f"/api/v1/jobs/{test3_job_id}", headers=AUTH_ONLY, timeout=10)
    if resp5.status_code == 200:
        job_info = resp5.json().get("data", {})
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
        check("Test5: Job progress info", False, f"HTTP {resp5.status_code}")
else:
    check("Test5: Job progress info", False, "Skipped (no job)")

# ====== Test 6: SSE reconnect ======
log("\n--- Test 6: SSE reconnect basic ---")
if job_id:
    r1 = client.get(f"/api/v1/jobs/{job_id}/stream", headers=AUTH_ONLY, timeout=10)
    r2 = client.get(f"/api/v1/jobs/{job_id}/stream", headers=AUTH_ONLY, timeout=10)
    if r1.status_code == 200 and r2.status_code == 200:
        check("Test6: SSE reconnect", True, "Two connections both 200")
    else:
        check(
            "Test6: SSE reconnect",
            False,
            f"conn1={r1.status_code}, conn2={r2.status_code}",
        )
else:
    check("Test6: SSE reconnect", False, "Skipped")

# ====== Test 7: Task history ======
log("\n--- Test 7: Task history ---")
resp7 = client.get("/api/v1/jobs", headers=AUTH_ONLY, timeout=10)
if resp7.status_code == 200:
    items = resp7.json().get("data", {}).get("jobs", [])
    if len(items) >= 2:
        times = [i.get("created_at", "") for i in items[:5]]
        check(
            "Test7: History records", True, f"{len(items)} jobs, first: {times[0][:19]}"
        )
    else:
        check("Test7: History records", False, f"count={len(items)}")
else:
    check("Test7: History records", False, f"HTTP {resp7.status_code}")

# ====== Test 8: Task re-execute ======
log("\n--- Test 8: Task re-execute ---")
ids = []
for i in range(2):
    resp8 = client.post("/api/v1/lnn/train", json=payload2, headers=HEADERS, timeout=10)
    jid = resp8.json().get("data", {}).get("job_id", "")
    ids.append(jid)
    log(f"  Attempt {i + 1}: job_id={jid[:20] if jid else 'N/A'}...")
if len(set(ids)) == 2 and all(ids):
    check(
        "Test8: Re-execute unique IDs",
        True,
        f"distinct ids: {ids[0][:12]}... vs {ids[1][:12]}...",
    )
else:
    check("Test8: Re-execute unique IDs", False, f"ids: {ids}")

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

# Write log file
LOG_FILE.write_text("\n".join(log_lines), encoding="utf-8")
log(f"\nLog written to: {LOG_FILE}")
print(f"LOG_FILE={LOG_FILE}", flush=True)
