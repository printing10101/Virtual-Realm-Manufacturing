from typing import Dict, Any
from app.agents.tools import BaseTool, ToolObservation


class GetMaterialInfoTool(BaseTool):
    def __init__(self):
        super().__init__(
            name="get_material_info",
            description="查询工件材料属性，包括硬度、抗拉强度、热导率、密度等物理性能参数。当需要分析材料加工特性时使用此工具。"
        )

    def get_input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "material_name": {
                    "type": "string",
                    "description": "材料名称，如 45钢、6061铝合金、Ti6Al4V钛合金等"
                },
                "property_type": {
                    "type": "string",
                    "description": "属性类型：mechanical（力学性能）、thermal（热物理性能）、all（全部）",
                    "enum": ["mechanical", "thermal", "all"]
                }
            },
            "required": ["material_name"]
        }

    async def execute(self, material_name: str = "45钢", property_type: str = "all", **kwargs) -> ToolObservation:
        materials_db = {
            "45钢": {
                "mechanical": {
                    "hardness_hrc": 25.0,
                    "tensile_strength_mpa": 600.0,
                    "yield_strength_mpa": 355.0,
                    "elongation_percent": 16.0,
                    "modulus_of_elasticity_gpa": 210.0
                },
                "thermal": {
                    "thermal_conductivity_wmk": 50.0,
                    "specific_heat_jkgk": 480.0,
                    "melting_point_celsius": 1500.0,
                    "thermal_expansion_coefficient": 11.5e-6
                },
                "density_kgm3": 7850.0
            },
            "6061铝合金": {
                "mechanical": {
                    "hardness_hrc": 15.0,
                    "tensile_strength_mpa": 310.0,
                    "yield_strength_mpa": 276.0,
                    "elongation_percent": 12.0,
                    "modulus_of_elasticity_gpa": 69.0
                },
                "thermal": {
                    "thermal_conductivity_wmk": 167.0,
                    "specific_heat_jkgk": 896.0,
                    "melting_point_celsius": 650.0,
                    "thermal_expansion_coefficient": 23.6e-6
                },
                "density_kgm3": 2700.0
            },
            "Ti6Al4V": {
                "mechanical": {
                    "hardness_hrc": 35.0,
                    "tensile_strength_mpa": 950.0,
                    "yield_strength_mpa": 880.0,
                    "elongation_percent": 14.0,
                    "modulus_of_elasticity_gpa": 114.0
                },
                "thermal": {
                    "thermal_conductivity_wmk": 7.0,
                    "specific_heat_jkgk": 560.0,
                    "melting_point_celsius": 1660.0,
                    "thermal_expansion_coefficient": 8.6e-6
                },
                "density_kgm3": 4430.0
            }
        }

        material = materials_db.get(material_name, materials_db["45钢"])
        
        if property_type == "all":
            result = material
            summary = f"获取{material_name}全部材料属性：硬度 {material['mechanical']['hardness_hrc']:.2f} HRC，抗拉强度 {material['mechanical']['tensile_strength_mpa']:.2f} MPa"
        elif property_type in material:
            result = {property_type: material[property_type]}
            summary = f"获取{material_name}的{property_type}属性"
        else:
            result = material
            summary = f"获取{material_name}全部材料属性"

        return ToolObservation(
            tool_name=self.name,
            input_data={"material_name": material_name, "property_type": property_type},
            output_data=result,
            summary=summary
        )
