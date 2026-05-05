import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'python'))

from app.services.tool_wear_predictor import ToolWearPredictor
from app.models.validation import WearPhase, UrgencyLevel

predictor = ToolWearPredictor()

def test_wear_curve_prediction():
    print("=== Test 1: Wear Curve Prediction ===")
    params = {
        "cutting_speed": 150.0,
        "feed_rate": 0.2,
        "depth_of_cut": 1.5,
        "material_type": "steel_45",
        "tool_type": "carbide"
    }
    curve = predictor.predict_wear_curve(params)
    assert len(curve.data_points) > 0, "Should have data points"
    assert curve.total_life > 0, "Total life should be positive"
    assert curve.time_to_threshold > 0, "Time to threshold should be positive"
    assert 0 < curve.confidence <= 1, "Confidence should be between 0 and 1"
    print(f"  Total life: {curve.total_life:.1f} min")
    print(f"  Data points: {len(curve.data_points)}")
    print(f"  Confidence: {curve.confidence:.2f}")
    print(f"  First point VB: {curve.data_points[0].vb:.4f} mm")
    print(f"  Last point VB: {curve.data_points[-1].vb:.4f} mm")
    print("  PASSED\n")

def test_phase_identification():
    print("=== Test 2: Wear Phase Identification ===")
    params = {
        "cutting_speed": 150.0,
        "feed_rate": 0.2,
        "depth_of_cut": 1.5,
        "material_type": "steel_45",
        "tool_type": "carbide"
    }
    curve = predictor.predict_wear_curve(params)
    phases_seen = set()
    for point in curve.data_points:
        phases_seen.add(point.phase)
    print(f"  Phases identified: {[p.value for p in phases_seen]}")
    assert len(phases_seen) >= 1, "Should have at least one phase"
    for point in curve.data_points:
        if point.vb < 0.05:
            assert point.phase == WearPhase.INITIAL, f"VB={point.vb} should be initial"
        elif point.vb < 0.2:
            assert point.phase == WearPhase.STEADY, f"VB={point.vb} should be steady"
        else:
            assert point.phase == WearPhase.ACCELERATED, f"VB={point.vb} should be accelerated"
    print("  PASSED\n")

def test_remaining_life():
    print("=== Test 3: Remaining Life Prediction ===")
    params = {
        "cutting_speed": 150.0,
        "feed_rate": 0.2,
        "depth_of_cut": 1.5,
        "material_type": "steel_45",
        "tool_type": "carbide"
    }
    life_0 = predictor.predict_remaining_life(0.0, params)
    life_01 = predictor.predict_remaining_life(0.1, params)
    life_02 = predictor.predict_remaining_life(0.2, params)
    print(f"  Remaining life at VB=0.0: {life_0:.1f} min")
    print(f"  Remaining life at VB=0.1: {life_01:.1f} min")
    print(f"  Remaining life at VB=0.2: {life_02:.1f} min")
    assert life_0 > life_01 > life_02 >= 0, "Remaining life should decrease with wear"
    print("  PASSED\n")

def test_replacement_threshold():
    print("=== Test 4: Replacement Threshold ===")
    t_default = predictor.get_replacement_threshold()
    t_steel = predictor.get_replacement_threshold("steel_45")
    t_ti = predictor.get_replacement_threshold("titanium_ti64")
    t_al = predictor.get_replacement_threshold("aluminum_6061")
    print(f"  Default threshold: {t_default} mm")
    print(f"  Steel 45 threshold: {t_steel} mm")
    print(f"  Titanium threshold: {t_ti} mm")
    print(f"  Aluminum threshold: {t_al} mm")
    assert t_default == 0.3, "Default should be 0.3"
    assert t_ti < t_steel, "Harder material should have lower threshold"
    assert t_al > t_steel, "Softer material should have higher threshold"
    print("  PASSED\n")

