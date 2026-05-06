"""
输入验证与数据清洗中间件

提供全面的输入验证机制，包括：
- XSS攻击防护
- SQL注入检测
- 长度限制验证
- 自定义验证器（材料名称、尺寸格式、公差等级）
"""
import logging
import re
from collections.abc import Callable
from functools import wraps
from typing import Any

from fastapi import HTTPException, status
from fastapi.responses import JSONResponse

from app.core.response import ErrorCode, error

logger = logging.getLogger(__name__)

# ==================== 常量定义 ====================

MAX_INPUT_LENGTH = 1000

XSS_PATTERNS = [
    r'<script[^>]*>.*?</script>',
    r'javascript\s*:',
    r'on\w+\s*=\s*["\']',
    r'<iframe[^>]*>',
    r'<object[^>]*>',
    r'<embed[^>]*>',
    r'<form[^>]*>',
    r'<input[^>]*>',
    r'<img[^>]*onerror',
    r'<svg[^>]*onload',
    r'expression\s*\(',
    r'url\s*\(\s*["\']?\s*javascript',
]

SQL_INJECTION_PATTERNS = [
    r'(\b(SELECT|INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|EXEC|EXECUTE)\b.*\b(FROM|INTO|TABLE|WHERE|SET)\b)',
    r'(--|;|/\*|\*/)',
    r'(\bOR\b\s+\d+\s*=\s*\d+)',
    r'(\bUNION\b\s+\bSELECT\b)',
    r"('\s*(OR|AND)\s+')",
    r'(WAITFOR\s+DELAY)',
    r'(BENCHMARK\s*\()',
    r'(SLEEP\s*\()',
]

VALID_MATERIALS = {
    "45钢", "Q235", "40Cr", "20CrMnTi", "GCr15", "60Si2Mn",
    "6061铝合金", "7075铝合金", "5052铝合金", "2024铝合金",
    "304不锈钢", "316不锈钢", "430不锈钢", "201不锈钢",
    "T8", "T10", "T12", "Cr12", "Cr12MoV", "H13",
    "HT200", "HT300", "QT400-15", "QT500-7", "QT600-3",
    "TC4", "TA1", "TB6",
    "黄铜", "紫铜", "青铜",
}

VALID_UNITS = {
    "mm": {"factor": 1.0, "name": "毫米"},
    "cm": {"factor": 10.0, "name": "厘米"},
    "m": {"factor": 1000.0, "name": "米"},
    "inch": {"factor": 25.4, "name": "英寸"},
    "in": {"factor": 25.4, "name": "英寸"},
}

VALID_TOLERANCE_GRADES = {
    "IT6", "IT7", "IT8", "IT9", "IT10", "IT11", "IT12", "IT13", "IT14"
}

TOLERANCE_NUMERIC_MAP = {
    6: "IT6", 7: "IT7", 8: "IT8", 9: "IT9", 10: "IT10",
    11: "IT11", 12: "IT12", 13: "IT13", 14: "IT14"
}

# ==================== 预编译正则 ====================

XSS_REGEX = [re.compile(p, re.IGNORECASE) for p in XSS_PATTERNS]
SQL_INJECTION_REGEX = [re.compile(p, re.IGNORECASE) for p in SQL_INJECTION_PATTERNS]
SIZE_PATTERN = re.compile(r'^(\d+\.?\d*)\s*(mm|cm|m|inch|in)$', re.IGNORECASE)
MATERIAL_PATTERN = re.compile(r'^[a-zA-Z0-9\u4e00-\u9fa5\-]+$')

# ==================== 验证错误类 ====================

class ValidationErrorDetail:
    """验证错误详情"""
    def __init__(
        self,
        code: int,
        error_type: str,
        message: str,
        field: str,
        suggestion: str,
        detail: str | None = None
    ):
        self.code = code
        self.error_type = error_type
        self.message = message
        self.field = field
        self.suggestion = suggestion
        self.detail = detail

    def to_response(self) -> dict:
        return {
            "code": self.code,
            "error_type": self.error_type,
            "message": self.message,
            "field": self.field,
            "suggestion": self.suggestion,
            "detail": self.detail,
        }

