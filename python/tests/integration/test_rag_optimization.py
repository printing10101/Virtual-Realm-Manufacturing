"""RAG知识库优化功能集成测试。

测试知识库扩展、重排序、文档导入、管理界面和评估体系的功能。
"""

import pytest


@pytest.mark.integration
class TestExtendedKnowledge:
    """测试扩展知识库功能。"""

    async def test_init_extended_knowledge(self, client, patch_external_services):
        """初始化扩展知识库应返回成功响应。"""
        response = await client.post("/api/knowledge/init-extended")

        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 0
        assert "stats" in data["data"]
        assert data["data"]["stats"]["success"] > 100

    async def test_extended_knowledge_count(self, client, patch_external_services):
        """扩展知识库应包含100+条知识。"""
        response = await client.post("/api/knowledge/init-extended")

        response = await client.get("/api/knowledge/count")
        data = response.json()["data"]

        assert data["count"] > 100

    async def test_query_extended_knowledge(self, client, patch_external_services):
        """查询扩展知识库应返回相关结果。"""
        await client.post("/api/knowledge/init-extended")

        response = await client.post(
            "/api/knowledge/query",
            json={"query_text": "45钢车削参数", "n_results": 3}
        )

        assert response.status_code == 200
        data = response.json()
        assert "data" in data
        assert len(data["data"]["documents"]) > 0


@pytest.mark.integration
class TestReranker:
    """测试重排序功能。"""

    async def test_query_with_rerank(self, client, patch_external_services):
        """带重排序的查询应返回重排序结果。"""
        await client.post("/api/knowledge/init-extended")

        response = await client.post(
            "/api/knowledge/query",
            json={"query_text": "不锈钢铣削", "n_results": 3, "enable_rerank": True}
        )

        assert response.status_code == 200
        data = response.json()["data"]
        assert data.get("reranked")
        assert "results" in data
        assert len(data["results"]) > 0

    async def test_query_without_rerank(self, client, patch_external_services):
        """不带重排序的查询应返回原始结果。"""
        await client.post("/api/knowledge/init-extended")

        response = await client.post(
            "/api/knowledge/query",
            json={"query_text": "不锈钢铣削", "n_results": 3, "enable_rerank": False}
        )

        assert response.status_code == 200
        data = response.json()["data"]
        assert "documents" in data

    async def test_reranker_info(self, client, patch_external_services):
        """重排序信息接口应返回配置信息。"""
        response = await client.get("/api/knowledge/reranker-info")

        assert response.status_code == 200
        data = response.json()["data"]
        assert "cross_encoder_enabled" in data
        assert "lightweight_reranker" in data

    async def test_rerank_improves_relevance(self, client, patch_external_services):
        """重排序应提高相关性。"""
        await client.post("/api/knowledge/init-extended")

        response_no_rerank = await client.post(
            "/api/knowledge/query",
            json={"query_text": "刀具选择", "n_results": 5, "enable_rerank": False}
        )

        response_with_rerank = await client.post(
            "/api/knowledge/query",
            json={"query_text": "刀具选择", "n_results": 5, "enable_rerank": True}
        )

        assert response_no_rerank.status_code == 200
        assert response_with_rerank.status_code == 200


