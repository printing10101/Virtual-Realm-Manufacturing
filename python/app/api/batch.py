"""
批量请求处理接口

提供请求合并机制，将多个独立API请求合并为一次HTTP调用，
减少网络开销和服务器负载。
"""
import asyncio
import logging
from typing import Any

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.core.response import success

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/batch", tags=["Batch"])

BATCH_TIMEOUT = 30
SUB_REQUEST_TIMEOUT = 10
MAX_CONCURRENT = 5


class SubRequest(BaseModel):
    """子请求模型"""
    id: str = Field(..., description="唯一请求标识符")
    method: str = Field(..., description="HTTP方法(GET/POST/PUT/DELETE等)")
    path: str = Field(..., description="API请求路径")
    headers: dict[str, str] | None = Field(default=None, description="请求头信息")
    body: dict[str, Any] | None = Field(default=None, description="请求体数据")


class BatchExecuteRequest(BaseModel):
    """批量请求模型"""
    requests: list[SubRequest] = Field(..., description="子请求列表", min_length=1, max_length=20)


class SubError(BaseModel):
    """子请求错误信息"""
    code: str = Field(..., description="错误码")
    message: str = Field(..., description="错误信息")


class SubResponse(BaseModel):
    """子请求响应模型"""
    id: str = Field(..., description="请求标识符")
    status: int = Field(..., description="HTTP状态码")
    data: Any | None = Field(default=None, description="成功时的响应数据")
    error: SubError | None = Field(default=None, description="失败时的错误信息")


class BatchExecuteResponse(BaseModel):
    """批量响应模型"""
    results: list[SubResponse] = Field(..., description="子请求响应列表")


async def execute_sub_request(
    request: SubRequest,
    base_url: str
) -> SubResponse:
    """
    执行单个子请求

    Args:
        request: 子请求对象
        base_url: 基础URL

    Returns:
        子请求响应对象
    """
    try:
        async with httpx.AsyncClient(timeout=SUB_REQUEST_TIMEOUT) as client:
            url = f"{base_url}{request.path}"

            kwargs: dict[str, Any] = {
                "method": request.method.lower(),
                "url": url,
            }

            if request.headers:
                kwargs["headers"] = request.headers

            if request.body and request.method.upper() in ["POST", "PUT", "PATCH"]:
                kwargs["json"] = request.body

            response = await client.request(**kwargs)

            if response.status_code >= 400:
                error_data = response.json() if response.content else {}
                return SubResponse(
                    id=request.id,
                    status=response.status_code,
                    data=None,
                    error=SubError(
                        code=str(response.status_code),
                        message=error_data.get("message", f"HTTP {response.status_code} 错误"),
                    ),
                )

            return SubResponse(
                id=request.id,
                status=response.status_code,
                data=response.json(),
                error=None,
            )

    except httpx.TimeoutException:
        logger.warning(f"子请求超时: {request.method} {request.path}")
        return SubResponse(
            id=request.id,
            status=408,
            data=None,
            error=SubError(
                code="TIMEOUT",
                message=f"请求超时 ({SUB_REQUEST_TIMEOUT}s)",
            ),
        )

    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP状态错误: {e.response.status_code} - {request.path}")
        return SubResponse(
            id=request.id,
            status=e.response.status_code,
            data=None,
            error=SubError(
                code=str(e.response.status_code),
                message=f"HTTP {e.response.status_code} 错误",
            ),
        )

    except Exception as e:
        logger.error(f"子请求执行失败: {request.method} {request.path} - {e!s}")
        return SubResponse(
            id=request.id,
            status=500,
            data=None,
            error=SubError(
                code="INTERNAL_ERROR",
                message=f"请求执行失败: {e!s}",
            ),
        )


@router.post("/execute", response_model=BatchExecuteResponse)
async def batch_execute(batch_request: BatchExecuteRequest):
    """
    批量执行API请求

    接收多个子请求，并行执行后统一返回结果。
    单个请求失败不影响其他请求的处理。
    """
    if not batch_request.requests:
        raise HTTPException(
            status_code=400,
            detail="请求列表不能为空"
        )

    if len(batch_request.requests) > 20:
        raise HTTPException(
            status_code=400,
            detail="单次批量请求最多支持20个子请求"
        )

    logger.info(f"批量请求开始: {len(batch_request.requests)} 个子请求")

    base_url = "http://localhost:8000"

    semaphore = asyncio.Semaphore(MAX_CONCURRENT)

    async def limited_execute(req: SubRequest) -> SubResponse:
        async with semaphore:
            return await execute_sub_request(req, base_url)

    tasks = [limited_execute(req) for req in batch_request.requests]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    final_results = []
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            logger.error(f"批量请求中第 {i} 个请求异常: {result!s}")
            final_results.append(SubResponse(
                id=batch_request.requests[i].id,
                status=500,
                data=None,
                error=SubError(
                    code="BATCH_ERROR",
                    message=f"批量处理异常: {result!s}",
                ),
            ))
        else:
            final_results.append(result)

    logger.info(f"批量请求完成: {len(final_results)} 个结果")

    return success(data={"results": [r.model_dump() for r in final_results]})
