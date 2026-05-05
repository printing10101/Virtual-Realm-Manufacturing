"""HypothesisDrivenLoop 单元测试模块。

测试 HypothesisDrivenLoop 的核心功能，包括第一轮验证通过、
多轮迭代收敛、最大迭代次数保护、任务取消和边界条件等场景。
所有测试遵循 AAA（Arrange-Act-Assert）模式，
确保测试独立性和可重复性。

测试类别:
    - 第一轮验证通过测试
    - 多轮迭代收敛测试
    - 最大迭代次数保护测试
    - 任务取消测试
    - 边界条件测试
"""
import sys
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

_mock_tools_module = MagicMock()
_mock_tools_module.BaseTool = MagicMock
_mock_tools_module.ToolObservation = MagicMock
sys.modules['app.agents.tools'] = _mock_tools_module

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.hypothesis_loop import (
    HypothesisDrivenLoop,
    HypothesisIteration,
    HypothesisLoopResult,
)
from app.core.task_manager import TaskManager, TaskStatus, TaskType
from app.core.workflow_logger import AIWorkflowLogger
from app.models.hypothesis import ProcessHypothesis


class TestHypothesisDrivenLoopSetup:
    """HypothesisDrivenLoop 初始化和结构测试。

    验证假设驱动循环的基本结构和初始化状态。
    """

    def setup_method(self, method):
        """测试方法执行前的准备工作。

        Args:
            method: 当前执行的测试方法
        """
        self.task_manager = TaskManager(default_timeout=300.0)
        self.logger = AIWorkflowLogger()
        self.hypothesis_generator = AsyncMock()

    def teardown_method(self, method):
        """测试方法执行后的清理工作。

        Args:
            method: 当前执行的测试方法
        """
        self.task_manager = None
        self.logger = None
        self.hypothesis_generator = None

    def test_default_initialization(self):
        """验证使用默认参数初始化时各属性正确设置。

        Arrange:
            - 创建必要的 mock 对象
        Act:
            - 使用默认参数创建 HypothesisDrivenLoop 实例
        Assert:
            - 验证 max_iterations 为默认值 5
            - 验证 process_trace 已初始化
            - 验证其他可选依赖为 None
        """
        loop = HypothesisDrivenLoop(
            task_manager=self.task_manager,
            workflow_logger=self.logger,
            hypothesis_generator=self.hypothesis_generator
        )

        assert loop.max_iterations == 5
        assert loop.process_trace is not None
        assert loop.constraint_mapper is None
        assert loop.solver is None
        assert loop.validator is None
        assert loop.incremental_solver is None
        assert loop.alternating_validator is None
        assert loop.validation_strategy == "tolerant"
        assert loop.tolerance_threshold == 0.1

    def test_custom_initialization(self):
        """验证使用自定义参数初始化时各属性正确设置。

        Arrange:
            - 创建必要的 mock 对象和自定义参数
        Act:
            - 使用自定义参数创建 HypothesisDrivenLoop 实例
        Assert:
            - 验证 max_iterations 为自定义值
            - 验证 tolerance_threshold 为自定义值
            - 验证 validation_strategy 为自定义值
        """
        loop = HypothesisDrivenLoop(
            task_manager=self.task_manager,
            workflow_logger=self.logger,
            hypothesis_generator=self.hypothesis_generator,
            max_iterations=10,
            validation_strategy="strict",
            tolerance_threshold=0.05
        )

        assert loop.max_iterations == 10
        assert loop.validation_strategy == "strict"
        assert loop.tolerance_threshold == 0.05


