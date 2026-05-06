from enum import StrEnum
from typing import Any


class ErrorCode(StrEnum):
    SUCCESS = "SUCCESS"
    INTERNAL_ERROR = "INTERNAL_ERROR"
    NOT_FOUND = "NOT_FOUND"
    INVALID_REQUEST = "INVALID_REQUEST"
    UNAUTHORIZED = "UNAUTHORIZED"


def success(data: Any = None, message: str = "Success") -> dict:
    return {
        "code": ErrorCode.SUCCESS,
        "message": message,
        "data": data
    }


def error(code: ErrorCode, message: str = "Error") -> dict:
    return {
        "code": code,
        "message": message,
        "data": None
    }
