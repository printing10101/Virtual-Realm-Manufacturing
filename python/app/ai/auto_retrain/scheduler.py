"""自动微调调度器

实现双重触发机制：
- 定时触发：支持cron表达式配置（每日/每周）
- 数据量阈值触发：监控新数据量，达到阈值时触发

触发抑制：
- 数据量小于阈值时不触发微调
- 防止频繁训练导致资源浪费
"""

from __future__ import annotations

import asyncio
import logging
import threading
import time
from datetime import datetime
from typing import Any, Dict, Optional

from app.tasks.task_system import AsyncTaskManager, TaskType
from app.training.data_lake import TrainingDataLake

logger = logging.getLogger(__name__)


class AutoRetrainConfig:
    """自动微调配置"""
    
    def __init__(
        self,
        # 定时触发配置
        schedule_enabled: bool = True,
        schedule_cron: str = "0 2 * * 0",  # 每周日凌晨2点
        schedule_interval_hours: int = 168,  # 7天
        
        # 阈值触发配置
        threshold_enabled: bool = True,
        min_samples_threshold: int = 100,  # 最小样本数阈值
        
        # 训练配置
        max_concurrent_training: int = 1,  # 最大并发训练数
        training_timeout_hours: int = 24,  # 训练超时时间
        
        # 数据配置
        data_lookback_days: int = 7,  # 数据回溯天数
        
        # 版本管理
        max_model_versions: int = 5,  # 保留的最大模型版本数
    ):
        self.schedule_enabled = schedule_enabled
        self.schedule_cron = schedule_cron
        self.schedule_interval_hours = schedule_interval_hours
        self.threshold_enabled = threshold_enabled
        self.min_samples_threshold = min_samples_threshold
        self.max_concurrent_training = max_concurrent_training
        self.training_timeout_hours = training_timeout_hours
        self.data_lookback_days = data_lookback_days
        self.max_model_versions = max_model_versions
    
    @classmethod
    def from_dict(cls, config: Dict[str, Any]) -> "AutoRetrainConfig":
        """从字典创建配置"""
        import inspect
        valid_params = set(inspect.signature(cls.__init__).parameters.keys()) - {"self"}
        return cls(**{k: v for k, v in config.items() if k in valid_params})


class TriggerResult:
    """触发检查结果"""
    
    def __init__(
        self,
        should_trigger: bool,
        reason: str,
        new_samples_count: int = 0,
        threshold: int = 0,
    ):
        self.should_trigger = should_trigger
        self.reason = reason
        self.new_samples_count = new_samples_count
        self.threshold = threshold
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "should_trigger": self.should_trigger,
            "reason": self.reason,
            "new_samples_count": self.new_samples_count,
            "threshold": self.threshold,
        }