# ==================== 基础验证函数 ====================

def validate_length(value: str, max_length: int = MAX_INPUT_LENGTH, field_name: str = "input") -> ValidationErrorDetail | None:
    """
    验证输入长度是否超过限制

    Args:
        value: 待验证的输入字符串
        max_length: 最大允许长度
        field_name: 字段名称，用于错误提示

    Returns:
        如果验证失败返回错误详情，成功返回None
    """
    if len(value) > max_length:
        return ValidationErrorDetail(
            code=ErrorCode.INVALID_REQUEST,
            error_type="length_exceeded",
            message=f"输入内容过长，当前{len(value)}字符，最大允许{max_length}字符",
            field=field_name,
            suggestion=f"请将{field_name}的内容精简到{max_length}字符以内"
        )
    return None


def filter_xss(value: str, field_name: str = "input") -> ValidationErrorDetail | None:
    """
    过滤并检测XSS攻击模式

    Args:
        value: 待验证的输入字符串
        field_name: 字段名称

    Returns:
        如果检测到XSS模式返回错误详情，安全返回None
    """
    for regex in XSS_REGEX:
        if regex.search(value):
            return ValidationErrorDetail(
                code=ErrorCode.INVALID_REQUEST,
                error_type="xss_detected",
                message="输入包含不允许的内容格式",
                field=field_name,
                suggestion="请检查并移除可能包含的脚本标签或特殊代码内容",
                detail="输入内容不符合安全规范"
            )
    return None


def detect_sql_injection(value: str, field_name: str = "input") -> ValidationErrorDetail | None:
    """
    检测SQL注入模式

    Args:
        value: 待验证的输入字符串
        field_name: 字段名称

    Returns:
        如果检测到SQL注入模式返回错误详情，安全返回None
    """
    for regex in SQL_INJECTION_REGEX:
        if regex.search(value):
            return ValidationErrorDetail(
                code=ErrorCode.INVALID_REQUEST,
                error_type="sql_injection_detected",
                message="输入包含不允许的数据库操作关键字",
                field=field_name,
                suggestion="请检查并移除SQL相关关键字或特殊符号",
                detail="输入内容包含潜在的数据库操作指令"
            )
    return None


def validate_and_clean(value: str, field_name: str = "input") -> tuple[str, ValidationErrorDetail | None]:
    """
    执行完整的验证与清洗流程

    Args:
        value: 待验证的原始输入
        field_name: 字段名称

    Returns:
        (清洗后的值, 错误详情或None)
    """
    if not isinstance(value, str):
        return value, ValidationErrorDetail(
            code=ErrorCode.INVALID_REQUEST,
            error_type="invalid_type",
            message="输入必须是文本格式",
            field=field_name,
            suggestion="请提供有效的文本内容"
        )

    cleaned = value.strip()

    length_error = validate_length(cleaned, field_name=field_name)
    if length_error:
        return cleaned, length_error

    xss_error = filter_xss(cleaned, field_name=field_name)
    if xss_error:
        return cleaned, xss_error

    sql_error = detect_sql_injection(cleaned, field_name=field_name)
    if sql_error:
        return cleaned, sql_error

    return cleaned, None

# ==================== 自定义验证器 ====================

