"""关键模块性能基准测试

测试目标：
- 验证核心模块的响应时间和吞吐量
- 确保关键路径性能符合生产要求
- 识别性能瓶颈和优化机会

测试模块：
1. 数据库连接池性能
2. 异常处理性能
3. 认证授权性能
4. API路由性能
5. 数据处理管道性能
"""

import pytest
import time
import asyncio
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch


class TestDatabaseConnectionPoolPerformance:
    """数据库连接池性能测试"""

    def test_connection_pool_creation_time(self):
        """测试连接池创建时间"""
        from app.database.connection import _DatabaseSingletons
        
        start = time.perf_counter()
        singletons = _DatabaseSingletons()
        elapsed = (time.perf_counter() - start) * 1000
        
        # 连接池对象创建应该在1ms内完成
        assert elapsed < 1.0, f"连接池创建时间过长: {elapsed:.3f}ms"
        
        print(f"\n连接池创建时间: {elapsed:.3f}ms")

    def test_concurrent_engine_access(self):
        """测试并发引擎访问性能"""
        from app.database.connection import _DatabaseSingletons
        import threading
        
        singletons = _DatabaseSingletons()
        results = []
        errors = []
        
        def access_engine(thread_id: int):
            try:
                start = time.perf_counter()
                with patch('app.database.connection.create_async_engine') as mock_create:
                    mock_create.return_value = MagicMock()
                    engine = singletons.get_engine()
                    elapsed = (time.perf_counter() - start) * 1000
                    results.append(elapsed)
            except Exception as e:
                errors.append(e)
        
        # 创建20个并发线程
        threads = [threading.Thread(target=access_engine, args=(i,)) for i in range(20)]
        
        start_total = time.perf_counter()
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        total_elapsed = (time.perf_counter() - start_total) * 1000
        
        # 验证无错误
        assert len(errors) == 0, f"并发访问出错: {errors}"
        
        # 验证性能
        avg_time = sum(results) / len(results) if results else 0
        p95_time = sorted(results)[int(len(results) * 0.95)] if results else 0
        
        assert avg_time < 5.0, f"平均访问时间过长: {avg_time:.3f}ms"
        assert p95_time < 10.0, f"P95访问时间过长: {p95_time:.3f}ms"
        
        print(f"\n并发引擎访问性能 (20线程):")
        print(f"  总时间: {total_elapsed:.3f}ms")
        print(f"  平均时间: {avg_time:.3f}ms")
        print(f"  P95时间: {p95_time:.3f}ms")


class TestExceptionHandlerPerformance:
    """异常处理性能测试"""

    def test_exception_creation_performance(self):
        """测试异常对象创建性能"""
        from app.core.exceptions import (
            AppException,
            NotFoundException,
            ValidationException,
            InternalServerException,
        )
        
        iterations = 10000
        start = time.perf_counter()
        
        for _ in range(iterations):
            _ = NotFoundException(message="Test")
            _ = ValidationException(message="Test")
            _ = InternalServerException(message="Test")
        
        elapsed = time.perf_counter() - start
        per_exception_ms = (elapsed / (iterations * 3)) * 1000
        
        # 每个异常创建应该在0.01ms内完成
        assert per_exception_ms < 0.01, f"异常创建过慢: {per_exception_ms:.4f}ms"
        
        print(f"\n异常创建性能 ({iterations*3}次):")
        print(f"  总时间: {elapsed*1000:.2f}ms")
        print(f"  每次: {per_exception_ms:.4f}ms")

    def test_exception_handler_response_time(self):
        """测试异常处理器响应时间"""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from app.core.exceptions import NotFoundException
        from app.core.exception_handlers import register_exception_handlers
        
        app = FastAPI()
        register_exception_handlers(app)
        
        @app.get("/test")
        async def test_endpoint():
            raise NotFoundException(message="Test error")
        
        client = TestClient(app, raise_server_exceptions=False)
        
        # 预热
        for _ in range(10):
            client.get("/test")
        
        # 性能测试
        iterations = 100
        times = []
        
        for _ in range(iterations):
            start = time.perf_counter()
            response = client.get("/test")
            elapsed = (time.perf_counter() - start) * 1000
            times.append(elapsed)
            assert response.status_code == 404
        
        times.sort()
        n = len(times)
        avg_time = sum(times) / n
        p50_time = times[int(n * 0.50)]
        p95_time = times[min(int(n * 0.95), n - 1)]
        
        # 异常处理响应应该在10ms内
        assert p95_time < 10.0, f"P95响应时间过长: {p95_time:.3f}ms"
        
        print(f"\n异常处理响应时间 ({iterations}次):")
        print(f"  平均: {avg_time:.3f}ms")
        print(f"  P50: {p50_time:.3f}ms")
        print(f"  P95: {p95_time:.3f}ms")


class TestAuthenticationPerformance:
    """认证授权性能测试"""

    def test_jwt_token_creation_performance(self):
        """测试JWT令牌创建性能"""
        from app.auth.security import create_access_token
        
        iterations = 1000
        start = time.perf_counter()
        
        for i in range(iterations):
            _ = create_access_token(data={"sub": f"user_{i}"})
        
        elapsed = time.perf_counter() - start
        per_token_ms = (elapsed / iterations) * 1000
        
        # 每个令牌创建应该在1ms内完成
        assert per_token_ms < 1.0, f"JWT令牌创建过慢: {per_token_ms:.3f}ms"
        
        print(f"\nJWT令牌创建性能 ({iterations}次):")
        print(f"  总时间: {elapsed*1000:.2f}ms")
        print(f"  每次: {per_token_ms:.3f}ms")

    def test_jwt_token_verification_performance(self):
        """测试JWT令牌验证性能"""
        from app.auth.security import create_access_token, decode_token
        
        # 创建测试令牌
        token = create_access_token(data={"sub": "test_user"})
        
        iterations = 1000
        start = time.perf_counter()
        
        for _ in range(iterations):
            _ = decode_token(token)
        
        elapsed = time.perf_counter() - start
        per_verify_ms = (elapsed / iterations) * 1000
        
        # 每个令牌验证应该在1ms内完成
        assert per_verify_ms < 1.0, f"JWT令牌验证过慢: {per_verify_ms:.3f}ms"
        
        print(f"\nJWT令牌验证性能 ({iterations}次):")
        print(f"  总时间: {elapsed*1000:.2f}ms")
        print(f"  每次: {per_verify_ms:.3f}ms")


