"""Shared utility functions used across the application."""

from __future__ import annotations

import json
import logging
import uuid
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


# ============================================================
# 集中式路径管理 - 消除各模块重复的路径定义
# ============================================================


def get_project_root() -> Path:
    """获取项目根目录（python/ 的上一级）。"""
    return Path(__file__).resolve().parent.parent.parent.parent


def get_output_dir(module_name: str) -> Path:
    """获取模块专属的输出目录，自动创建。

    Args:
        module_name: 模块名，如 'dxf_import', 'step_import', 'projects'

    Returns:
        已创建的输出目录路径
    """
    output_dir = get_project_root() / "output" / module_name
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


def get_upload_dir(module_name: str) -> Path:
    """获取模块专属的临时上传目录，自动创建。

    Args:
        module_name: 模块名

    Returns:
        已创建的上传临时目录路径
    """
    upload_dir = get_output_dir(module_name) / "_uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)
    return upload_dir


def make_temp_path(upload_dir: Path, prefix: str, suffix: str) -> Path:
    """生成唯一的临时文件路径。

    Args:
        upload_dir: 上传目录
        prefix: 文件名前缀
        suffix: 文件扩展名（含点号，如 '.dxf'）

    Returns:
        唯一的临时文件路径
    """
    unique_id = uuid.uuid4().hex[:12]
    return upload_dir / f"{prefix}_{unique_id}{suffix}"


def cleanup_temp_file(temp_path: Path) -> None:
    """安全清理临时文件，失败时记录日志但不抛出异常。

    Args:
        temp_path: 要删除的临时文件路径
    """
    try:
        temp_path.unlink(missing_ok=True)
    except OSError as cleanup_err:
        logger.debug(
            "临时文件清理失败 %s: %s", temp_path, cleanup_err, exc_info=True
        )


# ============================================================
# 路径安全工具函数 - 防止路径遍历攻击
# ============================================================

def safe_file_path(user_input: str, base_dir: str) -> Path:
    """验证文件路径，防止目录遍历攻击。

    安全校验逻辑:
        1. 将基础目录和用户输入都解析为绝对路径
        2. 验证目标路径必须在基础目录内
        3. 拒绝任何试图通过 '../' 等序列逃逸基础目录的路径

    Args:
        user_input: 用户提供的文件路径（可能是相对路径）
        base_dir: 允许访问的基础目录（绝对路径）

    Returns:
        验证通过的安全路径

    Raises:
        ValueError: 路径遍历检测失败时抛出
    """
    base = Path(base_dir).resolve()
    target = (base / user_input).resolve()

    # 核心校验：目标路径必须在基础目录内
    if not str(target).startswith(str(base)):
        logger.warning(
            "路径遍历检测: 用户输入 '%s' 试图访问基础目录 '%s' 之外的路径 '%s'",
            user_input, base_dir, target
        )
        raise ValueError("非法的文件路径: 路径遍历被拒绝")

    return target


def safe_open(file_path: str, base_dir: str, mode: str = 'r', **kwargs):
    """安全文件打开，防止路径遍历攻击。

    在打开文件前验证路径合法性，确保不会访问基础目录之外的文件。

    Args:
        file_path: 文件路径（可以是相对路径）
        base_dir: 允许访问的基础目录
        mode: 文件打开模式，默认 'r'
        **kwargs: 传递给 open() 的其他参数

    Returns:
        文件对象

    Raises:
        ValueError: 路径遍历检测失败时抛出
    """
    safe_path = safe_file_path(file_path, base_dir)
    return open(safe_path, mode, **kwargs)


def extract_json_from_markdown(content: str) -> dict[str, Any]:
    """Extract JSON from LLM response that may contain markdown code blocks.

    Handles ```json, ```, and ```gcode code fences,
    falling back to raw content if no fence is found.

    Returns:
        Parsed JSON dict. Returns empty dict on parse failure.
    """
    text = content.strip()
    if "```json" in text:
        text = text.split("```json")[1].split("```")[0].strip()
    elif "```gcode" in text:
        text = text.split("```gcode")[1].split("```")[0].strip()
    elif "```" in text:
        text = text.split("```")[1].split("```")[0].strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        logger.warning("JSON parse failed from markdown content: %s", e)
        return {}


