"""Shared utility functions used across the application."""

from __future__ import annotations

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)


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
                from app.core.ring_buffer import get_ring_log_buffer

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
            except Exception:
                pass
        return "\n".join(lines)


_metrics = MetricsCollector()


def get_metrics_collector() -> MetricsCollector:
    return _metrics
