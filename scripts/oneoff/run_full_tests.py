"""Self-contained integration test - runs via API directly."""
import json
import os
import sys
import time
import requests
from pathlib import Path

# 动态获取项目根目录
PROJECT_ROOT = Path(__file__).parent
os.chdir(PROJECT_ROOT)

BASE_URL = "http://localhost:8765"
results = []
passed = 0
failed = 0

def test(name, func):
    global passed, failed
    try:
        func()
        results.append((name, "PASS"))
        passed += 1
        print(f"[PASS] {name}")
    except Exception as e:
        results.append((name, f"FAIL: {e}"))
        failed += 1
        print(f"[FAIL] {name}: {e}")

def step1_token_creation():
    r = requests.post(f"{BASE_URL}/api/agent/v1/tokens", json={
        "scopes": ["R", "B"], "expires_in": 3600, "paper_only": True
    })
    assert r.status_code == 200, f"创建失败: {r.text}"
    td = r.json()["data"]
    assert td["token"].startswith("lj_agent_"), "格式错误"
    assert len(td["token"]) == len("lj_agent_") + 32, "长度错误"
    global RB_TOKEN, AGENT_ID
    RB_TOKEN = td["token"]
    AGENT_ID = td["agent_id"]

def step2_model_access():
    r = requests.get(f"{BASE_URL}/api/agent/v1/models",
                     headers={"Authorization": f"Bearer {RB_TOKEN}"})
    assert r.status_code == 200, f"模型列表失败: {r.text}"
    data = r.json()
    assert "data" in data, "响应结构错误"

def step3_permission_control():
    r = requests.post(f"{BASE_URL}/api/agent/v1/execute",
                      headers={"Authorization": f"Bearer {RB_TOKEN}"},
                      json={"model_name": "test", "parameters": {"p1": 1.0}, "paper_only": True})
    assert r.status_code == 403, f"应返回403, 实际: {r.status_code}, {r.text}"

def step4_paper_only():
    r = requests.post(f"{BASE_URL}/api/agent/v1/tokens", json={
        "scopes": ["R", "B", "T"], "expires_in": 3600, "paper_only": True
    })
    t_token = r.json()["data"]["token"]
    r = requests.post(f"{BASE_URL}/api/agent/v1/execute",
                      headers={
                          "Authorization": f"Bearer {t_token}",
                          "Idempotency-Key": f"po_{int(time.time())}"
                      },
                      json={"model_name": "test", "parameters": {"p1": 1.0}})
    assert r.status_code == 200, f"Paper-only失败: {r.text}"
    d = r.json().get("data", {})
    assert d.get("paper_only") is True or d.get("mode") == "simulation" or d.get("simulated") is True

def step5_mcp_structure():
    mcp = Path(__file__).parent / "mcp_server"
    pt = mcp / "pyproject.toml"
    assert pt.exists(), "MCP包不存在"
    tools = mcp / "tools.py"
    assert tools.exists(), "MCP tools不存在"
    server = mcp / "server.py"
    assert server.exists(), "MCP server不存在"

def step6_audit_log():
    time.sleep(0.5)
    r = requests.get(f"{BASE_URL}/api/agent/v1/audit-log",
                     headers={"Authorization": f"Bearer {RB_TOKEN}"}, params={"limit": 50})
    assert r.status_code == 200, f"审计日志失败: {r.text}"
    logs = r.json().get("data", {}).get("entries", [])
    assert len(logs) > 0, "日志为空"
    s = logs[0]
    for f in ["timestamp_ms", "agent_id", "route", "permission_class", "status_code", "latency_ms"]:
        assert f in s, f"缺失字段: {f}"

def step7_idempotency():
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
    assert r1.status_code == 200, f"第一次训练失败: {r1.text}"
    t2 = time.time()
    r2 = requests.post(f"{BASE_URL}/api/agent/v1/train",
                       headers={"Authorization": f"Bearer {token}", "Idempotency-Key": key}, json=payload)
    e2 = time.time() - t2
    assert r2.status_code == 200, f"第二次训练失败: {r2.text}"
    j1 = r1.json().get("data", {}).get("job_id")
    j2 = r2.json().get("data", {}).get("job_id")
    assert j1 == j2, f"job_id不同: {j1} vs {j2}"
    assert e2 < e1 * 0.5, f"第二次耗时未缩短: {e2:.3f}s vs {e1:.3f}s"

def step8_batch_revoke():
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
    assert r.status_code == 200, f"撤销失败: {r.text}"
    rc = r.json().get("data", {}).get("revoked_count", 0)
    assert rc >= 3, f"应撤销至少3个, 实际: {rc}"
    for tok in t_tokens:
        r = requests.get(f"{BASE_URL}/api/agent/v1/models", headers={"Authorization": f"Bearer {tok}"})
        assert r.status_code in [401, 403], f"已撤销T Token仍可访问: {r.status_code}"
    r = requests.get(f"{BASE_URL}/api/agent/v1/models", headers={"Authorization": f"Bearer {non_t_token}"})
    assert r.status_code == 200, "非T Token应不受影响"

if __name__ == "__main__":
    print("Agent功能完整性集成测试")
    print(f"目标服务器: {BASE_URL}\n")

    test("1. Token创建与验证", step1_token_creation)
    test("2. 模型列表API访问", step2_model_access)
    test("3. 权限控制(T类403)", step3_permission_control)
    test("4. Paper-only模式", step4_paper_only)
    test("5. MCP服务器结构", step5_mcp_structure)
    test("6. 审计日志完整性", step6_audit_log)
    test("7. 幂等性机制", step7_idempotency)
    test("8. 批量Token撤销", step8_batch_revoke)

    print(f"\n{'='*60}")
    print(f"测试总结: 通过 {passed}/{passed+failed}")
    for name, status in results:
        print(f"  {'[PASS]' if status == 'PASS' else '[FAIL]'} {name}: {status}")
    print(f"{'='*60}")
    sys.exit(0 if failed == 0 else 1)
