"""材料-刀具-工艺参数知识图谱集成模块

从材料库、刀具库和切削参数库构建知识图谱，实现：
1. 材料-刀具-参数的关联关系建立
2. 基于图谱的工艺推荐：输入材料 → 推荐刀具 → 推荐参数
3. 图谱查询 API
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from app.knowledge_graph.graph_store import GraphStore

logger = logging.getLogger(__name__)


@dataclass
class ProcessRecommendation:
    """工艺推荐结果"""
    material_id: str
    material_name: str
    recommended_tools: list[dict]
    recommended_parameters: list[dict]
    confidence: float = 0.0


class MaterialToolGraph:
    """材料-刀具-工艺参数知识图谱

    从 JSON 数据文件构建知识图谱，提供工艺推荐能力。
    """

    def __init__(self, data_dir: Optional[Path] = None):
        """初始化知识图谱

        Args:
            data_dir: 数据目录路径，默认为 app/data
        """
        if data_dir is None:
            data_dir = Path(__file__).parent.parent / "data"
        self.data_dir = data_dir

        self.graph = GraphStore(auto_load=False)
        self._loaded = False

    def build_from_json_files(self) -> bool:
        """从 JSON 数据文件构建知识图谱

        Returns:
            bool: 构建是否成功
        """
        try:
            # 加载材料库
            materials_file = self.data_dir / "materials.json"
            if materials_file.exists():
                self._load_materials(materials_file)

            # 加载刀具库
            tools_file = self.data_dir / "tools.json"
            if tools_file.exists():
                self._load_tools(tools_file)

            # 加载切削参数库
            params_file = self.data_dir / "cutting_parameters.json"
            if params_file.exists():
                self._load_cutting_parameters(params_file)

            # 建立材料-刀具-参数关联
            self._build_relationships()

            self._loaded = True
            logger.info(
                "知识图谱构建完成: %d 节点, %d 关系",
                self.graph.node_count(),
                self.graph.edge_count(),
            )
            return True

        except Exception as e:
            logger.error("知识图谱构建失败: %s", e)
            return False

    def _load_materials(self, file_path: Path) -> None:
        """加载材料库到知识图谱"""
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        materials = data if isinstance(data, list) else data.get("materials", [])

        for material in materials:
            material_id = material.get("id", "")
            if not material_id:
                continue

            # 规范化节点 ID
            node_id = f"material-{material_id.replace('material_', '')}"

            self.graph.add_node(
                node_type="material",
                node_id=node_id,
                properties={
                    "name": material.get("name", ""),
                    "category": material.get("category", ""),
                    "density": material.get("density_gcm3", 0),
                    "hardness": material.get("hardness_hb", 0),
                    "tensile_strength": material.get("tensile_strength_mpa", 0),
                    "cutting_performance": material.get("cutting_performance", ""),
                    "description": material.get("description", ""),
                },
            )

    def _load_tools(self, file_path: Path) -> None:
        """加载刀具库到知识图谱"""
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        tools = data if isinstance(data, list) else data.get("tools", [])

        for tool in tools:
            tool_id = tool.get("id", "")
            if not tool_id:
                continue

            # 规范化节点 ID
            node_id = f"tool-{tool_id.replace('tool_', '')}"

            self.graph.add_node(
                node_type="tool",
                node_id=node_id,
                properties={
                    "name": tool.get("name", ""),
                    "series": tool.get("series", ""),
                    "diameter": tool.get("diameter_mm", 0),
                    "radius": tool.get("radius_mm", 0),
                    "material": tool.get("material", ""),
                    "application": tool.get("application", ""),
                    "description": tool.get("description", ""),
                },
            )

    def _load_cutting_parameters(self, file_path: Path) -> None:
        """加载切削参数库到知识图谱"""
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        params = data if isinstance(data, list) else data.get("parameters", [])

        for param in params:
            param_id = param.get("id", "")
            if not param_id:
                continue

            # 规范化节点 ID
            node_id = f"param-{param_id.replace('param_', '')}"

            self.graph.add_node(
                node_type="parameter",
                node_id=node_id,
                properties={
                    "material_id": param.get("material_id", ""),
                    "material_name": param.get("material_name", ""),
                    "tool_series": param.get("tool_series", ""),
                    "tool_material": param.get("tool_material", ""),
                    "cutting_speed_min": param.get("cutting_speed_min_mpm", 0),
                    "cutting_speed_max": param.get("cutting_speed_max_mpm", 0),
                    "feed_min": param.get("feed_min_mmpr", 0),
                    "feed_max": param.get("feed_max_mmpr", 0),
                    "feed_unit": param.get("feed_unit", ""),
                    "description": param.get("description", ""),
                },
            )

    def _build_relationships(self) -> None:
        """建立材料-刀具-参数关联关系"""
        # 获取所有参数节点
        param_nodes = self.graph.list_nodes_by_type("parameter")

        for param_node in param_nodes:
            param_id = param_node["node_id"]
            props = param_node["properties"]

            material_id = props.get("material_id", "")
            tool_series = props.get("tool_series", "")

            # 建立材料-参数关系
            if material_id:
                material_node_id = f"material-{material_id.replace('material_', '')}"
                if self.graph.has_node(material_node_id):
                    self.graph.add_edge(
                        source_id=material_node_id,
                        target_id=param_id,
                        edge_type="HAS_PARAMETER",
                        properties={"confidence": 0.9},
                    )

            # 建立刀具-参数关系
            if tool_series:
                # 查找匹配的刀具
                tool_nodes = self.graph.list_nodes_by_type("tool")
                for tool_node in tool_nodes:
                    tool_props = tool_node["properties"]
                    if tool_props.get("series") == tool_series:
                        tool_node_id = tool_node["node_id"]
                        self.graph.add_edge(
                            source_id=tool_node_id,
                            target_id=param_id,
                            edge_type="HAS_PARAMETER",
                            properties={"confidence": 0.9},
                        )

                        # 建立材料-刀具关系（通过参数间接关联）
                        if material_id and self.graph.has_node(material_node_id):
                            # 检查是否已存在直接关系
                            if not self.graph.has_edge(
                                material_node_id, tool_node_id, "RECOMMENDS_TOOL"
                            ):
                                self.graph.add_edge(
                                    source_id=material_node_id,
                                    target_id=tool_node_id,
                                    edge_type="RECOMMENDS_TOOL",
                                    properties={
                                        "confidence": 0.8,
                                        "based_on": "cutting_parameters",
                                    },
                                )

    def recommend_process(
        self,
        material_id: str,
        tool_series: Optional[str] = None,
    ) -> Optional[ProcessRecommendation]:
        """基于知识图谱推荐工艺参数

        Args:
            material_id: 材料 ID
            tool_series: 可选的刀具系列限制

        Returns:
            ProcessRecommendation: 推荐结果，包含刀具和参数
        """
        if not self._loaded:
            logger.warning("知识图谱未加载")
            return None

        # 规范化材料节点 ID
        material_node_id = f"material-{material_id.replace('material_', '')}"

        if not self.graph.has_node(material_node_id):
            logger.warning("材料不存在: %s", material_id)
            return None

        # 获取材料信息
        material_node = self.graph.get_node(material_node_id)
        material_name = material_node["properties"].get("name", material_id)

        # 查询推荐的刀具
        recommended_tools = []
        tool_edges = self.graph.list_edges_by_source(
            material_node_id, edge_type="RECOMMENDS_TOOL"
        )

        for edge in tool_edges:
            tool_node_id = edge["target_id"]
            tool_node = self.graph.get_node(tool_node_id)

            if tool_node:
                tool_props = tool_node["properties"]

                # 如果指定了刀具系列，过滤不匹配的
                if tool_series and tool_props.get("series") != tool_series:
                    continue

                recommended_tools.append({
                    "tool_id": tool_node_id,
                    "name": tool_props.get("name", ""),
                    "series": tool_props.get("series", ""),
                    "diameter": tool_props.get("diameter", 0),
                    "material": tool_props.get("material", ""),
                    "application": tool_props.get("application", ""),
                    "confidence": edge["properties"].get("confidence", 0.5),
                })

        # 按置信度排序
        recommended_tools.sort(key=lambda x: x["confidence"], reverse=True)

        # 查询推荐的参数
        recommended_parameters = []
        param_edges = self.graph.list_edges_by_source(
            material_node_id, edge_type="HAS_PARAMETER"
        )

        for edge in param_edges:
            param_node_id = edge["target_id"]
            param_node = self.graph.get_node(param_node_id)

            if param_node:
                param_props = param_node["properties"]

                # 如果指定了刀具系列，过滤不匹配的
                if tool_series and param_props.get("tool_series") != tool_series:
                    continue

                recommended_parameters.append({
                    "parameter_id": param_node_id,
                    "tool_series": param_props.get("tool_series", ""),
                    "tool_material": param_props.get("tool_material", ""),
                    "cutting_speed_min": param_props.get("cutting_speed_min", 0),
                    "cutting_speed_max": param_props.get("cutting_speed_max", 0),
                    "feed_min": param_props.get("feed_min", 0),
                    "feed_max": param_props.get("feed_max", 0),
                    "feed_unit": param_props.get("feed_unit", ""),
                    "description": param_props.get("description", ""),
                    "confidence": edge["properties"].get("confidence", 0.5),
                })

        # 按置信度排序
        recommended_parameters.sort(key=lambda x: x["confidence"], reverse=True)

        # 计算整体置信度
        avg_confidence = 0.0
        if recommended_tools or recommended_parameters:
            total_conf = sum(t["confidence"] for t in recommended_tools)
            total_conf += sum(p["confidence"] for p in recommended_parameters)
            total_count = len(recommended_tools) + len(recommended_parameters)
            avg_confidence = total_conf / total_count if total_count > 0 else 0.0

        return ProcessRecommendation(
            material_id=material_id,
            material_name=material_name,
            recommended_tools=recommended_tools,
            recommended_parameters=recommended_parameters,
            confidence=avg_confidence,
        )

    def query_materials(self) -> list[dict]:
        """查询所有可用材料"""
        if not self._loaded:
            return []

        materials = []
        for node in self.graph.list_nodes_by_type("material"):
            materials.append({
                "material_id": node["node_id"],
                **node["properties"],
            })
        return materials

    def query_tools(
        self,
        material_id: Optional[str] = None,
    ) -> list[dict]:
        """查询刀具，可选按材料过滤"""
        if not self._loaded:
            return []

        tools = []

        if material_id:
            # 查询材料推荐的刀具
            material_node_id = f"material-{material_id.replace('material_', '')}"
            tool_edges = self.graph.list_edges_by_source(
                material_node_id, edge_type="RECOMMENDS_TOOL"
            )

            for edge in tool_edges:
                tool_node = self.graph.get_node(edge["target_id"])
                if tool_node:
                    tools.append({
                        "tool_id": tool_node["node_id"],
                        **tool_node["properties"],
                        "recommendation_confidence": edge["properties"].get(
                            "confidence", 0.5
                        ),
                    })
        else:
            # 查询所有刀具
            for node in self.graph.list_nodes_by_type("tool"):
                tools.append({
                    "tool_id": node["node_id"],
                    **node["properties"],
                })

        return tools

    def query_parameters(
        self,
        material_id: Optional[str] = None,
        tool_series: Optional[str] = None,
    ) -> list[dict]:
        """查询切削参数，可选按材料和刀具过滤"""
        if not self._loaded:
            return []

        parameters = []

        if material_id:
            # 查询材料相关的参数
            material_node_id = f"material-{material_id.replace('material_', '')}"
            param_edges = self.graph.list_edges_by_source(
                material_node_id, edge_type="HAS_PARAMETER"
            )

            for edge in param_edges:
                param_node = self.graph.get_node(edge["target_id"])
                if param_node:
                    param_data = {
                        "parameter_id": param_node["node_id"],
                        **param_node["properties"],
                        "recommendation_confidence": edge["properties"].get(
                            "confidence", 0.5
                        ),
                    }

                    # 如果指定了刀具系列，过滤
                    if tool_series:
                        if param_data.get("tool_series") == tool_series:
                            parameters.append(param_data)
                    else:
                        parameters.append(param_data)
        else:
            # 查询所有参数
            for node in self.graph.list_nodes_by_type("parameter"):
                param_data = {
                    "parameter_id": node["node_id"],
                    **node["properties"],
                }

                # 如果指定了刀具系列，过滤
                if tool_series:
                    if param_data.get("tool_series") == tool_series:
                        parameters.append(param_data)
                else:
                    parameters.append(param_data)

        return parameters


__all__ = [
    "MaterialToolGraph",
    "ProcessRecommendation",
]
