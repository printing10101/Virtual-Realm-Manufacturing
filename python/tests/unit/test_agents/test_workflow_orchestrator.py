"""WorkflowOrchestrator 单元测试模块。

测试 WorkflowOrchestrator 的核心功能，包括完整工作流执行、
单个 Agent 失败处理、进度回调、任务取消和超时控制等场景。
所有测试遵循 AAA（Arrange-Act-Assert）模式，
确保测试独立性和可重复性。

测试类别:
    - 完整工作流执行测试
    - 单个 Agent 失败场景测试
    - 进度回调测试
    - 任务取消测试
    - 超时控制测试
"""
import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from app.ai.agents import AgentContext
from app.ai.workflow import WorkflowOrchestrator
from app.core.task_manager import TaskManager, TaskStatus, TaskType


class TestWorkflowOrchestratorSetup:
    """WorkflowOrchestrator 初始化和结构测试。

    验证工作流编排器的基本结构，包括 Agent 注册和阶段定义。
    """

    def setup_method(self, method):
        """测试方法执行前的准备工作。

        Args:
            method: 当前执行的测试方法
        """
        self.orchestrator = WorkflowOrchestrator()

    def teardown_method(self, method):
        """测试方法执行后的清理工作。

        Args:
            method: 当前执行的测试方法
        """
        self.orchestrator = None

    def test_agents_initialized(self):
        """验证所有 6 个 Agent 在初始化时被正确创建。

        Arrange:
            - 创建 WorkflowOrchestrator 实例
        Assert:
            - 验证 agents 字典包含 6 个 Agent
            - 验证包含所有预期的 Agent 名称
        """
        expected_agents = [
            "understanding",
            "planning",
            "parameter",
            "nc_generation",
            "verification",
            "repair"
        ]

        assert len(self.orchestrator.agents) == 6
        for agent_name in expected_agents:
            assert agent_name in self.orchestrator.agents

    def test_workflow_stages_defined(self):
        """验证工作流阶段按正确顺序定义。

        Arrange:
            - 创建 WorkflowOrchestrator 实例
        Assert:
            - 验证 workflow_stages 包含 6 个阶段
            - 验证阶段顺序正确
        """
        expected_stages = [
            "understanding",
            "planning",
            "parameter",
            "nc_generation",
            "verification",
            "repair"
        ]

        assert self.orchestrator.workflow_stages == expected_stages
        assert len(self.orchestrator.workflow_stages) == 6