class AutoRetrainScheduler:
    """自动微调调度器
    
    负责：
    - 定时调度检查
    - 数据量阈值监控
    - 触发训练任务提交
    """
    
    def __init__(
        self,
        config: Optional[AutoRetrainConfig] = None,
        task_manager: Optional[AsyncTaskManager] = None,
        data_lake: Optional[TrainingDataLake] = None,
    ):
        self.config = config or AutoRetrainConfig()
        self.task_manager = task_manager or AsyncTaskManager()
        self.data_lake = data_lake or TrainingDataLake()
        
        self._last_trigger_time: Optional[datetime] = None
        self._last_samples_count: int = 0
        self._running = False
        self._scheduler_task: Optional[asyncio.Task] = None
        
        logger.info("AutoRetrainScheduler initialized with config: %s", self.config.__dict__)
    
    async def start(self):
        """启动调度器"""
        if self._running:
            logger.warning("Scheduler is already running")
            return
        
        self._running = True
        self._scheduler_task = asyncio.create_task(self._scheduler_loop())
        logger.info("AutoRetrainScheduler started")
    
    async def stop(self):
        """停止调度器"""
        self._running = False
        if self._scheduler_task:
            self._scheduler_task.cancel()
            try:
                await self._scheduler_task
            except asyncio.CancelledError:
                pass
        logger.info("AutoRetrainScheduler stopped")
    
    async def _scheduler_loop(self):
        """调度循环"""
        check_interval = 3600  # 每小时检查一次
        
        while self._running:
            try:
                await self.check_and_trigger()
                await asyncio.sleep(check_interval)
            except asyncio.CancelledError:
                break
            except (RuntimeError, ValueError, OSError) as e:
                logger.error("Scheduler loop error: %s", e, exc_info=True)
                await asyncio.sleep(60)  # 出错后等待1分钟重试
    
    async def check_and_trigger(self) -> TriggerResult:
        """检查是否应该触发微调
        
        Returns:
            TriggerResult: 触发检查结果
        """
        # 1. 获取新数据量
        new_samples = await self._count_new_samples()
        
        # 2. 检查阈值触发
        if self.config.threshold_enabled:
            if new_samples < self.config.min_samples_threshold:
                return TriggerResult(
                    should_trigger=False,
                    reason=f"新数据量({new_samples})未达到阈值({self.config.min_samples_threshold})",
                    new_samples_count=new_samples,
                    threshold=self.config.min_samples_threshold,
                )
            
            return TriggerResult(
                should_trigger=True,
                reason=f"新数据量({new_samples})达到阈值({self.config.min_samples_threshold})",
                new_samples_count=new_samples,
                threshold=self.config.min_samples_threshold,
            )
        
        # 3. 检查定时触发
        if self.config.schedule_enabled:
            if self._should_trigger_by_time():
                return TriggerResult(
                    should_trigger=True,
                    reason="定时触发条件满足",
                    new_samples_count=new_samples,
                    threshold=self.config.min_samples_threshold,
                )
            
            return TriggerResult(
                should_trigger=False,
                reason="未到定时触发时间",
                new_samples_count=new_samples,
                threshold=self.config.min_samples_threshold,
            )
        
        return TriggerResult(
            should_trigger=False,
            reason="所有触发机制均未启用",
            new_samples_count=new_samples,
            threshold=self.config.min_samples_threshold,
        )
    
    async def _count_new_samples(self) -> int:
        """统计新数据量
        
        Returns:
            新样本数量
        """
        try:
            stats = self.data_lake.get_statistics()
            total_samples = stats.get("total_samples", 0)
            
            # 计算新增样本数（相对于上次触发）
            new_samples = total_samples - self._last_samples_count
            return max(0, new_samples)
        except (AttributeError, TypeError, ValueError, OSError) as e:
            logger.warning("Failed to count new samples: %s", e, exc_info=True)
            return 0
    
    def _should_trigger_by_time(self) -> bool:
        """检查是否应该按时间触发"""
        if self._last_trigger_time is None:
            return True
        
        hours_since_last = (datetime.now() - self._last_trigger_time).total_seconds() / 3600
        return hours_since_last >= self.config.schedule_interval_hours
    
    async def trigger_retrain(self, trigger_reason: str = "manual") -> Dict[str, Any]:
        """手动触发微调
        
        Args:
            trigger_reason: 触发原因
            
        Returns:
            触发结果字典
        """
        logger.info("Manual retrain triggered: %s", trigger_reason)
        
        # 检查数据量
        new_samples = await self._count_new_samples()
        if new_samples < self.config.min_samples_threshold:
            return {
                "success": False,
                "reason": f"数据量不足: {new_samples} < {self.config.min_samples_threshold}",
                "new_samples": new_samples,
            }
        
        # 提交训练任务
        return await self._submit_training_task(trigger_reason, new_samples)
    
    async def _submit_training_task(
        self, trigger_reason: str, new_samples: int
    ) -> Dict[str, Any]:
        """提交训练任务
        
        Args:
            trigger_reason: 触发原因
            new_samples: 新样本数量
            
        Returns:
            提交结果
        """
        try:
            # 准备任务参数
            params = {
                "trigger_reason": trigger_reason,
                "new_samples_count": new_samples,
                "data_lookback_days": self.config.data_lookback_days,
                "max_model_versions": self.config.max_model_versions,
                "timestamp": datetime.now().isoformat(),
            }
            
            # 创建任务
            task = await self.task_manager.create_task(
                task_type=TaskType.LNN_TRAINING,
                params=params,
                owner_id="auto_retrain_scheduler",
                idempotency_key=f"auto_retrain_{int(time.time())}",
            )
            
            # 更新触发状态
            self._last_trigger_time = datetime.now()
            self._last_samples_count += new_samples
            
            logger.info("Training task submitted: %s", task.job_id)
            
            return {
                "success": True,
                "task_id": task.job_id,
                "trigger_reason": trigger_reason,
                "new_samples": new_samples,
            }
            
        except (RuntimeError, ValueError, KeyError, OSError) as e:
            logger.error("Failed to submit training task: %s", e, exc_info=True)
            return {
                "success": False,
                "reason": f"提交训练任务失败: {str(e)}",
            }
    
    def get_status(self) -> Dict[str, Any]:
        """获取调度器状态"""
        return {
            "running": self._running,
            "last_trigger_time": self._last_trigger_time.isoformat() if self._last_trigger_time else None,
            "last_samples_count": self._last_samples_count,
            "config": {
                "schedule_enabled": self.config.schedule_enabled,
                "threshold_enabled": self.config.threshold_enabled,
                "min_samples_threshold": self.config.min_samples_threshold,
                "schedule_interval_hours": self.config.schedule_interval_hours,
            },
        }


# 全局实例
_scheduler_instance: Optional[AutoRetrainScheduler] = None
_scheduler_instance_lock = threading.Lock()


def get_scheduler(config: Optional[AutoRetrainConfig] = None) -> AutoRetrainScheduler:
    """获取全局调度器实例"""
    # 安全修复：双重检查锁，防止并发创建多个实例
    global _scheduler_instance
    if _scheduler_instance is None:
        with _scheduler_instance_lock:
            if _scheduler_instance is None:
                _scheduler_instance = AutoRetrainScheduler(config)
    return _scheduler_instance


def reset_scheduler() -> None:
    """重置全局调度器实例（主要用于测试）。"""
    global _scheduler_instance
    with _scheduler_instance_lock:
        _scheduler_instance = None


async def trigger_now() -> Dict[str, Any]:
    """立即触发微调（命令行入口）"""
    scheduler = get_scheduler()
    return await scheduler.trigger_retrain(trigger_reason="manual_cli")


if __name__ == "__main__":
    """命令行入口：python -m app.ai.auto_retrain.scheduler --trigger-now"""
    import sys

    if "--trigger-now" in sys.argv:
        result = asyncio.run(trigger_now())
        logger.info("Trigger result: %s", result)
    else:
        logger.info("Usage: python -m app.ai.auto_retrain.scheduler --trigger-now")
