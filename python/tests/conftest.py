"""全局测试fixtures配置。

提供测试过程中常用的mock对象和测试数据，
包括LLM客户端模拟、知识库模拟、AgentContext工厂等。
"""
import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from app.ai.agents import AgentContext, UnderstandingAgent
    _AI_MODULES_AVAILABLE = True
except (ImportError, ModuleNotFoundError):
    _AI_MODULES_AVAILABLE = False


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
    if not _AI_MODULES_AVAILABLE:
        pytest.skip("AI模块不可用")
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
    if not _AI_MODULES_AVAILABLE:
        pytest.skip("AI模块不可用")
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
    if not _AI_MODULES_AVAILABLE:
        pytest.skip("AI模块不可用")
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
    if not _AI_MODULES_AVAILABLE:
        pytest.skip("AI模块不可用")
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


# ==================== Bosch CNC 集成测试fixtures ====================

import numpy as np

TEST_RANDOM_SEED = 42
np.random.seed(TEST_RANDOM_SEED)


@pytest.fixture(scope="session")
def bosch_test_data_dir():
    """提供Bosch CNC测试样本数据目录路径。

    Returns:
        str: Bosch CNC测试样本数据的绝对路径
    """
    test_data_path = Path(__file__).parent / "data" / "bosch_test_samples"
    if not test_data_path.exists():
        pytest.skip("测试样本数据不存在，请先运行 generate_test_data.py 生成测试数据")
    return str(test_data_path.resolve())


@pytest.fixture(scope="session")
def sample_vibration_data():
    """提供标准样本振动数据。

    Returns:
        np.ndarray: 形状为(500, 3)的三轴振动数据 (x, y, z)
    """
    rng = np.random.RandomState(TEST_RANDOM_SEED)
    t = np.arange(500) / 2000

    x = 0.1 * np.sin(2 * np.pi * 50 * t) + 0.05 * rng.randn(500)
    y = 0.08 * np.sin(2 * np.pi * 60 * t + 0.5) + 0.05 * rng.randn(500)
    z = 0.05 * np.sin(2 * np.pi * 70 * t + 1.0) + 0.05 * rng.randn(500)

    return np.column_stack([x, y, z]).astype(np.float64)


@pytest.fixture(scope="session")
def abnormal_vibration_data():
    """提供异常振动数据样本。

    Returns:
        np.ndarray: 形状为(500, 3)的异常三轴振动数据
    """
    rng = np.random.RandomState(TEST_RANDOM_SEED + 1)
    t = np.arange(500) / 2000

    x = 0.5 * np.sin(2 * np.pi * 50 * t) + 0.3 * rng.randn(500)
    y = 0.4 * np.sin(2 * np.pi * 60 * t + 0.5) + 0.3 * rng.randn(500)
    z = 0.25 * np.sin(2 * np.pi * 70 * t + 1.0) + 0.3 * rng.randn(500)

    return np.column_stack([x, y, z]).astype(np.float64)


@pytest.fixture
def temp_chroma_dir():
    """创建临时ChromaDB目录用于Bosch知识库测试。

    测试完成后自动清理。在Windows上处理文件锁定问题。

    Yields:
        str: 临时数据库目录路径
    """
    import shutil
    
    temp_dir = tempfile.mkdtemp()
    try:
        yield temp_dir
    finally:
        # Windows上ChromaDB可能保持文件打开,需要延迟清理
        import gc
        gc.collect()  # 强制垃圾回收释放文件句柄
        import time
        time.sleep(0.1)  # 短暂等待文件释放
        
        if os.path.exists(temp_dir):
            try:
                shutil.rmtree(temp_dir, ignore_errors=True)
            except Exception:
                pass  # 忽略清理错误


@pytest.fixture
def temp_rules_file():
    """创建临时验证规则文件用于测试。

    Yields:
        Path: 临时规则文件路径
    """
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        f.write("{}")
        rules_path = Path(f.name)
    try:
        yield rules_path
    finally:
        if rules_path.exists():
            rules_path.unlink()


@pytest.fixture
def temp_experience_dir():
    """创建临时经验存储目录用于测试。

    Yields:
        str: 临时经验存储目录路径
    """
    with tempfile.TemporaryDirectory() as temp_dir:
        yield temp_dir


