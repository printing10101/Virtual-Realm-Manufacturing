from typing import List, Optional, Dict, Any
from app.core.task_manager import TaskManager
from app.core.workflow_logger import AIWorkflowLogger, StepType


class KnowledgeService:
    def __init__(self, task_manager: TaskManager, workflow_logger: AIWorkflowLogger, config: Any):
        self.task_manager = task_manager
        self.logger = workflow_logger
        self.config = config
        self._materials: Dict[str, Dict] = {}
        self._tools: Dict[str, Dict] = {}
        self._constraints: Dict[str, Dict] = {}

    async def create_material(self, task_id: str, material: Dict[str, Any]) -> Dict:
        with self.logger.log_step(
            task_id, "knowledge_service", StepType.CONSTRAINT_PARSE,
            input_data={"action": "create_material", "material_name": material.get("name")}
        ):
            material_id = material.get("id", f"mat_{len(self._materials) + 1}")
            self._materials[material_id] = material
            return {"id": material_id, **material}

    async def get_material(self, task_id: str, material_id: str) -> Optional[Dict]:
        with self.logger.log_step(
            task_id, "knowledge_service", StepType.CONSTRAINT_PARSE,
            input_data={"action": "get_material", "material_id": material_id}
        ):
            return self._materials.get(material_id)

    async def list_materials(self, task_id: str) -> List[Dict]:
        with self.logger.log_step(
            task_id, "knowledge_service", StepType.CONSTRAINT_PARSE,
            input_data={"action": "list_materials"}
        ):
            return list(self._materials.values())

    async def delete_material(self, task_id: str, material_id: str) -> bool:
        with self.logger.log_step(
            task_id, "knowledge_service", StepType.CONSTRAINT_PARSE,
            input_data={"action": "delete_material", "material_id": material_id}
        ):
            if material_id in self._materials:
                del self._materials[material_id]
                return True
            return False

    async def create_tool(self, task_id: str, tool: Dict[str, Any]) -> Dict:
        with self.logger.log_step(
            task_id, "knowledge_service", StepType.CONSTRAINT_PARSE,
            input_data={"action": "create_tool", "tool_name": tool.get("name")}
        ):
            tool_id = tool.get("id", f"tool_{len(self._tools) + 1}")
            self._tools[tool_id] = tool
            return {"id": tool_id, **tool}

    async def get_tool(self, task_id: str, tool_id: str) -> Optional[Dict]:
        with self.logger.log_step(
            task_id, "knowledge_service", StepType.CONSTRAINT_PARSE,
            input_data={"action": "get_tool", "tool_id": tool_id}
        ):
            return self._tools.get(tool_id)

    async def list_tools(self, task_id: str) -> List[Dict]:
        with self.logger.log_step(
            task_id, "knowledge_service", StepType.CONSTRAINT_PARSE,
            input_data={"action": "list_tools"}
        ):
            return list(self._tools.values())

    async def delete_tool(self, task_id: str, tool_id: str) -> bool:
        with self.logger.log_step(
            task_id, "knowledge_service", StepType.CONSTRAINT_PARSE,
            input_data={"action": "delete_tool", "tool_id": tool_id}
        ):
            if tool_id in self._tools:
                del self._tools[tool_id]
                return True
            return False

    async def create_constraint(self, task_id: str, constraint: Dict[str, Any]) -> Dict:
        with self.logger.log_step(
            task_id, "knowledge_service", StepType.CONSTRAINT_PARSE,
            input_data={"action": "create_constraint", "constraint_type": constraint.get("type")}
        ):
            constraint_id = constraint.get("id", f"con_{len(self._constraints) + 1}")
            self._constraints[constraint_id] = constraint
            return {"id": constraint_id, **constraint}

    async def get_constraint(self, task_id: str, constraint_id: str) -> Optional[Dict]:
        with self.logger.log_step(
            task_id, "knowledge_service", StepType.CONSTRAINT_PARSE,
            input_data={"action": "get_constraint", "constraint_id": constraint_id}
        ):
            return self._constraints.get(constraint_id)

    async def list_constraints(self, task_id: str) -> List[Dict]:
        with self.logger.log_step(
            task_id, "knowledge_service", StepType.CONSTRAINT_PARSE,
            input_data={"action": "list_constraints"}
        ):
            return list(self._constraints.values())

    async def delete_constraint(self, task_id: str, constraint_id: str) -> bool:
        with self.logger.log_step(
            task_id, "knowledge_service", StepType.CONSTRAINT_PARSE,
            input_data={"action": "delete_constraint", "constraint_id": constraint_id}
        ):
            if constraint_id in self._constraints:
                del self._constraints[constraint_id]
                return True
            return False


knowledge_service = KnowledgeService
