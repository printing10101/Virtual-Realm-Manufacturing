"""统一API响应格式。

所有响应均包含: code（数值错误码）、message（描述）、request_id（请求追踪标识）。
ErrorCode保留字符串枚举以保持向后兼容，内部通过映射表转换为数值。

响应示例：
    成功: {"code": 0, "message": "Success", "data": {...}, "request_id": "abc123..."}
    错误: {"code": 1001, "message": "资源未找到", "request_id": "abc123..."}
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from app.core.request_id import get_request_id


class ErrorCode(StrEnum):
    SUCCESS = "SUCCESS"
    INTERNAL_ERROR = "INTERNAL_ERROR"
    NOT_FOUND = "NOT_FOUND"
    INVALID_REQUEST = "INVALID_REQUEST"
    UNAUTHORIZED = "UNAUTHORIZED"
    FILE_NOT_FOUND = "FILE_NOT_FOUND"
    CAD_GENERATION_ERROR = "CAD_GENERATION_ERROR"
    SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"


_ERROR_CODE_TO_NUMERIC: dict[ErrorCode, int] = {
    ErrorCode.SUCCESS: 0,
    ErrorCode.NOT_FOUND: 1001,
    ErrorCode.INVALID_REQUEST: 1002,
    ErrorCode.UNAUTHORIZED: 1003,
    ErrorCode.FILE_NOT_FOUND: 1008,
    ErrorCode.CAD_GENERATION_ERROR: 7001,
    ErrorCode.INTERNAL_ERROR: 2001,
    ErrorCode.SERVICE_UNAVAILABLE: 2002,
}

_NUMERIC_TO_ERROR_CODE: dict[int, ErrorCode] = {
    v: k for k, v in _ERROR_CODE_TO_NUMERIC.items()
}


def code_to_numeric(code: ErrorCode) -> int:
    return _ERROR_CODE_TO_NUMERIC.get(code, 2001)


def numeric_to_code(num: int) -> ErrorCode:
    return _NUMERIC_TO_ERROR_CODE.get(num, ErrorCode.INTERNAL_ERROR)


def success(data: Any = None, message: str = "Success") -> dict[str, Any]:
    return {
        "code": 0,
        "message": message,
        "data": data,
        "request_id": get_request_id(),
    }


def error(
    code: ErrorCode,
    message: str = "Error",
    detail: Any = None,
    suggestion: str | None = None,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "code": code_to_numeric(code),
        "message": message,
        "request_id": get_request_id(),
    }
    if detail is not None:
        result["detail"] = detail
    if suggestion is not None:
        result["suggestion"] = suggestion
    return result


def error_response(
    code: int,
    message: str,
    detail: Any = None,
) -> dict[str, Any]:
    """使用数值错误码直接构建错误响应（供异常处理器使用）。"""
    result: dict[str, Any] = {
        "code": code,
        "message": message,
        "request_id": get_request_id(),
    }
    if detail is not None:
        result["detail"] = detail
    return result
