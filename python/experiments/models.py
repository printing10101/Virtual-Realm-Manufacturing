"""
CT-LTC 模型实现
包含连续时间液态时间常数网络及其变体
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
from typing import Tuple, Optional
import numpy as np


class LTCCell(nn.Module):
    """
    LTC单元
    实现液态时间常数机制
    """
    
    def __init__(self, input_size: int, hidden_size: int):
        super().__init__()
        self.input_size = input_size
        self.hidden_size = hidden_size
        
        # 可学习参数
        self.W = nn.Parameter(torch.randn(hidden_size, input_size))
        self.U = nn.Parameter(torch.randn(hidden_size, hidden_size))
        self.bias = nn.Parameter(torch.zeros(hidden_size))
        
        # 可学习时间常数 τ
        self.tau = nn.Parameter(torch.ones(hidden_size) * 0.1)
        
        # 初始化权重
        nn.init.xavier_uniform_(self.W)
        nn.init.xavier_uniform_(self.U)
    
    def forward(self, x: torch.Tensor, h: torch.Tensor, dt: float = 0.1) -> torch.Tensor:
        """
        前向传播
        
        Args:
            x: 输入 [batch_size, input_size]
            h: 隐藏状态 [batch_size, hidden_size]
            dt: 时间步长
        
        Returns:
            新的隐藏状态
        """
        # 确保 τ > 0
        tau = torch.clamp(self.tau, min=0.01)
        
        # 计算状态变化
        dh = torch.tanh(torch.mm(x, self.W.t()) + torch.mm(h, self.U.t()) + self.bias)
        
        # LTC更新规则: h_new = h + dt * (dh - h) / tau
        h_new = h + dt * (dh - h) / tau.unsqueeze(0)
        
        return h_new


class CTLTCModel(nn.Module):
    """
    CT-LTC 模型
    连续时间液态时间常数网络用于颤振预测
    """
    
    def __init__(
        self,
        input_dim: int = 2,
        hidden_dim: int = 64,
        num_layers: int = 3,
        output_dim: int = 1,
        dt: float = 0.1,
        dropout: float = 0.2
    ):
        """
        初始化CT-LTC模型
        
        Args:
            input_dim: 输入维度
            hidden_dim: 隐藏层维度
            num_layers: LTC层数
            output_dim: 输出维度
            dt: 时间步长
            dropout: dropout率
        """
        super().__init__()
        
        self.input_dim = input_dim
        self.hidden_dim = hidden_dim
        self.num_layers = num_layers
        self.output_dim = output_dim
        self.dt = dt
        
        # 输入投影层
        self.input_proj = nn.Linear(input_dim, hidden_dim)
        
        # LTC层
        self.ltc_cells = nn.ModuleList([
            LTCCell(hidden_dim, hidden_dim) for _ in range(num_layers)
        ])
        
        # 输出层
        self.output_proj = nn.Sequential(
            nn.Linear(hidden_dim, hidden_dim // 2),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_dim // 2, output_dim)
        )
        
        # 初始化隐藏状态
        self.hidden_states = None
    
    def init_hidden(self, batch_size: int, device: torch.device) -> None:
        """初始化隐藏状态"""
        self.hidden_states = [
            torch.zeros(batch_size, self.hidden_dim, device=device)
            for _ in range(self.num_layers)
        ]
    
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        前向传播
        
        Args:
            x: 输入 [batch_size, input_dim]
        
        Returns:
            输出 [batch_size, output_dim]
        """
        batch_size = x.size(0)
        device = x.device
        
        # 初始化隐藏状态（每个批次都重新初始化，避免计算图持久化）
        # 使用 zeros_like 风格但确保 requires_grad 正确传播
        hidden_states = []
        for _ in range(self.num_layers):
            h = torch.zeros(batch_size, self.hidden_dim, device=device)
            hidden_states.append(h)
        
        # 输入投影
        h = self.input_proj(x)
        
        # 通过 LTC 层
        for i, ltc_cell in enumerate(self.ltc_cells):
            hidden_states[i] = ltc_cell(h, hidden_states[i], self.dt)
            h = hidden_states[i]
        
        # 输出投影
        output = self.output_proj(h)
        
        return output
    
    def reset_hidden(self):
        """重置隐藏状态"""
        self.hidden_states = None


