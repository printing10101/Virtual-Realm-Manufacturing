from typing import Dict, Any
from app.agents.tools import BaseTool, ToolObservation


class GetConstraintStatusTool(BaseTool):
    def __init__(self):
        super().__init__(
            name="get_constraint_status",
            description="查询所有物理约束的满足情况，包括哪些约束满足、哪些违反、违反程度。当需要评估工艺参数是否符合约束条件时使用此工具。"
        )

    def get_input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "constraint_type": {
                    "type": "string",
                    "description": "约束类型：force（切削力约束）、temperature（温度约束）、wear（磨损约束）、surface（表面质量约束）、all（全部）",
                    "enum": ["force", "temperature", "wear", "surface", "all"]
                }
            },
            "required": ["constraint_type"]
        }

    async def execute(self, constraint_type: str = "all", **kwargs) -> ToolObservation:
        constraints = {
            "force": {
                "constraint": "切削力 <= 5000 N",
                "actual_value": 3250.0,
                "limit": 5000.0,
                "unit": "N",
                "satisfied": True,
                "violation_degree": 0.0,
                "margin_percent": 35.0
            },
            "temperature": {
                "constraint": "切削温度 <= 800 °C",
                "actual_value": 650.0,
                "limit": 800.0,
                "unit": "°C",
                "satisfied": True,
                "violation_degree": 0.0,
                "margin_percent": 18.75
            },
            "wear": {
                "constraint": "刀具磨损量 <= 0.3 mm",
                "actual_value": 0.25,
                "limit": 0.3,
                "unit": "mm",
                "satisfied": True,
                "violation_degree": 0.0,
                "margin_percent": 16.67
            },
            "surface": {
                "constraint": "表面粗糙度 Ra <= 1.6 μm",
                "actual_value": 0.62,
                "limit": 1.6,
                "unit": "μm",
                "satisfied": True,
                "violation_degree": 0.0,
                "margin_percent": 61.25
            }
        }

        if constraint_type == "all":
            result = constraints
            satisfied_count = sum(1 for c in constraints.values() if c["satisfied"])
            total_count = len(constraints)
            summary = f"约束满足情况：{satisfied_count}/{total_count} 项约束满足，无违反项"
        elif constraint_type in constraints:
            result = {constraint_type: constraints[constraint_type]}
            c = constraints[constraint_type]
            status = "满足" if c["satisfied"] else "违反"
            summary = f"{constraint_type}约束{status}，实际值 {c['actual_value']:.2f} {c['unit']}"
        else:
            result = {}
            summary = f"未找到约束类型: {constraint_type}"

        return ToolObservation(
            tool_name=self.name,
            input_data={"constraint_type": constraint_type},
            output_data=result,
            summary=summary
        )
