"""DXF 端到端批处理 API。

提供：
    - POST /api/v1/dxf/process    端到端处理单个 DXF
    - POST /api/v1/dxf/batch      批量处理（最多 20 个）
    - POST /api/v1/dxf/e2e-fixture   用 fixtures 跑端到端 smoke test

用于：CI、研发自测、研究模块的 shadow mode 触发。
"""

import logging
import os
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator

from app.auth.permissions import require_permission
from app.utils.utils import validate_user_path
from app.core.safe_errors import safe_error_message

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/dxf",
    tags=["dxf"],
    dependencies=[Depends(require_permission("dxf:read"))],
)


# 路径安全：防止路径遍历攻击

# 允许的 DXF 根目录（项目根 + data/ 子目录）。生产环境可通过环境变量覆盖。
_ALLOWED_DXF_BASE_DIRS: list[Path] = [
    (Path(os.getenv("LNN_PROJECT_ROOT", Path(__file__).resolve().parents[4]))).resolve(),
    (Path(os.getenv("LNN_DATA_DIR", "data"))).resolve(),
]


def _validate_dxf_path(user_path: str) -> Path:
    """校验用户提供的 DXF 路径，防止路径遍历攻击。

    规则：
        1. 必须是 .dxf 扩展名
        2. 解析后的绝对路径必须位于 _ALLOWED_DXF_BASE_DIRS 之一之下
        3. 拒绝包含 .. 或绝对路径逃逸的输入

    委托给统一的 ``app.utils.utils.validate_user_path`` 实现。

    Args:
        user_path: 用户提交的 DXF 文件路径（相对或绝对）

    Returns:
        校验通过后的 Path 对象

    Raises:
        HTTPException: 400 当路径不合法或逃逸允许范围
    """
    try:
        return validate_user_path(
            user_path=user_path,
            allowed_base_dirs=_ALLOWED_DXF_BASE_DIRS,
            allowed_extensions={".dxf"},
            project_root=_ALLOWED_DXF_BASE_DIRS[0],
        )
    except ValueError as exc:
        # 包装异常消息，避免直接回显内部错误细节
        safe = safe_error_message(exc, context="dxf_pipeline.validate_user_path", fallback="DXF 路径校验失败")
        raise HTTPException(
            status_code=400,
            detail=safe["message"],
            headers={"X-Error-ID": safe["error_id"]},
        ) from exc


# 请求/响应模型


class DxfProcessRequest(BaseModel):
    dxf_path: str
    output_dir: str | None = None
    postprocessor: str | None = "fanuc_0i"
    user_id: str | None = None

    @field_validator("dxf_path")
    @classmethod
    def _validate_dxf_path_field(cls, v: str) -> str:
        """在模型层校验 DXF 路径，防止路径遍历。"""
        _validate_dxf_path(v)  # 抛出 HTTPException 即终止
        return v


class DxfBatchRequest(BaseModel):
    dxf_paths: list[str] = Field(..., min_length=1, max_length=20)
    output_dir: str | None = None
    postprocessor: str | None = "fanuc_0i"
    user_id: str | None = None

    @field_validator("dxf_paths")
    @classmethod
    def _validate_dxf_paths_field(cls, v: list[str]) -> list[str]:
        """批量校验每个 DXF 路径。"""
        for p in v:
            _validate_dxf_path(p)
        return v


class DxfE2EFixtureRequest(BaseModel):
    fixtures_dir: str = "data/test_fixtures"
    output_dir: str = "data/outputs/e2e"
    postprocessor: str = "fanuc_0i"
    user_id: str | None = "e2e_runner"


# 端点


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
            detail="指定的 fixtures 目录不存在，请检查路径配置",
        )
    dxf_files = sorted(fixtures_dir.glob("*.dxf"))
    if not dxf_files:
        raise HTTPException(
            status_code=404,
            detail="指定目录中未找到任何 DXF 文件",
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
