from typing import Dict, Any
from app.agents.tools import BaseTool, ToolObservation


class GetToolInfoTool(BaseTool):
    def __init__(self):
        super().__init__(
            name="get_tool_info",
            description="查询刀具参数，包括材质、涂层、几何角度（前角、后角、主偏角等）、刀片型号等。当需要分析刀具切削特性时使用此工具。"
        )

    def get_input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "tool_type": {
                    "type": "string",
                    "description": "刀具类型：turning（车刀）、milling（铣刀）、drilling（钻头）",
                    "enum": ["turning", "milling", "drilling"]
                },
                "tool_id": {
                    "type": "string",
                    "description": "可选，指定刀具ID"
                }
            },
            "required": ["tool_type"]
        }

    async def execute(self, tool_type: str = "turning", tool_id: str = None, **kwargs) -> ToolObservation:
        tools_db = {
            "turning": {
                "tool_material": "硬质合金 (WC-Co)",
                "coating": "TiAlN",
                "geometry": {
                    "rake_angle_deg": 5.0,
                    "clearance_angle_deg": 7.0,
                    "cutting_edge_angle_deg": 90.0,
                    "nose_radius_mm": 0.8
                },
                "insert_model": "CNMG120408-MA",
                "tool_holder": "MCLNL2020K12",
                "max_cutting_depth_mm": 5.0,
                "recommended_speed_mmin": "150-250"
            },
            "milling": {
                "tool_material": "高速钢 (HSS)",
                "coating": "TiN",
                "geometry": {
                    "rake_angle_deg": 10.0,
                    "clearance_angle_deg": 12.0,
                    "helix_angle_deg": 30.0,
                    "number_of_flutes": 4
                },
                "diameter_mm": 20.0,
                "max_depth_of_cut_mm": 3.0,
                "recommended_speed_mmin": "80-120"
            },
            "drilling": {
                "tool_material": "硬质合金",
                "coating": "TiAlN",
                "geometry": {
                    "point_angle_deg": 118.0,
                    "helix_angle_deg": 30.0,
                    "margin_width_mm": 0.3
                },
                "diameter_mm": 10.0,
                "max_drilling_depth_mm": 30.0,
                "recommended_speed_mmin": "60-100"
            }
        }

        tool_info = tools_db.get(tool_type, tools_db["turning"])
        summary = f"获取{tool_type}刀具参数：材质 {tool_info['tool_material']}，涂层 {tool_info['coating']}"

        return ToolObservation(
            tool_name=self.name,
            input_data={"tool_type": tool_type, "tool_id": tool_id},
            output_data=tool_info,
            summary=summary
        )
