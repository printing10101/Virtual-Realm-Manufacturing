"""调度器单元测试"""

import pytest
from unittest.mock import Mock, AsyncMock, MagicMock, patch
from datetime import datetime, timedelta

from app.ai.auto_retrain.scheduler import (
    AutoRetrainScheduler,
    AutoRetrainConfig,
    TriggerResult,
    get_scheduler,
)


class TestAutoRetrainConfig:
    """配置测试"""
    
    def test_default_config(self):
        """测试默认配置"""
        config = AutoRetrainConfig()
        assert config.schedule_enabled is True
        assert config.threshold_enabled is True
        assert config.min_samples_threshold == 100
        assert config.schedule_interval_hours == 168
    
    def test_config_from_dict(self):
        """测试从字典创建配置"""
        config_dict = {
            "min_samples_threshold": 50,
            "schedule_interval_hours": 24,
        }
        config = AutoRetrainConfig.from_dict(config_dict)
        assert config.min_samples_threshold == 50
        assert config.schedule_interval_hours == 24


class TestTriggerResult:
    """触发结果测试"""
    
    def test_trigger_result_to_dict(self):
        """测试触发结果序列化"""
        result = TriggerResult(
            should_trigger=True,
            reason="测试原因",
            new_samples_count=150,
            threshold=100,
        )
        result_dict = result.to_dict()
        assert result_dict["should_trigger"] is True
        assert result_dict["reason"] == "测试原因"
        assert result_dict["new_samples_count"] == 150
        assert result_dict["threshold"] == 100


class TestAutoRetrainScheduler:
    """调度器测试"""
    
    @pytest.fixture
    def mock_task_manager(self):
        """模拟任务管理器"""
        manager = Mock()
        manager.create_task = AsyncMock()
        return manager
    
    @pytest.fixture
    def mock_data_lake(self):
        """模拟数据湖"""
        lake = Mock()
        lake.get_statistics = Mock(return_value={"total_samples": 200})
        return lake
    
    @pytest.fixture
    def scheduler(self, mock_task_manager, mock_data_lake):
        """创建测试调度器"""
        config = AutoRetrainConfig(
            min_samples_threshold=100,
            schedule_interval_hours=24,
        )
        return AutoRetrainScheduler(
            config=config,
            task_manager=mock_task_manager,
            data_lake=mock_data_lake,
        )
    
    @pytest.mark.asyncio
    async def test_count_new_samples(self, scheduler, mock_data_lake):
        """测试新样本计数"""
        count = await scheduler._count_new_samples()
        assert count == 200
        mock_data_lake.get_statistics.assert_called()
    
    @pytest.mark.asyncio
    async def test_check_and_trigger_threshold_met(self, scheduler):
        """测试阈值触发 - 满足条件"""
        result = await scheduler.check_and_trigger()
        assert result.should_trigger is True
        assert "达到阈值" in result.reason
    
    @pytest.mark.asyncio
    async def test_check_and_trigger_threshold_not_met(self, scheduler, mock_data_lake):
        """测试阈值触发 - 不满足条件"""
        mock_data_lake.get_statistics.return_value = {"total_samples": 50}
        result = await scheduler.check_and_trigger()
        assert result.should_trigger is False
        assert "未达到阈值" in result.reason
    
    @pytest.mark.asyncio
    async def test_trigger_retrain_success(self, scheduler, mock_task_manager):
        """测试手动触发成功"""
        # 模拟任务创建成功
        mock_task = Mock()
        mock_task.job_id = "training-test123"
        mock_task_manager.create_task.return_value = mock_task
        
        result = await scheduler.trigger_retrain(trigger_reason="test")
        assert result["success"] is True
        assert result["task_id"] == "training-test123"
    
    @pytest.mark.asyncio
    async def test_trigger_retrain_insufficient_data(self, scheduler, mock_data_lake):
        """测试手动触发 - 数据不足"""
        mock_data_lake.get_statistics.return_value = {"total_samples": 50}
        result = await scheduler.trigger_retrain(trigger_reason="test")
        assert result["success"] is False
        assert "数据量不足" in result["reason"]
    
    def test_get_status(self, scheduler):
        """测试获取状态"""
        status = scheduler.get_status()
        assert "running" in status
        assert "config" in status
        assert status["config"]["min_samples_threshold"] == 100
    
    def test_should_trigger_by_time_first_time(self, scheduler):
        """测试时间触发 - 首次"""
        assert scheduler._should_trigger_by_time() is True
    
    def test_should_trigger_by_time_interval_passed(self, scheduler):
        """测试时间触发 - 间隔已过"""
        scheduler._last_trigger_time = datetime.now() - timedelta(hours=25)
        assert scheduler._should_trigger_by_time() is True
    
    def test_should_trigger_by_time_interval_not_passed(self, scheduler):
        """测试时间触发 - 间隔未过"""
        scheduler._last_trigger_time = datetime.now() - timedelta(hours=1)
        assert scheduler._should_trigger_by_time() is False


class TestGetScheduler:
    """全局调度器实例测试"""
    
    def test_get_scheduler_singleton(self):
        """测试单例模式"""
        scheduler1 = get_scheduler()
        scheduler2 = get_scheduler()
        assert scheduler1 is scheduler2
