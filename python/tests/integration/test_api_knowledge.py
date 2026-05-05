"""知识库相关API集成测试。

测试知识库健康检查、知识添加、查询、删除等接口的功能正确性和稳定性。
"""
import pytest


@pytest.mark.integration
class TestKnowledgeHealth:
    """测试 /api/knowledge/health 接口。"""

    async def test_health_returns_success(self, client, patch_external_services):
        """知识库健康检查应返回成功响应。"""
        response = await client.get("/api/knowledge/health")

        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 0
        assert "data" in data

    async def test_health_contains_status_and_count(self, client, patch_external_services):
        """健康检查响应应包含status和count字段。"""
        response = await client.get("/api/knowledge/health")
        data = response.json()["data"]

        assert "status" in data
        assert "count" in data

    async def test_health_count_is_integer(self, client, patch_external_services):
        """知识数量应该是整数。"""
        response = await client.get("/api/knowledge/health")
        data = response.json()["data"]

        assert isinstance(data["count"], int)
        assert data["count"] >= 0

    async def test_health_status_is_string(self, client, patch_external_services):
        """健康状态应该是字符串。"""
        response = await client.get("/api/knowledge/health")
        data = response.json()["data"]

        assert isinstance(data["status"], str)

    async def test_health_get_only(self, client, patch_external_services):
        """健康检查接口应只支持GET方法。"""
        response = await client.post("/api/knowledge/health")
        assert response.status_code in [405, 404]


@pytest.mark.integration
class TestKnowledgeAdd:
    """测试 /api/knowledge/add 接口。"""

    async def test_add_knowledge_with_valid_data(self, client, patch_external_services, sample_knowledge_data):
        """有效数据应成功添加知识。"""
        response = await client.post(
            "/api/knowledge/add",
            json=sample_knowledge_data["add"]
        )

        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 0
        assert "data" in data
        assert "doc_id" in data["data"]

    async def test_add_knowledge_returns_doc_id(self, client, patch_external_services, sample_knowledge_data):
        """添加知识应返回文档ID。"""
        response = await client.post(
            "/api/knowledge/add",
            json=sample_knowledge_data["add"]
        )
        data = response.json()["data"]

        assert "doc_id" in data
        assert isinstance(data["doc_id"], str)
        assert len(data["doc_id"]) > 0

    async def test_add_knowledge_missing_document(self, client, patch_external_services):
        """缺少document字段应返回验证错误。"""
        response = await client.post(
            "/api/knowledge/add",
            json={"metadata": {"type": "测试"}}
        )

        data = response.json()
        assert response.status_code == 200
        assert data["code"] != 0

    async def test_add_knowledge_empty_document(self, client, patch_external_services):
        """空文档内容应返回验证错误。"""
        response = await client.post(
            "/api/knowledge/add",
            json={"document": "", "metadata": {}}
        )

        data = response.json()
        assert response.status_code == 200
        assert data["code"] != 0

    async def test_add_knowledge_short_document(self, client, patch_external_services):
        """过短文档内容应返回验证错误。"""
        response = await client.post(
            "/api/knowledge/add",
            json={"document": "短", "metadata": {}}
        )

        data = response.json()
        assert response.status_code == 200
        assert data["code"] != 0

    async def test_add_knowledge_with_metadata(self, client, patch_external_services):
        """带元数据的知识应成功添加。"""
        response = await client.post(
            "/api/knowledge/add",
            json={
                "document": "这是一条带元数据的测试知识内容，长度需要超过10个字符。",
                "metadata": {"type": "测试", "category": "集成测试", "priority": "high"},
                "doc_id": "test_with_metadata"
            }
        )

        assert response.status_code == 200

    async def test_add_knowledge_with_custom_doc_id(self, client, patch_external_services, sample_knowledge_data):
        """自定义文档ID应成功添加。"""
        response = await client.post(
            "/api/knowledge/add",
            json={
                "document": sample_knowledge_data["add"]["document"],
                "metadata": {},
                "doc_id": sample_knowledge_data["add"]["doc_id"]
            }
        )

        assert response.status_code == 200

    async def test_add_knowledge_post_only(self, client, patch_external_services, sample_knowledge_data):
        """添加知识接口应只支持POST方法。"""
        response = await client.get("/api/knowledge/add")
        assert response.status_code in [405, 404]


