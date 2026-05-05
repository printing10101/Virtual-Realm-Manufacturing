"""Ollama模型管理API集成测试。

测试Ollama模型状态、模型列表、模型管理等接口的功能正确性和稳定性。
"""
import pytest


@pytest.mark.integration
class TestOllamaStatus:
    """测试 /api/ollama/status 接口。"""

    async def test_status_returns_success(self, client, patch_external_services):
        """Ollama状态接口应返回成功响应。"""
        response = await client.get("/api/ollama/status")

        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 0
        assert "data" in data

    async def test_status_contains_required_fields(
        self, client, patch_external_services, sample_ollama_data
    ):
        """状态响应应包含所有必需字段。"""
        response = await client.get("/api/ollama/status")
        data = response.json()["data"]

        for field in sample_ollama_data["expected_status_keys"]:
            assert field in data, f"缺少必需字段: {field}"

    async def test_status_available_is_boolean(self, client, patch_external_services):
        """可用状态应该是布尔值。"""
        response = await client.get("/api/ollama/status")
        data = response.json()["data"]

        assert isinstance(data["available"], bool)

    async def test_status_version_is_string(self, client, patch_external_services):
        """版本号应该是字符串。"""
        response = await client.get("/api/ollama/status")
        data = response.json()["data"]

        assert isinstance(data["version"], str)

    async def test_status_base_url_is_string(self, client, patch_external_services):
        """基础URL应该是字符串。"""
        response = await client.get("/api/ollama/status")
        data = response.json()["data"]

        assert isinstance(data["base_url"], str)

    async def test_status_get_only(self, client, patch_external_services):
        """状态接口应只支持GET方法。"""
        response = await client.post("/api/ollama/status")
        assert response.status_code in [405, 404]


@pytest.mark.integration
class TestOllamaModels:
    """测试 /api/ollama/models 接口。"""

    async def test_list_models_returns_success(self, client, patch_external_services):
        """模型列表接口应返回成功响应。"""
        response = await client.get("/api/ollama/models")

        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 0

    async def test_list_models_returns_models_list(self, client, patch_external_services):
        """模型列表应返回数组。"""
        response = await client.get("/api/ollama/models")
        data = response.json()["data"]

        assert "models" in data
        assert isinstance(data["models"], list)

    async def test_list_models_returns_total(self, client, patch_external_services):
        """模型列表应返回总数。"""
        response = await client.get("/api/ollama/models")
        data = response.json()["data"]

        assert "total" in data
        assert isinstance(data["total"], int)
        assert data["total"] == len(data["models"])

    async def test_list_models_get_only(self, client, patch_external_services):
        """模型列表接口应只支持GET方法。"""
        response = await client.post("/api/ollama/models")
        assert response.status_code in [405, 404]


@pytest.mark.integration
class TestOllamaRecommendedModels:
    """测试 /api/ollama/models/recommended 接口。"""

    async def test_recommended_models_returns_success(self, client, patch_external_services):
        """推荐模型接口应返回成功响应。"""
        response = await client.get("/api/ollama/models/recommended")

        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 0

    async def test_recommended_models_contains_models_key(self, client, patch_external_services):
        """推荐模型响应应包含models键。"""
        response = await client.get("/api/ollama/models/recommended")
        data = response.json()["data"]

        assert "models" in data
        assert isinstance(data["models"], list)

    async def test_recommended_models_has_total(self, client, patch_external_services):
        """推荐模型响应应包含总数。"""
        response = await client.get("/api/ollama/models/recommended")
        data = response.json()["data"]

        assert "total" in data
        assert isinstance(data["total"], int)

    async def test_recommended_models_get_only(self, client, patch_external_services):
        """推荐模型接口应只支持GET方法。"""
        response = await client.post("/api/ollama/models/recommended")
        assert response.status_code in [405, 404]


