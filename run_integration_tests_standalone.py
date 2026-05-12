import json
import os
import sys
import time
from pathlib import Path

import requests

BASE_URL = "http://localhost:8000"

passed = 0
failed = 0
errors = []

def run_test(name, func):
    global passed, failed
    try:
        func()
        passed += 1
        print(f"  PASS: {name}")
    except Exception as e:
        failed += 1
        errors.append((name, str(e)))
        print(f"  FAIL: {name} - {e}")

def print_section(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")

# ===== Test 1: Create RB Token =====
print_section("Test 1: Create RB Token")
def test_create_rb_token():
    r = requests.post(f"{BASE_URL}/api/agent/v1/tokens", json={
        "scopes": ["R", "B"], "expires_in": 3600, "paper_only": True
    })
    assert r.status_code == 200, f"创建Token失败: {r.text}"
    td = r.json()
    assert td["data"]["token"].startswith("lj_agent_"), f"Token格式错误: {td['data']['token']}"
    assert len(td["data"]["token"]) == len("lj_agent_") + 32, f"Token长度错误: {len(td['data']['token'])}"
run_test("Create RB Token", test_create_rb_token)

# ===== Test 2: Models List =====
print_section("Test 2: Models List")
def test_models_list():
    r = requests.post(f"{BASE_URL}/api/agent/v1/tokens", json={
        "scopes": ["R", "B"], "expires_in": 3600, "paper_only": True
    })
    token = r.json()["data"]["token"]
    r2 = requests.get(f"{BASE_URL}/api/agent/v1/models", headers={"Authorization": f"Bearer {token}"})
    assert r2.status_code == 200, f"模型列表失败: {r2.text}"
run_test("Models List", test_models_list)

# ===== Test 3: T Operation Forbidden =====
print_section("Test 3: T Operation Forbidden (Permission Control)")
def test_t_operation_forbidden():
    r = requests.post(f"{BASE_URL}/api/agent/v1/tokens", json={
        "scopes": ["R", "B"], "expires_in": 3600, "paper_only": True
    })
    token = r.json()["data"]["token"]
    r2 = requests.post(f"{BASE_URL}/api/agent/v1/execute",
        headers={"Authorization": f"Bearer {token}"},
        json={"model_name": "test", "parameters": {"p1": 1.0}, "paper_only": True}
    )
    assert r2.status_code == 403, f"预期403, 实际: {r2.status_code}, {r2.text}"
run_test("T Operation Forbidden", test_t_operation_forbidden)

# ===== Test 4: Paper-Only Mode =====
print_section("Test 4: Paper-Only Mode (Simulation)")
def test_paper_only_simulation():
    r = requests.post(f"{BASE_URL}/api/agent/v1/tokens", json={
        "scopes": ["R", "B", "T"], "expires_in": 3600, "paper_only": True
    })
    token = r.json()["data"]["token"]
    r2 = requests.post(f"{BASE_URL}/api/agent/v1/execute",
        headers={
            "Authorization": f"Bearer {token}",
            "Idempotency-Key": f"po_{int(time.time())}"
        },
        json={"model_name": "test", "parameters": {"p1": 1.0}}
    )
    assert r2.status_code == 200, f"Paper-only失败: {r2.text}"
    d = r2.json().get("data", {})
    assert d.get("paper_only") is True or d.get("mode") == "simulation" or d.get("simulated") is True, \
        f"缺少paper_only标识: {d}"
run_test("Paper-Only Simulation", test_paper_only_simulation)

# ===== Test 5: Idempotency =====
print_section("Test 5: Idempotency Key")
def test_same_idempotency_key():
    r = requests.post(f"{BASE_URL}/api/agent/v1/tokens", json={
        "scopes": ["R", "B"], "expires_in": 3600, "paper_only": True
    })
    token = r.json()["data"]["token"]
    key = f"idem_{int(time.time())}"
    payload = {"model_name": "idem", "data_path": "/tmp/test.csv"}
    t1 = time.time()
    r1 = requests.post(f"{BASE_URL}/api/agent/v1/train",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": key}, json=payload)
    e1 = time.time() - t1
    assert r1.status_code == 200, f"第一次train失败: {r1.text}"
    t2 = time.time()
    r2 = requests.post(f"{BASE_URL}/api/agent/v1/train",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": key}, json=payload)
    e2 = time.time() - t2
    assert r2.status_code == 200, f"第二次train失败: {r2.text}"
    j1 = r1.json().get("data", {}).get("job_id")
    j2 = r2.json().get("data", {}).get("job_id")
    assert j1 == j2, f"job_id不同: {j1} vs {j2}"
    assert e2 < e1 * 0.5, f"第二次耗时未缩短: {e2:.3f}s vs {e1:.3f}s"
run_test("Same Idempotency Key", test_same_idempotency_key)

# ===== Test 6: Batch Token Revocation =====
print_section("Test 6: Batch Token Revocation (Revoke All T Tokens)")
def test_revoke_all_t_tokens():
    r = requests.post(f"{BASE_URL}/api/agent/v1/tokens", json={
        "scopes": ["R", "B"], "expires_in": 3600, "paper_only": True
    })
    rb_token = r.json()["data"]["token"]

    t_tokens = []
    for _ in range(3):
        r = requests.post(f"{BASE_URL}/api/agent/v1/tokens", json={
            "scopes": ["R", "T"], "expires_in": 3600, "paper_only": True
        })
        t_tokens.append(r.json()["data"]["token"])

    r = requests.post(f"{BASE_URL}/api/agent/v1/tokens", json={
        "scopes": ["R", "W", "B"], "expires_in": 3600, "paper_only": True
    })
    non_t_token = r.json()["data"]["token"]

    for tok in t_tokens:
        r = requests.get(f"{BASE_URL}/api/agent/v1/models", headers={"Authorization": f"Bearer {tok}"})
        assert r.status_code == 200, "撤销前T Token应可用"

    r = requests.post(f"{BASE_URL}/api/agent/v1/tokens/revoke-t-all",
        headers={"Authorization": f"Bearer {rb_token}"})
    assert r.status_code == 200, f"撤销请求失败: {r.text}"
    rc = r.json().get("data", {}).get("revoked_count", 0)
    assert rc >= 3, f"应撤销至少3个T Token, 实际: {rc}"

    for tok in t_tokens:
        r = requests.get(f"{BASE_URL}/api/agent/v1/models", headers={"Authorization": f"Bearer {tok}"})
        assert r.status_code in [401, 403], f"已撤销T Token仍可访问: {r.status_code}"

    r = requests.get(f"{BASE_URL}/api/agent/v1/models", headers={"Authorization": f"Bearer {non_t_token}"})
    assert r.status_code == 200, "非T Token应不受影响"
run_test("Revoke All T Tokens", test_revoke_all_t_tokens)

# ===== Test 7: Audit Log =====
print_section("Test 7: Audit Log Entries")
def test_audit_log_entries():
    r = requests.post(f"{BASE_URL}/api/agent/v1/tokens", json={
        "scopes": ["R", "B"], "expires_in": 3600, "paper_only": True
    })
    token = r.json()["data"]["token"]

    requests.get(f"{BASE_URL}/api/agent/v1/models", headers={"Authorization": f"Bearer {token}"})

    r2 = requests.get(f"{BASE_URL}/api/agent/v1/audit-log",
        headers={"Authorization": f"Bearer {token}"}, params={"limit": 50})
    assert r2.status_code == 200, f"审计日志请求失败: {r2.text}"
    logs = r2.json().get("data", {}).get("entries", [])
    assert len(logs) > 0, "审计日志不应为空"
    s = logs[0]
    for f in ["timestamp_ms", "agent_id", "route", "permission_class", "status_code", "latency_ms"]:
        assert f in s, f"缺失字段: {f}"
run_test("Audit Log Entries", test_audit_log_entries)

# ===== Summary =====
print(f"\n{'='*60}")
print(f"  RESULTS")
print(f"{'='*60}")
print(f"  Passed: {passed}")
print(f"  Failed: {failed}")
print(f"  Total:  {passed + failed}")

if errors:
    print(f"\n{'='*60}")
    print(f"  FAILURES")
    print(f"{'='*60}")
    for name, err in errors:
        print(f"  - {name}: {err}")

print(f"\n{'='*60}")
print(f"  {'ALL TESTS PASSED!' if failed == 0 else 'SOME TESTS FAILED!'}")
print(f"{'='*60}\n")

sys.exit(0 if failed == 0 else 1)