@pytest.mark.integration
class TestDocumentImport:
    """测试文档导入功能。"""

    async def test_import_markdown_document(self, client, patch_external_services):
        """导入Markdown文档应成功。"""
        await client.post("/api/knowledge/init-extended")

        md_content = """# 车削加工指南

## 基本概念
车削是最基本的金属切削加工方法。

## 切削参数
粗车45钢时，推荐切削速度80-120m/min。

## 注意事项
注意冷却液的使用和刀具选择。
"""

        response = await client.post(
            "/api/knowledge/import-document",
            files={"file": ("test_guide.md", md_content, "text/markdown")},
            data={"category": "车削", "description": "测试文档", "tags": "车削,加工"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 0
        assert data["data"]["chunk_count"] > 0

    async def test_import_history(self, client, patch_external_services):
        """导入历史应记录导入操作。"""
        await client.post("/api/knowledge/init-extended")

        md_content = "# 测试文档\n这是一条测试知识。"
        await client.post(
            "/api/knowledge/import-document",
            files={"file": ("test.md", md_content, "text/markdown")}
        )

        response = await client.get("/api/knowledge/import-history")

        assert response.status_code == 200
        data = response.json()["data"]
        assert "history" in data
        assert len(data["history"]) > 0

    async def test_import_stats(self, client, patch_external_services):
        """导入统计应返回统计信息。"""
        response = await client.get("/api/knowledge/import-stats")

        assert response.status_code == 200
        data = response.json()["data"]
        assert "total_documents" in data
        assert "total_chunks" in data

    async def test_import_unsupported_format(self, client, patch_external_services):
        """导入不支持的格式应返回错误。"""
        response = await client.post(
            "/api/knowledge/import-document",
            files={"file": ("test.txt", "test content", "text/plain")}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["code"] != 0


@pytest.mark.integration
class TestKnowledgeManagement:
    """测试知识库管理功能。"""

    async def test_list_knowledge(self, client, patch_external_services):
        """知识列表应返回分页结果。"""
        await client.post("/api/knowledge/init-extended")

        response = await client.get("/api/knowledge/list?page=1&page_size=10")

        assert response.status_code == 200
        data = response.json()["data"]
        assert "documents" in data
        assert "pagination" in data
        assert len(data["documents"]) <= 10

    async def test_list_knowledge_with_category(self, client, patch_external_services):
        """按分类筛选应返回对应分类的知识。"""
        await client.post("/api/knowledge/init-extended")

        response = await client.get("/api/knowledge/list?category=不锈钢")

        assert response.status_code == 200
        data = response.json()["data"]
        for doc in data["documents"]:
            assert doc["metadata"].get("category") == "不锈钢"

    async def test_list_knowledge_with_keyword(self, client, patch_external_services):
        """按关键词搜索应返回相关知识。"""
        await client.post("/api/knowledge/init-extended")

        response = await client.get("/api/knowledge/list?keyword=车削")

        assert response.status_code == 200
        data = response.json()["data"]
        assert len(data["documents"]) > 0

    async def test_get_categories(self, client, patch_external_services):
        """获取分类统计应返回分类信息。"""
        await client.post("/api/knowledge/init-extended")

        response = await client.get("/api/knowledge/categories")

        assert response.status_code == 200
        data = response.json()["data"]
        assert "categories" in data
        assert "doc_types" in data
        assert len(data["categories"]) > 0

    async def test_get_single_knowledge(self, client, patch_external_services):
        """获取单条知识应返回知识详情。"""
        await client.post("/api/knowledge/init-extended")

        response = await client.get("/api/knowledge/get/ext_mat_ss_001")

        assert response.status_code == 200
        data = response.json()["data"]
        assert data["doc_id"] == "ext_mat_ss_001"
        assert "document" in data
        assert "metadata" in data

    async def test_update_knowledge(self, client, patch_external_services):
        """更新知识应成功修改知识内容。"""
        await client.post("/api/knowledge/init-extended")

        response = await client.put(
            "/api/knowledge/update/ext_mat_ss_001",
            json={
                "document": "更新后的304不锈钢知识内容，长度需要超过10个字符。",
                "metadata": {"type": "材料", "category": "不锈钢", "subcategory": "304更新"},
                "doc_id": "ext_mat_ss_001"
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 0

    async def test_delete_knowledge_batch(self, client, patch_external_services):
        """批量删除知识应成功删除多条知识。"""
        await client.post("/api/knowledge/init-extended")

        response = await client.post(
            "/api/knowledge/delete-batch",
            json={"doc_ids": ["ext_mat_ss_001", "ext_mat_ss_002"]}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["data"]["deleted_count"] == 2

    async def test_get_knowledge_stats(self, client, patch_external_services):
        """获取统计信息应返回详细统计。"""
        await client.post("/api/knowledge/init-extended")

        response = await client.get("/api/knowledge/stats")

        assert response.status_code == 200
        data = response.json()["data"]
        assert "total_count" in data
        assert "categories" in data
        assert "doc_types" in data
        assert "avg_document_length" in data

    async def test_export_knowledge(self, client, patch_external_services):
        """导出知识应返回JSON格式数据。"""
        await client.post("/api/knowledge/init-extended")

        response = await client.post("/api/knowledge/export?format=json")

        assert response.status_code == 200
        data = response.json()["data"]
        assert data["format"] == "json"
        assert "count" in data
        assert "data" in data


@pytest.mark.integration
class TestEvaluation:
    """测试检索效果评估功能。"""

    async def test_dataset_stats(self, client, patch_external_services):
        """评估数据集统计应返回统计信息。"""
        response = await client.get("/api/knowledge/evaluation/dataset-stats")

        assert response.status_code == 200
        data = response.json()["data"]
        assert data["total_queries"] >= 50
        assert "categories" in data
        assert "difficulties" in data

    async def test_run_evaluation(self, client, patch_external_services):
        """运行评估应返回评估报告。"""
        await client.post("/api/knowledge/init-extended")

        response = await client.post("/api/knowledge/evaluation/run?top_k=3")

        assert response.status_code == 200
        data = response.json()["data"]
        assert "report_id" in data
        assert "top3_accuracy" in data
        assert "performance_target_met" in data
        assert isinstance(data["top3_accuracy"], float)

    async def test_evaluation_by_category(self, client, patch_external_services):
        """按分类评估应返回该分类的评估结果。"""
        await client.post("/api/knowledge/init-extended")

        response = await client.post(
            "/api/knowledge/evaluation/run?top_k=3&category=材料参数"
        )

        assert response.status_code == 200
        data = response.json()["data"]
        assert "total_queries" in data

    async def test_generate_evaluation_report(self, client, patch_external_services):
        """生成评估报告应返回报告内容。"""
        await client.post("/api/knowledge/init-extended")

        response = await client.post(
            "/api/knowledge/evaluation/generate-report?top_k=3"
        )

        assert response.status_code == 200
        data = response.json()["data"]
        assert "report" in data or "report_path" in data

    async def test_get_evaluation_query(self, client, patch_external_services):
        """获取评估查询应返回查询详情。"""
        response = await client.get("/api/knowledge/evaluation/query/EQ001")

        assert response.status_code == 200
        data = response.json()["data"]
        assert data["query_id"] == "EQ001"
        assert "query_text" in data
        assert "expected_doc_ids" in data

    async def test_evaluation_performance_target(self, client, patch_external_services):
        """评估应检查是否达到性能目标。"""
        await client.post("/api/knowledge/init-extended")

        response = await client.post("/api/knowledge/evaluation/run?top_k=3")

        assert response.status_code == 200
        data = response.json()["data"]
        assert "performance_target_met" in data
        assert "target_accuracy" in data
        assert data["target_accuracy"] == 0.80