def flatten_documents(documents: Any) -> list[str]:
    """Flatten knowledge base document results into a list of strings.

    Compatible with:
      - ChromaDB nested: [[doc1, doc2]] -> ["doc1", "doc2"]
      - Flat list: [doc1, doc2] -> ["doc1", "doc2"]

    Returns empty list for None or empty input.
    """
    if not isinstance(documents, list) or not documents:
        return []
    if isinstance(documents[0], list):
        return [str(d) for d in documents[0]]
    if isinstance(documents[0], str):
        return [str(d) for d in documents]
    return [str(d) for d in documents]


def format_bytes(size_bytes: int) -> str:
    """Format byte count as human-readable string."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    if size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.2f} KB"
    if size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.2f} MB"
    return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"


class MetricsCollector:
    """Thread-safe metrics collector for Prometheus-style exposition."""

    _INFERENCE_BUCKETS = (
        0.001,
        0.005,
        0.01,
        0.025,
        0.05,
        0.1,
        0.25,
        0.5,
        1.0,
        2.5,
        5.0,
        10.0,
        float("inf"),
    )
    _MODEL_LOAD_BUCKETS = (0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0, float("inf"))

    def __init__(self):
        from threading import Lock
        from time import time as _time

        self._lock = Lock()
        self._start_time = _time()
        self._request_count = 0
        self._request_latency: dict[str, list[float]] = {}
        self._max_latency_entries = 1000

        self._lnn_inference_duration: dict[str, list[float]] = {}
        self._lnn_model_load_duration: dict[str, list[float]] = {}
        self._lnn_prediction_count: dict[str, dict[str, int]] = {}
        self._agent_requests_total: dict[str, dict[str, int]] = {}
        self._active_training_tasks = 0

    def record(self, path: str, elapsed: float):
        with self._lock:
            self._request_count += 1
            latencies = self._request_latency.setdefault(path, [])
            latencies.append(elapsed)
            if len(latencies) > self._max_latency_entries:
                latencies[:] = latencies[-self._max_latency_entries :]

    def record_lnn_inference(self, model_name: str, duration_sec: float):
        with self._lock:
            times = self._lnn_inference_duration.setdefault(model_name, [])
            times.append(duration_sec)
            if len(times) > self._max_latency_entries:
                self._lnn_inference_duration[model_name] = times[
                    -self._max_latency_entries :
                ]

    def record_lnn_model_load(self, model_name: str, duration_sec: float):
        with self._lock:
            times = self._lnn_model_load_duration.setdefault(model_name, [])
            times.append(duration_sec)
            if len(times) > 200:
                self._lnn_model_load_duration[model_name] = times[-200:]

    def record_lnn_prediction(self, model_name: str, status: str = "success"):
        with self._lock:
            model_counts = self._lnn_prediction_count.setdefault(model_name, {})
            model_counts[status] = model_counts.get(status, 0) + 1

    def record_agent_request(self, permission: str, status: str):
        with self._lock:
            perm_counts = self._agent_requests_total.setdefault(permission, {})
            perm_counts[status] = perm_counts.get(status, 0) + 1

    def set_active_training_tasks(self, count: int):
        with self._lock:
            self._active_training_tasks = count

    def _format_histogram(
        self,
        name: str,
        help_text: str,
        label_name: str,
        data: dict[str, list[float]],
        buckets: tuple,
    ) -> list[str]:
        lines = [f"# HELP {name} {help_text}", f"# TYPE {name} histogram"]
        for label_val, values in data.items():
            if not values:
                continue
            bucket_counts = {b: 0.0 for b in buckets}
            for v in values:
                for b in buckets:
                    if v <= b:
                        bucket_counts[b] += 1
            cum = 0.0
            for b in buckets:
                cum += bucket_counts[b]
                label = "+Inf" if b == float("inf") else str(b)
                lines.append(
                    f'{name}_bucket{{{label_name}="{label_val}",le="{label}"}} {cum:.0f}'
                )
            total = sum(values)
            count = len(values)
            lines.append(f'{name}_sum{{{label_name}="{label_val}"}} {total:.6f}')
            lines.append(f'{name}_count{{{label_name}="{label_val}"}} {count}')
        return lines

    def _format_counter_by_label(
        self,
        name: str,
        help_text: str,
        label_name: str,
        data: dict[str, dict[str, int]],
    ) -> list[str]:
        lines = [f"# HELP {name} {help_text}", f"# TYPE {name} counter"]
        for label_val, status_counts in data.items():
            for status, count in status_counts.items():
                lines.append(
                    f'{name}{{{label_name}="{label_val}",status="{status}"}} {count}'
                )
        return lines

    def export(self) -> str:
        from time import time as _time
        import psutil as _psutil

        lines = [
            "# HELP app_uptime_seconds Application uptime in seconds",
            "# TYPE app_uptime_seconds counter",
            f"app_uptime_seconds {_time() - self._start_time:.0f}",
            "",
            "# HELP sidecar_uptime_seconds Sidecar process uptime in seconds",
            "# TYPE sidecar_uptime_seconds gauge",
            f"sidecar_uptime_seconds {_time() - self._start_time:.0f}",
            "",
            "# HELP process_resident_memory_bytes Resident memory size in bytes",
            "# TYPE process_resident_memory_bytes gauge",
            f"process_resident_memory_bytes {_psutil.Process().memory_info().rss}",
            "",
            "# HELP process_cpu_percent Process CPU usage percentage",
            "# TYPE process_cpu_percent gauge",
            f"process_cpu_percent {_psutil.Process().cpu_percent():.1f}",
            "",
            "# HELP http_requests_total Total number of HTTP requests",
            "# TYPE http_requests_total counter",
            f'http_requests_total{{method="total"}} {self._request_count}',
            "",
            "# HELP http_request_duration_seconds HTTP request duration in seconds",
            "# TYPE http_request_duration_seconds histogram",
        ]
        with self._lock:
            for path, latencies in self._request_latency.items():
                if latencies:
                    avg = sum(latencies) / len(latencies)
                    lines.append(
                        f'http_request_duration_seconds_bucket{{path="{path}",le="+Inf"}} {avg:.4f}'
                    )
            lines.append("")
            lines.extend(
                self._format_histogram(
                    "lnn_inference_duration_seconds",
                    "LNN model inference duration in seconds",
                    "model",
                    self._lnn_inference_duration,
                    self._INFERENCE_BUCKETS,
                )
            )
            lines.append("")
            lines.extend(
                self._format_histogram(
                    "lnn_model_load_duration_seconds",
                    "LNN model load duration in seconds",
                    "model",
                    self._lnn_model_load_duration,
                    self._MODEL_LOAD_BUCKETS,
                )
            )
            lines.append("")
            lines.extend(
                self._format_counter_by_label(
                    "lnn_prediction_count",
                    "Total LNN predictions by model and status",
                    "model",
                    self._lnn_prediction_count,
                )
            )
            lines.append("")
            lines.extend(
                self._format_counter_by_label(
                    "agent_requests_total",
                    "Total agent API requests by permission and status",
                    "permission",
                    self._agent_requests_total,
                )
            )
            lines.append("")
            lines.append(
                "# HELP lnn_active_training_tasks Current number of active training tasks"
            )
            lines.append("# TYPE lnn_active_training_tasks gauge")
            lines.append(f"lnn_active_training_tasks {self._active_training_tasks}")
            lines.append("")
            try:
                from app.utils.ring_buffer import get_ring_log_buffer

                rlb = get_ring_log_buffer()
                buf_stats = rlb.stats()
                lines.append(
                    "# HELP ring_buffer_entries Number of entries in ring buffer"
                )
                lines.append("# TYPE ring_buffer_entries gauge")
                for buf_type in buf_stats["buffers"]:
                    s = buf_stats["buffers"][buf_type]
                    lines.append(
                        f'ring_buffer_entries{{type="{buf_type}"}} {s["size"]}'
                    )
                    lines.append(
                        f'ring_buffer_capacity{{type="{buf_type}"}} {s["capacity"]}'
                    )
                    lines.append(
                        f'ring_buffer_appended_total{{type="{buf_type}"}} {s["total_appended"]}'
                    )
                    lines.append(
                        f'ring_buffer_dropped_total{{type="{buf_type}"}} {s["total_dropped"]}'
                    )
            except (AttributeError, TypeError, ValueError) as metric_err:
                # 单个 ring buffer 指标格式化失败不应阻塞其他指标输出
                logger.debug(
                    "Failed to format ring buffer metrics for type %s: %s",
                    buf_type,
                    metric_err,
                    exc_info=True,
                )
        return "\n".join(lines)


_metrics = MetricsCollector()


def get_metrics_collector() -> MetricsCollector:
    return _metrics
