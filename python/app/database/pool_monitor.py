"""数据库连接池监控与告警模块

提供连接池性能指标收集、阈值告警和健康检查功能。
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Optional, Dict, Any
from collections import deque

logger = logging.getLogger(__name__)


@dataclass
class PoolMetrics:
    """连接池指标快照"""
    pool_size: int
    max_overflow: int
    active_count: int
    idle_count: int
    wait_count: int
    overflow_count: int
    utilization_percent: float
    avg_wait_time_ms: float
    max_wait_time_ms: float
    error_count: int
    timestamp: float


@dataclass
class PoolAlert:
    """连接池告警"""
    level: str  # WARNING, ERROR, CRITICAL
    metric: str
    value: float
    threshold: float
    message: str
    timestamp: float


class ConnectionPoolMonitor:
    """连接池监控器
    
    收集连接池性能指标，检测异常并触发告警。
    """
    
    def __init__(
        self,
        pool_name: str,
        warning_threshold: float = 0.8,
        critical_threshold: float = 0.95,
        max_wait_time_ms: float = 5000.0,
    ):
        """
        Args:
            pool_name: 连接池名称（用于日志标识）
            warning_threshold: 警告阈值（0-1，连接池使用率）
            critical_threshold: 严重告警阈值（0-1）
            max_wait_time_ms: 最大等待时间告警阈值（毫秒）
        """
        self.pool_name = pool_name
        self.warning_threshold = warning_threshold
        self.critical_threshold = critical_threshold
        self.max_wait_time_ms = max_wait_time_ms
        
        # 历史指标记录（保留最近 100 条）
        self._metrics_history: deque[PoolMetrics] = deque(maxlen=100)
        self._alerts: deque[PoolAlert] = deque(maxlen=50)
        
        # 等待时间统计
        self._wait_times: deque[float] = deque(maxlen=100)
        self._error_count = 0
        
        logger.info(
            "ConnectionPoolMonitor initialized: pool=%s warning=%.2f critical=%.2f",
            pool_name,
            warning_threshold,
            critical_threshold,
        )
    
    def record_wait_time(self, wait_time_ms: float) -> None:
        """记录连接等待时间"""
        self._wait_times.append(wait_time_ms)
    
    def record_error(self) -> None:
        """记录连接错误"""
        self._error_count += 1
    
    def collect_metrics(
        self,
        pool_size: int,
        max_overflow: int,
        active_count: int,
        idle_count: int,
        wait_count: int = 0,
        overflow_count: int = 0,
    ) -> PoolMetrics:
        """收集当前时刻的指标快照
        
        Args:
            pool_size: 连接池大小
            max_overflow: 最大溢出连接数
            active_count: 活跃连接数
            idle_count: 空闲连接数
            wait_count: 等待获取连接的请求数
            overflow_count: 当前溢出连接数
            
        Returns:
            PoolMetrics: 指标快照
        """
        total_capacity = pool_size + max_overflow
        utilization = (active_count / total_capacity) if total_capacity > 0 else 0.0
        
        # 计算等待时间统计
        avg_wait = sum(self._wait_times) / len(self._wait_times) if self._wait_times else 0.0
        max_wait = max(self._wait_times) if self._wait_times else 0.0
        
        metrics = PoolMetrics(
            pool_size=pool_size,
            max_overflow=max_overflow,
            active_count=active_count,
            idle_count=idle_count,
            wait_count=wait_count,
            overflow_count=overflow_count,
            utilization_percent=utilization * 100,
            avg_wait_time_ms=avg_wait,
            max_wait_time_ms=max_wait,
            error_count=self._error_count,
            timestamp=time.time(),
        )
        
        self._metrics_history.append(metrics)
        
        # 检查是否需要触发告警
        self._check_alerts(metrics)
        
        return metrics
    
    def _check_alerts(self, metrics: PoolMetrics) -> None:
        """检查指标是否触发告警"""
        alerts = []
        
        # 连接池使用率告警
        utilization = metrics.utilization_percent / 100.0
        if utilization >= self.critical_threshold:
            alert = PoolAlert(
                level="CRITICAL",
                metric="utilization",
                value=metrics.utilization_percent,
                threshold=self.critical_threshold * 100,
                message=f"连接池使用率严重过高: {metrics.utilization_percent:.1f}% (阈值: {self.critical_threshold * 100:.1f}%)",
                timestamp=time.time(),
            )
            alerts.append(alert)
            logger.critical("[%s] %s", self.pool_name, alert.message)
        elif utilization >= self.warning_threshold:
            alert = PoolAlert(
                level="WARNING",
                metric="utilization",
                value=metrics.utilization_percent,
                threshold=self.warning_threshold * 100,
                message=f"连接池使用率偏高: {metrics.utilization_percent:.1f}% (阈值: {self.warning_threshold * 100:.1f}%)",
                timestamp=time.time(),
            )
            alerts.append(alert)
            logger.warning("[%s] %s", self.pool_name, alert.message)
        
        # 等待时间告警
        if metrics.max_wait_time_ms >= self.max_wait_time_ms:
            alert = PoolAlert(
                level="WARNING",
                metric="wait_time",
                value=metrics.max_wait_time_ms,
                threshold=self.max_wait_time_ms,
                message=f"连接等待时间过长: {metrics.max_wait_time_ms:.1f}ms (阈值: {self.max_wait_time_ms:.1f}ms)",
                timestamp=time.time(),
            )
            alerts.append(alert)
            logger.warning("[%s] %s", self.pool_name, alert.message)
        
        # 等待队列告警
        if metrics.wait_count > 0:
            alert = PoolAlert(
                level="WARNING",
                metric="wait_queue",
                value=metrics.wait_count,
                threshold=0,
                message=f"有 {metrics.wait_count} 个请求正在等待连接",
                timestamp=time.time(),
            )
            alerts.append(alert)
            logger.warning("[%s] %s", self.pool_name, alert.message)
        
        # 错误率告警（最近 100 次操作中错误超过 10 次）
        if metrics.error_count > 10:
            alert = PoolAlert(
                level="ERROR",
                metric="error_count",
                value=metrics.error_count,
                threshold=10,
                message=f"连接错误次数过多: {metrics.error_count} 次",
                timestamp=time.time(),
            )
            alerts.append(alert)
            logger.error("[%s] %s", self.pool_name, alert.message)
        
        self._alerts.extend(alerts)
    
    def get_latest_metrics(self) -> Optional[PoolMetrics]:
        """获取最新的指标快照"""
        return self._metrics_history[-1] if self._metrics_history else None
    
    def get_recent_alerts(self, count: int = 10) -> list[PoolAlert]:
        """获取最近的告警记录"""
        return list(self._alerts)[-count:]
    
    def get_health_status(self) -> Dict[str, Any]:
        """获取连接池健康状态摘要"""
        latest = self.get_latest_metrics()
        if latest is None:
            return {
                "status": "unknown",
                "message": "尚未收集到指标数据",
            }
        
        # 根据最新指标判断健康状态
        utilization = latest.utilization_percent / 100.0
        if utilization >= self.critical_threshold or latest.error_count > 10:
            status = "critical"
        elif utilization >= self.warning_threshold or latest.max_wait_time_ms > 1000:
            status = "warning"
        else:
            status = "healthy"
        
        return {
            "status": status,
            "pool_name": self.pool_name,
            "utilization_percent": latest.utilization_percent,
            "active_connections": latest.active_count,
            "idle_connections": latest.idle_count,
            "wait_queue": latest.wait_count,
            "avg_wait_time_ms": latest.avg_wait_time_ms,
            "error_count": latest.error_count,
            "recent_alerts": len(self._alerts),
        }


# 全局监控器实例（延迟初始化）
_monitors: Dict[str, ConnectionPoolMonitor] = {}


def get_pool_monitor(pool_name: str, **kwargs) -> ConnectionPoolMonitor:
    """获取或创建连接池监控器
    
    Args:
        pool_name: 连接池名称
        **kwargs: 传递给 ConnectionPoolMonitor 构造函数的参数
        
    Returns:
        ConnectionPoolMonitor: 监控器实例
    """
    if pool_name not in _monitors:
        _monitors[pool_name] = ConnectionPoolMonitor(pool_name, **kwargs)
    return _monitors[pool_name]


def get_all_monitors() -> Dict[str, ConnectionPoolMonitor]:
    """获取所有监控器实例"""
    return _monitors.copy()


def get_all_health_status() -> Dict[str, Dict[str, Any]]:
    """获取所有连接池的健康状态"""
    return {
        name: monitor.get_health_status()
        for name, monitor in _monitors.items()
    }
