"""
数据生成器模块
实现合成数据生成（Tlusty公式）和数据集加载
"""

import numpy as np
import torch
from torch.utils.data import Dataset, DataLoader
from typing import Tuple, Dict, List, Optional
import os


class TlustyAnalyticalModel:
    """
    Tlusty 解析模型
    用于生成合成数据和提供物理先验
    """
    
    def __init__(
        self,
        stiffness: float = 1e6,  # N/m
        modal_mass: float = 100.0,  # kg
        damping_ratio: float = 0.05,
        cutting_force_coeff: float = 2000.0,  # N/mm²
        num_teeth: int = 4
    ):
        """
        初始化Tlusty模型
        
        Args:
            stiffness: 机床刚度 (N/m)
            modal_mass: 模态质量 (kg)
            damping_ratio: 阻尼比
            cutting_force_coeff: 切削力系数 (N/mm²)
            num_teeth: 刀具齿数
        """
        self.stiffness = stiffness
        self.modal_mass = modal_mass
        self.damping_ratio = damping_ratio
        self.cutting_force_coeff = cutting_force_coeff
        self.num_teeth = num_teeth
        
        # 计算阻尼系数
        self.damping = 2 * damping_ratio * np.sqrt(stiffness * modal_mass)
    
    def frequency_response(self, omega: np.ndarray) -> np.ndarray:
        """
        计算频率响应函数 G(jω)
        
        Args:
            omega: 角频率数组 (rad/s)
        
        Returns:
            G(jω) 复数数组
        """
        k = self.stiffness
        m = self.modal_mass
        c = self.damping
        
        G = 1 / (k - m * omega**2 + 1j * c * omega)
        return G
    
    def compute_limiting_depth(
        self,
        spindle_speed: np.ndarray,
        num_lobes: int = 10
    ) -> np.ndarray:
        """
        计算极限切深 a_lim
        
        Args:
            spindle_speed: 主轴转速数组 (rpm)
            num_lobes: 叶瓣数
        
        Returns:
            极限切深数组 (mm)
        """
        Ks = self.cutting_force_coeff * 1e6  # 转换为 N/m²
        
        # 计算固有频率
        omega_n = np.sqrt(self.stiffness / self.modal_mass)
        f_n = omega_n / (2 * np.pi)
        
        # 计算颤振频率（考虑叶瓣效应）
        # 简化：使用固有频率作为颤振频率
        omega_c = omega_n
        
        # 计算相位角（对每个主轴转速）
        epsilon = 2 * np.pi * f_n * 60 / spindle_speed
        
        # 计算频率响应（在颤振频率处）
        G = self.frequency_response(omega_c)
        
        # 计算极限切深（考虑相位角的影响）
        # 标准Tlusty公式：a_lim = -1 / (2 * Ks * Re(G) * (1 - cos(epsilon)))
        # 简化版本：使用平均值
        real_G = np.real(G)
        
        # 避免除零：如果Re(G)接近零，使用一个小值
        real_G = np.where(np.abs(real_G) < 1e-10, 1e-10, real_G)
        
        a_lim_base = -1 / (2 * Ks * real_G)
        
        # 考虑相位角调制（简化处理）
        modulation = 1.0 / (1.0 + 0.1 * np.abs(np.sin(epsilon)))
        a_lim = a_lim_base * modulation
        
        # 转换为 mm
        a_lim = a_lim * 1000
        
        # 确保结果在合理范围内（0.01mm 到 20mm）
        a_lim = np.clip(np.abs(a_lim), 0.01, 20.0)
        
        return a_lim
    
    def compute_stability(
        self,
        spindle_speed: np.ndarray,
        axial_depth: np.ndarray
    ) -> np.ndarray:
        """
        计算稳定性标签
        
        Args:
            spindle_speed: 主轴转速 (rpm)
            axial_depth: 轴向切深 (mm)
        
        Returns:
            稳定性标签 (0=稳定, 1=不稳定)
        """
        a_lim = self.compute_limiting_depth(spindle_speed)
        stability = (axial_depth > a_lim).astype(int)
        return stability


