"""日志查询端点（ring buffer 统计与明细）。"""
from fastapi import APIRouter, Query

from app.core.request_id import get_request_id

router = APIRouter(prefix="/api/v1/logs", tags=["Logs"])


def _ring_log():
    """惰性导入 ring_log 实例，避免与 main.py 循环导入。"""
    from app.main import ring_log
    return ring_log


@router.get("/stats")
async def logs_stats():
    return {
        "code": 0,
        "message": "OK",
        "data": _ring_log().stats(),
        "request_id": get_request_id(),
    }


@router.get("/{buffer_type}")
async def logs_query(
    buffer_type: str,
    since: str | None = Query(None),
    level: str | None = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
):
    result = _ring_log().query(
        buffer_type=buffer_type,
        since=since,
        level=level,
        limit=limit,
        offset=offset,
    )
    return {"code": 0, "message": "OK", "data": result, "request_id": get_request_id()}
