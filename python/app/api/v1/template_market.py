"""Template Marketplace API Routes — enhanced with evolution data, trending, subscriptions, export/import."""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.core.template_branching import get_branch_manager
from app.core.template_ab_testing import get_ab_testing
from app.core.response import success, error

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/template_market", tags=["template_market"])


class PublishRequest(BaseModel):
    branch_id: str = Field(..., description="Branch ID to publish")
    name: str = Field(..., description="Template name")
    category: str = Field(default="general", description="Template category")
    description: str = Field(default="", description="Template description")


class SubscribeRequest(BaseModel):
    category: str = Field(..., description="Category to subscribe")
    project_id: str = Field(..., description="Project ID")


class ExportRequest(BaseModel):
    branch_id: str = Field(..., description="Branch ID to export")
    include_history: bool = Field(default=True, description="Include evolution history")


class ImportRequest(BaseModel):
    template_data: Dict[str, Any] = Field(..., description="Template data to import")
    target_branch: Optional[str] = Field(default=None, description="Target branch name")
    adapt_params: bool = Field(default=True, description="Auto-adapt parameters")


_marketplace_data: Dict[str, Any] = {
    "templates": [],
    "subscriptions": [],
    "downloads": {},
    "trending": [],
}


@router.get("/trending")
def get_trending():
    """Get trending templates based on adoption rate."""
    trending = sorted(
        _marketplace_data.get("templates", []),
        key=lambda t: t.get("adoption_count", 0),
        reverse=True,
    )[:20]
    return success(data=trending)


@router.get("/templates/{branch_id}/metrics")
def get_template_metrics(branch_id: str):
    """Get effectiveness metrics for a template."""
    branch_mgr = get_branch_manager()
    branch = branch_mgr.get_branch(branch_id)
    if branch is None:
        return error(code="BRANCH_NOT_FOUND", message="Branch not found")

    ab_framework = get_ab_testing()
    exps = [
        e
        for e in ab_framework.list_experiments()
        if e.control_branch == branch_id or e.candidate_branch == branch_id
    ]

    total_experiments = len(exps)
    success_count = sum(
        1
        for e in exps
        if e.result == "winner_control" or e.result == "winner_candidate"
    )
    success_rate = success_count / max(total_experiments, 1)

    return success(
        data={
            "branch_id": branch_id,
            "name": branch.name,
            "success_rate": round(success_rate, 4),
            "total_experiments": total_experiments,
            "adoption_count": _marketplace_data.get("downloads", {}).get(branch_id, 0),
            "last_updated": branch.updated_at,
        }
    )


@router.post("/publish")
def publish_template(req: PublishRequest):
    """Publish a validated template to the marketplace."""
    branch_mgr = get_branch_manager()
    branch = branch_mgr.get_branch(req.branch_id)
    if branch is None:
        return error(code="BRANCH_NOT_FOUND", message="Branch not found")

    template_entry = {
        "branch_id": req.branch_id,
        "name": req.name,
        "category": req.category,
        "description": req.description,
        "published_at": time.time(),
        "adoption_count": 0,
        "source_branch": branch.name,
    }
    _marketplace_data["templates"].append(template_entry)
    logger.info("Template published: id=%s, name=%s", req.branch_id, req.name)
    return success(data=template_entry)


@router.post("/subscribe")
def subscribe(req: SubscribeRequest):
    """Subscribe to template category updates."""
    subscription = {
        "project_id": req.project_id,
        "category": req.category,
        "subscribed_at": time.time(),
    }
    _marketplace_data["subscriptions"].append(subscription)
    return success(data=subscription)


@router.get("/subscriptions/{project_id}")
def get_subscriptions(project_id: str):
    """Get subscriptions for a project."""
    subs = [
        s
        for s in _marketplace_data.get("subscriptions", [])
        if s["project_id"] == project_id
    ]
    return success(data=subs)


@router.post("/export/{branch_id}")
def export_template(branch_id: str, req: ExportRequest = None):
    """Export a template with optional evolution history."""
    if req is None:
        req = ExportRequest(branch_id=branch_id)

    branch_mgr = get_branch_manager()
    branch = branch_mgr.get_branch(branch_id)
    if branch is None:
        return error(code="BRANCH_NOT_FOUND", message="Branch not found")

    export_data = {
        "branch_id": branch_id,
        "name": branch.name,
        "template_data": branch.template_data,
        "metadata": branch.metadata,
        "created_at": branch.created_at,
        "updated_at": branch.updated_at,
    }

    if req.include_history:
        export_data["commit_log"] = branch.commit_log

        ab_framework = get_ab_testing()
        exps = [
            e
            for e in ab_framework.list_experiments()
            if e.control_branch == branch_id or e.candidate_branch == branch_id
        ]
        export_data["experiments"] = [e.to_dict() for e in exps]

    _marketplace_data["downloads"][branch_id] = (
        _marketplace_data.get("downloads", {}).get(branch_id, 0) + 1
    )

    return success(data=export_data)


@router.post("/import")
def import_template(req: ImportRequest):
    """Import a template with optional parameter adaptation."""
    branch_mgr = get_branch_manager()

    target_name = req.target_branch or f"imported_{int(time.time())}"
    data = req.template_data.copy()

    if req.adapt_params and "parameters" in data:
        data["parameters"] = _adapt_parameters(data["parameters"])

    branch = branch_mgr.create_branch(
        name=target_name,
        base_branch="main",
        data=data,
        metadata={"type": "imported", "imported_at": time.time()},
    )
    logger.info(
        "Template imported: branch_id=%s, name=%s", branch.branch_id, target_name
    )
    return success(data={"branch_id": branch.branch_id, "name": target_name})


@router.get("/sync/{branch_id}")
def sync_changes(branch_id: str):
    """Get incremental changes for a branch (delta sync)."""
    branch_mgr = get_branch_manager()
    branch = branch_mgr.get_branch(branch_id)
    if branch is None:
        return error(code="BRANCH_NOT_FOUND", message="Branch not found")

    return success(
        data={
            "branch_id": branch_id,
            "content_hash": branch_mgr._compute_content_hash(branch.template_data),
            "updated_at": branch.updated_at,
            "changes": branch.commit_log[-5:],
        }
    )


def _adapt_parameters(params: Dict[str, Any]) -> Dict[str, Any]:
    """Adapt template parameters for target environment."""
    adapted = params.copy()
    if "learning_rate" in adapted:
        adapted["learning_rate"] = min(adapted["learning_rate"], 0.1)
    if "batch_size" in adapted:
        adapted["batch_size"] = min(adapted["batch_size"], 128)
    if "timeout" in adapted:
        adapted["timeout"] = max(adapted["timeout"], 30)
    return adapted
