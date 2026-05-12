"""
Test Exception Handlers

Tests for:
- AppError: Base application error
- NotFoundError: Resource not found error
- ValidationFailedError: Input validation error
- InternalError: Internal service error
- ServiceUnavailableError: Service unavailable error
- Exception handlers registration
"""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel

from app.core.exception_handlers import (
    AppError,
    NotFoundError,
    ValidationFailedError,
    InternalError,
    ServiceUnavailableError,
    register_exception_handlers,
    generic_exception_handler,
    validation_exception_handler,
    http_exception_handler,
    record_not_found_handler,
    repository_error_handler,
)
from app.core.repository.exceptions import RecordNotFoundError as RepoRecordNotFoundError
from app.core.repository.exceptions import RepositoryError
from starlette.exceptions import HTTPException as StarletteHTTPException


class TestAppError:
    """Test base AppError"""

    def test_default_initialization(self):
        error = AppError("Test error")
        assert error.detail == "Test error"
        assert error.status_code == 500
        assert error.error_code is None

    def test_custom_status_code(self):
        error = AppError("Custom error", status_code=418)
        assert error.status_code == 418

    def test_custom_error_code(self):
        error = AppError("Error with code", error_code="CUSTOM_CODE")
        assert error.error_code == "CUSTOM_CODE"

    def test_full_customization(self):
        error = AppError("Full error", status_code=403, error_code="FORBIDDEN")
        assert error.detail == "Full error"
        assert error.status_code == 403
        assert error.error_code == "FORBIDDEN"

    def test_inherits_from_exception(self):
        error = AppError("Test")
        assert isinstance(error, Exception)


class TestNotFoundError:
    """Test NotFoundError"""

    def test_default_message(self):
        error = NotFoundError()
        assert error.detail == "资源未找到"
        assert error.status_code == 404
        assert error.error_code == "NOT_FOUND"

    def test_custom_message(self):
        error = NotFoundError(detail="用户不存在")
        assert error.detail == "用户不存在"

    def test_custom_error_code(self):
        error = NotFoundError(error_code="USER_NOT_FOUND")
        assert error.error_code == "USER_NOT_FOUND"


class TestValidationFailedError:
    """Test ValidationFailedError"""

    def test_default_message(self):
        error = ValidationFailedError()
        assert error.detail == "输入验证失败"
        assert error.status_code == 400
        assert error.error_code == "VALIDATION_FAILED"

    def test_custom_message(self):
        error = ValidationFailedError(detail="参数格式错误")
        assert error.detail == "参数格式错误"


class TestInternalError:
    """Test InternalError"""

    def test_default_message(self):
        error = InternalError()
        assert error.detail == "内部服务错误"
        assert error.status_code == 500
        assert error.error_code == "INTERNAL_ERROR"

    def test_custom_message(self):
        error = InternalError(detail="数据库连接失败")
        assert error.detail == "数据库连接失败"


class TestServiceUnavailableError:
    """Test ServiceUnavailableError"""

    def test_default_message(self):
        error = ServiceUnavailableError()
        assert error.detail == "服务暂不可用"
        assert error.status_code == 503
        assert error.error_code == "SERVICE_UNAVAILABLE"

    def test_custom_message(self):
        error = ServiceUnavailableError(detail="GPU资源暂不可用")
        assert error.detail == "GPU资源暂不可用"


