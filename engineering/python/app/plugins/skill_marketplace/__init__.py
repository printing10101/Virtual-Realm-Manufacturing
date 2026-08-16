"""Skill marketplace plugin module.

占位模块：提供 get_marketplace() 返回 stub 实例，避免 import 失败。
后续填充真实实现时替换 stub 类即可。
"""

from __future__ import annotations

from typing import Any


class _StubMarketplace:
    """占位 marketplace，所有方法返回空结果。"""

    def get_stats(self) -> dict[str, Any]:
        return {"total": 0, "published": 0, "downloaded": 0}

    def list_available(self, tag: str | None = None) -> list[dict[str, Any]]:
        return []

    def search(self, query: str) -> list[dict[str, Any]]:
        return []

    def publish(self, skill_id: str, author: str) -> dict[str, Any]:
        return {"skill_id": skill_id, "status": "stub_published"}

    def download(self, skill_id: str, level: str, target_sub_id: str | None = None) -> dict[str, Any]:
        return {"skill_id": skill_id, "status": "stub_downloaded"}

    def rate_skill(self, skill_id: str, rating: float, agent_id: str = "") -> dict[str, Any]:
        return {"skill_id": skill_id, "rating": rating, "status": "stub_rated"}

    def unpublish(self, skill_id: str) -> bool:
        return True


_marketplace_instance = _StubMarketplace()


def get_marketplace() -> _StubMarketplace:
    """返回 marketplace 单例（当前为 stub）。"""
    return _marketplace_instance
