"""统一异常处理器——将各类异常转换为标准化错误响应。

响应格式: {"code": <int>, "message": "...", "request_id": "<uuid>"}
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.exceptions import (
    AppException,
    InternalServerException,
    NotFoundException,
    ValidationException,
)
from app.core.repository.exceptions import RecordNotFoundError, RepositoryError
from app.core.response import error_response

logger = logging.getLogger(__name__)


_STARLETTE_HTTP_TO_CODE: dict[int, int] = {
    400: 1006,
    401: 1003,
    403: 1004,
    404: 1001,
    405: 1006,
    408: 2004,
    409: 1005,
    422: 1002,
    429: 1007,
    500: 2001,
    502: 2003,
    503: 2002,
    504: 2004,
}


def _build_json_response(
    code: int,
    message: str,
    http_status: int,
    detail: Any = None,
) -> JSONResponse:
    body = error_response(code=code, message=message, detail=detail)
    return JSONResponse(status_code=http_status, content=body)


async def app_exception_handler(_request: Request, exc: AppException) -> JSONResponse:
    logger.warning(
        "AppException caught: code=%d message=%s path=%s",
        exc.code,
        exc.message,
        _request.url.path,
    )
    return _build_json_response(
        code=exc.code,
        message=exc.message,
        http_status=exc.status_code,
        detail=exc.detail,
    )


async def http_exception_handler(
    _request: Request, exc: StarletteHTTPException
) -> JSONResponse:
    code = _STARLETTE_HTTP_TO_CODE.get(exc.status_code, 2001)
    message = str(exc.detail) if exc.detail else "请求处理异常"
    logger.warning(
        "HTTPException: status=%d message=%s path=%s",
        exc.status_code,
        message,
        _request.url.path,
    )
    return _build_json_response(
        code=code, message=message, http_status=exc.status_code
    )


async def validation_exception_handler(
    _request: Request, exc: RequestValidationError
) -> JSONResponse:
    errors = []
    for error in exc.errors():
        loc = " -> ".join(str(p) for p in error.get("loc", []))
        msg = error.get("msg", "校验失败")
        errors.append(f"{loc}: {msg}")
    detail = "; ".join(errors) if errors else str(exc)
    exc_obj = ValidationException(message="请求参数校验失败", detail=detail)
    logger.warning("Validation failed: %s", detail)
    return _build_json_response(
        code=exc_obj.code,
        message=exc_obj.message,
        http_status=exc_obj.status_code,
        detail=exc_obj.detail,
    )


async def generic_exception_handler(_request: Request, exc: Exception) -> JSONResponse:
    error_id = f"{id(exc):x}"
    logger.exception("Unhandled exception [id=%s] path=%s: %s", error_id, _request.url.path, exc)
    exc_obj = InternalServerException(
        message="服务器内部错误",
        detail={"error_id": error_id, "type": type(exc).__name__},
    )
    return _build_json_response(
        code=exc_obj.code,
        message=exc_obj.message,
        http_status=exc_obj.status_code,
        detail=exc_obj.detail,
    )


async def record_not_found_handler(
    _request: Request, exc: RecordNotFoundError
) -> JSONResponse:
    exc_obj = NotFoundException(message=str(exc))
    logger.warning("RecordNotFound: %s path=%s", exc, _request.url.path)
    return _build_json_response(
        code=exc_obj.code,
        message=exc_obj.message,
        http_status=exc_obj.status_code,
        detail={"repository_type": getattr(exc, "repository_type", None)},
    )


async def repository_error_handler(
    _request: Request, exc: RepositoryError
) -> JSONResponse:
    logger.error("RepositoryError: %s path=%s", exc, _request.url.path)
    return _build_json_response(
        code=3001,
        message=str(exc),
        http_status=500,
    )


def register_exception_handlers(app: Any) -> None:
    app.add_exception_handler(AppException, app_exception_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(RecordNotFoundError, record_not_found_handler)
    app.add_exception_handler(RepositoryError, repository_error_handler)
    app.add_exception_handler(Exception, generic_exception_handler)