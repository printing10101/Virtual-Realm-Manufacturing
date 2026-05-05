"""系统状态API集成测试。

测试健康检查、根路由等系统级接口的功能正确性和稳定性。
"""
import pytest


@pytest.mark.integration
class TestHealthEndpoint:
    """测试 /health 健康检查接口。"""

    async def test_health_returns_healthy_when_services_available(
        self, client, patch_external_services
    ):
        """当所有服务可用时，健康检查应返回healthy状态。"""
        response = await client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] in ["healthy", "degraded"]
        assert "version" in data
        assert "ai_status" in data
        assert "mode" in data["ai_status"]
        assert "available" in data["ai_status"]
        assert "model" in data["ai_status"]

    async def test_health_response_structure(self, client, patch_external_services):
        """健康检查响应应包含所有必需字段。"""
        response = await client.get("/health")
        data = response.json()

        required_fields = ["status", "version", "ai_status"]
        for field in required_fields:
            assert field in data, f"缺少必需字段: {field}"

        ai_status_fields = ["mode", "available", "model"]
        for field in ai_status_fields:
            assert field in data["ai_status"], f"AI状态缺少字段: {field}"

    async def test_health_version_matches_config(self, client, patch_external_services):
        """健康检查返回的版本应与配置文件一致。"""
        from app.config import config

        response = await client.get("/health")
        data = response.json()

        assert data["version"] == config.app_version

    async def test_health_ai_mode_valid_values(self, client, patch_external_services):
        """健康检查返回的AI模式应该是合法值。"""
        response = await client.get("/health")
        data = response.json()

        valid_modes = ["local", "cloud", "rule"]
        assert data["ai_status"]["mode"] in valid_modes

    async def test_health_is_get_only(self, client, patch_external_services):
        """健康检查接口应只支持GET方法。"""
        response = await client.post("/health")
        assert response.status_code in [405, 404]

    async def test_health_ai_status_available_is_boolean(self, client, patch_external_services):
        """健康检查返回的AI可用状态应该是布尔值。"""
        response = await client.get("/health")
        data = response.json()

        assert isinstance(data["ai_status"]["available"], bool)


@pytest.mark.integration
class TestRootEndpoint:
    """测试 / 根路由接口。"""

    async def test_root_returns_success_response(self, client, patch_external_services):
        """根路由应返回成功的响应格式。"""
        response = await client.get("/")

        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 0
        assert "data" in data
        assert "message" in data or data.get("message") is not None

    async def test_root_contains_app_info(self, client, patch_external_services):
        """根路由响应应包含应用基本信息。"""
        from app.config import config

        response = await client.get("/")
        data = response.json()

        assert data["data"]["app"] == config.app_name
        assert data["data"]["version"] == config.app_version
        assert data["data"]["docs"] == "/docs"

    async def test_root_get_only(self, client, patch_external_services):
        """根路由应只支持GET方法。"""
        response = await client.post("/")
        assert response.status_code in [405, 404]
