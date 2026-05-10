"""
Unit tests for YAML Configuration Manager and Workflow LNN Orchestrator

Tests cover:
- Configuration loading, validation, access, updates, and persistence
- Workflow execution with LNN enhancement
- Fallback mechanisms
- Environment adaptation
"""
import os
import sys
import pytest
import tempfile
import shutil
import yaml
from unittest.mock import MagicMock, patch
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.ai.lnn.config.config_manager import (
    YAMLConfigManager,
    ModelConfig,
    ThresholdConfig,
    LNNConfig,
    WorkflowConfig,
    EnvironmentConfig,
    AppConfig,
)
from app.ai.lnn.workflow.workflow_orchestrator import (
    WorkflowLNNOrchestrator,
    WorkflowStep,
    WorkflowStepStatus,
    WorkflowExecutionPlan,
    WorkflowResult,
    FallbackStrategy,
)
from app.ai.lnn.core import (
    EngineType,
    TaskInput,
    RoutingDecision,
    InferenceResult,
    FusionResult,
    TaskCategory,
    DataType,
)


class TestYAMLConfigManager:
    """测试YAML配置管理器"""

    @pytest.fixture
    def sample_yaml_config(self):
        """创建示例YAML配置文件"""
        config = {
            "lnn": {
                "enabled": True,
                "models_dir": "models/lnn",
                "default_device": "cpu",
                "models": {
                    "cutting_force": {
                        "type": "cfc",
                        "path": "cutting_force_v1.pt",
                    },
                    "wear_prediction": {
                        "type": "ltc",
                        "path": "wear_prediction_v1.pt",
                    },
                },
                "thresholds": {
                    "quick": 0.85,
                    "hybrid": 0.60,
                    "complexity": 3,
                },
            },
            "workflow": {
                "enabled": True,
                "max_steps": 10,
                "timeout_seconds": 300,
                "enable_fallback": True,
                "fallback_engine": "Rule",
            },
            "environment": {
                "name": "development",
                "debug": True,
            },
        }
        return config

    @pytest.fixture
    def temp_config_file(self, sample_yaml_config):
        """创建临时配置文件"""
        temp_dir = tempfile.mkdtemp()
        config_path = os.path.join(temp_dir, "test_config.yaml")
        with open(config_path, "w", encoding="utf-8") as f:
            yaml.dump(sample_yaml_config, f, default_flow_style=False)
        yield config_path
        shutil.rmtree(temp_dir)

    @pytest.fixture
    def config_manager(self):
        """创建使用默认配置的管理器"""
        return YAMLConfigManager()

    @pytest.fixture
    def config_manager_from_file(self, temp_config_file):
        """创建从文件加载配置的管理器"""
        return YAMLConfigManager(config_path=temp_config_file)

    def test_default_initialization(self, config_manager):
        """测试默认初始化"""
        assert config_manager is not None
        assert config_manager.config_path is None
        assert config_manager.is_dirty() is False

    def test_load_from_file(self, config_manager_from_file):
        """测试从文件加载配置"""
        assert config_manager_from_file is not None
        assert config_manager_from_file.config_path is not None
        assert config_manager_from_file.is_dirty() is False

    def test_load_nonexistent_file(self):
        """测试加载不存在的文件"""
        with pytest.raises(FileNotFoundError):
            YAMLConfigManager(config_path="nonexistent/path/config.yaml")

    def test_load_invalid_yaml(self):
        """测试加载无效YAML"""
        temp_dir = tempfile.mkdtemp()
        config_path = os.path.join(temp_dir, "invalid.yaml")
        with open(config_path, "w") as f:
            f.write("invalid: yaml: content: [")

        with pytest.raises(Exception):
            manager = YAMLConfigManager()
            manager.load(config_path)

        shutil.rmtree(temp_dir)

    def test_get_config_value(self, config_manager_from_file):
        """测试获取配置值"""
        assert config_manager_from_file.get("lnn", "enabled") is True
        assert config_manager_from_file.get("lnn", "default_device") == "cpu"
        assert config_manager_from_file.get("workflow", "max_steps") == 10

    def test_get_nested_config(self, config_manager_from_file):
        """测试获取嵌套配置"""
        thresholds = config_manager_from_file.get("lnn", "thresholds")
        assert isinstance(thresholds, dict)
        assert thresholds["quick"] == 0.85
        assert thresholds["hybrid"] == 0.60

    def test_get_default_value(self, config_manager):
        """测试获取默认值"""
        assert config_manager.get("nonexistent", "key", "default") == "default"
        assert config_manager.get("lnn", "nonexistent_key", "fallback") == "fallback"

    def test_set_config_value(self, config_manager):
        """测试设置配置值"""
        config_manager.set("lnn", "enabled", False)
        assert config_manager.get("lnn", "enabled") is False
        assert config_manager.is_dirty() is True

    def test_set_nested_config_value(self, config_manager):
        """测试设置嵌套配置值"""
        config_manager.set("lnn", "thresholds.quick", 0.90)
        assert config_manager.get("lnn", "thresholds", {}).get("quick") == 0.90

    def test_set_new_section(self, config_manager):
        """测试设置新配置节"""
        config_manager.set("new_section", "key1", "value1")
        assert config_manager.get("new_section", "key1") == "value1"

    def test_validate_valid_config(self, config_manager_from_file):
        """测试验证有效配置"""
        result = config_manager_from_file.validate()
        assert result["valid"] is True
        assert len(result["errors"]) == 0

    def test_validate_invalid_config(self):
        """测试验证无效配置"""
        manager = YAMLConfigManager(use_defaults=True)
        manager._raw_config["lnn"]["default_device"] = "invalid_device"

        result = manager.validate()
        assert result["valid"] is False
        assert any("Invalid default_device" in e for e in result["errors"])

    def test_validate_missing_keys(self):
        """测试验证缺少必需键"""
        manager = YAMLConfigManager(use_defaults=True)
        manager._raw_config["lnn"] = {}

        result = manager.validate()
        assert result["valid"] is False
        error_text = "\n".join(result["errors"])
        assert "Missing required LNN key" in error_text

    def test_save_config(self, config_manager, tmp_path):
        """测试保存配置"""
        output_path = str(tmp_path / "saved_config.yaml")
        config_manager.set("lnn", "enabled", False)
        config_manager.save(output_path)

        assert os.path.exists(output_path)
        assert config_manager.is_dirty() is False

        with open(output_path, "r") as f:
            saved_config = yaml.safe_load(f)
        assert saved_config["lnn"]["enabled"] is False

    def test_save_without_path(self, config_manager):
        """测试未指定路径时保存"""
        with pytest.raises(ValueError):
            config_manager.save()

    def test_to_dict(self, config_manager_from_file):
        """测试转换为字典"""
        config_dict = config_manager_from_file.to_dict()
        assert isinstance(config_dict, dict)
        assert "lnn" in config_dict
        assert "workflow" in config_dict

    def test_to_dataclass(self, config_manager_from_file):
        """测试转换为数据类"""
        app_config = config_manager_from_file.to_dataclass()
        assert isinstance(app_config, AppConfig)
        assert isinstance(app_config.lnn, LNNConfig)
        assert isinstance(app_config.workflow, WorkflowConfig)

    def test_reset_to_defaults(self, config_manager):
        """测试重置为默认配置"""
        config_manager.set("lnn", "enabled", False)
        config_manager.reset_to_defaults()
        assert config_manager.get("lnn", "enabled") is True

    def test_get_model_config(self, config_manager_from_file):
        """测试获取模型配置"""
        model_config = config_manager_from_file.get_model_config("cutting_force")
        assert model_config is not None
        assert isinstance(model_config, ModelConfig)
        assert model_config.type == "cfc"
        assert "cutting_force" in model_config.path

    def test_get_nonexistent_model_config(self, config_manager_from_file):
        """测试获取不存在的模型配置"""
        model_config = config_manager_from_file.get_model_config("nonexistent_model")
        assert model_config is None

    def test_add_model(self, config_manager):
        """测试添加模型配置"""
        model_config = {
            "type": "cfc",
            "path": "new_model.pt",
            "enabled": True,
        }
        config_manager.add_model("new_model", model_config)

        assert config_manager.get("lnn", "models.new_model.type") == "cfc"
        assert config_manager.is_dirty() is True

    def test_remove_model(self, config_manager_from_file):
        """测试移除模型配置"""
        assert config_manager_from_file.remove_model("cutting_force") is True
        assert config_manager_from_file.get_model_config("cutting_force") is None
        assert config_manager_from_file.is_dirty() is True

    def test_remove_nonexistent_model(self, config_manager):
        """测试移除不存在的模型"""
        assert config_manager.remove_model("nonexistent") is False

    def test_environment_adaptation_production(self):
        """测试生产环境适配"""
        config = {
            "lnn": {"enabled": True, "models_dir": "models", "default_device": "cpu"},
            "environment": {"name": "production"},
        }
        temp_dir = tempfile.mkdtemp()
        config_path = os.path.join(temp_dir, "prod.yaml")
        with open(config_path, "w") as f:
            yaml.dump(config, f)

        manager = YAMLConfigManager(config_path=config_path)
        assert manager.get("environment", "debug") is False

        shutil.rmtree(temp_dir)

    def test_environment_adaptation_testing(self):
        """测试测试环境适配"""
        config = {
            "lnn": {"enabled": True, "models_dir": "models", "default_device": "cpu"},
            "environment": {"name": "testing"},
        }
        temp_dir = tempfile.mkdtemp()
        config_path = os.path.join(temp_dir, "test.yaml")
        with open(config_path, "w") as f:
            yaml.dump(config, f)

        manager = YAMLConfigManager(config_path=config_path)
        assert manager.get("workflow", "timeout_seconds") == 60

        shutil.rmtree(temp_dir)

    def test_device_override(self):
        """测试设备覆盖"""
        config = {
            "lnn": {"enabled": True, "models_dir": "models", "default_device": "cuda"},
            "environment": {
                "name": "development",
                "device_override": "cpu",
            },
        }
        temp_dir = tempfile.mkdtemp()
        config_path = os.path.join(temp_dir, "override.yaml")
        with open(config_path, "w") as f:
            yaml.dump(config, f)

        manager = YAMLConfigManager(config_path=config_path)
        assert manager.get("lnn", "default_device") == "cpu"

        shutil.rmtree(temp_dir)

    def test_validate_invalid_model_type(self):
        """测试验证无效模型类型"""
        manager = YAMLConfigManager(use_defaults=True)
        manager._raw_config["lnn"]["models"]["bad_model"] = {
            "type": "invalid_type",
            "path": "bad.pt",
        }

        result = manager.validate()
        assert result["valid"] is False
        error_text = "\n".join(result["errors"])
        assert "Invalid model type" in error_text

    def test_validate_invalid_threshold(self):
        """测试验证无效阈值"""
        manager = YAMLConfigManager(use_defaults=True)
        manager._raw_config["lnn"]["thresholds"]["quick"] = 1.5

        result = manager.validate()
        assert result["valid"] is False
        error_text = "\n".join(result["errors"])
        assert "Threshold 'quick' must be a float between 0 and 1" in error_text

    def test_validate_invalid_environment(self):
        """测试验证无效环境"""
        manager = YAMLConfigManager(use_defaults=True)
        manager._raw_config["environment"]["name"] = "invalid_env"

        result = manager.validate()
        assert result["valid"] is False
        error_text = "\n".join(result["errors"])
        assert "Invalid environment name" in error_text

    def test_validate_workflow_config(self):
        """测试工作流配置验证"""
        manager = YAMLConfigManager(use_defaults=True)
        manager._raw_config["workflow"]["max_steps"] = -1

        result = manager.validate()
        assert result["valid"] is False
        error_text = "\n".join(result["errors"])
        assert "Workflow max_steps must be a positive integer" in error_text


