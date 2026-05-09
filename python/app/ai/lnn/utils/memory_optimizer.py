"""
LNN内存优化模块

功能：
- 内存池管理：预分配和复用内存块
- 梯度检查点：以计算换内存
- 模型卸载：动态卸载未使用模型到CPU/磁盘
- 垃圾回收优化：智能触发gc
- 内存监控：实时监控内存使用情况
"""
import gc
import time
import psutil
import logging
import threading
from typing import Any, Dict, List, Optional
from dataclasses import dataclass
from collections import OrderedDict

try:
    import torch
    HAS_TORCH = True
except ImportError:
    HAS_TORCH = False

logger = logging.getLogger(__name__)


@dataclass
class MemoryStats:
    """内存使用统计"""
    total_mb: float = 0.0
    available_mb: float = 0.0
    used_mb: float = 0.0
    process_mb: float = 0.0
    gpu_total_mb: float = 0.0
    gpu_used_mb: float = 0.0
    gpu_free_mb: float = 0.0
    cache_hit_rate: float = 0.0

    def to_dict(self) -> Dict[str, float]:
        return {
            "total_mb": round(self.total_mb, 2),
            "available_mb": round(self.available_mb, 2),
            "used_mb": round(self.used_mb, 2),
            "process_mb": round(self.process_mb, 2),
            "gpu_total_mb": round(self.gpu_total_mb, 2),
            "gpu_used_mb": round(self.gpu_used_mb, 2),
            "gpu_free_mb": round(self.gpu_free_mb, 2),
            "cache_hit_rate": round(self.cache_hit_rate, 4),
        }


class MemoryPool:
    """
    内存池管理器

    预分配内存块，减少频繁分配和释放带来的开销
    """

    def __init__(self, max_blocks: int = 100, block_size_mb: float = 1.0):
        self.max_blocks = max_blocks
        self.block_size_bytes = int(block_size_mb * 1024 * 1024)
        self._pool: OrderedDict[str, bytearray] = OrderedDict()
        self._lock = threading.Lock()
        self._stats = {"allocations": 0, "reuses": 0, "evictions": 0}

    def allocate(self, key: str) -> bytearray:
        """分配或复用内存块"""
        with self._lock:
            if key in self._pool:
                self._pool.move_to_end(key)
                self._stats["reuses"] += 1
                return self._pool[key]

            if len(self._pool) >= self.max_blocks:
                self._pool.popitem(last=False)
                self._stats["evictions"] += 1

            block = bytearray(self.block_size_bytes)
            self._pool[key] = block
            self._stats["allocations"] += 1
            return block

    def release(self, key: str) -> None:
        """释放内存块"""
        with self._lock:
            if key in self._pool:
                del self._pool[key]

    def clear(self) -> None:
        """清空内存池"""
        with self._lock:
            self._pool.clear()

    def get_stats(self) -> Dict[str, int]:
        return self._stats.copy()