@pytest.mark.integration
class TestKnowledgeQuery:
    """测试 /api/knowledge/query 接口。"""

    async def test_query_with_valid_request(self, client, patch_external_services, sample_knowledge_data):
        """有效查询请求应返回结果。"""
        response = await client.post(
            "/api/knowledge/query",
            json=sample_knowledge_data["query"]
        )

        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 0

    async def test_query_response_structure(self, client, patch_external_services, sample_knowledge_data):
        """查询响应应包含标准结构。"""
        response = await client.post(
            "/api/knowledge/query",
            json=sample_knowledge_data["query"]
        )
        data = response.json()["data"]

        for key in sample_knowledge_data["expected_keys"]:
            assert key in data, f"缺少必需字段: {key}"

    async def test_query_returns_lists(self, client, patch_external_services, sample_knowledge_data):
        """查询响应中的关键字段应该是列表。"""
        response = await client.post(
            "/api/knowledge/query",
            json=sample_knowledge_data["query"]
        )
        data = response.json()["data"]

        assert isinstance(data["documents"], list)
        assert isinstance(data["metadatas"], list)
        assert isinstance(data["distances"], list)
        assert isinstance(data["ids"], list)

    async def test_query_missing_query_text(self, client, patch_external_services):
        """缺少query_text字段应返回验证错误。"""
        response = await client.post(
            "/api/knowledge/query",
            json={"n_results": 5}
        )

        data = response.json()
        assert response.status_code == 200
        assert data["code"] != 0

    async def test_query_empty_query_text(self, client, patch_external_services):
        """空查询文本应返回验证错误。"""
        response = await client.post(
            "/api/knowledge/query",
            json={"query_text": "", "n_results": 5}
        )

        data = response.json()
        assert response.status_code == 200
        assert data["code"] != 0

    async def test_query_with_large_n_results(self, client, patch_external_services):
        """超出范围的n_results应返回验证错误。"""
        response = await client.post(
            "/api/knowledge/query",
            json={"query_text": "测试查询", "n_results": 100}
        )

        data = response.json()
        assert response.status_code == 200
        assert data["code"] != 0

    async def test_query_with_negative_n_results(self, client, patch_external_services):
        """负数n_results应返回验证错误。"""
        response = await client.post(
            "/api/knowledge/query",
            json={"query_text": "测试查询", "n_results": -1}
        )

        data = response.json()
        assert response.status_code == 200
        assert data["code"] != 0

    async def test_query_post_only(self, client, patch_external_services, sample_knowledge_data):
        """查询接口应只支持POST方法。"""
        response = await client.get("/api/knowledge/query")
        assert response.status_code in [405, 404]


@pytest.mark.integration
class TestKnowledgeDelete:
    """测试 /api/knowledge/delete 接口。"""

    async def test_delete_knowledge_with_valid_doc_id(self, client, patch_external_services, sample_knowledge_data):
        """有效文档ID应成功删除知识。"""
        response = await client.post(
            "/api/knowledge/delete",
            json={"doc_id": sample_knowledge_data["add"]["doc_id"]}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 0

    async def test_delete_knowledge_missing_doc_id(self, client, patch_external_services):
        """缺少doc_id字段应返回验证错误。"""
        response = await client.post("/api/knowledge/delete", json={})

        data = response.json()
        assert response.status_code == 200
        assert data["code"] != 0

    async def test_delete_knowledge_empty_doc_id(self, client, patch_external_services):
        """空doc_id应返回验证错误。"""
        response = await client.post(
            "/api/knowledge/delete",
            json={"doc_id": ""}
        )

        data = response.json()
        assert response.status_code == 200
        assert data["code"] != 0

    async def test_delete_knowledge_post_only(self, client, patch_external_services, sample_knowledge_data):
        """删除知识接口应只支持POST方法。"""
        response = await client.get("/api/knowledge/delete")
        assert response.status_code in [405, 404]


@pytest.mark.integration
class TestKnowledgeCount:
    """测试 /api/knowledge/count 接口。"""

    async def test_count_returns_success(self, client, patch_external_services):
        """知识计数接口应返回成功响应。"""
        response = await client.get("/api/knowledge/count")

        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 0

    async def test_count_returns_count_value(self, client, patch_external_services):
        """知识计数应返回count字段。"""
        response = await client.get("/api/knowledge/count")
        data = response.json()["data"]

        assert "count" in data
        assert isinstance(data["count"], int)
        assert data["count"] >= 0

    async def test_count_get_only(self, client, patch_external_services):
        """知识计数接口应只支持GET方法。"""
        response = await client.post("/api/knowledge/count")
        assert response.status_code in [405, 404]


@pytest.mark.integration
class TestKnowledgeInit:
    """测试 /api/knowledge/init 接口。"""

    async def test_init_knowledge_returns_success(self, client, patch_external_services):
        """初始化知识库应返回成功响应。"""
        response = await client.post("/api/knowledge/init")

        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 0

    async def test_init_knowledge_returns_count(self, client, patch_external_services):
        """初始化知识库应返回知识数量。"""
        response = await client.post("/api/knowledge/init")
        data = response.json()["data"]

        assert "count" in data
        assert isinstance(data["count"], int)

    async def test_init_knowledge_post_only(self, client, patch_external_services):
        """初始化知识库接口应只支持POST方法。"""
        response = await client.get("/api/knowledge/init")
        assert response.status_code in [405, 404]


@pytest.mark.integration
class TestKnowledgeImportJson:
    """测试 /api/knowledge/import-json 接口。"""

    async def test_import_json_returns_success(self, client, patch_external_services):
        """导入JSON知识库应返回成功响应。"""
        response = await client.post("/api/knowledge/import-json")

        assert response.status_code == 200

    async def test_import_json_returns_stats(self, client, patch_external_services):
        """导入JSON知识库应返回统计信息。"""
        response = await client.post("/api/knowledge/import-json")
        data = response.json()

        if data["code"] == 0:
            assert "data" in data
            if "stats" in data["data"]:
                stats = data["data"]["stats"]
                assert isinstance(stats, dict)

    async def test_import_json_post_only(self, client, patch_external_services):
        """导入JSON知识库接口应只支持POST方法。"""
        response = await client.get("/api/knowledge/import-json")
        assert response.status_code in [405, 404]
