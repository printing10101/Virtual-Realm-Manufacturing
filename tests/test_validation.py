import sys
import os
import pytest
import math
import asyncio


sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'python'))


from app.models.validation import CuttingDataPoint, ValidationResult, ValidationReport, ValidationStatus

from app.core.task_manager import TaskManager


class MockLogger:
    class Context:
        def __enter__(self): return self
        def __exit__(self, *args): pass
    def log_step(self, task_id, component, step_type, input_data=None, output_data=None):
        return self.Context()


class MockConfig:
    pass


from app.services.dataset_manager import DatasetManager
from app.services.validation_engine import ValidationEngine


@pytest.fixture
def task_manager():
    return TaskManager()


@pytest.fixture
def validation_engine(task_manager):
    engine = ValidationEngine(
        task_manager=task_manager,
        workflow_logger=MockLogger(),
        config=MockConfig()
    )
    return engine


@pytest.fixture
def dataset_manager():
    return DatasetManager()


class TestKienzleForce:
    def test_default_params(self, validation_engine):
        fc = validation_engine.calculate_kienzle_force(150.0, 0.2, 2.0)
        assert fc > 0
        print(f"\nKienzle force at v_c=150, f=0.2, a_p=2.0: {fc:.2f} N")

    def test_feed_rate_effect(self, validation_engine):
        fc1 = validation_engine.calculate_kienzle_force(150.0, 0.1, 2.0)
        fc2 = validation_engine.calculate_kienzle_force(150.0, 0.2, 2.0)
        assert fc2 > fc1

    def test_depth_effect(self, validation_engine):
        fc1 = validation_engine.calculate_kienzle_force(150.0, 0.2, 1.0)
        fc2 = validation_engine.calculate_kienzle_force(150.0, 0.2, 2.0)
        assert fc2 > fc1


class TestTaylorLife:
    def test_default_params(self, validation_engine):
        t = validation_engine.calculate_taylor_life(150.0)
        assert t > 0
        print(f"\nTaylor life at v_c=150: {t:.2f} min")

    def test_higher_speed_shorter_life(self, validation_engine):
        t1 = validation_engine.calculate_taylor_life(100.0)
        t2 = validation_engine.calculate_taylor_life(200.0)
        assert t2 < t1

    def test_custom_constants(self, validation_engine):
        t = validation_engine.calculate_taylor_life(150.0, n=0.3, c=400.0)
        assert t > 0


class TestSurfaceRoughness:
    def test_default_params(self, validation_engine):
        ra = validation_engine.calculate_surface_roughness(0.2)
        assert ra > 0
        print(f"\nSurface roughness at f=0.2, re=0.8: {ra:.2f} μm")

    def test_feed_rate_effect(self, validation_engine):
        ra1 = validation_engine.calculate_surface_roughness(0.1)
        ra2 = validation_engine.calculate_surface_roughness(0.2)
        assert ra2 > ra1

    def test_nose_radius_effect(self, validation_engine):
        ra1 = validation_engine.calculate_surface_roughness(0.2, 0.4)
        ra2 = validation_engine.calculate_surface_roughness(0.2, 0.8)
        assert ra2 < ra1


class TestStatisticalMetrics:
    def test_mape_perfect(self, validation_engine):
        predicted = [100, 200, 300]
        actual = [100, 200, 300]
        mape = validation_engine.calculate_mape(predicted, actual)
        assert mape == 0.0

    def test_mape_10_percent(self, validation_engine):
        predicted = [110, 220, 330]
        actual = [100, 200, 300]
        mape = validation_engine.calculate_mape(predicted, actual)
        assert abs(mape - 10.0) < 0.01

    def test_rmse_perfect(self, validation_engine):
        predicted = [100, 200, 300]
        actual = [100, 200, 300]
        rmse = validation_engine.calculate_rmse(predicted, actual)
        assert rmse == 0.0

    def test_rmse_known(self, validation_engine):
        predicted = [1, 2, 3]
        actual = [1, 2, 4]
        rmse = validation_engine.calculate_rmse(predicted, actual)
        expected = math.sqrt((0 + 0 + 1) / 3)
        assert abs(rmse - expected) < 0.001

    def test_r_squared_perfect(self, validation_engine):
        predicted = [100, 200, 300]
        actual = [100, 200, 300]
        r2 = validation_engine.calculate_r_squared(predicted, actual)
        assert abs(r2 - 1.0) < 0.001

    def test_r_squared_empty(self, validation_engine):
        predicted = []
        actual = []
        r2 = validation_engine.calculate_r_squared(predicted, actual)
        assert r2 == 0.0


class TestDatasetManager:
    def test_list_datasets(self, dataset_manager):
        datasets = dataset_manager.list_datasets()
        assert len(datasets) >= 3

    def test_load_nasa_milling(self, dataset_manager):
        data = dataset_manager.load_dataset("nasa_milling_sample")
        assert len(data) > 0
        assert all(isinstance(p, CuttingDataPoint) for p in data)

    def test_filter_by_operation(self, dataset_manager):
        data = dataset_manager.filter_dataset(operation="milling")
        assert len(data) > 0
        assert all(p.operation == "milling" for p in data)

    def test_filter_by_material(self, dataset_manager):
        data = dataset_manager.filter_dataset(material="45钢")
        assert len(data) > 0
        assert all(p.material == "45钢" for p in data)


class TestValidationEngine:
    @pytest.mark.asyncio
    async def test_online_validation_no_actuals(self, validation_engine):
        task_id = "test_online_1"
        params = {"v_c": 150.0, "f": 0.2, "a_p": 2.0, "material": "45钢"}
        results = await validation_engine.run_online_validation(task_id, params)
        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_online_validation_with_actuals(self, validation_engine):
        task_id = "test_online_2"
        params = {
            "v_c": 150.0, "f": 0.2, "a_p": 2.0, "material": "45钢",
            "F_c_actual": 1500.0
        }
        results = await validation_engine.run_online_validation(task_id, params)
        assert len(results) == 1
        assert results[0].metric_name == "F_c"

    @pytest.mark.asyncio
    async def test_dataset_validation(self, validation_engine):
        task_id = "test_dataset_1"
        params = {"v_c": 150.0, "f": 0.2, "a_p": 2.0}
        report = await validation_engine.run_dataset_validation(task_id, "nasa_milling_sample", params)
        assert report.dataset_name == "nasa_milling_sample"
        assert report.total_samples > 0
        assert report.mape >= 0
        assert report.rmse >= 0

    @pytest.mark.asyncio
    async def test_comprehensive_validation(self, validation_engine):
        task_id = "test_comprehensive_1"
        params = {
            "v_c": 150.0, "f": 0.2, "a_p": 2.0, "material": "45钢",
            "F_c_actual": 1500.0
        }
        result = await validation_engine.run_comprehensive_validation(
            task_id, ["nasa_milling_sample", "phm2010_sample"], params
        )
        assert "online_results" in result
        assert "dataset_reports" in result
        assert "combined_metrics" in result
        assert len(result["dataset_reports"]) == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