class CTCTCWithPhysics(nn.Module):
    """
    CT-LTC 带物理分支的完整模型
    包含数据驱动分支和解析物理分支
    """
    
    def __init__(
        self,
        input_dim: int = 2,
        hidden_dim: int = 64,
        num_layers: int = 3,
        output_dim: int = 1,
        dt: float = 0.1,
        dropout: float = 0.2
    ):
        super().__init__()
        
        # 数据驱动分支 (LTC)
        self.ltc_branch = CTLTCModel(
            input_dim=input_dim,
            hidden_dim=hidden_dim,
            num_layers=num_layers,
            output_dim=output_dim,
            dt=dt,
            dropout=dropout
        )
        
        # 门控融合层
        self.gate = nn.Sequential(
            nn.Linear(input_dim, 32),
            nn.ReLU(),
            nn.Linear(32, 1),
            nn.Sigmoid()
        )
        
        # 物理分支参数（可学习）
        self.physics_scale = nn.Parameter(torch.ones(1))
        self.physics_bias = nn.Parameter(torch.zeros(1))
    
    def forward(
        self,
        x: torch.Tensor,
        physics_pred: Optional[torch.Tensor] = None
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        前向传播
        
        Args:
            x: 输入特征 [batch_size, input_dim]
            physics_pred: 物理模型预测 [batch_size, output_dim]
        
        Returns:
            final_pred: 最终预测
            ltc_pred: LTC分支预测
        """
        # LTC分支预测
        ltc_pred = self.ltc_branch(x)
        
        # 如果没有物理预测，只使用LTC分支
        if physics_pred is None:
            return ltc_pred, ltc_pred
        
        # 门控融合
        alpha = self.gate(x)
        final_pred = alpha * ltc_pred + (1 - alpha) * (
            self.physics_scale * physics_pred + self.physics_bias
        )
        
        return final_pred, ltc_pred
    
    def reset_hidden(self):
        """重置隐藏状态"""
        self.ltc_branch.reset_hidden()


class BaselineLSTM(nn.Module):
    """基线LSTM模型"""
    
    def __init__(self, input_dim: int = 2, hidden_dim: int = 64, num_layers: int = 2, output_dim: int = 1):
        super().__init__()
        
        self.lstm = nn.LSTM(
            input_size=input_dim,
            hidden_size=hidden_dim,
            num_layers=num_layers,
            batch_first=True,
            dropout=0.2
        )
        
        self.fc = nn.Sequential(
            nn.Linear(hidden_dim, hidden_dim // 2),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(hidden_dim // 2, output_dim)
        )
    
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # LSTM需要序列输入，这里将单个样本视为长度为1的序列
        if x.dim() == 2:
            x = x.unsqueeze(1)
        
        lstm_out, _ = self.lstm(x)
        output = self.fc(lstm_out[:, -1, :])
        return output


class BaselineTransformer(nn.Module):
    """基线Transformer模型"""
    
    def __init__(self, input_dim: int = 2, d_model: int = 64, nhead: int = 4, num_layers: int = 2, output_dim: int = 1):
        super().__init__()
        
        self.input_proj = nn.Linear(input_dim, d_model)
        
        encoder_layer = nn.TransformerEncoderLayer(
            d_model=d_model,
            nhead=nhead,
            dim_feedforward=d_model * 2,
            dropout=0.2,
            batch_first=True
        )
        
        self.transformer = nn.TransformerEncoder(encoder_layer, num_layers=num_layers)
        
        self.output_proj = nn.Sequential(
            nn.Linear(d_model, d_model // 2),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(d_model // 2, output_dim)
        )
    
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        if x.dim() == 2:
            x = x.unsqueeze(1)
        
        x = self.input_proj(x)
        x = self.transformer(x)
        output = self.output_proj(x[:, -1, :])
        return output


class BaselinePINN(nn.Module):
    """基线PINN模型"""
    
    def __init__(self, input_dim: int = 2, hidden_dim: int = 64, num_layers: int = 4, output_dim: int = 1):
        super().__init__()
        
        layers = []
        in_dim = input_dim
        
        for _ in range(num_layers):
            layers.append(nn.Linear(in_dim, hidden_dim))
            layers.append(nn.Tanh())
            in_dim = hidden_dim
        
        layers.append(nn.Linear(in_dim, output_dim))
        
        self.network = nn.Sequential(*layers)
    
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.network(x)


class BaselineBPNN(nn.Module):
    """基线BPNN模型"""
    
    def __init__(self, input_dim: int = 2, hidden_dim: int = 64, num_layers: int = 3, output_dim: int = 1):
        super().__init__()
        
        layers = []
        in_dim = input_dim
        
        for _ in range(num_layers):
            layers.append(nn.Linear(in_dim, hidden_dim))
            layers.append(nn.ReLU())
            layers.append(nn.Dropout(0.2))
            in_dim = hidden_dim
        
        layers.append(nn.Linear(in_dim, output_dim))
        
        self.network = nn.Sequential(*layers)
    
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.network(x)


class BaselineCNN(nn.Module):
    """基线CNN模型"""
    
    def __init__(self, input_dim: int = 2, hidden_dim: int = 64, output_dim: int = 1):
        super().__init__()
        
        # 1D卷积层 - 移除MaxPool1d以适配短序列
        self.conv_layers = nn.Sequential(
            nn.Conv1d(input_dim, hidden_dim, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.Conv1d(hidden_dim, hidden_dim * 2, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.AdaptiveAvgPool1d(1)
        )
        
        # 全连接层
        self.fc_layers = nn.Sequential(
            nn.Linear(hidden_dim * 2, hidden_dim),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(hidden_dim, output_dim)
        )
    
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # CNN需要序列输入 [batch, channels, length]
        if x.dim() == 2:
            x = x.unsqueeze(2)  # [batch, features, 1]
        
        conv_out = self.conv_layers(x)
        conv_out = conv_out.squeeze(2)  # [batch, features]
        output = self.fc_layers(conv_out)
        return output


class BaselineGRU(nn.Module):
    """基线GRU模型"""
    
    def __init__(self, input_dim: int = 2, hidden_dim: int = 64, num_layers: int = 2, output_dim: int = 1):
        super().__init__()
        
        self.gru = nn.GRU(
            input_size=input_dim,
            hidden_size=hidden_dim,
            num_layers=num_layers,
            batch_first=True,
            dropout=0.2
        )
        
        self.fc = nn.Sequential(
            nn.Linear(hidden_dim, hidden_dim // 2),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(hidden_dim // 2, output_dim)
        )
    
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # GRU需要序列输入
        if x.dim() == 2:
            x = x.unsqueeze(1)
        
        gru_out, _ = self.gru(x)
        output = self.fc(gru_out[:, -1, :])
        return output


class BaselinegPINN(nn.Module):
    """基线gPINN模型（梯度增强PINN）"""
    
    def __init__(self, input_dim: int = 2, hidden_dim: int = 64, num_layers: int = 4, output_dim: int = 1):
        super().__init__()
        
        layers = []
        in_dim = input_dim
        
        for _ in range(num_layers):
            layers.append(nn.Linear(in_dim, hidden_dim))
            layers.append(nn.Tanh())
            in_dim = hidden_dim
        
        layers.append(nn.Linear(in_dim, output_dim))
        
        self.network = nn.Sequential(*layers)
    
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.network(x)
    
    def gradient_loss(self, x: torch.Tensor, y_pred: torch.Tensor) -> torch.Tensor:
        """计算梯度损失（gPINN特有）"""
        # 计算一阶导数
        grad_outputs = torch.ones_like(y_pred)
        gradients = torch.autograd.grad(
            outputs=y_pred,
            inputs=x,
            grad_outputs=grad_outputs,
            create_graph=True
        )[0]
        
        # 梯度正则化损失
        grad_loss = torch.mean(gradients ** 2)
        return grad_loss


class BaselinePeRCNN(nn.Module):
    """基线PeRCNN模型（物理编码循环卷积网络）"""
    
    def __init__(self, input_dim: int = 2, hidden_dim: int = 64, output_dim: int = 1):
        super().__init__()
        
        # 物理编码层
        self.physics_encoder = nn.Sequential(
            nn.Linear(input_dim, hidden_dim),
            nn.Tanh(),
            nn.Linear(hidden_dim, hidden_dim)
        )
        
        # 循环卷积层
        self.conv_rnn = nn.Sequential(
            nn.Conv1d(hidden_dim, hidden_dim * 2, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.Conv1d(hidden_dim * 2, hidden_dim * 2, kernel_size=3, padding=1),
            nn.ReLU()
        )
        
        # 输出层
        self.output_layer = nn.Sequential(
            nn.AdaptiveAvgPool1d(1),
            nn.Flatten(),
            nn.Linear(hidden_dim * 2, hidden_dim),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(hidden_dim, output_dim)
        )
    
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # 物理编码
        physics_features = self.physics_encoder(x)
        
        # 转换为序列格式 [batch, channels, length]
        if physics_features.dim() == 2:
            physics_features = physics_features.unsqueeze(2)
        
        # 循环卷积
        conv_out = self.conv_rnn(physics_features)
        
        # 输出
        output = self.output_layer(conv_out)
        return output


def create_model(model_name: str, config) -> nn.Module:
    """
    创建模型
    
    Args:
        model_name: 模型名称
        config: 配置
    
    Returns:
        模型实例
    """
    input_dim = config.model.input_dim
    hidden_dim = config.model.hidden_dim
    num_layers = config.model.num_layers
    output_dim = config.model.output_dim
    
    if model_name == "CT-LTC":
        return CTCTCWithPhysics(
            input_dim=input_dim,
            hidden_dim=hidden_dim,
            num_layers=num_layers,
            output_dim=output_dim,
            dt=config.model.ltc_dt,
            dropout=config.model.dropout
        )
    elif model_name == "LTC":
        return CTLTCModel(
            input_dim=input_dim,
            hidden_dim=hidden_dim,
            num_layers=num_layers,
            output_dim=output_dim,
            dt=config.model.ltc_dt,
            dropout=config.model.dropout
        )
    elif model_name == "LSTM":
        return BaselineLSTM(
            input_dim=input_dim,
            hidden_dim=hidden_dim,
            num_layers=num_layers,
            output_dim=output_dim
        )
    elif model_name == "Transformer":
        return BaselineTransformer(
            input_dim=input_dim,
            d_model=hidden_dim,
            num_layers=num_layers,
            output_dim=output_dim
        )
    elif model_name == "PINN":
        return BaselinePINN(
            input_dim=input_dim,
            hidden_dim=hidden_dim,
            num_layers=num_layers,
            output_dim=output_dim
        )
    elif model_name == "BPNN":
        return BaselineBPNN(
            input_dim=input_dim,
            hidden_dim=hidden_dim,
            num_layers=num_layers,
            output_dim=output_dim
        )
    else:
        raise ValueError(f"未知模型: {model_name}")


if __name__ == "__main__":
    # 测试模型
    print("测试CT-LTC模型...")
    
    config = type('Config', (), {
        'model': type('ModelConfig', (), {
            'input_dim': 2,
            'hidden_dim': 64,
            'num_layers': 3,
            'output_dim': 1,
            'ltc_dt': 0.1,
            'dropout': 0.2
        })()
    })()
    
    model = create_model("CT-LTC", config)
    
    # 测试前向传播
    x = torch.randn(32, 2)
    output, ltc_output = model(x)
    
    print(f"输入形状: {x.shape}")
    print(f"输出形状: {output.shape}")
    print(f"LTC输出形状: {ltc_output.shape}")
    
    print("\n模型测试通过！")