@pytest.mark.integration
class TestOllamaModelInfo:
    """测试 /api/ollama/models/{model_name}/info 接口。"""

    async def test_model_info_returns_success(self, client, patch_external_services, sample_ollama_data):
        """模型信息接口应返回成功响应。"""
        model_name = sample_ollama_data["valid_model_name"]
        response = await client.get(f"/api/ollama/models/{model_name}/info")

        assert response.status_code == 200

    async def test_model_info_contains_model_name(self, client, patch_external_services, sample_ollama_data):
        """模型信息应包含模型名称。"""
        model_name = sample_ollama_data["valid_model_name"]
        response = await client.get(f"/api/ollama/models/{model_name}/info")
        data = response.json()["data"]

        assert "name" in data
        assert data["name"] == model_name

    async def test_model_info_invalid_name_returns_error(self, client, patch_external_services, sample_ollama_data):
        """不存在的模型信息应返回错误。"""
        model_name = sample_ollama_data["invalid_model_name"]
        response = await client.get(f"/api/ollama/models/{model_name}/info")

        assert response.status_code == 200
        data = response.json()
        assert data["code"] != 0 or "error" in data.get("message", "").lower()

    async def test_model_info_get_only(self, client, patch_external_services, sample_ollama_data):
        """模型信息接口应只支持GET方法。"""
        model_name = sample_ollama_data["valid_model_name"]
        response = await client.post(f"/api/ollama/models/{model_name}/info")
        assert response.status_code in [405, 404]


@pytest.mark.integration
class TestOllamaGpuInfo:
    """测试 /api/ollama/gpu-info 接口。"""

    async def test_gpu_info_returns_success(self, client, patch_external_services):
        """GPU信息接口应返回成功响应。"""
        response = await client.get("/api/ollama/gpu-info")

        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 0

    async def test_gpu_info_returns_data(self, client, patch_external_services):
        """GPU信息应返回数据对象。"""
        response = await client.get("/api/ollama/gpu-info")
        data = response.json()

        assert "data" in data

    async def test_gpu_info_get_only(self, client, patch_external_services):
        """GPU信息接口应只支持GET方法。"""
        response = await client.post("/api/ollama/gpu-info")
        assert response.status_code in [405, 404]


@pytest.mark.integration
class TestOllamaModelPull:
    """测试 /api/ollama/models/pull/{model_name} 接口。"""

    async def test_pull_model_returns_streaming_response(self, client, patch_external_services, sample_ollama_data):
        """拉取模型接口应返回流式响应。"""
        model_name = sample_ollama_data["valid_model_name"]
        response = await client.post(f"/api/ollama/models/pull/{model_name}")

        assert response.status_code == 200
        assert "text/event-stream" in response.headers.get("content-type", "")

    async def test_pull_model_empty_name_returns_error(self, client, patch_external_services):
        """空模型名称应返回错误。"""
        response = await client.post("/api/ollama/models/pull/")

        assert response.status_code in [404, 422]

    async def test_pull_model_post_only(self, client, patch_external_services, sample_ollama_data):
        """拉取模型接口应只支持POST方法。"""
        model_name = sample_ollama_data["valid_model_name"]
        response = await client.get(f"/api/ollama/models/pull/{model_name}")
        assert response.status_code in [405, 404]


@pytest.mark.integration
class TestOllamaModelDelete:
    """测试 /api/ollama/models/{model_name} DELETE 接口。"""

    async def test_delete_model_returns_success(self, client, patch_external_services, sample_ollama_data):
        """删除模型接口应返回成功响应。"""
        model_name = sample_ollama_data["valid_model_name"]
        response = await client.delete(f"/api/ollama/models/{model_name}")

        assert response.status_code == 200

    async def test_delete_model_invalid_name_returns_error(self, client, patch_external_services, sample_ollama_data):
        """不存在的模型删除应返回错误。"""
        model_name = sample_ollama_data["invalid_model_name"]
        response = await client.delete(f"/api/ollama/models/{model_name}")

        data = response.json()
        assert data["code"] != 0 or "error" in data.get("message", "").lower()

    async def test_delete_model_delete_only(self, client, patch_external_services, sample_ollama_data):
        """删除模型接口应只支持DELETE方法。"""
        model_name = sample_ollama_data["valid_model_name"]
        response = await client.post(f"/api/ollama/models/{model_name}")
        assert response.status_code in [405, 404]
