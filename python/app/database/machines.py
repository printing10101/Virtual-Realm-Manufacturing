"""机床数据库模块（基础版）。

提供机床参数查询功能。
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class MachineEntry:
    id: str
    name: str
    type: str
    spindle_power_kw: float = 0
    spindle_speed_rpm: list[float] = field(default_factory=lambda: [0, 0])
    feed_rapid_mmmin: float = 0
    feed_cutting_max_mmmin: float = 0
    max_cutting_force_n: float = 0
    max_turning_diameter_mm: float = 0
    max_turning_length_mm: float = 0
    table_size_mm: list[float] = field(default_factory=lambda: [0, 0])
    travel_xyz_mm: list[float] = field(default_factory=lambda: [0, 0, 0])
    tool_changer_capacity: int = 0
    coolant_pressure_mpa: float = 0
    positioning_accuracy_mm: float = 0

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MachineEntry:
        return cls(
            id=data["id"],
            name=data["name"],
            type=data["type"],
            spindle_power_kw=data.get("spindle_power_kw", 0),
            spindle_speed_rpm=data.get("spindle_speed_rpm", [0, 0]),
            feed_rapid_mmmin=data.get("feed_rapid_mmmin", 0),
            feed_cutting_max_mmmin=data.get("feed_cutting_max_mmmin", 0),
            max_cutting_force_n=data.get("max_cutting_force_n", 0),
            max_turning_diameter_mm=data.get("max_turning_diameter_mm", 0),
            max_turning_length_mm=data.get("max_turning_length_mm", 0),
            table_size_mm=data.get("table_size_mm", [0, 0]),
            travel_xyz_mm=data.get("travel_xyz_mm", [0, 0, 0]),
            tool_changer_capacity=data.get("tool_changer_capacity", 0),
            coolant_pressure_mpa=data.get("coolant_pressure_mpa", 0),
            positioning_accuracy_mm=data.get("positioning_accuracy_mm", 0),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "type": self.type,
            "spindle_power_kw": self.spindle_power_kw,
            "spindle_speed_rpm": self.spindle_speed_rpm,
            "feed_rapid_mmmin": self.feed_rapid_mmmin,
            "feed_cutting_max_mmmin": self.feed_cutting_max_mmmin,
            "max_cutting_force_n": self.max_cutting_force_n,
            "table_size_mm": self.table_size_mm,
            "travel_xyz_mm": self.travel_xyz_mm,
            "tool_changer_capacity": self.tool_changer_capacity,
            "coolant_pressure_mpa": self.coolant_pressure_mpa,
            "positioning_accuracy_mm": self.positioning_accuracy_mm,
        }


class MachineDatabase:
    def __init__(self, data_path: str | None = None) -> None:
        if data_path is None:
            data_dir = Path(__file__).resolve().parent / "data"
            data_path = str(data_dir / "machines.json")
        self._data_path = data_path
        self._machines: dict[str, MachineEntry] = {}
        self._load()

    def _load(self) -> None:
        with open(self._data_path, "r", encoding="utf-8") as f:
            raw = json.load(f)
        for item in raw:
            entry = MachineEntry.from_dict(item)
            self._machines[entry.id] = entry

    def get(self, machine_id: str) -> MachineEntry:
        if machine_id not in self._machines:
            available = ", ".join(self._machines.keys())
            raise KeyError(f"机床 '{machine_id}' 不在数据库中。可用机床: {available}")
        return self._machines[machine_id]

    def list_ids(self) -> list[str]:
        return sorted(self._machines.keys())
