"""模型评估模块

负责训练后模型的评估与验证：
- 计算关键性能指标
- 判断模型是否达标
- 生成评估报告
- 集成模型注册服务

评估指标：
- 验证损失 (val_loss)
- 验证准确率 (val_accuracy)
- R²分数 (val_r2)
- 其他业务指标

设计原则：
- 新模型必须评估达标才能注册
- 评估指标可配置
- 保留评估历史记录
"""

from __future__ import annotations

import logging
import threading
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

import torch
import torch.nn as nn
from torch.utils.data import DataLoader

from app.services.model_registry_service import get_model_registry_service

logger = logging.getLogger(__name__)


class EvaluationConfig:
    """评估配置"""
    
    def __init__(
        self,
        # 指标阈值
        min_val_accuracy: float = 0.85,  # 最低验证准确率
        max_val_loss: float = 0.5,  # 最大验证损失
        min_val_r2: float = 0.7,  # 最低R²分数
        
        # 相对改进要求
        require_improvement: bool = True,  # 是否要求相对改进
        min_improvement_percent: float = 1.0,  # 最小改进百分比
        
        # 评估参数
        evaluation_batch_size: int = 64,
    ):
        self.min_val_accuracy = min_val_accuracy
        self.max_val_loss = max_val_loss
        self.min_val_r2 = min_val_r2
        self.require_improvement = require_improvement
        self.min_improvement_percent = min_improvement_percent
        self.evaluation_batch_size = evaluation_batch_size


class EvaluationResult:
    """评估结果"""
    
    def __init__(
        self,
        passed: bool,
        metrics: Dict[str, float],
        reason: str,
        baseline_metrics: Optional[Dict[str, float]] = None,
    ):
        self.passed = passed
        self.metrics = metrics
        self.reason = reason
        self.baseline_metrics = baseline_metrics
        self.timestamp = datetime.now()
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "passed": self.passed,
            "metrics": self.metrics,
            "reason": self.reason,
            "baseline_metrics": self.baseline_metrics,
            "timestamp": self.timestamp.isoformat(),
        }


