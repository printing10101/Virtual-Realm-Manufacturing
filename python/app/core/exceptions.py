"""统一异常体系——基类与业务异常派生类。

每个异常类型具备:
- code: 唯一数字错误码
- message: 错误描述
- status_code: HTTP状态码
- detail: 可选的详细信息
"""

from __future__ import annotations

from typing import Any


class AppException(Exception):
    """应用异常基类，所有业务异常均从此派生。

    Attributes:
        code: 数字错误码，全局唯一
        message: 用户可读的错误描述
        status_code: 对应HTTP状态码
        detail: 可选的调试/补充信息
    """

    def __init__(
        self,
        code: int,
        message: str,
        status_code: int = 500,
        detail: Any = None,
    ):
        self.code = code
        self.message = message
        self.status_code = status_code
        self.detail = detail
        super().__init__(message)

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "code": self.code,
            "message": self.message,
        }
        if self.detail is not None:
            result["detail"] = self.detail
        return result


# ============================================================
# 客户端错误 (1xxx, HTTP 4xx)
# ============================================================

class NotFoundException(AppException):
    def __init__(self, message: str = "资源未找到", detail: Any = None):
        super().__init__(code=1001, message=message, status_code=404, detail=detail)


class ValidationException(AppException):
    def __init__(self, message: str = "请求参数校验失败", detail: Any = None):
        super().__init__(code=1002, message=message, status_code=422, detail=detail)


class UnauthorizedException(AppException):
    def __init__(self, message: str = "未认证或Token无效", detail: Any = None):
        super().__init__(code=1003, message=message, status_code=401, detail=detail)


class ForbiddenException(AppException):
    def __init__(self, message: str = "权限不足", detail: Any = None):
        super().__init__(code=1004, message=message, status_code=403, detail=detail)


class ConflictException(AppException):
    def __init__(self, message: str = "资源冲突", detail: Any = None):
        super().__init__(code=1005, message=message, status_code=409, detail=detail)


class BadRequestException(AppException):
    def __init__(self, message: str = "请求参数错误", detail: Any = None):
        super().__init__(code=1006, message=message, status_code=400, detail=detail)


class RateLimitException(AppException):
    def __init__(self, message: str = "请求频率超限", detail: Any = None):
        super().__init__(code=1007, message=message, status_code=429, detail=detail)


# ============================================================
# 服务端错误 (2xxx, HTTP 5xx)
# ============================================================

class InternalServerException(AppException):
    def __init__(self, message: str = "服务器内部错误", detail: Any = None):
        super().__init__(code=2001, message=message, status_code=500, detail=detail)


class ServiceUnavailableException(AppException):
    def __init__(self, message: str = "服务暂不可用", detail: Any = None):
        super().__init__(code=2002, message=message, status_code=503, detail=detail)


class GatewayException(AppException):
    def __init__(self, message: str = "网关错误", detail: Any = None):
        super().__init__(code=2003, message=message, status_code=502, detail=detail)


class TimeoutException(AppException):
    def __init__(self, message: str = "请求超时", detail: Any = None):
        super().__init__(code=2004, message=message, status_code=504, detail=detail)


# ============================================================
# 仓库层错误 (3xxx)
# ============================================================

class RepositoryException(AppException):
    def __init__(self, message: str = "数据仓库操作异常", detail: Any = None):
        super().__init__(code=3001, message=message, status_code=500, detail=detail)


class RecordNotFoundException(AppException):
    def __init__(self, message: str = "数据记录不存在", detail: Any = None):
        super().__init__(code=3002, message=message, status_code=404, detail=detail)


class StorageException(AppException):
    def __init__(self, message: str = "存储操作失败", detail: Any = None):
        super().__init__(code=3003, message=message, status_code=500, detail=detail)


# ============================================================
# 执行锁错误 (4xxx)
# ============================================================

class LockException(AppException):
    def __init__(self, message: str = "锁操作异常", detail: Any = None):
        super().__init__(code=4001, message=message, status_code=409, detail=detail)


class LockConflictException(AppException):
    def __init__(self, message: str = "锁冲突", detail: Any = None):
        super().__init__(code=4002, message=message, status_code=409, detail=detail)


class LockNotFoundException(AppException):
    def __init__(self, message: str = "锁不存在", detail: Any = None):
        super().__init__(code=4003, message=message, status_code=404, detail=detail)


class LockExpiredException(AppException):
    def __init__(self, message: str = "锁已过期", detail: Any = None):
        super().__init__(code=4004, message=message, status_code=409, detail=detail)


class LockOwnershipException(AppException):
    def __init__(self, message: str = "锁所属权错误", detail: Any = None):
        super().__init__(code=4005, message=message, status_code=403, detail=detail)


# ============================================================
# 状态持久化错误 (5xxx)
# ============================================================

class StateException(AppException):
    def __init__(self, message: str = "状态操作异常", detail: Any = None):
        super().__init__(code=5001, message=message, status_code=409, detail=detail)


class StateConflictException(AppException):
    def __init__(self, message: str = "状态冲突", detail: Any = None):
        super().__init__(code=5002, message=message, status_code=409, detail=detail)


class StateNotFoundException(AppException):
    def __init__(self, message: str = "状态不存在", detail: Any = None):
        super().__init__(code=5003, message=message, status_code=404, detail=detail)


# ============================================================
# AI/LLM错误 (6xxx)
# ============================================================

class LLMException(AppException):
    def __init__(self, message: str = "大模型调用异常", detail: Any = None):
        super().__init__(code=6001, message=message, status_code=502, detail=detail)


class LLMRateLimitException(AppException):
    def __init__(self, message: str = "LLM调用频率超限", detail: Any = None):
        super().__init__(code=6002, message=message, status_code=429, detail=detail)


class LLMResponseException(AppException):
    def __init__(self, message: str = "LLM响应无效", detail: Any = None):
        super().__init__(code=6003, message=message, status_code=502, detail=detail)


# ============================================================
# CAD错误 (7xxx)
# ============================================================

class CadException(AppException):
    def __init__(self, message: str = "CAD操作异常", detail: Any = None):
        super().__init__(code=7001, message=message, status_code=500, detail=detail)


class CadScriptException(AppException):
    def __init__(self, message: str = "CAD脚本执行失败", detail: Any = None):
        super().__init__(code=7002, message=message, status_code=500, detail=detail)


class CadExportException(AppException):
    def __init__(self, message: str = "CAD导出失败", detail: Any = None):
        super().__init__(code=7003, message=message, status_code=500, detail=detail)


# ============================================================
# 错误码映射：AppException.code -> 异常类
# ============================================================

EXCEPTION_CODE_MAP: dict[int, type[AppException]] = {
    1001: NotFoundException,
    1002: ValidationException,
    1003: UnauthorizedException,
    1004: ForbiddenException,
    1005: ConflictException,
    1006: BadRequestException,
    1007: RateLimitException,
    2001: InternalServerException,
    2002: ServiceUnavailableException,
    2003: GatewayException,
    2004: TimeoutException,
    3001: RepositoryException,
    3002: RecordNotFoundException,
    3003: StorageException,
    4001: LockException,
    4002: LockConflictException,
    4003: LockNotFoundException,
    4004: LockExpiredException,
    4005: LockOwnershipException,
    5001: StateException,
    5002: StateConflictException,
    5003: StateNotFoundException,
    6001: LLMException,
    6002: LLMRateLimitException,
    6003: LLMResponseException,
    7001: CadException,
    7002: CadScriptException,
    7003: CadExportException,
}