class MaterialValidator:
    """材料名称验证器"""

    _whitelist: set[str] = set(VALID_MATERIALS)

    @classmethod
    def validate(cls, material: str) -> ValidationErrorDetail | None:
        """
        验证材料名称是否在白名单中

        Args:
            material: 材料名称

        Returns:
            验证失败返回错误详情，成功返回None
        """
        if not material:
            return ValidationErrorDetail(
                code=ErrorCode.INVALID_REQUEST,
                error_type="empty_material",
                message="材料名称不能为空",
                field="material",
                suggestion="请提供有效的材料名称，如45钢、304不锈钢等"
            )

        material = material.strip()

        if not MATERIAL_PATTERN.match(material):
            return ValidationErrorDetail(
                code=ErrorCode.INVALID_REQUEST,
                error_type="invalid_material_format",
                message="材料名称格式不正确",
                field="material",
                suggestion="材料名称只能包含字母、数字和中文",
                detail=f"输入的材料名称: {material}"
            )

        if material not in cls._whitelist:
            return ValidationErrorDetail(
                code=ErrorCode.INVALID_REQUEST,
                error_type="material_not_allowed",
                message=f"材料'{material}'不在支持列表中",
                field="material",
                suggestion="请选择系统支持的材料",
                detail=f"支持的材料: {', '.join(sorted(cls._whitelist))}"
            )

        return None

    @classmethod
    def add_material(cls, material: str) -> None:
        """
        动态添加材料到白名单

        Args:
            material: 要添加的材料名称
        """
        cls._whitelist.add(material.strip())
        logger.info(f"材料'{material}'已添加到白名单")

    @classmethod
    def remove_material(cls, material: str) -> bool:
        """
        从白名单移除材料

        Args:
            material: 要移除的材料名称

        Returns:
            是否成功移除
        """
        material = material.strip()
        if material in cls._whitelist:
            cls._whitelist.discard(material)
            logger.info(f"材料'{material}'已从白名单移除")
            return True
        return False

    @classmethod
    def get_whitelist(cls) -> set[str]:
        """获取当前白名单"""
        return cls._whitelist.copy()


class SizeValidator:
    """尺寸格式验证器"""

    @classmethod
    def validate(cls, size_str: str, min_value: float = 0.001, max_value: float = 10000.0) -> tuple[dict | None, ValidationErrorDetail | None]:
        """
        验证尺寸格式为"数字+单位"模式

        Args:
            size_str: 尺寸字符串，如"100mm"、"5.5inch"
            min_value: 最小允许数值
            max_value: 最大允许数值

        Returns:
            (解析后的尺寸字典, 错误详情或None)
            解析后字典格式: {"value": 数值, "unit": 单位, "unit_mm": 换算为mm的值}
        """
        if not size_str:
            return None, ValidationErrorDetail(
                code=ErrorCode.INVALID_REQUEST,
                error_type="empty_size",
                message="尺寸不能为空",
                field="size",
                suggestion="请输入格式为'数字+单位'的尺寸，如100mm"
            )

        match = SIZE_PATTERN.match(size_str.strip())
        if not match:
            return None, ValidationErrorDetail(
                code=ErrorCode.INVALID_REQUEST,
                error_type="invalid_size_format",
                message="尺寸格式不正确",
                field="size",
                suggestion="请输入格式为'数字+单位'的尺寸，支持单位: mm, cm, m, inch",
                detail=f"输入的尺寸: {size_str}"
            )

        value = float(match.group(1))
        unit = match.group(2).lower()

        if unit not in VALID_UNITS:
            return None, ValidationErrorDetail(
                code=ErrorCode.INVALID_REQUEST,
                error_type="unsupported_unit",
                message=f"不支持的单位'{unit}'",
                field="size",
                suggestion=f"请使用支持的单位: {', '.join(VALID_UNITS.keys())}",
            )

        if value < min_value:
            return None, ValidationErrorDetail(
                code=ErrorCode.INVALID_REQUEST,
                error_type="size_too_small",
                message=f"尺寸数值过小，当前{value}，最小允许{min_value}",
                field="size",
                suggestion=f"请将尺寸数值调整到{min_value}以上",
            )

        if value > max_value:
            return None, ValidationErrorDetail(
                code=ErrorCode.INVALID_REQUEST,
                error_type="size_too_large",
                message=f"尺寸数值过大，当前{value}，最大允许{max_value}",
                field="size",
                suggestion=f"请将尺寸数值调整到{max_value}以下",
            )

        unit_mm = value * VALID_UNITS[unit]["factor"]

        return {
            "value": value,
            "unit": unit,
            "unit_mm": round(unit_mm, 3)
        }, None

    @classmethod
    def get_supported_units(cls) -> dict:
        """获取支持的所有单位"""
        return VALID_UNITS.copy()


