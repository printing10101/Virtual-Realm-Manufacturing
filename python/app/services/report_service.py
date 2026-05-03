import asyncio
from typing import Optional, Dict, Any, List
from app.core.task_manager import TaskManager
from app.core.workflow_logger import AIWorkflowLogger, StepType
from app.agents.report_agent import ReportAgent


class ReportGenerationService:
    def __init__(self, task_manager: TaskManager, workflow_logger: AIWorkflowLogger, config: Any):
        self.task_manager = task_manager
        self.logger = workflow_logger
        self.config = config
        self.report_agent = ReportAgent(task_manager, workflow_logger, config)
        self._reports: Dict[str, Dict] = {}

    async def generate_react_report(self, task_id: str, process_task_id: Optional[str] = None) -> str:
        report = await self.report_agent.generate_report(task_id, process_task_id)
        self._reports[task_id] = {
            "report": report,
            "reasoning_steps": self.report_agent.get_reasoning_steps()
        }
        return report

    def get_report(self, task_id: str) -> Optional[Dict]:
        return self._reports.get(task_id)

    def get_reasoning_steps(self, task_id: str) -> Optional[List[Dict]]:
        report = self._reports.get(task_id)
        return report.get("reasoning_steps") if report else None


report_service = ReportGenerationService
