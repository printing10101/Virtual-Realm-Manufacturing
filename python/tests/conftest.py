"""全局测试fixtures配置。

提供测试过程中常用的mock对象和测试数据，
包括LLM客户端模拟、知识库模拟、AgentContext工厂等。
"""
import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.ai.agents import AgentContext, UnderstandingAgent


@pytest.fixture
def mock_llm_response_success():
    """创建成功的LLM响应mock。

    Returns:
        dict: 模拟LLM成功返回的响应字典
    """
    return {
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


@pytest.fixture
def mock_llm_response_with_markdown():
    """创建包含markdown代码块的LLM响应mock。

    Returns:
        dict: 模拟包含```json```包裹的LLM响应
    """
    return {
        "content": "```json\n" + json.dumps({
            "material": "6061铝合金",
            "part_type": "壳体类零件",
            "dimensions": {"length": 200.0, "width": 150.0, "height": 100.0},
            "tolerance": "IT8",
            "surface_roughness": "Ra 1.6",
            "quantity": 50
        }, ensure_ascii=False) + "\n```",
        "model": "qwen2.5-coder:7b",
        "finish_reason": "stop"
    }


@pytest.fixture
def mock_llm_response_invalid_json():
    """创建无效JSON的LLM响应mock。

    Returns:
        dict: 模拟JSON格式错误的LLM响应
    """
    return {
        "content": '{"material": "45钢", "part_type": "轴类", "dimensions": {"length": 100}',
        "model": "qwen2.5-coder:7b",
        "finish_reason": "stop"
    }


@pytest.fixture
def mock_llm_response_empty():
    """创建空内容的LLM响应mock。

    Returns:
        dict: 模拟空内容的LLM响应
    """
    return {
        "content": "",
        "model": "qwen2.5-coder:7b",
        "finish_reason": "stop"
    }


@pytest.fixture
def mock_llm_response_plain_text():
    """创建纯文本（非JSON）的LLM响应mock。

    Returns:
        dict: 模拟纯文本格式的LLM响应
    """
    return {
        "content": "根据您的需求，我分析出以下参数：\n材料：45钢\n零件类型：轴类\n尺寸：长度100mm",
        "model": "qwen2.5-coder:7b",
        "finish_reason": "stop"
    }


@pytest.fixture
def mock_knowledge_base():
    """创建知识库mock对象。

    模拟KnowledgeBase的query方法，返回预设的检索结果。

    Returns:
        MagicMock: 配置了query方法的知识库mock对象
    """
    kb = MagicMock()
    kb.query.return_value = {
        "documents": [
            "车削加工基础：车削是最基本的金属切削加工方法，主要用于加工回转体表面。",
            "45钢材料参数：45钢是中国GB标准的中碳结构钢，抗拉强度≥600MPa。",
            "表面粗糙度等级：Ra 0.8属于半精加工级别。"
        ],
        "metadatas": [
            {"type": "车削", "category": "加工工艺"},
            {"type": "材料", "category": "45钢"},
            {"type": "标准", "category": "表面粗糙度"}
        ],
        "distances": [0.1, 0.2, 0.3],
        "ids": ["turning_basic", "steel_45", "surface_roughness"]
    }
    return kb


@pytest.fixture
def mock_knowledge_base_empty():
    """创建空检索结果的知识库mock对象。

    Returns:
        MagicMock: 返回空检索结果的知识库mock对象
    """
    kb = MagicMock()
    kb.query.return_value = {
        "documents": [],
        "metadatas": [],
        "distances": [],
        "ids": []
    }
    return kb


@pytest.fixture
def mock_llm_client():
    """创建LLM客户端mock对象。

    模拟BaseLLMClient的chat_completion方法，返回预设的响应。

    Returns:
        AsyncMock: 配置了chat_completion方法的LLM客户端mock对象
    """
    client = AsyncMock()
    client.chat_completion.return_value = {
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
    return client


@pytest.fixture
def mock_model_router():
    """创建模型路由mock对象。

    模拟model_router的execute方法，返回预设的响应。

    Returns:
        AsyncMock: 配置了execute方法的模型路由mock对象
    """
    router = AsyncMock()
    router.execute.return_value = {
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
    return router


@pytest.fixture
def agent_context():
    """创建默认的AgentContext对象。

    Returns:
        AgentContext: 初始状态的AgentContext实例
    """
    return AgentContext(
        user_input="我需要加工一批45钢的轴类零件，长度100mm，直径50mm，精度IT7",
        extracted_params={},
        process_route=[],
        cutting_parameters={},
        nc_code="",
        verification_result={},
        repair_suggestions=[],
        current_stage="",
        stage_status=""
    )


@pytest.fixture
def agent_context_complex():
    """创建包含复杂需求的AgentContext对象。

    包含多种材料、精度要求和特殊加工条件。

    Returns:
        AgentContext: 包含复杂需求的AgentContext实例
    """
    return AgentContext(
        user_input="""
        需要加工以下零件：
        1. 6061铝合金壳体，尺寸200x150x100mm，公差IT8，表面粗糙度Ra1.6
        2. 45钢传动轴，直径30mm，长度500mm，公差IT6，表面粗糙度Ra0.4
        加工数量：各50件
        特殊要求：铝合金件需要阳极氧化处理
        """,
        extracted_params={},
        process_route=[],
        cutting_parameters={},
        nc_code="",
        verification_result={},
        repair_suggestions=[],
        current_stage="",
        stage_status=""
    )


@pytest.fixture
def agent_context_boundary():
    """创建边界条件的AgentContext对象。

    包含极值、空输入、特殊字符等边界情况。

    Returns:
        AgentContext: 包含边界条件的AgentContext实例
    """
    return AgentContext(
        user_input="",
        extracted_params={},
        process_route=[],
        cutting_parameters={},
        nc_code="",
        verification_result={},
        repair_suggestions=[],
        current_stage="",
        stage_status=""
    )


@pytest.fixture
def understanding_agent_instance(mock_llm_client, mock_knowledge_base):
    """创建UnderstandingAgent测试实例。

    使用mock对象替换真实的LLM客户端和知识库，
    确保测试不依赖外部资源。

    Args:
        mock_llm_client: LLM客户端mock
        mock_knowledge_base: 知识库mock

    Returns:
        UnderstandingAgent: 配置了mock依赖的UnderstandingAgent实例
    """
    agent = UnderstandingAgent()
    agent.llm_client = mock_llm_client
    agent.knowledge_base = mock_knowledge_base
    agent._model_router = None
    return agent


@pytest.fixture
def temp_chroma_db():
    """创建临时ChromaDB目录。

    提供独立的临时目录用于测试知识库持久化，
    测试完成后自动清理。

    Yields:
        str: 临时数据库目录路径
    """
    with tempfile.TemporaryDirectory() as temp_dir:
        yield temp_dir


@pytest.fixture
def patch_get_llm_client(mock_llm_client):
    """修补get_llm_client函数。

    使得所有调用get_llm_client()的地方都返回mock_llm_client。

    Args:
        mock_llm_client: LLM客户端mock

    Yields:
        MagicMock: patch对象
    """
    with patch("app.ai.agents.get_llm_client", return_value=mock_llm_client) as mock:
        yield mock


@pytest.fixture
def patch_get_knowledge_base(mock_knowledge_base):
    """修补get_knowledge_base函数。

    使得所有调用get_knowledge_base()的地方都返回mock_knowledge_base。

    Args:
        mock_knowledge_base: 知识库mock

    Yields:
        MagicMock: patch对象
    """
    with patch("app.ai.agents.get_knowledge_base", return_value=mock_knowledge_base) as mock:
        yield mock


@pytest.fixture
def patch_container_model_router(mock_model_router):
    """修补container获取model_router的逻辑。

    使得agent._get_model_router()返回mock_model_router。

    Args:
        mock_model_router: 模型路由mock

    Yields:
        MagicMock: patch对象
    """
    with patch("app.core.container.container.get_service", return_value=mock_model_router) as mock:
        yield mock
