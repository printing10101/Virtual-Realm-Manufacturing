"""API routes for template branching system.

Refactored to use FastAPI dependency injection (Depends) instead of a
module-level ``_test_manager`` global variable.  Tests can override the
branch manager by using ``app.dependency_overrides[get_branch_manager]``.
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.templates.template_branching import (
    TemplateBranchManager,
    get_branch_manager,
)

router = APIRouter(prefix="/api/v1/templates/branches", tags=["template-branching"])


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
async def create_branch(
    req: CreateBranchRequest,
    manager: TemplateBranchManager = Depends(get_branch_manager),
):
    branch = manager.create_branch(
        name=req.name,
        base_branch=req.base_branch,
        data=req.data,
        metadata=req.metadata,
    )
    return {"branch": branch.to_dict()}


@router.get("/")
async def list_branches(
    type_filter: Optional[str] = None,
    manager: TemplateBranchManager = Depends(get_branch_manager),
):
    branches = manager.list_branches(type_filter=type_filter)
    return {"branches": [b.to_dict() for b in branches]}


@router.get("/{branch_id}")
async def get_branch(
    branch_id: str,
    manager: TemplateBranchManager = Depends(get_branch_manager),
):
    branch = manager.get_branch(branch_id)
    if branch is None:
        raise HTTPException(status_code=404, detail=f"Branch not found: {branch_id}")
    return {"branch": branch.to_dict()}


@router.get("/{branch_id}/log")
async def get_commit_log(
    branch_id: str,
    manager: TemplateBranchManager = Depends(get_branch_manager),
):
    branch = manager.get_branch(branch_id)
    if branch is None:
        raise HTTPException(status_code=404, detail=f"Branch not found: {branch_id}")
    return {"commit_log": manager.get_commit_log(branch_id)}


@router.post("/merge")
async def merge_branch(
    req: MergeBranchRequest,
    manager: TemplateBranchManager = Depends(get_branch_manager),
):
    result = manager.merge_branch(req.source_id, req.target_id, strategy=req.strategy)
    if result is None:
        raise HTTPException(status_code=404, detail="Source or target branch not found")
    return {"merged_branch": result.to_dict()}


@router.put("/{branch_id}")
async def update_branch(
    branch_id: str,
    req: UpdateBranchRequest,
    manager: TemplateBranchManager = Depends(get_branch_manager),
):
    result = manager.update_branch_data(branch_id, req.data)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Branch not found: {branch_id}")
    return {"branch": result.to_dict()}


@router.delete("/{branch_id}")
async def delete_branch(
    branch_id: str,
    manager: TemplateBranchManager = Depends(get_branch_manager),
):
    try:
        success = manager.delete_branch(branch_id)
        if not success:
            raise HTTPException(
                status_code=404, detail=f"Branch not found: {branch_id}"
            )
        return {"message": "Branch deleted"}
    except ValueError:
        # 修复：避免将内部异常细节（可能含路径/对象结构）泄露给客户端
        raise HTTPException(status_code=403, detail="Operation not permitted")