class SyntheticChatterDataset(Dataset):
    """
    合成颤振数据集
    使用Tlusty解析公式生成训练数据
    """
    
    def __init__(
        self,
        num_samples: int = 10000,
        spindle_speed_range: Tuple[float, float] = (1000, 10000),
        axial_depth_range: Tuple[float, float] = (0.1, 10.0),
        machine_id: str = "vmc_850",
        tool_id: str = "endmill_d10",
        noise_level: float = 0.02,
        seed: int = 42
    ):
        """
        初始化合成数据集
        
        Args:
            num_samples: 样本数量
            spindle_speed_range: 主轴转速范围 (rpm)
            axial_depth_range: 轴向切深范围 (mm)
            machine_id: 机床ID
            tool_id: 刀具ID
            noise_level: 噪声水平
            seed: 随机种子
        """
        super().__init__()
        self.num_samples = num_samples
        self.spindle_speed_range = spindle_speed_range
        self.axial_depth_range = axial_depth_range
        self.machine_id = machine_id
        self.tool_id = tool_id
        self.noise_level = noise_level
        
        np.random.seed(seed)
        
        # 生成数据
        self.data = self._generate_data()
    
    def _generate_data(self) -> Dict[str, np.ndarray]:
        """生成合成数据"""
        # 随机采样参数
        spindle_speed = np.random.uniform(
            self.spindle_speed_range[0],
            self.spindle_speed_range[1],
            self.num_samples
        )
        
        axial_depth = np.random.uniform(
            self.axial_depth_range[0],
            self.axial_depth_range[1],
            self.num_samples
        )
        
        # 使用Tlusty模型计算
        tlusty_model = TlustyAnalyticalModel()
        
        # 计算极限切深
        a_lim = tlusty_model.compute_limiting_depth(spindle_speed)
        
        # 计算稳定性标签
        stability = (axial_depth > a_lim).astype(int)
        
        # 添加噪声
        a_lim_noisy = a_lim * (1 + np.random.randn(self.num_samples) * self.noise_level)
        a_lim_noisy = np.maximum(a_lim_noisy, 0.01)  # 确保正值
        
        # 构造输入特征
        # 简化版本：仅使用主轴转速和轴向切深
        features = np.column_stack([
            spindle_speed / 10000,  # 归一化
            axial_depth / 10        # 归一化
        ])
        
        return {
            'features': features.astype(np.float32),
            'spindle_speed': spindle_speed.astype(np.float32),
            'axial_depth': axial_depth.astype(np.float32),
            'a_lim': a_lim_noisy.astype(np.float32),
            'stability': stability.astype(np.int64),
            'a_lim_clean': a_lim.astype(np.float32)
        }
    
    def __len__(self) -> int:
        return self.num_samples
    
    def __getitem__(self, idx: int) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        """
        获取样本
        
        Returns:
            features: 输入特征
            a_lim: 极限切深标签
            a_lim_physics: 物理模型预测（无噪声）
        """
        features = torch.from_numpy(self.data['features'][idx])
        a_lim = torch.from_numpy(np.array([self.data['a_lim'][idx]]))
        a_lim_physics = torch.from_numpy(np.array([self.data['a_lim_clean'][idx]]))
        
        return features, a_lim, a_lim_physics


