"""Agent Gateway Orchestrator.

High-level orchestration layer that chains business pipeline steps:
DXF parsing -> process understanding -> parameter recommendation -> G-code generation.

Supports three orchestration patterns:
- Sequential chain: linear step-by-step execution
- Conditional branching: different paths based on material/feature type
- Error fallback: degradation when a step fails

Provides unified interface for MCP Server tools and frontend API.
"""

from __future__ import annotations

import json
import logging
import os
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Optional

from app.core.safe_errors import safe_error_message

logger = logging.getLogger(__name__)


class StepStatus(str, Enum):
    """Pipeline step execution status."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    FALLBACK = "fallback"


class OrchestratorMode(str, Enum):
    """Orchestration execution mode."""

    SEQUENTIAL = "sequential"
    CONDITIONAL = "conditional"


@dataclass
class StepResult:
    """Result from a single pipeline step."""

    step_name: str
    status: StepStatus
    output: dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    duration_ms: float = 0.0
    started_at: Optional[float] = None
    completed_at: Optional[float] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "step_name": self.step_name,
            "status": self.status.value,
            "output": self.output,
            "error": self.error,
            "duration_ms": round(self.duration_ms, 2),
        }


@dataclass
class PipelineResult:
    """Result from a complete pipeline execution."""

    pipeline_id: str
    success: bool
    steps: list[StepResult] = field(default_factory=list)
    final_output: dict[str, Any] = field(default_factory=dict)
    total_duration_ms: float = 0.0
    fallback_triggered: bool = False
    fallback_reason: str = ""
    trace_id: str = ""
    timestamp: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "pipeline_id": self.pipeline_id,
            "success": self.success,
            "steps": [s.to_dict() for s in self.steps],
            "final_output": self.final_output,
            "total_duration_ms": round(self.total_duration_ms, 2),
            "fallback_triggered": self.fallback_triggered,
            "fallback_reason": self.fallback_reason,
            "trace_id": self.trace_id,
            "timestamp": self.timestamp,
        }


class AgentOrchestrator:
    """Agent Gateway orchestrator for multi-step manufacturing pipelines.

    Chains business logic steps (DXF parsing, process understanding,
    parameter recommendation, G-code generation) with error handling
    and execution tracing.
    """

    def __init__(self, trace_log_dir: Optional[str] = None):
        self._trace_log_dir = trace_log_dir or os.path.join(
            os.getcwd(), "data", "traces"
        )
        self._pipeline_history: list[PipelineResult] = []
        self._step_registry: dict[str, Callable] = {}
        self._validate_dependencies()
        self._register_default_steps()

    def _validate_dependencies(self) -> None:
        """Validate that required pipeline step modules are available.
        
        Logs warnings for missing modules but does not prevent initialization,
        as modules may be loaded lazily at runtime.
        """
        required_modules = [
            ("app.dxf.process_service", "DXF processing"),
            ("app.ai.process_understanding.engine", "Process understanding"),
            ("app.process_planning.pipeline", "Process planning"),
            ("app.process_planning.gcode_generator", "G-code generation"),
        ]
        
        missing = []
        for module_name, description in required_modules:
            try:
                __import__(module_name)
            except ImportError:
                missing.append((module_name, description))
        
        if missing:
            logger.warning(
                "Some pipeline dependencies are not available: %s. "
                "Pipeline steps using these modules will use stub implementations.",
                ", ".join(f"{desc} ({mod})" for mod, desc in missing)
            )

    def _register_default_steps(self) -> None:
        """Register default pipeline step handlers."""
        self._step_registry["dxf_parse"] = self._step_dxf_parse
        self._step_registry["process_understanding"] = self._step_process_understanding
        self._step_registry["parameter_recommend"] = self._step_parameter_recommend
        self._step_registry["gcode_generate"] = self._step_gcode_generate

    def register_step(self, name: str, handler: Callable) -> None:
        """Register a custom pipeline step handler."""
        self._step_registry[name] = handler

    async def execute_pipeline(
        self,
        pipeline_type: str,
        input_data: dict[str, Any],
        mode: OrchestratorMode = OrchestratorMode.SEQUENTIAL,
    ) -> PipelineResult:
        """Execute a manufacturing pipeline.

        Args:
            pipeline_type: Type of pipeline ("dxf_to_gcode", "process_plan", etc.)
            input_data: Input parameters for the pipeline
            mode: Orchestration mode (sequential or conditional)

        Returns:
            PipelineResult with execution details and trace
        """
        pipeline_id = f"pipe_{datetime.now().strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:6]}"
        trace_id = f"trace_{uuid.uuid4().hex[:12]}"
        start_time = time.perf_counter()

        result = PipelineResult(
            pipeline_id=pipeline_id,
            success=False,
            trace_id=trace_id,
            timestamp=time.time(),
        )

        try:
            steps = self._get_pipeline_steps(pipeline_type, input_data, mode)
            context: dict[str, Any] = {"input": input_data}

            for step_name, step_config in steps:
                step_result = await self._execute_step(
                    step_name, step_config, context, pipeline_id
                )
                result.steps.append(step_result)

                if step_result.status == StepStatus.FAILED:
                    if step_config.get("optional", False):
                        step_result.status = StepStatus.SKIPPED
                        logger.warning(
                            "Optional step '%s' failed, skipping: %s",
                            step_name,
                            step_result.error,
                        )
                        continue
                    result.fallback_triggered = True
                    result.fallback_reason = f"Step '{step_name}' failed: {step_result.error}"
                    break

                context[step_name] = step_result.output

            result.success = all(
                s.status in (StepStatus.COMPLETED, StepStatus.SKIPPED)
                for s in result.steps
            )
            result.final_output = self._extract_final_output(context, result.steps)

        except Exception as exc:
            logger.exception("Pipeline execution failed: %s", exc)
            result.fallback_triggered = True
            result.fallback_reason = f"Pipeline error: {exc}"

        result.total_duration_ms = (time.perf_counter() - start_time) * 1000
        self._pipeline_history.append(result)
        self._write_trace(result)

        return result

    def _get_pipeline_steps(
        self,
        pipeline_type: str,
        input_data: dict[str, Any],
        mode: OrchestratorMode,
    ) -> list[tuple[str, dict[str, Any]]]:
        """Determine pipeline steps based on type and mode."""
        if pipeline_type == "dxf_to_gcode":
            return [
                ("dxf_parse", {"input_key": "dxf_path", "optional": False}),
                ("process_understanding", {"input_key": "dxf_parse", "optional": False}),
                ("parameter_recommend", {"input_key": "process_understanding", "optional": False}),
                ("gcode_generate", {"input_key": "parameter_recommend", "optional": False}),
            ]
        elif pipeline_type == "process_plan":
            return [
                ("process_understanding", {"input_key": "description", "optional": False}),
                ("parameter_recommend", {"input_key": "process_understanding", "optional": False}),
            ]
        else:
            logger.warning("Unknown pipeline type '%s', using empty steps", pipeline_type)
            return []

    async def _execute_step(
        self,
        step_name: str,
        config: dict[str, Any],
        context: dict[str, Any],
        pipeline_id: str,
    ) -> StepResult:
        """Execute a single pipeline step."""
        step_result = StepResult(
            step_name=step_name,
            status=StepStatus.PENDING,
            started_at=time.perf_counter(),
        )

        handler = self._step_registry.get(step_name)
        if not handler:
            step_result.status = StepStatus.FAILED
            step_result.error = f"No handler registered for step '{step_name}'"
            return step_result

        step_result.status = StepStatus.RUNNING
        try:
            input_key = config.get("input_key", step_name)
            step_input = context.get(input_key, context.get("input", {}))
            output = await handler(step_input, context)
            step_result.output = output if isinstance(output, dict) else {"result": output}
            step_result.status = StepStatus.COMPLETED
        except Exception as exc:
            step_result.status = StepStatus.FAILED
            step_result.error = safe_error_message(exc)
            logger.warning("Step '%s' failed: %s", step_name, exc)

        step_result.completed_at = time.perf_counter()
        step_result.duration_ms = (step_result.completed_at - step_result.started_at) * 1000
        return step_result

    # -----------------------------------------------------------------------
    # Default step handlers
    # -----------------------------------------------------------------------

    async def _step_dxf_parse(
        self, input_data: Any, context: dict[str, Any]
    ) -> dict[str, Any]:
        """Parse DXF file and extract features."""
        dxf_path = input_data if isinstance(input_data, str) else input_data.get("dxf_path", "")
        if not dxf_path:
            raise ValueError("dxf_path is required")

        try:
            from app.dxf.process_service import DxfProcessService

            svc = DxfProcessService()
            parse_result = svc.process_dxf(dxf_path)
            return {
                "status": "success",
                "features": parse_result.get("features", []),
                "metadata": parse_result.get("metadata", {}),
                "dxf_path": dxf_path,
            }
        except ImportError:
            logger.warning("DXF module not available, using stub")
            return {
                "status": "stub",
                "features": [],
                "metadata": {"dxf_path": dxf_path},
                "dxf_path": dxf_path,
            }

    async def _step_process_understanding(
        self, input_data: Any, context: dict[str, Any]
    ) -> dict[str, Any]:
        """Analyze part features and determine process requirements."""
        try:
            from app.ai.process_understanding.engine import ProcessUnderstandingEngine

            engine = ProcessUnderstandingEngine()
            description = input_data.get("description", "") if isinstance(input_data, dict) else str(input_data)
            result = engine.process(description)
            return {
                "status": "success",
                "task_type": result.task_type if hasattr(result, "task_type") else "unknown",
                "intent": result.intent if hasattr(result, "intent") else "",
                "entities": result.entities if hasattr(result, "entities") else {},
                "confidence": result.confidence if hasattr(result, "confidence") else 0.0,
            }
        except ImportError:
            logger.warning("Process understanding module not available, using stub")
            return {
                "status": "stub",
                "task_type": "unknown",
                "intent": "process_plan",
                "entities": {},
                "confidence": 0.5,
            }

    async def _step_parameter_recommend(
        self, input_data: Any, context: dict[str, Any]
    ) -> dict[str, Any]:
        """Recommend machining parameters based on features and material."""
        try:
            from app.process_planning.pipeline import ProcessPlanningPipeline

            pipeline = ProcessPlanningPipeline()
            part_desc = input_data if isinstance(input_data, dict) else {"description": str(input_data)}
            plan_result = pipeline.run(part_desc)
            return {
                "status": "success",
                "parameters": plan_result.get("parameters", {}),
                "operations": plan_result.get("operations", []),
                "confidence": plan_result.get("confidence", 0.0),
            }
        except ImportError:
            logger.warning("Parameter recommendation module not available, using stub")
            return {
                "status": "stub",
                "parameters": {"cutting_speed": 100, "feed_rate": 0.1, "depth_of_cut": 1.0},
                "operations": [],
                "confidence": 0.3,
            }

    async def _step_gcode_generate(
        self, input_data: Any, context: dict[str, Any]
    ) -> dict[str, Any]:
        """Generate G-code from process plan and parameters."""
        try:
            from app.process_planning.gcode_generator import GCodeGenerator

            generator = GCodeGenerator()
            plan_data = input_data if isinstance(input_data, dict) else {}
            gcode_result = generator.generate(plan_data)
            return {
                "status": "success",
                "gcode": gcode_result.get("gcode", "") if isinstance(gcode_result, dict) else str(gcode_result),
                "metadata": gcode_result.get("metadata", {}) if isinstance(gcode_result, dict) else {},
            }
        except ImportError:
            logger.warning("G-code generator not available, using stub")
            return {
                "status": "stub",
                "gcode": "; G-code stub output\n; No generator available",
                "metadata": {"stub": True},
            }

    # -----------------------------------------------------------------------
    # Trace and history
    # -----------------------------------------------------------------------

    def _write_trace(self, result: PipelineResult) -> None:
        """Write pipeline execution trace to log file."""
        try:
            os.makedirs(self._trace_log_dir, exist_ok=True)
            trace_file = os.path.join(
                self._trace_log_dir,
                f"agent_trace_{datetime.now().strftime('%Y-%m-%d')}.jsonl",
            )
            with open(trace_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(result.to_dict(), ensure_ascii=False) + "\n")
        except (OSError, IOError, TypeError, ValueError) as exc:
            logger.error("Failed to write agent trace: %s", exc)

    def get_history(self, limit: int = 50) -> list[PipelineResult]:
        """Get recent pipeline execution history."""
        return self._pipeline_history[-limit:]

    def get_pipeline_history(self, limit: int = 50, offset: int = 0) -> list[PipelineResult]:
        """Get pipeline execution history with pagination.
        
        Args:
            limit: Maximum number of records to return
            offset: Number of records to skip
            
        Returns:
            List of PipelineResult records
        """
        total_records = self._pipeline_history
        start_idx = offset
        end_idx = offset + limit
        return total_records[start_idx:end_idx]

    def get_pipeline_trace(self, pipeline_id: str) -> dict[str, Any] | None:
        """Get detailed trace for a specific pipeline execution.
        
        Args:
            pipeline_id: The pipeline ID to look up
            
        Returns:
            Dictionary with trace details or None if not found
        """
        for result in self._pipeline_history:
            if result.pipeline_id == pipeline_id:
                return result.to_dict()
        return None

    def get_statistics(self) -> dict[str, Any]:
        """Get orchestrator statistics."""
        total = len(self._pipeline_history)
        successful = sum(1 for p in self._pipeline_history if p.success)
        fallback_count = sum(1 for p in self._pipeline_history if p.fallback_triggered)

        return {
            "total_pipelines": total,
            "successful_pipelines": successful,
            "failed_pipelines": total - successful,
            "fallback_count": fallback_count,
            "success_rate": successful / total if total > 0 else 0.0,
            "registered_steps": list(self._step_registry.keys()),
        }


# Singleton instance
_orchestrator: Optional[AgentOrchestrator] = None


def get_orchestrator() -> AgentOrchestrator:
    """Get the global orchestrator instance."""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = AgentOrchestrator()
    return _orchestrator
