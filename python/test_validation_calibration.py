#!/usr/bin/env python
"""Standalone test script for validation calibration functionality."""
import sys
sys.path.insert(0, '.')

from app.services.validation_engine import ValidationEngine
from app.services.validation_calibrator import ValidationCalibrator

print("=== Testing ValidationEngine ===")
engine = ValidationEngine()
print("1. Rules loaded:", "general_rules" in engine.rules)

print("2. Theoretical validation (pass):")
result = engine.validate_with_theoretical(vibration_rms=0.10, frequency_shift_percent=5.0)
print("   is_valid={}, risk={}".format(result["is_valid"], result["overall_risk"]))

print("3. Theoretical validation (warning):")
result = engine.validate_with_theoretical(vibration_rms=0.35, frequency_shift_percent=5.0)
print("   is_valid={}, risk={}".format(result["is_valid"], result["overall_risk"]))

print("4. Theoretical validation (fail):")
result = engine.validate_with_theoretical(vibration_rms=0.50, frequency_shift_percent=25.0)
print("   is_valid={}, risk={}".format(result["is_valid"], result["overall_risk"]))

print("5. Calibration status:")
status = engine.get_process_calibration_status("OP03")
print("   calibrated={}".format(status["calibrated"]))

print("6. Kienzle force: {:.2f}".format(engine.calculate_kienzle_force(150.0, 0.2, 2.0)))
print("7. Taylor life: {:.2f}".format(engine.calculate_taylor_life(150.0)))
print("8. Surface roughness: {:.2f}".format(engine.calculate_surface_roughness(0.2)))

print("")
print("=== Testing ValidationCalibrator ===")
cal = ValidationCalibrator(data_dir="python/data/datasets/bosch_cnc")

print("9. Dataset summary:")
summary = cal.loader.get_dataset_summary()
print("   total_samples={}".format(summary["total_samples"]))
print("   machines={}".format(summary.get("available_machines", [])))
print("   processes={}".format(summary.get("available_processes", [])))

print("")
print("10. Calibrating OP02...")
try:
    result = cal.calibrate_vibration_thresholds(process="OP02")
    print("   process={}".format(result["process"]))
    print("   samples={}".format(result["sample_count"]))
    print("   confidence={}".format(result["confidence"]))
    print("   x_axis warning={}".format(result["vibration"]["x_axis"]["warning_threshold"]))
    print("   x_axis critical={}".format(result["vibration"]["x_axis"]["critical_threshold"]))
except Exception as e:
    print("   Error: {}".format(e))

print("")
print("11. Calibrating all processes...")
try:
    all_results = cal.calibrate_all_processes()
    print("   Calibrated {} processes".format(len(all_results)))
    for proc, data in list(all_results.items())[:3]:
        print("   {}: samples={}, confidence={}".format(
            proc, data["sample_count"], data["confidence"]
        ))
except Exception as e:
    print("   Error: {}".format(e))

print("")
print("12. Comparing with current rules...")
try:
    comparison = cal.compare_with_current_rules()
    print("   Compared {} processes".format(len(comparison)))
except Exception as e:
    print("   Error: {}".format(e))

print("")
print("All tests completed!")