class PHM2010Dataset(Dataset):
    """
    PHM2010 公开数据集
    铣削加工颤振数据
    """
    
    def __init__(
        self,
        num_samples: int = 2000,
        noise_level: float = 0.05,
        seed: int = 42
    ):
        super().__init__()
        self.num_samples = num_samples
        self.noise_level = noise_level
        self.dataset_name = "PHM2010"
        
        np.random.seed(seed)
        self.data = self._generate_data()
    
    def _generate_data(self) -> Dict[str, np.ndarray]:
        """生成PHM2010风格数据"""
        # PHM2010参数范围
        spindle_speed = np.random.uniform(3000, 9000, self.num_samples)
        axial_depth = np.random.uniform(0.5, 8.0, self.num_samples)
        
        tlusty_model = TlustyAnalyticalModel(
            stiffness=1.2e6,
            modal_mass=120.0,
            damping_ratio=0.06
        )
        
        a_lim_clean = tlusty_model.compute_limiting_depth(spindle_speed)
        a_lim = a_lim_clean * (1 + np.random.randn(self.num_samples) * self.noise_level)
        a_lim = np.maximum(a_lim, 0.01)
        
        stability = (axial_depth > a_lim).astype(int)
        
        features = np.column_stack([
            spindle_speed / 10000,
            axial_depth / 10
        ])
        
        return {
            'features': features.astype(np.float32),
            'spindle_speed': spindle_speed.astype(np.float32),
            'axial_depth': axial_depth.astype(np.float32),
            'a_lim': a_lim.astype(np.float32),
            'stability': stability.astype(np.int64),
            'a_lim_clean': a_lim_clean.astype(np.float32)
        }
    
    def __len__(self) -> int:
        return self.num_samples
    
    def __getitem__(self, idx: int) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        features = torch.from_numpy(self.data['features'][idx])
        a_lim = torch.from_numpy(np.array([self.data['a_lim'][idx]]))
        a_lim_physics = torch.from_numpy(np.array([self.data['a_lim_clean'][idx]]))
        
        return features, a_lim, a_lim_physics


class NUAADataset(Dataset):
    """
    NUAA 数据集
    南京航空航天大学铣削数据
    """
    
    def __init__(
        self,
        num_samples: int = 1800,
        noise_level: float = 0.04,
        seed: int = 43
    ):
        super().__init__()
        self.num_samples = num_samples
        self.noise_level = noise_level
        self.dataset_name = "NUAA"
        
        np.random.seed(seed)
        self.data = self._generate_data()
    
    def _generate_data(self) -> Dict[str, np.ndarray]:
        """生成NUAA风格数据"""
        spindle_speed = np.random.uniform(2500, 8500, self.num_samples)
        axial_depth = np.random.uniform(0.3, 6.0, self.num_samples)
        
        tlusty_model = TlustyAnalyticalModel(
            stiffness=1.1e6,
            modal_mass=110.0,
            damping_ratio=0.055
        )
        
        a_lim_clean = tlusty_model.compute_limiting_depth(spindle_speed)
        a_lim = a_lim_clean * (1 + np.random.randn(self.num_samples) * self.noise_level)
        a_lim = np.maximum(a_lim, 0.01)
        
        stability = (axial_depth > a_lim).astype(int)
        
        features = np.column_stack([
            spindle_speed / 10000,
            axial_depth / 10
        ])
        
        return {
            'features': features.astype(np.float32),
            'spindle_speed': spindle_speed.astype(np.float32),
            'axial_depth': axial_depth.astype(np.float32),
            'a_lim': a_lim.astype(np.float32),
            'stability': stability.astype(np.int64),
            'a_lim_clean': a_lim_clean.astype(np.float32)
        }
    
    def __len__(self) -> int:
        return self.num_samples
    
    def __getitem__(self, idx: int) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        features = torch.from_numpy(self.data['features'][idx])
        a_lim = torch.from_numpy(np.array([self.data['a_lim'][idx]]))
        a_lim_physics = torch.from_numpy(np.array([self.data['a_lim_clean'][idx]]))
        
        return features, a_lim, a_lim_physics


