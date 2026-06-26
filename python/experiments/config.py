"""
CT-LTC 实验配置文件
定义所有实验参数、数据集配置、模型超参数等
"""

from dataclasses import dataclass, field
from typing import Dict, List, Tuple
import os


@dataclass
class DatasetConfig:
    """数据集配置"""
    name: str
    sample_size: int
    num_conditions: int
    material: str
    source: str
    train_ratio: float = 0.7
    val_ratio: float = 0.15
    test_ratio: float = 0.15
    
    @property
    def path(self) -> str:
        """数据集路径"""
        return f"data/{self.name.lower()}"


@dataclass
class ModelConfig:
    """模型配置"""
    # LTC 参数
    ltc_hidden_dim: int = 64
    ltc_num_layers: int = 3
    ltc_dt: float = 0.1
    ltc_tau_init: float = 0.1
    
    # 网络参数
    input_dim: int = 2  # 简化版本：主轴转速 + 轴向切深
    hidden_dim: int = 128
    output_dim: int = 1
    num_layers: int = 3
    dropout: float = 0.2
    
    # 训练参数
    batch_size: int = 32
    learning_rate: float = 1e-3  # 提高学习率加快收敛
    weight_decay: float = 1e-4
    num_epochs_stage1: int = 150  # 增加阶段一epoch
    num_epochs_stage2: int = 100  # 减少阶段二epoch避免过拟合
    
    # 物理损失权重 - 降低物理约束强度
    lambda_data: float = 1.0
    lambda_phys: float = 0.1  # 从0.5降到0.1
    lambda_pcc: float = 0.01  # 从0.1降到0.01
    epsilon_phys: float = 0.1  # 从0.05增加到0.1，更宽松的约束
    
    # 设备
    device: str = "cuda"


@dataclass
class ExperimentConfig:
    """实验配置"""
    # 实验名称
    experiment_name: str = "ct_ltc_chatter_prediction"
    
    # 数据集列表
    datasets: List[DatasetConfig] = field(default_factory=lambda: [
        DatasetConfig("PHM2010", 315, 6, "碳钢", "IEEE PHM 2010"),
        DatasetConfig("NUAA", 180, 12, "铝合金", "南京航空航天大学"),
        DatasetConfig("NIST", 240, 18, "多材料", "NIST"),
        DatasetConfig("ACADEMIC", 150, 5, "钛合金", "学术合作"),
        DatasetConfig("INDUSTRIAL_6061T6", 500, 30, "铝合金6061-T6", "自采工业数据"),
    ])
    
    # 模型配置
    model: ModelConfig = field(default_factory=ModelConfig)
    
    # 基线方法
    baselines: List[str] = field(default_factory=lambda: [
        "SVR", "RandomForest", "XGBoost", "BPNN",
        "LSTM", "Transformer", "PINN", "GaussianProcess"
    ])
    
    # 评价指标
    metrics: List[str] = field(default_factory=lambda: [
        "MAE", "RMSE", "R2", "PCC", "InferenceTime"
    ])
    
    # 输出目录
    output_dir: str = "experiments/results"
    checkpoint_dir: str = "experiments/checkpoints"
    log_dir: str = "experiments/logs"
    
    def __post_init__(self):
        """创建必要的目录"""
        os.makedirs(self.output_dir, exist_ok=True)
        os.makedirs(self.checkpoint_dir, exist_ok=True)
        os.makedirs(self.log_dir, exist_ok=True)


# 默认配置
DEFAULT_CONFIG = ExperimentConfig()


def get_config(experiment_name: str = None) -> ExperimentConfig:
    """获取实验配置"""
    if experiment_name:
        config = ExperimentConfig(experiment_name=experiment_name)
    else:
        config = DEFAULT_CONFIG
    return config
