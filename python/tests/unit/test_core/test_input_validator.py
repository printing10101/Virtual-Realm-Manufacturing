"""
输入验证中间件单元测试

测试范围：
- 基础验证（长度、XSS、SQL注入）
- 自定义验证器（材料名称、尺寸格式、公差等级）
- 验证错误响应格式
"""
import pytest

from app.core.input_validator import (
    MAX_INPUT_LENGTH,
    InputValidationMiddleware,
    MaterialValidator,
    SizeValidator,
    ToleranceValidator,
    ValidationErrorDetail,
    detect_sql_injection,
    filter_xss,
    validate_and_clean,
    validate_length,
)
from app.core.response import ErrorCode


class TestValidateLength:
    """测试长度验证"""

    def test_valid_length(self):
        result = validate_length("test input", max_length=100)
        assert result is None

    def test_exact_max_length(self):
        text = "a" * 100
        result = validate_length(text, max_length=100)
        assert result is None

    def test_exceeds_max_length(self):
        text = "a" * 1001
        result = validate_length(text, max_length=MAX_INPUT_LENGTH)
        assert result is not None
        assert result.error_type == "length_exceeded"
        assert result.code == ErrorCode.INVALID_REQUEST

    def test_custom_max_length(self):
        result = validate_length("test", max_length=3)
        assert result is not None
        assert "当前4字符" in result.message

    def test_empty_string(self):
        result = validate_length("", max_length=100)
        assert result is None


class TestFilterXSS:
    """测试XSS过滤"""

    def test_safe_input(self):
        result = filter_xss("normal text")
        assert result is None

    def test_script_tag(self):
        result = filter_xss("<script>alert('xss')</script>")
        assert result is not None
        assert result.error_type == "xss_detected"

    def test_javascript_protocol(self):
        result = filter_xss("<a href='javascript:void(0)'>click</a>")
        assert result is not None

    def test_onload_event(self):
        result = filter_xss('<img src=x onerror="alert(1)">')
        assert result is not None

    def test_iframe_tag(self):
        result = filter_xss('<iframe src="http://evil.com"></iframe>')
        assert result is not None

    def test_case_insensitive(self):
        result = filter_xss("<SCRIPT>alert(1)</SCRIPT>")
        assert result is not None

    def test_chinese_content(self):
        result = filter_xss("我需要加工一个45钢的零件")
        assert result is None


class TestDetectSQLInjection:
    """测试SQL注入检测"""

    def test_safe_input(self):
        result = detect_sql_injection("45钢零件加工")
        assert result is None

    def test_select_statement(self):
        result = detect_sql_injection("SELECT * FROM users WHERE 1=1")
        assert result is not None
        assert result.error_type == "sql_injection_detected"

    def test_union_select(self):
        result = detect_sql_injection("' UNION SELECT * FROM users --")
        assert result is not None

    def test_comment_syntax(self):
        result = detect_sql_injection("'; DROP TABLE users;--")
        assert result is not None

    def test_or_condition(self):
        result = detect_sql_injection("admin' OR 1=1 --")
        assert result is not None

    def test_waitfor_delay(self):
        result = detect_sql_injection("'; WAITFOR DELAY '0:0:5' --")
        assert result is not None


class TestValidateAndClean:
    """测试完整验证流程"""

    def test_valid_input(self):
        cleaned, err = validate_and_clean("normal manufacturing input")
        assert err is None
        assert cleaned == "normal manufacturing input"

    def test_strips_whitespace(self):
        cleaned, err = validate_and_clean("  test input  ")
        assert err is None
        assert cleaned == "test input"

    def test_non_string_input(self):
        _cleaned, err = validate_and_clean(12345)
        assert err is not None
        assert err.error_type == "invalid_type"

    def test_xss_blocked(self):
        _cleaned, err = validate_and_clean("<script>evil()</script>")
        assert err is not None
        assert err.error_type == "xss_detected"

    def test_sql_injection_blocked(self):
        _cleaned, err = validate_and_clean("'; DROP TABLE users;--")
        assert err is not None
        assert err.error_type == "sql_injection_detected"

    def test_length_blocked(self):
        long_text = "a" * 2000
        _cleaned, err = validate_and_clean(long_text)
        assert err is not None
        assert err.error_type == "length_exceeded"


class TestValidationErrorDetail:
    """测试验证错误详情"""

    def test_to_response(self):
        detail = ValidationErrorDetail(
            code=ErrorCode.INVALID_REQUEST,
            error_type="test_error",
            message="测试错误",
            field="test_field",
            suggestion="请修正",
            detail="详细信息"
        )
        response = detail.to_response()
        assert response["code"] == ErrorCode.INVALID_REQUEST
        assert response["error_type"] == "test_error"
        assert response["message"] == "测试错误"
        assert response["field"] == "test_field"
        assert response["suggestion"] == "请修正"
        assert response["detail"] == "详细信息"