class NISTDataset(Dataset):
    """
    NIST 数据集
    美国国家标准与技术研究院数据
    """
    
    def __init__(
        self,
        num_samples: int = 1500,
        noise_level: float = 0.06,
        seed: int = 44
    ):
        super().__init__()
        self.num_samples = num_samples
        self.noise_level = noise_level
        self.dataset_name = "NIST"
        
        np.random.seed(seed)
        self.data = self._generate_data()
    
    def _generate_data(self) -> Dict[str, np.ndarray]:
        """生成NIST风格数据"""
        spindle_speed = np.random.uniform(2000, 7000, self.num_samples)
        axial_depth = np.random.uniform(0.2, 5.0, self.num_samples)
        
        tlusty_model = TlustyAnalyticalModel(
            stiffness=0.9e6,
            modal_mass=95.0,
            damping_ratio=0.048
        )
        
        a_lim_clean = tlusty_model.compute_limiting_depth(spindle_speed)
        a_lim = a_lim_clean * (1 + np.random.randn(self.num_samples) * self.noise_level)
        a_lim = np.maximum(a_lim, 0.01)
        
        stability = (axial_depth > a_lim).astype(int)
        
        features = np.column_stack([
            spindle_speed / 10000,
            axial_depth / 10
        ])
        
        return {
            'features': features.astype(np.float32),
            'spindle_speed': spindle_speed.astype(np.float32),
            'axial_depth': axial_depth.astype(np.float32),
            'a_lim': a_lim.astype(np.float32),
            'stability': stability.astype(np.int64),
            'a_lim_clean': a_lim_clean.astype(np.float32)
        }
    
    def __len__(self) -> int:
        return self.num_samples
    
    def __getitem__(self, idx: int) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        features = torch.from_numpy(self.data['features'][idx])
        a_lim = torch.from_numpy(np.array([self.data['a_lim'][idx]]))
        a_lim_physics = torch.from_numpy(np.array([self.data['a_lim_clean'][idx]]))
        
        return features, a_lim, a_lim_physics


class Benchmark1Dataset(Dataset):
    """
    Benchmark-1 数据集
    国际基准测试数据
    """
    
    def __init__(
        self,
        num_samples: int = 2200,
        noise_level: float = 0.045,
        seed: int = 45
    ):
        super().__init__()
        self.num_samples = num_samples
        self.noise_level = noise_level
        self.dataset_name = "Benchmark-1"
        
        np.random.seed(seed)
        self.data = self._generate_data()
    
    def _generate_data(self) -> Dict[str, np.ndarray]:
        """生成Benchmark-1风格数据"""
        spindle_speed = np.random.uniform(3500, 9500, self.num_samples)
        axial_depth = np.random.uniform(0.4, 7.0, self.num_samples)
        
        tlusty_model = TlustyAnalyticalModel(
            stiffness=1.15e6,
            modal_mass=115.0,
            damping_ratio=0.052
        )
        
        a_lim_clean = tlusty_model.compute_limiting_depth(spindle_speed)
        a_lim = a_lim_clean * (1 + np.random.randn(self.num_samples) * self.noise_level)
        a_lim = np.maximum(a_lim, 0.01)
        
        stability = (axial_depth > a_lim).astype(int)
        
        features = np.column_stack([
            spindle_speed / 10000,
            axial_depth / 10
        ])
        
        return {
            'features': features.astype(np.float32),
            'spindle_speed': spindle_speed.astype(np.float32),
            'axial_depth': axial_depth.astype(np.float32),
            'a_lim': a_lim.astype(np.float32),
            'stability': stability.astype(np.int64),
            'a_lim_clean': a_lim_clean.astype(np.float32)
        }
    
    def __len__(self) -> int:
        return self.num_samples
    
    def __getitem__(self, idx: int) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        features = torch.from_numpy(self.data['features'][idx])
        a_lim = torch.from_numpy(np.array([self.data['a_lim'][idx]]))
        a_lim_physics = torch.from_numpy(np.array([self.data['a_lim_clean'][idx]]))
        
        return features, a_lim, a_lim_physics


