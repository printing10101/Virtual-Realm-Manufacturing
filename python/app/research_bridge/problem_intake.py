"""问题工单：用户在产品中点击"报告问题"时调用。

这个工单同时落到：
1. data/bridge/error_samples/user_reports.jsonl（产品日志）
2. research/shared/problem_registry/registry.jsonl（研究工单池）

研究模块会从 registry.jsonl 里挑优先级。
"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class ProblemIntake:
    """用户问题工单入口。"""

    _instance: Optional["ProblemIntake"] = None

    def __init__(
        self,
        product_log: str = "data/bridge/error_samples/user_reports.jsonl",
        research_registry: str = "research/shared/problem_registry/registry.jsonl",
    ):
        self._product_log = Path(product_log)
        self._research_registry = Path(research_registry)
        self._product_log.parent.mkdir(parents=True, exist_ok=True)
        self._research_registry.parent.mkdir(parents=True, exist_ok=True)

    @classmethod
    def get_instance(cls) -> "ProblemIntake":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def submit(
        self,
        title: str,
        description: str,
        category: str = "general",
        severity: str = "medium",
        user_id: Optional[str] = None,
        context: Optional[dict] = None,
    ) -> str:
        """提交一个问题工单。

        返回工单 ID。
        """
        ticket_id = f"INTK-{datetime.now().strftime('%Y%m%d%H%M%S%f')[:17]}"
        record = {
            "ticket_id": ticket_id,
            "title": title,
            "description": description,
            "category": category,
            "severity": severity,
            "user_id_hash": _quick_hash(user_id),
            "context": context or {},
            "created_at": datetime.now().isoformat(),
            "status": "open",
        }
        self._append(self._product_log, record)
        # 同时写一份到研究侧（脱敏版本）
        research_record = {**record, "user_id": "[ANON]"}
        self._append(self._research_registry, research_record)
        logger.info("problem_intake ticket=%s category=%s severity=%s", ticket_id, category, severity)
        return ticket_id

    def _append(self, path: Path, record: dict) -> None:
        try:
            with open(path, "a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False))
                f.write("\n")
        except (OSError, IOError, ValueError, TypeError) as e:
            logger.warning("intake_append_failed path=%s err=%s", path, e)


def _quick_hash(s: Optional[str]) -> str:
    import hashlib

    if not s:
        return ""
    return hashlib.sha256(s.encode("utf-8")).hexdigest()[:12]


__all__ = ["ProblemIntake"]
