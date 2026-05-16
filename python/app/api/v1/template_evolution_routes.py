"""Template Evolution API Routes."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.core.template_evolution import get_evolution_engine
from app.core.response import success, error

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/templates/evolution", tags=["evolution"])


class MetricsUpdateRequest(BaseModel):
    metrics: Dict[str, Any] = Field(..., description="Metrics data")


class CreateSuggestionRequest(BaseModel):
    trigger_type: str = Field(..., description="Trigger type")
    evidence: Dict[str, Any] = Field(..., description="Evidence data")
    proposed_change: Dict[str, Any] = Field(..., description="Proposed change")


class ApplySuggestionRequest(BaseModel):
    suggestion_id: str = Field(..., description="Suggestion ID")
    branch_id: str = Field(..., description="Target branch ID")


@router.get("/suggestions")
def list_suggestions(status_filter: Optional[str] = None):
    """List evolution suggestions."""
    engine = get_evolution_engine()
    suggestions = engine.list_suggestions(status_filter=status_filter)
    return success(data=[s.to_dict() for s in suggestions])


@router.post("/suggestions")
def create_suggestion(req: CreateSuggestionRequest):
    """Create a new evolution suggestion."""
    engine = get_evolution_engine()
    suggestion = engine.create_suggestion(
        trigger_type=req.trigger_type,
        evidence=req.evidence,
        proposed_change=req.proposed_change,
    )
    return success(data=suggestion.to_dict())


@router.post("/suggestions/apply")
def apply_suggestion(req: ApplySuggestionRequest):
    """Apply an evolution suggestion to a branch."""
    engine = get_evolution_engine()
    result = engine.apply_suggestion(req.suggestion_id, req.branch_id)
    if result is None:
        return error(code="SUGGESTION_NOT_FOUND", message="Suggestion not found")
    return success(data=result.to_dict())


@router.post("/metrics")
def update_metrics(req: MetricsUpdateRequest):
    """Update metrics for trigger evaluation."""
    engine = get_evolution_engine()
    engine.update_metrics(req.metrics)
    return success(data={"updated": len(req.metrics)})


@router.post("/triggers/evaluate")
def evaluate_triggers():
    """Evaluate all evolution triggers."""
    engine = get_evolution_engine()
    new_suggestions = engine.evaluate_triggers()
    return success(
        data={
            "new_suggestions": len(new_suggestions),
            "suggestions": [s.to_dict() for s in new_suggestions],
        }
    )


@router.get("/history")
def get_history(branch_id: Optional[str] = None):
    """Get evolution history."""
    engine = get_evolution_engine()
    history = engine.get_evolution_history(branch_id=branch_id)
    return success(data=history)
