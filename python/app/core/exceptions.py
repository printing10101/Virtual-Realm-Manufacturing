import logging
from typing import Optional

from fastapi import Request
from fastapi.responses import JSONResponse

from app.core.response import error, ErrorCode

logger = logging.getLogger(__name__)


class AppException(Exception):
    def __init__(self, code: int, message: str, detail: Optional[str] = None):
        self.code = code
        self.message = message
        self.detail = detail
        super().__init__(message)


class AIModelUnavailableError(AppException):
    def __init__(self, detail: Optional[str] = None):
        super().__init__(
            code=ErrorCode.AI_MODEL_UNAVAILABLE,
            message="AI 模型不可用",
            detail=detail
        )


class AIModelTimeoutError(AppException):
    def __init__(self, detail: Optional[str] = None):
        super().__init__(
            code=ErrorCode.AI_MODEL_TIMEOUT,
            message="AI 模型请求超时",
            detail=detail
        )


class CADGenerationError(AppException):
    def __init__(self, detail: Optional[str] = None):
        super().__init__(
            code=ErrorCode.CAD_GENERATION_ERROR,
            message="CAD 生成失败",
            detail=detail
        )


class FileNotFoundException(AppException):
    def __init__(self, detail: Optional[str] = None):
        super().__init__(
            code=ErrorCode.FILE_NOT_FOUND,
            message="文件未找到",
            detail=detail
        )


async def app_exception_handler(request: Request, exc: AppException):
    return JSONResponse(
        status_code=200,
        content=error(code=exc.code, message=exc.message, detail=exc.detail)
    )


async def general_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception at {request.url.path}: {str(exc)}", exc_info=True)
    
    return JSONResponse(
        status_code=200,
        content=error(
            code=ErrorCode.INTERNAL_ERROR,
            message="服务器内部错误"
        )
    )
