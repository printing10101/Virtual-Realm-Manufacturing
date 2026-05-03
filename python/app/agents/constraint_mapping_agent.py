from typing import Dict, Any, List, Optional
from app.services.experience_store import ExperienceStore
from app.core.scenario_manager import scenario_manager


class ConstraintMappingAgent:
    def __init__(self, experience_store: Optional[ExperienceStore] = None):
        self.experience_store = experience_store

    def get_scenario_constraints(
        self,
        scenario_id: str,
        material: str = "",
        tool: str = ""
    ) -> Dict[str, Any]:
        try:
            return scenario_manager.get_constraints(scenario_id, material if material else None, tool if tool else None)
        except Exception:
            return scenario_manager.get_constraints("base", material if material else None, tool if tool else None)

    def get_experience_constraints(
        self,
        material: str = "",
        tool: str = "",
        operation: str = "",
        scenario: str = ""
    ) -> List[Dict[str, Any]]:
        if not self.experience_store:
            return []

        rules = self.experience_store.get_rules(scenario)

        constraints = []
        for scenario_name, rule_list in rules.items():
            for rule_data in rule_list:
                if not rule_data.get("enabled", True):
                    continue

                rule_text = rule_data["rule"]
                constraint = self._parse_rule_to_constraint(rule_text)
                if constraint:
                    constraint["source_scenario"] = scenario_name
                    constraint["source_experience"] = rule_data.get("source_experience_id", "")
                    constraint["priority"] = "experience"
                    constraints.append(constraint)

        return constraints

    def _parse_rule_to_constraint(self, rule_text: str) -> Optional[Dict[str, Any]]:
        rule_text_lower = rule_text.lower()

        param_map = {
            "切削速度": "v_c",
            "v_c": "v_c",
            "进给量": "f",
            "f": "f",
            "背吃刀量": "a_p",
            "a_p": "a_p",
            "表面粗糙度": "Ra",
            "切削力": "F_c",
            "刀具寿命": "T"
        }

        for keyword, param in param_map.items():
            if keyword in rule_text:
                if "上限" in rule_text or "下调" in rule_text or "不宜超过" in rule_text or "不宜大于" in rule_text:
                    value = self._extract_number(rule_text)
                    if value:
                        return {
                            "param": param,
                            "type": "upper_bound",
                            "value": value,
                            "description": rule_text,
                            "modifier": "multiply" if any(w in rule_text for w in ["下调", "上调", "倍"]) else "absolute"
                        }
                elif "下限" in rule_text or "不低于" in rule_text:
                    value = self._extract_number(rule_text)
                    if value:
                        return {
                            "param": param,
                            "type": "lower_bound",
                            "value": value,
                            "description": rule_text,
                            "modifier": "multiply" if any(w in rule_text for w in ["下调", "上调", "倍"]) else "absolute"
                        }
                elif "不宜" in rule_text or "避免" in rule_text:
                    return {
                        "param": param,
                        "type": "avoid",
                        "value": None,
                        "description": rule_text,
                        "modifier": "avoid"
                    }

        return None

    def _extract_number(self, text: str) -> Optional[float]:
        import re
        numbers = re.findall(r'[\d.]+', text)
        if numbers:
            try:
                return float(numbers[0])
            except ValueError:
                return None
        return None

    def apply_experience_constraints(
        self,
        base_params: Dict[str, float],
        material: str = "",
        tool: str = "",
        operation: str = "",
        scenario: str = ""
    ) -> Dict[str, float]:
        constraints = self.get_experience_constraints(material, tool, operation, scenario)

        modified_params = base_params.copy()
        for constraint in constraints:
            param = constraint["param"]
            if param not in modified_params:
                continue

            if constraint["type"] == "upper_bound":
                if constraint["modifier"] == "multiply":
                    modified_params[param] = modified_params[param] * constraint["value"]
                else:
                    modified_params[param] = min(modified_params[param], constraint["value"])
            elif constraint["type"] == "lower_bound":
                if constraint["modifier"] == "multiply":
                    modified_params[param] = modified_params[param] * constraint["value"]
                else:
                    modified_params[param] = max(modified_params[param], constraint["value"])

        return modified_params
