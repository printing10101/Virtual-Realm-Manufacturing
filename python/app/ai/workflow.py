import time
import asyncio
from typing import Callable, Optional
from app.ai.agents import (
    AgentContext,
    UnderstandingAgent,
    PlanningAgent,
    ParameterAgent,
    NCAgent,
    VerificationAgent,
    RepairAgent
)
from app.core.task_manager import task_manager, TaskType, TaskStatus


class WorkflowOrchestrator:
    def __init__(self):
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

    async def execute_workflow(self, user_input: str, progress_callback: Callable = None) -> dict:
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
                    "status": f"failed: {str(e)}",
                    "elapsed_seconds": round(time.time() - start_time, 2),
                    "error": str(e)
                }

                if progress_callback:
                    progress_callback({
                        "current_stage": stage_name,
                        "stage_index": idx + 1,
                        "total_stages": total_stages,
                        "progress": ((idx + 1) / total_stages) * 100,
                        "status": f"failed: {str(e)}"
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

    async def execute_workflow_with_task(self, user_input: str, task_id: Optional[str] = None) -> dict:
        if not task_id:
            task_id = task_manager.create_task(TaskType.WORKFLOW_EXECUTION, {"user_input": user_input})
        
        await task_manager.update_progress(task_id, 0, "正在初始化工作流...")
        
        async def _run_workflow():
            context = AgentContext(user_input=user_input)
            stage_results = {}
            total_stages = len(self.workflow_stages)

            for idx, stage_name in enumerate(self.workflow_stages):
                task = task_manager.get_task(task_id)
                if task and task.status == TaskStatus.CANCELLED:
                    return {"cancelled": True, "stage_results": stage_results}

                agent = self.agents[stage_name]
                progress = (idx / total_stages) * 100
                await task_manager.update_progress(task_id, progress, f"正在执行: {stage_name}...")

                start_time = time.time()
                try:
                    context = await agent.execute(context)
                    elapsed = time.time() - start_time

                    stage_results[stage_name] = {
                        "status": context.stage_status,
                        "elapsed_seconds": round(elapsed, 2),
                        "output_summary": self._get_stage_summary(stage_name, context)
                    }

                    await task_manager.update_progress(
                        task_id, 
                        ((idx + 1) / total_stages) * 100, 
                        f"完成: {stage_name}"
                    )

                except Exception as e:
                    stage_results[stage_name] = {
                        "status": f"failed: {str(e)}",
                        "elapsed_seconds": round(time.time() - start_time, 2),
                        "error": str(e)
                    }
                    raise

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

        try:
            await task_manager.update_progress(task_id, 5, "开始执行工作流...")
            result = await task_manager.run_with_timeout(task_id, _run_workflow())
            
            if result.get("cancelled"):
                await task_manager.cancel_task(task_id)
                return result
            
            await task_manager.complete_task(task_id, result)
            return result
        except Exception as e:
            await task_manager.fail_task(task_id, str(e))
            raise

orchestrator = WorkflowOrchestrator()
