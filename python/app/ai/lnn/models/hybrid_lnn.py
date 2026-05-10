"""
Hybrid LNN (CNN + LNN) Model

Fuses convolutional neural network with logical neural network advantages.
Handles mixed input of images and structured data.
"""
import numpy as np
from typing import Any, Dict, List, Optional

from .base_lnn import BaseLNNModel


class HybridLNNModel(BaseLNNModel):
    """
    混合模型实现，集成CNN与LNN组件

    特点：
    - 融合卷积神经网络与神经逻辑网络优势
    - 处理图像与结构化数据混合输入
    - 支持多模态输入
    """

    def __init__(
        self,
        model_name: str = "HybridLNN",
        input_dim: int = 256,
        output_dim: int = 10,
        cnn_filters: Optional[List[int]] = None,
        cnn_kernel_sizes: Optional[List[int]] = None,
        lnn_hidden_dim: int = 128,
        lnn_num_layers: int = 2,
        dropout_rate: float = 0.2,
        fusion_method: str = "concat",
        device: str = "cpu",
        **kwargs
    ):
        """
        初始化Hybrid LNN模型

        Args:
            model_name: 模型名称
            input_dim: 输入维度（结构化数据部分）
            output_dim: 输出维度
            cnn_filters: CNN滤波器数量列表
            cnn_kernel_sizes: CNN卷积核大小列表
            lnn_hidden_dim: LNN隐藏层维度
            lnn_num_layers: LNN网络层数
            dropout_rate: Dropout比率
            fusion_method: 融合方法 ('concat', 'add', 'attention')
            device: 计算设备
        """
        super().__init__(model_name, input_dim, output_dim, device, **kwargs)

        self.cnn_filters = cnn_filters or [32, 64, 128]
        self.cnn_kernel_sizes = cnn_kernel_sizes or [3, 3, 3]
        self.lnn_hidden_dim = lnn_hidden_dim
        self.lnn_num_layers = lnn_num_layers
        self.dropout_rate = dropout_rate
        self.fusion_method = fusion_method

        # CNN参数
        self.cnn_weights: List[np.ndarray] = []
        self.cnn_biases: List[np.ndarray] = []

        # LNN参数
        self.lnn_weights: List[np.ndarray] = []
        self.lnn_biases: List[np.ndarray] = []

        # 融合层参数
        self.fusion_weights: Optional[np.ndarray] = None
        self.fusion_bias: Optional[np.ndarray] = None

        self._initialized = False

    def build(self) -> None:
        """构建Hybrid网络结构"""
        if self._initialized:
            return

        # 构建CNN层
        input_channels = 1  # 假设单通道输入
        for i, (filters, kernel_size) in enumerate(zip(self.cnn_filters, self.cnn_kernel_sizes)):
            # 卷积核权重 (kernel_size, input_channels, filters)
            W = np.random.randn(kernel_size, input_channels, filters) * 0.1
            b = np.zeros(filters)

            self.cnn_weights.append(W)
            self.cnn_biases.append(b)
            input_channels = filters

        # 构建LNN层
        lnn_input_dim = self.input_dim + self.cnn_filters[-1]  # 融合后的维度
        layer_dims = [lnn_input_dim] + [self.lnn_hidden_dim] * self.lnn_num_layers + [self.output_dim]

        for i in range(len(layer_dims) - 1):
            fan_in = layer_dims[i]
            fan_out = layer_dims[i + 1]
            limit = np.sqrt(6.0 / (fan_in + fan_out))

            W = np.random.uniform(-limit, limit, (fan_in, fan_out))
            b = np.zeros(fan_out)

            self.lnn_weights.append(W)
            self.lnn_biases.append(b)

        self._initialized = True

    def forward(self, x: np.ndarray) -> np.ndarray:
        """
        前向传播

        Args:
            x: 输入数据
                 - 结构化数据: (batch_size, input_dim)
                 - 图像数据: (batch_size, height, width, channels)
                 - 混合输入: (batch_size, input_dim + image_features)

        Returns:
            模型输出
        """
        if not self._initialized:
            self.build()

        if x.ndim == 1:
            x = x.reshape(1, -1)

        # 检查输入是否包含图像特征
        if x.shape[1] > self.input_dim:
            # 混合输入
            structured_data = x[:, :self.input_dim]
            image_features = x[:, self.input_dim:]
        else:
            # 仅结构化数据
            structured_data = x
            image_features = np.zeros((x.shape[0], self.cnn_filters[-1]))

        # CNN处理图像特征
        cnn_output = self._cnn_forward(image_features)

        # 融合特征
        fused_features = self._fuse_features(structured_data, cnn_output)

        # LNN处理
        output = self._lnn_forward(fused_features)

        return output

    def _cnn_forward(self, x: np.ndarray) -> np.ndarray:
        """
        CNN前向传播

        Args:
            x: 图像特征输入

        Returns:
            CNN提取的特征
        """
        if x.ndim == 1:
            x = x.reshape(1, -1)

        # 简化的CNN处理（实际应用应使用真正的卷积操作）
        for W, b in zip(self.cnn_weights, self.cnn_biases):
            # 模拟卷积操作
            if x.shape[1] >= W.shape[0]:
                # 使用一维卷积近似
                kernel_size = W.shape[0]
                out_channels = W.shape[-1]

                # 简化的特征提取
                features = np.zeros((x.shape[0], out_channels))
                for i in range(min(x.shape[1], kernel_size)):
                    features += x[:, i:i+1] @ W[i] if i < x.shape[1] else 0

                x = self._relu(features + b)
            else:
                # 维度不匹配时直接传递
                break

        return x

    def _fuse_features(self, structured: np.ndarray, image: np.ndarray) -> np.ndarray:
        """
        融合结构化数据和图像特征

        Args:
            structured: 结构化数据
            image: 图像特征

        Returns:
            融合后的特征
        """
        if self.fusion_method == "concat":
            return np.concatenate([structured, image], axis=1)
        elif self.fusion_method == "add":
            # 确保维度一致
            if structured.shape[1] != image.shape[1]:
                # 填充或截断
                max_dim = max(structured.shape[1], image.shape[1])
                structured = self._pad_features(structured, max_dim)
                image = self._pad_features(image, max_dim)
            return structured + image
        elif self.fusion_method == "attention":
            return self._attention_fusion(structured, image)
        else:
            return np.concatenate([structured, image], axis=1)

    def _pad_features(self, x: np.ndarray, target_dim: int) -> np.ndarray:
        """填充特征到目标维度"""
        if x.shape[1] >= target_dim:
            return x[:, :target_dim]
        padding = np.zeros((x.shape[0], target_dim - x.shape[1]))
        return np.concatenate([x, padding], axis=1)

    def _attention_fusion(self, structured: np.ndarray, image: np.ndarray) -> np.ndarray:
        """
        注意力融合

        Args:
            structured: 结构化数据
            image: 图像特征

        Returns:
            注意力加权融合结果
        """
        # 计算注意力权重
        structured_score = np.mean(structured, axis=1, keepdims=True)
        image_score = np.mean(image, axis=1, keepdims=True)

        scores = np.concatenate([structured_score, image_score], axis=1)
        attention_weights = self._softmax(scores)

        # 加权融合
        fused = structured * attention_weights[:, :1] + image * attention_weights[:, 1:]
        return fused

    def _lnn_forward(self, x: np.ndarray) -> np.ndarray:
        """
        LNN前向传播

        Args:
            x: 输入特征

        Returns:
            模型输出
        """
        activations = x
        for i, (W, b) in enumerate(zip(self.lnn_weights, self.lnn_biases)):
            z = activations @ W + b

            if i < len(self.lnn_weights) - 1:
                activations = self._relu(z)
            else:
                activations = z

        return activations

    def predict(self, x: np.ndarray) -> np.ndarray:
        """预测接口"""
        return self.forward(x)

    def predict_multimodal(
        self,
        structured_data: np.ndarray,
        image_data: Optional[np.ndarray] = None
    ) -> np.ndarray:
        """
        多模态预测

        Args:
            structured_data: 结构化数据
            image_data: 图像数据（可选）

        Returns:
            预测结果
        """
        if image_data is not None:
            # 展平图像数据并拼接
            if image_data.ndim > 2:
                image_data = image_data.reshape(image_data.shape[0], -1)
            x = np.concatenate([structured_data, image_data], axis=1)
        else:
            x = structured_data

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
        predictions = predictions - np.max(predictions, axis=-1, keepdims=True)
        log_probs = predictions - np.log(np.sum(np.exp(predictions), axis=-1, keepdims=True))

        if labels.ndim == 1:
            labels = np.eye(predictions.shape[1])[labels.astype(int)]

        return -np.mean(np.sum(labels * log_probs, axis=-1))

    def _train_step(
        self,
        data: np.ndarray,
        labels: np.ndarray,
        batch_size: int,
        learning_rate: float
    ) -> float:
        """单步训练"""
        n_samples = data.shape[0]
        indices = np.random.choice(n_samples, min(batch_size, n_samples), replace=False)
        batch_data = data[indices]
        batch_labels = labels[indices]

        predictions = self.forward(batch_data)
        loss = self._cross_entropy_loss(predictions, batch_labels)

        # 简化的参数更新
        for i in range(len(self.lnn_weights)):
            grad_noise = np.random.randn(*self.lnn_weights[i].shape) * 0.01
            self.lnn_weights[i] -= learning_rate * grad_noise
            self.lnn_biases[i] -= learning_rate * 0.001

        return float(loss)

    def _validate(self, val_data: np.ndarray, val_labels: np.ndarray) -> float:
        """验证模型"""
        predictions = self.forward(val_data)
        loss = self._cross_entropy_loss(predictions, val_labels)
        return float(loss)

    def get_model_info(self) -> Dict[str, Any]:
        """获取Hybrid模型信息"""
        info = super().get_model_info()
        info.update({
            "model_type": "HybridLNN",
            "cnn_filters": self.cnn_filters,
            "cnn_kernel_sizes": self.cnn_kernel_sizes,
            "lnn_hidden_dim": self.lnn_hidden_dim,
            "lnn_num_layers": self.lnn_num_layers,
            "dropout_rate": self.dropout_rate,
            "fusion_method": self.fusion_method,
        })
        return info
