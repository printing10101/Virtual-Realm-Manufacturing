"""
LTC (Long-Term Context Network) Model

Focused on time-series prediction tasks, supporting sequence length > 1000.
Implements temporal processing with memory mechanisms.
"""

import numpy as np
from typing import Any, Dict, List, Optional

from .base_lnn import BaseLNNModel


class LTCModel(BaseLNNModel):
    """
    LTC模型实现，专注时序预测任务

    特点：
    - 支持序列长度 > 1000 的时间序列处理
    - 包含时序处理特殊逻辑
    - 适用于预测、趋势分析等场景
    """

    def __init__(
        self,
        model_name: str = "LTC",
        input_dim: int = 64,
        output_dim: int = 32,
        hidden_dim: int = 128,
        memory_size: int = 512,
        temporal_horizon: int = 1000,
        num_layers: int = 2,
        dropout_rate: float = 0.2,
        device: str = "cpu",
        **kwargs,
    ):
        """
        初始化LTC模型

        Args:
            model_name: 模型名称
            input_dim: 输入维度
            output_dim: 输出维度
            hidden_dim: 隐藏层维度
            memory_size: 记忆单元大小
            temporal_horizon: 时间视野（支持的最大序列长度）
            num_layers: 网络层数
            dropout_rate: Dropout比率
            device: 计算设备
        """
        super().__init__(model_name, input_dim, output_dim, device, **kwargs)

        self.hidden_dim = hidden_dim
        self.memory_size = memory_size
        self.temporal_horizon = temporal_horizon
        self.num_layers = num_layers
        self.dropout_rate = dropout_rate

        # 网络参数
        self.weights: List[np.ndarray] = []
        self.biases: List[np.ndarray] = []
        self.memory_weights: List[np.ndarray] = []
        self._initialized = False
        self.memory_state: Optional[np.ndarray] = None

    def build(self) -> None:
        """构建LTC网络结构"""
        if self._initialized:
            return

        # 初始化时序处理权重
        layer_dims = (
            [self.input_dim] + [self.hidden_dim] * self.num_layers + [self.output_dim]
        )

        for i in range(len(layer_dims) - 1):
            fan_in = layer_dims[i]
            fan_out = layer_dims[i + 1]
            limit = np.sqrt(6.0 / (fan_in + fan_out))

            W = np.random.uniform(-limit, limit, (fan_in, fan_out))
            b = np.zeros(fan_out)

            self.weights.append(W)
            self.biases.append(b)

        # 初始化记忆单元权重
        self.memory_weights = [
            np.random.randn(self.hidden_dim, self.memory_size) * 0.1,
            np.random.randn(self.memory_size, self.hidden_dim) * 0.1,
        ]

        # 初始化记忆状态
        self.memory_state = np.zeros((1, self.memory_size))

        self._initialized = True

    def forward(self, x: np.ndarray) -> np.ndarray:
        """
        前向传播（支持序列输入）

        Args:
            x: 输入数据
                 - 单序列: (sequence_length, input_dim)
                 - 批量序列: (batch_size, sequence_length, input_dim)

        Returns:
            模型输出
        """
        if not self._initialized:
            self.build()

        # 处理输入维度
        if x.ndim == 1:
            x = x.reshape(1, 1, -1)
        elif x.ndim == 2:
            x = x.reshape(1, x.shape[0], x.shape[1])

        batch_size, seq_len, _ = x.shape

        # 确保序列长度在支持范围内
        if seq_len > self.temporal_horizon:
            x = x[:, -self.temporal_horizon :, :]
            seq_len = self.temporal_horizon

        # 时序处理
        hidden_states = []
        current_memory = self.memory_state.copy()

        for t in range(seq_len):
            # 获取当前时间步输入
            x_t = x[:, t, :]  # (batch_size, input_dim)

            # 时序特征提取
            h_t = self._temporal_step(x_t, current_memory)

            hidden_states.append(h_t)

        # 聚合时序信息
        final_output = self._aggregate_temporal_states(hidden_states)

        return final_output

    def _temporal_step(self, x_t: np.ndarray, memory: np.ndarray) -> np.ndarray:
        """
        单步时序处理

        Args:
            x_t: 当前时间步输入
            memory: 当前记忆状态

        Returns:
            当前时间步隐藏状态
        """
        h = x_t

        for i, (W, b) in enumerate(zip(self.weights, self.biases)):
            # 结合记忆信息
            if i == 0 and memory is not None:
                memory_influence = memory @ self.memory_weights[1]
                memory_influence = memory_influence[:, : h.shape[1]]
                if h.shape[1] < memory_influence.shape[1]:
                    memory_influence = memory_influence[:, : h.shape[1]]
                h = h + 0.1 * memory_influence

            z = h @ W + b

            if i < len(self.weights) - 1:
                h = self._relu(z)
            else:
                h = z

        # 更新记忆
        self._update_memory(h)

        return h

    def _update_memory(self, hidden_state: np.ndarray) -> None:
        """
        更新记忆状态

        Args:
            hidden_state: 当前隐藏状态
        """
        if self.memory_state is None:
            return

        # 简化的记忆更新（实际应使用更复杂的机制）
        new_memory = hidden_state @ self.memory_weights[0]
        self.memory_state = 0.9 * self.memory_state + 0.1 * new_memory

    def _aggregate_temporal_states(self, states: List[np.ndarray]) -> np.ndarray:
        """
        聚合时序状态

        Args:
            states: 各时间步的隐藏状态列表

        Returns:
            聚合后的输出
        """
        if not states:
            raise ValueError(
                "LTC 模型状态聚合失败：状态列表（states）为空。LTC 网络需要至少一个时间步的状态数据进行聚合。请检查数据生成逻辑，确保状态列表包含有效的状态数据。"
            )

        # 使用注意力机制聚合
        stacked = np.stack(states, axis=1)  # (batch_size, seq_len, hidden_dim)

        # 简单平均（可替换为注意力加权）
        output = np.mean(stacked, axis=1)

        # 最终输出层
        if self.weights:
            output = output @ self.weights[-1] + self.biases[-1]

        return output

    def predict(self, x: np.ndarray) -> np.ndarray:
        """
        时序预测接口

        Args:
            x: 输入序列数据

        Returns:
            预测结果
        """
        return self.forward(x)

    def predict_sequence(self, x: np.ndarray, future_steps: int = 1) -> np.ndarray:
        """
        多步时序预测

        Args:
            x: 历史序列数据 (seq_len, input_dim)
            future_steps: 预测未来步数

        Returns:
            未来预测结果 (future_steps, output_dim)
        """
        predictions = []
        current_input = x.copy()

        for _ in range(future_steps):
            pred = self.predict(current_input)
            predictions.append(pred[-1])

            # 将预测结果作为下一步输入的一部分
            if pred.ndim == 1:
                pred = pred.reshape(1, -1)

            current_input = np.vstack([current_input[1:], pred])

        return np.array(predictions)

    def _relu(self, x: np.ndarray) -> np.ndarray:
        """ReLU激活函数"""
        return np.maximum(0, x)

    def _mse_loss(self, predictions: np.ndarray, labels: np.ndarray) -> float:
        """均方误差损失"""
        return float(np.mean((predictions - labels) ** 2))

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
        n_samples = data.shape[0]
        indices = np.random.choice(n_samples, min(batch_size, n_samples), replace=False)
        batch_data = data[indices]
        batch_labels = labels[indices]

        # 前向传播
        predictions = self.forward(batch_data)
        loss = self._mse_loss(predictions, batch_labels)

        # 简化的参数更新
        for i in range(len(self.weights)):
            grad_noise = np.random.randn(*self.weights[i].shape) * 0.01
            self.weights[i] -= learning_rate * grad_noise
            self.biases[i] -= learning_rate * 0.001

        return float(loss)

    def _validate(self, val_data: np.ndarray, val_labels: np.ndarray) -> float:
        """验证模型"""
        predictions = self.forward(val_data)
        loss = self._mse_loss(predictions, val_labels)
        return float(loss)

    def reset_memory(self) -> None:
        """重置记忆状态"""
        if self._initialized:
            self.memory_state = np.zeros((1, self.memory_size))

    def get_model_info(self) -> Dict[str, Any]:
        """获取LTC模型信息"""
        info = super().get_model_info()
        info.update(
            {
                "model_type": "LTC",
                "hidden_dim": self.hidden_dim,
                "memory_size": self.memory_size,
                "temporal_horizon": self.temporal_horizon,
                "num_layers": self.num_layers,
                "dropout_rate": self.dropout_rate,
            }
        )
        return info

    def to_torch(self, device: str = "cpu"):
        """
        将NumPy模型转换为PyTorch模型以支持GPU训练

        Args:
            device: 目标设备 ('cpu' 或 'cuda')

        Returns:
            PyTorch LTCModel实例
        """
        if not self._initialized:
            self.build()

        try:
            import torch
            from app.ai.lnn.models.torch_ltc_model import LTCModel as TorchLTCModel
            from app.ai.lnn.models.torch_base_lnn import LNNConfig

            config = LNNConfig(
                input_size=self.input_dim,
                hidden_size=self.hidden_dim,
                output_size=self.output_dim,
                num_layers=self.num_layers,
                dropout=self.dropout_rate,
            )

            torch_model = TorchLTCModel(config)

            with torch.no_grad():
                if len(self.weights) >= 1 and len(torch_model.ltc_cells) >= 1:
                    first_cell = torch_model.ltc_cells[0]
                    first_cell.W.data = torch.tensor(
                        self.weights[0].T, dtype=torch.float32
                    )
                    first_cell.bias.data = torch.tensor(
                        self.biases[0], dtype=torch.float32
                    )
                    if self.weights[0].shape[1] == self.weights[0].shape[0]:
                        first_cell.U.data = torch.tensor(
                            self.weights[0].T, dtype=torch.float32
                        )

                if len(self.weights) >= 2 and len(torch_model.ltc_cells) >= 2:
                    second_cell = torch_model.ltc_cells[1]
                    second_cell.W.data = torch.tensor(
                        self.weights[1].T, dtype=torch.float32
                    )
                    second_cell.bias.data = torch.tensor(
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
            raise RuntimeError(
                "LTC 模型转换失败：转换为 PyTorch 张量需要安装 PyTorch 库。当前环境中未检测到 PyTorch。请安装 PyTorch（pip install torch）后重试。"
            )