def test_parameter_suggestions():
    print("=== Test 5: Parameter Adjustment Suggestions ===")
    params = {
        "cutting_speed": 150.0,
        "feed_rate": 0.2,
        "depth_of_cut": 1.5,
        "coolant_flow": 10.0,
        "material_type": "steel_45",
        "tool_type": "carbide"
    }
    sugg_normal = predictor.suggest_parameter_adjustment(0.05, 100.0, params)
    sugg_warning = predictor.suggest_parameter_adjustment(0.18, 30.0, params)
    sugg_critical = predictor.suggest_parameter_adjustment(0.26, 5.0, params)
    
    assert sugg_normal.urgency == UrgencyLevel.NORMAL, "VB=0.05 should be normal"
    assert sugg_warning.urgency == UrgencyLevel.WARNING, "VB=0.18 should be warning"
    assert sugg_critical.urgency == UrgencyLevel.CRITICAL, "VB=0.26 should be critical"
    
    print(f"  Normal urgency suggestions: {len(sugg_normal.suggestions)}")
    print(f"  Warning urgency suggestions: {len(sugg_warning.suggestions)}")
    print(f"  Critical urgency suggestions: {len(sugg_critical.suggestions)}")
    
    for s in sugg_critical.suggestions:
        assert s.param_type is not None, "Each suggestion should have param_type"
        assert s.expected_effect is not None, "Each suggestion should have expected_effect"
    print("  PASSED\n")

def test_material_variants():
    print("=== Test 6: Different Materials ===")
    materials = ["aluminum_6061", "steel_45", "stainless_304", "titanium_ti64", "inconel_718"]
    for mat in materials:
        params = {
            "cutting_speed": 150.0,
            "feed_rate": 0.2,
            "depth_of_cut": 1.5,
            "material_type": mat,
            "tool_type": "carbide"
        }
        curve = predictor.predict_wear_curve(params)
        print(f"  {mat}: total_life={curve.total_life:.1f} min, confidence={curve.confidence:.2f}")
    print("  PASSED\n")

def test_calibration():
    print("=== Test 7: Calibration with Measurement ===")
    params = {
        "cutting_speed": 150.0,
        "feed_rate": 0.2,
        "depth_of_cut": 1.5,
        "material_type": "steel_45",
        "tool_type": "carbide"
    }
    result = predictor.calibrate_with_measurement(0.12, 30.0, params)
    assert "deviation" in result, "Should have deviation"
    assert "correction_factor" in result, "Should have correction_factor"
    assert "calibrated_curve" in result, "Should have calibrated_curve"
    print(f"  Deviation: {result['deviation']:.4f} mm")
    print(f"  Deviation %: {result['deviation_percent']:.2f}%")
    print(f"  Correction factor: {result['correction_factor']:.3f}")
    print("  PASSED\n")

def test_supported_models():
    print("=== Test 8: Supported Models ===")
    models = predictor.get_supported_models()
    assert len(models) >= 3, "Should have at least 3 models"
    for m in models:
        assert "name" in m, "Model should have name"
        assert "formula" in m, "Model should have formula"
        print(f"  Model: {m['name']}")
    print("  PASSED\n")

def test_curve_to_dict():
    print("=== Test 9: Curve Serialization ===")
    params = {
        "cutting_speed": 150.0,
        "feed_rate": 0.2,
        "depth_of_cut": 1.5,
        "material_type": "steel_45",
        "tool_type": "carbide"
    }
    curve = predictor.predict_wear_curve(params)
    d = curve.to_dict()
    assert "data_points" in d, "Should have data_points"
    assert "total_life" in d, "Should have total_life"
    assert "wear_rate_avg" in d, "Should have wear_rate_avg"
    assert "confidence" in d, "Should have confidence"
    for dp in d["data_points"]:
        assert "time" in dp, "Data point should have time"
        assert "vb" in dp, "Data point should have vb"
        assert "wear_rate" in dp, "Data point should have wear_rate"
        assert "phase" in dp, "Data point should have phase"
    print("  PASSED\n")

if __name__ == "__main__":
    print("\n*** Tool Wear Prediction System Tests ***\n")
    test_wear_curve_prediction()
    test_phase_identification()
    test_remaining_life()
    test_replacement_threshold()
    test_parameter_suggestions()
    test_material_variants()
    test_calibration()
    test_supported_models()
    test_curve_to_dict()
    print("*** All 9 tests passed! ***\n")
