"""DXF 端到端批处理 API。

提供：
    - POST /api/v1/dxf/process    端到端处理单个 DXF
    - POST /api/v1/dxf/batch      批量处理（最多 20 个）
    - POST /api/v1/dxf/e2e-fixture   用 fixtures 跑端到端 smoke test

用于：CI、研发自测、研究模块的 shadow mode 触发。
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/dxf", tags=["dxf"])


# ---------------------------------------------------------------------------
# 请求/响应模型
# ---------------------------------------------------------------------------


class DxfProcessRequest(BaseModel):
    dxf_path: str
    output_dir: Optional[str] = None
    postprocessor: Optional[str] = "fanuc_0i"
    user_id: Optional[str] = None


class DxfBatchRequest(BaseModel):
    dxf_paths: list[str] = Field(..., min_length=1, max_length=20)
    output_dir: Optional[str] = None
    postprocessor: Optional[str] = "fanuc_0i"
    user_id: Optional[str] = None


class DxfE2EFixtureRequest(BaseModel):
    fixtures_dir: str = "data/test_fixtures"
    output_dir: str = "data/outputs/e2e"
    postprocessor: str = "fanuc_0i"
    user_id: Optional[str] = "e2e_runner"


# ---------------------------------------------------------------------------
# 端点
# ---------------------------------------------------------------------------


@router.post("/process")
def process_dxf(req: DxfProcessRequest) -> dict[str, Any]:
    """处理单个 DXF 文件（端到端）。"""
    from app.dxf.process_service import DxfProcessService

    svc = DxfProcessService()
    r = svc.process(
        dxf_path=req.dxf_path,
        output_dir=req.output_dir,
        postprocessor=req.postprocessor,
        user_id=req.user_id,
    )
    return r.to_dict()


@router.post("/batch")
def process_batch(req: DxfBatchRequest) -> dict[str, Any]:
    """批量处理多个 DXF（最多 20 个）。"""
    from app.dxf.process_service import DxfProcessService

    svc = DxfProcessService()
    results = []
    for p in req.dxf_paths:
        r = svc.process(
            dxf_path=p,
            output_dir=req.output_dir,
            postprocessor=req.postprocessor,
            user_id=req.user_id,
        )
        results.append(r.to_dict())
    success_count = sum(1 for x in results if x["success"])
    return {
        "total": len(results),
        "success": success_count,
        "failed": len(results) - success_count,
        "results": results,
    }


@router.post("/e2e-fixture")
def e2e_fixture(req: DxfE2EFixtureRequest) -> dict[str, Any]:
    """用 data/test_fixtures/ 下的所有 DXF 跑端到端测试。

    通常有 5+ 个 fixture，可以扩展到 20+。
    """
    fixtures_dir = Path(req.fixtures_dir)
    if not fixtures_dir.exists():
        raise HTTPException(
            status_code=404,
            detail=f"fixtures dir not found: {req.fixtures_dir}",
        )
    dxf_files = sorted(fixtures_dir.glob("*.dxf"))
    if not dxf_files:
        raise HTTPException(
            status_code=404,
            detail=f"no dxf files in {req.fixtures_dir}",
        )
    if len(dxf_files) > 20:
        dxf_files = dxf_files[:20]

    from app.dxf.process_service import DxfProcessService

    svc = DxfProcessService()
    results = []
    out_root = Path(req.output_dir)
    for dxf in dxf_files:
        # 每个 fixture 用自己的子目录
        sub = out_root / dxf.stem
        r = svc.process(
            dxf_path=dxf,
            output_dir=sub,
            postprocessor=req.postprocessor,
            user_id=req.user_id,
        )
        results.append(r.to_dict())
    success = sum(1 for x in results if x["success"])
    return {
        "fixtures_dir": str(fixtures_dir),
        "output_dir": str(out_root),
        "total": len(results),
        "success": success,
        "failed": len(results) - success,
        "postprocessor": req.postprocessor,
        "results": results,
    }


__all__ = ["router"]
