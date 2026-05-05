"""
批量请求处理接口单元测试
"""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.api.batch import (
    SubError,
    SubRequest,
    SubResponse,
    execute_sub_request,
)


@pytest.mark.asyncio
class TestExecuteSubRequest:
    """测试子请求执行"""

    async def test_successful_get_request(self):
        """测试成功的GET请求"""
        request = SubRequest(
            id="test-1",
            method="GET",
            path="/api/tasks/1",
        )

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"id": 1, "status": "completed"}
        mock_response.content = b'{"id": 1, "status": "completed"}'

        with patch("app.api.batch.httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.request = AsyncMock(return_value=mock_response)
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=False)
            mock_client.return_value = mock_instance

            result = await execute_sub_request(request, "http://localhost:8000")

            assert result.id == "test-1"
            assert result.status == 200
            assert result.data == {"id": 1, "status": "completed"}
            assert result.error is None

    async def test_successful_post_request(self):
        """测试成功的POST请求"""
        request = SubRequest(
            id="test-2",
            method="POST",
            path="/api/tasks",
            body={"name": "new task"},
        )

        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.json.return_value = {"id": 2, "name": "new task"}
        mock_response.content = b'{"id": 2, "name": "new task"}'

        with patch("app.api.batch.httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.request = AsyncMock(return_value=mock_response)
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=False)
            mock_client.return_value = mock_instance

            result = await execute_sub_request(request, "http://localhost:8000")

            assert result.id == "test-2"
            assert result.status == 201
            assert result.data == {"id": 2, "name": "new task"}
            assert result.error is None

    async def test_404_error(self):
        """测试404错误"""
        request = SubRequest(
            id="test-3",
            method="GET",
            path="/api/tasks/999",
        )

        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.json.return_value = {"message": "资源不存在"}
        mock_response.content = '{"message": "资源不存在"}'.encode()

        with patch("app.api.batch.httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.request = AsyncMock(return_value=mock_response)
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=False)
            mock_client.return_value = mock_instance

            result = await execute_sub_request(request, "http://localhost:8000")

            assert result.id == "test-3"
            assert result.status == 404
            assert result.data is None
            assert result.error is not None
            assert result.error.code == "404"
            assert result.error.message == "资源不存在"

    async def test_timeout_error(self):
        """测试请求超时"""
        request = SubRequest(
            id="test-4",
            method="GET",
            path="/api/slow-task",
        )

        import httpx

        with patch("app.api.batch.httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.request = AsyncMock(side_effect=httpx.TimeoutException("请求超时"))
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=False)
            mock_client.return_value = mock_instance

            result = await execute_sub_request(request, "http://localhost:8000")

            assert result.id == "test-4"
            assert result.status == 408
            assert result.data is None
            assert result.error is not None
            assert result.error.code == "TIMEOUT"
            assert "超时" in result.error.message

    async def test_network_error(self):
        """测试网络错误"""
        request = SubRequest(
            id="test-5",
            method="GET",
            path="/api/tasks/1",
        )

        with patch("app.api.batch.httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.request = AsyncMock(side_effect=ConnectionError("连接失败"))
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=False)
            mock_client.return_value = mock_instance

            result = await execute_sub_request(request, "http://localhost:8000")

            assert result.id == "test-5"
            assert result.status == 500
            assert result.data is None
            assert result.error is not None
            assert result.error.code == "INTERNAL_ERROR"
            assert "连接失败" in result.error.message

    async def test_request_with_headers(self):
        """测试带请求头的请求"""
        request = SubRequest(
            id="test-6",
            method="GET",
            path="/api/protected",
            headers={"Authorization": "Bearer token123"},
        )

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"protected": True}
        mock_response.content = b'{"protected": true}'

        with patch("app.api.batch.httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.request = AsyncMock(return_value=mock_response)
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=False)
            mock_client.return_value = mock_instance

            result = await execute_sub_request(request, "http://localhost:8000")

            assert result.status == 200

            mock_instance.request.assert_called_once()
            call_kwargs = mock_instance.request.call_args[1]
            assert "headers" in call_kwargs
            assert call_kwargs["headers"] == {"Authorization": "Bearer token123"}

    async def test_put_request_with_body(self):
        """测试PUT请求带请求体"""
        request = SubRequest(
            id="test-7",
            method="PUT",
            path="/api/tasks/1",
            body={"status": "updated"},
        )

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"id": 1, "status": "updated"}
        mock_response.content = b'{"id": 1, "status": "updated"}'

        with patch("app.api.batch.httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.request = AsyncMock(return_value=mock_response)
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=False)
            mock_client.return_value = mock_instance

            result = await execute_sub_request(request, "http://localhost:8000")

            assert result.status == 200
            assert result.data["status"] == "updated"

            mock_instance.request.assert_called_once()
            call_kwargs = mock_instance.request.call_args[1]
            assert "json" in call_kwargs
            assert call_kwargs["json"] == {"status": "updated"}


class TestSubRequestValidation:
    """测试子请求验证"""

    def test_valid_sub_request(self):
        """测试有效的子请求"""
        request = SubRequest(
            id="valid-1",
            method="GET",
            path="/api/tasks",
        )

        assert request.id == "valid-1"
        assert request.method == "GET"
        assert request.path == "/api/tasks"
        assert request.headers is None
        assert request.body is None

    def test_sub_request_with_optional_fields(self):
        """测试带可选字段的子请求"""
        request = SubRequest(
            id="valid-2",
            method="POST",
            path="/api/tasks",
            headers={"Content-Type": "application/json"},
            body={"name": "test"},
        )

        assert request.headers == {"Content-Type": "application/json"}
        assert request.body == {"name": "test"}

    def test_sub_request_missing_required_fields(self):
        """测试缺少必填字段的子请求"""
        with pytest.raises(Exception):
            SubRequest(method="GET", path="/api/tasks")

        with pytest.raises(Exception):
            SubRequest(id="test", path="/api/tasks")

        with pytest.raises(Exception):
            SubRequest(id="test", method="GET")


class TestSubResponse:
    """测试子请求响应"""

    def test_successful_response(self):
        """测试成功响应"""
        response = SubResponse(
            id="resp-1",
            status=200,
            data={"message": "success"},
            error=None,
        )

        assert response.id == "resp-1"
        assert response.status == 200
        assert response.data == {"message": "success"}
        assert response.error is None

    def test_error_response(self):
        """测试错误响应"""
        response = SubResponse(
            id="resp-2",
            status=500,
            data=None,
            error=SubError(code="INTERNAL_ERROR", message="服务器错误"),
        )

        assert response.id == "resp-2"
        assert response.status == 500
        assert response.data is None
        assert response.error is not None
        assert response.error.code == "INTERNAL_ERROR"
        assert response.error.message == "服务器错误"

    def test_response_model_dump(self):
        """测试响应模型序列化"""
        response = SubResponse(
            id="resp-3",
            status=200,
            data={"key": "value"},
            error=None,
        )

        dumped = response.model_dump()

        assert dumped["id"] == "resp-3"
        assert dumped["status"] == 200
        assert dumped["data"] == {"key": "value"}
        assert dumped["error"] is None
