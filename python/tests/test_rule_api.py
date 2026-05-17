"""
工艺规则 API 测试

测试所有 RESTful 端点的正确性
"""

import pytest
from fastapi.testclient import TestClient
from fastapi import FastAPI
import tempfile
import os
from pathlib import Path
import sys
import json

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database.rule_db import RuleDatabase, ProcessRule, RuleCondition, RuleResult, RuleGroup, _global_db
import app.rules.api as rules_api
import app.database.rule_db as rule_db_module


@pytest.fixture(autouse=True)
def setup_temp_db():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    temp_db = RuleDatabase(path)
    original_global = rule_db_module._global_db
    rule_db_module._global_db = temp_db
    yield temp_db
    rule_db_module._global_db = original_global
    temp_db.close()
    if os.path.exists(path):
        os.unlink(path)


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(rules_api.router)
    return TestClient(app)


@pytest.fixture
def sample_rule_data():
    return {
        "name": "45钢粗铣切深限制",
        "description": "45钢粗铣加工时切深不超过2mm",
        "conditions": [
            {"parameter": "材料", "operator": "=", "value": "45钢"},
            {"parameter": "工序", "operator": "=", "value": "粗铣"},
        ],
        "logic_operator": "AND",
        "result": {"parameter": "切深", "operator": "<=", "value": "2", "unit": "mm"},
        "status": "active",
        "priority": 10,
    }


@pytest.fixture
def sample_group_data():
    return {
        "name": "铣削规则",
        "description": "铣削加工相关规则",
    }


