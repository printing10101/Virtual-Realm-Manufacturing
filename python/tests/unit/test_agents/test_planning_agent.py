"""PlanningAgent单元测试模块。

测试PlanningAgent的核心功能，包括工艺路线生成、
材料差异处理、无效输入容错、以及与UnderstandingAgent的集成场景。
所有测试遵循AAA（Arrange-Act-Assert）模式，
确保测试独立性和可重复性。

测试类别:
    - 工艺路线生成功能测试
    - 材料类型工艺差异测试
    - 无效输入处理测试
    - 与UnderstandingAgent集成测试
"""
import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.ai.agents import PlanningAgent
from tests.factories import (
    AgentContextFactory,
    KnowledgeQueryResultFactory,
)


class TestProcessRouteGeneration:
    """工艺路线生成功能测试类。

    验证PlanningAgent在不同输入参数下的工艺路线生成准确性，
    包括完整参数输入、输出字段验证、工序顺序验证等场景。
    """

    def setup_method(self, method):
        """测试方法执行前的准备工作。

        创建PlanningAgent实例和相关的mock对象，
        确保每个测试方法都在干净的初始状态下执行。

        Args:
            method: 当前执行的测试方法
        """
        self.agent = PlanningAgent()
        self.mock_llm_client = AsyncMock()
        self.mock_knowledge_base = MagicMock()
        self.mock_model_router = AsyncMock()

        # 替换真实依赖为mock对象
        self.agent.llm_client = self.mock_llm_client
        self.agent.knowledge_base = self.mock_knowledge_base
        self.agent._model_router = None

        # 配置知识库mock默认返回
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
    async def test_generate_route_with_complete_params(self):
        """测试使用完整参数生成工艺路线。

        验证当提供材料、零件类型、尺寸等完整参数时，
        PlanningAgent能够生成包含所有必填字段的工艺路线。

        Arrange:
            - 配置LLM mock返回完整的工艺路线JSON
            - 创建包含完整参数的AgentContext
        Act:
            - 调用agent.execute()执行工艺路线生成
        Assert:
            - 验证stage_status为completed
            - 验证process_route包含step, operation, machine, description字段
            - 验证工序数量与预期一致
        """
        # Arrange
        route_data = {
            "route": [
                {"step": 1, "operation": "下料", "machine": "锯床", "description": "按尺寸下料45钢棒料"},
                {"step": 2, "operation": "粗车", "machine": "车床", "description": "粗加工外圆至直径52mm"},
                {"step": 3, "operation": "半精车", "machine": "车床", "description": "半精加工至直径50.5mm"},
                {"step": 4, "operation": "精车", "machine": "数控车床", "description": "精加工外圆至直径50mm，公差IT7"},
                {"step": 5, "operation": "检验", "machine": "量具", "description": "检验尺寸和表面粗糙度"}
            ]
        }

        self.mock_llm_client.chat_completion.return_value = {
            "content": json.dumps(route_data, ensure_ascii=False),
            "model": "qwen2.5-coder:7b",
            "finish_reason": "stop"
        }

        context = AgentContextFactory(understood=True)

        # Act
        result = await self.agent.execute(context)

        # Assert
        assert result.current_stage == "planning"
        assert "completed" in result.stage_status
        assert len(result.process_route) == 5

        # 验证必填字段
        for step_data in result.process_route:
            assert "step" in step_data
            assert "operation" in step_data
            assert "machine" in step_data
            assert "description" in step_data

    @pytest.mark.asyncio
    async def test_route_steps_sequential_numbering(self):
        """验证工序步骤编号的连续性。

        确保生成的工艺路线中step字段从1开始连续递增。

        Arrange:
            - 配置LLM mock返回包含5道工序的路线
        Act:
            - 调用agent.execute()
        Assert:
            - 验证step字段为1, 2, 3, 4, 5
        """
        # Arrange
        route_data = {
            "route": [
                {"step": 1, "operation": "下料", "machine": "锯床", "description": "下料"},
                {"step": 2, "operation": "粗加工", "machine": "车床", "description": "粗加工"},
                {"step": 3, "operation": "精加工", "machine": "车床", "description": "精加工"}
            ]
        }

        self.mock_llm_client.chat_completion.return_value = {
            "content": json.dumps(route_data, ensure_ascii=False),
            "model": "qwen2.5-coder:7b",
            "finish_reason": "stop"
        }

        context = AgentContextFactory(understood=True)

        # Act
        result = await self.agent.execute(context)

        # Assert
        expected_steps = [1, 2, 3]
        actual_steps = [step["step"] for step in result.process_route]
        assert actual_steps == expected_steps

    @pytest.mark.asyncio
    async def test_route_operation_order_follows_process_logic(self):
        """验证工序顺序遵循合理工艺流程。

        验证工艺路线严格遵循"下料→粗加工→精加工→检验"的顺序。

        Arrange:
            - 配置LLM mock返回标准工艺顺序
        Act:
            - 调用agent.execute()
        Assert:
            - 验证工序顺序包含下料、粗加工、精加工
            - 验证下料在粗加工之前，粗加工在精加工之前
        """
        # Arrange
        route_data = {
            "route": [
                {"step": 1, "operation": "下料", "machine": "锯床", "description": "按尺寸下料"},
                {"step": 2, "operation": "粗车", "machine": "车床", "description": "粗加工外圆"},
                {"step": 3, "operation": "半精车", "machine": "车床", "description": "半精加工"},
                {"step": 4, "operation": "精车", "machine": "数控车床", "description": "精加工到尺寸"},
                {"step": 5, "operation": "检验", "machine": "量具", "description": "检验尺寸"}
            ]
        }

        self.mock_llm_client.chat_completion.return_value = {
            "content": json.dumps(route_data, ensure_ascii=False),
            "model": "qwen2.5-coder:7b",
            "finish_reason": "stop"
        }

        context = AgentContextFactory(understood=True)

        # Act
        result = await self.agent.execute(context)

        # Assert - 验证工艺顺序
        operations = [step["operation"] for step in result.process_route]

        # 找到关键工序的索引
        cutting_idx = next(i for i, op in enumerate(operations) if "下料" in op)
        rough_idx = next(i for i, op in enumerate(operations) if "粗" in op)
        finish_idx = next(i for i, op in enumerate(operations) if "精" in op)
        inspect_idx = next(i for i, op in enumerate(operations) if "检验" in op)

        # 验证顺序：下料 < 粗加工 < 精加工 < 检验
        assert cutting_idx < rough_idx < finish_idx < inspect_idx

    @pytest.mark.asyncio
    async def test_route_machine_matches_operation(self):
        """验证设备与工序的匹配性。

        验证各工序的machine字段与operation字段合理匹配。

        Arrange:
            - 配置LLM mock返回包含设备信息的工艺路线
        Act:
            - 调用agent.execute()
        Assert:
            - 验证下料工序使用锯床或类似设备
            - 验证车削工序使用车床或数控车床
            - 验证检验工序使用量具或检测设备
        """
        # Arrange
        route_data = {
            "route": [
                {"step": 1, "operation": "下料", "machine": "锯床", "description": "按尺寸下料"},
                {"step": 2, "operation": "粗车", "machine": "车床", "description": "粗加工外圆"},
                {"step": 3, "operation": "精车", "machine": "数控车床", "description": "精加工"},
                {"step": 4, "operation": "铣削", "machine": "铣床", "description": "铣键槽"},
                {"step": 5, "operation": "检验", "machine": "三坐标测量机", "description": "检验尺寸"}
            ]
        }

        self.mock_llm_client.chat_completion.return_value = {
            "content": json.dumps(route_data, ensure_ascii=False),
            "model": "qwen2.5-coder:7b",
            "finish_reason": "stop"
        }

        context = AgentContextFactory(understood=True)

        # Act
        result = await self.agent.execute(context)

        # Assert - 验证设备与工序匹配
        for step in result.process_route:
            op = step["operation"].lower()
            machine = step["machine"].lower()

            if "下料" in op:
                assert any(keyword in machine for keyword in ["锯", "切割"])
            elif "车" in op:
                assert "车" in machine
            elif "铣" in op:
                assert "铣" in machine
            elif "检验" in op or "检测" in op:
                assert any(keyword in machine for keyword in ["量", "测量", "检测"])

    @pytest.mark.asyncio
    async def test_route_description_contains_material_info(self):
        """验证工序说明包含材料信息。

        验证各工序的description字段与输入材料参数相关联。

        Arrange:
            - 配置LLM mock返回包含材料信息的描述
            - 设置材料为45钢
        Act:
            - 调用agent.execute()
        Assert:
            - 验证至少一个工序的description包含"45钢"
            - 验证描述内容与输入参数匹配
        """
        # Arrange
        route_data = {
            "route": [
                {"step": 1, "operation": "下料", "machine": "锯床", "description": "按尺寸下料45钢棒料"},
                {"step": 2, "operation": "粗车", "machine": "车床", "description": "粗加工45钢外圆"},
                {"step": 3, "operation": "精车", "machine": "车床", "description": "精加工到尺寸"}
            ]
        }

        self.mock_llm_client.chat_completion.return_value = {
            "content": json.dumps(route_data, ensure_ascii=False),
            "model": "qwen2.5-coder:7b",
            "finish_reason": "stop"
        }

        context = AgentContextFactory(understood=True)

        # Act
        result = await self.agent.execute(context)

        # Assert
        descriptions = " ".join([step["description"] for step in result.process_route])
        assert "45钢" in descriptions

    @pytest.mark.asyncio
    async def test_route_with_markdown_wrapped_json(self):
        """测试解析被markdown代码块包裹的工艺路线JSON。

        验证当LLM返回的工艺路线被```json或```包裹时，
        Agent能够正确提取并解析。

        Arrange:
            - 配置LLM mock返回markdown包裹的JSON
        Act:
            - 调用agent.execute()
        Assert:
            - 验证stage_status为completed
            - 验证process_route正确解析
        """
        # Arrange
        route_data = {
            "route": [
                {"step": 1, "operation": "下料", "machine": "锯床", "description": "下料"},
                {"step": 2, "operation": "粗加工", "machine": "车床", "description": "粗加工"}
            ]
        }
        json_content = json.dumps(route_data, ensure_ascii=False)

        self.mock_llm_client.chat_completion.return_value = {
            "content": f"```json\n{json_content}\n```",
            "model": "qwen2.5-coder:7b",
            "finish_reason": "stop"
        }

        context = AgentContextFactory(understood=True)

        # Act
        result = await self.agent.execute(context)

        # Assert
        assert "completed" in result.stage_status
        assert len(result.process_route) == 2
        assert result.process_route[0]["operation"] == "下料"


