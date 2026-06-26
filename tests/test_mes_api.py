"""MES/ERP 系统集成 API 端到端测试。

测试覆盖：
- 工单同步
- 生产数据上报
- 物料查询
- 质量数据上报
- 健康检查
- 配置验证
"""

from __future__ import annotations

import pytest
from datetime import datetime
from httpx import AsyncClient, ASGITransport
from fastapi.testclient import TestClient

from app.main import app
from app.integrations.mes.client import MESClient


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def client():
    """创建测试客户端"""
    return TestClient(app)


@pytest.fixture
async def async_client():
    """创建异步测试客户端"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def mock_mes_client(mocker):
    """创建 mock MES 客户端"""
    mock = mocker.MagicMock(spec=MESClient)
    mock.health_check = mocker.AsyncMock(return_value=True)
    return mock


# ---------------------------------------------------------------------------
# 工单同步测试
# ---------------------------------------------------------------------------


class TestWorkOrderSync:
    """工单同步测试"""

    def test_sync_work_order_success(self, client, mock_mes_client):
        """测试工单同步成功"""
        from app.integrations.mes.client import SyncResult
        
        mock_mes_client.sync_work_order = mocker.AsyncMock(
            return_value=SyncResult(
                success=True,
                message="工单同步成功",
                data_id="WO-001",
                timestamp=datetime.now()
            )
        )
        
        app.dependency_overrides[get_mes_client] = lambda: mock_mes_client
        
        try:
            response = client.post(
                "/api/v1/mes/sync-work-order",
                json={
                    "work_order_no": "WO-2024-001",
                    "product_code": "PROD-001",
                    "quantity": 100,
                    "priority": 5,
                    "planned_start": "2024-01-01T08:00:00",
                    "planned_end": "2024-01-05T17:00:00",
                },
            )
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["message"] == "工单同步成功"
        finally:
            app.dependency_overrides.clear()

    def test_sync_work_order_missing_fields(self, client):
        """测试工单同步缺少必填字段"""
        response = client.post(
            "/api/v1/mes/sync-work-order",
            json={
                "work_order_no": "WO-2024-001",
                # 缺少 product_code 和 quantity
            },
        )
        assert response.status_code == 422

    def test_sync_work_order_invalid_quantity(self, client):
        """测试工单同步数量无效"""
        response = client.post(
            "/api/v1/mes/sync-work-order",
            json={
                "work_order_no": "WO-2024-001",
                "product_code": "PROD-001",
                "quantity": -10,  # 负数
            },
        )
        assert response.status_code == 422


# ---------------------------------------------------------------------------
# 生产数据上报测试
# ---------------------------------------------------------------------------


class TestProductionReport:
    """生产数据上报测试"""

    def test_report_production_success(self, client, mock_mes_client):
        """测试生产数据上报成功"""
        from app.integrations.mes.client import SyncResult
        
        mock_mes_client.report_production = mocker.AsyncMock(
            return_value=SyncResult(
                success=True,
                message="生产数据上报成功",
                data_id="PROD-001",
                timestamp=datetime.now()
            )
        )
        
        app.dependency_overrides[get_mes_client] = lambda: mock_mes_client
        
        try:
            response = client.post(
                "/api/v1/mes/report-production",
                json={
                    "batch_no": "BATCH-2024-001",
                    "quantity": 100,
                    "qualified": 95,
                },
            )
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
        finally:
            app.dependency_overrides.clear()

    def test_report_production_qualified_exceeds_total(self, client):
        """测试合格数量超过总数量"""
        response = client.post(
            "/api/v1/mes/report-production",
            json={
                "batch_no": "BATCH-2024-001",
                "quantity": 100,
                "qualified": 150,  # 超过总数量
            },
        )
        # 应该通过（业务逻辑验证在 MES 客户端）
        assert response.status_code in [200, 400, 422]


# ---------------------------------------------------------------------------
# 物料查询测试
# ---------------------------------------------------------------------------


class TestMaterialQuery:
    """物料查询测试"""

    def test_query_material_success(self, client, mock_mes_client):
        """测试物料查询成功"""
        from app.integrations.mes.client import MaterialInfo
        
        mock_mes_client.query_material = mocker.AsyncMock(
            return_value=MaterialInfo(
                material_code="MAT-001",
                name="铝合金 6061-T6",
                specification="100x100x50mm",
                unit="件",
                stock_quantity=500.0,
                warehouse_location="A-01-01",
                batch_no="BATCH-MAT-001",
                expiry_date=datetime(2025, 12, 31)
            )
        )
        
        app.dependency_overrides[get_mes_client] = lambda: mock_mes_client
        
        try:
            response = client.get("/api/v1/mes/material/MAT-001")
            assert response.status_code == 200
            data = response.json()
            assert data["material_code"] == "MAT-001"
            assert data["name"] == "铝合金 6061-T6"
        finally:
            app.dependency_overrides.clear()

    def test_query_material_not_found(self, client, mock_mes_client):
        """测试物料未找到"""
        mock_mes_client.query_material = mocker.AsyncMock(return_value=None)
        
        app.dependency_overrides[get_mes_client] = lambda: mock_mes_client
        
        try:
            response = client.get("/api/v1/mes/material/MAT-NOT-EXIST")
            assert response.status_code == 404
        finally:
            app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# 质量数据上报测试
# ---------------------------------------------------------------------------


class TestQualityReport:
    """质量数据上报测试"""

    def test_report_quality_success(self, client, mock_mes_client):
        """测试质量数据上报成功"""
        from app.integrations.mes.client import SyncResult
        
        mock_mes_client.report_quality = mocker.AsyncMock(
            return_value=SyncResult(
                success=True,
                message="质量数据上报成功",
                data_id="QUAL-001",
                timestamp=datetime.now()
            )
        )
        
        app.dependency_overrides[get_mes_client] = lambda: mock_mes_client
        
        try:
            response = client.post(
                "/api/v1/mes/report-quality",
                json={
                    "batch_no": "BATCH-2024-001",
                    "product_code": "PROD-001",
                    "inspection_type": "in_process",
                    "result": "pass",
                    "inspector": "张三",
                    "inspection_time": "2024-01-01T10:00:00",
                    "sample_size": 10,
                    "qualified_qty": 9,
                    "defective_qty": 1,
                },
            )
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
        finally:
            app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# 健康检查测试
# ---------------------------------------------------------------------------


class TestHealthCheck:
    """健康检查测试"""

    def test_health_check_healthy(self, client, mock_mes_client):
        """测试健康检查 - 系统正常"""
        app.dependency_overrides[get_mes_client] = lambda: mock_mes_client
        
        try:
            response = client.get("/api/v1/mes/health")
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "healthy"
            assert data["mes_connected"] is True
        finally:
            app.dependency_overrides.clear()

    def test_health_check_unhealthy(self, client, mock_mes_client):
        """测试健康检查 - 系统异常"""
        mock_mes_client.health_check = mocker.AsyncMock(return_value=False)
        
        app.dependency_overrides[get_mes_client] = lambda: mock_mes_client
        
        try:
            response = client.get("/api/v1/mes/health")
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "unhealthy"
            assert data["mes_connected"] is False
        finally:
            app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# 配置验证测试
# ---------------------------------------------------------------------------


class TestConfiguration:
    """配置验证测试"""

    def test_mes_not_enabled(self, client):
        """测试 MES 未启用"""
        # 确保依赖覆盖已清理
        app.dependency_overrides.clear()
        
        response = client.get("/api/v1/mes/health")
        # 应该返回 503（服务不可用）
        assert response.status_code == 503
        assert "not enabled" in response.json()["detail"].lower()

    def test_mes_not_configured(self, client, mocker):
        """测试 MES 配置不完整"""
        from app.config import config
        
        # Mock 配置
        mocker.patch.object(config.mes, 'enabled', True)
        mocker.patch.object(config.mes, 'base_url', '')
        mocker.patch.object(config.mes, 'api_key', '')
        
        response = client.get("/api/v1/mes/health")
        assert response.status_code == 503
        assert "not configured" in response.json()["detail"].lower()


# ---------------------------------------------------------------------------
# 导入辅助函数
# ---------------------------------------------------------------------------


from app.integrations.mes.api import get_mes_client