class TestWorkflowLNNOrchestrator:
    """测试LNN工作流编排器"""

    @pytest.fixture
    def mock_engine(self):
        """模拟混合推理引擎"""
        engine = MagicMock()
        engine.router = MagicMock()
        engine.router.route.return_value = RoutingDecision(
            selected_engine=EngineType.LNN,
            selected_model="CFC-Fast",
            confidence=0.85,
            reasoning="Test routing decision",
        )
        engine.lnn_models = {"CFC-Fast": MagicMock()}

        mock_result = InferenceResult(
            prediction=[0.8],
            confidence=0.85,
            engine_used=EngineType.LNN,
            model_used="CFC-Fast",
            processing_time_ms=50.0,
        )
        engine.infer.return_value = mock_result

        rule_result = InferenceResult(
            prediction=[0.5],
            confidence=0.5,
            engine_used=EngineType.RULE,
            model_used="RuleEngine-v1",
            processing_time_ms=10.0,
        )
        engine._rule_inference.return_value = rule_result

        engine.get_engine_stats.return_value = {
            "inference_count": 0,
            "avg_processing_time_ms": 0.0,
            "registered_models": [],
            "router_stats": {},
            "fusion_stats": {},
            "cache_stats": {},
        }

        return engine

    @pytest.fixture
    def orchestrator(self, mock_engine):
        """创建工作流编排器"""
        return WorkflowLNNOrchestrator(engine=mock_engine)

    @pytest.fixture
    def orchestrator_with_config(self, mock_engine, tmp_path):
        """创建带配置文件的编排器"""
        config_data = {
            "lnn": {
                "enabled": True,
                "models_dir": "models/lnn",
                "default_device": "cpu",
                "models": {
                    "cutting_force": {"type": "cfc", "path": "cutting_force_v1.pt"},
                },
                "thresholds": {
                    "quick": 0.85,
                    "hybrid": 0.60,
                    "complexity": 3,
                },
            },
            "workflow": {
                "enabled": True,
                "max_steps": 10,
                "timeout_seconds": 300,
                "enable_fallback": True,
                "fallback_engine": "Rule",
            },
            "environment": {
                "name": "development",
                "debug": True,
            },
        }
        config_path = tmp_path / "test_config.yaml"
        with open(config_path, "w") as f:
            yaml.dump(config_data, f)

        return WorkflowLNNOrchestrator(
            config_path=str(config_path),
            engine=mock_engine,
        )

    def test_initialization(self, orchestrator):
        """测试编排器初始化"""
        assert orchestrator is not None
        assert orchestrator.config is not None
        assert orchestrator.engine is not None
        assert orchestrator._workflow_history == []

    def test_execute_workflow_with_string_input(self, orchestrator):
        """测试使用字符串输入执行工作流"""
        result = orchestrator.execute_workflow("预测刀具磨损")

        assert result is not None
        assert isinstance(result, WorkflowResult)
        assert result.workflow_id is not None
        assert len(orchestrator._workflow_history) == 1

    def test_execute_workflow_with_dict_input(self, orchestrator):
        """测试使用字典输入执行工作流"""
        task_input = {
            "task_description": "预测刀具磨损",
            "input_data": [0.1, 0.2, 0.3],
            "precision_requirement": 0.95,
        }
        result = orchestrator.execute_workflow(task_input)

        assert result is not None
        assert isinstance(result, WorkflowResult)

    def test_execute_workflow_with_task_input(self, orchestrator):
        """测试使用TaskInput执行工作流"""
        import numpy as np
        task_input = TaskInput(
            task_description="预测刀具磨损",
            input_data=np.array([[0.1, 0.2, 0.3]]),
            precision_requirement=0.9,
        )
        result = orchestrator.execute_workflow(task_input)

        assert result is not None
        assert isinstance(result, WorkflowResult)

    def test_execute_workflow_generates_plan(self, orchestrator):
        """测试工作流生成执行计划"""
        result = orchestrator.execute_workflow("预测刀具磨损")

        assert result.execution_plan is not None
        assert isinstance(result.execution_plan, WorkflowExecutionPlan)
        assert result.execution_plan.total_steps > 0

    def test_execute_workflow_steps_status(self, orchestrator):
        """测试工作流步骤状态"""
        result = orchestrator.execute_workflow("预测刀具磨损")

        for step_result in result.steps_result:
            assert "name" in step_result
            assert "status" in step_result
            assert "execution_time_ms" in step_result

    def test_execute_with_fallback_success(self, orchestrator):
        """测试成功执行降级工作流"""
        result = orchestrator.execute_with_fallback("预测刀具磨损")

        assert result is not None
        assert isinstance(result, WorkflowResult)

    def test_execute_with_fallback_triggers_fallback_on_low_confidence(self):
        """测试低置信度触发降级"""
        engine = MagicMock()
        engine.router = MagicMock()
        engine.router.route.return_value = RoutingDecision(
            selected_engine=EngineType.LNN,
            selected_model="CFC-Fast",
            confidence=0.3,
            reasoning="Low confidence routing",
        )
        engine.lnn_models = {"CFC-Fast": MagicMock()}

        low_conf_result = InferenceResult(
            prediction=[0.3],
            confidence=0.3,
            engine_used=EngineType.LNN,
            processing_time_ms=50.0,
        )
        engine.infer.return_value = low_conf_result

        rule_result = InferenceResult(
            prediction=[0.5],
            confidence=0.5,
            engine_used=EngineType.RULE,
            processing_time_ms=10.0,
        )
        engine._rule_inference.return_value = rule_result
        engine.get_engine_stats.return_value = {}

        orchestrator = WorkflowLNNOrchestrator(engine=engine)
        orchestrator._fallback_threshold = 0.50

        result = orchestrator.execute_with_fallback("预测刀具磨损")

        assert result.fallback_triggered is True
        assert "Low confidence" in result.fallback_reason

    def test_execute_with_fallback_lnn_not_available(self):
        """测试LNN不可用时触发降级"""
        engine = MagicMock()
        engine.lnn_models = {}
        engine.router = MagicMock()
        engine.initialize_models.side_effect = Exception("Models not available")
        engine.get_engine_stats.return_value = {}

        rule_result = InferenceResult(
            prediction=[0.5],
            confidence=0.5,
            engine_used=EngineType.RULE,
            processing_time_ms=10.0,
        )
        engine._rule_inference.return_value = rule_result

        orchestrator = WorkflowLNNOrchestrator(engine=engine)
        orchestrator.config.set("lnn", "enabled", False)

        result = orchestrator.execute_with_fallback("预测刀具磨损")

        assert result.fallback_triggered is True
        assert "LNN not available" in result.fallback_reason

    def test_workflow_result_serialization(self):
        """测试工作流结果序列化"""
        result = WorkflowResult(
            workflow_id="test_wf_001",
            success=True,
            output={"prediction": [0.8]},
            total_time_ms=100.0,
            fallback_triggered=False,
            timestamp=1234567890.0,
        )

        result_dict = result.to_dict()
        assert isinstance(result_dict, dict)
        assert result_dict["workflow_id"] == "test_wf_001"
        assert result_dict["success"] is True
        assert result_dict["total_time_ms"] == 100.0

    def test_workflow_step_status_enum(self):
        """测试工作流步骤状态枚举"""
        assert WorkflowStepStatus.PENDING.value == "pending"
        assert WorkflowStepStatus.RUNNING.value == "running"
        assert WorkflowStepStatus.COMPLETED.value == "completed"
        assert WorkflowStepStatus.FAILED.value == "failed"
        assert WorkflowStepStatus.FALLBACK.value == "fallback"

    def test_fallback_strategy_enum(self):
        """测试降级策略枚举"""
        assert FallbackStrategy.RULE_ENGINE.value == "rule_engine"
        assert FallbackStrategy.DEFAULT_OUTPUT.value == "default_output"
        assert FallbackStrategy.CACHED_RESULT.value == "cached_result"
        assert FallbackStrategy.ERROR_RAISE.value == "error_raise"

    def test_get_workflow_history(self, orchestrator):
        """测试获取工作流历史"""
        orchestrator.execute_workflow("task 1")
        orchestrator.execute_workflow("task 2")
        orchestrator.execute_workflow("task 3")

        history = orchestrator.get_workflow_history()
        assert len(history) == 3

        limited_history = orchestrator.get_workflow_history(limit=2)
        assert len(limited_history) == 2

    def test_get_statistics(self, orchestrator):
        """测试获取统计信息"""
        orchestrator.execute_workflow("task 1")
        orchestrator.execute_workflow("task 2")

        stats = orchestrator.get_statistics()

        assert "total_workflows" in stats
        assert "successful_workflows" in stats
        assert "failed_workflows" in stats
        assert "success_rate" in stats
        assert stats["total_workflows"] == 2

    def test_update_config(self, orchestrator):
        """测试运行时更新配置"""
        orchestrator.update_config("lnn", "thresholds.fallback", 0.60)
        assert orchestrator._fallback_threshold == 0.60

        orchestrator.update_config("workflow", "max_steps", 5)
        assert orchestrator._max_steps == 5

    def test_set_fallback_strategy(self, orchestrator):
        """测试设置降级策略"""
        orchestrator.set_fallback_strategy(FallbackStrategy.DEFAULT_OUTPUT)
        assert orchestrator._fallback_strategy == FallbackStrategy.DEFAULT_OUTPUT

        orchestrator.set_fallback_strategy(FallbackStrategy.CACHED_RESULT)
        assert orchestrator._fallback_strategy == FallbackStrategy.CACHED_RESULT

    def test_workflow_step_defaults(self):
        """测试工作流步骤默认值"""
        step = WorkflowStep(name="test_step")

        assert step.step_type == "lnn_inference"
        assert step.model_name is None
        assert step.output_key == "result"
        assert step.timeout_ms == 5000
        assert step.retry_count == 0
        assert step.status == WorkflowStepStatus.PENDING

    def test_workflow_execution_plan(self):
        """测试工作流执行计划"""
        steps = [
            WorkflowStep(name="step1", step_type="preprocess"),
            WorkflowStep(name="step2", step_type="inference"),
        ]
        plan = WorkflowExecutionPlan(
            workflow_id="test_plan",
            steps=steps,
            selected_model="CFC-Fast",
            total_steps=2,
        )

        assert plan.workflow_id == "test_plan"
        assert len(plan.steps) == 2
        assert plan.selected_model == "CFC-Fast"
        assert plan.status == WorkflowStepStatus.PENDING

    def test_preprocess_input_string(self, orchestrator):
        """测试字符串输入预处理"""
        task_input = orchestrator._preprocess_input("预测刀具磨损")

        assert isinstance(task_input, TaskInput)
        assert task_input.task_description == "预测刀具磨损"
        assert task_input.data_type == DataType.UNSTRUCTURED

    def test_preprocess_input_dict(self, orchestrator):
        """测试字典输入预处理"""
        user_input = {
            "task_description": "预测刀具磨损",
            "input_data": [0.1, 0.2, 0.3],
            "precision_requirement": 0.95,
            "time_sensitivity": 0.8,
        }
        task_input = orchestrator._preprocess_input(user_input)

        assert isinstance(task_input, TaskInput)
        assert task_input.task_description == "预测刀具磨损"
        assert task_input.precision_requirement == 0.95
        assert task_input.time_sensitivity == 0.8

    def test_preprocess_input_task_input(self, orchestrator):
        """测试TaskInput输入预处理"""
        original_input = TaskInput(
            task_description="test",
            input_data=[1, 2, 3],
        )
        task_input = orchestrator._preprocess_input(original_input)

        assert task_input is original_input

    def test_infer_task_category_temporal(self, orchestrator):
        """测试推断时序任务类别"""
        category = orchestrator._infer_task_category("预测未来趋势")
        assert category == TaskCategory.TIME_SERIES

    def test_infer_task_category_rule(self, orchestrator):
        """测试推断规则任务类别"""
        category = orchestrator._infer_task_category("检查规则验证")
        assert category == TaskCategory.RULE_BASED

    def test_infer_task_category_nlp(self, orchestrator):
        """测试推断NLP任务类别"""
        category = orchestrator._infer_task_category("解释分析结果")
        assert category == TaskCategory.NLP

    def test_infer_task_category_default(self, orchestrator):
        """测试默认任务类别"""
        category = orchestrator._infer_task_category("处理数据")
        assert category == TaskCategory.REGRESSION

    def test_execute_workflow_error_handling(self):
        """测试工作流错误处理"""
        engine = MagicMock()
        engine.router = MagicMock()
        engine.router.route.side_effect = Exception("Router error")
        engine.get_engine_stats.return_value = {}

        orchestrator = WorkflowLNNOrchestrator(engine=engine)
        result = orchestrator.execute_workflow("test task")

        assert result.success is False
        assert "Workflow execution error" in result.fallback_reason

    def test_generate_execution_plan(self, orchestrator):
        """测试生成执行计划"""
        task = TaskInput(
            task_description="预测刀具磨损",
            input_data=[0.1, 0.2, 0.3],
        )
        routing = RoutingDecision(
            selected_engine=EngineType.LNN,
            selected_model="CFC-Fast",
            confidence=0.85,
        )

        plan = orchestrator._generate_execution_plan("wf_001", task, routing)

        assert isinstance(plan, WorkflowExecutionPlan)
        assert plan.workflow_id == "wf_001"
        assert len(plan.steps) > 0
        assert plan.selected_model == "CFC-Fast"

    def test_log_workflow(self, orchestrator, tmp_path):
        """测试工作流日志记录"""
        log_dir = str(tmp_path / "logs" / "workflows")
        orchestrator._log_dir = log_dir
        orchestrator._log_enabled = True

        result = WorkflowResult(
            workflow_id="test_log_wf",
            success=True,
            output={"test": "data"},
            total_time_ms=50.0,
            timestamp=1234567890.0,
        )

        orchestrator._log_workflow(result)

        log_file = os.path.join(
            log_dir, f"workflow_{datetime.now().strftime('%Y-%m-%d')}.jsonl"
        )
        assert os.path.exists(log_file)

        with open(log_file, "r") as f:
            content = f.readline()
            assert "test_log_wf" in content

    def test_log_workflow_disabled(self, orchestrator, tmp_path):
        """测试禁用日志记录"""
        log_dir = str(tmp_path / "logs" / "workflows")
        orchestrator._log_dir = log_dir
        orchestrator._log_enabled = False

        result = WorkflowResult(
            workflow_id="test_no_log",
            success=True,
            total_time_ms=50.0,
            timestamp=1234567890.0,
        )

        orchestrator._log_workflow(result)

        assert not os.path.exists(log_dir)

    def test_save_config(self, orchestrator_with_config, tmp_path):
        """测试保存配置"""
        output_path = str(tmp_path / "saved_config.yaml")
        orchestrator_with_config.update_config("lnn", "enabled", False)
        orchestrator_with_config.save_config(output_path)

        assert os.path.exists(output_path)

        with open(output_path, "r") as f:
            saved_config = yaml.safe_load(f)
        assert saved_config["lnn"]["enabled"] is False