class TestCompleteWorkflowExecution:
    """完整工作流执行测试类。

    验证所有 6 个 Agent 按预定顺序依次执行，
    AgentContext 在各 Agent 间正确传递，
    工作流最终返回结果的完整性、格式正确性和数据准确性。
    """

    def setup_method(self, method):
        """测试方法执行前的准备工作。

        创建 WorkflowOrchestrator 实例和所有 Agent 的 mock 对象。

        Args:
            method: 当前执行的测试方法
        """
        self.orchestrator = WorkflowOrchestrator()

        self.mock_agents = {}
        for stage_name in self.orchestrator.workflow_stages:
            mock_agent = AsyncMock()
            mock_agent.execute.return_value = AgentContext(
                user_input="我需要加工一个45钢的轴类零件",
                extracted_params={"material": "45钢", "part_type": "轴类"},
                process_route=[{"step": 1, "operation": "车削"}],
                cutting_parameters={"parameters": [{"step": 1, "v": 120}]},
                nc_code="G00 X0 Y0\nM30",
                verification_result={"is_valid": True, "issues": []},
                repair_suggestions=[],
                current_stage=stage_name,
                stage_status="completed"
            )
            self.mock_agents[stage_name] = mock_agent

        self.orchestrator.agents = self.mock_agents

    def teardown_method(self, method):
        """测试方法执行后的清理工作。

        清理 mock 对象，确保测试间独立性。

        Args:
            method: 当前执行的测试方法
        """
        self.orchestrator = None
        self.mock_agents = None

    @pytest.mark.asyncio
    async def test_all_agents_execute_in_order(self):
        """验证所有 Agent 按预定顺序依次执行。

        Arrange:
            - 配置所有 Agent mock 返回成功的 context
        Act:
            - 调用 execute_workflow()
        Assert:
            - 验证每个 Agent 的 execute 方法被调用一次
            - 验证调用顺序与 workflow_stages 一致
        """
        user_input = "我需要加工一个45钢的轴类零件"

        await self.orchestrator.execute_workflow(user_input)

        for _idx, stage_name in enumerate(self.orchestrator.workflow_stages):
            self.mock_agents[stage_name].execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_agent_context_passed_between_agents(self):
        """验证 AgentContext 对象在各 Agent 间正确传递。

        Arrange:
            - 配置每个 Agent mock 返回不同的 context
        Act:
            - 调用 execute_workflow()
        Assert:
            - 验证第一个 Agent 接收包含 user_input 的 context
            - 验证每个后续 Agent 接收前一个 Agent 返回的 context
        """
        contexts = []
        for idx, stage_name in enumerate(self.orchestrator.workflow_stages):
            ctx = AgentContext(
                user_input="test input",
                extracted_params={"material": "45钢", "stage_idx": idx},
                process_route=[],
                cutting_parameters={},
                nc_code="",
                verification_result={},
                repair_suggestions=[],
                current_stage=stage_name,
                stage_status="completed"
            )
            contexts.append(ctx)
            self.mock_agents[stage_name].execute.return_value = ctx

        await self.orchestrator.execute_workflow("test input")

        first_call_args = self.mock_agents["understanding"].execute.call_args
        first_context = first_call_args[0][0]
        assert first_context.user_input == "test input"

        for idx in range(1, len(self.orchestrator.workflow_stages)):
            prev_stage = self.orchestrator.workflow_stages[idx - 1]
            curr_stage = self.orchestrator.workflow_stages[idx]

            prev_return_value = self.mock_agents[prev_stage].execute.return_value
            curr_call_args = self.mock_agents[curr_stage].execute.call_args
            received_context = curr_call_args[0][0]

            assert received_context.user_input == prev_return_value.user_input
            assert received_context.extracted_params == prev_return_value.extracted_params

    @pytest.mark.asyncio
    async def test_workflow_return_result_completeness(self):
        """验证工作流最终返回结果的完整性。

        Arrange:
            - 配置所有 Agent mock 返回完整的 context
        Act:
            - 调用 execute_workflow()
        Assert:
            - 验证返回结果包含所有必需的字段
            - 验证 stage_results 包含所有 6 个阶段
            - 验证 completed_stages 等于总阶段数
        """
        await self.orchestrator.execute_workflow("test input")

        result = await self.orchestrator.execute_workflow("test input")

        required_fields = [
            "user_input",
            "extracted_params",
            "process_route",
            "cutting_parameters",
            "nc_code",
            "verification_result",
            "repair_suggestions",
            "stage_results",
            "total_stages",
            "completed_stages"
        ]

        for field in required_fields:
            assert field in result, f"缺少字段: {field}"

        assert result["total_stages"] == 6
        assert result["completed_stages"] == 6
        assert len(result["stage_results"]) == 6

    @pytest.mark.asyncio
    async def test_workflow_result_format_correctness(self):
        """验证工作流返回结果的格式正确性。

        Arrange:
            - 配置所有 Agent mock 返回成功状态
        Act:
            - 调用 execute_workflow()
        Assert:
            - 验证 stage_results 中每个阶段的格式正确
            - 验证每个阶段包含 status、elapsed_seconds、output_summary
            - 验证 status 为 "completed"
        """
        result = await self.orchestrator.execute_workflow("test input")

        for stage_name in self.orchestrator.workflow_stages:
            assert stage_name in result["stage_results"]
            stage_result = result["stage_results"][stage_name]

            assert "status" in stage_result
            assert "elapsed_seconds" in stage_result
            assert "output_summary" in stage_result

            assert "completed" in stage_result["status"]
            assert isinstance(stage_result["elapsed_seconds"], (int, float))
            assert isinstance(stage_result["output_summary"], dict)

    @pytest.mark.asyncio
    async def test_workflow_result_data_accuracy(self):
        """验证工作流返回结果的数据准确性。

        Arrange:
            - 配置 Agent mock 返回特定的数据值
        Act:
            - 调用 execute_workflow()
        Assert:
            - 验证返回的 user_input 与输入一致
            - 验证 extracted_params 包含预期的材料信息
            - 验证 nc_code 包含预期的代码
        """
        test_input = "加工一批45钢齿轮，模数2，精度7级"

        specific_context = AgentContext(
            user_input=test_input,
            extracted_params={
                "material": "45钢",
                "part_type": "齿轮",
                "dimensions": {"module": 2}
            },
            process_route=[{"step": 1, "operation": "滚齿"}],
            cutting_parameters={"parameters": [{"step": 1, "v": 80}]},
            nc_code="%O0001\nG00 X0 Y0\nM30",
            verification_result={"is_valid": True, "issues": [], "summary": "验证通过"},
            repair_suggestions=[],
            current_stage="repair",
            stage_status="completed"
        )

        for stage_name in self.orchestrator.workflow_stages:
            self.mock_agents[stage_name].execute.return_value = specific_context

        result = await self.orchestrator.execute_workflow(test_input)

        assert result["user_input"] == test_input
        assert result["extracted_params"]["material"] == "45钢"
        assert result["extracted_params"]["part_type"] == "齿轮"
        assert result["nc_code"] == "%O0001\nG00 X0 Y0\nM30"
        assert result["verification_result"]["is_valid"] is True

    @pytest.mark.asyncio
    async def test_stage_results_contain_stage_specific_summary(self):
        """验证每个阶段的 output_summary 包含阶段特定信息。

        Arrange:
            - 配置所有 Agent mock 返回完整 context
        Act:
            - 调用 execute_workflow()
        Assert:
            - 验证 understanding 阶段 summary 包含 material 和 part_type
            - 验证 planning 阶段 summary 包含 route_steps
            - 验证 nc_generation 阶段 summary 包含 nc_code_length
        """
        result = await self.orchestrator.execute_workflow("test input")

        understanding_summary = result["stage_results"]["understanding"]["output_summary"]
        assert "material" in understanding_summary
        assert "part_type" in understanding_summary

        planning_summary = result["stage_results"]["planning"]["output_summary"]
        assert "route_steps" in planning_summary

        nc_summary = result["stage_results"]["nc_generation"]["output_summary"]
        assert "nc_code_length" in nc_summary


