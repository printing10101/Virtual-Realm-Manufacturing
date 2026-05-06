#!/usr/bin/env python
"""Generate and apply Bosch calibration data to validation_rules.json."""
import sys
import json
sys.path.insert(0, '.')

from app.services.validation_calibrator import ValidationCalibrator

print("Generating Bosch calibration data...")
cal = ValidationCalibrator(data_dir="python/data/datasets/bosch_cnc")
rules = cal.generate_updated_rules()

print("Applying calibration...")
cal.apply_calibration(confirmed=True)

print("Calibration applied successfully!")
print("Last calibrated:", rules["bosch_calibrated"]["last_calibrated"])
print("Processes calibrated:", list(rules["bosch_calibrated"]["process_thresholds"].keys()))
