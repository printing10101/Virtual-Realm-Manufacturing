"""AI对话相关API集成测试。

测试AI Agents接口的功能正确性、异常处理和边界条件。
"""
import pytest


@pytest.mark.integration
class TestAgentsInfo:
    """测试 /api/agents/info 接口。"""

    async def test_agents_info_returns_success(self, client, patch_external_services):
        """Agents信息接口应返回成功响应。"""
        response = await client.get("/api/agents/info")

        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 200
        assert "data" in data
        assert "message" in data

    async def test_agents_info_contains_all_agents(self, client, patch_external_services, sample_ai_data):
        """Agents信息应包含所有预期的Agent。"""
        response = await client.get("/api/agents/info")
        data = response.json()

        agents = data["data"]["agents"]
        assert len(agents) == sample_ai_data["expected_agents_count"]

        agent_names = [agent["name"] for agent in agents]
        for expected_name in sample_ai_data["agent_names"]:
            assert expected_name in agent_names

    async def test_agents_info_structure_valid(self, client, patch_external_services, sample_ai_data):
        """Agents信息响应结构应正确。"""
        response = await client.get("/api/agents/info")
        data = response.json()

        for key in sample_ai_data["agents_info_keys"]:
            assert key in data

        agents = data["data"]["agents"]
        assert isinstance(agents, list)
        assert len(agents) > 0

        first_agent = agents[0]
        assert "name" in first_agent
        assert "description" in first_agent

    async def test_agents_info_agent_has_description(self, client, patch_external_services):
        """每个Agent都应该有描述信息。"""
        response = await client.get("/api/agents/info")
        data = response.json()

        agents = data["data"]["agents"]
        for agent in agents:
            assert "description" in agent
            assert len(agent["description"]) > 0
            assert isinstance(agent["description"], str)

    async def test_agents_info_get_only(self, client, patch_external_services):
        """Agents信息接口应只支持GET方法。"""
        response = await client.post("/api/agents/info")
        assert response.status_code in [405, 404]

    async def test_agents_info_no_auth_required(self, client, patch_external_services):
        """Agents信息接口不需要认证头信息。"""
        response = await client.get("/api/agents/info", headers={})
        assert response.status_code == 200
