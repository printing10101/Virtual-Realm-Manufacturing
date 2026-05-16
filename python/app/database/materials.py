"""材料数据库模块。

提供材料参数查询和检索功能。
覆盖碳钢、合金钢、不锈钢、铝合金、钛合金、铸铁等常用机械加工材料。
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class MaterialCuttingRange:
    roughing: tuple[float, float]
    finishing: tuple[float, float]


@dataclass
class MaterialEntry:
    id: str
    name: str
    category: str
    hardness_hb: float
    tensile_strength_mpa: float
    thermal_conductivity: float
    density_gcm3: float = 7.85
    specific_cutting_force: float = 2000
    cutting_speed_range: dict[str, list[float]] = field(default_factory=dict)
    feed_range: dict[str, list[float]] = field(default_factory=dict)
    depth_of_cut_range: dict[str, list[float]] = field(default_factory=dict)
    taylor_exponent_n: float = 0.25
    taylor_constant_c: float = 250

    def get_cutting_speed(self, operation: str = "roughing") -> tuple[float, float]:
        r = self.cutting_speed_range.get(operation)
        if r and len(r) >= 2:
            return (r[0], r[1])
        return (0.0, 0.0)

    def get_feed(self, operation: str = "roughing") -> tuple[float, float]:
        r = self.feed_range.get(operation)
        if r and len(r) >= 2:
            return (r[0], r[1])
        return (0.0, 0.0)

    def get_doc(self, operation: str = "roughing") -> tuple[float, float]:
        r = self.depth_of_cut_range.get(operation)
        if r and len(r) >= 2:
            return (r[0], r[1])
        return (0.0, 0.0)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MaterialEntry:
        return cls(
            id=data["id"],
            name=data["name"],
            category=data["category"],
            hardness_hb=data.get("hardness_hb", 0),
            tensile_strength_mpa=data.get("tensile_strength_mpa", 0),
            thermal_conductivity=data.get("thermal_conductivity", 0),
            density_gcm3=data.get("density_gcm3", 7.85),
            specific_cutting_force=data.get("specific_cutting_force", 2000),
            cutting_speed_range=data.get("cutting_speed_range", {}),
            feed_range=data.get("feed_range", {}),
            depth_of_cut_range=data.get("depth_of_cut_range", {}),
            taylor_exponent_n=data.get("taylor_exponent_n", 0.25),
            taylor_constant_c=data.get("taylor_constant_c", 250),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "category": self.category,
            "hardness_hb": self.hardness_hb,
            "tensile_strength_mpa": self.tensile_strength_mpa,
            "thermal_conductivity": self.thermal_conductivity,
            "density_gcm3": self.density_gcm3,
            "specific_cutting_force": self.specific_cutting_force,
            "cutting_speed_range": self.cutting_speed_range,
            "feed_range": self.feed_range,
            "depth_of_cut_range": self.depth_of_cut_range,
            "taylor_exponent_n": self.taylor_exponent_n,
            "taylor_constant_c": self.taylor_constant_c,
        }


class MaterialDatabase:
    def __init__(self, data_path: str | None = None) -> None:
        if data_path is None:
            data_dir = Path(__file__).resolve().parent / "data"
            data_path = str(data_dir / "materials.json")
        self._data_path = data_path
        self._materials: dict[str, MaterialEntry] = {}
        self._load()

    def _load(self) -> None:
        with open(self._data_path, "r", encoding="utf-8") as f:
            raw = json.load(f)
        for item in raw:
            entry = MaterialEntry.from_dict(item)
            self._materials[entry.id] = entry

    def get(self, material_id: str) -> MaterialEntry:
        if material_id not in self._materials:
            available = ", ".join(self._materials.keys())
            raise KeyError(f"材料 '{material_id}' 不在数据库中。可用材料: {available}")
        return self._materials[material_id]

    def list_all(self) -> list[MaterialEntry]:
        return sorted(self._materials.values(), key=lambda m: m.name)

    def list_ids(self) -> list[str]:
        return sorted(self._materials.keys())

    def filter_by_category(self, category: str) -> list[MaterialEntry]:
        return [m for m in self._materials.values() if m.category == category]

    def search(self, keyword: str) -> list[MaterialEntry]:
        kw = keyword.lower()
        return [
            m
            for m in self._materials.values()
            if kw in m.name.lower() or kw in m.id.lower()
        ]
