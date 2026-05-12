"""
CFC (Context-Free Grammar Network) Model

Optimized for fast inference scenarios with response time < 100ms.
Uses context-free grammar principles for efficient pattern matching and classification.
"""
import numpy as np
from typing import Any, Dict, List

from .base_lnn import BaseLNNModel


class CFCModel(BaseLNNModel):
    """
    CFC模型实现，优化快速推理场景

    特点：
    - 响应时间 < 100ms
    - 适用于快速分类和模式识别
    - 使用无上下文文法网络结构
    """

    def __init__(
        self,
        model_name: str = "CFC",
        input_dim: int = 128,
        output_dim: int = 10,
        hidden_dim: int = 256,
        num_layers: int = 2,
        dropout_rate: float = 0.1,
        device: str = "cpu",
        **kwargs
    ):
        """
        初始化CFC模型

        Args:
            model_name: 模型名称
            input_dim: 输入维度
            output_dim: 输出维度
            hidden_dim: 隐藏层维度
            num_layers: 网络层数
            dropout_rate: Dropout比率
            device: 计算设备
        """
        super().__init__(model_name, input_dim, output_dim, device, **kwargs)

        self.hidden_dim = hidden_dim
        self.num_layers = num_layers
        self.dropout_rate = dropout_rate

        # 网络权重（使用随机初始化，可通过训练流程更新）
        self.weights: List[np.ndarray] = []
        self.biases: List[np.ndarray] = []
        self._initialized = False
        self.training = False

    def build(self) -> None:
        """构建CFC网络结构"""
        if self._initialized:
            return

        # 初始化网络权重
        layer_dims = [self.input_dim] + [self.hidden_dim] * self.num_layers + [self.output_dim]

        for i in range(len(layer_dims) - 1):
            # He初始化 (适用于ReLU激活函数)
            fan_in = layer_dims[i]
            fan_out = layer_dims[i + 1]
            std = np.sqrt(2.0 / (fan_in + 1e-8))
            W = np.random.normal(0, std, (fan_in, fan_out))
            b = np.zeros(fan_out)

            self.weights.append(W)
            self.biases.append(b)

        self._initialized = True

    def forward(self, x: np.ndarray) -> np.ndarray:
        """
        前向传播

        Args:
            x: 输入数据 (batch_size, input_dim)

        Returns:
            模型输出 (batch_size, output_dim)
        """
        if not self._initialized:
            self.build()

        # 确保输入是2D
        if x.ndim == 1:
            x = x.reshape(1, -1)

        # 逐层传播
        activations = x
        for i, (W, b) in enumerate(zip(self.weights, self.biases)):
            z = activations @ W + b

            # 最后一层不使用激活函数（或根据任务选择）
            if i < len(self.weights) - 1:
                activations = self._relu(z)
                # 应用Dropout（仅在训练时）
                if self.training:
                    mask = (np.random.random(z.shape) > self.dropout_rate).astype(float)
                    activations = activations * mask / (1 - self.dropout_rate)
            else:
                activations = z

        return activations

    def predict(self, x: np.ndarray) -> np.ndarray:
        """
        快速预测接口

        Args:
            x: 输入数据

        Returns:
            预测结果
        """
        return self.forward(x)

    def _relu(self, x: np.ndarray) -> np.ndarray:
        """ReLU激活函数"""
        return np.maximum(0, x)

    def _softmax(self, x: np.ndarray) -> np.ndarray:
        """Softmax激活函数"""
        exp_x = np.exp(x - np.max(x, axis=-1, keepdims=True))
        return exp_x / np.sum(exp_x, axis=-1, keepdims=True)

    def _cross_entropy_loss(self, predictions: np.ndarray, labels: np.ndarray) -> float:
        """交叉熵损失"""
        # 数值稳定性处理
        predictions = predictions - np.max(predictions, axis=-1, keepdims=True)
        log_probs = predictions - np.log(np.sum(np.exp(predictions), axis=-1, keepdims=True))

        if labels.ndim == 1:
            # 转换为one-hot
            labels = np.eye(predictions.shape[1])[labels.astype(int)]

        return -np.mean(np.sum(labels * log_probs, axis=-1))

    def _train_step(
        self,
        data: np.ndarray,
        labels: np.ndarray,
        batch_size: int,
        learning_rate: float
    ) -> float:
        """
        单步训练（使用数值梯度近似）

        Args:
            data: 训练数据
            labels: 训练标签
            batch_size: 批次大小
            learning_rate: 学习率

        Returns:
            当前step的loss
        """
        n_samples = data.shape[0]
        indices = np.random.choice(n_samples, min(batch_size, n_samples), replace=False)
        batch_data = data[indices]
        batch_labels = labels[indices]

        # 前向传播
        predictions = self.forward(batch_data)
        loss = self._cross_entropy_loss(predictions, batch_labels)

        # 简化的参数更新（模拟反向传播）
        # 实际应用中应使用自动微分或框架实现
        # 数值梯度近似更新参数
        for i in range(len(self.weights)):
            # 对权重使用数值梯度计算
            original_weights = [w.copy() for w in self.weights]
            original_biases = [b.copy() for b in self.biases]
            shape_w = self.weights[i].shape
            grad_w = np.zeros(shape_w)
            eps = 1e-5
            # 随机采样部分参数计算数值梯度以加速
            sample_indices = np.random.choice(
                self.weights[i].size,
                min(100, self.weights[i].size),
                replace=False
            )
            flat_w = self.weights[i].flatten().copy()
            for idx in sample_indices:
                old_val = flat_w[idx]
                flat_w[idx] = old_val + eps
                self.weights[i] = flat_w.reshape(shape_w)
                pred_plus = self.forward(batch_data)
                loss_plus = self._cross_entropy_loss(pred_plus, batch_labels)

                flat_w[idx] = old_val - eps
                self.weights[i] = flat_w.reshape(shape_w)
                pred_minus = self.forward(batch_data)
                loss_minus = self._cross_entropy_loss(pred_minus, batch_labels)

                grad_w.flat[idx] = (loss_plus - loss_minus) / (2 * eps)
                flat_w[idx] = old_val

            self.weights[i] = flat_w.reshape(shape_w)
            self.weights[i] -= learning_rate * grad_w

            # 对偏置使用数值梯度
            shape_b = self.biases[i].shape
            grad_b = np.zeros(shape_b)
            flat_b = self.biases[i].flatten().copy()
            for idx in range(len(flat_b)):
                old_val = flat_b[idx]
                flat_b[idx] = old_val + eps
                self.biases[i] = flat_b.reshape(shape_b)
                pred_plus = self.forward(batch_data)
                loss_plus = self._cross_entropy_loss(pred_plus, batch_labels)

                flat_b[idx] = old_val - eps
                self.biases[i] = flat_b.reshape(shape_b)
                pred_minus = self.forward(batch_data)
                loss_minus = self._cross_entropy_loss(pred_minus, batch_labels)

                grad_b.flat[idx] = (loss_plus - loss_minus) / (2 * eps)
                flat_b[idx] = old_val

            self.biases[i] = flat_b.reshape(shape_b)
            self.biases[i] -= learning_rate * grad_b

            # 恢复未修改层的权重
            for j in range(len(self.weights)):
                if j != i:
                    self.weights[j] = original_weights[j]
                    self.biases[j] = original_biases[j]

        return float(loss)

    def _validate(self, val_data: np.ndarray, val_labels: np.ndarray) -> float:
        """
        验证模型

        Args:
            val_data: 验证数据
            val_labels: 验证标签

        Returns:
            验证损失
        """
        predictions = self.forward(val_data)
        loss = self._cross_entropy_loss(predictions, val_labels)
        return float(loss)

    def get_model_info(self) -> Dict[str, Any]:
        """获取CFC模型信息"""
        info = super().get_model_info()
        info.update({
            "model_type": "CFC",
            "hidden_dim": self.hidden_dim,
            "num_layers": self.num_layers,
            "dropout_rate": self.dropout_rate,
            "target_latency_ms": 100,
        })
        return info

    def to_torch(self, device: str = "cpu"):
        """
        将NumPy模型转换为PyTorch模型以支持GPU训练

        Args:
            device: 目标设备 ('cpu' 或 'cuda')

        Returns:
            PyTorch CFCModel实例
        """
        if not self._initialized:
            self.build()

        try:
            import torch
            from app.ai.lnn.models.torch_cfc_model import CFCModel as TorchCFCModel
            from app.ai.lnn.models.torch_base_lnn import LNNConfig

            config = LNNConfig(
                input_size=self.input_dim,
                hidden_size=self.hidden_dim,
                output_size=self.output_dim,
                num_layers=self.num_layers,
                dropout=self.dropout_rate,
            )

            torch_model = TorchCFCModel(config)

            with torch.no_grad():
                torch_model.cfc_layer.backbone[0].weight.data = torch.tensor(
                    self.weights[0].T, dtype=torch.float32
                )
                torch_model.cfc_layer.backbone[0].bias.data = torch.tensor(
                    self.biases[0], dtype=torch.float32
                )

                if len(self.weights) > 1:
                    torch_model.cfc_layer.backbone[2].weight.data = torch.tensor(
                        self.weights[1].T, dtype=torch.float32
                    )
                    torch_model.cfc_layer.backbone[2].bias.data = torch.tensor(
                        self.biases[1], dtype=torch.float32
                    )

                if len(self.weights) >= 3:
                    torch_model.output_layer.weight.data = torch.tensor(
                        self.weights[-1].T, dtype=torch.float32
                    )
                    torch_model.output_layer.bias.data = torch.tensor(
                        self.biases[-1], dtype=torch.float32
                    )

            torch_model = torch_model.to(device)
            torch_model.model_name = self.model_name
            torch_model.input_dim = self.input_dim
            torch_model.output_dim = self.output_dim
            torch_model.is_trained = self.is_trained

            return torch_model

        except ImportError:
            raise RuntimeError("CFC 模型转换失败：转换为 PyTorch 张量需要安装 PyTorch 库。当前环境中未检测到 PyTorch。请安装 PyTorch（pip install torch）后重试。")