class ModelEvaluator:
    """模型评估器
    
    负责：
    - 在验证集上评估模型
    - 计算性能指标
    - 判断是否达标
    - 与基线模型比较
    """
    
    def __init__(
        self,
        config: Optional[EvaluationConfig] = None,
    ):
        self.config = config or EvaluationConfig()
        self._evaluation_history: List[EvaluationResult] = []
        
        logger.info("ModelEvaluator initialized with config: %s", self.config.__dict__)
    
    def evaluate_model(
        self,
        model: nn.Module,
        val_loader: DataLoader,
        device: str = "cpu",
        baseline_metrics: Optional[Dict[str, float]] = None,
    ) -> EvaluationResult:
        """评估模型性能
        
        Args:
            model: 待评估模型
            val_loader: 验证数据加载器
            device: 计算设备
            baseline_metrics: 基线指标（用于比较）
            
        Returns:
            EvaluationResult: 评估结果
        """
        logger.info("Starting model evaluation...")
        
        try:
            # 1. 计算验证指标
            metrics = self._compute_metrics(model, val_loader, device)
            
            # 2. 检查绝对指标
            absolute_check = self._check_absolute_metrics(metrics)
            if not absolute_check["passed"]:
                return EvaluationResult(
                    passed=False,
                    metrics=metrics,
                    reason=f"绝对指标未达标: {absolute_check['reason']}",
                    baseline_metrics=baseline_metrics,
                )
            
            # 3. 检查相对改进（如果有基线）
            if self.config.require_improvement and baseline_metrics:
                relative_check = self._check_relative_improvement(metrics, baseline_metrics)
                if not relative_check["passed"]:
                    return EvaluationResult(
                        passed=False,
                        metrics=metrics,
                        reason=f"相对改进不足: {relative_check['reason']}",
                        baseline_metrics=baseline_metrics,
                    )
            
            # 4. 评估通过
            return EvaluationResult(
                passed=True,
                metrics=metrics,
                reason="所有评估指标达标",
                baseline_metrics=baseline_metrics,
            )
            
        except (RuntimeError, ValueError, KeyError, TypeError, OSError) as e:
            logger.error("Model evaluation failed: %s", e, exc_info=True)
            return EvaluationResult(
                passed=False,
                metrics={},
                reason=f"评估过程出错: {str(e)}",
                baseline_metrics=baseline_metrics,
            )
    
    def _compute_metrics(
        self,
        model: nn.Module,
        val_loader: DataLoader,
        device: str,
    ) -> Dict[str, float]:
        """计算验证指标
        
        Args:
            model: 模型
            val_loader: 验证数据加载器
            device: 计算设备
            
        Returns:
            指标字典
        """
        model.eval()
        device_obj = torch.device(device)
        model = model.to(device_obj)
        
        total_loss = 0.0
        total_correct = 0
        total_samples = 0
        all_preds = []
        all_labels = []
        
        criterion = nn.MSELoss()
        
        with torch.no_grad():
            for batch_X, batch_y in val_loader:
                batch_X = batch_X.to(device_obj)
                batch_y = batch_y.to(device_obj)
                
                outputs = model(batch_X)
                if isinstance(outputs, tuple):
                    outputs = outputs[0]
                
                loss = criterion(outputs, batch_y)
                total_loss += loss.item() * batch_X.size(0)
                
                all_preds.append(outputs.cpu())
                all_labels.append(batch_y.cpu())
                total_samples += batch_X.size(0)
        
        # 计算准确率（基于分类任务）
        all_preds = torch.cat(all_preds, dim=0).numpy()
        all_labels = torch.cat(all_labels, dim=0).numpy()
        
        # 对于回归任务，使用R²作为主要指标
        r2 = self._compute_r2(all_labels, all_preds)
        
        # 计算准确率（假设第一个输出是分类结果）
        if all_preds.shape[1] > 1:
            preds_class = (all_preds[:, 0] > 0.5).astype(float)
            labels_class = all_labels[:, 0]
            accuracy = float((preds_class == labels_class).mean())
        else:
            accuracy = 0.0  # 纯回归任务
        
        avg_loss = total_loss / total_samples if total_samples > 0 else float('inf')
        
        metrics = {
            "val_loss": round(avg_loss, 4),
            "val_accuracy": round(accuracy, 4),
            "val_r2": round(r2, 4),
            "total_samples": total_samples,
        }
        
        logger.info("Evaluation metrics: %s", metrics)
        return metrics
    
    def _compute_r2(self, y_true, y_pred) -> float:
        """计算R²分数"""
        import numpy as np
        
        y_true = y_true.flatten()
        y_pred = y_pred.flatten()
        
        ss_res = np.sum((y_true - y_pred) ** 2)
        ss_tot = np.sum((y_true - np.mean(y_true)) ** 2)
        
        if ss_tot == 0:
            return 0.0
        
        return float(1 - ss_res / ss_tot)
    
    def _check_absolute_metrics(self, metrics: Dict[str, float]) -> Dict[str, Any]:
        """检查绝对指标是否达标"""
        # 检查验证损失
        if metrics.get("val_loss", float('inf')) > self.config.max_val_loss:
            return {
                "passed": False,
                "reason": f"验证损失({metrics.get('val_loss')})超过阈值({self.config.max_val_loss})",
            }
        
        # 检查验证准确率（如果有）
        if metrics.get("val_accuracy", 0) < self.config.min_val_accuracy:
            # 对于纯回归任务，准确率可能为0，跳过此检查
            if metrics.get("val_accuracy", 0) > 0:
                return {
                    "passed": False,
                    "reason": f"验证准确率({metrics.get('val_accuracy')})低于阈值({self.config.min_val_accuracy})",
                }
        
        # 检查R²分数
        if metrics.get("val_r2", 0) < self.config.min_val_r2:
            return {
                "passed": False,
                "reason": f"R²分数({metrics.get('val_r2')})低于阈值({self.config.min_val_r2})",
            }
        
        return {"passed": True, "reason": "所有绝对指标达标"}
    
    def _check_relative_improvement(
        self,
        metrics: Dict[str, float],
        baseline: Dict[str, float],
    ) -> Dict[str, Any]:
        """检查相对改进是否达标"""
        # 检查验证损失改进
        baseline_loss = baseline.get("val_loss", float('inf'))
        current_loss = metrics.get("val_loss", float('inf'))
        
        if baseline_loss < float('inf'):
            loss_improvement = (baseline_loss - current_loss) / baseline_loss * 100
            if loss_improvement < -self.config.min_improvement_percent:
                return {
                    "passed": False,
                    "reason": f"验证损失未改进: {loss_improvement:.2f}% (要求>={self.config.min_improvement_percent}%)",
                }
        
        # 检查R²改进
        baseline_r2 = baseline.get("val_r2", 0)
        current_r2 = metrics.get("val_r2", 0)
        
        if baseline_r2 > 0:
            r2_improvement = (current_r2 - baseline_r2) / baseline_r2 * 100
            if r2_improvement < -self.config.min_improvement_percent:
                return {
                    "passed": False,
                    "reason": f"R²分数未改进: {r2_improvement:.2f}%",
                }
        
        return {"passed": True, "reason": "相对改进达标"}
    
    def register_model_if_passed(
        self,
        model: nn.Module,
        evaluation_result: EvaluationResult,
        model_name: str,
        training_params: Dict[str, Any],
    ) -> Dict[str, Any]:
        """如果评估通过则注册模型
        
        Args:
            model: 训练好的模型
            evaluation_result: 评估结果
            model_name: 模型名称
            training_params: 训练参数
            
        Returns:
            注册结果
        """
        if not evaluation_result.passed:
            return {
                "success": False,
                "reason": f"评估未通过: {evaluation_result.reason}",
            }
        
        try:
            # 获取模型注册服务
            registry_service = get_model_registry_service()
            
            # 生成版本标签
            version_tag = f"v{int(time.time())}"
            
            # 准备模型信息
            model_info = {
                "model_name": model_name,
                "version": version_tag,
                "model": model,
                "metrics": evaluation_result.metrics,
                "training_params": training_params,
                "evaluation_result": evaluation_result.to_dict(),
                "registered_at": datetime.now().isoformat(),
            }
            
            # 注册模型
            success = registry_service.register_model(model_info)
            
            if success:
                logger.info("Model registered: %s (%s)", model_name, version_tag)
                return {
                    "success": True,
                    "model_name": model_name,
                    "version": version_tag,
                    "metrics": evaluation_result.metrics,
                }
            else:
                return {
                    "success": False,
                    "reason": "模型注册失败",
                }
                
        except (RuntimeError, ValueError, KeyError, OSError) as e:
            logger.error("Model registration failed: %s", e, exc_info=True)
            return {
                "success": False,
                "reason": f"注册过程出错: {str(e)}",
            }
    
    def get_evaluation_history(self) -> List[Dict[str, Any]]:
        """获取评估历史"""
        return [result.to_dict() for result in self._evaluation_history]


# 全局实例
_evaluator_instance: Optional[ModelEvaluator] = None
_evaluator_instance_lock = threading.Lock()


def get_model_evaluator(config: Optional[EvaluationConfig] = None) -> ModelEvaluator:
    """获取全局评估器实例"""
    # 安全修复：双重检查锁，防止并发创建多个实例
    global _evaluator_instance
    if _evaluator_instance is None:
        with _evaluator_instance_lock:
            if _evaluator_instance is None:
                _evaluator_instance = ModelEvaluator(config)
    return _evaluator_instance


def reset_model_evaluator() -> None:
    """重置全局评估器实例（主要用于测试）。"""
    global _evaluator_instance
    with _evaluator_instance_lock:
        _evaluator_instance = None