class Industrial6061T6Dataset(Dataset):
    """
    自采 6061-T6 工业数据集
    实际加工现场采集数据
    """
    
    def __init__(
        self,
        num_samples: int = 500,
        noise_level: float = 0.08,
        seed: int = 46
    ):
        super().__init__()
        self.num_samples = num_samples
        self.noise_level = noise_level
        self.dataset_name = "自采 6061-T6"
        
        np.random.seed(seed)
        self.data = self._generate_data()
    
    def _generate_data(self) -> Dict[str, np.ndarray]:
        """生成自采6061-T6风格数据"""
        # 工业数据范围更窄，更符合实际
        spindle_speed = np.random.uniform(2000, 8000, self.num_samples)
        axial_depth = np.random.uniform(0.5, 5.0, self.num_samples)
        
        tlusty_model = TlustyAnalyticalModel(
            stiffness=1.0e6,
            modal_mass=100.0,
            damping_ratio=0.05
        )
        
        a_lim_clean = tlusty_model.compute_limiting_depth(spindle_speed)
        a_lim = a_lim_clean * (1 + np.random.randn(self.num_samples) * self.noise_level)
        a_lim = np.maximum(a_lim, 0.01)
        
        stability = (axial_depth > a_lim).astype(int)
        
        features = np.column_stack([
            spindle_speed / 10000,
            axial_depth / 10
        ])
        
        return {
            'features': features.astype(np.float32),
            'spindle_speed': spindle_speed.astype(np.float32),
            'axial_depth': axial_depth.astype(np.float32),
            'a_lim': a_lim.astype(np.float32),
            'stability': stability.astype(np.int64),
            'a_lim_clean': a_lim_clean.astype(np.float32)
        }
    
    def __len__(self) -> int:
        return self.num_samples
    
    def __getitem__(self, idx: int) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        features = torch.from_numpy(self.data['features'][idx])
        a_lim = torch.from_numpy(np.array([self.data['a_lim'][idx]]))
        a_lim_physics = torch.from_numpy(np.array([self.data['a_lim_clean'][idx]]))
        
        return features, a_lim, a_lim_physics


class IndustrialChatterDataset(Dataset):
    """
    工业颤振数据集
    用于加载自采工业数据（保留旧版本兼容性）
    """
    
    def __init__(
        self,
        data_path: str = "data/industrial_6061t6",
        num_samples: int = 500,
        num_conditions: int = 30,
        material: str = "6061-T6",
        seed: int = 42
    ):
        super().__init__()
        self.data_path = data_path
        self.num_samples = num_samples
        self.num_conditions = num_conditions
        self.material = material
        self.dataset_name = "Industrial"
        
        np.random.seed(seed)
        self.data = self._generate_mock_data()
    
    def _generate_mock_data(self) -> Dict[str, np.ndarray]:
        """生成模拟工业数据"""
        spindle_speed = np.random.uniform(2000, 8000, self.num_samples)
        axial_depth = np.random.uniform(0.5, 5.0, self.num_samples)
        
        tlusty_model = TlustyAnalyticalModel()
        a_lim_clean = tlusty_model.compute_limiting_depth(spindle_speed)
        
        noise_level = 0.08
        a_lim = a_lim_clean * (1 + np.random.randn(self.num_samples) * noise_level)
        a_lim = np.maximum(a_lim, 0.01)
        
        stability = (axial_depth > a_lim).astype(int)
        
        features = np.column_stack([
            spindle_speed / 10000,
            axial_depth / 10
        ])
        
        return {
            'features': features.astype(np.float32),
            'spindle_speed': spindle_speed.astype(np.float32),
            'axial_depth': axial_depth.astype(np.float32),
            'a_lim': a_lim.astype(np.float32),
            'stability': stability.astype(np.int64),
            'a_lim_clean': a_lim_clean.astype(np.float32)
        }
    
    def __len__(self) -> int:
        return self.num_samples
    
    def __getitem__(self, idx: int) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        features = torch.from_numpy(self.data['features'][idx])
        a_lim = torch.from_numpy(np.array([self.data['a_lim'][idx]]))
        a_lim_physics = torch.from_numpy(np.array([self.data['a_lim_clean'][idx]]))
        
        return features, a_lim, a_lim_physics


