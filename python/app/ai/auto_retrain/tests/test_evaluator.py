"""模型评估模块单元测试"""

import pytest
from unittest.mock import Mock, patch, MagicMock
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset

from app.ai.auto_retrain.evaluator import (
    ModelEvaluator,
    EvaluationConfig,
    EvaluationResult,
    get_model_evaluator,
)


class TestEvaluationConfig:
    """评估配置测试"""
    
    def test_default_config(self):
        """测试默认配置"""
        config = EvaluationConfig()
        assert config.min_val_accuracy == 0.85
        assert config.max_val_loss == 0.5
        assert config.min_val_r2 == 0.7
        assert config.require_improvement is True
    
    def test_custom_config(self):
        """测试自定义配置"""
        config = EvaluationConfig(
            min_val_accuracy=0.90,
            max_val_loss=0.3,
        )
        assert config.min_val_accuracy == 0.90
        assert config.max_val_loss == 0.3


class TestEvaluationResult:
    """评估结果测试"""
    
    def test_passed_result(self):
        """测试通过结果"""
        result = EvaluationResult(
            passed=True,
            metrics={"val_loss": 0.3, "val_r2": 0.85},
            reason="评估通过",
        )
        assert result.passed is True
        assert result.metrics["val_loss"] == 0.3
    
    def test_failed_result(self):
        """测试失败结果"""
        result = EvaluationResult(
            passed=False,
            metrics={"val_loss": 0.8},
            reason="验证损失过高",
        )
        assert result.passed is False
    
    def test_result_to_dict(self):
        """测试结果序列化"""
        result = EvaluationResult(
            passed=True,
            metrics={"val_loss": 0.3},
            reason="测试",
            baseline_metrics={"val_loss": 0.4},
        )
        result_dict = result.to_dict()
        assert "passed" in result_dict
        assert "metrics" in result_dict
        assert "baseline_metrics" in result_dict
        assert "timestamp" in result_dict


