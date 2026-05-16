"""刀具数据库模块。

提供刀具参数查询和检索功能。
覆盖立铣刀、车刀、钻头、丝锥等常用切削刀具。
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class ToolEntry:
    id: str
    name: str
    type: str
    subtype: str
    material: str
    diameter_range: list[float] = field(default_factory=lambda: [0, 0])
    flutes: int = 2
    rake_angle: float = 0
    clearance_angle: float = 0
    helix_angle: float = 0
    nose_radius: float = 0.0
    max_doc: float = 0.0
    cutting_speed_range: dict[str, list[float]] = field(default_factory=dict)
    feed_per_tooth_range: dict[str, list[float]] = field(default_factory=dict)
    max_cutting_force_n: float = 0
    tool_life_minutes: float = 60

    def get_cutting_speed_for_material(
        self,
        material_category: str,
    ) -> tuple[float, float]:
        r = self.cutting_speed_range.get(material_category)
        if r and len(r) >= 2:
            return (r[0], r[1])
        r = self.cutting_speed_range.get("steel")
        if r and len(r) >= 2:
            return (r[0], r[1])
        return (0.0, 0.0)

    def get_feed_per_tooth(
        self,
        operation: str = "roughing",
    ) -> tuple[float, float]:
        r = self.feed_per_tooth_range.get(operation)
        if r and len(r) >= 2:
            return (r[0], r[1])
        return (0.0, 0.0)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ToolEntry:
        return cls(
            id=data["id"],
            name=data["name"],
            type=data["type"],
            subtype=data.get("subtype", ""),
            material=data["material"],
            diameter_range=data.get("diameter_range", [0, 0]),
            flutes=data.get("flutes", 2),
            rake_angle=data.get("rake_angle", 0),
            clearance_angle=data.get("clearance_angle", 0),
            helix_angle=data.get("helix_angle", 0),
            nose_radius=data.get("nose_radius", 0.0),
            max_doc=data.get("max_doc", 0.0),
            cutting_speed_range=data.get("cutting_speed_range", {}),
            feed_per_tooth_range=data.get("feed_per_tooth_range", {}),
            max_cutting_force_n=data.get("max_cutting_force_n", 0),
            tool_life_minutes=data.get("tool_life_minutes", 60),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "type": self.type,
            "subtype": self.subtype,
            "material": self.material,
            "diameter_range": self.diameter_range,
            "flutes": self.flutes,
            "rake_angle": self.rake_angle,
            "clearance_angle": self.clearance_angle,
            "helix_angle": self.helix_angle,
            "nose_radius": self.nose_radius,
            "max_doc": self.max_doc,
            "cutting_speed_range": self.cutting_speed_range,
            "feed_per_tooth_range": self.feed_per_tooth_range,
            "max_cutting_force_n": self.max_cutting_force_n,
            "tool_life_minutes": self.tool_life_minutes,
        }


class ToolDatabase:
    def __init__(self, data_path: str | None = None) -> None:
        if data_path is None:
            data_dir = Path(__file__).resolve().parent / "data"
            data_path = str(data_dir / "tools.json")
        self._data_path = data_path
        self._tools: dict[str, ToolEntry] = {}
        self._load()

    def _load(self) -> None:
        with open(self._data_path, "r", encoding="utf-8") as f:
            raw = json.load(f)
        for item in raw:
            entry = ToolEntry.from_dict(item)
            self._tools[entry.id] = entry

    def get(self, tool_id: str) -> ToolEntry:
        if tool_id not in self._tools:
            available = ", ".join(self._tools.keys())
            raise KeyError(f"刀具 '{tool_id}' 不在数据库中。可用刀具: {available}")
        return self._tools[tool_id]

    def list_all(self) -> list[ToolEntry]:
        return sorted(self._tools.values(), key=lambda t: t.name)

    def list_ids(self) -> list[str]:
        return sorted(self._tools.keys())

    def filter_by_type(self, tool_type: str) -> list[ToolEntry]:
        return [t for t in self._tools.values() if t.type == tool_type]

    def filter_by_material(self, tool_material: str) -> list[ToolEntry]:
        return [t for t in self._tools.values() if t.material == tool_material]
