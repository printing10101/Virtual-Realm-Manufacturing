"""产品 → 研究的问题反馈通道：把产品中遇到的真实问题反馈给研究模块。

两种反馈形式：
1. 自动反馈：产品在运行中检测到异常（识别失败、置信度低、超时）时自动调用
2. 主动反馈：用户点击"报告问题"按钮时调用
"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


class FeedbackToResearch:
    """问题反馈通道（单例）。"""

    _instance: Optional["FeedbackToResearch"] = None
    DEFAULT_REGISTRY_PATH = "research/shared/problem_registry/registry.jsonl"

    def __init__(self, registry_path: Optional[str] = None):
        self._registry_path = Path(registry_path or self.DEFAULT_REGISTRY_PATH)
        self._registry_path.parent.mkdir(parents=True, exist_ok=True)

    @classmethod
    def get_instance(cls) -> "FeedbackToResearch":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def report(
        self,
        feature: str,
        problem_type: str,
        description: str,
        sample_id: Optional[str] = None,
        context: Optional[dict] = None,
        priority: str = "normal",
    ) -> str:
        """反馈一个问题到研究模块。

        返回 ticket_id。
        """
        ticket_id = f"PRB-{datetime.now().strftime('%Y%m%d%H%M%S%f')[:17]}"
        record = {
            "ticket_id": ticket_id,
            "feature": feature,
            "problem_type": problem_type,
            "description": description,
            "sample_id": sample_id,
            "context": context or {},
            "priority": priority,
            "status": "open",
            "created_at": datetime.now().isoformat(),
        }
        try:
            with open(self._registry_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False))
                f.write("\n")
            logger.info("feedback_to_research ticket=%s feature=%s", ticket_id, feature)
        except Exception as e:  # noqa: BLE001
            logger.warning("feedback_write_failed err=%s", e)
        return ticket_id

    def count_open(self, feature: Optional[str] = None) -> int:
        """统计未关闭的工单数。"""
        if not self._registry_path.exists():
            return 0
        cnt = 0
        try:
            with open(self._registry_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    rec = json.loads(line)
                    if rec.get("status") == "open":
                        if feature is None or rec.get("feature") == feature:
                            cnt += 1
        except Exception:  # noqa: BLE001
            return -1
        return cnt


__all__ = ["FeedbackToResearch"]