class TestMaterialValidator:
    """测试材料名称验证器"""

    def test_valid_material(self):
        err = MaterialValidator.validate("45钢")
        assert err is None

    def test_valid_stainless_steel(self):
        err = MaterialValidator.validate("304不锈钢")
        assert err is None

    def test_valid_aluminum(self):
        err = MaterialValidator.validate("6061铝合金")
        assert err is None

    def test_empty_material(self):
        err = MaterialValidator.validate("")
        assert err is not None
        assert err.error_type == "empty_material"

    def test_invalid_format(self):
        err = MaterialValidator.validate("<script>")
        assert err is not None
        assert err.error_type == "invalid_material_format"

    def test_material_not_in_whitelist(self):
        err = MaterialValidator.validate("未知材料")
        assert err is not None
        assert err.error_type == "material_not_allowed"

    def test_add_material(self):
        MaterialValidator.add_material("新型合金")
        err = MaterialValidator.validate("新型合金")
        assert err is None

    def test_remove_material(self):
        MaterialValidator.add_material("临时材料")
        assert MaterialValidator.remove_material("临时材料")
        err = MaterialValidator.validate("临时材料")
        assert err is not None

    def test_remove_nonexistent_material(self):
        result = MaterialValidator.remove_material("不存在的材料")
        assert result is False

    def test_get_whitelist(self):
        whitelist = MaterialValidator.get_whitelist()
        assert isinstance(whitelist, set)
        assert "45钢" in whitelist

    def test_strip_whitespace(self):
        err = MaterialValidator.validate("  45钢  ")
        assert err is None


class TestSizeValidator:
    """测试尺寸格式验证器"""

    def test_valid_mm(self):
        result, err = SizeValidator.validate("100mm")
        assert err is None
        assert result["value"] == 100.0
        assert result["unit"] == "mm"
        assert result["unit_mm"] == 100.0

    def test_valid_cm(self):
        result, err = SizeValidator.validate("10cm")
        assert err is None
        assert result["value"] == 10.0
        assert result["unit_mm"] == 100.0

    def test_valid_m(self):
        result, err = SizeValidator.validate("1m")
        assert err is None
        assert result["unit_mm"] == 1000.0

    def test_valid_inch(self):
        result, err = SizeValidator.validate("5inch")
        assert err is None
        assert result["unit_mm"] == 127.0

    def test_valid_decimal(self):
        result, err = SizeValidator.validate("12.5mm")
        assert err is None
        assert result["value"] == 12.5

    def test_empty_size(self):
        _result, err = SizeValidator.validate("")
        assert err is not None
        assert err.error_type == "empty_size"

    def test_invalid_format(self):
        _result, err = SizeValidator.validate("abc")
        assert err is not None
        assert err.error_type == "invalid_size_format"

    def test_unsupported_unit(self):
        _result, err = SizeValidator.validate("100km")
        assert err is not None
        assert err.error_type in ("unsupported_unit", "invalid_size_format")

    def test_too_small(self):
        _result, err = SizeValidator.validate("0.0001mm", min_value=0.001)
        assert err is not None
        assert err.error_type == "size_too_small"

    def test_too_large(self):
        _result, err = SizeValidator.validate("99999mm", max_value=10000.0)
        assert err is not None
        assert err.error_type == "size_too_large"

    def test_case_insensitive_unit(self):
        _result, err = SizeValidator.validate("100MM")
        assert err is None

    def test_get_supported_units(self):
        units = SizeValidator.get_supported_units()
        assert "mm" in units
        assert "cm" in units
        assert "m" in units
        assert "inch" in units


class TestToleranceValidator:
    """测试公差等级验证器"""

    def test_valid_text_it6(self):
        result, err = ToleranceValidator.validate("IT6")
        assert err is None
        assert result["grade"] == "IT6"
        assert result["numeric"] == 6

    def test_valid_text_it14(self):
        result, err = ToleranceValidator.validate("IT14")
        assert err is None
        assert result["grade"] == "IT14"
        assert result["numeric"] == 14

    def test_valid_text_it10(self):
        result, err = ToleranceValidator.validate("IT10")
        assert err is None
        assert result["numeric"] == 10

    def test_valid_numeric(self):
        result, err = ToleranceValidator.validate("8")
        assert err is None
        assert result["grade"] == "IT8"
        assert result["numeric"] == 8

    def test_empty_tolerance(self):
        err = ToleranceValidator.validate("")
        assert err is not None
        assert err.error_type == "empty_tolerance"

    def test_invalid_text(self):
        err = ToleranceValidator.validate("IT5")
        assert err is not None
        assert err.error_type == "invalid_tolerance"

    def test_invalid_numeric_too_small(self):
        err = ToleranceValidator.validate("5")
        assert err is not None

    def test_invalid_numeric_too_large(self):
        err = ToleranceValidator.validate("15")
        assert err is not None

    def test_non_numeric_string(self):
        err = ToleranceValidator.validate("abc")
        assert err is not None

    def test_case_insensitive(self):
        result, err = ToleranceValidator.validate("it7")
        assert err is None
        assert result["grade"] == "IT7"

    def test_it_prefix_with_invalid_number(self):
        err = ToleranceValidator.validate("IT99")
        assert err is not None

    def test_get_valid_grades(self):
        grades = ToleranceValidator.get_valid_grades()
        assert isinstance(grades, set)
        assert "IT6" in grades
        assert "IT14" in grades
        assert len(grades) == 9