class TestDataClasses:
    """测试数据类"""

    def test_model_config(self):
        """测试模型配置数据类"""
        config = ModelConfig(
            type="cfc",
            path="model.pt",
            enabled=True,
            device="cuda",
        )

        assert config.type == "cfc"
        assert config.path == "model.pt"
        assert config.enabled is True
        assert config.device == "cuda"

    def test_threshold_config(self):
        """测试阈值配置数据类"""
        config = ThresholdConfig(
            quick=0.90,
            hybrid=0.70,
            complexity=5,
            fallback=0.60,
            confidence=0.80,
        )

        assert config.quick == 0.90
        assert config.hybrid == 0.70
        assert config.complexity == 5

    def test_lnn_config(self):
        """测试LNN配置数据类"""
        config = LNNConfig(
            enabled=True,
            models_dir="models/lnn",
            default_device="cuda",
        )

        assert config.enabled is True
        assert config.models_dir == "models/lnn"
        assert config.default_device == "cuda"

    def test_workflow_config(self):
        """测试工作流配置数据类"""
        config = WorkflowConfig(
            enabled=True,
            max_steps=15,
            timeout_seconds=600,
            enable_fallback=True,
            fallback_engine="Rule",
        )

        assert config.enabled is True
        assert config.max_steps == 15
        assert config.timeout_seconds == 600

    def test_environment_config(self):
        """测试环境配置数据类"""
        config = EnvironmentConfig(
            name="production",
            debug=False,
            device_override="cpu",
        )

        assert config.name == "production"
        assert config.debug is False
        assert config.device_override == "cpu"

    def test_app_config(self):
        """测试应用配置数据类"""
        config = AppConfig()

        assert isinstance(config.lnn, LNNConfig)
        assert isinstance(config.workflow, WorkflowConfig)
        assert isinstance(config.environment, EnvironmentConfig)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