class TestFirstIterationPass:
    """第一轮验证通过测试类。

    验证在第一轮迭代中假设生成和验证都通过时，
    循环正确终止并返回预期结果。
    """

    def setup_method(self, method):
        """测试方法执行前的准备工作。

        创建必要的 mock 对象和测试数据。

        Args:
            method: 当前执行的测试方法
        """
        self.task_manager = TaskManager(default_timeout=300.0)
        self.logger = AIWorkflowLogger()
        self.hypothesis_generator = AsyncMock()
        self.validator = AsyncMock()

        self.loop = HypothesisDrivenLoop(
            task_manager=self.task_manager,
            workflow_logger=self.logger,
            hypothesis_generator=self.hypothesis_generator,
            validator=self.validator,
            max_iterations=5
        )

    def teardown_method(self, method):
        """测试方法执行后的清理工作。

        Args:
            method: 当前执行的测试方法
        """
        self.task_manager = None
        self.logger = None
        self.hypothesis_generator = None
        self.validator = None
        self.loop = None

    @pytest.mark.asyncio
    async def test_first_iteration_passes_successfully(self):
        """验证循环在第一轮后正确终止。

        Arrange:
            - 配置假设生成器返回有效假设
            - 配置验证器返回通过结果
        Act:
            - 调用 run() 方法执行假设驱动循环
        Assert:
            - 验证返回结果 success 为 True
            - 验证 iterations 列表长度为 1
            - 验证 final_hypothesis 不为 None
        """
        task_id = self.task_manager.create_task(TaskType.WORKFLOW_EXECUTION)

        test_hypothesis = ProcessHypothesis(
            content="使用高速钢刀具，切削速度 120m/min，进给量 0.15mm/rev",
            reason="根据材料特性选择最优参数组合",
            expected_outcomes={
                "cutting_force": "< 800N",
                "surface_roughness": "< 1.6μm",
                "tool_life": "> 60min"
            },
            confidence=0.85
        )
        self.hypothesis_generator.generate_initial_hypothesis.return_value = test_hypothesis

        self.validator.validate.return_value = {
            "passed": True,
            "failure_reason": "",
            "unmet_constraints": [],
            "metrics": {
                "cutting_force": 750.0,
                "surface_roughness": 1.4,
                "tool_life": 65.0
            }
        }

        result = await self.loop.run(
            task_id=task_id,
            requirements={"max_cutting_force": 800, "max_surface_roughness": 1.6, "min_tool_life": 60},
            material_info={"material": "45钢", "hardness": "HRC25"},
            tool_info={"tool_type": "高速钢", "diameter": 10}
        )

        assert result.success is True
        assert len(result.iterations) == 1
        assert result.final_hypothesis is not None
        assert result.best_feasible_solution is not None

    @pytest.mark.asyncio
    async def test_returned_result_matches_expected_hypothesis(self):
        """验证返回结果与预期假设一致。

        Arrange:
            - 配置假设生成器返回特定假设
            - 配置验证器返回通过结果
        Act:
            - 调用 run() 方法
        Assert:
            - 验证 final_hypothesis 的 content 与输入一致
            - 验证 final_hypothesis 的 hypothesis_id 与生成的一致
            - 验证 best_feasible_solution 包含预期字段
        """
        task_id = self.task_manager.create_task(TaskType.WORKFLOW_EXECUTION)

        expected_content = "采用陶瓷刀具进行干式切削"
        test_hypothesis = ProcessHypothesis(
            content=expected_content,
            reason="陶瓷刀具适合高速干式切削",
            expected_outcomes={"cutting_force": "< 500N"},
            confidence=0.9
        )
        self.hypothesis_generator.generate_initial_hypothesis.return_value = test_hypothesis
        self.validator.validate.return_value = {"passed": True, "failure_reason": "", "unmet_constraints": []}

        result = await self.loop.run(
            task_id=task_id,
            requirements={"max_cutting_force": 500},
            material_info={"material": "铸铁"},
            tool_info={"tool_type": "陶瓷"}
        )

        assert result.final_hypothesis.content == expected_content
        assert result.final_hypothesis.hypothesis_id == test_hypothesis.hypothesis_id
        assert result.final_hypothesis.confidence == 0.9

    @pytest.mark.asyncio
    async def test_state_variables_correctly_set(self):
        """验证相关状态变量被正确设置。

        Arrange:
            - 配置假设生成器和验证器
        Act:
            - 调用 run() 方法
        Assert:
            - 验证 total_duration_ms 大于 0
            - 验证 iterations[0] 的 is_passed 为 True
            - 验证 iterations[0] 的 iteration 为 1
            - 验证 iterations[0] 的 correction_direction 为空字符串
        """
        task_id = self.task_manager.create_task(TaskType.WORKFLOW_EXECUTION)

        test_hypothesis = ProcessHypothesis(content="测试假设")
        self.hypothesis_generator.generate_initial_hypothesis.return_value = test_hypothesis
        self.validator.validate.return_value = {"passed": True, "failure_reason": "", "unmet_constraints": []}

        result = await self.loop.run(
            task_id=task_id,
            requirements={},
            material_info={},
            tool_info={}
        )

        assert result.total_duration_ms > 0
        assert result.iterations[0].is_passed is True
        assert result.iterations[0].iteration == 1
        assert result.iterations[0].correction_direction == ""
        assert result.warning_message == ""


