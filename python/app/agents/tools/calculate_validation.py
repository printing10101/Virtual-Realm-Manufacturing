from typing import Dict, Any
from app.agents.tools import BaseTool, ToolObservation


class CalculateValidationTool(BaseTool):
    def __init__(self):
        super().__init__(
            name="calculate_validation",
            description="调用在线验证公式计算切削力、刀具寿命、表面粗糙度等指标。当需要验证工艺参数是否满足约束条件时使用此工具。"
        )

    def get_input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "formula_type": {
                    "type": "string",
                    "description": "公式类型：kienzle（切削力）、taylor（刀具寿命）、surface_roughness（表面粗糙度）、all（全部）",
                    "enum": ["kienzle", "taylor", "surface_roughness", "all"]
                },
                "params": {
                    "type": "object",
                    "description": "计算参数",
                    "properties": {
                        "cutting_speed": {"type": "number", "description": "切削速度 (m/min)"},
                        "feed_rate": {"type": "number", "description": "进给量 (mm/rev)"},
                        "depth_of_cut": {"type": "number", "description": "切削深度 (mm)"},
                        "material_hardness": {"type": "number", "description": "材料硬度 (HRC)"}
                    }
                }
            },
            "required": ["formula_type"]
        }

    async def execute(self, formula_type: str = "all", params: Dict = None, **kwargs) -> ToolObservation:
        p = params or {
            "cutting_speed": 150.0,
            "feed_rate": 0.20,
            "depth_of_cut": 2.0,
            "material_hardness": 25.0
        }

        v_c = p.get("cutting_speed", 150.0)
        f = p.get("feed_rate", 0.20)
        a_p = p.get("depth_of_cut", 2.0)
        hrc = p.get("material_hardness", 25.0)

        results = {}

        if formula_type in ["kienzle", "all"]:
            k_c = 1800.0 * (f ** -0.25)
            f_c = k_c * a_p * f
            results["kienzle"] = {
                "cutting_force_N": f_c,
                "specific_cutting_force_Nmm2": k_c,
                "formula": "Fc = Kc * ap * f",
                "unit": "N"
            }

        if formula_type in ["taylor", "all"]:
            n = 0.25
            c = 350.0
            t = (c / (v_c ** n)) ** (1 / n)
            results["taylor"] = {
                "tool_life_min": t,
                "tool_life_hours": t / 60,
                "taylor_exponent": n,
                "formula": "Vc * T^n = C",
                "unit": "min"
            }

        if formula_type in ["surface_roughness", "all"]:
            r_e = 0.8
            r_a = (f ** 2) / (8 * r_e) * 1000
            results["surface_roughness"] = {
                "predicted_ra_um": r_a,
                "formula": "Ra = f² / (8 * rε) × 1000",
                "unit": "μm",
                "meets_requirement": r_a <= 1.6
            }

        summary = self._build_summary(results, formula_type)

        return ToolObservation(
            tool_name=self.name,
            input_data={"formula_type": formula_type, "params": p},
            output_data=results,
            summary=summary
        )

    def _build_summary(self, results: Dict, formula_type: str) -> str:
        parts = []
        if "kienzle" in results:
            parts.append(f"切削力 {results['kienzle']['cutting_force_N']:.2f} N")
        if "taylor" in results:
            parts.append(f"刀具寿命 {results['taylor']['tool_life_min']:.2f} min")
        if "surface_roughness" in results:
            parts.append(f"表面粗糙度 Ra {results['surface_roughness']['predicted_ra_um']:.2f} μm")
        return "计算结果：" + "，".join(parts)
