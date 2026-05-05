"""
灵境制造 - API 性能基准测试
"""
import pytest
from httpx import AsyncClient

from app.main import create_app


@pytest.fixture
async def client():
    app = create_app()
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac


class TestHealthEndpoint:
    """健康检查接口基准测试"""

    @pytest.mark.benchmark(group="health")
    def test_health_check(self, benchmark, client):
        """健康检查应该在 10ms 内完成"""
        @benchmark
        def _():
            import asyncio
            return asyncio.get_event_loop().run_until_complete(
                self._request_health(client)
            )

    async def _request_health(self, client):
        response = await client.get("/health")
        assert response.status_code == 200
        return response


class TestAIChatEndpoint:
    """AI对话接口基准测试"""

    @pytest.mark.benchmark(group="ai_chat")
    def test_ai_chat_latency(self, benchmark):
        """AI对话接口延迟测试"""
        pass

    @pytest.mark.benchmark(group="agents")
    def test_agents_info(self, benchmark):
        """获取Agent信息接口"""
        pass


class TestWorkflowPerformance:
    """工作流性能基准测试"""

    @pytest.mark.benchmark(group="workflow")
    def test_full_workflow_latency(self, benchmark):
        """完整工作流延迟测试（目标：<60s）"""
        pass

    @pytest.mark.benchmark(group="workflow_understanding")
    def test_understanding_stage(self, benchmark):
        """理解阶段性能测试"""
        pass

    @pytest.mark.benchmark(group="workflow_planning")
    def test_planning_stage(self, benchmark):
        """规划阶段性能测试"""
        pass


class TestKnowledgeBasePerformance:
    """知识库性能基准测试"""

    @pytest.mark.benchmark(group="knowledge_query")
    def test_knowledge_query_latency(self, benchmark):
        """知识库查询延迟测试（目标：<3s）"""
        pass

    @pytest.mark.benchmark(group="knowledge_insert")
    def test_knowledge_insert_batch(self, benchmark):
        """批量知识插入性能"""
        pass