class TestModelEvaluator:
    """模型评估器测试"""
    
    @pytest.fixture
    def simple_model(self):
        """创建简单测试模型"""
        return nn.Sequential(
            nn.Linear(6, 32),
            nn.ReLU(),
            nn.Linear(32, 3),
        )
    
    @pytest.fixture
    def mock_dataloader(self):
        """创建模拟数据加载器"""
        # 创建随机数据
        X = torch.randn(100, 6)
        y = torch.randn(100, 3)
        dataset = TensorDataset(X, y)
        return DataLoader(dataset, batch_size=32)
    
    @pytest.fixture
    def evaluator(self):
        """创建测试评估器"""
        config = EvaluationConfig(
            min_val_accuracy=0.5,
            max_val_loss=1.0,
            min_val_r2=0.0,
            require_improvement=False,
        )
        return ModelEvaluator(config=config)
    
    def test_compute_r2_perfect(self, evaluator):
        """测试R²计算 - 完美预测"""
        import numpy as np
        y_true = np.array([1.0, 2.0, 3.0, 4.0])
        y_pred = np.array([1.0, 2.0, 3.0, 4.0])
        r2 = evaluator._compute_r2(y_true, y_pred)
        assert r2 == 1.0
    
    def test_compute_r2_poor(self, evaluator):
        """测试R²计算 - 差预测"""
        import numpy as np
        y_true = np.array([1.0, 2.0, 3.0, 4.0])
        y_pred = np.array([4.0, 3.0, 2.0, 1.0])
        r2 = evaluator._compute_r2(y_true, y_pred)
        assert r2 < 0
    
    def test_check_absolute_metrics_pass(self, evaluator):
        """测试绝对指标检查 - 通过"""
        metrics = {
            "val_loss": 0.3,
            "val_accuracy": 0.9,
            "val_r2": 0.8,
        }
        result = evaluator._check_absolute_metrics(metrics)
        assert result["passed"] is True
    
    def test_check_absolute_metrics_fail_loss(self, evaluator):
        """测试绝对指标检查 - 损失过高"""
        metrics = {
            "val_loss": 2.0,  # 超过阈值1.0
            "val_accuracy": 0.9,
            "val_r2": 0.8,
        }
        result = evaluator._check_absolute_metrics(metrics)
        assert result["passed"] is False
        assert "验证损失" in result["reason"]
    
    def test_check_absolute_metrics_fail_r2(self, evaluator):
        """测试绝对指标检查 - R²过低"""
        config = EvaluationConfig(min_val_r2=0.9, require_improvement=False)
        evaluator = ModelEvaluator(config=config)
        metrics = {
            "val_loss": 0.3,
            "val_accuracy": 0.9,
            "val_r2": 0.5,  # 低于阈值0.9
        }
        result = evaluator._check_absolute_metrics(metrics)
        assert result["passed"] is False
        assert "R²" in result["reason"]
    
    def test_check_relative_improvement_pass(self, evaluator):
        """测试相对改进检查 - 通过"""
        metrics = {"val_loss": 0.3, "val_r2": 0.85}
        baseline = {"val_loss": 0.4, "val_r2": 0.80}
        result = evaluator._check_relative_improvement(metrics, baseline)
        assert result["passed"] is True
    
    def test_check_relative_improvement_fail(self, evaluator):
        """测试相对改进检查 - 失败"""
        metrics = {"val_loss": 0.5, "val_r2": 0.70}
        baseline = {"val_loss": 0.4, "val_r2": 0.80}
        result = evaluator._check_relative_improvement(metrics, baseline)
        assert result["passed"] is False
    
    def test_evaluate_model_success(self, evaluator, simple_model, mock_dataloader):
        """测试模型评估 - 成功"""
        result = evaluator.evaluate_model(
            model=simple_model,
            val_loader=mock_dataloader,
            device="cpu",
        )
        # 由于是随机模型，可能通过也可能不通过，但不应抛出异常
        assert isinstance(result, EvaluationResult)
        assert result.metrics is not None
    
    def test_evaluate_model_with_baseline(self, evaluator, simple_model, mock_dataloader):
        """测试模型评估 - 带基线"""
        baseline = {"val_loss": 0.5, "val_r2": 0.7}
        result = evaluator.evaluate_model(
            model=simple_model,
            val_loader=mock_dataloader,
            device="cpu",
            baseline_metrics=baseline,
        )
        assert result.baseline_metrics == baseline
    
    @patch("app.ai.auto_retrain.evaluator.get_model_registry_service")
    def test_register_model_if_passed_success(self, mock_registry_service, evaluator, simple_model):
        """测试模型注册 - 评估通过"""
        # 模拟注册服务
        mock_service = Mock()
        mock_service.register_model = Mock(return_value=True)
        mock_registry_service.return_value = mock_service
        
        # 创建通过的评估结果
        eval_result = EvaluationResult(
            passed=True,
            metrics={"val_loss": 0.3, "val_r2": 0.85},
            reason="评估通过",
        )
        
        result = evaluator.register_model_if_passed(
            model=simple_model,
            evaluation_result=eval_result,
            model_name="test_model",
            training_params={"epochs": 10},
        )
        
        assert result["success"] is True
        assert "version" in result
    
    def test_register_model_if_passed_failed(self, evaluator, simple_model):
        """测试模型注册 - 评估未通过"""
        eval_result = EvaluationResult(
            passed=False,
            metrics={"val_loss": 0.8},
            reason="验证损失过高",
        )
        
        result = evaluator.register_model_if_passed(
            model=simple_model,
            evaluation_result=eval_result,
            model_name="test_model",
            training_params={"epochs": 10},
        )
        
        assert result["success"] is False
        assert "评估未通过" in result["reason"]
    
    def test_get_evaluation_history(self, evaluator):
        """测试获取评估历史"""
        history = evaluator.get_evaluation_history()
        assert isinstance(history, list)


class TestGetModelEvaluator:
    """全局评估器实例测试"""
    
    def test_get_evaluator_singleton(self):
        """测试单例模式"""
        evaluator1 = get_model_evaluator()
        evaluator2 = get_model_evaluator()
        assert evaluator1 is evaluator2
