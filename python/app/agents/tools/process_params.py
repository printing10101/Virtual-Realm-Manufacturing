from typing import Dict, Any
from app.agents.tools import BaseTool, ToolObservation


class GetProcessParamsTool(BaseTool):
    def __init__(self):
        super().__init__(
            name="get_process_params",
            description="查询已生成的工艺参数，包括切削速度、进给量、切削深度等。当需要获取工艺参数数据时使用此工具。"
        )

    def get_input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "param_type": {
                    "type": "string",
                    "description": "参数类型：cutting_speed（切削速度）、feed_rate（进给量）、depth_of_cut（切削深度）、all（所有参数）",
                    "enum": ["cutting_speed", "feed_rate", "depth_of_cut", "all"]
                },
                "operation_id": {
                    "type": "string",
                    "description": "可选，指定工序ID"
                }
            },
            "required": ["param_type"]
        }

    async def execute(self, param_type: str = "all", operation_id: str = None, **kwargs) -> ToolObservation:
        params_data = {
            "cutting_speed": {
                "v_c": 150.0,
                "unit": "m/min",
                "material": "45钢",
                "tool_material": "硬质合金"
            },
            "feed_rate": {
                "f": 0.20,
                "unit": "mm/rev",
                "surface_finish_requirement": "Ra 1.6"
            },
            "depth_of_cut": {
                "a_p": 2.0,
                "unit": "mm",
                "roughing_depth": 3.0,
                "finishing_depth": 0.5
            }
        }

        if param_type == "all":
            result = params_data
            summary = "获取全部工艺参数：切削速度 150.00 m/min，进给量 0.20 mm/rev，切削深度 2.00 mm"
        elif param_type in params_data:
            result = {param_type: params_data[param_type]}
            summary = f"获取{param_type}参数"
        else:
            result = {}
            summary = f"未找到参数类型: {param_type}"

        return ToolObservation(
            tool_name=self.name,
            input_data={"param_type": param_type, "operation_id": operation_id},
            output_data=result,
            summary=summary
        )
