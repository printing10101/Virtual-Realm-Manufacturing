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

    def __init__(self):
        from threading import Lock
        from time import time as _time
        self._lock = Lock()
        self._start_time = _time()
        self._request_count = 0
        self._request_latency: dict[str, list[float]] = {}
        self._max_latency_entries = 1000

    def record(self, path: str, elapsed: float):
        with self._lock:
            self._request_count += 1
            latencies = self._request_latency.setdefault(path, [])
            latencies.append(elapsed)
            if len(latencies) > self._max_latency_entries:
                latencies[:] = latencies[-self._max_latency_entries:]

    def export(self) -> str:
        from time import time as _time
        lines = [
            "# HELP app_uptime_seconds Application uptime in seconds",
            "# TYPE app_uptime_seconds counter",
            f"app_uptime_seconds {_time() - self._start_time:.0f}",
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
        return "\n".join(lines)


_metrics = MetricsCollector()


def get_metrics_collector() -> MetricsCollector:
    return _metrics