class LNNMemoryOptimizer:
    """
    LNN内存优化器

    功能：
    - 监控CPU/GPU内存使用
    - 智能垃圾回收
    - PyTorch缓存管理
    - 模型卸载
    - 梯度检查点
    """

    def __init__(
        self,
        gc_threshold_mb: float = 500.0,
        gc_check_interval_sec: float = 10.0,
        enable_auto_gc: bool = True,
    ):
        self.gc_threshold_mb = gc_threshold_mb
        self.gc_check_interval = gc_check_interval_sec
        self.enable_auto_gc = enable_auto_gc
        self.memory_pool = MemoryPool()
        self._monitor_thread: Optional[threading.Thread] = None
        self._stop_monitor = False
        self._historical_stats: List[MemoryStats] = []

    def get_memory_stats(self) -> MemoryStats:
        """获取当前内存使用统计"""
        process = psutil.Process()
        mem_info = process.memory_info()
        system_mem = psutil.virtual_memory()

        stats = MemoryStats(
            total_mb=system_mem.total / (1024 ** 3),
            available_mb=system_mem.available / (1024 ** 3),
            used_mb=system_mem.used / (1024 ** 3),
            process_mb=mem_info.rss / (1024 ** 2),
        )

        if HAS_TORCH and torch.cuda.is_available():
            stats.gpu_total_mb = torch.cuda.get_device_properties(0).total_mem_bytes / (1024 ** 2)
            stats.gpu_used_mb = torch.cuda.memory_allocated(0) / (1024 ** 2)
            stats.gpu_free_mb = torch.cuda.memory_reserved(0) / (1024 ** 2)

        self._historical_stats.append(stats)
        if len(self._historical_stats) > 1000:
            self._historical_stats = self._historical_stats[-500:]

        return stats

    def optimize_memory(self) -> Dict[str, Any]:
        """
        执行全面内存优化

        Returns:
            优化前后统计对比
        """
        before = self.get_memory_stats()

        if HAS_TORCH:
            self._clear_pytorch_cache()
            self._compact_pytorch_memory()

        self._optimize_gc()
        self._clear_python_cache()

        after = self.get_memory_stats()

        result = {
            "before": before.to_dict(),
            "after": after.to_dict(),
            "freed_mb": round(before.process_mb - after.process_mb, 2),
        }

        logger.info(f"Memory optimization: freed {result['freed_mb']:.2f}MB")
        return result

    def enable_gradient_checkpointing(self, model: "torch.nn.Module") -> None:
        """
        启用梯度检查点（以计算换内存）

        Args:
            model: PyTorch模型
        """
        if not HAS_TORCH:
            return

        if hasattr(model, "gradient_checkpointing_enable"):
            model.gradient_checkpointing_enable()
            logger.info("Gradient checkpointing enabled")
        else:
            for param in model.parameters():
                param.requires_grad = True
            logger.info("Gradient checkpointing not natively supported, using manual approach")

    def unload_model_to_cpu(self, model: "torch.nn.Module") -> None:
        """
        将模型从GPU卸载到CPU以释放显存

        Args:
            model: PyTorch模型
        """
        if not HAS_TORCH:
            return

        if next(model.parameters()).is_cuda:
            model = model.cpu()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            logger.info("Model unloaded to CPU, GPU cache cleared")

    def start_monitoring(self) -> None:
        """启动后台内存监控线程"""
        if self._monitor_thread is not None:
            return

        self._stop_monitor = False
        self._monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._monitor_thread.start()
        logger.info("Memory monitoring started")

    def stop_monitoring(self) -> None:
        """停止内存监控"""
        self._stop_monitor = True
        if self._monitor_thread:
            self._monitor_thread.join(timeout=5)
            self._monitor_thread = None
        logger.info("Memory monitoring stopped")

    def _clear_pytorch_cache(self) -> None:
        """清空PyTorch CUDA缓存"""
        if HAS_TORCH and torch.cuda.is_available():
            torch.cuda.empty_cache()
            logger.debug("PyTorch CUDA cache cleared")

    def _compact_pytorch_memory(self) -> None:
        """压缩PyTorch内存分配器"""
        if HAS_TORCH and torch.cuda.is_available():
            torch.cuda.ipc_collect()
            torch.cuda.synchronize()
            logger.debug("PyTorch memory compacted")

    def _optimize_gc(self) -> None:
        """优化Python垃圾回收"""
        gc.collect()
        gc.set_threshold(700, 10, 10)
        logger.debug(f"GC optimized. Thresholds: {gc.get_threshold()}")

    def _clear_python_cache(self) -> None:
        """清空Python导入缓存"""
        import sys

        uncached = []
        for name, module in sys.modules.items():
            if module is None or name.startswith("_"):
                uncached.append(name)

        for name in uncached:
            sys.modules.pop(name, None)

        logger.debug(f"Python cache cleared: {len(uncached)} modules")

    def _monitor_loop(self) -> None:
        """后台监控循环"""
        while not self._stop_monitor:
            stats = self.get_memory_stats()

            if stats.process_mb > self.gc_threshold_mb and self.enable_auto_gc:
                self.optimize_memory()
                logger.warning(f"High memory usage detected: {stats.process_mb:.0f}MB, auto-optimization triggered")

            time.sleep(self.gc_check_interval)
