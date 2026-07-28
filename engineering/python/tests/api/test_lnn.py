"""Tests for LNN API endpoints (/api/v1/lnn)."""

from __future__ import annotations


class TestLNNPredict:
    """Tests for POST /api/v1/lnn/predict."""

    def test_predict_nonexistent_model_returns_not_found(self, client):
        payload = {"model_name": "nonexistent_model_xyz", "input_data": [1.0, 2.0]}
        response = client.post("/api/v1/lnn/predict", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 1001

    def test_predict_empty_input_returns_error(self, client):
        payload = {"model_name": "test_model", "input_data": []}
        response = client.post("/api/v1/lnn/predict", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["code"] in (1002, 1001)

    def test_predict_non_numeric_input_returns_error(self, client):
        payload = {"model_name": "test_model", "input_data": ["abc", 123]}
        response = client.post("/api/v1/lnn/predict", json=payload)
        assert response.status_code in (200, 422)
        if response.status_code == 200:
            data = response.json()
            assert data["code"] in (1002, 1001)

    def test_predict_missing_model_name_returns_422(self, client):
        payload = {"input_data": [1.0, 2.0, 3.0]}
        response = client.post("/api/v1/lnn/predict", json=payload)
        assert response.status_code == 422

    def test_predict_missing_input_data_returns_422(self, client):
        payload = {"model_name": "test"}
        response = client.post("/api/v1/lnn/predict", json=payload)
        assert response.status_code == 422


class TestLNNHealth:
    """Tests for GET /api/v1/lnn/health."""

    def test_health_returns_success(self, client):
        response = client.get("/api/v1/lnn/health")
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 0


class TestLNNModels:
    """Tests for GET /api/v1/lnn/models."""

    def test_list_models_returns_success(self, client):
        response = client.get("/api/v1/lnn/models")
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 0
        assert "models" in data["data"]

    def test_models_response_has_total(self, client):
        response = client.get("/api/v1/lnn/models")
        data = response.json()
        assert "total" in data["data"]


class TestLNNModelInfo:
    """Tests for GET /api/v1/lnn/models/{name}/info."""

    def test_info_nonexistent_model_returns_not_found(self, client):
        response = client.get("/api/v1/lnn/models/nonexistent_xyz_model/info")
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 1001


class TestLNNCache:
    """Tests for GET/DELETE /api/v1/lnn/cache/*."""

    def test_cache_stats_returns_success(self, client):
        response = client.get("/api/v1/lnn/cache/stats")
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 0

    def test_cache_clear_returns_success(self, client):
        response = client.delete("/api/v1/lnn/cache/clear")
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 0


class TestLNNTasks:
    """Tests for GET /api/v1/lnn/tasks."""

    def test_get_tasks_returns_success(self, client):
        response = client.get("/api/v1/lnn/tasks")
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 0


class TestLNNPerformance:
    """Tests for GET /api/v1/lnn/performance."""

    def test_performance_returns_success(self, client):
        response = client.get("/api/v1/lnn/performance")
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 0


class TestLNNDevice:
    """Tests for GET /api/v1/lnn/device/* endpoints."""

    def test_device_info_returns_success(self, client):
        response = client.get("/api/v1/lnn/device/info")
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 0

    def test_device_status_returns_success(self, client):
        response = client.get("/api/v1/lnn/device/status")
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 0

    def test_device_clear_cache_endpoint_responds(self, client):
        response = client.post("/api/v1/lnn/device/clear-cache")
        assert response.status_code == 200
        data = response.json()
        assert "code" in data


class TestLNNValidate:
    """Tests for POST /api/v1/lnn/models/{name}/validate."""

    def test_validate_nonexistent_model_returns_error(self, client):
        payload = {"validation_data": [1.0, 2.0]}
        response = client.post(
            "/api/v1/lnn/models/nonexistent_xyz/validate", json=payload
        )
        assert response.status_code == 200
        data = response.json()
        assert data["code"] in (1001, 2001)


class TestLNNBatchInference:
    """Tests for POST /api/v1/lnn/batch-inference."""

    def test_batch_inference_missing_required_fields_returns_422(self, client):
        response = client.post("/api/v1/lnn/batch-inference", json={})
        assert response.status_code == 422


class TestLNNSecurityHeaders:
    """Verify security headers on LNN endpoints."""

    def test_lnn_endpoint_has_security_headers(self, client):
        response = client.get("/api/v1/lnn/health")
        assert response.headers.get("X-Content-Type-Options") == "nosniff"