class TestMaterialProcessDifferences:
    """材料类型工艺差异测试类。

    测试不同材料（45钢、铝合金、钛合金）对工艺路线的影响，
    验证材料特性与加工工艺的匹配性。
    """

    def setup_method(self, method):
        """测试方法执行前的准备工作。

        Args:
            method: 当前执行的测试方法
        """
        self.agent = PlanningAgent()
        self.mock_llm_client = AsyncMock()
        self.mock_knowledge_base = MagicMock()
        self.mock_model_router = AsyncMock()

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
        self.mock_model_router = None

    @pytest.mark.asyncio
    async def test_45steel_process_route(self):
        """测试45钢材质的工艺路线。

        验证45钢（中碳钢）的工艺路线包含适当的热处理工序
        和合理的加工参数。

        Arrange:
            - 配置LLM mock返回45钢的工艺路线
            - 设置材料为45钢
        Act:
            - 调用agent.execute()
        Assert:
            - 验证工艺路线包含热处理或调质工序
            - 验证描述中包含45钢相关信息
        """
        # Arrange
        route_data = {
            "route": [
                {"step": 1, "operation": "下料", "machine": "锯床", "description": "下料45钢棒料"},
                {"step": 2, "operation": "粗车", "machine": "车床", "description": "粗加工外圆"},
                {"step": 3, "operation": "调质处理", "machine": "热处理炉", "description": "45钢调质处理HB220-250"},
                {"step": 4, "operation": "精车", "machine": "数控车床", "description": "精加工到尺寸"},
                {"step": 5, "operation": "检验", "machine": "量具", "description": "检验尺寸"}
            ]
        }

        self.mock_llm_client.chat_completion.return_value = {
            "content": json.dumps(route_data, ensure_ascii=False),
            "model": "qwen2.5-coder:7b",
            "finish_reason": "stop"
        }

        context = AgentContextFactory(understood=True)
        context.extracted_params["material"] = "45钢"

        # Act
        result = await self.agent.execute(context)

        # Assert
        assert "completed" in result.stage_status
        operations = [step["operation"] for step in result.process_route]
        assert any("调质" in op or "热" in op for op in operations)

    @pytest.mark.asyncio
    async def test_aluminum_alloy_process_route(self):
        """测试铝合金材质的工艺路线。

        验证铝合金的工艺路线采用更高的切削速度建议，
        且通常不需要热处理工序。

        Arrange:
            - 配置LLM mock返回铝合金的工艺路线
            - 设置材料为6061铝合金
        Act:
            - 调用agent.execute()
        Assert:
            - 验证工艺路线描述中包含高切削速度相关信息
            - 验证通常不包含热处理工序（或包含时效处理）
        """
        # Arrange
        route_data = {
            "route": [
                {"step": 1, "operation": "下料", "machine": "锯床", "description": "下料6061铝合金棒料"},
                {"step": 2, "operation": "粗铣", "machine": "加工中心", "description": "粗加工，切削速度200m/min"},
                {"step": 3, "operation": "精铣", "machine": "加工中心", "description": "精加工到尺寸，切削速度300m/min"},
                {"step": 4, "operation": "去毛刺", "machine": "手工", "description": "去除毛刺"},
                {"step": 5, "operation": "检验", "machine": "量具", "description": "检验尺寸"}
            ]
        }

        self.mock_llm_client.chat_completion.return_value = {
            "content": json.dumps(route_data, ensure_ascii=False),
            "model": "qwen2.5-coder:7b",
            "finish_reason": "stop"
        }

        context = AgentContextFactory(understood=True)
        context.extracted_params["material"] = "6061铝合金"

        # Act
        result = await self.agent.execute(context)

        # Assert
        assert "completed" in result.stage_status

        # 验证描述中包含高切削速度
        descriptions = " ".join([step["description"] for step in result.process_route])
        assert any(keyword in descriptions for keyword in ["200", "300", "高"])

        # 铝合金通常不需要传统热处理（可能有阳极氧化等表面处理）
        operations = [step["operation"] for step in result.process_route]
        assert not any("调质" in op for op in operations)

    @pytest.mark.asyncio
    async def test_titanium_alloy_process_route(self):
        """测试钛合金材质的工艺路线。

        验证钛合金的工艺路线采用较低的切削速度，
        并包含充分的冷却措施。

        Arrange:
            - 配置LLM mock返回钛合金的工艺路线
            - 设置材料为TC4钛合金
        Act:
            - 调用agent.execute()
        Assert:
            - 验证工艺路线描述中包含低切削速度相关信息
            - 验证包含充分冷却的描述
        """
        # Arrange
        route_data = {
            "route": [
                {"step": 1, "operation": "下料", "machine": "带锯", "description": "下料TC4钛合金棒料"},
                {"step": 2, "operation": "粗车", "machine": "数控车床", "description": "粗加工，切削速度30m/min，充分冷却"},
                {"step": 3, "operation": "半精车", "machine": "数控车床", "description": "半精加工，使用切削液"},
                {"step": 4, "operation": "精车", "machine": "数控车床", "description": "精加工到尺寸，低速精车"},
                {"step": 5, "operation": "检验", "machine": "三坐标", "description": "检验尺寸"}
            ]
        }

        self.mock_llm_client.chat_completion.return_value = {
            "content": json.dumps(route_data, ensure_ascii=False),
            "model": "qwen2.5-coder:7b",
            "finish_reason": "stop"
        }

        context = AgentContextFactory(understood=True)
        context.extracted_params["material"] = "TC4钛合金"

        # Act
        result = await self.agent.execute(context)

        # Assert
        assert "completed" in result.stage_status

        # 验证描述中包含低切削速度和冷却措施
        descriptions = " ".join([step["description"] for step in result.process_route])
        assert any(keyword in descriptions for keyword in ["30", "低速", "冷却", "切削液"])

    @pytest.mark.asyncio
    @pytest.mark.parametrize("material,expected_keywords", [
        ("45钢", ["调质", "热", "HB"]),
        ("6061铝合金", ["高", "200", "300"]),
        ("TC4钛合金", ["低速", "冷却", "30"]),
    ])
    async def test_material_specific_process_parameters(self, material, expected_keywords):
        """参数化测试不同材料的工艺参数差异。

        验证不同材料对应不同的加工参数建议。

        Arrange:
            - 根据材料类型配置相应的LLM mock响应
        Act:
            - 调用agent.execute()
        Assert:
            - 验证工艺路线描述中包含该材料特有的关键词
        """
        # Arrange - 根据材料类型返回不同的工艺路线
        route_templates = {
            "45钢": {
                "route": [
                    {"step": 1, "operation": "下料", "machine": "锯床", "description": "下料45钢"},
                    {"step": 2, "operation": "粗车", "machine": "车床", "description": "粗加工，调质处理HB220-250"},
                    {"step": 3, "operation": "精车", "machine": "车床", "description": "精加工到尺寸"}
                ]
            },
            "6061铝合金": {
                "route": [
                    {"step": 1, "operation": "下料", "machine": "锯床", "description": "下料铝合金"},
                    {"step": 2, "operation": "粗铣", "machine": "加工中心", "description": "粗加工，高速切削300m/min"},
                    {"step": 3, "operation": "精铣", "machine": "加工中心", "description": "精加工到尺寸"}
                ]
            },
            "TC4钛合金": {
                "route": [
                    {"step": 1, "operation": "下料", "machine": "带锯", "description": "下料钛合金"},
                    {"step": 2, "operation": "粗车", "machine": "车床", "description": "低速粗车30m/min，充分冷却"},
                    {"step": 3, "operation": "精车", "machine": "车床", "description": "低速精加工"}
                ]
            }
        }

        self.mock_llm_client.chat_completion.return_value = {
            "content": json.dumps(route_templates[material], ensure_ascii=False),
            "model": "qwen2.5-coder:7b",
            "finish_reason": "stop"
        }

        context = AgentContextFactory(understood=True)
        context.extracted_params["material"] = material

        # Act
        result = await self.agent.execute(context)

        # Assert
        descriptions = " ".join([step["description"] for step in result.process_route])
        assert any(keyword in descriptions for keyword in expected_keywords)