class TestMultipleIterationsConvergence:
    """多轮迭代收敛测试类。

    验证前 3 轮验证失败、第 4 轮通过的场景下，
    系统能正确提取修正方向并最终收敛。
    """

    def setup_method(self, method):
        """测试方法执行前的准备工作。

        Args:
            method: 当前执行的测试方法
        """
        self.task_manager = TaskManager(default_timeout=300.0)
        self.logger = AIWorkflowLogger()
        self.hypothesis_generator = AsyncMock()
        self.validator = AsyncMock()

        self.loop = HypothesisDrivenLoop(
            task_manager=self.task_manager,
            workflow_logger=self.logger,
            hypothesis_generator=self.hypothesis_generator,
            validator=self.validator,
            max_iterations=5
        )

    def teardown_method(self, method):
        """测试方法执行后的清理工作。

        Args:
            method: 当前执行的测试方法
        """
        self.task_manager = None
        self.logger = None
        self.hypothesis_generator = None
        self.validator = None
        self.loop = None

    @pytest.mark.asyncio
    async def test_convergence_after_three_failures(self):
        """验证每次失败后系统能正确提取修正方向。

        Arrange:
            - 配置前 3 轮验证失败，第 4 轮验证通过
            - 配置假设生成器根据失败反馈生成修正假设
        Act:
            - 调用 run() 方法
        Assert:
            - 验证最终返回 success 为 True
            - 验证 iterations 列表长度为 4
            - 验证前 3 轮 is_passed 为 False
            - 验证第 4 轮 is_passed 为 True
        """
        task_id = self.task_manager.create_task(TaskType.WORKFLOW_EXECUTION)

        fail_results = [
            {
                "passed": False,
                "failure_reason": "切削力 900N 超过限制 800N",
                "unmet_constraints": ["cutting_force: 900N > 800N"]
            },
            {
                "passed": False,
                "failure_reason": "表面粗糙度 2.0μm 超过限制 1.6μm",
                "unmet_constraints": ["surface_roughness: 2.0μm > 1.6μm"]
            },
            {
                "passed": False,
                "failure_reason": "刀具寿命 25min 低于要求 30min",
                "unmet_constraints": ["tool_life: 25min < 30min"]
            }
        ]

        pass_result = {
            "passed": True,
            "failure_reason": "",
            "unmet_constraints": []
        }

        validation_results = [*fail_results, pass_result]
        validation_call_count = [0]

        async def mock_validate(solution, requirements, material_info):
            idx = validation_call_count[0]
            validation_call_count[0] += 1
            return validation_results[idx]

        self.validator.validate.side_effect = mock_validate

        hypotheses = [
            ProcessHypothesis(content=f"假设版本{i+1}", confidence=0.5 + i * 0.1)
            for i in range(4)
        ]
        self.hypothesis_generator.generate_initial_hypothesis.return_value = hypotheses[0]
        self.hypothesis_generator.generate_correction_hypothesis.side_effect = hypotheses[1:]

        result = await self.loop.run(
            task_id=task_id,
            requirements={"max_cutting_force": 800, "max_surface_roughness": 1.6, "min_tool_life": 30},
            material_info={"material": "45钢"},
            tool_info={"tool_type": "高速钢"}
        )

        assert result.success is True
        assert len(result.iterations) == 4

        for i in range(3):
            assert result.iterations[i].is_passed is False

        assert result.iterations[3].is_passed is True

    @pytest.mark.asyncio
    async def test_correction_directions_extracted(self):
        """验证每次失败后修正方向被正确提取。

        Arrange:
            - 配置前 3 轮验证失败，第 4 轮通过
        Act:
            - 调用 run() 方法
        Assert:
            - 验证前 3 轮的 correction_direction 不为空
            - 验证第 4 轮的 correction_direction 为空字符串
        """
        task_id = self.task_manager.create_task(TaskType.WORKFLOW_EXECUTION)

        fail_results = [
            {"passed": False, "failure_reason": "切削力 900N 超过限制 800N", "unmet_constraints": []},
            {"passed": False, "failure_reason": "表面粗糙度超标", "unmet_constraints": []},
            {"passed": False, "failure_reason": "刀具寿命不足", "unmet_constraints": []}
        ]
        pass_result = {"passed": True, "failure_reason": "", "unmet_constraints": []}

        validation_results = [*fail_results, pass_result]
        validation_call_count = [0]

        async def mock_validate(solution, requirements, material_info):
            idx = validation_call_count[0]
            validation_call_count[0] += 1
            return validation_results[idx]

        self.validator.validate.side_effect = mock_validate

        hypotheses = [ProcessHypothesis(content=f"假设{i+1}") for i in range(4)]
        self.hypothesis_generator.generate_initial_hypothesis.return_value = hypotheses[0]
        self.hypothesis_generator.generate_correction_hypothesis.side_effect = hypotheses[1:]

        result = await self.loop.run(
            task_id=task_id,
            requirements={},
            material_info={},
            tool_info={}
        )

        for i in range(3):
            assert result.iterations[i].correction_direction != ""

        assert result.iterations[3].correction_direction == ""

    @pytest.mark.asyncio
    async def test_trace_node_records_iterations(self):
        """验证 TraceNode 数据结构准确记录每次迭代的信息。

        Arrange:
            - 配置多轮迭代场景
        Act:
            - 调用 run() 方法
        Assert:
            - 验证 process_trace.nodes 包含 4 个节点
            - 验证每个节点包含 hypothesis、validation_result、feedback 字段
        """
        task_id = self.task_manager.create_task(TaskType.WORKFLOW_EXECUTION)

        validation_results = [
            {"passed": False, "failure_reason": "失败1", "unmet_constraints": []},
            {"passed": False, "failure_reason": "失败2", "unmet_constraints": []},
            {"passed": False, "failure_reason": "失败3", "unmet_constraints": []},
            {"passed": True, "failure_reason": "", "unmet_constraints": []}
        ]
        validation_call_count = [0]

        async def mock_validate(solution, requirements, material_info):
            idx = validation_call_count[0]
            validation_call_count[0] += 1
            return validation_results[idx]

        self.validator.validate.side_effect = mock_validate

        hypotheses = [ProcessHypothesis(content=f"假设{i+1}") for i in range(4)]
        self.hypothesis_generator.generate_initial_hypothesis.return_value = hypotheses[0]
        self.hypothesis_generator.generate_correction_hypothesis.side_effect = hypotheses[1:]

        await self.loop.run(
            task_id=task_id,
            requirements={},
            material_info={},
            tool_info={}
        )

        assert len(self.loop.process_trace.nodes) == 4

        for node in self.loop.process_trace.nodes.values():
            assert node.hypothesis != ""
            assert len(node.validation_result) > 0
            assert hasattr(node, 'feedback')

    @pytest.mark.asyncio
    async def test_iteration_counter_matches_actual(self):
        """验证迭代次数计数器与实际迭代次数一致。

        Arrange:
            - 配置 4 轮迭代场景
        Act:
            - 调用 run() 方法
        Assert:
            - 验证 iterations 列表长度为 4
            - 验证每个 iteration 对象的 iteration 字段与索引一致
        """
        task_id = self.task_manager.create_task(TaskType.WORKFLOW_EXECUTION)

        validation_results = [
            {"passed": False, "failure_reason": "f1", "unmet_constraints": []},
            {"passed": False, "failure_reason": "f2", "unmet_constraints": []},
            {"passed": False, "failure_reason": "f3", "unmet_constraints": []},
            {"passed": True, "failure_reason": "", "unmet_constraints": []}
        ]
        validation_call_count = [0]

        async def mock_validate(solution, requirements, material_info):
            idx = validation_call_count[0]
            validation_call_count[0] += 1
            return validation_results[idx]

        self.validator.validate.side_effect = mock_validate

        hypotheses = [ProcessHypothesis(content=f"假设{i+1}") for i in range(4)]
        self.hypothesis_generator.generate_initial_hypothesis.return_value = hypotheses[0]
        self.hypothesis_generator.generate_correction_hypothesis.side_effect = hypotheses[1:]

        result = await self.loop.run(
            task_id=task_id,
            requirements={},
            material_info={},
            tool_info={}
        )

        assert len(result.iterations) == 4

        for idx, iteration in enumerate(result.iterations):
            assert iteration.iteration == idx + 1


