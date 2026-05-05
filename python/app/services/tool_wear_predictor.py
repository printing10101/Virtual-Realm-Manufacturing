import math
from typing import Any

from app.models.validation import (
    AdjustmentSuggestion,
    AdjustmentSuggestionItem,
    UrgencyLevel,
    WearCurve,
    WearDataPoint,
    WearPhase,
)


class MaterialParams:
    def __init__(self, taylor_n: float, taylor_C: float, usui_A: float,
                 usui_B: float, hardness_factor: float, name: str):
        self.taylor_n = taylor_n
        self.taylor_C = taylor_C
        self.usui_A = usui_A
        self.usui_B = usui_B
        self.hardness_factor = hardness_factor
        self.name = name


MATERIAL_PARAMS = {
    "aluminum_6061": MaterialParams(
        taylor_n=0.40, taylor_C=450.0, usui_A=0.002, usui_B=1200.0,
        hardness_factor=0.6, name="Aluminum 6061"
    ),
    "aluminum_7075": MaterialParams(
        taylor_n=0.35, taylor_C=380.0, usui_A=0.004, usui_B=1100.0,
        hardness_factor=0.75, name="Aluminum 7075"
    ),
    "steel_45": MaterialParams(
        taylor_n=0.25, taylor_C=280.0, usui_A=0.008, usui_B=900.0,
        hardness_factor=1.0, name="Steel 45#"
    ),
    "steel_4140": MaterialParams(
        taylor_n=0.23, taylor_C=250.0, usui_A=0.010, usui_B=850.0,
        hardness_factor=1.1, name="Steel 4140"
    ),
    "stainless_304": MaterialParams(
        taylor_n=0.20, taylor_C=200.0, usui_A=0.015, usui_B=800.0,
        hardness_factor=1.3, name="Stainless Steel 304"
    ),
    "stainless_316": MaterialParams(
        taylor_n=0.18, taylor_C=180.0, usui_A=0.018, usui_B=750.0,
        hardness_factor=1.4, name="Stainless Steel 316"
    ),
    "titanium_ti64": MaterialParams(
        taylor_n=0.15, taylor_C=120.0, usui_A=0.025, usui_B=650.0,
        hardness_factor=1.8, name="Titanium Ti-6Al-4V"
    ),
    "inconel_718": MaterialParams(
        taylor_n=0.12, taylor_C=90.0, usui_A=0.035, usui_B=600.0,
        hardness_factor=2.2, name="Inconel 718"
    ),
    "cast_iron": MaterialParams(
        taylor_n=0.22, taylor_C=220.0, usui_A=0.012, usui_B=850.0,
        hardness_factor=1.15, name="Cast Iron"
    ),
    "brass": MaterialParams(
        taylor_n=0.38, taylor_C=400.0, usui_A=0.003, usui_B=1150.0,
        hardness_factor=0.5, name="Brass"
    ),
    "default": MaterialParams(
        taylor_n=0.25, taylor_C=250.0, usui_A=0.010, usui_B=850.0,
        hardness_factor=1.0, name="Default"
    )
}

TOOL_PARAMS = {
    "carbide": {"wear_factor": 1.0, "max_vb": 0.3},
    "coated_carbide": {"wear_factor": 0.7, "max_vb": 0.35},
    "cermet": {"wear_factor": 0.8, "max_vb": 0.3},
    "ceramic": {"wear_factor": 0.6, "max_vb": 0.35},
    "cbn": {"wear_factor": 0.4, "max_vb": 0.4},
    "pcd": {"wear_factor": 0.3, "max_vb": 0.35},
    "hss": {"wear_factor": 1.5, "max_vb": 0.25},
    "default": {"wear_factor": 1.0, "max_vb": 0.3}
}