class ToleranceValidator:
    """公差等级验证器"""

    @classmethod
    def validate(cls, tolerance: str) -> dict | None:
        """
        验证公差等级是否符合IT6至IT14标准

        Args:
            tolerance: 公差等级，支持文本(IT6-IT14)或数字(6-14)表示

        Returns:
            验证失败返回错误详情，成功返回标准化后的公差信息字典
            字典格式: {"grade": "ITx", "numeric": x}
        """
        if not tolerance:
            return ValidationErrorDetail(
                code=ErrorCode.INVALID_REQUEST,
                error_type="empty_tolerance",
                message="公差等级不能为空",
                field="tolerance",
                suggestion="请输入IT6至IT14之间的公差等级",
            )

        tolerance = str(tolerance).strip().upper()

        if tolerance in VALID_TOLERANCE_GRADES:
            numeric = int(tolerance[2:])
            return {"grade": tolerance, "numeric": numeric}, None

        if tolerance.startswith("IT"):
            try:
                numeric = int(tolerance[2:])
                if numeric in TOLERANCE_NUMERIC_MAP:
                    return {"grade": TOLERANCE_NUMERIC_MAP[numeric], "numeric": numeric}, None
            except ValueError:
                pass

        try:
            numeric = int(tolerance)
            if numeric in TOLERANCE_NUMERIC_MAP:
                return {"grade": TOLERANCE_NUMERIC_MAP[numeric], "numeric": numeric}, None
        except ValueError:
            pass

        return ValidationErrorDetail(
            code=ErrorCode.INVALID_REQUEST,
            error_type="invalid_tolerance",
            message=f"公差等级'{tolerance}'不在IT6至IT14范围内",
            field="tolerance",
            suggestion="请输入IT6至IT14之间的公差等级，如IT7、IT8等",
            detail=f"输入的公差等级: {tolerance}，有效范围: IT6-IT14"
        )

    @classmethod
    def get_valid_grades(cls) -> set:
        """获取所有有效的公差等级"""
        return VALID_TOLERANCE_GRADES.copy()

# ==================== 中间件类 ====================