class TestInvalidInputHandling:
    """无效输入处理测试类。

    测试PlanningAgent对缺少必要参数、格式错误等异常输入的处理能力，
    验证系统的鲁棒性和降级策略。
    """

    def setup_method(self, method):
        """测试方法执行前的准备工作。

        Args:
            method: 当前执行的测试方法
        """
        self.agent = PlanningAgent()
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
    async def test_missing_material_param_uses_default(self):
        """测试缺少材料参数时使用默认值。

        验证当extracted_params中缺少material字段时，
        Agent使用默认值"45钢"。

        Arrange:
            - 创建不包含material的extracted_params
            - 配置LLM mock返回有效响应
        Act:
            - 调用agent.execute()
        Assert:
            - 验证stage_status为completed
            - 验证LLM调用时system_prompt包含默认材料"45钢"
        """
        # Arrange
        route_data = {
            "route": [
                {"step": 1, "operation": "下料", "machine": "锯床", "description": "下料"}
            ]
        }

        self.mock_llm_client.chat_completion.return_value = {
            "content": json.dumps(route_data, ensure_ascii=False),
            "model": "qwen2.5-coder:7b",
            "finish_reason": "stop"
        }

        context = AgentContextFactory()
        context.extracted_params = {"part_type": "轴类"}  # 缺少material

        # Act
        result = await self.agent.execute(context)

        # Assert
        assert "completed" in result.stage_status

        # 验证LLM调用时使用了默认材料
        call_args = self.mock_llm_client.chat_completion.call_args
        system_prompt = call_args[0][0][0]["content"]
        assert "45钢" in system_prompt

    @pytest.mark.asyncio
    async def test_missing_part_type_uses_default(self):
        """测试缺少零件类型参数时使用默认值。

        验证当extracted_params中缺少part_type字段时，
        Agent使用默认值"轴类零件"。

        Arrange:
            - 创建不包含part_type的extracted_params
        Act:
            - 调用agent.execute()
        Assert:
            - 验证LLM调用时system_prompt包含默认零件类型
        """
        # Arrange
        route_data = {
            "route": [
                {"step": 1, "operation": "下料", "machine": "锯床", "description": "下料"}
            ]
        }

        self.mock_llm_client.chat_completion.return_value = {
            "content": json.dumps(route_data, ensure_ascii=False),
            "model": "qwen2.5-coder:7b",
            "finish_reason": "stop"
        }

        context = AgentContextFactory()
        context.extracted_params = {"material": "45钢"}  # 缺少part_type

        # Act
        result = await self.agent.execute(context)

        # Assert
        assert "completed" in result.stage_status

        call_args = self.mock_llm_client.chat_completion.call_args
        system_prompt = call_args[0][0][0]["content"]
        assert "轴类零件" in system_prompt

    @pytest.mark.asyncio
    async def test_empty_extracted_params_uses_all_defaults(self):
        """测试完全空的extracted_params时使用所有默认值。

        验证当extracted_params为空字典时，
        Agent使用所有默认参数值。

        Arrange:
            - 创建空的extracted_params
        Act:
            - 调用agent.execute()
        Assert:
            - 验证stage_status为completed
            - 验证LLM调用时使用默认材料和零件类型
        """
        # Arrange
        route_data = {
            "route": [
                {"step": 1, "operation": "下料", "machine": "锯床", "description": "下料"}
            ]
        }

        self.mock_llm_client.chat_completion.return_value = {
            "content": json.dumps(route_data, ensure_ascii=False),
            "model": "qwen2.5-coder:7b",
            "finish_reason": "stop"
        }

        context = AgentContextFactory()
        context.extracted_params = {}

        # Act
        result = await self.agent.execute(context)

        # Assert
        assert "completed" in result.stage_status

        call_args = self.mock_llm_client.chat_completion.call_args
        messages = call_args[0][0]
        system_prompt = messages[0]["content"]
        assert "45钢" in system_prompt
        assert "轴类零件" in system_prompt

    @pytest.mark.asyncio
    async def test_invalid_json_response_uses_fallback_route(self):
        """测试LLM返回无效JSON时使用降级工艺路线。

        验证当LLM返回无法解析的JSON时，
        Agent使用预设的默认工艺路线作为降级策略。

        Arrange:
            - 配置LLM mock返回无效JSON
        Act:
            - 调用agent.execute()
        Assert:
            - 验证stage_status包含failed信息
            - 验证process_route使用默认降级路线
        """
        # Arrange
        self.mock_llm_client.chat_completion.return_value = {
            "content": "这不是有效的JSON格式",
            "model": "qwen2.5-coder:7b",
            "finish_reason": "stop"
        }

        context = AgentContextFactory(understood=True)

        # Act
        result = await self.agent.execute(context)

        # Assert
        assert "failed" in result.stage_status

        # 验证使用降级策略的默认路线
        assert len(result.process_route) == 4
        assert result.process_route[0]["operation"] == "下料"
        assert result.process_route[0]["machine"] == "锯床"
        assert result.process_route[1]["operation"] == "粗车"
        assert result.process_route[2]["operation"] == "精车"
        assert result.process_route[3]["operation"] == "检验"

    @pytest.mark.asyncio
    async def test_malformed_json_uses_fallback_route(self):
        """测试格式错误的JSON时使用降级路线。

        验证当LLM返回格式错误的JSON（如缺少括号）时，
        Agent使用预设的默认工艺路线。

        Arrange:
            - 配置LLM mock返回格式错误的JSON
        Act:
            - 调用agent.execute()
        Assert:
            - 验证stage_status包含failed
            - 验证process_route使用默认降级路线
        """
        # Arrange
        self.mock_llm_client.chat_completion.return_value = {
            "content": '{"route": [{"step": 1, "operation": "下料"}',  # 缺少闭合括号
            "model": "qwen2.5-coder:7b",
            "finish_reason": "stop"
        }

        context = AgentContextFactory(understood=True)

        # Act
        result = await self.agent.execute(context)

        # Assert
        assert "failed" in result.stage_status
        assert len(result.process_route) == 4

    @pytest.mark.asyncio
    async def test_empty_response_uses_fallback_route(self):
        """测试LLM返回空内容时使用降级路线。

        验证当LLM返回空字符串时，
        Agent使用预设的默认工艺路线。

        Arrange:
            - 配置LLM mock返回空字符串
        Act:
            - 调用agent.execute()
        Assert:
            - 验证stage_status包含failed
            - 验证process_route使用默认降级路线
        """
        # Arrange
        self.mock_llm_client.chat_completion.return_value = {
            "content": "",
            "model": "qwen2.5-coder:7b",
            "finish_reason": "stop"
        }

        context = AgentContextFactory(understood=True)

        # Act
        result = await self.agent.execute(context)

        # Assert
        assert "failed" in result.stage_status
        assert len(result.process_route) == 4

    @pytest.mark.asyncio
    async def test_route_missing_route_key_uses_fallback(self):
        """测试JSON中缺少route键时使用降级路线。

        验证当LLM返回的JSON格式正确但缺少"route"键时，
        Agent使用空列表或降级路线。

        Arrange:
            - 配置LLM mock返回不包含route键的JSON
        Act:
            - 调用agent.execute()
        Assert:
            - 验证stage_status为completed（因为JSON解析成功）
            - 验证process_route为空列表或使用默认值
        """
        # Arrange
        self.mock_llm_client.chat_completion.return_value = {
            "content": json.dumps({"steps": []}, ensure_ascii=False),  # 缺少route键
            "model": "qwen2.5-coder:7b",
            "finish_reason": "stop"
        }

        context = AgentContextFactory(understood=True)

        # Act
        result = await self.agent.execute(context)

        # Assert
        # 根据代码实现，route_data.get("route", [])会返回空列表
        assert "completed" in result.stage_status
        assert result.process_route == []

    @pytest.mark.asyncio
    async def test_llm_exception_propagates(self):
        """测试LLM调用异常时的处理。

        验证当LLM客户端抛出异常时，
        异常会向上传播（因为execute方法没有捕获LLM调用异常）。

        Arrange:
            - 配置LLM mock抛出异常
        Act & Assert:
            - 验证异常向上传播
        """
        # Arrange
        self.mock_llm_client.chat_completion.side_effect = Exception("LLM连接超时")

        context = AgentContextFactory(understood=True)

        # Act & Assert
        with pytest.raises(Exception, match="LLM连接超时"):
            await self.agent.execute(context)