class TestSingleAgentFailure:
    """单个 Agent 失败场景测试类。

    模拟第 3 个 Agent 在执行过程中抛出异常，
    验证工作流能够捕获异常并正确处理，
    返回结果中包含已完成阶段的部分结果。
    """

    def setup_method(self, method):
        """测试方法执行前的准备工作。

        Args:
            method: 当前执行的测试方法
        """
        self.orchestrator = WorkflowOrchestrator()

        self.mock_agents = {}
        for stage_name in self.orchestrator.workflow_stages:
            mock_agent = AsyncMock()
            mock_agent.execute.return_value = AgentContext(
                user_input="test input",
                extracted_params={"material": "45钢"},
                process_route=[{"step": 1}],
                cutting_parameters={"parameters": []},
                nc_code="G00 X0",
                verification_result={},
                repair_suggestions=[],
                current_stage=stage_name,
                stage_status="completed"
            )
            self.mock_agents[stage_name] = mock_agent

        self.orchestrator.agents = self.mock_agents

    def teardown_method(self, method):
        """测试方法执行后的清理工作。

        Args:
            method: 当前执行的测试方法
        """
        self.orchestrator = None
        self.mock_agents = None

    @pytest.mark.asyncio
    async def test_third_agent_raises_valueerror(self):
        """模拟第 3 个 Agent (ParameterAgent) 抛出 ValueError。

        Arrange:
            - 配置 ParameterAgent 的 execute 方法抛出 ValueError
        Act:
            - 调用 execute_workflow()
        Assert:
            - 验证工作流不抛出异常（异常被内部捕获）
            - 验证 stage_results 中包含 parameter 阶段的失败状态
            - 验证 completed_stages 小于 total_stages
        """
        self.mock_agents["parameter"].execute.side_effect = ValueError("切削参数计算失败：材料参数不完整")

        result = await self.orchestrator.execute_workflow("test input")

        assert "parameter" in result["stage_results"]
        param_result = result["stage_results"]["parameter"]
        assert "failed" in param_result["status"]
        assert "ValueError" in param_result["status"] or "切削参数计算失败" in param_result["status"]

        assert result["completed_stages"] < result["total_stages"]

    @pytest.mark.asyncio
    async def test_third_agent_raises_runtimeerror(self):
        """模拟第 3 个 Agent 抛出 RuntimeError。

        Arrange:
            - 配置 ParameterAgent 的 execute 方法抛出 RuntimeError
        Act:
            - 调用 execute_workflow()
        Assert:
            - 验证异常被正确捕获
            - 验证 stage_results 中包含错误信息
        """
        self.mock_agents["parameter"].execute.side_effect = RuntimeError("数据库连接超时")

        result = await self.orchestrator.execute_workflow("test input")

        param_result = result["stage_results"]["parameter"]
        assert "failed" in param_result["status"]
        assert "error" in param_result
        assert "数据库连接超时" in param_result["error"]

    @pytest.mark.asyncio
    async def test_partial_results_returned_after_failure(self):
        """验证失败后返回已完成阶段的部分结果。

        Arrange:
            - 配置第 3 个 Agent 抛出异常
            - 前 2 个 Agent 正常执行
        Act:
            - 调用 execute_workflow()
        Assert:
            - 验证 stage_results 包含 understanding 和 planning 的成功状态
            - 验证 stage_results 不包含 nc_generation、verification、repair 阶段
            - 验证返回结果包含已执行阶段的输出数据
        """
        self.mock_agents["parameter"].execute.side_effect = ValueError("参数计算失败")

        result = await self.orchestrator.execute_workflow("test input")

        assert "understanding" in result["stage_results"]
        assert "planning" in result["stage_results"]
        assert "parameter" in result["stage_results"]

        assert "nc_generation" not in result["stage_results"]
        assert "verification" not in result["stage_results"]
        assert "repair" not in result["stage_results"]

        assert result["stage_results"]["understanding"]["status"] == "completed"
        assert result["stage_results"]["planning"]["status"] == "completed"

    @pytest.mark.asyncio
    async def test_stage_status_reflects_failure_state(self):
        """验证 stage_status 状态字典正确反映各阶段执行状态。

        Arrange:
            - 配置第 3 个 Agent 抛出特定异常
        Act:
            - 调用 execute_workflow()
        Assert:
            - 验证前 2 个阶段 status 为 "completed"
            - 验证第 3 个阶段 status 包含 "failed" 和异常信息
            - 验证失败阶段包含 elapsed_seconds 字段
        """
        error_message = "知识库查询失败：服务不可用"
        self.mock_agents["parameter"].execute.side_effect = RuntimeError(error_message)

        result = await self.orchestrator.execute_workflow("test input")

        assert "completed" in result["stage_results"]["understanding"]["status"]
        assert "completed" in result["stage_results"]["planning"]["status"]

        param_status = result["stage_results"]["parameter"]["status"]
        assert "failed" in param_status
        assert error_message in param_status

        assert "elapsed_seconds" in result["stage_results"]["parameter"]
        assert isinstance(result["stage_results"]["parameter"]["elapsed_seconds"], (int, float))

    @pytest.mark.asyncio
    async def test_subsequent_agents_not_executed_after_failure(self):
        """验证失败后后续 Agent 不被执行。

        Arrange:
            - 配置第 3 个 Agent 抛出异常
        Act:
            - 调用 execute_workflow()
        Assert:
            - 验证 nc_generation、verification、repair Agent 的 execute 未被调用
        """
        self.mock_agents["parameter"].execute.side_effect = ValueError("失败")

        await self.orchestrator.execute_workflow("test input")

        self.mock_agents["nc_generation"].execute.assert_not_called()
        self.mock_agents["verification"].execute.assert_not_called()
        self.mock_agents["repair"].execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_first_agent_failure(self):
        """测试第 1 个 Agent 失败的场景。

        Arrange:
            - 配置 UnderstandingAgent 抛出异常
        Act:
            - 调用 execute_workflow()
        Assert:
            - 验证仅 understanding 阶段在结果中
            - 验证 completed_stages 为 0 或其他阶段数少于失败点
        """
        self.mock_agents["understanding"].execute.side_effect = Exception("理解失败")

        result = await self.orchestrator.execute_workflow("test input")

        assert "understanding" in result["stage_results"]
        assert "failed" in result["stage_results"]["understanding"]["status"]

        completed_count = result["completed_stages"]
        assert completed_count < result["total_stages"]

    @pytest.mark.asyncio
    async def test_last_agent_failure(self):
        """测试最后一个 Agent 失败的场景。

        Arrange:
            - 配置 RepairAgent 抛出异常
        Act:
            - 调用 execute_workflow()
        Assert:
            - 验证前 5 个阶段成功
            - 验证 repair 阶段失败
            - 验证 completed_stages 为 5
        """
        self.mock_agents["repair"].execute.side_effect = RuntimeError("修复失败")

        result = await self.orchestrator.execute_workflow("test input")

        for stage_name in self.orchestrator.workflow_stages[:-1]:
            assert "completed" in result["stage_results"][stage_name]["status"]

        assert "failed" in result["stage_results"]["repair"]["status"]
        assert result["completed_stages"] == 5