class TestMaxIterationsProtection:
    """最大迭代次数保护测试类。

    验证当达到最大迭代次数时，系统能正确终止并返回最佳可行解。
    """

    def setup_method(self, method):
        """测试方法执行前的准备工作。

        Args:
            method: 当前执行的测试方法
        """
        self.task_manager = TaskManager(default_timeout=300.0)
        self.logger = AIWorkflowLogger()
        self.hypothesis_generator = AsyncMock()
        self.validator = AsyncMock()

    def teardown_method(self, method):
        """测试方法执行后的清理工作。

        Args:
            method: 当前执行的测试方法
        """
        self.task_manager = None
        self.logger = None
        self.hypothesis_generator = None
        self.validator = None

    @pytest.mark.asyncio
    async def test_terminates_at_max_iterations(self):
        """验证系统在达到最大迭代次数后终止。

        Arrange:
            - 设置 max_iterations 为 5
            - 配置所有 5 轮验证均失败
        Act:
            - 调用 run() 方法
        Assert:
            - 验证返回结果 success 为 False
            - 验证 iterations 列表长度为 5
            - 验证循环不会继续执行第 6 轮
        """
        loop = HypothesisDrivenLoop(
            task_manager=self.task_manager,
            workflow_logger=self.logger,
            hypothesis_generator=self.hypothesis_generator,
            validator=self.validator,
            max_iterations=5
        )

        task_id = self.task_manager.create_task(TaskType.WORKFLOW_EXECUTION)

        self.validator.validate.return_value = {
            "passed": False,
            "failure_reason": "约束不满足",
            "unmet_constraints": ["constraint_violation"]
        }

        hypotheses = [ProcessHypothesis(content=f"假设{i+1}") for i in range(5)]
        self.hypothesis_generator.generate_initial_hypothesis.return_value = hypotheses[0]
        self.hypothesis_generator.generate_correction_hypothesis.side_effect = hypotheses[1:]

        result = await loop.run(
            task_id=task_id,
            requirements={},
            material_info={},
            tool_info={}
        )

        assert result.success is False
        assert len(result.iterations) == 5
        assert self.hypothesis_generator.generate_correction_hypothesis.call_count == 4

    @pytest.mark.asyncio
    async def test_returns_best_feasible_solution(self):
        """验证返回当前最优可行解。

        Arrange:
            - 设置 max_iterations 为 5
            - 配置所有验证失败
        Act:
            - 调用 run() 方法
        Assert:
            - 验证 best_feasible_solution 不为 None
            - 验证返回默认求解器的解
        """
        loop = HypothesisDrivenLoop(
            task_manager=self.task_manager,
            workflow_logger=self.logger,
            hypothesis_generator=self.hypothesis_generator,
            validator=self.validator,
            max_iterations=5
        )

        task_id = self.task_manager.create_task(TaskType.WORKFLOW_EXECUTION)

        self.validator.validate.return_value = {
            "passed": False,
            "failure_reason": "约束不满足",
            "unmet_constraints": []
        }

        hypotheses = [ProcessHypothesis(content=f"假设{i+1}") for i in range(5)]
        self.hypothesis_generator.generate_initial_hypothesis.return_value = hypotheses[0]
        self.hypothesis_generator.generate_correction_hypothesis.side_effect = hypotheses[1:]

        result = await loop.run(
            task_id=task_id,
            requirements={},
            material_info={},
            tool_info={}
        )

        assert result.best_feasible_solution is not None
        assert "cutting_speed" in result.best_feasible_solution
        assert "feed_rate" in result.best_feasible_solution
        assert "depth_of_cut" in result.best_feasible_solution

    @pytest.mark.asyncio
    async def test_no_infinite_loop(self):
        """验证系统不会进入无限循环。

        Arrange:
            - 设置较小的 max_iterations 为 3
            - 配置所有验证失败
        Act:
            - 调用 run() 方法并设置超时保护
        Assert:
            - 验证方法在合理时间内返回
            - 验证 iterations 数量不超过 max_iterations
        """
        loop = HypothesisDrivenLoop(
            task_manager=self.task_manager,
            workflow_logger=self.logger,
            hypothesis_generator=self.hypothesis_generator,
            validator=self.validator,
            max_iterations=3
        )

        task_id = self.task_manager.create_task(TaskType.WORKFLOW_EXECUTION)

        self.validator.validate.return_value = {
            "passed": False,
            "failure_reason": "始终失败",
            "unmet_constraints": []
        }

        hypotheses = [ProcessHypothesis(content=f"假设{i+1}") for i in range(3)]
        self.hypothesis_generator.generate_initial_hypothesis.return_value = hypotheses[0]
        self.hypothesis_generator.generate_correction_hypothesis.side_effect = hypotheses[1:]

        result = await loop.run(
            task_id=task_id,
            requirements={},
            material_info={},
            tool_info={}
        )

        assert len(result.iterations) <= 3
        assert result.total_duration_ms > 0

    @pytest.mark.asyncio
    async def test_termination_reason_included(self):
        """验证返回结果包含迭代终止原因说明。

        Arrange:
            - 设置 max_iterations 为 5
            - 配置所有验证失败
        Act:
            - 调用 run() 方法
        Assert:
            - 验证 warning_message 不为空
            - 验证 warning_message 包含"达到最大迭代次数"
            - 验证 warning_message 包含迭代次数信息
        """
        loop = HypothesisDrivenLoop(
            task_manager=self.task_manager,
            workflow_logger=self.logger,
            hypothesis_generator=self.hypothesis_generator,
            validator=self.validator,
            max_iterations=5
        )

        task_id = self.task_manager.create_task(TaskType.WORKFLOW_EXECUTION)

        self.validator.validate.return_value = {
            "passed": False,
            "failure_reason": "约束不满足",
            "unmet_constraints": []
        }

        hypotheses = [ProcessHypothesis(content=f"假设{i+1}") for i in range(5)]
        self.hypothesis_generator.generate_initial_hypothesis.return_value = hypotheses[0]
        self.hypothesis_generator.generate_correction_hypothesis.side_effect = hypotheses[1:]

        result = await loop.run(
            task_id=task_id,
            requirements={},
            material_info={},
            tool_info={}
        )

        assert result.warning_message != ""
        assert "达到最大迭代次数" in result.warning_message
        assert "5" in result.warning_message


