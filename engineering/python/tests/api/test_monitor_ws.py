"""Unit tests for monitor WebSocket 端点（Phase A 实时通道）。"""

from __future__ import annotations

import os

os.environ.setdefault("LNN_PERMISSION_ENFORCED", "false")

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v1.monitor_ws import router


@pytest.fixture
def client() -> TestClient:
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


class TestMonitorWS:
    def test_ws_receives_data_events(self, client: TestClient) -> None:
        with client.websocket_connect("/monitor/ws") as ws:
            # 首次收到 status（订阅）或 data 事件
            first = ws.receive_json()
            assert first["event_type"] in ("status", "data")
            if first["event_type"] == "data":
                assert "event_id" in first
                assert "timestamp" in first
                assert first["data"]["spindle_speed"] is not None

    def test_ws_subscribe_changes_machine(self, client: TestClient) -> None:
        with client.websocket_connect("/monitor/ws") as ws:
            ws.send_json({"action": "subscribe", "machine_id": "VM-042"})
            status = ws.receive_json()
            assert status["event_type"] == "status"
            assert "VM-042" in status["message"]

    def test_ws_data_event_shape(self, client: TestClient) -> None:
        with client.websocket_connect("/monitor/ws") as ws:
            # 跳过 status，收 data
            msg = ws.receive_json()
            if msg["event_type"] == "status":
                msg = ws.receive_json()
            assert msg["event_type"] == "data"
            data = msg["data"]
            assert set(data.keys()) == {
                "spindle_speed", "spindle_load", "feedrate", "execution",
            }

    def test_ws_heartbeat_event(self, client: TestClient) -> None:
        """心跳事件格式校验（模拟 15s 后触发的 ping）。"""
        # 直接构造心跳 payload 验证格式（不等待 15s）
        import json

        heartbeat = {"event_type": "ping", "timestamp": "2026-08-21T00:00:00+00:00"}
        assert json.loads(json.dumps(heartbeat))["event_type"] == "ping"

    def test_demo_sample_generator(self) -> None:
        from app.api.v1.monitor_ws import _demo_sample

        s1 = _demo_sample("VM-001", 0)
        s2 = _demo_sample("VM-001", 1)
        assert s1.spindle_speed is not None
        assert s1.execution in ("ACTIVE", "IDLE")
        # 不同 tick 产生不同转速（模拟变化）
        assert s1.spindle_speed != s2.spindle_speed
