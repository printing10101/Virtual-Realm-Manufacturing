from enum import IntEnum
from typing import Any, Generic, Optional, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class ErrorCode(IntEnum):
    SUCCESS = 0
    AI_MODEL_UNAVAILABLE = 1001
    AI_MODEL_TIMEOUT = 1002
    CAD_GENERATION_ERROR = 2001
    FILE_NOT_FOUND = 3001
    INVALID_REQUEST = 4001
    INTERNAL_ERROR = 5000


class ApiResponse(BaseModel, Generic[T]):
    code: int = Field(default=ErrorCode.SUCCESS)
    message: str = Field(default="success")
    data: Optional[T] = None


def success(data: Any = None, message: str = "success") -> dict:
    return ApiResponse(code=ErrorCode.SUCCESS, message=message, data=data).model_dump()


def error(code: int, message: str, data: Any = None, detail: Optional[str] = None) -> dict:
    result = ApiResponse(code=code, message=message, data=data).model_dump()
    if detail:
        result["detail"] = detail
    return result
