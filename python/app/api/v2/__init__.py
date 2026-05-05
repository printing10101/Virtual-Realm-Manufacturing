"""
灵境制造 - API v2 路由
当前版本：v1
v2 版本预留，待后续开发
"""
from fastapi import APIRouter

router = APIRouter(prefix="/api/v2", tags=["API v2"])


@router.get("/health")
async def health_check_v2() -> dict[str, str]:
    """v2 健康检查（预留）"""
    return {"status": "planned", "version": "v2"}