class TestUnderstandingAgentIntegration:
    """与UnderstandingAgent集成测试类。

    测试PlanningAgent能否正确接收和解析UnderstandingAgent提供的参数，
    验证完整的参数传递流程和工艺路线生成的正确性。
    """

    def setup_method(self, method):
        """测试方法执行前的准备工作。

        Args:
            method: 当前执行的测试方法
        """
        self.agent = PlanningAgent()
        self.mock_llm_client = AsyncMock()
        self.mock_knowledge_base = MagicMock()
        self.mock_model_router = AsyncMock()

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
        self.mock_model_router = None

    @pytest.mark.asyncio
    async def test_receive_understanding_agent_output(self):
        """测试接收UnderstandingAgent的输出参数。

        模拟UnderstandingAgent提取的参数输出格式，
        验证PlanningAgent能够正确接收和使用这些参数。

        Arrange:
            - 模拟UnderstandingAgent的提取结果
            - 创建包含这些参数的AgentContext
        Act:
            - 调用PlanningAgent.execute()
        Assert:
            - 验证stage_status为completed
            - 验证LLM调用时使用了UnderstandingAgent提供的参数
        """
        # Arrange - 模拟UnderstandingAgent的输出
        understanding_output = {
            "material": "45钢",
            "part_type": "轴类零件",
            "dimensions": {"length": 100.0, "width": 50.0, "height": 30.0},
            "tolerance": "IT7",
            "surface_roughness": "Ra 0.8",
            "quantity": 100
        }

        route_data = {
            "route": [
                {"step": 1, "operation": "下料", "machine": "锯床", "description": "按尺寸下料"},
                {"step": 2, "operation": "粗车", "machine": "车床", "description": "粗加工外圆"},
                {"step": 3, "operation": "精车", "machine": "车床", "description": "精加工到尺寸"}
            ]
        }

        self.mock_llm_client.chat_completion.return_value = {
            "content": json.dumps(route_data, ensure_ascii=False),
            "model": "qwen2.5-coder:7b",
            "finish_reason": "stop"
        }

        context = AgentContextFactory()
        context.extracted_params = understanding_output

        # Act
        result = await self.agent.execute(context)

        # Assert
        assert "completed" in result.stage_status

        # 验证LLM调用时使用了UnderstandingAgent提供的材料
        call_args = self.mock_llm_client.chat_completion.call_args
        system_prompt = call_args[0][0][0]["content"]
        assert "45钢" in system_prompt
        assert "轴类零件" in system_prompt

    @pytest.mark.asyncio
    async def test_full_pipeline_understanding_to_planning(self):
        """测试完整的UnderstandingAgent到PlanningAgent的管道流程。

        构建完整的参数传递流程测试场景，
        模拟从需求理解到工艺规划的完整链路。

        Arrange:
            - 创建初始用户输入
            - 模拟UnderstandingAgent已执行完成的场景
        Act:
            - 调用PlanningAgent.execute()
        Assert:
            - 验证工艺路线生成成功
            - 验证路线与输入参数匹配
        """
        # Arrange - 模拟UnderstandingAgent已完成参数提取
        context = AgentContextFactory(
            user_input="我需要加工一批45钢的轴类零件，长度100mm，直径50mm，精度IT7"
        )
        context.extracted_params = {
            "material": "45钢",
            "part_type": "轴类零件",
            "dimensions": {"length": 100.0, "diameter": 50.0},
            "tolerance": "IT7",
            "surface_roughness": "Ra 0.8",
            "quantity": 100
        }
        context.current_stage = "understanding"
        context.stage_status = "completed"

        route_data = {
            "route": [
                {"step": 1, "operation": "下料", "machine": "锯床", "description": "按100mm长度下料"},
                {"step": 2, "operation": "粗车", "machine": "车床", "description": "粗加工直径50mm外圆"},
                {"step": 3, "operation": "精车", "machine": "数控车床", "description": "精加工到IT7公差"},
                {"step": 4, "operation": "检验", "machine": "量具", "description": "检验尺寸和粗糙度"}
            ]
        }

        self.mock_llm_client.chat_completion.return_value = {
            "content": json.dumps(route_data, ensure_ascii=False),
            "model": "qwen2.5-coder:7b",
            "finish_reason": "stop"
        }

        # Act
        result = await self.agent.execute(context)

        # Assert
        assert result.current_stage == "planning"
        assert "completed" in result.stage_status
        assert len(result.process_route) == 4

        # 验证工艺路线与输入参数匹配
        descriptions = " ".join([step["description"] for step in result.process_route])
        assert any(keyword in descriptions for keyword in ["100", "50", "IT7"])

    @pytest.mark.asyncio
    async def test_integration_with_partial_understanding_params(self):
        """测试与部分理解参数的集成。

        验证当UnderstandingAgent只提取了部分参数时，
        PlanningAgent能够使用默认值补全并继续执行。

        Arrange:
            - 模拟UnderstandingAgent只提取了material
            - 其他参数缺失
        Act:
            - 调用PlanningAgent.execute()
        Assert:
            - 验证stage_status为completed
            - 验证使用默认值补全缺失参数
        """
        # Arrange
        context = AgentContextFactory()
        context.extracted_params = {
            "material": "6061铝合金"
            # 缺少part_type等其他参数
        }

        route_data = {
            "route": [
                {"step": 1, "operation": "下料", "machine": "锯床", "description": "下料"},
                {"step": 2, "operation": "粗加工", "machine": "加工中心", "description": "粗加工"},
                {"step": 3, "operation": "精加工", "machine": "加工中心", "description": "精加工"}
            ]
        }

        self.mock_llm_client.chat_completion.return_value = {
            "content": json.dumps(route_data, ensure_ascii=False),
            "model": "qwen2.5-coder:7b",
            "finish_reason": "stop"
        }

        # Act
        result = await self.agent.execute(context)

        # Assert
        assert "completed" in result.stage_status

        # 验证LLM调用时使用了默认零件类型
        call_args = self.mock_llm_client.chat_completion.call_args
        system_prompt = call_args[0][0][0]["content"]
        assert "6061铝合金" in system_prompt
        assert "轴类零件" in system_prompt  # 默认值

    @pytest.mark.asyncio
    async def test_integration_preserves_context_stage_status(self):
        """验证集成过程中正确设置阶段状态。

        确保PlanningAgent执行时正确更新current_stage和stage_status。

        Arrange:
            - 创建包含UnderstandingAgent结果的context
        Act:
            - 调用PlanningAgent.execute()
        Assert:
            - 验证current_stage更新为"planning"
            - 验证stage_status根据执行结果更新
        """
        # Arrange
        route_data = {
            "route": [
                {"step": 1, "operation": "下料", "machine": "锯床", "description": "下料"}
            ]
        }

        self.mock_llm_client.chat_completion.return_value = {
            "content": json.dumps(route_data, ensure_ascii=False),
            "model": "qwen2.5-coder:7b",
            "finish_reason": "stop"
        }

        context = AgentContextFactory(understood=True)
        context.current_stage = "understanding"
        context.stage_status = "completed"

        # Act
        result = await self.agent.execute(context)

        # Assert
        assert result.current_stage == "planning"
        assert "completed" in result.stage_status

    @pytest.mark.asyncio
    async def test_integration_with_dimensions_in_input_data(self):
        """验证集成时dimensions参数正确传递给LLM路由。

        确保PlanningAgent在调用_call_llm_via_router时，
        正确传递UnderstandingAgent提供的dimensions参数。

        Arrange:
            - 配置包含dimensions的extracted_params
            - 配置model_router mock
        Act:
            - 调用PlanningAgent.execute()
        Assert:
            - 验证input_data中包含geometry字段
            - 验证geometry包含dimensions信息
        """
        # Arrange
        self.agent._model_router = self.mock_model_router

        route_data = {
            "route": [
                {"step": 1, "operation": "下料", "machine": "锯床", "description": "下料"}
            ]
        }

        self.mock_model_router.execute.return_value = {
            "content": json.dumps(route_data, ensure_ascii=False),
            "model": "qwen2.5-coder:7b",
            "finish_reason": "stop"
        }

        context = AgentContextFactory(understood=True)
        context.extracted_params["dimensions"] = {"length": 100.0, "width": 50.0}

        # Act
        await self.agent.execute(context)

        # Assert
        execute_call = self.mock_model_router.execute.call_args
        input_data = execute_call[1]["input_data"]
        assert "geometry" in input_data
        assert input_data["geometry"] == {"length": 100.0, "width": 50.0}