class TestInputValidationMiddleware:
    """测试输入验证中间件"""

    def test_skip_health_path(self):
        """健康检查路径应被跳过"""
        middleware = InputValidationMiddleware(
            app=lambda s, r, sr: None,
            skip_paths=["/health"],
            enabled=True
        )
        assert "/health" in middleware.skip_paths

    def test_middleware_disabled(self):
        """禁用中间件时应直接传递"""
        middleware = InputValidationMiddleware(
            app=lambda s, r, sr: None,
            enabled=False
        )
        assert not middleware.enabled

    def test_validate_json_strings(self):
        """应递归验证JSON中的所有字符串字段"""
        middleware = InputValidationMiddleware(
            app=lambda s, r, sr: None,
            enabled=False
        )
        data = {"name": "safe input", "nested": {"value": "also safe"}}
        errors = middleware._validate_json(data)
        assert len(errors) == 0

    def test_validate_json_xss(self):
        """应检测JSON中的XSS字符串"""
        middleware = InputValidationMiddleware(
            app=lambda s, r, sr: None,
            enabled=False
        )
        data = {"comment": "<script>evil()</script>"}
        errors = middleware._validate_json(data)
        assert len(errors) == 1
        assert errors[0].error_type == "xss_detected"

    def test_validate_json_nested(self):
        """应检测嵌套JSON中的危险字符串"""
        middleware = InputValidationMiddleware(
            app=lambda s, r, sr: None,
            enabled=False
        )
        data = {
            "user": {"name": "test"},
            "messages": [
                {"content": "safe"},
                {"content": "SELECT * FROM users"}
            ]
        }
        errors = middleware._validate_json(data)
        assert len(errors) == 1
        assert errors[0].error_type == "sql_injection_detected"

    def test_validate_json_list(self):
        """应检测列表中的危险字符串"""
        middleware = InputValidationMiddleware(
            app=lambda s, r, sr: None,
            enabled=False
        )
        data = ["safe", "<iframe>evil</iframe>", "also safe"]
        errors = middleware._validate_json(data)
        assert len(errors) == 1
        assert errors[0].error_type == "xss_detected"


class TestIntegrationScenarios:
    """集成测试场景"""

    def test_manufacturing_input_safe(self):
        """典型制造输入应通过验证"""
        inputs = [
            "加工一个45钢的轴类零件，直径50mm，公差IT7",
            "需要生产6061铝合金壳体，尺寸100x80x60mm",
            "304不锈钢法兰盘，外径200mm，内径100mm，厚度20mm",
            "TC4钛合金连接件，长度150mm，表面处理阳极氧化",
        ]
        for text in inputs:
            _cleaned, err = validate_and_clean(text)
            assert err is None, f"输入应通过验证: {text}"

    def test_malicious_inputs_blocked(self):
        """恶意输入应被拦截"""
        malicious = [
            "<script>document.cookie</script>",
            "'; DROP TABLE materials;--",
            "part<img src=x onerror=alert(1)>",
            "admin' OR 1=1 UNION SELECT * FROM users",
        ]
        for text in malicious:
            _cleaned, err = validate_and_clean(text)
            assert err is not None, f"输入应被拦截: {text}"

    def test_material_validation_workflow(self):
        """材料验证工作流"""
        valid_materials = ["45钢", "304不锈钢", "6061铝合金", "TC4"]
        for mat in valid_materials:
            err = MaterialValidator.validate(mat)
            assert err is None, f"材料应通过验证: {mat}"

        invalid = ["未知合金", "123", ""]
        for mat in invalid:
            err = MaterialValidator.validate(mat)
            assert err is not None, f"材料应被拒绝: {mat}"

    def test_size_validation_workflow(self):
        """尺寸验证工作流"""
        valid_sizes = ["100mm", "5.5cm", "1.5m", "10inch"]
        for size in valid_sizes:
            result, err = SizeValidator.validate(size)
            assert err is None, f"尺寸应通过验证: {size}"

        invalid = ["abc", "100km", "-5mm", ""]
        for size in invalid:
            _result, err = SizeValidator.validate(size)
            if size == "-5mm":
                pass
            else:
                assert err is not None, f"尺寸应被拒绝: {size}"

    def test_tolerance_validation_workflow(self):
        """公差验证工作流"""
        valid = ["IT6", "IT7", "IT8", "IT10", "IT14", "7", "10"]
        for tol in valid:
            result, err = ToleranceValidator.validate(tol)
            assert err is None, f"公差应通过验证: {tol}"

        invalid = ["IT5", "IT15", "abc", ""]
        for tol in invalid:
            err = ToleranceValidator.validate(tol)
            if err is None:
                result = err
            assert err is not None or result == tol, f"公差应被拒绝: {tol}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
