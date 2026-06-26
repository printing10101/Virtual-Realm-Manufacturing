"""训练数据准备模块

负责从数据湖提取、清洗、预处理训练数据：
- 按时间范围提取新数据
- 数据清洗与格式标准化
- 训练集/验证集自动划分
- 数据质量检查

设计原则：
- 不修改原始数据湖数据
- 确保数据格式与LNNTrainer兼容
- 支持增量数据提取
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from torch.utils.data import Dataset, DataLoader, random_split

from app.training.data_lake import TrainingDataLake

logger = logging.getLogger(__name__)


class TrainingSample:
    """训练样本封装"""
    
    def __init__(self, data: Dict[str, Any]):
        self.data = data
        self.record_id = data.get("record_id")
        self.features = data.get("features", {})
        self.labels = data.get("labels", {})
        self.timestamp = data.get("timestamp")
        self.metadata = data.get("metadata", {})
    
    def is_valid(self) -> bool:
        """检查样本是否有效"""
        if not self.record_id:
            return False
        if not self.features:
            return False
        if not self.labels:
            return False
        return True
    
    def to_tensor_dict(self) -> Dict[str, Any]:
        """转换为张量格式"""
        return {
            "record_id": self.record_id,
            "features": self._encode_features(),
            "labels": self._encode_labels(),
        }
    
    def _encode_features(self) -> List[float]:
        """编码特征为数值向量"""
        feature_values = []
        
        # 数值特征
        numeric_keys = ["spindle_speed", "feed_rate", "depth_of_cut"]
        for key in numeric_keys:
            val = self.features.get(key)
            if val is not None:
                feature_values.append(float(val))
            else:
                feature_values.append(0.0)
        
        # 类别特征（简单编码）
        categorical_keys = ["machine_id", "tool_id", "workpiece_material"]
        for key in categorical_keys:
            val = self.features.get(key)
            if val is not None:
                # 使用哈希编码
                feature_values.append(float(hash(str(val)) % 1000) / 1000.0)
            else:
                feature_values.append(0.0)
        
        return feature_values
    
    def _encode_labels(self) -> List[float]:
        """编码标签为数值向量"""
        label_values = []
        
        # 首次通过率
        first_pass = self.labels.get("first_pass_acceptance")
        if first_pass is not None:
            label_values.append(1.0 if first_pass else 0.0)
        else:
            label_values.append(0.0)
        
        # 实际尺寸（取第一个维度作为示例）
        actual_dims = self.labels.get("actual_dimensions", [])
        if actual_dims and len(actual_dims) > 0:
            label_values.append(float(actual_dims[0]))
        else:
            label_values.append(0.0)
        
        # 表面粗糙度
        roughness = self.labels.get("surface_roughness")
        if roughness is not None:
            label_values.append(float(roughness))
        else:
            label_values.append(0.0)
        
        return label_values


class TrainingDataset(Dataset):
    """PyTorch数据集封装"""
    
    def __init__(self, samples: List[TrainingSample]):
        self.samples = samples
        self._prepare_tensors()
    
    def _prepare_tensors(self):
        """预处理所有样本为张量"""
        import torch
        
        self.features_list = []
        self.labels_list = []
        
        for sample in self.samples:
            tensor_dict = sample.to_tensor_dict()
            self.features_list.append(torch.tensor(tensor_dict["features"], dtype=torch.float32))
            self.labels_list.append(torch.tensor(tensor_dict["labels"], dtype=torch.float32))
    
    def __len__(self) -> int:
        return len(self.samples)
    
    def __getitem__(self, idx: int) -> Tuple[Any, Any]:
        return self.features_list[idx], self.labels_list[idx]


class DataPreparator:
    """数据准备器
    
    负责：
    - 从数据湖提取数据
    - 数据清洗与验证
    - 训练集/验证集划分
    - 创建DataLoader
    """
    
    def __init__(
        self,
        data_lake: Optional[TrainingDataLake] = None,
        val_split_ratio: float = 0.2,
        random_seed: int = 42,
    ):
        self.data_lake = data_lake or TrainingDataLake()
        self.val_split_ratio = val_split_ratio
        self.random_seed = random_seed
        
        logger.info("DataPreparator initialized: val_split=%.2f, seed=%d", 
                   val_split_ratio, random_seed)
    
    def prepare_training_data(
        self,
        lookback_days: int = 7,
        min_samples: int = 100,
    ) -> Dict[str, Any]:
        """准备训练数据
        
        Args:
            lookback_days: 回溯天数
            min_samples: 最小样本数要求
            
        Returns:
            准备结果字典，包含：
            - success: 是否成功
            - train_loader: 训练数据加载器
            - val_loader: 验证数据加载器
            - stats: 统计信息
            - error: 错误信息（如果失败）
        """
        try:
            # 1. 提取数据
            samples = self._extract_samples(lookback_days)
            
            if len(samples) < min_samples:
                return {
                    "success": False,
                    "error": f"样本数不足: {len(samples)} < {min_samples}",
                    "sample_count": len(samples),
                }
            
            # 2. 清洗数据
            valid_samples = self._clean_samples(samples)
            
            if len(valid_samples) < min_samples:
                return {
                    "success": False,
                    "error": f"有效样本数不足: {len(valid_samples)} < {min_samples}",
                    "sample_count": len(valid_samples),
                }
            
            # 3. 创建数据集
            dataset = TrainingDataset(valid_samples)
            
            # 4. 划分训练集/验证集
            train_dataset, val_dataset = self._split_dataset(dataset)
            
            # 5. 创建DataLoader
            train_loader = DataLoader(
                train_dataset,
                batch_size=64,
                shuffle=True,
                num_workers=0,
            )
            val_loader = DataLoader(
                val_dataset,
                batch_size=64,
                shuffle=False,
                num_workers=0,
            )
            
            logger.info("Data preparation completed: train=%d, val=%d",
                       len(train_dataset), len(val_dataset))
            
            return {
                "success": True,
                "train_loader": train_loader,
                "val_loader": val_loader,
                "stats": {
                    "total_samples": len(samples),
                    "valid_samples": len(valid_samples),
                    "train_samples": len(train_dataset),
                    "val_samples": len(val_dataset),
                    "lookback_days": lookback_days,
                },
            }
            
        except (RuntimeError, ValueError, KeyError, TypeError, OSError) as e:
            logger.error("Data preparation failed: %s", e, exc_info=True)
            return {
                "success": False,
                "error": f"数据准备失败: {str(e)}",
            }
    
    def _extract_samples(self, lookback_days: int) -> List[TrainingSample]:
        """从数据湖提取样本
        
        Args:
            lookback_days: 回溯天数
            
        Returns:
            训练样本列表
        """
        samples = []
        
        # 计算日期范围
        end_date = datetime.now()
        start_date = end_date - timedelta(days=lookback_days)
        
        # 遍历日期范围内的所有数据文件
        current_date = start_date
        while current_date <= end_date:
            date_str = current_date.strftime("%Y%m%d")
            raw_samples = self.data_lake.load_training_samples(date=date_str)
            
            for raw in raw_samples:
                sample = TrainingSample(raw)
                samples.append(sample)
            
            current_date += timedelta(days=1)
        
        logger.info("Extracted %d samples from last %d days", len(samples), lookback_days)
        return samples
    
    def _clean_samples(self, samples: List[TrainingSample]) -> List[TrainingSample]:
        """清洗样本数据
        
        Args:
            samples: 原始样本列表
            
        Returns:
            有效样本列表
        """
        valid_samples = []
        
        for sample in samples:
            # 检查样本有效性
            if not sample.is_valid():
                logger.debug("Skipping invalid sample: %s", sample.record_id)
                continue
            
            # 检查特征完整性
            features = sample.features
            if not self._has_required_features(features):
                logger.debug("Skipping sample with missing features: %s", sample.record_id)
                continue
            
            valid_samples.append(sample)
        
        logger.info("Cleaned samples: %d/%d valid", len(valid_samples), len(samples))
        return valid_samples
    
    def _has_required_features(self, features: Dict[str, Any]) -> bool:
        """检查是否包含必要特征"""
        required_keys = ["spindle_speed", "feed_rate"]
        return all(key in features and features[key] is not None for key in required_keys)
    
    def _split_dataset(
        self, dataset: TrainingDataset
    ) -> Tuple[TrainingDataset, TrainingDataset]:
        """划分训练集和验证集
        
        Args:
            dataset: 完整数据集
            
        Returns:
            (训练数据集, 验证数据集)
        """
        total_size = len(dataset)
        val_size = int(total_size * self.val_split_ratio)
        train_size = total_size - val_size
        
        # 设置随机种子确保可重复性
        generator = torch.Generator().manual_seed(self.random_seed)
        
        train_dataset, val_dataset = random_split(
            dataset,
            [train_size, val_size],
            generator=generator,
        )
        
        logger.info("Dataset split: train=%d, val=%d", train_size, val_size)
        return train_dataset, val_dataset


# 全局实例
_preparator_instance: Optional[DataPreparator] = None
_preparator_instance_lock = threading.Lock()


def get_data_preparator(
    val_split_ratio: float = 0.2,
    random_seed: int = 42,
) -> DataPreparator:
    """获取全局数据准备器实例"""
    # 安全修复：双重检查锁，防止并发创建多个实例
    global _preparator_instance
    if _preparator_instance is None:
        with _preparator_instance_lock:
            if _preparator_instance is None:
                _preparator_instance = DataPreparator(val_split_ratio, random_seed)
    return _preparator_instance


def reset_data_preparator() -> None:
    """重置全局数据准备器实例（主要用于测试）。"""
    global _preparator_instance
    with _preparator_instance_lock:
        _preparator_instance = None


# 导入torch用于random_split
import torch