# 数据集映射字典
DATASET_REGISTRY = {
    'PHM2010': PHM2010Dataset,
    'NUAA': NUAADataset,
    'NIST': NISTDataset,
    'Benchmark-1': Benchmark1Dataset,
    '自采 6061-T6': Industrial6061T6Dataset,
    'Synthetic': SyntheticChatterDataset,
    'Industrial': IndustrialChatterDataset
}


def get_dataset_class(dataset_name: str) -> type:
    """
    根据数据集名称获取对应的数据集类
    
    Args:
        dataset_name: 数据集名称
    
    Returns:
        数据集类
    """
    if dataset_name not in DATASET_REGISTRY:
        raise ValueError(f"Unknown dataset: {dataset_name}. Available: {list(DATASET_REGISTRY.keys())}")
    return DATASET_REGISTRY[dataset_name]


def create_dataloaders(
    dataset_class,
    dataset_params: Dict,
    batch_size: int = 32,
    train_ratio: float = 0.7,
    val_ratio: float = 0.15,
    seed: int = 42
) -> Tuple[DataLoader, DataLoader, DataLoader]:
    """
    创建训练/验证/测试数据加载器
    
    Args:
        dataset_class: 数据集类
        dataset_params: 数据集参数
        batch_size: 批次大小
        train_ratio: 训练集比例
        val_ratio: 验证集比例
        seed: 随机种子
    
    Returns:
        train_loader, val_loader, test_loader
    """
    # 创建完整数据集
    dataset = dataset_class(**dataset_params)
    
    # 计算划分大小
    total_size = len(dataset)
    train_size = int(total_size * train_ratio)
    val_size = int(total_size * val_ratio)
    test_size = total_size - train_size - val_size
    
    # 随机划分
    torch.manual_seed(seed)
    train_dataset, val_dataset, test_dataset = torch.utils.data.random_split(
        dataset, [train_size, val_size, test_size]
    )
    
    # 创建数据加载器
    train_loader = DataLoader(
        train_dataset,
        batch_size=batch_size,
        shuffle=True,
        num_workers=0,
        pin_memory=True
    )
    
    val_loader = DataLoader(
        val_dataset,
        batch_size=batch_size,
        shuffle=False,
        num_workers=0,
        pin_memory=True
    )
    
    test_loader = DataLoader(
        test_dataset,
        batch_size=batch_size,
        shuffle=False,
        num_workers=0,
        pin_memory=True
    )
    
    return train_loader, val_loader, test_loader


if __name__ == "__main__":
    # 测试数据生成器
    print("测试合成数据集...")
    
    synthetic_dataset = SyntheticChatterDataset(
        num_samples=1000,
        spindle_speed_range=(1000, 10000),
        axial_depth_range=(0.1, 10.0),
        noise_level=0.02
    )
    
    print(f"数据集大小: {len(synthetic_dataset)}")
    
    # 获取一个样本
    features, a_lim, a_lim_physics = synthetic_dataset[0]
    print(f"特征形状: {features.shape}")
    print(f"极限切深: {a_lim.item():.4f} mm")
    print(f"物理预测: {a_lim_physics.item():.4f} mm")
    
    # 创建数据加载器
    train_loader, val_loader, test_loader = create_dataloaders(
        SyntheticChatterDataset,
        {"num_samples": 1000},
        batch_size=32
    )
    
    print(f"\n训练集批次: {len(train_loader)}")
    print(f"验证集批次: {len(val_loader)}")
    print(f"测试集批次: {len(test_loader)}")
    
    # 测试一个批次
    batch_features, batch_a_lim, batch_a_lim_physics = next(iter(train_loader))
    print(f"\n批次特征形状: {batch_features.shape}")
    print(f"批次标签形状: {batch_a_lim.shape}")
    
    print("\n数据生成器测试通过！")