class TestRagIntegration:
    """RAG检索增强测试类。

    验证PlanningAgent在执行工艺规划时，
    如何正确利用RAG检索结果增强LLM的系统提示。
    """

    def setup_method(self, method):
        """测试方法执行前的准备工作。

        Args:
            method: 当前执行的测试方法
        """
        self.agent = PlanningAgent()
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
    async def test_rag_query_called_with_planning_context(self):
        """验证RAG检索使用工艺规划相关的查询文本。

        确保Agent在工艺规划时，使用"加工工艺路线规划"
        作为知识库检索的查询条件。

        Arrange:
            - 创建AgentContext
            - 配置知识库mock和LLM mock
        Act:
            - 调用agent.execute()
        Assert:
            - 验证knowledge_base.query被调用
            - 验证调用参数包含工艺规划相关文本
            - 验证n_results参数为5
        """
        # Arrange
        route_data = {
            "route": [
                {"step": 1, "operation": "下料", "machine": "锯床", "description": "下料"}
            ]
        }

        self.mock_knowledge_base.query.return_value = KnowledgeQueryResultFactory(single_result=True)
        self.mock_llm_client.chat_completion.return_value = {
            "content": json.dumps(route_data, ensure_ascii=False),
            "model": "qwen2.5-coder:7b",
            "finish_reason": "stop"
        }

        context = AgentContextFactory(understood=True)

        # Act
        await self.agent.execute(context)

        # Assert
        self.mock_knowledge_base.query.assert_called_once()
        call_args = self.mock_knowledge_base.query.call_args
        assert call_args[1]["query_text"] == "加工工艺路线规划"
        assert call_args[1]["n_results"] == 5

    @pytest.mark.asyncio
    @pytest.mark.rag
    async def test_rag_results_integrated_in_system_prompt(self):
        """验证RAG检索结果被正确整合到系统提示中。

        确保检索到的知识文档被传递给LLM的系统提示，
        用于增强工艺路线规划的准确性。

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
        expected_knowledge = "加工工艺路线规划：车铣复合加工方法"
        self.mock_knowledge_base.query.return_value = {
            "documents": [expected_knowledge],
            "metadatas": [{"type": "工艺规划"}],
            "distances": [0.1],
            "ids": ["planning_basic"]
        }

        route_data = {
            "route": [
                {"step": 1, "operation": "下料", "machine": "锯床", "description": "下料"}
            ]
        }

        self.mock_llm_client.chat_completion.return_value = {
            "content": json.dumps(route_data, ensure_ascii=False),
            "model": "qwen2.5-coder:7b",
            "finish_reason": "stop"
        }

        context = AgentContextFactory(understood=True)

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
        执行工艺路线规划，不因空检索结果而失败。

        Arrange:
            - 配置知识库返回空检索结果
            - 配置LLM mock返回有效响应
        Act:
            - 调用agent.execute()
        Assert:
            - 验证stage_status为completed
            - 验证process_route正常生成
        """
        # Arrange
        self.mock_knowledge_base.query.return_value = KnowledgeQueryResultFactory(empty=True)

        route_data = {
            "route": [
                {"step": 1, "operation": "下料", "machine": "锯床", "description": "下料"}
            ]
        }

        self.mock_llm_client.chat_completion.return_value = {
            "content": json.dumps(route_data, ensure_ascii=False),
            "model": "qwen2.5-coder:7b",
            "finish_reason": "stop"
        }

        context = AgentContextFactory(understood=True)

        # Act
        result = await self.agent.execute(context)

        # Assert
        assert "completed" in result.stage_status
        assert len(result.process_route) == 1


