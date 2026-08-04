"""系统信息端点（version / info）。"""

from fastapi import APIRouter

from app.version import get_version_info

router = APIRouter(prefix="/api/v1/system", tags=["System"])


@router.get("/version")
async def system_version():
    return get_version_info()
