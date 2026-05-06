"""物理模型单元测试"""

import pytest

from app.core.physical_models import KienzleModel, TaylorModel, SurfaceRoughnessModel


class TestKienzleModel:
    """Kienzle切削力模型测试"""

    def test_calculate_specific_cutting_force_45steel(self):
        result = KienzleModel.calculate_specific_cutting_force(0.1, "45钢")
        assert result == pytest.approx(1800.0, rel=0.01)

    def test_calculate_specific_cutting_force_default_material(self):
        result = KienzleModel.calculate_specific_cutting_force(0.1)
        assert result == pytest.approx(1800.0, rel=0.01)

    def test_calculate_specific_cutting_force_unknown_material(self):
        result = KienzleModel.calculate_specific_cutting_force(0.1, "unknown")
        assert result == pytest.approx(2000.0, rel=0.01)

    def test_calculate_specific_cutting_force_zero_feed(self):
        result = KienzleModel.calculate_specific_cutting_force(0.0, "45钢")
        assert result == 0.0

    def test_calculate_cutting_force_returns_all_fields(self):
        result = KienzleModel.calculate_cutting_force(150.0, 0.2, 2.0, "45钢")
        assert "cutting_force_N" in result
        assert "specific_cutting_force_Nmm2" in result
        assert "h_um" in result
        assert "b_mm" in result

    def test_get_material_params(self):
        params = KienzleModel.get_material_params("45钢")
        assert params.kc_base == 1800.0
        assert params.mc == 0.25


class TestTaylorModel:
    """Taylor刀具寿命模型测试"""

    def test_calculate_tool_life_45steel(self):
        result = TaylorModel.calculate_tool_life(150.0, "45钢")
        expected = (350.0 / 150.0) ** 4
        assert result == pytest.approx(expected, rel=0.001)

    def test_calculate_tool_life_zero_speed(self):
        result = TaylorModel.calculate_tool_life(0.0, "45钢")
        assert result == 0.0

    def test_calculate_max_speed(self):
        result = TaylorModel.calculate_max_speed(60.0, "45钢")
        assert result > 0

    def test_get_params_unknown_material(self):
        params = TaylorModel.get_params("unknown")
        assert params.C == 350.0
        assert params.n == 0.25


class TestSurfaceRoughnessModel:
    """表面粗糙度模型测试"""

    def test_calculate_ra_basic(self):
        result = SurfaceRoughnessModel.calculate_ra(0.2, 0.8)
        expected = (0.2 ** 2) / (8 * 0.8) * 1000
        assert result == pytest.approx(expected, rel=0.001)

    def test_calculate_ra_default_nose_radius(self):
        result = SurfaceRoughnessModel.calculate_ra(0.2)
        expected = (0.2 ** 2) / (8 * 0.8) * 1000
        assert result == pytest.approx(expected, rel=0.001)

    def test_calculate_ra_zero_nose_radius(self):
        result = SurfaceRoughnessModel.calculate_ra(0.2, 0.0)
        assert result == 0.0

    def test_calculate_max_feed(self):
        result = SurfaceRoughnessModel.calculate_max_feed(1.6, 0.8)
        assert result > 0
        ra_check = SurfaceRoughnessModel.calculate_ra(result, 0.8)
        assert ra_check == pytest.approx(1.6, rel=0.01)
