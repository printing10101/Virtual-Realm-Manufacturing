import logging
import time
from collections.abc import Callable

from app.ai.agents import (
    AgentContext,
    NCAgent,
    ParameterAgent,
    PlanningAgent,
    RepairAgent,
    UnderstandingAgent,
    VerificationAgent,
)
from app.ai.workflow_parallel import parallel_orchestrator

logger = logging.getLogger(__name__)

from app.core.task_manager import task_manager, TaskStatus


class WorkflowOrchestrator:
    def __init__(self, use_parallel: bool = True):
        self.use_parallel = use_parallel
        self.agents = {
            "understanding": UnderstandingAgent(),
            "planning": PlanningAgent(),
            "parameter": ParameterAgent(),
            "nc_generation": NCAgent(),
            "verification": VerificationAgent(),
            "repair": RepairAgent()
        }

        self.workflow_stages = [
            "understanding",
            "planning",
            "parameter",
            "nc_generation",
            "verification",
            "repair"
        ]

    async def execute_workflow(self, user_input: str, progress_callback: Callable | None = None) -> dict:
        if self.use_parallel:
            try:
                return await parallel_orchestrator.execute_workflow(user_input, progress_callback)
            except Exception as e:
                logger.warning(f"并行工作流执行失败，回退到串行模式: {e}")
                self.use_parallel = False

        context = AgentContext(user_input=user_input)
        stage_results = {}
        total_stages = len(self.workflow_stages)

        for idx, stage_name in enumerate(self.workflow_stages):
            agent = self.agents[stage_name]

            if progress_callback:
                progress_callback({
                    "current_stage": stage_name,
                    "stage_index": idx + 1,
                    "total_stages": total_stages,
                    "progress": (idx / total_stages) * 100,
                    "status": "running"
                })

            start_time = time.time()
            try:
                context = await agent.execute(context)
                elapsed = time.time() - start_time

                stage_results[stage_name] = {
                    "status": context.stage_status,
                    "elapsed_seconds": round(elapsed, 2),
                    "output_summary": self._get_stage_summary(stage_name, context)
                }

                if progress_callback:
                    progress_callback({
                        "current_stage": stage_name,
                        "stage_index": idx + 1,
                        "total_stages": total_stages,
                        "progress": ((idx + 1) / total_stages) * 100,
                        "status": context.stage_status
                    })

            except Exception as e:
                stage_results[stage_name] = {
                    "status": f"failed: {e!s}",
                    "elapsed_seconds": round(time.time() - start_time, 2),
                    "error": str(e)
                }

                if progress_callback:
                    progress_callback({
                        "current_stage": stage_name,
                        "stage_index": idx + 1,
                        "total_stages": total_stages,
                        "progress": ((idx + 1) / total_stages) * 100,
                        "status": f"failed: {e!s}"
                    })

                break

        return {
            "user_input": context.user_input,
            "extracted_params": context.extracted_params,
            "process_route": context.process_route,
            "cutting_parameters": context.cutting_parameters,
            "nc_code": context.nc_code,
            "verification_result": context.verification_result,
            "repair_suggestions": context.repair_suggestions,
            "stage_results": stage_results,
            "total_stages": total_stages,
            "completed_stages": len([s for s in stage_results.values() if "failed" not in s["status"]])
        }

    def _get_stage_summary(self, stage_name: str, context: AgentContext) -> dict:
        summaries = {
            "understanding": {
                "material": context.extracted_params.get("material", ""),
                "part_type": context.extracted_params.get("part_type", "")
            },
            "planning": {
                "route_steps": len(context.process_route)
            },
            "parameter": {
                "parameter_count": len(context.cutting_parameters) if isinstance(context.cutting_parameters, list) else 0
            },
            "nc_generation": {
                "nc_code_length": len(context.nc_code)
            },
            "verification": {
                "is_valid": context.verification_result.get("is_valid", False),
                "issue_count": len(context.verification_result.get("issues", []))
            },
            "repair": {
                "has_suggestions": len(context.repair_suggestions) > 0
            }
        }
        return summaries.get(stage_name, {})

    def _is_task_cancelled(self, task_id: str) -> bool:
        """检查任务是否已取消"""
        try:
            task = task_manager.get_task(task_id)
            return task is not None and task.status == TaskStatus.CANCELLED
        except Exception:
            return False

    async def execute_workflow_with_task(self, user_input: str, task_id: str | None = None) -> dict:
        """执行工作流并关联任务ID"""
        if self.use_parallel:
            try:
                return await parallel_orchestrator.execute_workflow_with_task(user_input, task_id)
            except Exception as e:
                logger.warning(f"并行工作流执行失败，回退到串行模式: {e}")
                self.use_parallel = False

        if task_id:
            if self._is_task_cancelled(task_id):
                return {"cancelled": True, "stage_results": {}}

        context = AgentContext(user_input=user_input)
        stage_results = {}
        total_stages = len(self.workflow_stages)

        for idx, stage_name in enumerate(self.workflow_stages):
            agent = self.agents[stage_name]

            start_time = time.time()
            try:
                context = await agent.execute(context)
                elapsed = time.time() - start_time

                stage_results[stage_name] = {
                    "status": context.stage_status,
                    "elapsed_seconds": round(elapsed, 2),
                    "output_summary": self._get_stage_summary(stage_name, context)
                }

            except Exception as e:
                stage_results[stage_name] = {
                    "status": f"failed: {e!s}",
                    "elapsed_seconds": round(time.time() - start_time, 2),
                    "error": str(e)
                }
                break

        if task_id:
            try:
                task_manager.update_task_status(
                    task_id,
                    TaskStatus.COMPLETED,
                    result={
                        "user_input": context.user_input,
                        "extracted_params": context.extracted_params,
                        "process_route": context.process_route,
                        "cutting_parameters": context.cutting_parameters,
                        "nc_code": context.nc_code,
                        "verification_result": context.verification_result,
                        "repair_suggestions": context.repair_suggestions,
                        "stage_results": stage_results,
                    }
                )
            except Exception:
                pass

        return {
            "user_input": context.user_input,
            "extracted_params": context.extracted_params,
            "process_route": context.process_route,
            "cutting_parameters": context.cutting_parameters,
            "nc_code": context.nc_code,
            "verification_result": context.verification_result,
            "repair_suggestions": context.repair_suggestions,
            "stage_results": stage_results,
            "total_stages": total_stages,
            "completed_stages": len([s for s in stage_results.values() if "failed" not in s["status"]])
        }

orchestrator = WorkflowOrchestrator(use_parallel=True)
