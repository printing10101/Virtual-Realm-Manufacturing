"""Base LNN (Liquid Neural Network) Model Interface.

Defines the unified interface and base functionality for all LNN model implementations.
Provides abstract methods for building, training, and evaluating models, along with
concrete utility methods for confidence calculation, uncertainty estimation, and
performance measurement.

Key components:
    - BaseLNNModel: Abstract base class defining the LNN model contract.

Example:
    >>> class MyLNNModel(BaseLNNModel):
    ...     def build(self): pass
    ...     def forward(self, x): return x
    ...     def predict(self, x): return self.forward(x)
    ...     def _train_step(self, data, labels, batch_size, lr): return 0.0
    ...     def _validate(self, val_data, val_labels): return 0.0
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
import time


class BaseLNNModel(ABC):
    """Abstract base class defining the LNN model contract.

    All LNN model implementations must inherit from this class and implement
    the abstract methods: build(), forward(), predict(), _train_step(), and _validate().

    Provides concrete methods for:
    - Confidence-based prediction (predict_with_confidence)
    - Uncertainty calculation (calculate_uncertainty)
    - Training loop orchestration (train)
    - Model evaluation with multiple metrics (evaluate)
    - Model serialization (save/load)
    - Inference time benchmarking (measure_inference_time)

    Attributes:
        model_name: Human-readable model name.
        input_dim: Input feature dimension.
        output_dim: Output prediction dimension.
        device: Computation device ('cpu', 'cuda').
        is_trained: Whether the model has been trained.
        training_history: Dictionary tracking loss and accuracy over epochs.
        config: Additional model configuration parameters.

    Example:
        >>> model = CFCModel(model_name="Test", input_dim=10, output_dim=2)
        >>> model.build()
        >>> model.input_dim
        10
    """

    def __init__(
        self,
        model_name: str,
        input_dim: int,
        output_dim: int,
        device: str = "cpu",
        **kwargs,
    ):
        """
        初始化LNN基类

        Args:
            model_name: 模型名称
            input_dim: 输入维度
            output_dim: 输出维度
            device: 计算设备 ('cpu', 'cuda')
            **kwargs: 其他模型参数
        """
        self.model_name = model_name
        self.input_dim = input_dim
        self.output_dim = output_dim
        self.device = device
        self.is_trained = False
        self.training_history: Dict[str, List[float]] = {
            "loss": [],
            "accuracy": [],
            "val_loss": [],
            "val_accuracy": [],
        }
        self.config = kwargs

    @abstractmethod
    def build(self) -> None:
        """构建模型结构，子类必须实现"""
        pass

    @abstractmethod
    def forward(self, x: np.ndarray) -> np.ndarray:
        """
        前向传播

        Args:
            x: 输入数据 (batch_size, input_dim)

        Returns:
            模型输出 (batch_size, output_dim)
        """
        pass

    @abstractmethod
    def predict(self, x: np.ndarray) -> np.ndarray:
        """
        预测接口

        Args:
            x: 输入数据

        Returns:
            预测结果
        """
        pass

    def predict_with_confidence(self, x: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """
        带置信度的预测

        Args:
            x: 输入数据

        Returns:
            (predictions, confidences) 预测结果和对应的置信度
        """
        predictions = self.predict(x)
        confidences = self._calculate_confidence(predictions)
        return predictions, confidences

    def _calculate_confidence(self, predictions: np.ndarray) -> np.ndarray:
        """
        基于模型输出计算置信度

        对于分类任务（多维输出）：使用softmax归一化后的最大概率作为置信度
        对于回归任务（单值输出）：返回默认置信度0.8

        Args:
            predictions: 模型原始输出

        Returns:
            置信度数组 (0-1之间)
        """
        if predictions.ndim == 1:
            predictions = predictions.reshape(1, -1)

        # 回归任务：单值输出，使用默认置信度
        if predictions.shape[1] == 1:
            return np.ones(predictions.shape[0]) * 0.8

        # 分类任务：多维输出，使用softmax归一化后的最大概率
        exp_preds = np.exp(predictions - np.max(predictions, axis=1, keepdims=True))
        softmax_preds = exp_preds / np.sum(exp_preds, axis=1, keepdims=True)

        # 取最大概率作为置信度
        confidences = np.max(softmax_preds, axis=1)
        return confidences

    def calculate_uncertainty(self, predictions: np.ndarray) -> Dict[str, float]:
        """
        计算预测不确定性

        Args:
            predictions: 模型预测结果

        Returns:
            不确定性指标字典
        """
        if predictions.ndim == 1:
            predictions = predictions.reshape(1, -1)

        # 计算熵
        exp_preds = np.exp(predictions - np.max(predictions, axis=1, keepdims=True))
        softmax_preds = exp_preds / np.sum(exp_preds, axis=1, keepdims=True)

        entropy = -np.sum(softmax_preds * np.log(softmax_preds + 1e-10), axis=1)
        max_entropy = np.log(predictions.shape[1])
        normalized_entropy = entropy / (max_entropy + 1e-10)

        return {
            "entropy": float(np.mean(entropy)),
            "normalized_entropy": float(np.mean(normalized_entropy)),
            "confidence": float(1 - np.mean(normalized_entropy)),
            "variance": float(np.var(predictions)),
        }

    def train(
        self,
        train_data: np.ndarray,
        train_labels: np.ndarray,
        val_data: Optional[np.ndarray] = None,
        val_labels: Optional[np.ndarray] = None,
        epochs: int = 100,
        batch_size: int = 32,
        learning_rate: float = 0.001,
        **kwargs,
    ) -> Dict[str, List[float]]:
        """
        训练模型

        Args:
            train_data: 训练数据
            train_labels: 训练标签
            val_data: 验证数据
            val_labels: 验证标签
            epochs: 训练轮数
            batch_size: 批次大小
            learning_rate: 学习率

        Returns:
            训练历史记录
        """
        self.build()

        for epoch in range(epochs):
            # 简单模拟训练过程（子类应实现具体逻辑）
            epoch_loss = self._train_step(
                train_data, train_labels, batch_size, learning_rate
            )
            self.training_history["loss"].append(epoch_loss)

            if val_data is not None and val_labels is not None:
                val_loss = self._validate(val_data, val_labels)
                self.training_history["val_loss"].append(val_loss)

        self.is_trained = True
        return self.training_history

    @abstractmethod
    def _train_step(
        self,
        data: np.ndarray,
        labels: np.ndarray,
        batch_size: int,
        learning_rate: float,
    ) -> float:
        """
        单步训练

        Args:
            data: 训练数据
            labels: 训练标签
            batch_size: 批次大小
            learning_rate: 学习率

        Returns:
            当前step的loss
        """
        pass

    @abstractmethod
    def _validate(self, val_data: np.ndarray, val_labels: np.ndarray) -> float:
        """
        验证模型

        Args:
            val_data: 验证数据
            val_labels: 验证标签

        Returns:
            验证损失
        """
        pass

    def evaluate(
        self,
        test_data: np.ndarray,
        test_labels: np.ndarray,
        metrics: Optional[List[str]] = None,
    ) -> Dict[str, float]:
        """
        评估模型性能

        Args:
            test_data: 测试数据
            test_labels: 测试标签
            metrics: 评估指标列表

        Returns:
            评估结果字典
        """
        if not self.is_trained:
            raise RuntimeError(
                "LNN 模型评估失败：模型尚未完成训练，无法执行评估。评估操作只能在模型训练完成后进行。请先调用 train() 方法完成模型训练，或加载已训练的检查点。"
            )

        predictions = self.predict(test_data)

        results = {}

        if metrics is None or "accuracy" in metrics:
            results["accuracy"] = self._compute_accuracy(test_labels, predictions)

        if metrics is None or "precision" in metrics:
            results["precision"] = self._compute_precision(test_labels, predictions)

        if metrics is None or "recall" in metrics:
            results["recall"] = self._compute_recall(test_labels, predictions)

        if metrics is None or "f1" in metrics:
            results["f1"] = self._compute_f1(test_labels, predictions)

        if metrics is None or "loss" in metrics:
            results["loss"] = self._validate(test_data, test_labels)

        return results

    def _compute_accuracy(self, labels: np.ndarray, predictions: np.ndarray) -> float:
        """计算准确率"""
        if predictions.ndim > 1:
            pred_classes = np.argmax(predictions, axis=1)
        else:
            pred_classes = (predictions > 0.5).astype(int)

        if labels.ndim > 1:
            true_classes = np.argmax(labels, axis=1)
        else:
            true_classes = labels.astype(int)

        return float(np.mean(pred_classes == true_classes))

    def _compute_precision(self, labels: np.ndarray, predictions: np.ndarray) -> float:
        """计算精确率"""
        if predictions.ndim > 1:
            pred_classes = np.argmax(predictions, axis=1)
        else:
            pred_classes = (predictions > 0.5).astype(int)

        if labels.ndim > 1:
            true_classes = np.argmax(labels, axis=1)
        else:
            true_classes = labels.astype(int)

        tp = np.sum((pred_classes == 1) & (true_classes == 1))
        fp = np.sum((pred_classes == 1) & (true_classes == 0))

        if tp + fp == 0:
            return 0.0
        return float(tp / (tp + fp))

    def _compute_recall(self, labels: np.ndarray, predictions: np.ndarray) -> float:
        """计算召回率"""
        if predictions.ndim > 1:
            pred_classes = np.argmax(predictions, axis=1)
        else:
            pred_classes = (predictions > 0.5).astype(int)

        if labels.ndim > 1:
            true_classes = np.argmax(labels, axis=1)
        else:
            true_classes = labels.astype(int)

        tp = np.sum((pred_classes == 1) & (true_classes == 1))
        fn = np.sum((pred_classes == 0) & (true_classes == 1))

        if tp + fn == 0:
            return 0.0
        return float(tp / (tp + fn))

    def _compute_f1(self, labels: np.ndarray, predictions: np.ndarray) -> float:
        """计算F1分数"""
        precision = self._compute_precision(labels, predictions)
        recall = self._compute_recall(labels, predictions)

        if precision + recall == 0:
            return 0.0
        return float(2 * precision * recall / (precision + recall))

    def get_model_info(self) -> Dict[str, Any]:
        """获取模型信息"""
        return {
            "model_name": self.model_name,
            "input_dim": self.input_dim,
            "output_dim": self.output_dim,
            "device": self.device,
            "is_trained": self.is_trained,
            "config": self.config,
            "training_epochs": len(self.training_history.get("loss", [])),
        }

    def save(self, path: str) -> None:
        """
        保存模型

        Args:
            path: 保存路径
        """
        np.savez(
            path,
            model_name=self.model_name,
            input_dim=self.input_dim,
            output_dim=self.output_dim,
            is_trained=self.is_trained,
        )

    def load(self, path: str) -> None:
        """
        加载模型

        Args:
            path: 模型路径
        """
        data = np.load(path)
        self.model_name = str(data["model_name"])
        self.input_dim = int(data["input_dim"])
        self.output_dim = int(data["output_dim"])
        self.is_trained = bool(data["is_trained"])

    def measure_inference_time(
        self, x: np.ndarray, n_runs: int = 100
    ) -> Dict[str, float]:
        """
        测量推理时间

        Args:
            x: 输入数据
            n_runs: 运行次数

        Returns:
            推理时间统计
        """
        times = []
        for _ in range(n_runs):
            start = time.perf_counter()
            self.predict(x)
            end = time.perf_counter()
            times.append((end - start) * 1000)  # 转换为毫秒

        return {
            "mean_ms": np.mean(times),
            "std_ms": np.std(times),
            "min_ms": np.min(times),
            "max_ms": np.max(times),
            "p50_ms": np.percentile(times, 50),
            "p95_ms": np.percentile(times, 95),
            "p99_ms": np.percentile(times, 99),
        }
