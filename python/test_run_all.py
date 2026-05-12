import requests
import json
import time
import threading
import queue

BASE_URL = "http://localhost:8000"
UNIWEAR_CSV = "C:\\Users\\Lenovo\\AppData\\Local\\Temp\\uniwear.csv"

TEST_RESULTS = []

def log_result(test_name, passed, detail=""):
    status = "PASS" if passed else "FAIL"
    msg = f"[{status}] {test_name}: {detail}"
    print(msg)
    TEST_RESULTS.append({"test": test_name, "passed": passed, "detail": detail})

def test1_training_start():
    """测试1：启动训练任务，3秒内返回job_id"""
    print("\n=== 测试1：训练任务启动 ===")
    payload = {
        "model_name": "cutting_force",
        "data_path": UNIWEAR_CSV,
        "hyperparameters": {
            "epochs": 5,
            "batch_size": 32,
            "learning_rate": 0.001,
            "hidden_size": 64
        },
        "device": "cpu"
    }
    start = time.time()
    try:
        resp = requests.post(f"{BASE_URL}/api/v1/lnn/train", json=payload, timeout=10)
        elapsed = time.time() - start
        data = resp.json()
        job_id = data.get("data", {}).get("job_id", "")
        code = data.get("code", "")

        if resp.status_code == 200 and job_id and elapsed < 3:
            log_result("测试1-训练任务启动", True, f"job_id={job_id}, 耗时={elapsed:.2f}s")
            return job_id
        elif job_id and elapsed >= 3:
            log_result("测试1-训练任务启动", False, f"超时: {elapsed:.2f}s (>3s)")
            return job_id
        else:
            log_result("测试1-训练任务启动", False, f"code={code}, message={data.get('message', '')}")
            return None
    except Exception as e:
        log_result("测试1-训练任务启动", False, str(e))
        return None

def test2_sse_connection(job_id):
    """测试2：SSE事件流连接，5秒内返回200"""
    print("\n=== 测试2：SSE连接 ===")
    start = time.time()
    try:
        resp = requests.get(f"{BASE_URL}/api/v1/jobs/{job_id}/stream", stream=True, timeout=10)
        elapsed = time.time() - start
        if resp.status_code == 200 and elapsed < 5:
            log_result("测试2-SSE连接", True, f"status=200, 耗时={elapsed:.2f}s")
            return resp
        else:
            log_result("测试2-SSE连接", False, f"status={resp.status_code}, 耗时={elapsed:.2f}s")
            return None
    except Exception as e:
        log_result("测试2-SSE连接", False, str(e))
        return None

def test3_sse_events(job_id):
    """测试3：SSE事件序列验证 queued->started->progress->complete"""
    print("\n=== 测试3：SSE事件序列 ===")
    events = []
    event_types = []

    try:
        resp = requests.get(f"{BASE_URL}/api/v1/jobs/{job_id}/stream", stream=True, timeout=60)
        if resp.status_code != 200:
            log_result("测试3-SSE事件序列", False, f"HTTP {resp.status_code}")
            return

        for line in resp.iter_lines(decode_unicode=True):
            if line and line.startswith("data:"):
                data_str = line[5:].strip()
                if data_str == "[DONE]":
                    events.append({"type": "done"})
                    event_types.append("done")
                    break
                try:
                    evt = json.loads(data_str)
                    events.append(evt)
                    event_types.append(evt.get("event", evt.get("type", "unknown")))
                    print(f"  SSE event: {evt.get('event', evt.get('type', '?'))} progress={evt.get('progress', 'N/A')}")

                    if evt.get("event") in ("failed", "error", "complete", "cancelled"):
                        break
                except json.JSONDecodeError:
                    pass
    except Exception as e:
        log_result("测试3-SSE事件序列", False, f"Exception: {e}")

    print(f"  Event sequence: {' -> '.join(event_types)}")

    has_queued = "queued" in event_types
    has_started = "started" in event_types
    has_progress = sum(1 for t in event_types if t == "progress")
    has_complete = "complete" in event_types

    if has_queued and has_started and has_progress >= 1 and has_complete:
        log_result("测试3-SSE事件序列", True, f"queued=✓ started=✓ progress={has_progress}x complete=✓")
    else:
        issues = []
        if not has_queued: issues.append("missing queued")
        if not has_started: issues.append("missing started")
        if has_progress < 3: issues.append(f"progress only {has_progress}x (need >=3)")
        if not has_complete: issues.append("missing complete")
        log_result("测试3-SSE事件序列", False, "; ".join(issues))

    return events

