from enum import StrEnum
from typing import Any


class ErrorCode(StrEnum):
    SUCCESS = "SUCCESS"
    INTERNAL_ERROR = "INTERNAL_ERROR"
    NOT_FOUND = "NOT_FOUND"
    INVALID_REQUEST = "INVALID_REQUEST"
    UNAUTHORIZED = "UNAUTHORIZED"
    FILE_NOT_FOUND = "FILE_NOT_FOUND"
    CAD_GENERATION_ERROR = "CAD_GENERATION_ERROR"
    SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"


def success(data: Any = None, message: str = "Success") -> dict:
    return {
        "code": ErrorCode.SUCCESS,
        "message": message,
        "data": data,
    }


def error(
    code: ErrorCode,
    message: str = "Error",
    detail: Any = None,
    suggestion: str | None = None,
) -> dict:
    result: dict[str, Any] = {
        "code": code,
        "message": message,
        "data": None,
    }
    if detail is not None:
        result["detail"] = detail
    if suggestion is not None:
        result["suggestion"] = suggestion
    return result
