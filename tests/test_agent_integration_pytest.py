"""Integration test runner - runs as a pytest test to avoid terminal issues."""
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "python"))

import pytest
import requests

BASE_URL = "http://localhost:8765"

class TestAgentTokenCreation:
    def test_create_rb_token(self):
        r = requests.post(f"{BASE_URL}/api/agent/v1/tokens", json={
            "scopes": ["R", "B"], "expires_in": 3600, "paper_only": True
        })
        assert r.status_code == 200, f"创建Token失败: {r.text}"
        td = r.json()
        assert td["data"]["token"].startswith("lj_agent_")
        assert len(td["data"]["token"]) == len("lj_agent_") + 32

class TestAgentModelAccess:
    def test_models_list(self):
        r = requests.post(f"{BASE_URL}/api/agent/v1/tokens", json={
            "scopes": ["R", "B"], "expires_in": 3600, "paper_only": True
        })
        token = r.json()["data"]["token"]
        r2 = requests.get(f"{BASE_URL}/api/agent/v1/models", headers={"Authorization": f"Bearer {token}"})
        assert r2.status_code == 200, f"模型列表失败: {r2.text}"

class TestAgentPermissionControl:
    def test_t_operation_forbidden(self):
        r = requests.post(f"{BASE_URL}/api/agent/v1/tokens", json={
            "scopes": ["R", "B"], "expires_in": 3600, "paper_only": True
        })
        token = r.json()["data"]["token"]
        r2 = requests.post(f"{BASE_URL}/api/agent/v1/execute",
            headers={"Authorization": f"Bearer {token}"},
            json={"model_name": "test", "parameters": {"p1": 1.0}, "paper_only": True}
        )
        assert r2.status_code == 403, f"预期403, 实际: {r2.status_code}, {r2.text}"

class TestPaperOnlyMode:
    def test_paper_only_simulation(self):
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
        assert d.get("paper_only") is True or d.get("mode") == "simulation" or d.get("simulated") is True

class TestIdempotency:
    def test_same_idempotency_key(self):
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
        assert r1.status_code == 200
        t2 = time.time()
        r2 = requests.post(f"{BASE_URL}/api/agent/v1/train",
            headers={"Authorization": f"Bearer {token}", "Idempotency-Key": key}, json=payload)
        e2 = time.time() - t2
        assert r2.status_code == 200
        j1 = r1.json().get("data", {}).get("job_id")
        j2 = r2.json().get("data", {}).get("job_id")
        assert j1 == j2, f"job_id不同: {j1} vs {j2}"
        assert e2 < e1 * 0.5, f"第二次耗时未缩短: {e2:.3f}s vs {e1:.3f}s"

class TestBatchTokenRevocation:
    def test_revoke_all_t_tokens(self):
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
        assert r.status_code == 200
        rc = r.json().get("data", {}).get("revoked_count", 0)
        assert rc >= 3, f"应撤销至少3个T Token, 实际: {rc}"

        for tok in t_tokens:
            r = requests.get(f"{BASE_URL}/api/agent/v1/models", headers={"Authorization": f"Bearer {tok}"})
            assert r.status_code in [401, 403], f"已撤销T Token仍可访问: {r.status_code}"

        r = requests.get(f"{BASE_URL}/api/agent/v1/models", headers={"Authorization": f"Bearer {non_t_token}"})
        assert r.status_code == 200, "非T Token应不受影响"

class TestAuditLog:
    def test_audit_log_entries(self):
        r = requests.post(f"{BASE_URL}/api/agent/v1/tokens", json={
            "scopes": ["R", "B"], "expires_in": 3600, "paper_only": True
        })
        token = r.json()["data"]["token"]

        requests.get(f"{BASE_URL}/api/agent/v1/models", headers={"Authorization": f"Bearer {token}"})

        r2 = requests.get(f"{BASE_URL}/api/agent/v1/audit-log",
            headers={"Authorization": f"Bearer {token}"}, params={"limit": 50})
        assert r2.status_code == 200
        logs = r2.json().get("data", {}).get("entries", [])
        assert len(logs) > 0, "审计日志不应为空"
        s = logs[0]
        for f in ["timestamp_ms", "agent_id", "route", "permission_class", "status_code", "latency_ms"]:
            assert f in s, f"缺失字段: {f}"
