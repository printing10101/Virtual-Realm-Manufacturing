"""
熔断器模式实现

提供服务健康检查、自动熔断、半开状态探测等机制，防止级联故障。
"""

import time
import threading
from enum import Enum
from typing import Callable, Any, Optional
from dataclasses import dataclass
from datetime import datetime, timedelta

from .exceptions import CircuitBreakerOpenException, CircuitBreakerHalfOpenException


class CircuitState(Enum):
    """熔断器状态"""
    CLOSED = "closed"       # 闭合：正常调用
    OPEN = "open"           # 打开：拒绝调用
    HALF_OPEN = "half_open" # 半开：健康探测


@dataclass
class CircuitBreakerConfig:
    """熔断器配置"""
    failure_threshold: int = 5          # 连续失败次数阈值
    recovery_timeout: float = 30        # 熔断恢复超时 (秒)
    half_open_max_calls: int = 3        # 半开状态最大探测次数
    success_threshold: int = 2          # 半开成功后恢复次数


class CircuitBreaker:
    """
    熔断器实现
    
    用法示例:
        cb = CircuitBreaker("llm_service", CircuitBreakerConfig())
        cb.execute(lambda: call_ai_service())
    
    状态流转:
        CLOSED -> (失败>= threshold) -> OPEN
        OPEN -> (等待 recovery_timeout) -> HALF_OPEN
        HALF_OPEN -> (成功>= threshold) -> CLOSED
        HALF_OPEN -> (失败) -> OPEN
    """
    
    def __init__(
        self,
        name: str,
        config: Optional[CircuitBreakerConfig] = None,
        fallback: Optional[Callable[[Exception], Any]] = None,
    ):
        self.name = name
        self.config = config or CircuitBreakerConfig()
        self.fallback = fallback
        
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time: Optional[datetime] = None
        self._opened_at: Optional[datetime] = None
        self._last_success_time: Optional[datetime] = None
        self._lock = threading.RLock()
    
    @property
    def state(self) -> CircuitState:
        """获取当前状态，如果处于 OPEN 状态且超时，自动进入 HALF_OPEN"""
        with self._lock:
            if self._state == CircuitState.OPEN and self._is_recovery_timeout_expired():
                self._state = CircuitState.HALF_OPEN
                self._success_count = 0
        return self._state
    
    @property
    def is_available(self) -> bool:
        """服务是否可用（不包括半开探测中）"""
        return self.state in (CircuitState.CLOSED, CircuitState.HALF_OPEN)
    
    def _is_recovery_timeout_expired(self) -> bool:
        """是否已达到恢复超时时间"""
        if not self._opened_at:
            return False
        return datetime.now() - self._opened_at > timedelta(seconds=self.config.recovery_timeout)
    
    def _record_success(self):
        """记录成功调用"""
        with self._lock:
            self._failure_count = 0
            
            if self.state == CircuitState.HALF_OPEN:
                self._success_count += 1
                self._last_success_time = datetime.now()
                
                if self._success_count >= self.config.success_threshold:
                    self._transition_to_closed()
            else:
                self._last_success_time = datetime.now()
    
    def _record_failure(self, exception: Exception):
        """记录失败调用"""
        with self._lock:
            self._failure_count += 1
            self._last_failure_time = datetime.now()
            
            if self.state == CircuitState.HALF_OPEN:
                # 半开状态下失败，直接回到 OPEN 状态
                self._transition_to_open()
            elif self._failure_count >= self.config.failure_threshold:
                # 连续失败达到阈值，熔断
                self._transition_to_open()
    
    def _transition_to_open(self):
        """转换到 OPEN 状态"""
        self._state = CircuitState.OPEN
        self._opened_at = datetime.now()
        self._success_count = 0
    
    def _transition_to_closed(self):
        """转换到 CLOSED 状态"""
        self._state = CircuitState.CLOSED
        self._opened_at = None
        self._failure_count = 0
    
    def _transition_to_half_open(self):
        """转换到 HALF_OPEN 状态"""
        self._state = CircuitState.HALF_OPEN
        self._success_count = 0
    
    def execute(self, func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        """
        执行受保护的服务调用
        
        如果熔断器打开，则调用 fallback 或抛出异常
        如果服务调用成功，记录成功
        如果服务调用失败，记录失败
        
        Args:
            func: 需要熔断保护的可调用函数
            *args: 函数参数
            **kwargs: 函数关键字参数
            
        Returns:
            函数执行结果
            
        Raises:
            CircuitBreakerOpenException: 熔断器已打开，拒绝调用
            Exception: 函数执行失败，但已记录
        """
        with self._lock:
            current_state = self.state
            
            if current_state == CircuitState.OPEN:
                raise exceptions.CircuitBreakerOpenException(
                    service=self.name,
                    opened_at=self._opened_at.isoformat() if self._opened_at else None,
                )
        
        try:
            result = func(*args, **kwargs)
            self._record_success()
            return result
        except Exception as e:
            self._record_failure(e)
            
            # 调用 fallback
            if self.fallback and isinstance(e, Exception):
                return self.fallback(e)
            
            raise
    
    def reset(self):
        """重置熔断器状态"""
        with self._lock:
            self._state = CircuitState.CLOSED
            self._failure_count = 0
            self._success_count = 0
            self._opened_at = None
            self._last_failure_time = None
            self._last_success_time = None
    
    def get_status(self) -> dict:
        """获取熔断器状态信息"""
        with self._lock:
            return {
                "name": self.name,
                "state": self.state.value,
                "failure_count": self._failure_count,
                "success_count": self._success_count,
                "failure_threshold": self.config.failure_threshold,
                "last_failure_time": self._last_failure_time.isoformat() if self._last_failure_time else None,
                "opened_at": self._opened_at.isoformat() if self._opened_at else None,
            }


class CircuitBreakerRegistry:
    """
    熔断器注册中心
    
    提供全局熔断器管理，按服务名缓存实例
    """
    
    _instance: Optional["CircuitBreakerRegistry"] = None
    _lock = threading.Lock()
    
    def __new__(cls) -> "CircuitBreakerRegistry":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._breakers: dict[str, CircuitBreaker] = {}
        return cls._instance
    
    def get_or_create(
        self,
        name: str,
        config: Optional[CircuitBreakerConfig] = None,
        fallback: Optional[Callable[[Exception], Any]] = None,
    ) -> CircuitBreaker:
        """获取或创建设备名的熔断器"""
        if name not in self._breakers:
            # 双重检查锁
            with self._lock:
                if name not in self._breakers:
                    self._breakers[name] = CircuitBreaker(
                        name=name,
                        config=config,
                        fallback=fallback,
                    )
        return self._breakers[name]
    
    def get(self, name: str) -> Optional[CircuitBreaker]:
        """获取指定服务名的熔断器"""
        return self._breakers.get(name)
    
    def reset_all(self):
        """重置所有熔断器"""
        for breaker in self._breakers.values():
            breaker.reset()
    
    def get_all_status(self) -> dict[str, dict]:
        """获取所有熔断器状态"""
        return {name: breaker.get_status() for name, breaker in self._breakers.items()}


# ========================================
# 快捷上下文管理器
# ========================================

from typing import ContextManager
from contextlib import contextmanager


@contextmanager
def circuit_breaker_context(
    name: str,
    config: Optional[CircuitBreakerConfig] = None,
    fallback: Optional[Callable[[Exception], Any]] = None,
) -> ContextManager[CircuitBreaker]:
    """
    熔断器上下文管理器
    
    用法:
        with circuit_breaker_context("llm_service") as cb:
            result = cb.execute(lambda: call_ai())
    """
    registry = CircuitBreakerRegistry()
    breaker = registry.get_or_create(name, config, fallback)
    try:
        yield breaker
    except:
        raise
    finally:
        pass
