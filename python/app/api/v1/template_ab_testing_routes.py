"""A/B Testing API Routes."""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.core.template_ab_testing import get_ab_testing
from app.core.response import success, error

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/templates/ab_tests", tags=["ab_testing"])


class CreateExperimentRequest(BaseModel):
    name: str = Field(..., description="Experiment name")
    control_branch: str = Field(..., description="Control branch ID")
    candidate_branch: str = Field(..., description="Candidate branch ID")
    traffic_split: float = Field(
        default=0.10, description="Traffic split for candidate (0.0-1.0)"
    )


class RecordExecutionRequest(BaseModel):
    experiment_id: str = Field(..., description="Experiment ID")
    branch: str = Field(..., description="Branch used (control/candidate)")
    execution_time: float = Field(..., description="Execution time in seconds")
    success: bool = Field(default=True, description="Whether execution succeeded")
    resource_cost: float = Field(default=0.0, description="Resource cost")


class AssignBranchRequest(BaseModel):
    project_id: str = Field(..., description="Project ID")


@router.post("")
def create_experiment(req: CreateExperimentRequest):
    """Create a new A/B experiment."""
    framework = get_ab_testing()
    exp = framework.create_experiment(
        name=req.name,
        control_branch=req.control_branch,
        candidate_branch=req.candidate_branch,
        traffic_split=req.traffic_split,
    )
    return success(data=exp.to_dict())


@router.post("/record")
def record_execution(req: RecordExecutionRequest):
    """Record an execution in an experiment."""
    framework = get_ab_testing()
    framework.record_execution(
        experiment_id=req.experiment_id,
        branch=req.branch,
        metrics={
            "execution_time": req.execution_time,
            "success": req.success,
            "resource_cost": req.resource_cost,
        },
    )
    return success(data={"recorded": True})


@router.post("/assign")
def assign_branch(req: AssignBranchRequest):
    """Assign a project to a branch in all active experiments."""
    framework = get_ab_testing()
    results = {}
    for exp in framework.get_active_experiments():
        branch = framework.assign_branch(req.project_id, exp.experiment_id)
        results[exp.experiment_id] = branch
    return success(data=results)


@router.get("")
def list_experiments(status: Optional[str] = None):
    """List experiments."""
    framework = get_ab_testing()
    exps = framework.list_experiments(status_filter=status)
    return success(data=[e.to_dict() for e in exps])


@router.get("/{experiment_id}")
def get_experiment(experiment_id: str):
    """Get experiment details."""
    framework = get_ab_testing()
    result = framework.get_experiment_results(experiment_id)
    if result is None:
        return error(code="EXPERIMENT_NOT_FOUND", message="Experiment not found")
    return success(data=result)


@router.post("/{experiment_id}/evaluate")
def evaluate_experiment(experiment_id: str):
    """Evaluate an experiment."""
    framework = get_ab_testing()
    result = framework.evaluate(experiment_id)
    if result is None:
        return error(code="EXPERIMENT_NOT_FOUND", message="Experiment not found")
    return success(data=result)


@router.post("/{experiment_id}/conclude")
def conclude_experiment(experiment_id: str):
    """Auto-conclude an experiment (merge or rollback)."""
    framework = get_ab_testing()
    exp = framework.auto_conclude(experiment_id)
    if exp is None:
        return error(
            code="EXPERIMENT_NOT_FOUND", message="Experiment not found or not running"
        )
    return success(data=exp.to_dict())