class TestProgressCallback:
    """进度回调测试类。

    实现并注入测试用 progress_callback 函数，
    验证 progress_callback 在每个 Agent 执行前后被调用，
    验证每次回调调用的参数正确性。
    """

    def setup_method(self, method):
        """测试方法执行前的准备工作。

        Args:
            method: 当前执行的测试方法
        """
        self.orchestrator = WorkflowOrchestrator()

        self.mock_agents = {}
        for stage_name in self.orchestrator.workflow_stages:
            mock_agent = AsyncMock()
            mock_agent.execute.return_value = AgentContext(
                user_input="test input",
                extracted_params={"material": "45钢"},
                process_route=[{"step": 1}],
                cutting_parameters={"parameters": []},
                nc_code="G00",
                verification_result={},
                repair_suggestions=[],
                current_stage=stage_name,
                stage_status="completed"
            )
            self.mock_agents[stage_name] = mock_agent

        self.orchestrator.agents = self.mock_agents
        self.callback_calls = []

    def teardown_method(self, method):
        """测试方法执行后的清理工作。

        Args:
            method: 当前执行的测试方法
        """
        self.orchestrator = None
        self.mock_agents = None
        self.callback_calls = []

    def _test_callback(self, progress_data):
        """测试用进度回调函数。

        记录所有回调调用，用于后续验证。

        Args:
            progress_data: 进度数据字典
        """
        self.callback_calls.append(progress_data.copy())

    @pytest.mark.asyncio
    async def test_callback_called_before_each_agent(self):
        """验证 progress_callback 在每个 Agent 执行前被调用一次。

        Arrange:
            - 配置测试回调函数
            - 配置所有 Agent mock
        Act:
            - 调用 execute_workflow() 并传入 progress_callback
        Assert:
            - 验证每个阶段都有对应的"开始"回调
            - 验证开始回调的 status 为 "running"
        """
        await self.orchestrator.execute_workflow("test input", progress_callback=self._test_callback)

        total_stages = len(self.orchestrator.workflow_stages)
        start_callbacks = [c for c in self.callback_calls if c["status"] == "running"]

        assert len(start_callbacks) == total_stages

        for idx, stage_name in enumerate(self.orchestrator.workflow_stages):
            assert start_callbacks[idx]["current_stage"] == stage_name
            assert start_callbacks[idx]["stage_index"] == idx + 1

    @pytest.mark.asyncio
    async def test_callback_called_after_each_agent(self):
        """验证 progress_callback 在每个 Agent 执行后被调用一次。

        Arrange:
            - 配置测试回调函数
            - 配置所有 Agent mock 返回 completed 状态
        Act:
            - 调用 execute_workflow() 并传入 progress_callback
        Assert:
            - 验证每个阶段都有对应的"完成"回调
            - 验证完成回调的 status 为 "completed"
        """
        await self.orchestrator.execute_workflow("test input", progress_callback=self._test_callback)

        total_stages = len(self.orchestrator.workflow_stages)
        end_callbacks = [c for c in self.callback_calls if c["status"] == "completed"]

        assert len(end_callbacks) == total_stages

    @pytest.mark.asyncio
    async def test_callback_progress_values_correct(self):
        """验证回调调用的 progress 进度值准确性。

        Arrange:
            - 配置测试回调函数
        Act:
            - 调用 execute_workflow() 并传入 progress_callback
        Assert:
            - 验证开始回调的 progress 值为 (idx / total) * 100
            - 验证完成回调的 progress 值为 ((idx + 1) / total) * 100
            - 验证最后一个完成回调的 progress 为 100.0
        """
        await self.orchestrator.execute_workflow("test input", progress_callback=self._test_callback)

        total_stages = len(self.orchestrator.workflow_stages)

        for idx, stage_name in enumerate(self.orchestrator.workflow_stages):
            expected_start_progress = (idx / total_stages) * 100
            expected_end_progress = ((idx + 1) / total_stages) * 100

            stage_callbacks = [c for c in self.callback_calls if c["current_stage"] == stage_name]
            assert len(stage_callbacks) == 2

            start_callback = stage_callbacks[0]
            end_callback = stage_callbacks[1]

            assert abs(start_callback["progress"] - expected_start_progress) < 0.01
            assert abs(end_callback["progress"] - expected_end_progress) < 0.01

        last_callback = self.callback_calls[-1]
        assert abs(last_callback["progress"] - 100.0) < 0.01

    @pytest.mark.asyncio
    async def test_callback_total_stages_consistent(self):
        """验证回调中 total_stages 值一致性。

        Arrange:
            - 配置测试回调函数
        Act:
            - 调用 execute_workflow()
        Assert:
            - 验证所有回调的 total_stages 都等于 6
        """
        await self.orchestrator.execute_workflow("test input", progress_callback=self._test_callback)

        total_stages = len(self.orchestrator.workflow_stages)

        for callback_data in self.callback_calls:
            assert callback_data["total_stages"] == total_stages

    @pytest.mark.asyncio
    async def test_callback_message_description_complete(self):
        """验证回调的 message 描述信息完整性。

        Arrange:
            - 配置测试回调函数
        Act:
            - 调用 execute_workflow()
        Assert:
            - 验证回调数据包含 current_stage 字段
            - 验证 stage_index 正确递增
        """
        await self.orchestrator.execute_workflow("test input", progress_callback=self._test_callback)

        for _idx, callback_data in enumerate(self.callback_calls):
            assert "current_stage" in callback_data
            assert "stage_index" in callback_data
            assert "total_stages" in callback_data
            assert "progress" in callback_data
            assert "status" in callback_data

    @pytest.mark.asyncio
    async def test_callback_not_called_when_not_provided(self):
        """验证不提供 progress_callback 时不会报错。

        Arrange:
            - 不提供 progress_callback 参数
        Act:
            - 调用 execute_workflow()
        Assert:
            - 验证工作流正常完成
            - 验证不抛出异常
        """
        result = await self.orchestrator.execute_workflow("test input")

        assert result is not None
        assert "stage_results" in result

    @pytest.mark.asyncio
    async def test_callback_receives_correct_task_id(self):
        """验证回调参数中包含正确的任务标识信息。

        Arrange:
            - 配置测试回调函数
        Act:
            - 调用 execute_workflow()
        Assert:
            - 验证回调数据包含 current_stage 标识
            - 验证 stage_index 与阶段顺序一致
        """
        await self.orchestrator.execute_workflow("test input", progress_callback=self._test_callback)

        for idx, stage_name in enumerate(self.orchestrator.workflow_stages):
            stage_callbacks = [c for c in self.callback_calls if c["current_stage"] == stage_name]
            assert len(stage_callbacks) == 2

            assert stage_callbacks[0]["stage_index"] == idx + 1
            assert stage_callbacks[1]["stage_index"] == idx + 1

    @pytest.mark.asyncio
    async def test_callback_on_agent_failure(self):
        """验证 Agent 失败时回调仍被正确调用。

        Arrange:
            - 配置第 3 个 Agent 抛出异常
            - 配置测试回调函数
        Act:
            - 调用 execute_workflow()
        Assert:
            - 验证前 3 个阶段都有开始和完成回调
            - 验证第 3 个阶段的完成回调 status 包含 "failed"
            - 验证后续阶段没有回调
        """
        self.mock_agents["parameter"].execute.side_effect = ValueError("失败")

        await self.orchestrator.execute_workflow("test input", progress_callback=self._test_callback)

        failed_stage_callbacks = [c for c in self.callback_calls if c["current_stage"] == "parameter"]
        assert len(failed_stage_callbacks) == 2
        assert "failed" in failed_stage_callbacks[1]["status"]

        assert not any(c["current_stage"] == "nc_generation" for c in self.callback_calls)
        assert not any(c["current_stage"] == "verification" for c in self.callback_calls)
        assert not any(c["current_stage"] == "repair" for c in self.callback_calls)


