"""Test script for validation calibration functionality."""

import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.services.validation_engine import ValidationEngine
from app.services.validation_calibrator import ValidationCalibrator


class TestValidationEngine:
    @pytest.fixture
    def engine(self):
        return ValidationEngine()

    def test_init_loads_rules(self, engine):
        assert engine.rules is not None
        assert "general_rules" in engine.rules

    def test_backup_and_restore(self, engine, tmp_path):
        engine.rules_path = tmp_path / "rules.json"
        engine.save_rules()
        backup = engine.backup_rules()
        assert backup.exists()

    def test_validate_with_theoretical_pass(self, engine):
        result = engine.validate_with_theoretical(vibration_rms=0.10, frequency_shift_percent=5.0)
        assert result["is_valid"] is True
        assert result["overall_risk"] == "low"

    def test_validate_with_theoretical_warning(self, engine):
        result = engine.validate_with_theoretical(vibration_rms=0.35, frequency_shift_percent=5.0)
        assert any(c["status"] == "warning" for c in result["checks"])
        assert result["overall_risk"] == "medium"

    def test_validate_with_theoretical_fail(self, engine):
        result = engine.validate_with_theoretical(vibration_rms=0.50, frequency_shift_percent=25.0)
        assert result["overall_risk"] == "high"

    def test_get_process_calibration_status_not_calibrated(self, engine):
        status = engine.get_process_calibration_status("OP03")
        assert status["calibrated"] is False

    def test_kienzle_force(self, engine):
        fc = engine.calculate_kienzle_force(150.0, 0.2, 2.0)
        assert fc > 0

    def test_taylor_life(self, engine):
        t = engine.calculate_taylor_life(150.0)
        assert t > 0

    def test_surface_roughness(self, engine):
        ra = engine.calculate_surface_roughness(0.2)
        assert ra > 0


class TestValidationCalibrator:
    @pytest.fixture
    def calibrator(self):
        return ValidationCalibrator()

    def test_calibrate_vibration_thresholds(self, calibrator):
        try:
            result = calibrator.calibrate_vibration_thresholds(process="OP02")
            assert "vibration" in result
            assert "x_axis" in result["vibration"]
            assert "warning_threshold" in result["vibration"]["x_axis"]
            assert "critical_threshold" in result["vibration"]["x_axis"]
        except ValueError as e:
            pytest.skip(f"No data available: {e}")

    def test_calibrate_all_processes(self, calibrator):
        try:
            results = calibrator.calibrate_all_processes()
            assert len(results) > 0
        except ValueError as e:
            pytest.skip(f"No data available: {e}")

    def test_generate_updated_rules(self, calibrator):
        try:
            rules = calibrator.generate_updated_rules()
            assert "bosch_calibrated" in rules
            assert len(rules["bosch_calibrated"]["process_thresholds"]) > 0
        except ValueError as e:
            pytest.skip(f"No data available: {e}")

    def test_compare_with_current_rules(self, calibrator):
        try:
            comparison = calibrator.compare_with_current_rules()
            assert isinstance(comparison, dict)
        except ValueError as e:
            pytest.skip(f"No data available: {e}")

    def test_apply_calibration_cancelled(self, calibrator):
        result = calibrator.apply_calibration(confirmed=False)
        assert result["status"] == "cancelled"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])