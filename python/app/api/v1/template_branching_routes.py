"""API routes for template branching system."""

from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.core.template_branching import get_branch_manager

router = APIRouter(prefix="/api/v1/templates/branches", tags=["template-branching"])

# Allow test override
_test_manager = None


def _get_manager():
    return _test_manager if _test_manager is not None else get_branch_manager()


class CreateBranchRequest(BaseModel):
    name: str
    base_branch: Optional[str] = None
    data: dict = Field(default_factory=dict)
    metadata: dict = Field(default_factory=dict)


class MergeBranchRequest(BaseModel):
    source_id: str
    target_id: str
    strategy: str = "overwrite"


class UpdateBranchRequest(BaseModel):
    data: dict


@router.post("/", status_code=201)
async def create_branch(req: CreateBranchRequest):
    manager = _get_manager()
    branch = manager.create_branch(
        name=req.name,
        base_branch=req.base_branch,
        data=req.data,
        metadata=req.metadata,
    )
    return {"branch": branch.to_dict()}


@router.get("/")
async def list_branches(type_filter: Optional[str] = None):
    manager = _get_manager()
    branches = manager.list_branches(type_filter=type_filter)
    return {"branches": [b.to_dict() for b in branches]}


@router.get("/{branch_id}")
async def get_branch(branch_id: str):
    manager = _get_manager()
    branch = manager.get_branch(branch_id)
    if branch is None:
        raise HTTPException(status_code=404, detail=f"Branch not found: {branch_id}")
    return {"branch": branch.to_dict()}


@router.get("/{branch_id}/log")
async def get_commit_log(branch_id: str):
    manager = _get_manager()
    branch = manager.get_branch(branch_id)
    if branch is None:
        raise HTTPException(status_code=404, detail=f"Branch not found: {branch_id}")
    return {"commit_log": manager.get_commit_log(branch_id)}


@router.post("/merge")
async def merge_branch(req: MergeBranchRequest):
    manager = _get_manager()
    result = manager.merge_branch(req.source_id, req.target_id, strategy=req.strategy)
    if result is None:
        raise HTTPException(status_code=404, detail="Source or target branch not found")
    return {"merged_branch": result.to_dict()}


@router.put("/{branch_id}")
async def update_branch(branch_id: str, req: UpdateBranchRequest):
    manager = _get_manager()
    result = manager.update_branch_data(branch_id, req.data)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Branch not found: {branch_id}")
    return {"branch": result.to_dict()}


@router.delete("/{branch_id}")
async def delete_branch(branch_id: str):
    manager = _get_manager()
    try:
        success = manager.delete_branch(branch_id)
        if not success:
            raise HTTPException(
                status_code=404, detail=f"Branch not found: {branch_id}"
            )
        return {"message": "Branch deleted"}
    except ValueError as e:
        raise HTTPException(status_code=403, detail=str(e))