class ToolWearPredictor:
    """
    自适应刀具磨损预测系统
    组合修正Taylor模型与Usui磨损率模型
    VB < 0.2mm: Usui模型主导 (加速磨损阶段)
    VB >= 0.2mm: Taylor模型主导 (稳态磨损阶段)
    """

    USUI_TAYLOR_SWITCH_THRESHOLD = 0.2

    def __init__(self):
        self.material_params = MATERIAL_PARAMS
        self.tool_params = TOOL_PARAMS
        self.default_replacement_threshold = 0.3

    def _get_material_params(self, material_type: str) -> MaterialParams:
        mat_key = material_type.lower().replace(" ", "_").replace("-", "_")
        for key in self.material_params:
            if key in mat_key or mat_key in key:
                return self.material_params[key]
        return self.material_params["default"]

    def _get_tool_params(self, tool_type: str) -> dict:
        tool_key = tool_type.lower().replace(" ", "_").replace("-", "_")
        for key in self.tool_params:
            if key in tool_key or tool_key in key:
                return self.tool_params[key]
        return self.tool_params["default"]

    def _get_temperature(self, cutting_speed: float, feed_rate: float,
                         depth_of_cut: float, material: MaterialParams) -> float:
        base_temp = 400.0
        speed_effect = cutting_speed * 2.5
        feed_effect = feed_rate * 150.0
        depth_effect = depth_of_cut * 50.0
        temp = base_temp + speed_effect + feed_effect + depth_effect
        temp *= material.hardness_factor
        return max(300.0, min(1200.0, temp))

    def _usui_wear_rate(self, cutting_speed: float, feed_rate: float,
                        depth_of_cut: float, temperature: float,
                        material: MaterialParams, tool: dict) -> float:
        thermal_energy = material.usui_B / max(temperature, 300.0)
        exponential = math.exp(-thermal_energy)
        contact_pressure = feed_rate * depth_of_cut * material.hardness_factor * 100.0
        sliding_velocity = cutting_speed * 16.667
        rate = material.usui_A * exponential * contact_pressure * sliding_velocity
        rate *= tool["wear_factor"]
        return max(1e-6, min(0.01, rate))

    def _taylor_wear_rate(self, current_vb: float, cutting_speed: float,
                          feed_rate: float, depth_of_cut: float,
                          material: MaterialParams, tool: dict) -> float:
        effective_C = material.taylor_C / (tool["wear_factor"] ** 0.5)
        effective_n = material.taylor_n
        feed_correction = 1.0 + (feed_rate - 0.2) * 0.8
        depth_correction = 1.0 + (depth_of_cut - 1.0) * 0.15
        corrected_speed = cutting_speed * feed_correction * depth_correction
        equivalent_life = (effective_C / max(corrected_speed, 1.0)) ** (1.0 / effective_n)
        wear_progress = current_vb / self.default_replacement_threshold
        acceleration = 1.0 + 2.0 * (wear_progress ** 2)
        effective_vb = max(current_vb, 0.001)
        wear_rate = (effective_vb / max(equivalent_life, 1.0)) * acceleration
        wear_rate *= material.hardness_factor * 0.01
        return max(1e-5, min(0.02, wear_rate))

    def _determine_phase(self, vb: float) -> WearPhase:
        if vb < 0.05:
            return WearPhase.INITIAL
        elif vb < 0.2:
            return WearPhase.STEADY
        else:
            return WearPhase.ACCELERATED

    def _compute_confidence(self, current_wear: float | None,
                            cutting_speed: float,
                            material: MaterialParams) -> float:
        confidence = 0.85
        if cutting_speed > 250:
            confidence -= 0.1
        elif cutting_speed > 150:
            confidence -= 0.05
        if material.hardness_factor > 1.5:
            confidence -= 0.1
        elif material.hardness_factor > 1.2:
            confidence -= 0.05
        if current_wear is not None:
            confidence += 0.05
        return max(0.5, min(0.98, confidence))

    def predict_wear_curve(self, input_parameters: dict) -> WearCurve:
        cutting_speed = input_parameters.get("cutting_speed", 150.0)
        feed_rate = input_parameters.get("feed_rate", 0.2)
        depth_of_cut = input_parameters.get("depth_of_cut", 1.5)
        material_type = input_parameters.get("material_type", "steel_45")
        tool_type = input_parameters.get("tool_type", "carbide")
        current_wear = input_parameters.get("current_wear", 0.0)
        time_step = input_parameters.get("time_step", 1.0)
        max_time = input_parameters.get("max_time", 300.0)

        material = self._get_material_params(material_type)
        tool = self._get_tool_params(tool_type)
        wear_threshold = tool.get("max_vb", self.default_replacement_threshold)

        data_points = []
        current_vb = max(0.0, current_wear)
        time = 0.0
        total_wear = 0.0
        time_to_threshold = None

        while time <= max_time and current_vb < wear_threshold:
            temperature = self._get_temperature(
                cutting_speed, feed_rate, depth_of_cut, material
            )

            if current_vb < self.USUI_TAYLOR_SWITCH_THRESHOLD:
                usui_rate = self._usui_wear_rate(
                    cutting_speed, feed_rate, depth_of_cut,
                    temperature, material, tool
                )
                taylor_rate = self._taylor_wear_rate(
                    current_vb, cutting_speed, feed_rate,
                    depth_of_cut, material, tool
                )
                usui_weight = 1.0 - (current_vb / self.USUI_TAYLOR_SWITCH_THRESHOLD)
                usui_weight = max(0.3, min(0.9, usui_weight))
                wear_rate = usui_weight * usui_rate + (1.0 - usui_weight) * taylor_rate
            else:
                taylor_rate = self._taylor_wear_rate(
                    current_vb, cutting_speed, feed_rate,
                    depth_of_cut, material, tool
                )
                usui_rate = self._usui_wear_rate(
                    cutting_speed, feed_rate, depth_of_cut,
                    temperature, material, tool
                )
                progress = (current_vb - self.USUI_TAYLOR_SWITCH_THRESHOLD) / \
                           (wear_threshold - self.USUI_TAYLOR_SWITCH_THRESHOLD)
                taylor_weight = max(0.6, min(0.95, 0.5 + 0.45 * progress))
                wear_rate = taylor_weight * taylor_rate + (1.0 - taylor_weight) * usui_rate

            phase = self._determine_phase(current_vb)

            point = WearDataPoint(
                time=round(time, 2),
                vb=round(current_vb, 4),
                wear_rate=round(wear_rate, 6),
                phase=phase
            )
            data_points.append(point)

            if current_vb >= wear_threshold and time_to_threshold is None:
                time_to_threshold = round(time, 2)

            current_vb += wear_rate * time_step
            total_wear += wear_rate * time_step
            time += time_step

        if time_to_threshold is None:
            time_to_threshold = round(time, 2)

        total_life = round(time, 2)
        avg_wear_rate = round(total_wear / max(total_life, 0.01), 6)
        confidence = self._compute_confidence(current_wear, cutting_speed, material)

        return WearCurve(
            data_points=data_points,
            total_life=total_life,
            time_to_threshold=time_to_threshold,
            wear_rate_avg=avg_wear_rate,
            confidence=round(confidence, 2)
        )

    def predict_remaining_life(self, current_wear: float,
                               input_parameters: dict) -> float:
        input_parameters.get("cutting_speed", 150.0)
        input_parameters.get("feed_rate", 0.2)
        input_parameters.get("depth_of_cut", 1.5)
        material_type = input_parameters.get("material_type", "steel_45")
        tool_type = input_parameters.get("tool_type", "carbide")

        self._get_material_params(material_type)
        tool = self._get_tool_params(tool_type)
        wear_threshold = tool.get("max_vb", self.default_replacement_threshold)

        remaining_wear = max(0.0, wear_threshold - current_wear)
        if remaining_wear <= 0:
            return 0.0

        temp_params = input_parameters.copy()
        temp_params["current_wear"] = current_wear
        temp_params["time_step"] = 0.5
        temp_params["max_time"] = 500.0

        simulated_curve = self.predict_wear_curve(temp_params)
        elapsed = 0.0
        for point in simulated_curve.data_points:
            if point.vb >= current_wear:
                break
            elapsed = point.time

        return max(0.0, round(simulated_curve.time_to_threshold - elapsed, 2))

    def get_replacement_threshold(self, material_type: str | None = None) -> float:
        if material_type is None:
            return self.default_replacement_threshold

        material = self._get_material_params(material_type)
        if material.hardness_factor > 1.5:
            return 0.25
        elif material.hardness_factor > 1.2:
            return 0.28
        elif material.hardness_factor < 0.7:
            return 0.35
        else:
            return self.default_replacement_threshold

    def suggest_parameter_adjustment(self, current_wear: float,
                                     remaining_life: float,
                                     current_parameters: dict) -> AdjustmentSuggestion:
        cutting_speed = current_parameters.get("cutting_speed", 150.0)
        feed_rate = current_parameters.get("feed_rate", 0.2)
        depth_of_cut = current_parameters.get("depth_of_cut", 1.5)
        coolant_flow = current_parameters.get("coolant_flow", 10.0)
        material_type = current_parameters.get("material_type", "steel_45")
        tool_type = current_parameters.get("tool_type", "carbide")

        material = self._get_material_params(material_type)
        tool = self._get_tool_params(tool_type)
        wear_threshold = tool.get("max_vb", self.default_replacement_threshold)
        wear_ratio = current_wear / wear_threshold

        if wear_ratio > 0.8:
            urgency = UrgencyLevel.CRITICAL
            speed_reduction = 0.30
            feed_reduction = 0.20
            depth_reduction = 0.15
            coolant_increase = 0.50
        elif wear_ratio > 0.5:
            urgency = UrgencyLevel.WARNING
            speed_reduction = 0.15
            feed_reduction = 0.10
            depth_reduction = 0.05
            coolant_increase = 0.25
        else:
            urgency = UrgencyLevel.NORMAL
            speed_reduction = 0.05
            feed_reduction = 0.0
            depth_reduction = 0.0
            coolant_increase = 0.10

        new_speed = round(cutting_speed * (1.0 - speed_reduction), 1)
        new_feed = round(feed_rate * (1.0 - feed_reduction), 3)
        new_depth = round(depth_of_cut * (1.0 - depth_reduction), 2)
        new_coolant = round(coolant_flow * (1.0 + coolant_increase), 1)

        estimated_life_extension = 0.0
        if speed_reduction > 0:
            n = material.taylor_n
            speed_factor = (1.0 - speed_reduction) ** (-1.0 / n)
            estimated_life_extension = (speed_factor - 1.0) * 100.0

        suggestions = []

        if speed_reduction > 0:
            suggestions.append(AdjustmentSuggestionItem(
                param_type="cutting_speed",
                current_value=cutting_speed,
                suggested_value=new_speed,
                adjustment_delta=round(-speed_reduction * 100, 1),
                expected_effect=f"预计延长刀具寿命{round(estimated_life_extension, 1)}%"
            ))

        if feed_reduction > 0:
            feed_effect = round(feed_reduction * 80, 1)
            suggestions.append(AdjustmentSuggestionItem(
                param_type="feed_rate",
                current_value=feed_rate,
                suggested_value=new_feed,
                adjustment_delta=round(-feed_reduction * 100, 1),
                expected_effect=f"减少切削力，降低磨损率约{feed_effect}%"
            ))

        if depth_reduction > 0:
            suggestions.append(AdjustmentSuggestionItem(
                param_type="depth_of_cut",
                current_value=depth_of_cut,
                suggested_value=new_depth,
                adjustment_delta=round(-depth_reduction * 100, 1),
                expected_effect="减少切削负荷，改善散热条件"
            ))

        suggestions.append(AdjustmentSuggestionItem(
            param_type="coolant_flow",
            current_value=coolant_flow,
            suggested_value=new_coolant,
            adjustment_delta=round(coolant_increase * 100, 1),
            expected_effect="增强冷却效果，降低切削温度，减缓月牙洼磨损"
        ))

        if urgency == UrgencyLevel.CRITICAL:
            suggestions.append(AdjustmentSuggestionItem(
                param_type="tool_inspection",
                current_value=0,
                suggested_value=0,
                adjustment_delta=0,
                expected_effect="立即安排刀具检查，准备更换刀具"
            ))

        return AdjustmentSuggestion(
            current_wear=round(current_wear, 4),
            remaining_life=round(remaining_life, 2),
            urgency=urgency,
            suggestions=suggestions
        )

    def calibrate_with_measurement(self, measured_wear: float,
                                   elapsed_time: float,
                                   input_parameters: dict) -> dict[str, Any]:
        input_parameters.get("cutting_speed", 150.0)
        input_parameters.get("feed_rate", 0.2)
        input_parameters.get("depth_of_cut", 1.5)
        material_type = input_parameters.get("material_type", "steel_45")
        tool_type = input_parameters.get("tool_type", "carbide")

        self._get_material_params(material_type)
        self._get_tool_params(tool_type)

        predicted_curve = self.predict_wear_curve(input_parameters)
        predicted_at_time = None
        for point in predicted_curve.data_points:
            if abs(point.time - elapsed_time) < 1.0:
                predicted_at_time = point.vb
                break

        if predicted_at_time is None:
            predicted_at_time = predicted_curve.wear_rate_avg * elapsed_time

        deviation = measured_wear - predicted_at_time
        deviation_percent = (deviation / max(predicted_at_time, 0.001)) * 100.0

        calibrated_params = input_parameters.copy()
        correction_factor = 1.0 + (deviation_percent / 200.0)
        calibrated_params["material_hardness_adjustment"] = round(correction_factor, 3)

        recalibrated_curve = self.predict_wear_curve(calibrated_params)

        return {
            "measured_wear": measured_wear,
            "predicted_wear_at_time": round(predicted_at_time, 4),
            "deviation": round(deviation, 4),
            "deviation_percent": round(deviation_percent, 2),
            "correction_factor": round(correction_factor, 3),
            "calibrated_curve": recalibrated_curve.to_dict()
        }

    def get_supported_models(self) -> list[dict[str, Any]]:
        return [
            {
                "name": "Usui Wear Rate Model",
                "formula": "dW/dt = A * exp(-B/T) * sigma * v",
                "dominant_range": "VB < 0.2mm",
                "description": "基于热激活理论的磨损率模型，适用于初期和稳定磨损阶段"
            },
            {
                "name": "Modified Taylor Tool Life Model",
                "formula": "V * T^n = C",
                "dominant_range": "VB >= 0.2mm",
                "description": "经典的刀具寿命模型，经材料硬度和刀具类型修正，适用于加速磨损阶段"
            },
            {
                "name": "Hybrid Adaptive Model",
                "formula": "w * Usui + (1-w) * Taylor",
                "dominant_range": "Full range",
                "description": "自适应权重混合模型，根据当前磨损量动态调整两模型权重"
            }
        ]
