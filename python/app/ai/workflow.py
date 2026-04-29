import time
from typing import Callable
from app.ai.agents import (
    AgentContext,
    UnderstandingAgent,
    PlanningAgent,
    ParameterAgent,
    NCAgent,
    VerificationAgent,
    RepairAgent
)


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


orchestrator = WorkflowOrchestrator()