class TestExceptionHandlersIntegration:
    """Test exception handlers with FastAPI app"""

    @pytest.fixture
    def app_with_handlers(self):
        app = FastAPI()
        register_exception_handlers(app)
        return app

    def test_app_error_handler(self, app_with_handlers):
        @app_with_handlers.get("/test")
        async def test_endpoint():
            raise AppError("Test error", status_code=400, error_code="TEST")

        client = TestClient(app_with_handlers, raise_server_exceptions=False)
        response = client.get("/test")
        assert response.status_code == 400
        data = response.json()
        assert data["detail"] == "Test error"
        assert data["error_code"] == "TEST"

    def test_not_found_error_handler(self, app_with_handlers):
        @app_with_handlers.get("/notfound")
        async def test_endpoint():
            raise NotFoundError(detail="Experience not found")

        client = TestClient(app_with_handlers, raise_server_exceptions=False)
        response = client.get("/notfound")
        assert response.status_code == 404

    def test_validation_failed_error_handler(self, app_with_handlers):
        @app_with_handlers.get("/invalid")
        async def test_endpoint():
            raise ValidationFailedError(detail="Invalid parameters")

        client = TestClient(app_with_handlers, raise_server_exceptions=False)
        response = client.get("/invalid")
        assert response.status_code == 400

    def test_internal_error_handler(self, app_with_handlers):
        @app_with_handlers.get("/internal")
        async def test_endpoint():
            raise InternalError(detail="Database error")

        client = TestClient(app_with_handlers, raise_server_exceptions=False)
        response = client.get("/internal")
        assert response.status_code == 500

    def test_service_unavailable_error_handler(self, app_with_handlers):
        @app_with_handlers.get("/unavailable")
        async def test_endpoint():
            raise ServiceUnavailableError(detail="GPU busy")

        client = TestClient(app_with_handlers, raise_server_exceptions=False)
        response = client.get("/unavailable")
        assert response.status_code == 503

    def test_generic_exception_handler(self, app_with_handlers):
        @app_with_handlers.get("/crash")
        async def test_endpoint():
            raise ValueError("Unexpected error")

        client = TestClient(app_with_handlers, raise_server_exceptions=False)
        response = client.get("/crash")
        assert response.status_code == 500
        data = response.json()
        assert "error_code" in data
        assert "ID:" in data["detail"]


class TestHttpExceptionHandler:
    """Test Starlette HTTP exception handling"""

    @pytest.fixture
    def app_with_handlers(self):
        app = FastAPI()
        register_exception_handlers(app)
        return app

    def test_http_exception_handler(self, app_with_handlers):
        @app_with_handlers.get("/http")
        async def test_endpoint():
            raise StarletteHTTPException(status_code=401, detail="Unauthorized")

        client = TestClient(app_with_handlers, raise_server_exceptions=False)
        response = client.get("/http")
        assert response.status_code == 401
        data = response.json()
        assert data["detail"] == "Unauthorized"


class TestRecordNotFoundHandler:
    """Test record not found handler"""

    @pytest.fixture
    def app_with_handlers(self):
        app = FastAPI()
        register_exception_handlers(app)
        return app

    def test_record_not_found_handler(self, app_with_handlers):
        @app_with_handlers.get("/record/{id}")
        async def test_endpoint(id: str):
            raise RepoRecordNotFoundError(id, repository_type="json")

        client = TestClient(app_with_handlers, raise_server_exceptions=False)
        response = client.get("/record/test123")
        assert response.status_code == 404
        data = response.json()
        assert data["error_code"] == "RECORD_NOT_FOUND"


class TestRepositoryErrorHandler:
    """Test repository error handler"""

    @pytest.fixture
    def app_with_handlers(self):
        app = FastAPI()
        register_exception_handlers(app)
        return app

    def test_repository_error_handler(self, app_with_handlers):
        @app_with_handlers.get("/repo")
        async def test_endpoint():
            raise RepositoryError("Storage write failed", repository_type="json")

        client = TestClient(app_with_handlers, raise_server_exceptions=False)
        response = client.get("/repo")
        assert response.status_code == 500
        data = response.json()
        assert data["error_code"] == "REPOSITORY_ERROR"


class TestValidationExceptionHandler:
    """Test FastAPI validation exception handling"""

    @pytest.fixture
    def app_with_handlers(self):
        app = FastAPI()
        register_exception_handlers(app)

        class Item(BaseModel):
            name: str
            price: float

        @app_with_handlers.post("/item")
        async def create_item(item: Item):
            return item

        return app

    def test_validation_error_format(self, app_with_handlers):
        client = TestClient(app_with_handlers, raise_server_exceptions=False)
        response = client.post("/item", json={"name": "test"})
        assert response.status_code == 422
        data = response.json()
        assert "detail" in data
        assert data["error_code"] == "VALIDATION_ERROR"


class TestExceptionHandlerRegistration:
    """Test handler registration function"""

    def test_register_exception_handlers(self):
        app = FastAPI()
        register_exception_handlers(app)
        assert AppError in app.exception_handlers
        assert StarletteHTTPException in app.exception_handlers
        assert RequestValidationError in app.exception_handlers
        assert Exception in app.exception_handlers


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