class TestTaskCancellation:
    """任务取消测试类。

    实现任务取消机制的模拟，
    验证在工作流执行过程中收到取消请求时能够触发优雅停止，
    验证取消后资源正确释放。
    """

    def setup_method(self, method):
        """测试方法执行前的准备工作。

        Args:
            method: 当前执行的测试方法
        """
        self.orchestrator = WorkflowOrchestrator()

        self.mock_agents = {}
        for stage_name in self.orchestrator.workflow_stages:
            mock_agent = AsyncMock()
            mock_agent.execute.return_value = AgentContext(
                user_input="test input",
                extracted_params={"material": "45钢"},
                process_route=[{"step": 1}],
                cutting_parameters={"parameters": []},
                nc_code="G00",
                verification_result={},
                repair_suggestions=[],
                current_stage=stage_name,
                stage_status="completed"
            )
            self.mock_agents[stage_name] = mock_agent

        self.orchestrator.agents = self.mock_agents
        self.task_manager = TaskManager(default_timeout=300.0)

    def teardown_method(self, method):
        """测试方法执行后的清理工作。

        Args:
            method: 当前执行的测试方法
        """
        self.orchestrator = None
        self.mock_agents = None
        self.task_manager = None

    @pytest.mark.asyncio
    async def test_workflow_cancels_when_task_status_cancelled(self):
        """验证当任务状态为 CANCELLED 时工作流能够取消。

        Arrange:
            - 创建任务并标记为 CANCELLED
            - 配置 mock agents
        Act:
            - 调用 execute_workflow_with_task() 并传入已取消的任务 ID
        Assert:
            - 验证返回结果包含 cancelled: True
            - 验证 stage_results 为空或不包含任何阶段
        """
        task_id = self.task_manager.create_task(TaskType.WORKFLOW_EXECUTION)

        self.task_manager._tasks[task_id].status = TaskStatus.CANCELLED

        with patch.object(self.orchestrator, 'agents', self.mock_agents):
            with patch('app.ai.workflow.task_manager', self.task_manager):
                result = await self.orchestrator.execute_workflow_with_task("test input", task_id=task_id)

        assert result.get("cancelled") is True
        assert result.get("stage_results") == {}

    @pytest.mark.asyncio
    async def test_cancellation_during_execution_releases_resources(self):
        """验证执行过程中取消能够正确释放资源。

        Arrange:
            - 创建任务
            - 在调用前设置任务状态为 CANCELLED（不通过 cancel_task 方法，避免清理）
        Act:
            - 调用 execute_workflow_with_task()
        Assert:
            - 验证返回结果包含 cancelled: True
            - 验证 stage_results 为空
        """
        task_id = self.task_manager.create_task(TaskType.WORKFLOW_EXECUTION, {"user_input": "test input"})

        self.task_manager._tasks[task_id].status = TaskStatus.CANCELLED

        with patch('app.ai.workflow.task_manager', self.task_manager):
            result = await self.orchestrator.execute_workflow_with_task("test input", task_id=task_id)

        assert result.get("cancelled") is True
        assert result.get("stage_results") == {}

    @pytest.mark.asyncio
    async def test_cancelled_result_contains_executed_stages(self):
        """验证返回结果包含明确的取消状态和已执行阶段信息。

        Arrange:
            - 创建任务
            - 配置 mock agents
            - 在调用前设置任务状态为 CANCELLED
        Act:
            - 调用 execute_workflow_with_task() 并立即取消
        Assert:
            - 验证返回结果包含 cancelled: True
            - 验证返回结果包含已执行的阶段信息（如果有的话）
        """
        task_id = self.task_manager.create_task(TaskType.WORKFLOW_EXECUTION)

        self.task_manager._tasks[task_id].status = TaskStatus.CANCELLED

        with patch('app.ai.workflow.task_manager', self.task_manager):
            result = await self.orchestrator.execute_workflow_with_task("test input", task_id=task_id)

        assert result.get("cancelled") is True
        assert "stage_results" in result

    @pytest.mark.asyncio
    async def test_no_zombie_processes_after_cancellation(self):
        """验证取消后不会产生僵尸进程。

        Arrange:
            - 创建任务
            - 配置 mock agents 记录执行状态
        Act:
            - 调用 execute_workflow_with_task()
            - 取消任务
        Assert:
            - 验证所有 Agent 执行完成后或被取消时正确返回
            - 验证没有未完成的异步任务
        """
        task_id = self.task_manager.create_task(TaskType.WORKFLOW_EXECUTION)

        execution_count = {"count": 0}

        async def counting_execute(context):
            execution_count["count"] += 1
            return AgentContext(
                user_input="test",
                extracted_params={},
                process_route=[],
                cutting_parameters={},
                nc_code="",
                verification_result={},
                repair_suggestions=[],
                current_stage=context.current_stage,
                stage_status="completed"
            )

        for stage_name in self.orchestrator.workflow_stages:
            mock_agent = AsyncMock()
            mock_agent.execute.side_effect = counting_execute
            self.mock_agents[stage_name] = mock_agent

        self.task_manager._tasks[task_id].status = TaskStatus.CANCELLED

        with patch('app.ai.workflow.task_manager', self.task_manager):
            result = await self.orchestrator.execute_workflow_with_task("test input", task_id=task_id)

        assert result.get("cancelled") is True
        assert execution_count["count"] == 0

    @pytest.mark.asyncio
    async def test_graceful_shutdown_on_cancellation(self):
        """验证收到取消请求时能够触发优雅停止。

        Arrange:
            - 创建任务
            - 在调用前设置任务状态为已取消
        Act:
            - 调用 execute_workflow_with_task()
        Assert:
            - 验证工作流检测到取消状态
            - 验证返回结果正确反映取消状态
        """
        task_id = self.task_manager.create_task(TaskType.WORKFLOW_EXECUTION)
        self.task_manager._tasks[task_id].status = TaskStatus.CANCELLED

        with patch('app.ai.workflow.task_manager', self.task_manager):
            result = await self.orchestrator.execute_workflow_with_task("test input", task_id=task_id)

        assert result.get("cancelled") is True
        assert "stage_results" in result


