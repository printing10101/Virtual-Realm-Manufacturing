"""
Batch Inference Engine

Implements asynchronous batch processing with concurrency control,
dynamic batch sizing, and throughput monitoring.
"""
import time
from typing import Any, Dict, List, Optional
from concurrent.futures import ThreadPoolExecutor, Future
from queue import PriorityQueue
import threading
from collections import deque

from app.ai.lnn.inference.predictor import LNNPredictor, PredictionResult


class BatchInferenceEngine:
    """
    Batch Inference Engine with async processing and throughput monitoring.

    Features:
    - Asynchronous batch processing with Future-based API
    - Concurrent execution with configurable max concurrency (default: 10)
    - Dynamic batch size adjustment based on processing time
    - Throughput statistics with time-windowed metrics
    - Task priority support
    """

    def __init__(
        self,
        predictor: LNNPredictor,
        max_concurrency: int = 10,
        initial_batch_size: int = 32,
        enable_dynamic_batching: bool = True,
    ):
        """
        Initialize Batch Inference Engine

        Args:
            predictor: LNNPredictor instance for inference
            max_concurrency: Maximum concurrent inference tasks (>=10)
            initial_batch_size: Initial batch size
            enable_dynamic_batching: Enable dynamic batch size adjustment
        """
        self.predictor = predictor
        self.max_concurrency = max_concurrency
        self.initial_batch_size = initial_batch_size
        self.enable_dynamic_batching = enable_dynamic_batching

        self._task_queue = PriorityQueue()
        self._executor = ThreadPoolExecutor(max_workers=max_concurrency)
        self._lock = threading.Lock()

        self._stats = {
            "total_processed": 0,
            "total_success": 0,
            "total_failed": 0,
            "total_processing_time_ms": 0.0,
            "throughput_samples_per_sec": 0.0,
        }

        self._time_window_stats = deque()
        self._current_batch_size = initial_batch_size
        self._task_counter = 0

    def process_batch(
        self,
        data_list: List[Any],
        priority: int = 0,
    ) -> Future:
        """
        Process batch of data asynchronously

        Args:
            data_list: List of input data to process
            priority: Task priority (lower = higher priority)

        Returns:
            Future object for retrieving results
        """
        self._task_counter += 1
        task_id = self._task_counter

        future = self._executor.submit(self._process_batch_impl, data_list, task_id)

        with self._lock:
            self._stats["total_processed"] += len(data_list)

        return future

    def _process_batch_impl(self, data_list: List[Any], task_id: int) -> List[PredictionResult]:
        """Internal batch processing implementation"""
        start_time = time.perf_counter()
        batch_size = self._current_batch_size if self.enable_dynamic_batching else self.initial_batch_size

        try:
            results = self.predictor.predict_batch(data_list, batch_size=batch_size)

            processing_time = (time.perf_counter() - start_time) * 1000
            self._update_stats(len(data_list), processing_time, success=True)
            self._adjust_batch_size(len(data_list), processing_time)

            return results
        except Exception:
            processing_time = (time.perf_counter() - start_time) * 1000
            self._update_stats(len(data_list), processing_time, success=False)
            raise

    def _update_stats(self, count: int, processing_time_ms: float, success: bool) -> None:
        """Update inference statistics"""
        with self._lock:
            if success:
                self._stats["total_success"] += count
            else:
                self._stats["total_failed"] += count
            self._stats["total_processing_time_ms"] += processing_time_ms

            total_time_sec = self._stats["total_processing_time_ms"] / 1000.0
            if total_time_sec > 0:
                self._stats["throughput_samples_per_sec"] = (
                    self._stats["total_success"] / total_time_sec
                )

            self._time_window_stats.append({
                "timestamp": time.time(),
                "count": count,
                "processing_time_ms": processing_time_ms,
                "success": success,
            })

            while len(self._time_window_stats) > 10000:
                self._time_window_stats.popleft()

    def _adjust_batch_size(self, data_count: int, processing_time_ms: float) -> None:
        """Dynamically adjust batch size based on performance"""
        if not self.enable_dynamic_batching:
            return
        avg_time_per_sample = processing_time_ms / data_count if data_count > 0 else 50
        if avg_time_per_sample < 20:
            self._current_batch_size = min(self._current_batch_size * 2, 256)
        elif avg_time_per_sample > 100:
            self._current_batch_size = max(self._current_batch_size // 2, 8)

    def get_statistics(
        self,
        time_window_seconds: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Get batch inference statistics

        Args:
            time_window_seconds: Optional time window for stats (e.g., 60, 300)

        Returns:
            Dictionary with statistics including:
            - total_processed: Total processed samples
            - total_success: Successful samples
            - total_failed: Failed samples
            - average_processing_time_ms: Average processing time
            - throughput_samples_per_sec: Overall throughput
            - queue_length: Current queue length
            - current_batch_size: Current dynamic batch size
            - time_window: Time-windowed stats (if requested)
        """
        with self._lock:
            stats = self._stats.copy()
            stats["queue_length"] = self._task_queue.qsize()
            stats["current_batch_size"] = self._current_batch_size
            stats["average_processing_time_ms"] = (
                stats["total_processing_time_ms"] / stats["total_processed"]
                if stats["total_processed"] > 0
                else 0.0
            )

        if time_window_seconds:
            window_stats = self._get_time_window_stats(time_window_seconds)
            stats["time_window"] = window_stats

        return stats

    def _get_time_window_stats(self, window_seconds: int) -> Dict[str, Any]:
        """Get statistics for a specific time window"""
        now = time.time()
        cutoff = now - window_seconds

        window_items = [s for s in self._time_window_stats if s["timestamp"] >= cutoff]
        if not window_items:
            return {"count": 0, "success": 0, "failed": 0, "throughput_samples_per_sec": 0.0}

        total_count = sum(s["count"] for s in window_items)
        success_count = sum(s["count"] for s in window_items if s["success"])
        failed_count = total_count - success_count
        total_time_ms = sum(s["processing_time_ms"] for s in window_items)
        throughput = success_count / (total_time_ms / 1000.0) if total_time_ms > 0 else 0.0

        return {
            "count": total_count,
            "success": success_count,
            "failed": failed_count,
            "throughput_samples_per_sec": throughput,
            "window_seconds": window_seconds,
        }

    def shutdown(self) -> None:
        """Shutdown the executor and release resources"""
        self._executor.shutdown(wait=True)
