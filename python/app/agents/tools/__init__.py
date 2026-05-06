from app.agents.tools.process_params import GetProcessParamsTool
from app.agents.tools.material_info import GetMaterialInfoTool
from app.agents.tools.tool_info import GetToolInfoTool
from app.agents.tools.calculate_validation import CalculateValidationTool
from app.agents.tools.constraint_status import GetConstraintStatusTool


def get_all_tools():
    return [
        GetProcessParamsTool(),
        GetMaterialInfoTool(),
        GetToolInfoTool(),
        CalculateValidationTool(),
        GetConstraintStatusTool()
    ]


tools_dict = {tool.name: tool for tool in get_all_tools()}