class TestRuleCrudApi:
    def test_create_rule(self, client, sample_rule_data):
        response = client.post("/api/rules/create", json=sample_rule_data)
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 0
        assert data["data"]["name"] == "45钢粗铣切深限制"
        assert data["data"]["id"] is not None

    def test_create_rule_validation_error(self, client):
        response = client.post("/api/rules/create", json={
            "name": "test",
            "conditions": [],
            "result": {"parameter": "", "operator": "=", "value": ""},
        })
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 1002

    def test_create_rule_invalid_operator(self, client):
        response = client.post("/api/rules/create", json={
            "name": "test",
            "conditions": [{"parameter": "材料", "operator": "~~", "value": "45钢"}],
            "result": {"parameter": "切深", "operator": "<=", "value": "2"},
        })
        data = response.json()
        assert data["code"] == 1002

    def test_list_rules(self, client, sample_rule_data):
        client.post("/api/rules/create", json=sample_rule_data)
        response = client.get("/api/rules/list")
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 0
        assert data["data"]["total"] == 1
        assert len(data["data"]["rules"]) == 1

    def test_get_rule_detail(self, client, sample_rule_data):
        create_resp = client.post("/api/rules/create", json=sample_rule_data)
        rule_id = create_resp.json()["data"]["id"]

        response = client.get(f"/api/rules/detail/{rule_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["data"]["name"] == "45钢粗铣切深限制"

    def test_get_rule_not_found(self, client):
        response = client.get("/api/rules/detail/99999")
        data = response.json()
        assert data["code"] == 1001

    def test_update_rule(self, client, sample_rule_data):
        create_resp = client.post("/api/rules/create", json=sample_rule_data)
        rule_id = create_resp.json()["data"]["id"]

        response = client.put(f"/api/rules/update/{rule_id}", json={
            "name": "更新名称",
            "priority": 20,
        })
        assert response.status_code == 200
        data = response.json()
        assert data["data"]["name"] == "更新名称"
        assert data["data"]["priority"] == 20

    def test_delete_rule(self, client, sample_rule_data):
        create_resp = client.post("/api/rules/create", json=sample_rule_data)
        rule_id = create_resp.json()["data"]["id"]

        response = client.delete(f"/api/rules/delete/{rule_id}")
        assert response.status_code == 200

        response = client.get(f"/api/rules/detail/{rule_id}")
        assert response.json()["code"] == 1001

    def test_filter_rules_by_status(self, client):
        for i in range(5):
            client.post("/api/rules/create", json={
                "name": f"规则{i}",
                "conditions": [{"parameter": "材料", "operator": "=", "value": "45钢"}],
                "result": {"parameter": "切深", "operator": "<=", "value": "2"},
                "status": "active" if i < 3 else "draft",
            })

        response = client.get("/api/rules/list?status=active")
        assert response.json()["data"]["total"] == 3

        response = client.get("/api/rules/list?status=draft")
        assert response.json()["data"]["total"] == 2

    def test_search_rules_by_keyword(self, client):
        client.post("/api/rules/create", json={
            "name": "45钢规则",
            "description": "这是45钢的加工规则",
            "conditions": [{"parameter": "材料", "operator": "=", "value": "45钢"}],
            "result": {"parameter": "切深", "operator": "<=", "value": "2"},
        })
        client.post("/api/rules/create", json={
            "name": "铝合金规则",
            "conditions": [{"parameter": "材料", "operator": "=", "value": "6061"}],
            "result": {"parameter": "切深", "operator": "<=", "value": "3"},
        })

        response = client.get("/api/rules/list?keyword=45钢")
        assert response.json()["data"]["total"] == 1


class TestGroupApi:
    def test_create_group(self, client, sample_group_data):
        response = client.post("/api/rules/groups/create", json=sample_group_data)
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 0
        assert data["data"]["name"] == "铣削规则"

    def test_create_duplicate_group(self, client, sample_group_data):
        client.post("/api/rules/groups/create", json=sample_group_data)
        response = client.post("/api/rules/groups/create", json=sample_group_data)
        data = response.json()
        assert data["code"] == 1002

    def test_list_groups(self, client, sample_group_data):
        client.post("/api/rules/groups/create", json=sample_group_data)
        response = client.get("/api/rules/groups/list")
        assert response.status_code == 200
        data = response.json()
        assert data["data"]["total"] == 1

    def test_update_group(self, client, sample_group_data):
        create_resp = client.post("/api/rules/groups/create", json=sample_group_data)
        group_id = create_resp.json()["data"]["id"]

        response = client.put(f"/api/rules/groups/update/{group_id}", json={
            "name": "更新分组",
        })
        assert response.status_code == 200
        assert response.json()["data"]["name"] == "更新分组"

    def test_delete_group_with_rules(self, client, sample_group_data, sample_rule_data):
        create_resp = client.post("/api/rules/groups/create", json=sample_group_data)
        group_id = create_resp.json()["data"]["id"]

        sample_rule_data["group_id"] = group_id
        client.post("/api/rules/create", json=sample_rule_data)

        response = client.delete(f"/api/rules/groups/delete/{group_id}")
        data = response.json()
        assert data["code"] == 1002

    def test_delete_empty_group(self, client, sample_group_data):
        create_resp = client.post("/api/rules/groups/create", json=sample_group_data)
        group_id = create_resp.json()["data"]["id"]

        response = client.delete(f"/api/rules/groups/delete/{group_id}")
        assert response.status_code == 200


class TestImportExportApi:
    def test_export_rules(self, client, sample_rule_data):
        client.post("/api/rules/create", json=sample_rule_data)
        response = client.get("/api/rules/export")
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/json"
        data = json.loads(response.content)
        assert data["total_rules"] == 1

    def test_import_rules(self, client):
        export_data = {
            "version": "1.0",
            "groups": [{"name": "导入分组", "description": ""}],
            "rules": [{
                "name": "导入规则",
                "description": "",
                "conditions": [{"parameter": "材料", "operator": "=", "value": "45钢"}],
                "logic_operator": "AND",
                "result": {"parameter": "切深", "operator": "<=", "value": "2"},
                "status": "active",
                "priority": 0,
            }],
        }

        response = client.post(
            "/api/rules/import",
            files={"file": ("rules.json", json.dumps(export_data), "application/json")},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["data"]["imported_rules"] == 1

    def test_import_invalid_json(self, client):
        response = client.post(
            "/api/rules/import",
            files={"file": ("test.txt", "not json", "text/plain")},
        )
        data = response.json()
        assert data["code"] == 1002


class TestBackupApi:
    def test_backup_database(self, client):
        response = client.post("/api/rules/backup")
        assert response.status_code == 200
        data = response.json()
        assert "backup_path" in data["data"]


class TestStatsApi:
    def test_get_stats(self, client, sample_rule_data):
        for i in range(5):
            sample_rule_data["name"] = f"规则{i}"
            sample_rule_data["status"] = "active" if i < 3 else "draft"
            client.post("/api/rules/create", json=sample_rule_data)

        response = client.get("/api/rules/stats")
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["total_rules"] == 5
        assert data["active_rules"] == 3
        assert data["draft_rules"] == 2


class TestPreviewApi:
    def test_preview_rule_text(self, client):
        conditions = json.dumps([
            {"parameter": "材料", "operator": "=", "value": "45钢"},
            {"parameter": "工序", "operator": "=", "value": "粗铣"},
        ])
        result = json.dumps({"parameter": "切深", "operator": "<=", "value": "2"})

        response = client.get(
            "/api/rules/preview",
            params={"conditions": conditions, "result": result},
        )
        assert response.status_code == 200
        data = response.json()["data"]
        assert "IF" in data["preview_text"]
        assert "材料 = 45钢" in data["preview_text"]
        assert "THEN" in data["preview_text"]
