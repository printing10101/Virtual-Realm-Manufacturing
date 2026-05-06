import json
import os
import yaml
import shutil
from typing import Dict, Any, List, Optional
from pathlib import Path


REQUIRED_FILES = ["scenario.json", "constraints.json", "cost_model.json", "prompts.yaml", "validation_rules.json"]
REQUIRED_SCENARIO_FIELDS = ["id", "name", "description", "supported_operations", "supported_materials", "supported_tools", "version"]


class ScenarioValidationError(Exception):
    pass


class ScenarioNotFoundError(ScenarioValidationError):
    pass


class ScenarioManager:
    def __init__(self, builtin_scenarios_dir: str = None, user_scenarios_dir: str = None):
        if builtin_scenarios_dir is None:
            builtin_scenarios_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "scenarios")
        
        if user_scenarios_dir is None:
            user_scenarios_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "user_scenarios")
        
        self.builtin_scenarios_dir = Path(builtin_scenarios_dir)
        self.user_scenarios_dir = Path(user_scenarios_dir)
        
        self._scenario_cache: Dict[str, Dict[str, Any]] = {}
        
        self.user_scenarios_dir.mkdir(parents=True, exist_ok=True)
        
        self._discover_scenarios()
    
    def _discover_scenarios(self) -> Dict[str, Path]:
        self._scenario_paths: Dict[str, Path] = {}
        
        for scenario_dir in self.builtin_scenarios_dir.iterdir():
            if scenario_dir.is_dir() and (scenario_dir / "scenario.json").exists():
                self._scenario_paths[scenario_dir.name] = scenario_dir
        
        for scenario_dir in self.user_scenarios_dir.iterdir():
            if scenario_dir.is_dir() and (scenario_dir / "scenario.json").exists():
                self._scenario_paths[scenario_dir.name] = scenario_dir
        
        return self._scenario_paths
    
    def _load_json(self, file_path: Path) -> Dict[str, Any]:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def _load_yaml(self, file_path: Path) -> Dict[str, Any]:
        with open(file_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f) or {}
    
    def _save_json(self, file_path: Path, data: Dict[str, Any]) -> None:
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    def _save_yaml(self, file_path: Path, data: Dict[str, Any]) -> None:
        with open(file_path, 'w', encoding='utf-8') as f:
            yaml.dump(data, f, allow_unicode=True, default_flow_style=False)
    
    def _get_scenario_dir(self, scenario_id: str) -> Path:
        if scenario_id in self._scenario_paths:
            return self._scenario_paths[scenario_id]
        
        raise ScenarioNotFoundError(f"场景 '{scenario_id}' 不存在")
    
    def _is_user_scenario(self, scenario_id: str) -> bool:
        if scenario_id not in self._scenario_paths:
            return False
        scenario_dir = self._scenario_paths[scenario_id]
        try:
            scenario_dir.relative_to(self.user_scenarios_dir)
            return True
        except ValueError:
            return False
    
    def validate_scenario_config(self, config: Dict[str, Any]) -> List[str]:
        errors = []
        
        for field in REQUIRED_SCENARIO_FIELDS:
            if field not in config:
                errors.append(f"缺少必需字段: {field}")
        
        if not config.get("id"):
            errors.append("场景ID不能为空")
        
        if not config.get("name"):
            errors.append("场景名称不能为空")
        
        if not isinstance(config.get("supported_operations"), list):
            errors.append("supported_operations 必须是数组")
        
        if not isinstance(config.get("supported_materials"), list):
            errors.append("supported_materials 必须是数组")
        
        if not isinstance(config.get("supported_tools"), list):
            errors.append("supported_tools 必须是数组")
        
        return errors
    
    def load_scenario(self, scenario_id: str) -> Dict[str, Any]:
        if scenario_id in self._scenario_cache:
            return self._scenario_cache[scenario_id]
        
        scenario_dir = self._get_scenario_dir(scenario_id)
        
        scenario_data = {
            "id": scenario_id,
            "scenario": self._load_json(scenario_dir / "scenario.json"),
            "constraints": self._load_json(scenario_dir / "constraints.json"),
            "cost_model": self._load_json(scenario_dir / "cost_model.json"),
            "prompts": self._load_yaml(scenario_dir / "prompts.yaml"),
            "validation_rules": self._load_json(scenario_dir / "validation_rules.json"),
            "is_user_scenario": self._is_user_scenario(scenario_id)
        }
        
        self._scenario_cache[scenario_id] = scenario_data
        
        return scenario_data
    
    def list_scenarios(self) -> List[Dict[str, Any]]:
        scenarios = []
        
        for scenario_id, scenario_dir in self._scenario_paths.items():
            try:
                scenario_json = self._load_json(scenario_dir / "scenario.json")
                scenarios.append({
                    "id": scenario_id,
                    "name": scenario_json.get("name", scenario_id),
                    "description": scenario_json.get("description", ""),
                    "supported_operations": scenario_json.get("supported_operations", []),
                    "supported_materials": scenario_json.get("supported_materials", []),
                    "supported_tools": scenario_json.get("supported_tools", []),
                    "version": scenario_json.get("version", "1.0.0"),
                    "is_user_scenario": self._is_user_scenario(scenario_id)
                })
            except Exception as e:
                scenarios.append({
                    "id": scenario_id,
                    "name": scenario_id,
                    "description": f"加载失败: {str(e)}",
                    "supported_operations": [],
                    "supported_materials": [],
                    "supported_tools": [],
                    "version": "unknown",
                    "is_user_scenario": self._is_user_scenario(scenario_id),
                    "error": str(e)
                })
        
        return scenarios
    
    def get_constraints(self, scenario_id: str, material: str = None, tool: str = None) -> Dict[str, Any]:
        scenario_data = self.load_scenario(scenario_id)
        constraints = scenario_data["constraints"]
        
        result = {
            "material_constraints": {},
            "tool_constraints": {},
            "objective_weights": constraints.get("objective_weights", {})
        }
        
        if material:
            material_constraints = constraints.get("material_constraints", {})
            if material in material_constraints:
                result["material_constraints"][material] = material_constraints[material]
            else:
                result["material_constraints"] = material_constraints
        else:
            result["material_constraints"] = constraints.get("material_constraints", {})
        
        if tool:
            tool_constraints = constraints.get("tool_constraints", {})
            if tool in tool_constraints:
                result["tool_constraints"][tool] = tool_constraints[tool]
            else:
                result["tool_constraints"] = tool_constraints
        else:
            result["tool_constraints"] = constraints.get("tool_constraints", {})
        
        return result
    
    def get_objective_weights(self, scenario_id: str) -> Dict[str, float]:
        scenario_data = self.load_scenario(scenario_id)
        return scenario_data["constraints"].get("objective_weights", {})
    
    def get_validation_rules(self, scenario_id: str) -> Dict[str, Any]:
        scenario_data = self.load_scenario(scenario_id)
        return scenario_data["validation_rules"]
    
    def get_prompts(self, scenario_id: str, prompt_type: str) -> str:
        scenario_data = self.load_scenario(scenario_id)
        prompts = scenario_data["prompts"]
        
        if prompt_type in prompts:
            return prompts[prompt_type]
        
        raise KeyError(f"提示词类型 '{prompt_type}' 在场景 '{scenario_id}' 中不存在")
    
    def get_materials(self, scenario_id: str) -> List[str]:
        scenario_data = self.load_scenario(scenario_id)
        return scenario_data["scenario"].get("supported_materials", [])
    
    def get_tools(self, scenario_id: str) -> List[str]:
        scenario_data = self.load_scenario(scenario_id)
        return scenario_data["scenario"].get("supported_tools", [])
    
    def get_cost_model(self, scenario_id: str) -> Dict[str, Any]:
        scenario_data = self.load_scenario(scenario_id)
        return scenario_data["cost_model"]
    
    def create_user_scenario(self, scenario_id: str, config: Dict[str, Any]) -> str:
        errors = self.validate_scenario_config(config.get("scenario", {}))
        if errors:
            raise ScenarioValidationError(f"场景配置验证失败: {'; '.join(errors)}")
        
        if config["scenario"]["id"] != scenario_id:
            raise ScenarioValidationError("scenario.json 中的 id 必须与场景目录名一致")
        
        if scenario_id in self._scenario_paths:
            if not self._is_user_scenario(scenario_id):
                raise ScenarioValidationError(f"场景 '{scenario_id}' 已存在，不能覆盖内置场景")
        
        scenario_dir = self.user_scenarios_dir / scenario_id
        scenario_dir.mkdir(parents=True, exist_ok=True)
        
        self._save_json(scenario_dir / "scenario.json", config.get("scenario", {}))
        self._save_json(scenario_dir / "constraints.json", config.get("constraints", {}))
        self._save_json(scenario_dir / "cost_model.json", config.get("cost_model", {}))
        self._save_yaml(scenario_dir / "prompts.yaml", config.get("prompts", {}))
        self._save_json(scenario_dir / "validation_rules.json", config.get("validation_rules", {}))
        
        self._scenario_paths[scenario_id] = scenario_dir
        self._scenario_cache.pop(scenario_id, None)
        
        return scenario_id
    
    def update_user_scenario(self, scenario_id: str, config: Dict[str, Any]) -> str:
        if not self._is_user_scenario(scenario_id):
            raise ScenarioNotFoundError(f"场景 '{scenario_id}' 不是用户场景，无法更新")
        
        errors = self.validate_scenario_config(config.get("scenario", {}))
        if errors:
            raise ScenarioValidationError(f"场景配置验证失败: {'; '.join(errors)}")
        
        scenario_dir = self._get_scenario_dir(scenario_id)
        
        self._save_json(scenario_dir / "scenario.json", config.get("scenario", {}))
        self._save_json(scenario_dir / "constraints.json", config.get("constraints", {}))
        self._save_json(scenario_dir / "cost_model.json", config.get("cost_model", {}))
        self._save_yaml(scenario_dir / "prompts.yaml", config.get("prompts", {}))
        self._save_json(scenario_dir / "validation_rules.json", config.get("validation_rules", {}))
        
        self._scenario_cache.pop(scenario_id, None)
        
        return scenario_id
    
    def delete_user_scenario(self, scenario_id: str) -> None:
        if not self._is_user_scenario(scenario_id):
            raise ScenarioNotFoundError(f"场景 '{scenario_id}' 不是用户场景，无法删除")
        
        scenario_dir = self._get_scenario_dir(scenario_id)
        
        shutil.rmtree(scenario_dir)
        
        self._scenario_paths.pop(scenario_id, None)
        self._scenario_cache.pop(scenario_id, None)
    
    def reload(self) -> None:
        self._scenario_cache.clear()
        self._discover_scenarios()
    
    def get_scenario_info(self, scenario_id: str) -> Dict[str, Any]:
        scenario_dir = self._get_scenario_dir(scenario_id)
        scenario_json = self._load_json(scenario_dir / "scenario.json")
        
        return {
            "id": scenario_id,
            "name": scenario_json.get("name", scenario_id),
            "description": scenario_json.get("description", ""),
            "supported_operations": scenario_json.get("supported_operations", []),
            "supported_materials": scenario_json.get("supported_materials", []),
            "supported_tools": scenario_json.get("supported_tools", []),
            "priority_objectives": scenario_json.get("priority_objectives", []),
            "version": scenario_json.get("version", "1.0.0"),
            "is_user_scenario": self._is_user_scenario(scenario_id)
        }


scenario_manager = ScenarioManager()