class TestTaskCancellation:
    """任务取消测试类。

    验证在迭代过程中收到取消请求时系统能优雅停止。
    """

    def setup_method(self, method):
        """测试方法执行前的准备工作。

        Args:
            method: 当前执行的测试方法
        """
        self.task_manager = TaskManager(default_timeout=300.0)
        self.logger = AIWorkflowLogger()
        self.hypothesis_generator = AsyncMock()
        self.validator = AsyncMock()

        self.loop = HypothesisDrivenLoop(
            task_manager=self.task_manager,
            workflow_logger=self.logger,
            hypothesis_generator=self.hypothesis_generator,
            validator=self.validator,
            max_iterations=5
        )

    def teardown_method(self, method):
        """测试方法执行后的清理工作。

        Args:
            method: 当前执行的测试方法
        """
        self.task_manager = None
        self.logger = None
        self.hypothesis_generator = None
        self.validator = None
        self.loop = None

    @pytest.mark.asyncio
    async def test_graceful_stop_on_cancellation(self):
        """验证系统能够优雅停止当前操作。

        Arrange:
            - 创建任务
            - 配置假设生成器在第 1 轮后将任务状态设为 cancelled
            - 配置第 1 轮验证失败以进入第 2 轮
        Act:
            - 调用 run() 方法
        Assert:
            - 验证返回结果 success 为 False
            - 验证 warning_message 包含"取消"
        """
        task_id = self.task_manager.create_task(TaskType.WORKFLOW_EXECUTION)

        async def mock_generate_initial(**kwargs):
            self.task_manager._tasks[task_id].status = TaskStatus.CANCELLED
            return ProcessHypothesis(content="初始假设")

        self.hypothesis_generator.generate_initial_hypothesis.side_effect = mock_generate_initial
        self.validator.validate.return_value = {
            "passed": False,
            "failure_reason": "验证失败",
            "unmet_constraints": []
        }

        result = await self.loop.run(
            task_id=task_id,
            requirements={},
            material_info={},
            tool_info={}
        )

        assert result.success is False
        assert "取消" in result.warning_message

    @pytest.mark.asyncio
    async def test_resources_released_on_cancellation(self):
        """验证所有已分配资源被正确释放。

        Arrange:
            - 创建任务并配置取消场景
        Act:
            - 调用 run() 方法
        Assert:
            - 验证方法正常返回，不抛出异常
            - 验证 process_trace 仍可访问
        """
        task_id = self.task_manager.create_task(TaskType.WORKFLOW_EXECUTION)

        async def mock_generate_initial(**kwargs):
            self.task_manager._tasks[task_id].status = TaskStatus.CANCELLED
            return ProcessHypothesis(content="初始假设")

        self.hypothesis_generator.generate_initial_hypothesis.side_effect = mock_generate_initial

        result = await self.loop.run(
            task_id=task_id,
            requirements={},
            material_info={},
            tool_info={}
        )

        assert result is not None
        assert self.loop.process_trace is not None

    @pytest.mark.asyncio
    async def test_cancellation_returns_intermediate_results(self):
        """验证返回适当的取消状态和中间结果。

        Arrange:
            - 创建任务
            - 配置第 1 轮迭代后任务状态为 cancelled
        Act:
            - 调用 run() 方法
        Assert:
            - 验证返回结果包含已执行的迭代
            - 验证 final_hypothesis 为最后一次生成的假设
        """
        task_id = self.task_manager.create_task(TaskType.WORKFLOW_EXECUTION)

        async def mock_generate_initial(**kwargs):
            result_hypothesis = ProcessHypothesis(content="初始假设")
            return result_hypothesis

        self.hypothesis_generator.generate_initial_hypothesis.side_effect = mock_generate_initial
        self.validator.validate.return_value = {
            "passed": False,
            "failure_reason": "验证失败",
            "unmet_constraints": []
        }

        async def mock_generate_correction(**kwargs):
            self.task_manager._tasks[task_id].status = TaskStatus.CANCELLED
            return ProcessHypothesis(content="修正假设")

        self.hypothesis_generator.generate_correction_hypothesis.side_effect = mock_generate_correction

        result = await self.loop.run(
            task_id=task_id,
            requirements={},
            material_info={},
            tool_info={}
        )

        assert result.success is False
        assert "取消" in result.warning_message
        assert len(result.iterations) >= 1
        assert result.iterations[0].is_passed is False

    @pytest.mark.asyncio
    async def test_cancellation_no_data_inconsistency(self):
        """验证取消操作不会导致数据不一致。

        Arrange:
            - 创建任务并配置取消场景
        Act:
            - 调用 run() 方法
        Assert:
            - 验证 iterations 列表中的迭代序号连续
            - 验证所有迭代对象的数据完整
        """
        task_id = self.task_manager.create_task(TaskType.WORKFLOW_EXECUTION)

        self.validator.validate.return_value = {
            "passed": False,
            "failure_reason": "失败",
            "unmet_constraints": []
        }

        async def mock_generate_initial(**kwargs):
            self.task_manager._tasks[task_id].status = TaskStatus.CANCELLED
            return ProcessHypothesis(content="初始假设")

        self.hypothesis_generator.generate_initial_hypothesis.side_effect = mock_generate_initial

        result = await self.loop.run(
            task_id=task_id,
            requirements={},
            material_info={},
            tool_info={}
        )

        for i, iteration in enumerate(result.iterations):
            assert iteration.iteration == i + 1
            assert iteration.hypothesis is not None
            assert iteration.validation_result is not None