class TestLLMClientSimulation:
    """LLM客户端模拟测试类。

    使用pytest-mock模拟不同的LLM客户端行为，
    测试PlanningAgent在各种LLM响应场景下的表现。
    """

    def setup_method(self, method):
        """测试方法执行前的准备工作。

        Args:
            method: 当前执行的测试方法
        """
        self.agent = PlanningAgent()
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
        Act:
            - 调用agent.execute()
        Assert:
            - 验证model_router.execute被调用
            - 验证stage_status为completed
        """
        # Arrange
        route_data = {
            "route": [
                {"step": 1, "operation": "下料", "machine": "锯床", "description": "下料"}
            ]
        }

        expected_response = {
            "content": json.dumps(route_data, ensure_ascii=False),
            "model": "qwen2.5-coder:7b",
            "finish_reason": "stop"
        }
        self.mock_model_router.execute.return_value = expected_response

        context = AgentContextFactory(understood=True)

        # Act
        result = await self.agent.execute(context)

        # Assert
        self.mock_model_router.execute.assert_called_once()
        assert "completed" in result.stage_status

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

        route_data = {
            "route": [
                {"step": 1, "operation": "下料", "machine": "锯床", "description": "下料"}
            ]
        }

        self.mock_llm_client.chat_completion.return_value = {
            "content": json.dumps(route_data, ensure_ascii=False),
            "model": "qwen2.5-coder:7b",
            "finish_reason": "stop"
        }

        context = AgentContextFactory(understood=True)

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
        route_data = {
            "route": [
                {"step": 1, "operation": "下料", "machine": "锯床", "description": "下料"}
            ]
        }

        self.mock_model_router.execute.return_value = {
            "content": json.dumps(route_data, ensure_ascii=False),
            "model": "qwen2.5-coder:7b",
            "finish_reason": "stop"
        }

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

        工艺规划任务应该使用较低的temperature（0.3）
        以确保输出的确定性和合理性。

        Arrange:
            - 配置model_router不可用
            - 配置llm_client mock
        Act:
            - 调用agent.execute()
        Assert:
            - 验证chat_completion被调用
            - 验证temperature参数为0.3
            - 验证max_tokens参数为2048
        """
        # Arrange
        self.agent._model_router = None

        route_data = {
            "route": [
                {"step": 1, "operation": "下料", "machine": "锯床", "description": "下料"}
            ]
        }

        self.mock_llm_client.chat_completion.return_value = {
            "content": json.dumps(route_data, ensure_ascii=False),
            "model": "qwen2.5-coder:7b",
            "finish_reason": "stop"
        }

        context = AgentContextFactory(understood=True)

        # Act
        await self.agent.execute(context)

        # Assert
        call_args = self.mock_llm_client.chat_completion.call_args
        # chat_completion(messages, max_tokens, temperature, model)
        assert call_args[0][2] == 0.3  # temperature
        assert call_args[0][1] == 2048  # max_tokens

    @pytest.mark.asyncio
    @pytest.mark.llm
    async def test_both_router_and_llm_fail(self):
        """测试model_router和LLM客户端都失败的场景。

        当所有LLM调用途径都失败时，验证异常会向上传播。

        Arrange:
            - 配置model_router抛出异常
            - 配置llm_client也抛出异常
        Act & Assert:
            - 验证异常向上传播
        """
        # Arrange
        self.mock_model_router.execute.side_effect = Exception("路由失败")
        self.mock_llm_client.chat_completion.side_effect = Exception("LLM失败")

        context = AgentContextFactory(understood=True)

        # Act & Assert
        with pytest.raises(Exception, match="LLM失败"):
            await self.agent.execute(context)


