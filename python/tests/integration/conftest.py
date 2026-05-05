"""集成测试共享fixtures配置。

提供集成测试所需的测试客户端、mock对象和测试数据，
确保测试之间相互独立，不依赖外部服务。
"""
import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

# 确保项目根目录在Python路径中
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from app.main import create_app


@pytest_asyncio.fixture(scope="function")
async def client(patch_external_services):
    """创建异步HTTP测试客户端。

    为每个测试函数创建独立的FastAPI应用实例和HTTP客户端，
    确保测试之间的完全隔离。patches会在应用创建前生效。

    Yields:
        httpx.AsyncClient: 配置好的异步测试客户端
    """
    from httpx import ASGITransport, AsyncClient

    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def auth_headers():
    """生成标准认证头信息。

    当前系统暂未启用认证，返回空字典。
    后续启用认证后可在此扩展。

    Returns:
        dict: HTTP请求头信息
    """
    return {}


@pytest.fixture
def auth_headers_admin():
    """生成管理员级别的认证头信息。

    预留用于权限测试的fixture。

    Returns:
        dict: 管理员HTTP请求头信息
    """
    return {}


@pytest.fixture
def sample_knowledge_data():
    """提供标准化的知识库测试数据。

    Returns:
        dict: 包含知识库添加、查询、删除所需的数据
    """
    return {
        "add": {
            "document": "车削加工是金属切削加工中最基本的方法之一。",
            "metadata": {"type": "加工工艺", "category": "车削"},
            "doc_id": "test_knowledge_001"
        },
        "query": {
            "query_text": "车削加工",
            "n_results": 5
        },
        "expected_keys": ["documents", "metadatas", "distances", "ids"]
    }


@pytest.fixture
def sample_workflow_data():
    """提供标准化的工作流测试数据。

    Returns:
        dict: 包含工作流执行所需的输入数据
    """
    return {
        "valid_request": {
            "user_input": "我需要加工一批45钢的轴类零件，长度100mm，直径50mm，精度IT7"
        },
        "short_input": "加工零件",
        "empty_input": "",
        "max_length_input": "A" * 2001,
        "special_chars_input": "加工<>&\"'零件\n\r\t"
    }


@pytest.fixture
def sample_ollama_data():
    """提供标准化的Ollama模型测试数据。

    Returns:
        dict: 包含Ollama模型管理所需的测试数据
    """
    return {
        "recommended_models_count": 5,
        "valid_model_name": "qwen2.5-coder:7b",
        "invalid_model_name": "nonexistent-model:latest",
        "expected_status_keys": ["available", "version", "base_url"]
    }


@pytest.fixture
def sample_ai_data():
    """提供标准化的AI对话测试数据。

    Returns:
        dict: 包含AI对话接口所需的测试数据
    """
    return {
        "agents_info_keys": ["code", "data", "message"],
        "expected_agents_count": 6,
        "agent_names": [
            "UnderstandingAgent",
            "PlanningAgent",
            "ParameterAgent",
            "NCAgent",
            "VerificationAgent",
            "RepairAgent"
        ]
    }


@pytest.fixture
def mock_llm_for_integration():
    """创建集成测试专用的LLM客户端mock。

    模拟LLM客户端的chat_completion和is_available方法。

    Returns:
        AsyncMock: 配置好的LLM客户端mock
    """
    mock_client = AsyncMock()
    mock_client.chat_completion.return_value = {
        "content": json.dumps({
            "material": "45钢",
            "part_type": "轴类零件",
            "dimensions": {"length": 100.0, "width": 50.0, "height": 30.0},
            "tolerance": "IT7",
            "surface_roughness": "Ra 0.8",
            "quantity": 100
        }, ensure_ascii=False),
        "model": "qwen2.5-coder:7b",
        "finish_reason": "stop"
    }
    mock_client.is_available.return_value = True
    return mock_client


@pytest.fixture
def mock_knowledge_base_for_integration():
    """创建集成测试专用的知识库mock。

    模拟KnowledgeBase的query、add_knowledge、delete、count方法。

    Returns:
        MagicMock: 配置好的知识库mock
    """
    mock_kb = MagicMock()
    mock_kb.query.return_value = {
        "documents": ["测试知识文档1", "测试知识文档2"],
        "metadatas": [{"type": "测试"}, {"type": "集成"}],
        "distances": [0.1, 0.2],
        "ids": ["test_001", "test_002"]
    }
    mock_kb.add_knowledge.return_value = "test_doc_id_001"
    mock_kb.delete.return_value = None
    mock_kb.count.return_value = 10
    mock_kb.load_default_knowledge.return_value = None
    mock_kb.load_rag_json_knowledge.return_value = {"success": 5, "skipped": 0, "errors": 0}
    return mock_kb


@pytest.fixture
def mock_ollama_manager():
    """创建集成测试专用的Ollama管理器mock。

    模拟OllamaManager的各项方法。

    Returns:
        AsyncMock: 配置好的Ollama管理器mock
    """
    mock_manager = AsyncMock()
    mock_manager.is_available.return_value = True
    mock_manager.get_version.return_value = "0.5.0"
    mock_manager.list_models.return_value = [
        {"name": "qwen2.5-coder:7b", "size": "4.2GB"},
        {"name": "llama3.1:8b", "size": "4.7GB"}
    ]
    mock_manager.show_model_info.return_value = {
        "name": "qwen2.5-coder:7b",
        "details": {"format": "gguf", "family": "qwen2"}
    }
    mock_manager.delete_model.return_value = True
    mock_manager.get_gpu_info.return_value = {"gpu_count": 0}

    async def mock_pull_progress():
        yield {"status": "pulling", "progress": 100}

    mock_manager.pull_model.return_value = mock_pull_progress()
    return mock_manager


@pytest.fixture
def patch_external_services(mock_llm_for_integration, mock_knowledge_base_for_integration, mock_ollama_manager):
    """修补所有外部服务依赖。

    确保测试不依赖真实的Ollama、ChromaDB等服务。
    注意：patch需要在函数被使用的位置，而不是定义的位置。

    Yields:
        dict: 包含所有patch对象的字典
    """
    llm_patch = patch("app.ai.agents.get_llm_client", return_value=mock_llm_for_integration)
    kb_patch = patch("app.rag.routes.get_knowledge_base", return_value=mock_knowledge_base_for_integration)
    ollama_patch = patch("app.ai.ollama_routes.OllamaManager", return_value=mock_ollama_manager)
    ollama_instance_patch = patch("app.ai.ollama_routes._manager", mock_ollama_manager)

    llm_patch.start()
    kb_patch.start()
    ollama_patch.start()
    ollama_instance_patch.start()

    yield {
        "llm": llm_patch,
        "knowledge_base": kb_patch,
        "ollama_class": ollama_patch,
        "ollama_instance": ollama_instance_patch
    }

    llm_patch.stop()
    kb_patch.stop()
    ollama_patch.stop()
    ollama_instance_patch.stop()
