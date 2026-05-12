"""
Test Response Utilities

Tests for:
- ErrorCode: Enumeration of error codes
- success(): Success response builder
- error(): Error response builder with optional fields
"""
import pytest
from app.core.response import success, error, ErrorCode


class TestErrorCode:
    """Test ErrorCode enumeration"""

    def test_success_code(self):
        assert ErrorCode.SUCCESS == "SUCCESS"

    def test_error_codes_defined(self):
        assert ErrorCode.INTERNAL_ERROR == "INTERNAL_ERROR"
        assert ErrorCode.NOT_FOUND == "NOT_FOUND"
        assert ErrorCode.INVALID_REQUEST == "INVALID_REQUEST"
        assert ErrorCode.UNAUTHORIZED == "UNAUTHORIZED"

    def test_domain_specific_codes(self):
        assert ErrorCode.FILE_NOT_FOUND == "FILE_NOT_FOUND"
        assert ErrorCode.CAD_GENERATION_ERROR == "CAD_GENERATION_ERROR"
        assert ErrorCode.SERVICE_UNAVAILABLE == "SERVICE_UNAVAILABLE"


class TestSuccessResponse:
    """Test success response builder"""

    def test_success_with_default_values(self):
        result = success()
        assert result["code"] == ErrorCode.SUCCESS
        assert result["message"] == "Success"
        assert result["data"] is None

    def test_success_with_custom_message(self):
        result = success(message="Operation completed")
        assert result["message"] == "Operation completed"

    def test_success_with_data(self):
        data = {"id": "123", "name": "test"}
        result = success(data=data)
        assert result["data"] == data
        assert result["data"]["id"] == "123"

    def test_success_with_data_and_message(self):
        data = {"items": [1, 2, 3]}
        result = success(data=data, message="Items retrieved")
        assert result["data"] == data
        assert result["message"] == "Items retrieved"

    def test_success_with_empty_data(self):
        result = success(data=[])
        assert result["data"] == []

    def test_success_with_dict_data(self):
        data = {"key": "value", "count": 42}
        result = success(data=data)
        assert result["data"]["key"] == "value"
        assert result["data"]["count"] == 42

    def test_success_structure(self):
        result = success()
        assert "code" in result
        assert "message" in result
        assert "data" in result
        assert len(result) == 3


class TestErrorResponse:
    """Test error response builder"""

    def test_error_with_code_only(self):
        result = error(ErrorCode.NOT_FOUND)
        assert result["code"] == ErrorCode.NOT_FOUND
        assert result["message"] == "Error"
        assert result["data"] is None

    def test_error_with_custom_message(self):
        result = error(ErrorCode.INTERNAL_ERROR, message="Database connection failed")
        assert result["code"] == ErrorCode.INTERNAL_ERROR
        assert result["message"] == "Database connection failed"

    def test_error_with_detail(self):
        detail = {"field": "email", "reason": "invalid format"}
        result = error(ErrorCode.INVALID_REQUEST, detail=detail)
        assert result["detail"] == detail
        assert result["data"] is None

    def test_error_with_suggestion(self):
        suggestion = "Please check the input format and try again"
        result = error(ErrorCode.INVALID_REQUEST, suggestion=suggestion)
        assert result["suggestion"] == suggestion

    def test_error_with_all_fields(self):
        result = error(
            code=ErrorCode.INVALID_REQUEST,
            message="Validation failed",
            detail={"errors": ["field required"]},
            suggestion="Fill in all required fields",
        )
        assert result["code"] == ErrorCode.INVALID_REQUEST
        assert result["message"] == "Validation failed"
        assert "errors" in result["detail"]
        assert result["suggestion"] == "Fill in all required fields"

    def test_error_without_optional_fields(self):
        result = error(ErrorCode.NOT_FOUND)
        assert "detail" not in result
        assert "suggestion" not in result

    def test_error_with_none_detail(self):
        result = error(ErrorCode.INTERNAL_ERROR, detail=None)
        assert result["detail"] is None

    def test_error_with_none_suggestion(self):
        result = error(ErrorCode.INTERNAL_ERROR, suggestion=None)
        assert result["suggestion"] is None


class TestErrorResponseEdgeCases:
    """Test edge cases for error responses"""

    def test_error_with_empty_string_message(self):
        result = error(ErrorCode.INTERNAL_ERROR, message="")
        assert result["message"] == ""

    def test_error_with_numeric_detail(self):
        result = error(ErrorCode.INVALID_REQUEST, detail=42)
        assert result["detail"] == 42

    def test_error_with_list_detail(self):
        result = error(ErrorCode.INVALID_REQUEST, detail=["error1", "error2"])
        assert result["detail"] == ["error1", "error2"]

    def test_error_code_string_values(self):
        for code in ErrorCode:
            result = error(code)
            assert isinstance(result["code"], str)
            assert result["code"] == code.value


class TestResponseIntegration:
    """Test response patterns in integration scenarios"""

    def test_validation_error_response(self):
        result = error(
            code=ErrorCode.INVALID_REQUEST,
            message="输入验证失败",
            detail={"field": "cutting_speed", "reason": "must be positive"},
            suggestion="请输入大于0的切削速度值",
        )
        assert result["code"] == "INVALID_REQUEST"
        assert "detail" in result

    def test_not_found_response(self):
        result = error(
            code=ErrorCode.NOT_FOUND,
            message="资源未找到",
            detail={"resource": "experience", "id": "invalid-id"},
        )
        assert result["code"] == "NOT_FOUND"

    def test_service_unavailable_response(self):
        result = error(
            code=ErrorCode.SERVICE_UNAVAILABLE,
            message="服务暂不可用",
            suggestion="请稍后重试或联系管理员",
        )
        assert result["code"] == "SERVICE_UNAVAILABLE"

    def test_success_with_pagination(self):
        data = {
            "items": [{"id": 1}, {"id": 2}],
            "total": 100,
            "page": 1,
            "page_size": 10,
        }
        result = success(data=data, message="Page retrieved")
        assert result["data"]["total"] == 100
        assert result["data"]["page"] == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
