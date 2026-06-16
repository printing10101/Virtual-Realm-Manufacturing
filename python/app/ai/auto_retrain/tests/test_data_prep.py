"""数据准备模块单元测试"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
import tempfile
import json
from pathlib import Path

from app.ai.auto_retrain.data_prep import (
    DataPreparator,
    TrainingSample,
    TrainingDataset,
    get_data_preparator,
)


class TestTrainingSample:
    """训练样本测试"""
    
    def test_valid_sample(self):
        """测试有效样本"""
        data = {
            "record_id": "test_001",
            "features": {"spindle_speed": 1000, "feed_rate": 100},
            "labels": {"first_pass_acceptance": True},
        }
        sample = TrainingSample(data)
        assert sample.is_valid() is True
        assert sample.record_id == "test_001"
    
    def test_invalid_sample_missing_record_id(self):
        """测试无效样本 - 缺少record_id"""
        data = {
            "features": {"spindle_speed": 1000},
            "labels": {"first_pass_acceptance": True},
        }
        sample = TrainingSample(data)
        assert sample.is_valid() is False
    
    def test_invalid_sample_missing_features(self):
        """测试无效样本 - 缺少features"""
        data = {
            "record_id": "test_001",
            "labels": {"first_pass_acceptance": True},
        }
        sample = TrainingSample(data)
        assert sample.is_valid() is False
    
    def test_to_tensor_dict(self):
        """测试转换为张量字典"""
        data = {
            "record_id": "test_001",
            "features": {
                "spindle_speed": 1000,
                "feed_rate": 100,
                "depth_of_cut": 5,
            },
            "labels": {
                "first_pass_acceptance": True,
                "actual_dimensions": [10.5],
                "surface_roughness": 1.2,
            },
        }
        sample = TrainingSample(data)
        tensor_dict = sample.to_tensor_dict()
        assert "record_id" in tensor_dict
        assert "features" in tensor_dict
        assert "labels" in tensor_dict
        assert len(tensor_dict["features"]) == 6  # 3数值 + 3类别
        assert len(tensor_dict["labels"]) == 3


class TestDataPreparator:
    """数据准备器测试"""
    
    @pytest.fixture
    def mock_data_lake(self):
        """模拟数据湖"""
        lake = Mock()
        lake.load_training_samples = Mock(return_value=[])
        return lake
    
    @pytest.fixture
    def preparator(self, mock_data_lake):
        """创建测试数据准备器"""
        return DataPreparator(
            data_lake=mock_data_lake,
            val_split_ratio=0.2,
            random_seed=42,
        )
    
    def test_extract_samples_empty(self, preparator, mock_data_lake):
        """测试提取样本 - 空数据"""
        samples = preparator._extract_samples(lookback_days=7)
        assert len(samples) == 0
    
    def test_extract_samples_with_data(self, preparator, mock_data_lake):
        """测试提取样本 - 有数据"""
        # 模拟返回数据
        mock_data_lake.load_training_samples.return_value = [
            {
                "record_id": "test_001",
                "features": {"spindle_speed": 1000, "feed_rate": 100},
                "labels": {"first_pass_acceptance": True},
            },
            {
                "record_id": "test_002",
                "features": {"spindle_speed": 1200, "feed_rate": 120},
                "labels": {"first_pass_acceptance": False},
            },
        ]
        samples = preparator._extract_samples(lookback_days=7)
        assert len(samples) > 0
    
    def test_clean_samples_valid(self, preparator):
        """测试清洗样本 - 全部有效"""
        samples = [
            TrainingSample({
                "record_id": "test_001",
                "features": {"spindle_speed": 1000, "feed_rate": 100},
                "labels": {"first_pass_acceptance": True},
            }),
        ]
        valid = preparator._clean_samples(samples)
        assert len(valid) == 1
    
    def test_clean_samples_invalid(self, preparator):
        """测试清洗样本 - 包含无效样本"""
        samples = [
            TrainingSample({
                "record_id": "test_001",
                "features": {"spindle_speed": 1000, "feed_rate": 100},
                "labels": {"first_pass_acceptance": True},
            }),
            TrainingSample({
                "record_id": "test_002",
                "features": {},  # 缺少必要特征
                "labels": {"first_pass_acceptance": True},
            }),
        ]
        valid = preparator._clean_samples(samples)
        assert len(valid) == 1
    
    def test_has_required_features_complete(self, preparator):
        """测试特征检查 - 完整"""
        features = {"spindle_speed": 1000, "feed_rate": 100}
        assert preparator._has_required_features(features) is True
    
    def test_has_required_features_missing(self, preparator):
        """测试特征检查 - 缺失"""
        features = {"spindle_speed": 1000}
        assert preparator._has_required_features(features) is False
    
    @pytest.mark.asyncio
    async def test_prepare_training_data_insufficient(self, preparator, mock_data_lake):
        """测试数据准备 - 样本不足"""
        mock_data_lake.load_training_samples.return_value = []
        result = preparator.prepare_training_data(lookback_days=7, min_samples=100)
        assert result["success"] is False
        assert "样本数不足" in result["error"]


class TestTrainingDataset:
    """训练数据集测试"""
    
    def test_dataset_creation(self):
        """测试数据集创建"""
        samples = [
            TrainingSample({
                "record_id": f"test_{i}",
                "features": {"spindle_speed": 1000 + i, "feed_rate": 100 + i},
                "labels": {"first_pass_acceptance": True},
            })
            for i in range(10)
        ]
        dataset = TrainingDataset(samples)
        assert len(dataset) == 10
    
    def test_dataset_getitem(self):
        """测试数据集获取项"""
        samples = [
            TrainingSample({
                "record_id": "test_001",
                "features": {"spindle_speed": 1000, "feed_rate": 100},
                "labels": {"first_pass_acceptance": True},
            }),
        ]
        dataset = TrainingDataset(samples)
        features, labels = dataset[0]
        assert features is not None
        assert labels is not None


class TestGetDataPreparator:
    """全局数据准备器实例测试"""
    
    def test_get_preparator_singleton(self):
        """测试单例模式"""
        preparator1 = get_data_preparator()
        preparator2 = get_data_preparator()
        assert preparator1 is preparator2
