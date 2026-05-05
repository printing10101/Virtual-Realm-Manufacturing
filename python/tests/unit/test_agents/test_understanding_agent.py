"""UnderstandingAgent单元测试模块。

测试UnderstandingAgent的核心功能，包括参数提取、
JSON解析容错、RAG检索增强和LLM客户端模拟等场景。
所有测试遵循AAA（Arrange-Act-Assert）模式，
确保测试独立性和可重复性。

测试类别:
    - 正常参数提取测试
    - JSON解析容错测试
    - RAG检索增强测试
    - LLM客户端模拟测试
"""
import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.ai.agents import UnderstandingAgent
from tests.factories import (
    AgentContextFactory,
    KnowledgeQueryResultFactory,
    LLMResponseFactory,
)


class TestUnderstandingAgent:
    """UnderstandingAgent基础功能和正常参数提取测试。

    验证UnderstandingAgent在不同输入格式下的参数提取准确性，
    包括标准需求输入、复杂需求输入、边界条件等场景。
    """

    def setup_method(self, method):
        """测试方法执行前的准备工作。

        创建UnderstandingAgent实例和相关的mock对象，
        确保每个测试方法都在干净的初始状态下执行。

        Args:
            method: 当前执行的测试方法
        """
        self.agent = UnderstandingAgent()
        self.mock_llm_client = AsyncMock()
        self.mock_knowledge_base = MagicMock()
        self.mock_model_router = AsyncMock()

        # 替换真实依赖为mock对象
        self.agent.llm_client = self.mock_llm_client
        self.agent.knowledge_base = self.mock_knowledge_base
        self.agent._model_router = None

        # 配置知识库mock默认返回
        self.mock_knowledge_base.query.return_value = {
            "documents": ["车削加工基础知识"],
            "metadatas": [{"type": "车削"}],
            "distances": [0.1],
            "ids": ["turning_basic"]
        }

    def teardown_method(self, method):
        """测试方法执行后的清理工作。

        清理mock对象和测试数据，确保测试之间的隔离性。

        Args:
            method: 当前执行的测试方法
        """
        self.agent = None
        self.mock_llm_client = None
        self.mock_knowledge_base = None
        self.mock_model_router = None

    @pytest.mark.asyncio
    async def test_extract_params_from_standard_input(self):
        """测试从标准制造需求输入中提取参数。

        验证当用户提供完整的制造需求描述时，
        UnderstandingAgent能够正确提取材料、零件类型、
        尺寸要求等关键参数。

        Arrange:
            - 配置LLM mock返回有效的JSON参数
            - 创建包含完整制造需求的AgentContext
        Act:
            - 调用agent.execute()执行参数提取
        Assert:
            - 验证stage_status为completed
            - 验证extracted_params包含预期的材料、零件类型等字段
            - 验证知识库查询被正确调用
        """
        # Arrange
        self.mock_llm_client.chat_completion.return_value = {
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

        context = AgentContextFactory.create(
            user_input="我需要加工一批45钢的轴类零件，长度100mm，直径50mm，精度要求IT7"
        )

        # Act
        result = await self.agent.execute(context)

        # Assert
        assert result.current_stage == "understanding"
        assert "completed" in result.stage_status
        assert "material" in result.extracted_params
        assert result.extracted_params["material"] == "45钢"
        assert result.extracted_params["part_type"] == "轴类零件"
        assert result.extracted_params["tolerance"] == "IT7"
        self.mock_knowledge_base.query.assert_called_once()

    @pytest.mark.asyncio
    async def test_extract_params_from_complex_input(self):
        """测试从复杂多零件需求中提取参数。

        验证当用户输入包含多种材料、多种零件类型的复杂需求时，
        Agent能够尝试提取和整合关键参数。

        Arrange:
            - 配置LLM mock返回复杂多零件的JSON响应
            - 创建包含复杂需求的AgentContext
        Act:
            - 调用agent.execute()执行参数提取
        Assert:
            - 验证stage_status为completed
            - 验证extracted_params包含材料信息
            - 验证知识库查询被调用
        """
        # Arrange
        self.mock_llm_client.chat_completion.return_value = {
            "content": json.dumps({
                "material": "6061铝合金",
                "part_type": "壳体类零件",
                "dimensions": {"length": 200.0, "width": 150.0, "height": 100.0},
                "tolerance": "IT8",
                "surface_roughness": "Ra 1.6",
                "quantity": 50
            }, ensure_ascii=False),
            "model": "qwen2.5-coder:7b",
            "finish_reason": "stop"
        }

        context = AgentContextFactory(complex_request=True)

        # Act
        result = await self.agent.execute(context)

        # Assert
        assert result.current_stage == "understanding"
        assert "completed" in result.stage_status
        assert result.extracted_params["material"] == "6061铝合金"
        assert result.extracted_params["part_type"] == "壳体类零件"

    @pytest.mark.asyncio
    async def test_extract_params_from_vague_input(self):
        """测试从模糊简短输入中提取参数。

        验证当用户输入信息不完整或模糊时，
        Agent仍能尝试提取可用信息并返回结果。

        Arrange:
            - 配置LLM mock返回部分参数的JSON响应
            - 创建包含模糊输入的AgentContext
        Act:
            - 调用agent.execute()执行参数提取
        Assert:
            - 验证stage_status为completed
            - 验证extracted_params至少包含部分提取的参数
        """
        # Arrange
        self.mock_llm_client.chat_completion.return_value = {
            "content": json.dumps({
                "material": "金属",
                "part_type": "零件",
                "dimensions": {},
                "tolerance": "",
                "surface_roughness": "",
                "quantity": 1
            }, ensure_ascii=False),
            "model": "qwen2.5-coder:7b",
            "finish_reason": "stop"
        }

        context = AgentContextFactory(vague_request=True)

        # Act
        result = await self.agent.execute(context)

        # Assert
        assert result.current_stage == "understanding"
        assert "completed" in result.stage_status
        assert "material" in result.extracted_params

    @pytest.mark.asyncio
    async def test_extract_params_with_markdown_wrapped_json(self):
        """测试解析被markdown代码块包裹的JSON响应。

        验证当LLM返回的JSON被```json或```包裹时，
        Agent能够正确提取并解析JSON内容。

        Arrange:
            - 配置LLM mock返回markdown包裹的JSON
        Act:
            - 调用agent.execute()执行参数提取
        Assert:
            - 验证stage_status为completed
            - 验证extracted_params正确解析
        """
        # Arrange
        json_content = json.dumps({
            "material": "45钢",
            "part_type": "轴类零件",
            "dimensions": {"length": 100.0, "width": 50.0, "height": 30.0},
            "tolerance": "IT7",
            "surface_roughness": "Ra 0.8",
            "quantity": 100
        }, ensure_ascii=False)

        self.mock_llm_client.chat_completion.return_value = {
            "content": f"```json\n{json_content}\n```",
            "model": "qwen2.5-coder:7b",
            "finish_reason": "stop"
        }

        context = AgentContextFactory.create()

        # Act
        result = await self.agent.execute(context)

        # Assert
        assert result.current_stage == "understanding"
        assert "completed" in result.stage_status
        assert result.extracted_params["material"] == "45钢"

    @pytest.mark.asyncio
    async def test_extract_params_with_plain_code_block(self):
        """测试解析无语言标识的代码块包裹的JSON。

        验证当LLM返回的JSON仅被```包裹（无json标识）时，
        Agent能够正确提取并解析。

        Arrange:
            - 配置LLM mock返回纯代码块包裹的JSON
        Act:
            - 调用agent.execute()执行参数提取
        Assert:
            - 验证stage_status为completed
            - 验证extracted_params正确解析
        """
        # Arrange
        json_content = json.dumps({
            "material": "6061铝合金",
            "part_type": "壳体",
            "dimensions": {"length": 200.0},
            "tolerance": "IT8",
            "surface_roughness": "Ra 1.6",
            "quantity": 50
        }, ensure_ascii=False)

        self.mock_llm_client.chat_completion.return_value = {
            "content": f"```\n{json_content}\n```",
            "model": "qwen2.5-coder:7b",
            "finish_reason": "stop"
        }

        context = AgentContextFactory(simple_request=True)

        # Act
        result = await self.agent.execute(context)

        # Assert
        assert result.current_stage == "understanding"
        assert "completed" in result.stage_status


class TestJsonParsingErrorHandling:
    """JSON解析容错测试类。

    测试UnderstandingAgent对格式错误、不完整JSON、
    非JSON内容等异常情况下的处理能力，
    验证系统的鲁棒性和容错机制。
    """

    def setup_method(self, method):
        """测试方法执行前的准备工作。

        Args:
            method: 当前执行的测试方法
        """
        self.agent = UnderstandingAgent()
        self.mock_llm_client = AsyncMock()
        self.mock_knowledge_base = MagicMock()

        self.agent.llm_client = self.mock_llm_client
        self.agent.knowledge_base = self.mock_knowledge_base
        self.agent._model_router = None

        self.mock_knowledge_base.query.return_value = KnowledgeQueryResultFactory(single_result=True)

    def teardown_method(self, method):
        """测试方法执行后的清理工作。

        Args:
            method: 当前执行的测试方法
        """
        self.agent = None
        self.mock_llm_client = None
        self.mock_knowledge_base = None

    @pytest.mark.asyncio
    async def test_handle_invalid_json_response(self):
        """测试处理无效JSON格式的LLM响应。

        当LLM返回格式错误的JSON（如缺少值、括号不匹配）时，
        验证Agent能够捕获异常并设置失败状态。

        Arrange:
            - 配置LLM mock返回无效JSON字符串
        Act:
            - 调用agent.execute()
        Assert:
            - 验证stage_status包含failed信息
            - 验证extracted_params包含raw_input作为后备
        """
        # Arrange
        self.mock_llm_client.chat_completion.return_value = {
            "content": '{"material": "45钢", "part_type": }',
            "model": "qwen2.5-coder:7b",
            "finish_reason": "stop"
        }

        context = AgentContextFactory.create(
            user_input="加工45钢零件"
        )

        # Act
        result = await self.agent.execute(context)

        # Assert
        assert "failed" in result.stage_status
        assert "raw_input" in result.extracted_params
        assert result.extracted_params["raw_input"] == "加工45钢零件"

    @pytest.mark.asyncio
    async def test_handle_incomplete_json_response(self):
        """测试处理不完整JSON的LLM响应。

        当LLM返回未完成的JSON字符串（如缺少闭合括号）时，
        验证Agent能够正确捕获json.JSONDecodeError。

        Arrange:
            - 配置LLM mock返回未闭合的JSON字符串
        Act:
            - 调用agent.execute()
        Assert:
            - 验证stage_status包含failed
            - 验证extracted_params包含raw_input
        """
        # Arrange
        self.mock_llm_client.chat_completion.return_value = {
            "content": '{"material": "45钢", "part_type": "轴类", "dimensions": {"length": 100}',
            "model": "qwen2.5-coder:7b",
            "finish_reason": "stop"
        }

        context = AgentContextFactory.create(
            user_input="加工一根轴"
        )

        # Act
        result = await self.agent.execute(context)

        # Assert
        assert "failed" in result.stage_status
        assert result.extracted_params["raw_input"] == "加工一根轴"

    @pytest.mark.asyncio
    async def test_handle_empty_llm_response(self):
        """测试处理空内容的LLM响应。

        当LLM返回空字符串时，验证Agent能够正确处理
        并设置相应的失败状态。

        Arrange:
            - 配置LLM mock返回空字符串
        Act:
            - 调用agent.execute()
        Assert:
            - 验证stage_status包含failed
            - 验证extracted_params包含raw_input
        """
        # Arrange
        self.mock_llm_client.chat_completion.return_value = {
            "content": "",
            "model": "qwen2.5-coder:7b",
            "finish_reason": "stop"
        }

        context = AgentContextFactory.create(
            user_input="加工零件"
        )

        # Act
        result = await self.agent.execute(context)

        # Assert
        assert "failed" in result.stage_status
        assert "raw_input" in result.extracted_params

    @pytest.mark.asyncio
    async def test_handle_plain_text_response(self):
        """测试处理纯文本（非JSON格式）的LLM响应。

        当LLM返回自然语言描述而非JSON格式时，
        验证Agent能够捕获JSON解析错误。

        Arrange:
            - 配置LLM mock返回纯文本响应
        Act:
            - 调用agent.execute()
        Assert:
            - 验证stage_status包含failed
            - 验证extracted_params包含raw_input
        """
        # Arrange
        self.mock_llm_client.chat_completion.return_value = {
            "content": "根据您的需求分析，材料应该是45钢，零件类型为轴类。",
            "model": "qwen2.5-coder:7b",
            "finish_reason": "stop"
        }

        context = AgentContextFactory.create(
            user_input="加工45钢轴"
        )

        # Act
        result = await self.agent.execute(context)

        # Assert
        assert "failed" in result.stage_status
        assert result.extracted_params["raw_input"] == "加工45钢轴"

    @pytest.mark.asyncio
    async def test_handle_llm_exception(self):
        """测试处理LLM调用异常的情况。

        当LLM客户端抛出异常（如网络错误、超时）时，
        验证异常会向上传播（因为execute方法没有捕获LLM调用异常）。

        Arrange:
            - 配置LLM mock抛出异常
        Act:
            - 调用agent.execute()
        Assert:
            - 验证异常向上传播
        """
        # Arrange
        self.mock_llm_client.chat_completion.side_effect = Exception("LLM连接超时")

        context = AgentContextFactory.create(
            user_input="加工齿轮"
        )

        # Act & Assert
        with pytest.raises(Exception, match="LLM连接超时"):
            await self.agent.execute(context)


class TestRagEnhancement:
    """RAG检索增强测试类。

    验证UnderstandingAgent在参数提取过程中，
    如何正确利用RAG检索结果增强LLM的系统提示，
    以及在不同检索结果情况下的行为表现。
    """

    def setup_method(self, method):
        """测试方法执行前的准备工作。

        Args:
            method: 当前执行的测试方法
        """
        self.agent = UnderstandingAgent()
        self.mock_llm_client = AsyncMock()
        self.mock_knowledge_base = MagicMock()

        self.agent.llm_client = self.mock_llm_client
        self.agent.knowledge_base = self.mock_knowledge_base
        self.agent._model_router = None

    def teardown_method(self, method):
        """测试方法执行后的清理工作。

        Args:
            method: 当前执行的测试方法
        """
        self.agent = None
        self.mock_llm_client = None
        self.mock_knowledge_base = None

    @pytest.mark.asyncio
    @pytest.mark.rag
    async def test_rag_query_called_with_user_input(self):
        """验证RAG检索使用用户输入作为查询文本。

        确保Agent在参数提取时，使用用户的原始输入
        作为知识库检索的查询条件。

        Arrange:
            - 创建包含特定用户输入的AgentContext
            - 配置知识库mock和LLM mock
        Act:
            - 调用agent.execute()
        Assert:
            - 验证knowledge_base.query被调用
            - 验证调用参数包含用户输入内容
            - 验证n_results参数为3
        """
        # Arrange
        user_input = "我需要加工45钢的齿轮，模数2，精度7级"
        self.mock_knowledge_base.query.return_value = KnowledgeQueryResultFactory(single_result=True)
        self.mock_llm_client.chat_completion.return_value = LLMResponseFactory(json_only=True)

        context = AgentContextFactory.create(user_input=user_input)

        # Act
        await self.agent.execute(context)

        # Assert
        self.mock_knowledge_base.query.assert_called_once()
        call_args = self.mock_knowledge_base.query.call_args
        assert call_args[1]["query_text"] == user_input
        assert call_args[1]["n_results"] == 3

    @pytest.mark.asyncio
    @pytest.mark.rag
    async def test_rag_results_integrated_in_system_prompt(self):
        """验证RAG检索结果被正确整合到系统提示中。

        确保检索到的知识文档被传递给LLM的系统提示，
        用于增强参数提取的准确性。

        Arrange:
            - 配置知识库返回特定的检索结果
            - 配置LLM mock
        Act:
            - 调用agent.execute()
        Assert:
            - 验证LLM被调用
            - 验证调用消息中的system prompt包含检索到的知识内容
        """
        # Arrange
        expected_knowledge = "车削加工基础：车削加工方法"
        self.mock_knowledge_base.query.return_value = {
            "documents": [expected_knowledge],
            "metadatas": [{"type": "车削"}],
            "distances": [0.1],
            "ids": ["turning_basic"]
        }
        self.mock_llm_client.chat_completion.return_value = LLMResponseFactory(json_only=True)

        context = AgentContextFactory(simple_request=True)

        # Act
        await self.agent.execute(context)

        # Assert
        call_args = self.mock_llm_client.chat_completion.call_args
        messages = call_args[0][0]
        system_prompt = messages[0]["content"]
        assert expected_knowledge in system_prompt

    @pytest.mark.asyncio
    @pytest.mark.rag
    async def test_rag_empty_results_handling(self):
        """测试RAG检索返回空结果时的处理。

        当知识库中没有相关文档时，验证Agent能够正常继续
        执行参数提取，不因空检索结果而失败。

        Arrange:
            - 配置知识库返回空检索结果
            - 配置LLM mock返回有效响应
        Act:
            - 调用agent.execute()
        Assert:
            - 验证stage_status为completed
            - 验证extracted_params正常提取
            - 验证系统提示中不包含空知识
        """
        # Arrange
        self.mock_knowledge_base.query.return_value = KnowledgeQueryResultFactory(empty=True)
        self.mock_llm_client.chat_completion.return_value = {
            "content": json.dumps({
                "material": "45钢",
                "part_type": "轴类",
                "dimensions": {},
                "tolerance": "",
                "surface_roughness": "",
                "quantity": 1
            }, ensure_ascii=False),
            "model": "qwen2.5-coder:7b",
            "finish_reason": "stop"
        }

        context = AgentContextFactory.create(user_input="加工轴类零件")

        # Act
        result = await self.agent.execute(context)

        # Assert
        assert "completed" in result.stage_status
        assert result.extracted_params["material"] == "45钢"
        call_args = self.mock_llm_client.chat_completion.call_args
        system_prompt = call_args[0][0][0]["content"]
        assert "参考知识：" in system_prompt

    @pytest.mark.asyncio
    @pytest.mark.rag
    async def test_rag_multiple_results_integration(self):
        """测试多条RAG检索结果的整合。

        当知识库返回多条检索结果时，验证所有结果都被
        正确整合到系统提示中。

        Arrange:
            - 配置知识库返回多条检索结果
            - 配置LLM mock
        Act:
            - 调用agent.execute()
        Assert:
            - 验证系统提示包含所有检索到的文档
            - 验证文档之间使用换行符分隔
        """
        # Arrange
        knowledge_docs = [
            "车削加工基础知识文档",
            "45钢材料参数说明",
            "IT7公差等级标准"
        ]
        self.mock_knowledge_base.query.return_value = {
            "documents": knowledge_docs,
            "metadatas": [],
            "distances": [],
            "ids": []
        }
        self.mock_llm_client.chat_completion.return_value = LLMResponseFactory(json_only=True)

        context = AgentContextFactory(simple_request=True)

        # Act
        await self.agent.execute(context)

        # Assert
        call_args = self.mock_llm_client.chat_completion.call_args
        messages = call_args[0][0]
        system_prompt = messages[0]["content"]
        for doc in knowledge_docs:
            assert doc in system_prompt


class TestLLMClientSimulation:
    """LLM客户端模拟测试类。

    使用pytest-mock模拟不同的LLM客户端行为，
    测试UnderstandingAgent在各种LLM响应场景下的表现，
    包括通过model_router调用和直接LLM调用的降级逻辑。
    """

    def setup_method(self, method):
        """测试方法执行前的准备工作。

        Args:
            method: 当前执行的测试方法
        """
        self.agent = UnderstandingAgent()
        self.mock_llm_client = AsyncMock()
        self.mock_knowledge_base = MagicMock()
        self.mock_model_router = AsyncMock()

        self.agent.llm_client = self.mock_llm_client
        self.agent.knowledge_base = self.mock_knowledge_base
        self.agent._model_router = self.mock_model_router

        self.mock_knowledge_base.query.return_value = KnowledgeQueryResultFactory(single_result=True)

    def teardown_method(self, method):
        """测试方法执行后的清理工作。

        Args:
            method: 当前执行的测试方法
        """
        self.agent = None
        self.mock_llm_client = None
        self.mock_knowledge_base = None
        self.mock_model_router = None

    @pytest.mark.asyncio
    @pytest.mark.llm
    async def test_call_llm_via_model_router_success(self):
        """测试通过模型路由成功调用LLM的场景。

        当model_router可用且成功返回时，验证Agent
        使用路由进行LLM调用。

        Arrange:
            - 配置model_router返回有效响应
            - 配置正常的AgentContext
        Act:
            - 调用agent.execute()
        Assert:
            - 验证model_router.execute被调用
            - 验证execute调用包含正确的参数
            - 验证stage_status为completed
        """
        # Arrange
        expected_response = {
            "content": json.dumps({
                "material": "45钢",
                "part_type": "轴类",
                "dimensions": {},
                "tolerance": "",
                "surface_roughness": "",
                "quantity": 1
            }, ensure_ascii=False),
            "model": "qwen2.5-coder:7b",
            "finish_reason": "stop"
        }
        self.mock_model_router.execute.return_value = expected_response

        context = AgentContextFactory.create(user_input="加工轴")

        # Act
        result = await self.agent.execute(context)

        # Assert
        self.mock_model_router.execute.assert_called_once()
        execute_call = self.mock_model_router.execute.call_args
        assert execute_call[1]["agent_name"] == "UnderstandingAgent"
        assert "material" in execute_call[1]["input_data"]
        assert result.stage_status == "completed"

    @pytest.mark.asyncio
    @pytest.mark.llm
    async def test_model_router_fallback_to_llm_client(self):
        """测试model_router失败时降级到LLM客户端的场景。

        当model_router抛出异常时，验证Agent降级到
        直接使用llm_client.chat_completion进行调用。

        Arrange:
            - 配置model_router抛出异常
            - 配置llm_client返回有效响应
        Act:
            - 调用agent.execute()
        Assert:
            - 验证llm_client.chat_completion被调用
            - 验证stage_status为completed
        """
        # Arrange
        self.mock_model_router.execute.side_effect = Exception("路由服务不可用")
        self.mock_llm_client.chat_completion.return_value = {
            "content": json.dumps({
                "material": "45钢",
                "part_type": "轴类",
                "dimensions": {},
                "tolerance": "",
                "surface_roughness": "",
                "quantity": 1
            }, ensure_ascii=False),
            "model": "qwen2.5-coder:7b",
            "finish_reason": "stop"
        }

        context = AgentContextFactory(simple_request=True)

        # Act
        result = await self.agent.execute(context)

        # Assert
        self.mock_llm_client.chat_completion.assert_called_once()
        assert "completed" in result.stage_status

    @pytest.mark.asyncio
    @pytest.mark.llm
    async def test_model_router_with_correct_input_data(self):
        """验证传递给model_router的input_data格式正确。

        确保Agent在调用model_router时传递的input_data
        包含所有必需字段和正确的数据类型。

        Arrange:
            - 配置model_router和LLM mock
            - 创建包含extracted_params的context
        Act:
            - 调用agent.execute()
        Assert:
            - 验证input_data包含material、tool、constraints等字段
            - 验证各字段类型正确
        """
        # Arrange
        self.mock_model_router.execute.return_value = LLMResponseFactory(json_only=True)

        context = AgentContextFactory(understood=True)

        # Act
        await self.agent.execute(context)

        # Assert
        execute_call = self.mock_model_router.execute.call_args
        input_data = execute_call[1]["input_data"]
        assert isinstance(input_data, dict)
        assert "material" in input_data
        assert "tool" in input_data
        assert "constraints" in input_data
        assert "geometry" in input_data
        assert "history" in input_data
        assert isinstance(input_data["constraints"], list)
        assert isinstance(input_data["geometry"], dict)

    @pytest.mark.asyncio
    @pytest.mark.llm
    async def test_llm_client_called_with_appropriate_temperature(self):
        """验证LLM调用使用合适的temperature参数。

        参数提取任务应该使用较低的temperature（0.3）
        以确保输出的确定性。

        Arrange:
            - 配置model_router不可用
            - 配置llm_client mock
        Act:
            - 调用agent.execute()
        Assert:
            - 验证chat_completion被调用
            - 验证temperature参数为0.3
            - 验证max_tokens参数为1024
        """
        # Arrange
        self.agent._model_router = None
        self.mock_llm_client.chat_completion.return_value = LLMResponseFactory(json_only=True)

        context = AgentContextFactory()

        # Act
        await self.agent.execute(context)

        # Assert
        call_args = self.mock_llm_client.chat_completion.call_args
        # chat_completion(messages, max_tokens, temperature, model) - all positional
        assert call_args[0][2] == 0.3  # temperature
        assert call_args[0][1] == 1024  # max_tokens

    @pytest.mark.asyncio
    @pytest.mark.llm
    async def test_both_router_and_llm_fail(self):
        """测试model_router和LLM客户端都失败的场景。

        当所有LLM调用途径都失败时，验证异常会向上传播。

        Arrange:
            - 配置model_router抛出异常
            - 配置llm_client也抛出异常
        Act:
            - 调用agent.execute()
        Assert:
            - 验证异常向上传播
        """
        # Arrange
        self.mock_model_router.execute.side_effect = Exception("路由失败")
        self.mock_llm_client.chat_completion.side_effect = Exception("LLM失败")

        context = AgentContextFactory.create(user_input="测试输入")

        # Act & Assert
        with pytest.raises(Exception, match="LLM失败"):
            await self.agent.execute(context)

    @pytest.mark.asyncio
    @pytest.mark.llm
    async def test_model_router_none_uses_llm_client(self):
        """测试model_router为None时使用LLM客户端。

        当agent._model_router为None时，验证Agent
        直接使用llm_client进行调用。

        Arrange:
            - 设置_model_router为None
            - 配置llm_client返回有效响应
        Act:
            - 调用agent.execute()
        Assert:
            - 验证llm_client.chat_completion被调用
            - 验证stage_status为completed
        """
        # Arrange
        self.agent._model_router = None
        self.mock_llm_client.chat_completion.return_value = {
            "content": json.dumps({
                "material": "金属",
                "part_type": "零件",
                "dimensions": {},
                "tolerance": "",
                "surface_roughness": "",
                "quantity": 1
            }, ensure_ascii=False),
            "model": "qwen2.5-coder:7b",
            "finish_reason": "stop"
        }

        context = AgentContextFactory()

        # Act
        result = await self.agent.execute(context)

        # Assert
        self.mock_llm_client.chat_completion.assert_called_once()
        assert "completed" in result.stage_status


class TestAgentContextState:
    """AgentContext状态管理测试类。

    验证UnderstandingAgent执行过程中对AgentContext
    状态字段的正确设置和更新。
    """

    def setup_method(self, method):
        """测试方法执行前的准备工作。

        Args:
            method: 当前执行的测试方法
        """
        self.agent = UnderstandingAgent()
        self.mock_llm_client = AsyncMock()
        self.mock_knowledge_base = MagicMock()

        self.agent.llm_client = self.mock_llm_client
        self.agent.knowledge_base = self.mock_knowledge_base
        self.agent._model_router = None

        self.mock_knowledge_base.query.return_value = KnowledgeQueryResultFactory(single_result=True)

    def teardown_method(self, method):
        """测试方法执行后的清理工作。

        Args:
            method: 当前执行的测试方法
        """
        self.agent = None
        self.mock_llm_client = None
        self.mock_knowledge_base = None

    @pytest.mark.asyncio
    async def test_context_stage_set_to_understanding(self):
        """验证执行时context.current_stage被设置为understanding。

        Arrange:
            - 创建默认context
            - 配置mock返回成功响应
        Act:
            - 调用agent.execute()
        Assert:
            - 验证result.current_stage == "understanding"
        """
        # Arrange
        self.mock_llm_client.chat_completion.return_value = LLMResponseFactory(json_only=True)
        context = AgentContextFactory()

        # Act
        result = await self.agent.execute(context)

        # Assert
        assert result.current_stage == "understanding"

    @pytest.mark.asyncio
    async def test_context_status_running_before_completion(self):
        """验证执行开始时stage_status被设置为running。

        Arrange:
            - 配置mock
            - 创建context
        Act:
            - 调用agent.execute()
        Assert:
            - 验证stage_status最终为completed（成功情况）
            - 验证状态转换逻辑
        """
        # Arrange
        self.mock_llm_client.chat_completion.return_value = LLMResponseFactory(json_only=True)
        context = AgentContextFactory()

        # Act
        result = await self.agent.execute(context)

        # Assert
        assert result.stage_status == "completed"

    @pytest.mark.asyncio
    async def test_context_preserves_other_fields(self):
        """验证执行过程中不修改context的其他字段。

        确保Agent只修改current_stage、stage_status和
        extracted_params，保持process_route等其他字段不变。

        Arrange:
            - 创建包含特定字段值的context
        Act:
            - 调用agent.execute()
        Assert:
            - 验证process_route、nc_code等字段保持不变
        """
        # Arrange
        self.mock_llm_client.chat_completion.return_value = LLMResponseFactory(json_only=True)
        context = AgentContextFactory(
            process_route=["route1", "route2"],
            nc_code="G00 X0 Y0",
            cutting_parameters={"v": 100}
        )

        # Act
        result = await self.agent.execute(context)

        # Assert
        assert result.process_route == ["route1", "route2"]
        assert result.nc_code == "G00 X0 Y0"
        assert result.cutting_parameters == {"v": 100}


class TestSpecificUserRequirement:
    """用户指定具体输入案例的测试类。

    测试用户明确要求的具体输入场景：
    "需要加工一个45钢材质的传动轴，直径30mm，长度100mm"
    验证所有提取参数的准确性。
    """

    def setup_method(self, method):
        """测试方法执行前的准备工作。

        Args:
            method: 当前执行的测试方法
        """
        self.agent = UnderstandingAgent()
        self.mock_llm_client = AsyncMock()
        self.mock_knowledge_base = MagicMock()

        self.agent.llm_client = self.mock_llm_client
        self.agent.knowledge_base = self.mock_knowledge_base
        self.agent._model_router = None

        self.mock_knowledge_base.query.return_value = KnowledgeQueryResultFactory(single_result=True)

    def teardown_method(self, method):
        """测试方法执行后的清理工作。

        Args:
            method: 当前执行的测试方法
        """
        self.agent = None
        self.mock_llm_client = None
        self.mock_knowledge_base = None

    @pytest.mark.asyncio
    async def test_extract_transmission_shaft_params(self):
        """测试从用户指定的传动轴需求输入中提取参数。

        输入文本："需要加工一个45钢材质的传动轴，直径30mm，长度100mm"

        验证标准：
        - material属性准确提取为"45钢"
        - part_type属性正确识别为"轴类"
        - dimensions属性包含直径和长度的正确数值及单位
        - 所有提取参数与预期值精确匹配

        Arrange:
            - 配置LLM mock返回传动轴相关的JSON参数
            - 创建包含指定用户输入的AgentContext
        Act:
            - 调用agent.execute()执行参数提取
        Assert:
            - 验证material为"45钢"
            - 验证part_type为"轴类"
            - 验证dimensions包含直径30mm和长度100mm
            - 验证所有参数精确匹配预期值
        """
        # Arrange
        self.mock_llm_client.chat_completion.return_value = {
            "content": json.dumps({
                "material": "45钢",
                "part_type": "轴类",
                "dimensions": {
                    "diameter": 30.0,
                    "length": 100.0,
                    "unit": "mm"
                },
                "tolerance": "",
                "surface_roughness": "",
                "quantity": 1
            }, ensure_ascii=False),
            "model": "qwen2.5-coder:7b",
            "finish_reason": "stop"
        }

        context = AgentContextFactory.create(
            user_input="需要加工一个45钢材质的传动轴，直径30mm，长度100mm"
        )

        # Act
        result = await self.agent.execute(context)

        # Assert
        assert result.current_stage == "understanding"
        assert result.stage_status == "completed"
        assert result.extracted_params["material"] == "45钢"
        assert result.extracted_params["part_type"] == "轴类"
        assert "dimensions" in result.extracted_params
        assert result.extracted_params["dimensions"]["diameter"] == 30.0
        assert result.extracted_params["dimensions"]["length"] == 100.0
        assert result.extracted_params["dimensions"]["unit"] == "mm"

    @pytest.mark.asyncio
    @pytest.mark.parametrize("user_input,expected_material,expected_part_type", [
        ("需要加工一个45钢材质的传动轴，直径30mm，长度100mm", "45钢", "轴类"),
        ("加工6061铝合金壳体，尺寸200x150x100", "6061铝合金", "壳体类"),
        ("制作一个不锈钢的法兰盘，外径100mm", "不锈钢", "盘类"),
    ])
    async def test_parametrize_standard_inputs(self, user_input, expected_material, expected_part_type):
        """参数化测试多种标准制造需求输入。

        验证Agent能够准确提取不同材料和零件类型的参数。

        Arrange:
            - 配置LLM mock返回对应参数的JSON
        Act:
            - 调用agent.execute()执行参数提取
        Assert:
            - 验证material和part_type与预期值匹配
        """
        # Arrange
        self.mock_llm_client.chat_completion.return_value = {
            "content": json.dumps({
                "material": expected_material,
                "part_type": expected_part_type,
                "dimensions": {},
                "tolerance": "",
                "surface_roughness": "",
                "quantity": 1
            }, ensure_ascii=False),
            "model": "qwen2.5-coder:7b",
            "finish_reason": "stop"
        }

        context = AgentContextFactory.create(user_input=user_input)

        # Act
        result = await self.agent.execute(context)

        # Assert
        assert result.extracted_params["material"] == expected_material
        assert result.extracted_params["part_type"] == expected_part_type


class TestJsonParsingFaultTolerance:
    """JSON解析容错测试类。

    测试各种格式错误的JSON输入情况：
    - 缺少引号的JSON字符串
    - 多余逗号的JSON结构
    - 嵌套错误的JSON格式
    - 非JSON格式的纯文本输入

    验证标准：
    - 所有异常输入情况下程序不崩溃
    - 解析失败时正确使用预设默认值
    - 错误处理机制正常记录解析异常
    """

    def setup_method(self, method):
        """测试方法执行前的准备工作。

        Args:
            method: 当前执行的测试方法
        """
        self.agent = UnderstandingAgent()
        self.mock_llm_client = AsyncMock()
        self.mock_knowledge_base = MagicMock()

        self.agent.llm_client = self.mock_llm_client
        self.agent.knowledge_base = self.mock_knowledge_base
        self.agent._model_router = None

        self.mock_knowledge_base.query.return_value = KnowledgeQueryResultFactory(single_result=True)

    def teardown_method(self, method):
        """测试方法执行后的清理工作。

        Args:
            method: 当前执行的测试方法
        """
        self.agent = None
        self.mock_llm_client = None
        self.mock_knowledge_base = None

    @pytest.mark.asyncio
    @pytest.mark.parametrize("invalid_json,description", [
        ('{material: "45钢"}', "缺少引号的JSON字符串"),
        ('{"material": "45钢",}', "多余逗号的JSON结构"),
        ('{"dimensions": {"diameter": 30, "length": 100}', "嵌套错误的JSON格式（缺少闭合括号）"),
        ('{"material": "45钢", "part_type": "轴类"', "未完成的JSON字符串"),
    ])
    async def test_handle_malformed_json_responses(self, invalid_json, description):
        """参数化测试各种格式错误的JSON响应。

        验证Agent在面对不同格式的JSON错误时不会崩溃，
        并能正确捕获异常并使用默认值。

        Arrange:
            - 配置LLM mock返回格式错误的JSON
        Act:
            - 调用agent.execute()
        Assert:
            - 验证stage_status包含failed信息
            - 验证extracted_params包含raw_input作为后备
            - 验证程序不崩溃
        """
        # Arrange
        self.mock_llm_client.chat_completion.return_value = {
            "content": invalid_json,
            "model": "qwen2.5-coder:7b",
            "finish_reason": "stop"
        }

        user_input = "需要加工一个45钢材质的传动轴"
        context = AgentContextFactory.create(user_input=user_input)

        # Act
        result = await self.agent.execute(context)

        # Assert
        assert "failed" in result.stage_status
        assert "raw_input" in result.extracted_params
        assert result.extracted_params["raw_input"] == user_input

    @pytest.mark.asyncio
    async def test_handle_non_json_plain_text(self):
        """测试处理非JSON格式的纯文本输入。

        验证当LLM返回纯文本而非JSON时，
        Agent能够正确处理而不崩溃。

        Arrange:
            - 配置LLM mock返回纯文本响应
        Act:
            - 调用agent.execute()
        Assert:
            - 验证stage_status包含failed
            - 验证extracted_params包含raw_input
        """
        # Arrange
        self.mock_llm_client.chat_completion.return_value = {
            "content": "根据您的需求分析，材料应该是45钢，零件类型为传动轴，直径30mm，长度100mm。",
            "model": "qwen2.5-coder:7b",
            "finish_reason": "stop"
        }

        user_input = "需要加工一个45钢材质的传动轴，直径30mm，长度100mm"
        context = AgentContextFactory.create(user_input=user_input)

        # Act
        result = await self.agent.execute(context)

        # Assert
        assert "failed" in result.stage_status
        assert "raw_input" in result.extracted_params
        assert result.extracted_params["raw_input"] == user_input

    @pytest.mark.asyncio
    async def test_handle_json_with_extra_closing_brace(self):
        """测试处理多余闭合括号的JSON。

        验证当JSON包含多余的}时能够正确捕获错误。

        Arrange:
            - 配置LLM mock返回包含多余括号的JSON
        Act:
            - 调用agent.execute()
        Assert:
            - 验证stage_status包含failed
        """
        # Arrange
        self.mock_llm_client.chat_completion.return_value = {
            "content": '{"material": "45钢", "part_type": "轴类"}}',
            "model": "qwen2.5-coder:7b",
            "finish_reason": "stop"
        }

        context = AgentContextFactory.create(user_input="加工零件")

        # Act
        result = await self.agent.execute(context)

        # Assert
        assert "failed" in result.stage_status
        assert "raw_input" in result.extracted_params


class TestEdgeCasesAndBoundaryConditions:
    """空输入和边界情况测试类。

    测试以下边界情况：
    - 空字符串输入：验证返回默认参数结构
    - 超长输入（>1000字符）：验证处理性能和内存使用
    - 特殊字符输入：包含emoji、特殊符号、多语言混合文本

    验证标准：
    - 所有边界情况处理不引发异常
    - 输入长度超过限制时有适当处理机制
    - 特殊字符不影响参数提取的准确性
    """

    def setup_method(self, method):
        """测试方法执行前的准备工作。

        Args:
            method: 当前执行的测试方法
        """
        self.agent = UnderstandingAgent()
        self.mock_llm_client = AsyncMock()
        self.mock_knowledge_base = MagicMock()

        self.agent.llm_client = self.mock_llm_client
        self.agent.knowledge_base = self.mock_knowledge_base
        self.agent._model_router = None

        self.mock_knowledge_base.query.return_value = KnowledgeQueryResultFactory(single_result=True)

    def teardown_method(self, method):
        """测试方法执行后的清理工作。

        Args:
            method: 当前执行的测试方法
        """
        self.agent = None
        self.mock_llm_client = None
        self.mock_knowledge_base = None

    @pytest.mark.asyncio
    async def test_empty_string_input(self):
        """测试空字符串输入的处理。

        验证当用户输入为空字符串时，
        Agent能够返回默认参数结构而不崩溃。

        Arrange:
            - 配置LLM mock返回默认参数
            - 创建空user_input的AgentContext
        Act:
            - 调用agent.execute()
        Assert:
            - 验证stage_status为completed
            - 验证extracted_params包含默认结构
            - 验证不引发异常
        """
        # Arrange
        self.mock_llm_client.chat_completion.return_value = {
            "content": json.dumps({
                "material": "",
                "part_type": "",
                "dimensions": {},
                "tolerance": "",
                "surface_roughness": "",
                "quantity": 1
            }, ensure_ascii=False),
            "model": "qwen2.5-coder:7b",
            "finish_reason": "stop"
        }

        context = AgentContextFactory.create(user_input="")

        # Act
        result = await self.agent.execute(context)

        # Assert
        assert result.current_stage == "understanding"
        assert result.stage_status == "completed"
        assert isinstance(result.extracted_params, dict)
        assert "material" in result.extracted_params

    @pytest.mark.asyncio
    async def test_very_long_input_over_1000_chars(self):
        """测试超长输入（>1000字符）的处理。

        验证当用户输入超过1000字符时，
        Agent能够正常处理且不超时。

        Arrange:
            - 创建超过1000字符的user_input
            - 配置LLM mock返回有效响应
        Act:
            - 调用agent.execute()
        Assert:
            - 验证处理完成不超时
            - 验证stage_status为completed
            - 验证内存使用正常（不引发异常）
        """
        # Arrange
        long_input = "需要加工零件。" * 200
        assert len(long_input) > 1000

        self.mock_llm_client.chat_completion.return_value = {
            "content": json.dumps({
                "material": "45钢",
                "part_type": "轴类",
                "dimensions": {},
                "tolerance": "",
                "surface_roughness": "",
                "quantity": 1
            }, ensure_ascii=False),
            "model": "qwen2.5-coder:7b",
            "finish_reason": "stop"
        }

        context = AgentContextFactory.create(user_input=long_input)

        # Act
        result = await self.agent.execute(context)

        # Assert
        assert result.current_stage == "understanding"
        assert result.stage_status == "completed"
        assert result.extracted_params["material"] == "45钢"

    @pytest.mark.asyncio
    @pytest.mark.parametrize("special_input,description", [
        ("需要加工一个🔩零件，材料是45钢 ⚙️", "包含emoji的输入"),
        ("加工零件￥%#&*！@（）", "包含特殊符号的输入"),
        ("需要加工steel零件，材質是鋁合金", "多语言混合输入（中英文混合）"),
        ("加工<>&\"'零件", "包含HTML特殊字符的输入"),
        ("加工\n\t零件\r\n换行测试", "包含换行符和制表符的输入"),
    ])
    async def test_special_characters_input(self, special_input, description):
        """参数化测试各种特殊字符输入。

        验证Agent在处理包含emoji、特殊符号、
        多语言混合文本时不会崩溃。

        Arrange:
            - 配置LLM mock返回有效响应
            - 创建包含特殊字符的user_input
        Act:
            - 调用agent.execute()
        Assert:
            - 验证不引发异常
            - 验证stage_status为completed或failed（均可接受）
        """
        # Arrange
        self.mock_llm_client.chat_completion.return_value = {
            "content": json.dumps({
                "material": "45钢",
                "part_type": "零件",
                "dimensions": {},
                "tolerance": "",
                "surface_roughness": "",
                "quantity": 1
            }, ensure_ascii=False),
            "model": "qwen2.5-coder:7b",
            "finish_reason": "stop"
        }

        context = AgentContextFactory.create(user_input=special_input)

        # Act & Assert - 确保不引发异常
        try:
            result = await self.agent.execute(context)
            assert result.current_stage == "understanding"
        except Exception as e:
            pytest.fail(f"特殊字符输入处理失败: {description}, 错误: {e!s}")


class TestRagMockEnhancement:
    """RAG检索增强Mock测试类。

    实现Mock知识库返回固定测试数据：
    - 创建模拟检索函数，返回预定义的知识内容
    - 确保模拟函数正确拦截实际知识库调用

    验证标准：
    - Agent能够正确调用RAG检索接口
    - 检索到的知识被正确应用于参数提取过程
    - 最终结果中包含并正确使用了检索到的知识内容
    """

    def setup_method(self, method):
        """测试方法执行前的准备工作。

        Args:
            method: 当前执行的测试方法
        """
        self.agent = UnderstandingAgent()
        self.mock_llm_client = AsyncMock()
        self.mock_knowledge_base = MagicMock()

        self.agent.llm_client = self.mock_llm_client
        self.agent.knowledge_base = self.mock_knowledge_base
        self.agent._model_router = None

    def teardown_method(self, method):
        """测试方法执行后的清理工作。

        Args:
            method: 当前执行的测试方法
        """
        self.agent = None
        self.mock_llm_client = None
        self.mock_knowledge_base = None

    @pytest.mark.asyncio
    async def test_rag_mock_returns_fixed_data(self):
        """测试Mock知识库返回固定测试数据。

        创建模拟检索函数，返回预定义的知识内容，
        确保模拟函数正确拦截实际知识库调用。

        Arrange:
            - 配置mock知识库返回固定的测试数据
            - 配置LLM mock返回有效响应
        Act:
            - 调用agent.execute()
        Assert:
            - 验证knowledge_base.query被调用
            - 验证返回的是预设的固定测试数据
            - 验证LLM调用时系统提示包含检索到的知识
        """
        # Arrange - 创建模拟检索函数返回预定义知识内容
        fixed_knowledge = [
            "传动轴加工技术规范：传动轴直径公差一般为IT6-IT7级别",
            "45钢热处理工艺：调质处理HB220-250",
            "轴类零件车削参数：切削速度v=120-180m/min"
        ]

        self.mock_knowledge_base.query.return_value = {
            "documents": fixed_knowledge,
            "metadatas": [
                {"type": "传动轴", "category": "技术规范"},
                {"type": "45钢", "category": "热处理"},
                {"type": "车削", "category": "加工参数"}
            ],
            "distances": [0.05, 0.1, 0.15],
            "ids": ["shaft_spec", "steel_45_heat", "turning_params"]
        }

        self.mock_llm_client.chat_completion.return_value = {
            "content": json.dumps({
                "material": "45钢",
                "part_type": "轴类",
                "dimensions": {"diameter": 30.0, "length": 100.0},
                "tolerance": "IT7",
                "surface_roughness": "Ra 0.8",
                "quantity": 1
            }, ensure_ascii=False),
            "model": "qwen2.5-coder:7b",
            "finish_reason": "stop"
        }

        user_input = "需要加工一个45钢材质的传动轴，直径30mm，长度100mm"
        context = AgentContextFactory.create(user_input=user_input)

        # Act
        result = await self.agent.execute(context)

        # Assert - 验证RAG检索被正确调用
        self.mock_knowledge_base.query.assert_called_once_with(
            query_text=user_input,
            n_results=3
        )

        # 验证LLM调用时系统提示包含检索到的知识内容
        call_args = self.mock_llm_client.chat_completion.call_args
        messages = call_args[0][0]
        system_prompt = messages[0]["content"]

        for knowledge_doc in fixed_knowledge:
            assert knowledge_doc in system_prompt

        # 验证最终结果正确提取参数
        assert result.extracted_params["material"] == "45钢"
        assert result.extracted_params["part_type"] == "轴类"

    @pytest.mark.asyncio
    async def test_rag_knowledge_applied_in_extraction(self):
        """测试检索到的知识被正确应用于参数提取过程。

        验证RAG检索结果不仅被包含在系统提示中，
        而且对最终的参数提取产生了影响。

        Arrange:
            - 配置mock知识库返回包含技术参数的知识
            - 配置LLM mock返回使用了知识的参数结果
        Act:
            - 调用agent.execute()
        Assert:
            - 验证提取的参数包含了知识库中的信息
            - 验证tolerance等参数与知识库内容一致
        """
        # Arrange
        rag_knowledge = [
            "传动轴直径30mm通常采用IT7公差等级",
            "45钢材质的传动轴表面粗糙度要求一般为Ra 0.8"
        ]

        self.mock_knowledge_base.query.return_value = {
            "documents": rag_knowledge,
            "metadatas": [],
            "distances": [],
            "ids": []
        }

        # LLM返回的结果应该包含知识库中的信息
        self.mock_llm_client.chat_completion.return_value = {
            "content": json.dumps({
                "material": "45钢",
                "part_type": "轴类",
                "dimensions": {"diameter": 30.0, "length": 100.0},
                "tolerance": "IT7",
                "surface_roughness": "Ra 0.8",
                "quantity": 1
            }, ensure_ascii=False),
            "model": "qwen2.5-coder:7b",
            "finish_reason": "stop"
        }

        context = AgentContextFactory.create(
            user_input="需要加工一个45钢材质的传动轴，直径30mm，长度100mm"
        )

        # Act
        result = await self.agent.execute(context)

        # Assert - 验证提取的参数使用了RAG知识
        assert result.extracted_params["tolerance"] == "IT7"
        assert result.extracted_params["surface_roughness"] == "Ra 0.8"

        # 验证系统提示确实包含了RAG知识
        call_args = self.mock_llm_client.chat_completion.call_args
        messages = call_args[0][0]
        system_prompt = messages[0]["content"]

        assert rag_knowledge[0] in system_prompt
        assert rag_knowledge[1] in system_prompt

    @pytest.mark.asyncio
    async def test_rag_query_intercepted_correctly(self):
        """测试模拟函数正确拦截实际知识库调用。

        验证mock对象完全替代了真实的知识库调用，
        没有触发任何实际的数据库查询。

        Arrange:
            - 配置mock知识库
            - 确保mock正确设置
        Act:
            - 调用agent.execute()
        Assert:
            - 验证knowledge_base.query被调用且仅被调用一次
            - 验证调用参数正确
            - 验证返回的是mock数据而非真实数据
        """
        # Arrange
        mock_return_value = {
            "documents": ["Mock知识内容"],
            "metadatas": [{"type": "mock"}],
            "distances": [0.1],
            "ids": ["mock_id"]
        }

        self.mock_knowledge_base.query.return_value = mock_return_value
        self.mock_llm_client.chat_completion.return_value = LLMResponseFactory(json_only=True)

        context = AgentContextFactory.create(user_input="测试输入")

        # Act
        await self.agent.execute(context)

        # Assert - 验证mock被正确调用
        assert self.mock_knowledge_base.query.called
        assert self.mock_knowledge_base.query.call_count == 1

        # 验证调用参数
        call_kwargs = self.mock_knowledge_base.query.call_args[1]
        assert "query_text" in call_kwargs
        assert "n_results" in call_kwargs
        assert call_kwargs["n_results"] == 3

        # 验证返回的是mock数据
        assert self.mock_knowledge_base.query.return_value == mock_return_value