@pytest.fixture
def temp_finetune_output_dir():
    """创建临时微调输出目录用于测试。

    Yields:
        str: 临时微调输出目录路径
    """
    with tempfile.TemporaryDirectory() as temp_dir:
        yield temp_dir


@pytest.fixture
def mock_knowledge_base_bosch(temp_chroma_dir):
    """创建模拟知识库用于Bosch测试。

    使用临时ChromaDB目录，确保测试隔离。

    Returns:
        KnowledgeBase: 初始化的知识库实例
    """
    from app.rag.knowledge_base import KnowledgeBase

    kb = KnowledgeBase(
        persist_directory=temp_chroma_dir,
        collection_name="test_knowledge"
    )
    return kb


@pytest.fixture
def sample_process_features():
    """提供标准工艺特征数据用于测试。

    Returns:
        dict: 包含18种特征的标准特征字典
    """
    return {
        "time_x_rms": 0.1234,
        "time_x_peak": 0.2345,
        "time_x_peak_to_peak": 0.3456,
        "time_x_mean": 0.0012,
        "time_x_std": 0.0456,
        "time_x_skewness": 0.123,
        "time_x_kurtosis": 2.345,
        "time_y_rms": 0.0987,
        "time_y_peak": 0.1876,
        "time_y_peak_to_peak": 0.2765,
        "time_y_mean": -0.0008,
        "time_y_std": 0.0387,
        "time_y_skewness": -0.089,
        "time_y_kurtosis": 2.567,
        "time_z_rms": 0.0654,
        "time_z_peak": 0.1234,
        "time_z_peak_to_peak": 0.1876,
        "time_z_mean": 0.0003,
        "time_z_std": 0.0256,
        "time_z_skewness": 0.045,
        "time_z_kurtosis": 2.789,
        "freq_x_dominant_freq": 50.0,
        "freq_x_spectral_centroid": 120.5,
        "freq_x_spectral_bandwidth": 45.6,
        "freq_y_dominant_freq": 60.0,
        "freq_y_spectral_centroid": 135.2,
        "freq_y_spectral_bandwidth": 52.3,
        "freq_z_dominant_freq": 70.0,
        "freq_z_spectral_centroid": 150.8,
        "freq_z_spectral_bandwidth": 58.9,
        "cross_x_y_correlation": 0.765,
        "cross_x_z_correlation": 0.654,
        "cross_y_z_correlation": 0.543,
        "cross_x_energy_ratio": 0.456,
        "cross_y_energy_ratio": 0.345,
        "cross_z_energy_ratio": 0.199,
    }


@pytest.fixture
def sample_ground_truth_record():
    """提供标准ground truth记录用于测试。

    Returns:
        dict: 包含所有必需字段的ground truth记录
    """
    return {
        "experience_id": "exp-test-001",
        "task_id": "task-test-001",
        "process": "OP00",
        "parameters": {
            "cutting_speed": 150.0,
            "feed_rate": 0.2,
            "depth_of_cut": 1.5,
        },
        "metrics": {
            "vibration": 0.123,
            "temperature": 450.0,
            "force": 1200.0,
        },
        "validation_result": {
            "is_valid": True,
            "checks": [],
        },
        "metadata": {
            "machine": "M01",
            "timeframe": "Oct_2018",
        },
    }


@pytest.fixture
def sample_finetune_sample():
    """提供标准微调样本用于测试。

    Returns:
        dict: 包含instruction/input/output的微调样本
    """
    return {
        "instruction": "分析以下OP00工序的振动数据，判断是否存在异常并给出可能原因。",
        "input": "工序：OP00（端面铣削），机床：M01\n振动数据特征：\n- X轴 RMS: 0.1234g\n- Y轴 RMS: 0.0987g\n- Z轴 RMS: 0.0654g\n状态标注：正常",
        "output": "诊断结果：正常\n\n分析：三轴振动幅值均在正常范围内，建议继续维持当前加工参数。",
        "source": {
            "machine": "M01",
            "process": "OP00",
            "timeframe": "Oct_2018",
            "label": "good",
        },
        "category": "diagnosis",
    }