class TestAgentContextState:
    """AgentContext状态管理测试类。

    验证PlanningAgent执行过程中对AgentContext
    状态字段的正确设置和更新。
    """

    def setup_method(self, method):
        """测试方法执行前的准备工作。

        Args:
            method: 当前执行的测试方法
        """
        self.agent = PlanningAgent()
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
    async def test_context_stage_set_to_planning(self):
        """验证执行时context.current_stage被设置为planning。

        Arrange:
            - 创建默认context
            - 配置mock返回成功响应
        Act:
            - 调用agent.execute()
        Assert:
            - 验证result.current_stage == "planning"
        """
        # Arrange
        route_data = {
            "route": [
                {"step": 1, "operation": "下料", "machine": "锯床", "description": "下料"}
            ]
        }

        self.mock_llm_client.chat_completion.return_value = {
            "content": json.dumps(route_data, ensure_ascii=False),
            "model": "qwen2.5-coder:7b",
            "finish_reason": "stop"
        }

        context = AgentContextFactory()

        # Act
        result = await self.agent.execute(context)

        # Assert
        assert result.current_stage == "planning"

    @pytest.mark.asyncio
    async def test_context_preserves_other_fields(self):
        """验证执行过程中不修改context的其他字段。

        确保PlanningAgent只修改current_stage、stage_status和
        process_route，保持extracted_params等其他字段不变。

        Arrange:
            - 创建包含特定字段值的context
        Act:
            - 调用agent.execute()
        Assert:
            - 验证extracted_params、nc_code等字段保持不变
        """
        # Arrange
        route_data = {
            "route": [
                {"step": 1, "operation": "下料", "machine": "锯床", "description": "下料"}
            ]
        }

        self.mock_llm_client.chat_completion.return_value = {
            "content": json.dumps(route_data, ensure_ascii=False),
            "model": "qwen2.5-coder:7b",
            "finish_reason": "stop"
        }

        context = AgentContextFactory(
            extracted_params={"material": "45钢", "part_type": "轴类"},
            nc_code="G00 X0 Y0",
            cutting_parameters={"v": 100}
        )

        original_params = context.extracted_params.copy()
        original_nc_code = context.nc_code
        original_cutting_params = context.cutting_parameters.copy()

        # Act
        result = await self.agent.execute(context)

        # Assert
        assert result.extracted_params == original_params
        assert result.nc_code == original_nc_code
        assert result.cutting_parameters == original_cutting_params


