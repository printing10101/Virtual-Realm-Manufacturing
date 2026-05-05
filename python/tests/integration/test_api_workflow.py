"""工作流管理API集成测试。

测试工作流执行、异步任务等接口的功能正确性、异常处理和边界条件。
"""
import pytest


@pytest.mark.integration
class TestProcessPlan:
    """测试 /api/workflow/process-plan 同步工作流接口。"""

    async def test_process_plan_with_valid_input(self, client, patch_external_services, sample_workflow_data):
        """有效输入应成功执行工作流。"""
        response = await client.post(
            "/api/workflow/process-plan",
            json=sample_workflow_data["valid_request"]
        )

        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 0
        assert "data" in data
        assert "message" in data

    async def test_process_plan_response_structure(self, client, patch_external_services, sample_workflow_data):
        """工作流响应应包含完整的结构。"""
        response = await client.post(
            "/api/workflow/process-plan",
            json=sample_workflow_data["valid_request"]
        )
        data = response.json()["data"]

        required_keys = [
            "user_input",
            "extracted_params",
            "process_route",
            "cutting_parameters",
            "nc_code",
            "verification_result",
            "repair_suggestions",
            "stage_results"
        ]

        for key in required_keys:
            assert key in data, f"缺少必需字段: {key}"

    async def test_process_plan_with_short_input(self, client, patch_external_services, sample_workflow_data):
        """过短输入应返回错误或处理失败。"""
        response = await client.post(
            "/api/workflow/process-plan",
            json={"user_input": sample_workflow_data["short_input"]}
        )

        data = response.json()
        assert response.status_code == 200
        assert data["code"] != 0 or "error" in data.get("message", "").lower()

    async def test_process_plan_with_empty_input(self, client, patch_external_services, sample_workflow_data):
        """空输入应返回验证错误。"""
        response = await client.post(
            "/api/workflow/process-plan",
            json={"user_input": sample_workflow_data["empty_input"]}
        )

        data = response.json()
        assert response.status_code == 200
        assert data["code"] != 0

    async def test_process_plan_with_max_length_input(self, client, patch_external_services, sample_workflow_data):
        """超长输入应返回验证错误。"""
        response = await client.post(
            "/api/workflow/process-plan",
            json={"user_input": sample_workflow_data["max_length_input"]}
        )

        data = response.json()
        assert response.status_code == 200
        assert data["code"] != 0

    async def test_process_plan_with_special_chars(self, client, patch_external_services, sample_workflow_data):
        """特殊字符输入应被正确处理。"""
        response = await client.post(
            "/api/workflow/process-plan",
            json={"user_input": sample_workflow_data["special_chars_input"]}
        )

        assert response.status_code == 200

    async def test_process_plan_missing_user_input(self, client, patch_external_services):
        """缺少user_input字段应返回验证错误。"""
        response = await client.post("/api/workflow/process-plan", json={})

        data = response.json()
        assert response.status_code == 200
        assert data["code"] != 0

    async def test_process_plan_invalid_json(self, client, patch_external_services):
        """无效JSON应返回验证错误。"""
        response = await client.post(
            "/api/workflow/process-plan",
            content="not valid json",
            headers={"Content-Type": "application/json"}
        )

        assert response.status_code in [422, 400]

    async def test_process_plan_post_only(self, client, patch_external_services, sample_workflow_data):
        """工作流接口应只支持POST方法。"""
        response = await client.get("/api/workflow/process-plan")
        assert response.status_code in [405, 404]


@pytest.mark.integration
class TestProcessPlanAsync:
    """测试 /api/workflow/process-plan-async 异步工作流接口。"""

    async def test_process_plan_async_with_valid_input(self, client, patch_external_services, sample_workflow_data):
        """有效输入应成功创建异步任务。"""
        response = await client.post(
            "/api/workflow/process-plan-async",
            json=sample_workflow_data["valid_request"]
        )

        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 0
        assert "data" in data
        assert "task_id" in data["data"]

    async def test_process_plan_async_returns_task_id(self, client, patch_external_services, sample_workflow_data):
        """异步任务创建应返回任务ID。"""
        response = await client.post(
            "/api/workflow/process-plan-async",
            json=sample_workflow_data["valid_request"]
        )
        data = response.json()["data"]

        assert "task_id" in data
        assert isinstance(data["task_id"], str)
        assert len(data["task_id"]) > 0

    async def test_process_plan_async_with_empty_input(self, client, patch_external_services, sample_workflow_data):
        """空输入应返回验证错误。"""
        response = await client.post(
            "/api/workflow/process-plan-async",
            json={"user_input": sample_workflow_data["empty_input"]}
        )

        data = response.json()
        assert response.status_code == 200
        assert data["code"] != 0

    async def test_process_plan_async_with_short_input(self, client, patch_external_services, sample_workflow_data):
        """过短输入应返回验证错误。"""
        response = await client.post(
            "/api/workflow/process-plan-async",
            json={"user_input": sample_workflow_data["short_input"]}
        )

        data = response.json()
        assert response.status_code == 200
        assert data["code"] != 0

    async def test_process_plan_async_post_only(self, client, patch_external_services, sample_workflow_data):
        """异步工作流接口应只支持POST方法。"""
        response = await client.get("/api/workflow/process-plan-async")
        assert response.status_code in [405, 404]
