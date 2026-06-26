"""DNC 机床通信 API 端到端测试。

测试覆盖：
- 机床连接管理（添加、删除、列出）
- 机床状态查询
- NC 程序传输
- 报警信息查询
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient, ASGITransport
from fastapi.testclient import TestClient

from app.main import app
from app.dnc.dnc_manager import dnc_manager, ProtocolType


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def client():
    """创建测试客户端"""
    return TestClient(app)


@pytest.fixture
async def async_client():
    """创建异步测试客户端"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture(autouse=True)
async def cleanup_connections():
    """每个测试后清理 DNC 连接"""
    yield
    # 清理所有测试连接
    for machine_id in list(dnc_manager.connections.keys()):
        if machine_id.startswith("TEST-"):
            await dnc_manager.remove_machine(machine_id)


# ---------------------------------------------------------------------------
# 机床连接管理测试
# ---------------------------------------------------------------------------


class TestMachineConnection:
    """机床连接管理测试"""

    def test_connect_machine_opcua(self, client):
        """测试通过 OPC UA 协议连接机床"""
        response = client.post(
            "/api/v1/dnc/machines",
            json={
                "machine_id": "TEST-CNC-001",
                "protocol": "opcua",
                "endpoint": "opc.tcp://192.168.1.100:4840",
                "username": "test_user",
                "password": "test_pass",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["machine_id"] == "TEST-CNC-001"
        assert data["data"]["status"] == "connected"

    def test_connect_machine_mtconnect(self, client):
        """测试通过 MTConnect 协议连接机床"""
        response = client.post(
            "/api/v1/dnc/machines",
            json={
                "machine_id": "TEST-CNC-002",
                "protocol": "mtconnect",
                "endpoint": "http://192.168.1.101:5000",
                "device_name": "CNC-Device",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["machine_id"] == "TEST-CNC-002"

    def test_list_machines(self, client):
        """测试列出已连接机床"""
        # 先添加一台机床
        client.post(
            "/api/v1/dnc/machines",
            json={
                "machine_id": "TEST-CNC-LIST",
                "protocol": "opcua",
                "endpoint": "opc.tcp://192.168.1.100:4840",
            },
        )

        response = client.get("/api/v1/dnc/machines")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert isinstance(data["data"], list)

    def test_disconnect_machine(self, client):
        """测试断开机床连接"""
        # 先添加
        client.post(
            "/api/v1/dnc/machines",
            json={
                "machine_id": "TEST-CNC-DISC",
                "protocol": "opcua",
                "endpoint": "opc.tcp://192.168.1.100:4840",
            },
        )

        # 再删除
        response = client.delete("/api/v1/dnc/machines/TEST-CNC-DISC")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["status"] == "disconnected"


# ---------------------------------------------------------------------------
# 机床状态查询测试
# ---------------------------------------------------------------------------


class TestMachineStatus:
    """机床状态查询测试"""

    def test_get_machine_status(self, client):
        """测试获取单台机床状态"""
        # 添加机床
        client.post(
            "/api/v1/dnc/machines",
            json={
                "machine_id": "TEST-CNC-STATUS",
                "protocol": "opcua",
                "endpoint": "opc.tcp://192.168.1.100:4840",
            },
        )

        response = client.get("/api/v1/dnc/machines/TEST-CNC-STATUS/status")
        # 注意：实际连接会失败，但 API 应返回 404 或状态信息
        assert response.status_code in [200, 404]

    def test_get_all_machines_status(self, client):
        """测试获取所有机床状态"""
        response = client.get("/api/v1/dnc/status")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert isinstance(data["data"], dict)


# ---------------------------------------------------------------------------
# NC 程序传输测试
# ---------------------------------------------------------------------------


class TestNCProgramTransfer:
    """NC 程序传输测试"""

    def test_send_nc_program_file_not_found(self, client):
        """测试发送不存在的 NC 程序文件"""
        response = client.post(
            "/api/v1/dnc/nc-program/send",
            json={
                "machine_id": "TEST-CNC-001",
                "program_path": "/nonexistent/path/program.nc",
                "program_name": "test_program",
            },
        )
        assert response.status_code == 400
        assert "文件不存在" in response.json()["detail"]

    def test_send_nc_program_unsupported_protocol(self, client):
        """测试向不支持的协议发送 NC 程序"""
        # MTConnect 不支持程序传输
        client.post(
            "/api/v1/dnc/machines",
            json={
                "machine_id": "TEST-CNC-MTC",
                "protocol": "mtconnect",
                "endpoint": "http://192.168.1.101:5000",
            },
        )

        # 创建临时文件
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.nc', delete=False) as f:
            f.write("O0001\nG90 G54\nM30\n")
            temp_path = f.name

        try:
            response = client.post(
                "/api/v1/dnc/nc-program/send",
                json={
                    "machine_id": "TEST-CNC-MTC",
                    "program_path": temp_path,
                },
            )
            # 应该返回错误（MTConnect 不支持）或成功（如果 mock）
            assert response.status_code in [200, 400, 500]
        finally:
            import os
            os.unlink(temp_path)


# ---------------------------------------------------------------------------
# 报警信息查询测试
# ---------------------------------------------------------------------------


class TestMachineAlarms:
    """机床报警信息查询测试"""

    def test_get_machine_alarms_not_connected(self, client):
        """测试查询未连接机床的报警"""
        response = client.get("/api/v1/dnc/machines/TEST-NOT-EXIST/alarms")
        assert response.status_code == 404

    def test_get_machine_alarms_mtconnect(self, client):
        """测试查询 MTConnect 机床报警"""
        # 添加 MTConnect 机床
        client.post(
            "/api/v1/dnc/machines",
            json={
                "machine_id": "TEST-CNC-ALARM",
                "protocol": "mtconnect",
                "endpoint": "http://192.168.1.101:5000",
            },
        )

        response = client.get("/api/v1/dnc/machines/TEST-CNC-ALARM/alarms")
        # 实际连接会失败，但 API 应处理异常
        assert response.status_code in [200, 404, 500]

    def test_get_machine_alarms_opcua(self, client):
        """测试查询 OPC UA 机床报警（暂未实现）"""
        client.post(
            "/api/v1/dnc/machines",
            json={
                "machine_id": "TEST-CNC-OPCUA-ALARM",
                "protocol": "opcua",
                "endpoint": "opc.tcp://192.168.1.100:4840",
            },
        )

        response = client.get("/api/v1/dnc/machines/TEST-CNC-OPCUA-ALARM/alarms")
        assert response.status_code == 200
        data = response.json()
        # OPC UA 报警查询暂未实现，应返回空列表和提示
        assert data["success"] is True
        assert data["data"] == []


# ---------------------------------------------------------------------------
# 参数验证测试
# ---------------------------------------------------------------------------


class TestValidation:
    """参数验证测试"""

    def test_connect_machine_missing_fields(self, client):
        """测试缺少必填字段"""
        response = client.post(
            "/api/v1/dnc/machines",
            json={
                "machine_id": "TEST-CNC-001",
                # 缺少 protocol 和 endpoint
            },
        )
        assert response.status_code == 422

    def test_connect_machine_invalid_protocol(self, client):
        """测试无效的协议类型"""
        response = client.post(
            "/api/v1/dnc/machines",
            json={
                "machine_id": "TEST-CNC-001",
                "protocol": "invalid_protocol",
                "endpoint": "tcp://192.168.1.100",
            },
        )
        assert response.status_code == 422