class InputValidationMiddleware:
    """
    输入验证中间件

    对所有请求的输入进行验证与清洗，包括：
    - 长度限制验证
    - XSS攻击防护
    - SQL注入检测
    """

    def __init__(
        self,
        app,
        skip_paths: list[str] | None = None,
        max_length: int = MAX_INPUT_LENGTH,
        enabled: bool = True
    ):
        self.app = app
        self.skip_paths = skip_paths or ["/health", "/docs", "/openapi.json", "/redoc"]
        self.max_length = max_length
        self.enabled = enabled

    async def __call__(self, scope, receive, send):
        if not self.enabled or scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")

        if any(path.startswith(skip) for skip in self.skip_paths):
            await self.app(scope, receive, send)
            return

        if scope.get("method") in ("POST", "PUT", "PATCH"):
            body = await receive()

            if body.get("type") != "http.request":
                async def wrapped_receive():
                    return body
                await self.app(scope, wrapped_receive, send)
                return

            body_bytes = body.get("body", b"")

            async def new_receive():
                return {
                    "type": "http.request",
                    "body": body_bytes,
                    "more_body": False,
                }

            try:
                import json
                if body_bytes:
                    body_str = body_bytes.decode("utf-8")
                    if len(body_str) > self.max_length * 10:
                        response = JSONResponse(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            content=error(
                                code=ErrorCode.INVALID_REQUEST,
                                message="请求体过大",
                                suggestion="请减小请求数据大小"
                            )
                        )
                        await send({
                            "type": "http.response.start",
                            "status": response.status_code,
                            "headers": response.raw_headers,
                        })
                        await send({
                            "type": "http.response.body",
                            "body": response.body,
                        })
                        return

                    try:
                        data = json.loads(body_str)
                        validation_errors = self._validate_json(data)
                        if validation_errors:
                            response = JSONResponse(
                                status_code=status.HTTP_400_BAD_REQUEST,
                                content=error(
                                    code=ErrorCode.INVALID_REQUEST,
                                    message=f"输入验证失败: {validation_errors[0]['message']}",
                                    detail=validation_errors[0].to_response()
                                )
                            )
                            await send({
                                "type": "http.response.start",
                                "status": response.status_code,
                                "headers": response.raw_headers,
                            })
                            await send({
                                "type": "http.response.body",
                                "body": response.body,
                            })
                            return
                    except json.JSONDecodeError:
                        pass
            except Exception as e:
                logger.warning(f"输入验证中间件异常: {e!s}")

            await self.app(scope, new_receive, send)
            return

        await self.app(scope, receive, send)

    def _validate_json(self, data: Any, path: str = "root") -> list[ValidationErrorDetail]:
        """
        递归验证JSON数据中的所有字符串字段

        Args:
            data: 待验证的JSON数据
            path: 当前JSON路径，用于错误定位

        Returns:
            验证错误列表
        """
        errors = []

        if isinstance(data, str):
            _, err = validate_and_clean(data, field_name=path)
            if err:
                errors.append(err)
        elif isinstance(data, dict):
            for key, value in data.items():
                field_path = f"{path}.{key}"
                errors.extend(self._validate_json(value, field_path))
        elif isinstance(data, list):
            for i, item in enumerate(data):
                item_path = f"{path}[{i}]"
                errors.extend(self._validate_json(item, item_path))

        return errors

# ==================== 依赖注入装饰器 ====================

def validate_input(field_name: str = "input", required: bool = True):
    """
    字段验证装饰器

    用于验证单个输入字段，通常用于API端点

    Args:
        field_name: 字段名称
        required: 是否必填
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            value = kwargs.get(field_name)

            if required and not value:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=ValidationErrorDetail(
                        code=ErrorCode.INVALID_REQUEST,
                        error_type="missing_required_field",
                        message=f"缺少必填字段'{field_name}'",
                        field=field_name,
                        suggestion=f"请提供{field_name}的值"
                    ).to_response()
                )

            if value:
                cleaned, err = validate_and_clean(value, field_name=field_name)
                if err:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=err.to_response()
                    )
                kwargs[field_name] = cleaned

            return await func(*args, **kwargs)
        return wrapper
    return decorator


def validate_material(field_name: str = "material", required: bool = True):
    """材料名称验证装饰器"""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            value = kwargs.get(field_name)

            if required and not value:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=ValidationErrorDetail(
                        code=ErrorCode.INVALID_REQUEST,
                        error_type="missing_required_field",
                        message=f"缺少必填字段'{field_name}'",
                        field=field_name,
                        suggestion=f"请提供{field_name}的值"
                    ).to_response()
                )

            if value:
                err = MaterialValidator.validate(value)
                if err:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=err.to_response()
                    )

            return await func(*args, **kwargs)
        return wrapper
    return decorator


def validate_size(field_name: str = "size", min_value: float = 0.001, max_value: float = 10000.0):
    """尺寸格式验证装饰器"""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            value = kwargs.get(field_name)

            if value:
                result, err = SizeValidator.validate(value, min_value=min_value, max_value=max_value)
                if err:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=err.to_response()
                    )
                kwargs[f"{field_name}_parsed"] = result

            return await func(*args, **kwargs)
        return wrapper
    return decorator


def validate_tolerance(field_name: str = "tolerance"):
    """公差等级验证装饰器"""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            value = kwargs.get(field_name)

            if value:
                result = ToleranceValidator.validate(value)
                if isinstance(result, ValidationErrorDetail):
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=result.to_response()
                    )
                kwargs[f"{field_name}_parsed"] = result

            return await func(*args, **kwargs)
        return wrapper
    return decorator
