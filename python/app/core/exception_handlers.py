"""Unified exception handlers for FastAPI application."""
from __future__ import annotations

import logging
import traceback
from typing import Any

from fastapi import Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.repository.exceptions import RecordNotFoundError, RepositoryError

logger = logging.getLogger(__name__)


class AppError(Exception):
    """Base application error with structured detail."""

    def __init__(self, detail: str, status_code: int = 500, error_code: str | None = None):
        self.detail = detail
        self.status_code = status_code
        self.error_code = error_code
        super().__init__(detail)


class NotFoundError(AppError):
    def __init__(self, detail: str = "资源未找到", error_code: str = "NOT_FOUND"):
        super().__init__(detail, status_code=404, error_code=error_code)


class ValidationFailedError(AppError):
    def __init__(self, detail: str = "输入验证失败", error_code: str = "VALIDATION_FAILED"):
        super().__init__(detail, status_code=400, error_code=error_code)


class InternalError(AppError):
    def __init__(self, detail: str = "内部服务错误", error_code: str = "INTERNAL_ERROR"):
        super().__init__(detail, status_code=500, error_code=error_code)


class ServiceUnavailableError(AppError):
    def __init__(self, detail: str = "服务暂不可用", error_code: str = "SERVICE_UNAVAILABLE"):
        super().__init__(detail, status_code=503, error_code=error_code)


def _build_error_response(
    status_code: int,
    detail: str,
    error_code: str | None = None,
    request_path: str = "",
) -> JSONResponse:
    body: dict[str, Any] = {
        "detail": detail,
        "path": request_path,
    }
    if error_code:
        body["error_code"] = error_code
    return JSONResponse(status_code=status_code, content=body)


async def app_error_handler(_request: Request, exc: AppError) -> JSONResponse:
    return _build_error_response(exc.status_code, exc.detail, exc.error_code, str(_request.url.path))


async def http_exception_handler(_request: Request, exc: StarletteHTTPException) -> JSONResponse:
    return _build_error_response(exc.status_code, exc.detail, request_path=str(_request.url.path))


async def validation_exception_handler(_request: Request, exc: RequestValidationError) -> JSONResponse:
    errors = []
    for error in exc.errors():
        loc = " -> ".join(str(p) for p in error.get("loc", []))
        msg = error.get("msg", "验证失败")
        errors.append(f"{loc}: {msg}")
    detail = "; ".join(errors) if errors else str(exc)
    logger.warning("Validation failed: %s", detail)
    return _build_error_response(
        status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail,
        "VALIDATION_ERROR",
        str(_request.url.path),
    )


async def record_not_found_handler(_request: Request, exc: RecordNotFoundError) -> JSONResponse:
    return _build_error_response(404, str(exc), "RECORD_NOT_FOUND", str(_request.url.path))


async def repository_error_handler(_request: Request, exc: RepositoryError) -> JSONResponse:
    return _build_error_response(500, str(exc), "REPOSITORY_ERROR", str(_request.url.path))


async def generic_exception_handler(_request: Request, exc: Exception) -> JSONResponse:
    error_id = f"{id(exc):x}"
    logger.exception("Unhandled exception [%s]: %s", error_id, exc)
    return _build_error_response(
        500,
        "抱歉，发生了内部错误。请联系管理员并提供ID: " + error_id,
        "INTERNAL_SERVER_ERROR",
        str(_request.url.path),
    )


def register_exception_handlers(app: Any) -> None:
    """Register all exception handlers on a FastAPI or Starlette application."""
    app.add_exception_handler(AppError, app_error_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(RecordNotFoundError, record_not_found_handler)
    app.add_exception_handler(RepositoryError, repository_error_handler)
    app.add_exception_handler(Exception, generic_exception_handler)