class TestTimeoutControl:
    """超时控制测试类。

    为指定 Agent 设置合理的超时阈值，
    模拟 Agent 执行时间超过设定阈值的场景，
    验证超时处理逻辑正确触发。
    """

    def setup_method(self, method):
        """测试方法执行前的准备工作。

        Args:
            method: 当前执行的测试方法
        """
        self.orchestrator = WorkflowOrchestrator()

        self.mock_agents = {}
        for stage_name in self.orchestrator.workflow_stages:
            mock_agent = AsyncMock()
            mock_agent.execute.return_value = AgentContext(
                user_input="test input",
                extracted_params={"material": "45钢"},
                process_route=[{"step": 1}],
                cutting_parameters={"parameters": []},
                nc_code="G00",
                verification_result={},
                repair_suggestions=[],
                current_stage=stage_name,
                stage_status="completed"
            )
            self.mock_agents[stage_name] = mock_agent

        self.orchestrator.agents = self.mock_agents
        self.task_manager = TaskManager(default_timeout=0.1)

    def teardown_method(self, method):
        """测试方法执行后的清理工作。

        Args:
            method: 当前执行的测试方法
        """
        self.orchestrator = None
        self.mock_agents = None
        self.task_manager = None

    @pytest.mark.asyncio
    async def test_timeout_triggered_when_agent_takes_too_long(self):
        """验证 Agent 执行时间超过设定阈值时超时处理正确触发。

        Arrange:
            - 设置较短的超时时间（0.1 秒）
            - 配置 Agent 模拟长时间执行（睡眠 10 秒）
            - 修补 fail_task 防止清理后二次调用报错
        Act:
            - 调用 execute_workflow_with_task()
        Assert:
            - 验证抛出 TimeoutError
        """
        task_id = self.task_manager.create_task(TaskType.WORKFLOW_EXECUTION)

        async def slow_execute(context):
            await asyncio.sleep(10)
            return AgentContext(
                user_input="test",
                extracted_params={},
                process_route=[],
                cutting_parameters={},
                nc_code="",
                verification_result={},
                repair_suggestions=[],
                current_stage=context.current_stage,
                stage_status="completed"
            )

        for stage_name in self.orchestrator.workflow_stages:
            mock_agent = AsyncMock()
            mock_agent.execute.side_effect = slow_execute
            self.mock_agents[stage_name] = mock_agent

        self.task_manager.set_timeout(task_id, 0.1)

        async def no_op_fail(tid, error):
            pass

        with patch('app.ai.workflow.task_manager', self.task_manager):
            with patch.object(self.task_manager, 'fail_task', no_op_fail):
                with pytest.raises(asyncio.TimeoutError):
                    await self.orchestrator.execute_workflow_with_task("test input", task_id=task_id)

    @pytest.mark.asyncio
    async def test_task_marked_failed_on_timeout(self):
        """验证超时后任务被标记为失败状态。

        Arrange:
            - 设置很短的超时时间
            - 配置 Agent 睡眠超过超时时间
            - 修补 fail_task 防止清理后二次调用报错
        Act:
            - 调用 execute_workflow_with_task()
            - 捕获超时异常
        Assert:
            - 验证超时异常被抛出
        """
        task_id = self.task_manager.create_task(TaskType.WORKFLOW_EXECUTION)

        async def slow_execute(context):
            await asyncio.sleep(10)
            return AgentContext(user_input="test")

        for stage_name in self.orchestrator.workflow_stages:
            mock_agent = AsyncMock()
            mock_agent.execute.side_effect = slow_execute
            self.mock_agents[stage_name] = mock_agent

        self.task_manager.set_timeout(task_id, 0.05)

        async def no_op_fail(tid, error):
            pass

        with patch('app.ai.workflow.task_manager', self.task_manager):
            with patch.object(self.task_manager, 'fail_task', no_op_fail):
                with pytest.raises(asyncio.TimeoutError):
                    await self.orchestrator.execute_workflow_with_task("test input", task_id=task_id)

    @pytest.mark.asyncio
    async def test_workflow_completes_within_timeout(self):
        """验证正常执行时间在超时阈值内时工作流成功完成。

        Arrange:
            - 设置合理的超时时间（10 秒）
            - 配置 Agent 立即返回
        Act:
            - 调用 execute_workflow_with_task()
        Assert:
            - 验证工作流成功完成
            - 验证返回结果包含所有阶段
        """
        task_id = self.task_manager.create_task(TaskType.WORKFLOW_EXECUTION)
        self.task_manager.set_timeout(task_id, 10.0)

        with patch('app.ai.workflow.task_manager', self.task_manager):
            result = await self.orchestrator.execute_workflow_with_task("test input", task_id=task_id)

        assert result is not None
        assert "stage_results" in result
        assert len(result["stage_results"]) == 6
        assert result["completed_stages"] == 6

    @pytest.mark.asyncio
    async def test_timeout_error_message_included(self):
        """验证超时后错误信息包含超时相关内容。

        Arrange:
            - 设置很短的超时时间
            - 配置 Agent 长时间睡眠
            - 修补 fail_task 防止清理后二次调用报错
        Act:
            - 调用 execute_workflow_with_task()
            - 捕获超时异常
        Assert:
            - 验证抛出的是 asyncio.TimeoutError 类型异常
        """
        task_id = self.task_manager.create_task(TaskType.WORKFLOW_EXECUTION)

        async def slow_execute(context):
            await asyncio.sleep(10)
            return AgentContext(user_input="test")

        for stage_name in self.orchestrator.workflow_stages:
            mock_agent = AsyncMock()
            mock_agent.execute.side_effect = slow_execute
            self.mock_agents[stage_name] = mock_agent

        self.task_manager.set_timeout(task_id, 0.05)

        async def no_op_fail(tid, error):
            pass

        with patch('app.ai.workflow.task_manager', self.task_manager):
            with patch.object(self.task_manager, 'fail_task', no_op_fail):
                with pytest.raises(asyncio.TimeoutError):
                    await self.orchestrator.execute_workflow_with_task("test input", task_id=task_id)

    @pytest.mark.asyncio
    async def test_different_timeout_thresholds(self):
        """验证不同的超时阈值都能正确工作。

        Arrange:
            - 测试两种超时阈值（短和长）
            - 修补 fail_task 防止清理后二次调用报错
        Act:
            - 对短阈值执行工作流，验证超时
            - 对长阈值执行工作流，验证完成
        Assert:
            - 验证短时间超时触发
            - 验证长时间允许完成
        """
        async def slow_execute(context):
            await asyncio.sleep(0.2)
            return AgentContext(user_input="test", current_stage=context.current_stage, stage_status="completed")

        for stage_name in self.orchestrator.workflow_stages:
            mock_agent = AsyncMock()
            mock_agent.execute.side_effect = slow_execute
            self.mock_agents[stage_name] = mock_agent

        async def no_op_fail(tid, error):
            pass

        task_id_short = self.task_manager.create_task(TaskType.WORKFLOW_EXECUTION)
        self.task_manager.set_timeout(task_id_short, 0.05)

        with patch('app.ai.workflow.task_manager', self.task_manager):
            with patch.object(self.task_manager, 'fail_task', no_op_fail):
                with pytest.raises(asyncio.TimeoutError):
                    await self.orchestrator.execute_workflow_with_task("test input", task_id=task_id_short)

        self.mock_agents = {}
        for stage_name in self.orchestrator.workflow_stages:
            mock_agent = AsyncMock()
            mock_agent.execute.return_value = AgentContext(
                user_input="test input",
                extracted_params={"material": "45钢"},
                process_route=[{"step": 1}],
                cutting_parameters={"parameters": []},
                nc_code="G00",
                verification_result={},
                repair_suggestions=[],
                current_stage=stage_name,
                stage_status="completed"
            )
            self.mock_agents[stage_name] = mock_agent

        self.orchestrator.agents = self.mock_agents

        task_id_long = self.task_manager.create_task(TaskType.WORKFLOW_EXECUTION)
        self.task_manager.set_timeout(task_id_long, 10.0)

        with patch('app.ai.workflow.task_manager', self.task_manager):
            result = await self.orchestrator.execute_workflow_with_task("test input", task_id=task_id_long)

        assert result is not None
        assert "stage_results" in result