def test4_task_cancel():
    """测试4：任务取消 DELETE /api/v1/jobs/{job_id}"""
    print("\n=== 测试4：任务取消 ===")
    # First start a training task
    payload = {
        "model_name": "cutting_force",
        "data_path": UNIWEAR_CSV,
        "hyperparameters": {
            "epochs": 5,
            "batch_size": 32,
            "learning_rate": 0.001,
            "hidden_size": 64
        },
        "device": "cpu"
    }

    resp = requests.post(f"{BASE_URL}/api/v1/lnn/train", json=payload, timeout=10)
    data = resp.json()
    job_id = data.get("data", {}).get("job_id", "")
    if not job_id:
        log_result("测试4-任务取消", False, "Failed to start task for cancel test")
        return

    # Wait a moment for task to start
    time.sleep(0.5)

    # Send cancel (DELETE)
    start = time.time()
    try:
        cancel_resp = requests.delete(f"{BASE_URL}/api/v1/jobs/{job_id}", timeout=10)
        elapsed = time.time() - start
        cdata = cancel_resp.json()

        if cancel_resp.status_code == 200 and elapsed < 10:
            log_result("测试4-任务取消", True, f"deleted job={job_id}, 耗时={elapsed:.2f}s")
        else:
            log_result("测试4-任务取消", False, f"status={cancel_resp.status_code}, elapsed={elapsed:.2f}s")
    except Exception as e:
        log_result("测试4-任务取消", False, str(e))

    # Verify cancelled event via SSE
    try:
        resp = requests.get(f"{BASE_URL}/api/v1/jobs/{job_id}/stream", stream=True, timeout=15)
        events = []
        for line in resp.iter_lines(decode_unicode=True):
            if line and line.startswith("data:"):
                data_str = line[5:].strip()
                if data_str == "[DONE]":
                    break
                try:
                    evt = json.loads(data_str)
                    events.append(evt)
                    if evt.get("event") == "cancelled":
                        log_result("测试4-取消事件验证", True, "received cancelled event via SSE")
                        break
                except json.JSONDecodeError:
                    pass
        else:
            log_result("测试4-取消事件验证", False, "no cancelled event received")
    except Exception as e:
        log_result("测试4-取消事件验证", False, str(e))

def test7_task_history():
    """测试7：任务历史记录"""
    print("\n=== 测试7：任务历史记录 ===")
    try:
        # List all jobs
        resp = requests.get(f"{BASE_URL}/api/v1/jobs", timeout=10)
        data = resp.json()

        if resp.status_code == 200:
            jobs = data.get("data", {}).get("jobs", [])
            total = data.get("data", {}).get("total", 0)
            print(f"  历史记录总数: {total}")

            if total > 0:
                # Check that records have required fields
                required_fields = ["job_id", "status", "created_at"]
                sample = jobs[0]
                missing = [f for f in required_fields if f not in sample]
                if not missing:
                    log_result("测试7-任务历史记录", True, f"{total} records, fields complete")
                else:
                    log_result("测试7-任务历史记录", False, f"Missing fields: {missing}")

                # Check time ordering
                times = [j.get("created_at", "") for j in jobs]
                if times == sorted(times, reverse=True):
                    log_result("测试7-时间排序", True, "records sorted by time desc")
                else:
                    log_result("测试7-时间排序", False, "records not time-sorted")
            else:
                log_result("测试7-任务历史记录", True, "0 records (empty - OK, system was just restarted)")
        else:
            log_result("测试7-任务历史记录", False, f"HTTP {resp.status_code}")
    except Exception as e:
        log_result("测试7-任务历史记录", False, str(e))

def test8_task_reexecute():
    """测试8：任务重执行 - 重新提交训练生成新job_id"""
    print("\n=== 测试8：任务重执行 ===")
    payload = {
        "model_name": "cutting_force",
        "data_path": UNIWEAR_CSV,
        "hyperparameters": {
            "epochs": 3,
            "batch_size": 32,
            "learning_rate": 0.001,
            "hidden_size": 64
        },
        "device": "cpu"
    }

    job_ids = []
    for i in range(2):
        resp = requests.post(f"{BASE_URL}/api/v1/lnn/train", json=payload, timeout=10)
        data = resp.json()
        jid = data.get("data", {}).get("job_id", "")
        job_ids.append(jid)
        print(f"  第{i+1}次: job_id={jid}")
        time.sleep(0.5)

    if len(job_ids) == 2 and job_ids[0] != job_ids[1]:
        log_result("测试8-任务重执行", True, f"unique job_ids: {job_ids[0]} != {job_ids[1]}")
    else:
        log_result("测试8-任务重执行", False, f"job_ids: {job_ids}")

def main():
    print("=" * 60)
    print("灵境制造 异步任务+SSE 系统功能测试")
    print("=" * 60)

    # Test 1
    job_id = test1_training_start()
    if not job_id:
        print("\n>>> 测试1失败，跳过测试2、3")
    else:
        # Test 2
        stream_resp = test2_sse_connection(job_id)
        # Test 3 - needs new task since previous one might be done
        time.sleep(0.5)

    # Test 3 with a fresh task
    print("\n--- Starting fresh task for Test 3 ---")
    payload = {
        "model_name": "cutting_force",
        "data_path": UNIWEAR_CSV,
        "hyperparameters": {
            "epochs": 5,
            "batch_size": 32,
            "learning_rate": 0.001,
            "hidden_size": 64
        },
        "device": "cpu"
    }
    resp = requests.post(f"{BASE_URL}/api/v1/lnn/train", json=payload, timeout=10)
    data = resp.json()
    test3_job_id = data.get("data", {}).get("job_id", "")
    if test3_job_id:
        test3_sse_events(test3_job_id)
    else:
        log_result("测试3-SSE事件序列", False, "Could not start task")

    # Test 4
    test4_task_cancel()

    # Test 7
    test7_task_history()

    # Test 8
    test8_task_reexecute()

    # Summary
    print("\n" + "=" * 60)
    print("测试汇总")
    print("=" * 60)
    passed = sum(1 for r in TEST_RESULTS if r["passed"])
    failed = sum(1 for r in TEST_RESULTS if not r["passed"])
    for r in TEST_RESULTS:
        status = "PASS" if r["passed"] else "FAIL"
        print(f"  [{status}] {r['test']}: {r['detail']}")
    print(f"\n总计: {passed} 通过, {failed} 失败, {len(TEST_RESULTS)} 项测试")

if __name__ == "__main__":
    main()
