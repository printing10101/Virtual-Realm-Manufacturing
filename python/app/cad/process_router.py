from fastapi import APIRouter, Request

from app.core.response import success
from app.cad.process_route import generate_process_route

router = APIRouter(prefix="/api/process", tags=["Process"])


@router.post("/route")
async def process_route(request: Request):
    body = await request.json()
    item = body.get("item", "未知零件")
    result = generate_process_route(item)
    return success(data=result, message="工艺路线生成请求已接收")