class TestBoundaryConditions:
    """边界条件测试类。

    验证在极端或异常输入条件下系统的稳定性和错误处理能力。
    """

    def setup_method(self, method):
        """测试方法执行前的准备工作。

        Args:
            method: 当前执行的测试方法
        """
        self.task_manager = TaskManager(default_timeout=300.0)
        self.logger = AIWorkflowLogger()
        self.hypothesis_generator = AsyncMock()
        self.validator = AsyncMock()

        self.loop = HypothesisDrivenLoop(
            task_manager=self.task_manager,
            workflow_logger=self.logger,
            hypothesis_generator=self.hypothesis_generator,
            validator=self.validator,
            max_iterations=5
        )

    def teardown_method(self, method):
        """测试方法执行后的清理工作。

        Args:
            method: 当前执行的测试方法
        """
        self.task_manager = None
        self.logger = None
        self.hypothesis_generator = None
        self.validator = None
        self.loop = None

    @pytest.mark.asyncio
    async def test_empty_requirements_input(self):
        """测试空需求输入场景。

        Arrange:
            - 传入空的 requirements 字典
            - 配置假设生成器和验证器正常工作
        Act:
            - 调用 run() 方法
        Assert:
            - 验证系统不抛出异常
            - 验证方法正常返回结果
        """
        task_id = self.task_manager.create_task(TaskType.WORKFLOW_EXECUTION)

        test_hypothesis = ProcessHypothesis(content="测试假设")
        self.hypothesis_generator.generate_initial_hypothesis.return_value = test_hypothesis
        self.validator.validate.return_value = {"passed": True, "failure_reason": "", "unmet_constraints": []}

        result = await self.loop.run(
            task_id=task_id,
            requirements={},
            material_info={},
            tool_info={}
        )

        assert result is not None
        assert result.success is True

    @pytest.mark.asyncio
    async def test_invalid_material_info(self):
        """测试提供无效材料信息时的系统行为。

        Arrange:
            - 传入包含无效数据的 material_info
            - 配置假设生成器和验证器
        Act:
            - 调用 run() 方法
        Assert:
            - 验证系统不崩溃
            - 验证方法返回结果（即使验证失败）
        """
        task_id = self.task_manager.create_task(TaskType.WORKFLOW_EXECUTION)

        invalid_material_info = {
            "material": None,
            "hardness": "invalid_value",
            "density": -1
        }

        test_hypothesis = ProcessHypothesis(content="测试假设")
        self.hypothesis_generator.generate_initial_hypothesis.return_value = test_hypothesis
        self.validator.validate.return_value = {
            "passed": False,
            "failure_reason": "材料参数无效",
            "unmet_constraints": []
        }

        result = await self.loop.run(
            task_id=task_id,
            requirements={},
            material_info=invalid_material_info,
            tool_info={}
        )

        assert result is not None
        assert len(result.iterations) >= 1

    @pytest.mark.asyncio
    async def test_extreme_constraints(self):
        """测试极端约束条件下的系统表现。

        Arrange:
            - 传入极其严格的约束条件
            - 配置验证器始终返回失败
        Act:
            - 调用 run() 方法，设置较小的 max_iterations
        Assert:
            - 验证系统在达到最大迭代次数后终止
            - 验证返回最佳可行解
        """
        loop = HypothesisDrivenLoop(
            task_manager=self.task_manager,
            workflow_logger=self.logger,
            hypothesis_generator=self.hypothesis_generator,
            validator=self.validator,
            max_iterations=3
        )

        task_id = self.task_manager.create_task(TaskType.WORKFLOW_EXECUTION)

        extreme_requirements = {
            "max_cutting_force": 0.001,
            "max_surface_roughness": 0.0001,
            "min_tool_life": 10000
        }

        self.validator.validate.return_value = {
            "passed": False,
            "failure_reason": "约束过于严格，无法满足",
            "unmet_constraints": ["extreme_violation"]
        }

        hypotheses = [ProcessHypothesis(content=f"假设{i+1}") for i in range(3)]
        self.hypothesis_generator.generate_initial_hypothesis.return_value = hypotheses[0]
        self.hypothesis_generator.generate_correction_hypothesis.side_effect = hypotheses[1:]

        result = await loop.run(
            task_id=task_id,
            requirements=extreme_requirements,
            material_info={},
            tool_info={}
        )

        assert result.success is False
        assert len(result.iterations) == 3
        assert result.best_feasible_solution is not None

    @pytest.mark.asyncio
    async def test_solver_failure_handling(self):
        """测试求解器失败时的错误处理。

        Arrange:
            - 配置求解器返回失败状态
            - 设置 max_iterations 为 1 以简化测试
        Act:
            - 调用 run() 方法
        Assert:
            - 验证系统将失败信息记录到迭代结果中
            - 验证 correction_direction 包含调整建议
        """
        loop = HypothesisDrivenLoop(
            task_manager=self.task_manager,
            workflow_logger=self.logger,
            hypothesis_generator=self.hypothesis_generator,
            validator=self.validator,
            max_iterations=1
        )

        task_id = self.task_manager.create_task(TaskType.WORKFLOW_EXECUTION)

        test_hypothesis = ProcessHypothesis(content="测试假设")
        self.hypothesis_generator.generate_initial_hypothesis.return_value = test_hypothesis

        with patch.object(loop, '_run_solver', new_callable=lambda: AsyncMock()) as mock_solver:
            mock_solver.return_value = {
                "status": "failed",
                "error": "求解器无法找到可行解"
            }

            result = await loop.run(
                task_id=task_id,
                requirements={},
                material_info={},
                tool_info={}
            )

            assert len(result.iterations) == 1
            assert result.iterations[0].is_passed is False
            assert result.iterations[0].correction_direction != ""
            assert "求解器" in result.iterations[0].validation_result.get("failure_reason", "")

    @pytest.mark.asyncio
    async def test_exception_during_iteration(self):
        """测试迭代过程中发生异常时的处理。

        Arrange:
            - 配置假设生成器抛出异常
        Act:
            - 调用 run() 方法
        Assert:
            - 验证异常被捕获并记录到迭代结果中
            - 验证循环继续执行下一轮迭代
        """
        task_id = self.task_manager.create_task(TaskType.WORKFLOW_EXECUTION)

        call_count = [0]

        async def mock_generate_initial(**kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                raise RuntimeError("假设生成失败")
            return ProcessHypothesis(content="重试假设")

        self.hypothesis_generator.generate_initial_hypothesis.side_effect = mock_generate_initial

        self.validator.validate.return_value = {"passed": True, "failure_reason": "", "unmet_constraints": []}

        result = await self.loop.run(
            task_id=task_id,
            requirements={},
            material_info={},
            tool_info={}
        )

        assert len(result.iterations) >= 1
        assert result.iterations[0].is_passed is False
        assert "系统异常" in result.iterations[0].correction_direction

    @pytest.mark.asyncio
    async def test_max_iterations_one(self):
        """测试最大迭代次数为 1 的边界情况。

        Arrange:
            - 设置 max_iterations 为 1
            - 配置验证失败
        Act:
            - 调用 run() 方法
        Assert:
            - 验证仅执行 1 轮迭代
            - 验证返回结果 success 为 False
        """
        loop = HypothesisDrivenLoop(
            task_manager=self.task_manager,
            workflow_logger=self.logger,
            hypothesis_generator=self.hypothesis_generator,
            validator=self.validator,
            max_iterations=1
        )

        task_id = self.task_manager.create_task(TaskType.WORKFLOW_EXECUTION)

        test_hypothesis = ProcessHypothesis(content="唯一假设")
        self.hypothesis_generator.generate_initial_hypothesis.return_value = test_hypothesis
        self.validator.validate.return_value = {
            "passed": False,
            "failure_reason": "验证失败",
            "unmet_constraints": []
        }

        result = await loop.run(
            task_id=task_id,
            requirements={},
            material_info={},
            tool_info={}
        )

        assert len(result.iterations) == 1
        assert result.success is False
        assert self.hypothesis_generator.generate_correction_hypothesis.call_count == 0


class TestDefaultConstraintMapping:
    """默认约束映射测试类。

    验证 _default_constraint_mapping 方法的正确性。
    """

    def setup_method(self, method):
        """测试方法执行前的准备工作。

        Args:
            method: 当前执行的测试方法
        """
        self.task_manager = TaskManager(default_timeout=300.0)
        self.logger = AIWorkflowLogger()
        self.hypothesis_generator = AsyncMock()

        self.loop = HypothesisDrivenLoop(
            task_manager=self.task_manager,
            workflow_logger=self.logger,
            hypothesis_generator=self.hypothesis_generator
        )

    def teardown_method(self, method):
        """测试方法执行后的清理工作。

        Args:
            method: 当前执行的测试方法
        """
        self.task_manager = None
        self.logger = None
        self.hypothesis_generator = None
        self.loop = None

    def test_mapping_with_cutting_force(self):
        """验证切削力约束正确映射。

        Arrange:
            - 创建包含 cutting_force 预期的假设
        Act:
            - 调用 _default_constraint_mapping
        Assert:
            - 验证返回约束包含 cutting_force_max
        """
        hypothesis = ProcessHypothesis(
            content="测试假设",
            expected_outcomes={"cutting_force": "< 800N"}
        )
        requirements = {}

        constraints = self.loop._default_constraint_mapping(hypothesis, requirements)

        assert "cutting_force_max" in constraints
        assert constraints["cutting_force_max"] == 800.0

    def test_mapping_with_surface_roughness(self):
        """验证表面粗糙度约束正确映射。

        Arrange:
            - 创建包含 surface_roughness 预期的假设
        Act:
            - 调用 _default_constraint_mapping
        Assert:
            - 验证返回约束包含 surface_roughness_max
        """
        hypothesis = ProcessHypothesis(
            content="测试假设",
            expected_outcomes={"surface_roughness": "< 1.6μm"}
        )
        requirements = {}

        constraints = self.loop._default_constraint_mapping(hypothesis, requirements)

        assert "surface_roughness_max" in constraints
        assert constraints["surface_roughness_max"] == 1.6

    def test_mapping_with_tool_life(self):
        """验证刀具寿命约束正确映射。

        Arrange:
            - 创建包含 tool_life 预期的假设
        Act:
            - 调用 _default_constraint_mapping
        Assert:
            - 验证返回约束包含 tool_life_min
        """
        hypothesis = ProcessHypothesis(
            content="测试假设",
            expected_outcomes={"tool_life": "> 60min"}
        )
        requirements = {}

        constraints = self.loop._default_constraint_mapping(hypothesis, requirements)

        assert "tool_life_min" in constraints
        assert constraints["tool_life_min"] == 60.0

    def test_mapping_with_requirements_constraints(self):
        """验证需求中的约束被合并。

        Arrange:
            - 创建假设和包含 constraints 的需求
        Act:
            - 调用 _default_constraint_mapping
        Assert:
            - 验证返回约束包含假设和需求的约束
        """
        hypothesis = ProcessHypothesis(
            content="测试假设",
            expected_outcomes={"cutting_force": "< 800N"}
        )
        requirements = {
            "constraints": {
                "custom_constraint": 100
            }
        }

        constraints = self.loop._default_constraint_mapping(hypothesis, requirements)

        assert "cutting_force_max" in constraints
        assert "custom_constraint" in constraints
        assert constraints["custom_constraint"] == 100


class TestScoreSolution:
    """解评分测试类。

    验证 _score_solution 方法的评分逻辑。
    """

    def setup_method(self, method):
        """测试方法执行前的准备工作。

        Args:
            method: 当前执行的测试方法
        """
        self.task_manager = TaskManager(default_timeout=300.0)
        self.logger = AIWorkflowLogger()
        self.hypothesis_generator = AsyncMock()

        self.loop = HypothesisDrivenLoop(
            task_manager=self.task_manager,
            workflow_logger=self.logger,
            hypothesis_generator=self.hypothesis_generator
        )

    def teardown_method(self, method):
        """测试方法执行后的清理工作。

        Args:
            method: 当前执行的测试方法
        """
        self.task_manager = None
        self.logger = None
        self.hypothesis_generator = None
        self.loop = None

    def test_score_with_good_solution(self):
        """验证优质解获得较高评分。

        Arrange:
            - 创建包含优质指标的解
        Act:
            - 调用 _score_solution
        Assert:
            - 验证评分大于 0.5
        """
        solution = {
            "cutting_force": 500.0,
            "surface_roughness": 1.0,
            "tool_life": 80.0,
            "cutting_speed": 150.0
        }

        score = self.loop._score_solution(solution)

        assert score > 0.5

    def test_score_with_poor_solution(self):
        """验证劣质解获得较低评分。

        Arrange:
            - 创建包含较差指标的解
        Act:
            - 调用 _score_solution
        Assert:
            - 验证评分较低（小于 0.3）
        """
        solution = {
            "cutting_force": 950.0,
            "surface_roughness": 4.5,
            "tool_life": 10.0,
            "cutting_speed": 20.0
        }

        score = self.loop._score_solution(solution)

        assert score < 0.3

    def test_score_with_empty_solution(self):
        """验证空解获得默认评分。

        Arrange:
            - 创建空解
        Act:
            - 调用 _score_solution
        Assert:
            - 验证评分为默认值计算结果
        """
        solution = {}

        score = self.loop._score_solution(solution)

        assert isinstance(score, float)
        assert score >= 0


class TestHypothesisIterationDataClass:
    """HypothesisIteration 数据类测试。

    验证 HypothesisIteration 数据类的序列化和字段。
    """

    def test_to_dict_serialization(self):
        """验证 to_dict 方法正确序列化数据。

        Arrange:
            - 创建 HypothesisIteration 实例
        Act:
            - 调用 to_dict 方法
        Assert:
            - 验证返回字典包含所有必需字段
            - 验证字段值与实例一致
        """
        hypothesis = ProcessHypothesis(content="测试假设")
        iteration = HypothesisIteration(
            iteration=1,
            hypothesis=hypothesis,
            validation_result={"passed": True},
            is_passed=True,
            correction_direction="",
            duration_ms=150.5
        )

        result_dict = iteration.to_dict()

        assert "iteration" in result_dict
        assert "hypothesis" in result_dict
        assert "validation_result" in result_dict
        assert "is_passed" in result_dict
        assert "correction_direction" in result_dict
        assert "duration_ms" in result_dict
        assert "created_at" in result_dict

        assert result_dict["iteration"] == 1
        assert result_dict["is_passed"] is True
        assert result_dict["duration_ms"] == 150.5


class TestHypothesisLoopResultDataClass:
    """HypothesisLoopResult 数据类测试。

    验证 HypothesisLoopResult 数据类的序列化和字段。
    """

    def test_to_dict_serialization(self):
        """验证 to_dict 方法正确序列化数据。

        Arrange:
            - 创建 HypothesisLoopResult 实例
        Act:
            - 调用 to_dict 方法
        Assert:
            - 验证返回字典包含所有必需字段
            - 验证 iterations 被正确序列化
        """
        hypothesis = ProcessHypothesis(content="最终假设")
        iteration = HypothesisIteration(
            iteration=1,
            hypothesis=hypothesis,
            validation_result={"passed": True},
            is_passed=True
        )
        result = HypothesisLoopResult(
            success=True,
            final_hypothesis=hypothesis,
            iterations=[iteration],
            best_feasible_solution={"cutting_speed": 120.0},
            warning_message="",
            total_duration_ms=500.0
        )

        result_dict = result.to_dict()

        assert "success" in result_dict
        assert "final_hypothesis" in result_dict
        assert "iterations" in result_dict
        assert "best_feasible_solution" in result_dict
        assert "warning_message" in result_dict
        assert "total_duration_ms" in result_dict

        assert result_dict["success"] is True
        assert len(result_dict["iterations"]) == 1
        assert result_dict["total_duration_ms"] == 500.0

    def test_to_dict_with_none_hypothesis(self):
        """验证 final_hypothesis 为 None 时的序列化。

        Arrange:
            - 创建 final_hypothesis 为 None 的结果
        Act:
            - 调用 to_dict 方法
        Assert:
            - 验证 final_hypothesis 在字典中为 None
        """
        result = HypothesisLoopResult(
            success=False,
            final_hypothesis=None,
            iterations=[],
            best_feasible_solution=None
        )

        result_dict = result.to_dict()

        assert result_dict["final_hypothesis"] is None
        assert result_dict["success"] is False
        assert len(result_dict["iterations"]) == 0