class TestEdgeCasesAndBoundaryConditions:
    """边界情况和特殊场景测试类。

    测试PlanningAgent在特殊输入、极端参数等边界情况下的表现。
    """

    def setup_method(self, method):
        """测试方法执行前的准备工作。

        Args:
            method: 当前执行的测试方法
        """
        self.agent = PlanningAgent()
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
    async def test_special_characters_in_material(self):
        """测试材料名称包含特殊字符时的处理。

        验证当材料名称包含特殊字符（如中英文混合、符号）时，
        Agent能够正确处理。

        Arrange:
            - 配置包含特殊字符的材料名称
        Act:
            - 调用agent.execute()
        Assert:
            - 验证不引发异常
            - 验证stage_status为completed
        """
        # Arrange
        route_data = {
            "route": [
                {"step": 1, "operation": "下料", "machine": "锯床", "description": "下料"}
            ]
        }

        self.mock_llm_client.chat_completion.return_value = {
            "content": json.dumps(route_data, ensure_ascii=False),
            "model": "qwen2.5-coder:7b",
            "finish_reason": "stop"
        }

        context = AgentContextFactory()
        context.extracted_params = {
            "material": "45钢(中碳钢)",
            "part_type": "轴类"
        }

        # Act
        result = await self.agent.execute(context)

        # Assert
        assert "completed" in result.stage_status

    @pytest.mark.asyncio
    async def test_empty_route_list_handling(self):
        """测试LLM返回空工艺路线列表的处理。

        验证当LLM返回route为空列表时，
        Agent能够正确处理。

        Arrange:
            - 配置LLM mock返回空route列表
        Act:
            - 调用agent.execute()
        Assert:
            - 验证stage_status为completed
            - 验证process_route为空列表
        """
        # Arrange
        self.mock_llm_client.chat_completion.return_value = {
            "content": json.dumps({"route": []}, ensure_ascii=False),
            "model": "qwen2.5-coder:7b",
            "finish_reason": "stop"
        }

        context = AgentContextFactory(understood=True)

        # Act
        result = await self.agent.execute(context)

        # Assert
        assert "completed" in result.stage_status
        assert result.process_route == []

    @pytest.mark.asyncio
    async def test_large_route_handling(self):
        """测试处理大型工艺路线的能力。

        验证当LLM返回包含大量工序的工艺路线时，
        Agent能够正确处理。

        Arrange:
            - 配置LLM mock返回包含20道工序的路线
        Act:
            - 调用agent.execute()
        Assert:
            - 验证stage_status为completed
            - 验证process_route包含所有20道工序
        """
        # Arrange
        large_route = {
            "route": [
                {"step": i, "operation": f"工序{i}", "machine": "车床", "description": f"第{i}道工序"}
                for i in range(1, 21)
            ]
        }

        self.mock_llm_client.chat_completion.return_value = {
            "content": json.dumps(large_route, ensure_ascii=False),
            "model": "qwen2.5-coder:7b",
            "finish_reason": "stop"
        }

        context = AgentContextFactory(understood=True)

        # Act
        result = await self.agent.execute(context)

        # Assert
        assert "completed" in result.stage_status
        assert len(result.process_route) == 20
        assert result.process_route[-1]["step"] == 20
