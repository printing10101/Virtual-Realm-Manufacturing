"""机械加工工艺规划系统基础数据层。

提供JSON知识库数据的加载、验证、查询和管理功能。
包含材料库、刀具库、切削参数库和工艺规则库的完整数据访问接口。
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional


@dataclass
class MaterialEntry:
    id: str
    name: str
    category: str
    density_gcm3: float
    hardness_hb: float
    tensile_strength_mpa: float
    cutting_performance: str
    description: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MaterialEntry:
        return cls(
            id=data["id"],
            name=data["name"],
            category=data["category"],
            density_gcm3=data["density_gcm3"],
            hardness_hb=data["hardness_hb"],
            tensile_strength_mpa=data["tensile_strength_mpa"],
            cutting_performance=data["cutting_performance"],
            description=data.get("description", ""),
        )


@dataclass
class ToolEntry:
    id: str
    series: str
    name: str
    diameter_mm: float
    material: str
    application: str
    description: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ToolEntry:
        return cls(
            id=data["id"],
            series=data["series"],
            name=data["name"],
            diameter_mm=data["diameter_mm"],
            material=data["material"],
            application=data["application"],
            description=data.get("description", ""),
        )


@dataclass
class CuttingParameterEntry:
    id: str
    material_id: str
    material_name: str
    tool_series: str
    tool_material: str
    cutting_speed_min_mpm: float
    cutting_speed_max_mpm: float
    feed_min_mmpr: float
    feed_max_mmpr: float
    feed_unit: str
    description: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CuttingParameterEntry:
        return cls(
            id=data["id"],
            material_id=data["material_id"],
            material_name=data["material_name"],
            tool_series=data["tool_series"],
            tool_material=data["tool_material"],
            cutting_speed_min_mpm=data["cutting_speed_min_mpm"],
            cutting_speed_max_mpm=data["cutting_speed_max_mpm"],
            feed_min_mmpr=data["feed_min_mmpr"],
            feed_max_mmpr=data["feed_max_mmpr"],
            feed_unit=data["feed_unit"],
            description=data.get("description", ""),
        )


@dataclass
class ProcessRuleEntry:
    id: str
    name: str
    category: str
    description: str
    details: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ProcessRuleEntry:
        return cls(
            id=data["id"],
            name=data["name"],
            category=data["category"],
            description=data["description"],
            details=data.get("details", {}),
        )


class DataValidationError(Exception):
    """数据验证异常"""
    pass


class DataLoadError(Exception):
    """数据加载异常"""
    pass


class QueryError(Exception):
    """查询异常"""
    pass


class ProcessPlanningDataManager:
    """工艺规划数据管理器。

    提供统一的数据访问接口，支持JSON数据加载、验证和查询。
    """

    def __init__(self, data_dir: str | Path | None = None) -> None:
        if data_dir is None:
            data_dir = Path(__file__).resolve().parent
        self._data_dir = Path(data_dir)
        self._materials: dict[str, MaterialEntry] = {}
        self._tools: dict[str, ToolEntry] = {}
        self._cutting_parameters: dict[str, CuttingParameterEntry] = {}
        self._process_rules: dict[str, ProcessRuleEntry] = {}
        self._load_all()

    def _load_json(self, filename: str) -> list[dict[str, Any]]:
        filepath = self._data_dir / filename
        if not filepath.exists():
            raise DataLoadError(f"数据文件不存在: {filepath}")
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, list):
                raise DataValidationError(f"数据文件格式错误: {filename} 应为数组格式")
            return data
        except json.JSONDecodeError as e:
            raise DataLoadError(f"JSON解析失败: {filename}, 错误: {e}")
        except Exception as e:
            raise DataLoadError(f"加载数据文件失败: {filename}, 错误: {e}")

    def _load_all(self) -> None:
        self._load_materials()
        self._load_tools()
        self._load_cutting_parameters()
        self._load_process_rules()

    def _load_materials(self) -> None:
        raw_data = self._load_json("materials.json")
        for item in raw_data:
            entry = MaterialEntry.from_dict(item)
            self._materials[entry.id] = entry

    def _load_tools(self) -> None:
        raw_data = self._load_json("tools.json")
        for item in raw_data:
            entry = ToolEntry.from_dict(item)
            self._tools[entry.id] = entry

    def _load_cutting_parameters(self) -> None:
        raw_data = self._load_json("cutting_parameters.json")
        for item in raw_data:
            entry = CuttingParameterEntry.from_dict(item)
            self._cutting_parameters[entry.id] = entry

    def _load_process_rules(self) -> None:
        raw_data = self._load_json("process_rules.json")
        for item in raw_data:
            entry = ProcessRuleEntry.from_dict(item)
            self._process_rules[entry.id] = entry

    def get_material_by_name(self, name: str) -> Optional[MaterialEntry]:
        """按材料名称查询材料属性。

        Args:
            name: 材料名称，支持模糊匹配

        Returns:
            MaterialEntry: 匹配的材料条目，未找到返回None

        Raises:
            QueryError: 当输入参数无效时
        """
        if not name or not name.strip():
            raise QueryError("材料名称不能为空")
        search_name = name.strip().lower()
        for material in self._materials.values():
            if material.name.lower() == search_name or search_name in material.name.lower():
                return material
        return None

    def get_tools_by_material_and_process(
        self,
        material_category: str,
        process: str
    ) -> list[ToolEntry]:
        """按材料类型和加工工序查询适用刀具。

        Args:
            material_category: 材料类型，如 carbon_steel, aluminum 等
            process: 加工工序，如 钻孔, 型腔/轮廓加工, 平面加工 等

        Returns:
            list[ToolEntry]: 适用的刀具列表
        """
        if not material_category or not material_category.strip():
            raise QueryError("材料类型不能为空")
        if not process or not process.strip():
            raise QueryError("加工工序不能为空")

        process_map = {
            "钻孔": "twist_drill",
            "型腔/轮廓加工": "endmill",
            "平面加工": "face_mill",
            "打中心孔定位": "center_drill",
        }
        tool_series = process_map.get(process.strip())
        if not tool_series:
            return []

        return [
            tool for tool in self._tools.values()
            if tool.series == tool_series
        ]

    def get_cutting_parameters(
        self,
        material_id: str,
        tool_series: str
    ) -> list[CuttingParameterEntry]:
        """按材料类型和刀具类型查询推荐切削参数。

        Args:
            material_id: 材料ID
            tool_series: 刀具系列，如 twist_drill, endmill 等

        Returns:
            list[CuttingParameterEntry]: 切削参数列表
        """
        if not material_id or not material_id.strip():
            raise QueryError("材料ID不能为空")
        if not tool_series or not tool_series.strip():
            raise QueryError("刀具系列不能为空")

        results = []
        for param in self._cutting_parameters.values():
            if (param.material_id == material_id.strip() and
                    param.tool_series == tool_series.strip()):
                results.append(param)
        return results

    def get_material_by_id(self, material_id: str) -> Optional[MaterialEntry]:
        """按ID查询材料。

        Args:
            material_id: 材料ID

        Returns:
            MaterialEntry: 材料条目，未找到返回None
        """
        return self._materials.get(material_id)

    def get_tool_by_id(self, tool_id: str) -> Optional[ToolEntry]:
        """按ID查询刀具。

        Args:
            tool_id: 刀具ID

        Returns:
            ToolEntry: 刀具条目，未找到返回None
        """
        return self._tools.get(tool_id)

    def get_all_materials(self) -> list[MaterialEntry]:
        """获取所有材料。

        Returns:
            list[MaterialEntry]: 材料列表
        """
        return list(self._materials.values())

    def get_all_tools(self) -> list[ToolEntry]:
        """获取所有刀具。

        Returns:
            list[ToolEntry]: 刀具列表
        """
        return list(self._tools.values())

    def get_all_cutting_parameters(self) -> list[CuttingParameterEntry]:
        """获取所有切削参数。

        Returns:
            list[CuttingParameterEntry]: 切削参数列表
        """
        return list(self._cutting_parameters.values())

    def get_all_process_rules(self) -> list[ProcessRuleEntry]:
        """获取所有工艺规则。

        Returns:
            list[ProcessRuleEntry]: 工艺规则列表
        """
        return list(self._process_rules.values())

    def get_process_rule_by_id(self, rule_id: str) -> Optional[ProcessRuleEntry]:
        """按ID查询工艺规则。

        Args:
            rule_id: 规则ID

        Returns:
            ProcessRuleEntry: 规则条目，未找到返回None
        """
        return self._process_rules.get(rule_id)

    def get_process_rules_by_category(self, category: str) -> list[ProcessRuleEntry]:
        """按类别查询工艺规则。

        Args:
            category: 规则类别

        Returns:
            list[ProcessRuleEntry]: 规则列表
        """
        return [
            rule for rule in self._process_rules.values()
            if rule.category == category
        ]

    def get_tools_by_series(self, series: str) -> list[ToolEntry]:
        """按刀具系列查询刀具。

        Args:
            series: 刀具系列

        Returns:
            list[ToolEntry]: 刀具列表
        """
        return [
            tool for tool in self._tools.values()
            if tool.series == series
        ]

    def get_materials_by_category(self, category: str) -> list[MaterialEntry]:
        """按材料类别查询材料。

        Args:
            category: 材料类别

        Returns:
            list[MaterialEntry]: 材料列表
        """
        return [
            material for material in self._materials.values()
            if material.category == category
        ]

    def validate_data_integrity(self) -> dict[str, Any]:
        """验证数据完整性。

        Returns:
            dict: 验证结果，包含统计信息和错误列表
        """
        errors = []
        stats = {
            "materials_count": len(self._materials),
            "tools_count": len(self._tools),
            "cutting_parameters_count": len(self._cutting_parameters),
            "process_rules_count": len(self._process_rules),
        }

        for param in self._cutting_parameters.values():
            if param.material_id not in self._materials:
                errors.append(f"切削参数 {param.id} 引用了不存在的材料: {param.material_id}")

        return {
            "stats": stats,
            "errors": errors,
            "is_valid": len(errors) == 0,
        }

    def __repr__(self) -> str:
        return (
            f"ProcessPlanningDataManager("
            f"materials={len(self._materials)}, "
            f"tools={len(self._tools)}, "
            f"cutting_params={len(self._cutting_parameters)}, "
            f"rules={len(self._process_rules)})"
        )