class TestAPIRoutePerformance:
    """API路由性能测试"""

    def test_health_check_endpoint_performance(self):
        """测试健康检查端点性能"""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        
        app = FastAPI()
        
        @app.get("/health")
        async def health_check():
            return {"status": "ok"}
        
        client = TestClient(app)
        
        # 预热
        for _ in range(10):
            client.get("/health")
        
        # 性能测试
        iterations = 100
        times = []
        
        for _ in range(iterations):
            start = time.perf_counter()
            response = client.get("/health")
            elapsed = (time.perf_counter() - start) * 1000
            times.append(elapsed)
            assert response.status_code == 200
        
        times.sort()
        n = len(times)
        avg_time = sum(times) / n
        p95_time = times[min(int(n * 0.95), n - 1)]
        
        # 健康检查应该在5ms内响应
        assert p95_time < 5.0, f"健康检查P95响应过长: {p95_time:.3f}ms"
        
        print(f"\n健康检查端点性能 ({iterations}次):")
        print(f"  平均: {avg_time:.3f}ms")
        print(f"  P95: {p95_time:.3f}ms")

    def test_api_response_serialization_performance(self):
        """测试API响应序列化性能"""
        from app.core.response import success
        
        # 创建测试数据
        test_data = {
            "id": 1,
            "name": "Test Item",
            "description": "A test item for performance testing",
            "tags": ["tag1", "tag2", "tag3"],
            "metadata": {"key1": "value1", "key2": "value2"},
        }
        
        iterations = 10000
        start = time.perf_counter()
        
        for _ in range(iterations):
            _ = success(data=test_data)
        
        elapsed = time.perf_counter() - start
        per_response_ms = (elapsed / iterations) * 1000
        
        # 每个响应构建应该在0.1ms内完成
        assert per_response_ms < 0.1, f"响应序列化过慢: {per_response_ms:.4f}ms"
        
        print(f"\nAPI响应序列化性能 ({iterations}次):")
        print(f"  总时间: {elapsed*1000:.2f}ms")
        print(f"  每次: {per_response_ms:.4f}ms")


class TestDataPipelinePerformance:
    """数据处理管道性能测试"""

    def test_data_validation_performance(self):
        """测试数据校验性能"""
        from pydantic import BaseModel
        
        class TestDataModel(BaseModel):
            id: int
            name: str
            value: float
            tags: list[str]
        
        test_data = {
            "id": 1,
            "name": "Test",
            "value": 3.14,
            "tags": ["a", "b", "c"],
        }
        
        iterations = 10000
        start = time.perf_counter()
        
        for _ in range(iterations):
            _ = TestDataModel(**test_data)
        
        elapsed = time.perf_counter() - start
        per_validation_ms = (elapsed / iterations) * 1000
        
        # 每个校验应该在0.1ms内完成
        assert per_validation_ms < 0.1, f"数据校验过慢: {per_validation_ms:.4f}ms"
        
        print(f"\n数据校验性能 ({iterations}次):")
        print(f"  总时间: {elapsed*1000:.2f}ms")
        print(f"  每次: {per_validation_ms:.4f}ms")

    def test_json_serialization_performance(self):
        """测试JSON序列化性能"""
        import json
        
        test_data = {
            "id": 1,
            "name": "Test Item",
            "description": "A test item for performance testing",
            "tags": ["tag1", "tag2", "tag3"],
            "metadata": {"key1": "value1", "key2": "value2"},
            "nested": {
                "level1": {
                    "level2": {
                        "level3": {"value": "deep"}
                    }
                }
            },
        }
        
        iterations = 10000
        start = time.perf_counter()
        
        for _ in range(iterations):
            _ = json.dumps(test_data)
        
        elapsed = time.perf_counter() - start
        per_serialization_ms = (elapsed / iterations) * 1000
        
        # 每个序列化应该在0.1ms内完成
        assert per_serialization_ms < 0.1, f"JSON序列化过慢: {per_serialization_ms:.4f}ms"
        
        print(f"\nJSON序列化性能 ({iterations}次):")
        print(f"  总时间: {elapsed*1000:.2f}ms")
        print(f"  每次: {per_serialization_ms:.4f}ms")


class TestMemoryPerformance:
    """内存性能测试"""

    def test_connection_pool_memory_footprint(self):
        """测试连接池内存占用"""
        import gc
        from app.database.connection import _DatabaseSingletons
        
        gc.collect()
        initial_objects = len(gc.get_objects())
        
        # 创建多个连接池实例
        pools = []
        for _ in range(10):
            pools.append(_DatabaseSingletons())
        
        gc.collect()
        final_objects = len(gc.get_objects())
        
        object_growth = final_objects - initial_objects
        
        # 对象增长应该在合理范围内
        assert object_growth < 1000, f"对象增长过大: {object_growth}"
        
        print(f"\n连接池内存占用:")
        print(f"  对象增长: {object_growth}")
        
        # 清理
        pools.clear()
        gc.collect()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
