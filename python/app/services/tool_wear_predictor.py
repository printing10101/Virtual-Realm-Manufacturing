import logging
import math
from typing import Any, Optional

import numpy as np

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
    "stainless_hrc52": MaterialParams(
        taylor_n=0.17, taylor_C=160.0, usui_A=0.020, usui_B=720.0,
        hardness_factor=1.6, name="Stainless Steel HRC52"
    ),
    "titanium_ti64": MaterialParams(
        taylor_n=0.15, taylor_C=120.0, usui_A=0.025, usui_B=650.0,
        hardness_factor=1.8, name="Titanium Ti-6Al-4V"
    ),
    "titanium_tc4": MaterialParams(
        taylor_n=0.14, taylor_C=110.0, usui_A=0.028, usui_B=620.0,
        hardness_factor=1.85, name="Titanium TC4 (Uniwear-NUAA)"
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
        self._bosch_model: Optional[Any] = None
        self._bosch_scaler: Optional[Any] = None
        self._bosch_feature_loader: Optional[Any] = None
        self._uniwear_models: dict[str, Any] = {}
        self._uniwear_scalers: dict[str, Any] = {}
        self._uniwear_loader: Optional[Any] = None
        self._logger = logging.getLogger(self.__class__.__name__)

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

    def _compute_confidence(self, current_wear: Optional[float],
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
            if current_wear > 0.2:
                confidence -= 0.08
            elif current_wear > 0.1:
                confidence -= 0.03
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
        material_type = input_parameters.get("material_type", "steel_45")
        tool_type = input_parameters.get("tool_type", "carbide")

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

    def get_replacement_threshold(self, material_type: Optional[str] = None) -> float:
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
        material_type = input_parameters.get("material_type", "steel_45")

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

    def _get_bosch_loader(self, data_dir: str = "python/data/datasets/bosch_cnc"):
        if self._bosch_feature_loader is not None:
            return self._bosch_feature_loader
        try:
            from app.data.bosch_cnc_loader import BoschCNCDataLoader
            loader = BoschCNCDataLoader(data_dir=data_dir)
            self._bosch_feature_loader = loader
            return loader
        except ImportError:
            self._logger.error(
                "bosch_cnc_loader 模块不存在。Bosch CNC 数据处理功能不可用。"
            )
            return None

    def train_with_bosch_data(
        self,
        data_dir: str = "python/data/datasets/bosch_cnc",
        machines: Optional[list[str]] = None,
        processes: Optional[list[str]] = None,
        test_size: float = 0.2,
        model_type: str = "random_forest",
    ) -> dict:
        try:
            import sklearn
            from packaging import version

            sklearn_version = version.parse(sklearn.__version__)
            min_version = version.parse("1.0.0")
            if sklearn_version < min_version:
                self._logger.error(
                    "scikit-learn 版本过低 (%s < 1.0.0)，不兼容当前训练逻辑",
                    sklearn.__version__
                )
                return {
                    "error": f"scikit-learn 版本过低 ({sklearn.__version__} < 1.0.0)，请升级: pip install 'scikit-learn>=1.0.0'",
                    "accuracy": 0.0,
                    "precision": 0.0,
                    "recall": 0.0,
                    "f1": 0.0,
                    "confusion_matrix": [],
                    "feature_importance": [],
                }

            from sklearn.ensemble import RandomForestClassifier
            from sklearn.metrics import (
                accuracy_score,
                confusion_matrix,
                f1_score,
                precision_score,
                recall_score,
            )
            from sklearn.model_selection import train_test_split
            from sklearn.preprocessing import StandardScaler
            from sklearn.svm import SVC
        except ImportError:
            self._logger.error("机器学习依赖未安装，请安装 scikit-learn 等包")
            return {
                "error": "机器学习依赖未安装，请运行: pip install scikit-learn",
                "accuracy": 0.0,
                "precision": 0.0,
                "recall": 0.0,
                "f1": 0.0,
                "confusion_matrix": [],
                "feature_importance": [],
            }

        loader = self._get_bosch_loader(data_dir=data_dir)
        if loader is None:
            return {
                "error": "bosch_cnc_loader 模块不可用，Bosch CNC 数据处理功能需要此模块支持",
                "accuracy": 0.0,
                "precision": 0.0,
                "recall": 0.0,
                "f1": 0.0,
                "confusion_matrix": [],
                "feature_importance": [],
            }

        X, y, _metadata_list = loader.get_feature_dataset(
            machines=machines, processes=processes
        )

        unique, counts = np.unique(y, return_counts=True)
        self._logger.info(
            "Dataset loaded: %d samples, label distribution: %s",
            len(y), dict(zip(unique.astype(str).tolist(), counts.tolist()))
        )

        if len(unique) < 2:
            return {
                "error": "Dataset must contain both good and bad samples for training",
                "accuracy": 0.0,
                "precision": 0.0,
                "recall": 0.0,
                "f1": 0.0,
                "confusion_matrix": [],
                "feature_importance": [],
            }

        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=test_size, random_state=42, stratify=y
        )

        scaler = StandardScaler()
        X_train_scaled = scaler.fit_transform(X_train)
        X_test_scaled = scaler.transform(X_test)
        self._bosch_scaler = scaler

        if model_type == "random_forest":
            model = RandomForestClassifier(
                n_estimators=100, max_depth=10, random_state=42, n_jobs=-1
            )
        elif model_type == "xgboost":
            try:
                from xgboost import XGBClassifier
                model = XGBClassifier(
                    n_estimators=100, max_depth=6, learning_rate=0.1,
                    random_state=42, n_jobs=-1, eval_metric="logloss"
                )
            except ImportError:
                self._logger.warning("XGBoost not installed, falling back to RandomForest")
                model = RandomForestClassifier(
                    n_estimators=100, max_depth=10, random_state=42, n_jobs=-1
                )
                model_type = "random_forest"
        elif model_type == "svm":
            model = SVC(kernel="rbf", probability=True, random_state=42)
        else:
            raise ValueError(f"刀具磨损预测失败：不支持的模型类型 '{model_type}'。支持的模型类型包括：'LNN'（神经逻辑网络）、'CTC'（连续时间分类）、'CFC'（连续-离散混合模型）。请调用 GET /api/v1/lnn/models 查看支持的模型类型列表，或检查 model_type 参数配置。")

        model.fit(X_train_scaled, y_train)
        self._bosch_model = model

        y_pred = model.predict(X_test_scaled)

        accuracy = round(float(accuracy_score(y_test, y_pred)), 4)
        precision = round(float(precision_score(y_test, y_pred, zero_division=0)), 4)
        recall = round(float(recall_score(y_test, y_pred, zero_division=0)), 4)
        f1 = round(float(f1_score(y_test, y_pred, zero_division=0)), 4)
        cm = confusion_matrix(y_test, y_pred).tolist()

        feature_importance: list[dict] = []
        if model_type in ("random_forest", "xgboost") and hasattr(model, "feature_importances_"):
            feature_keys = sorted(loader.extract_features(np.zeros((100, 3))).keys())
            importances = model.feature_importances_.tolist()
            feature_importance = sorted(
                [
                    {"feature": feature_keys[i] if i < len(feature_keys) else f"f{i}", "importance": round(imp, 6)}
                    for i, imp in enumerate(importances)
                ],
                key=lambda x: x["importance"],
                reverse=True,
            )[:20]

        self._logger.info(
            "Training complete: model=%s, accuracy=%.4f, f1=%.4f",
            model_type, accuracy, f1
        )

        return {
            "accuracy": accuracy,
            "precision": precision,
            "recall": recall,
            "f1": f1,
            "confusion_matrix": cm,
            "feature_importance": feature_importance,
            "model_type": model_type,
            "train_samples": len(X_train),
            "test_samples": len(X_test),
        }

    def predict_vibration_anomaly(
        self,
        vibration_data: np.ndarray,
    ) -> dict:
        if self._bosch_model is None or self._bosch_scaler is None:
            return {
                "prediction": "unknown",
                "confidence": 0.0,
                "features": {},
                "explanation": "Model not trained. Call train_with_bosch_data() first.",
            }

        if self._bosch_feature_loader is None:
            loader = self._get_bosch_loader()
            if loader is None:
                return {
                    "prediction": "unknown",
                    "confidence": 0.0,
                    "features": {},
                    "explanation": "bosch_cnc_loader 模块不可用。",
                }

        features = self._bosch_feature_loader.extract_features(vibration_data)
        feature_keys = sorted(features.keys())
        X = np.array([[features[k] for k in feature_keys]], dtype=np.float64)
        X_scaled = self._bosch_scaler.transform(X)

        proba = self._bosch_model.predict_proba(X_scaled)[0]
        pred_class = int(self._bosch_model.predict(X_scaled)[0])
        label = "bad" if pred_class == 1 else "good"
        confidence = round(float(max(proba)), 4)

        explanation_parts: list[str] = []
        rms_values = {ax: features.get(f"time_{ax}_rms", 0) for ax in ["x", "y", "z"]}
        max_rms_axis = max(rms_values, key=rms_values.get)
        explanation_parts.append(
            f"RMS峰值出现在{max_rms_axis.upper()}轴 ({rms_values[max_rms_axis]:.4f}g)"
        )

        dom_freqs = {ax: features.get(f"freq_{ax}_dominant_freq", 0) for ax in ["x", "y", "z"]}
        max_freq_axis = max(dom_freqs, key=dom_freqs.get)
        explanation_parts.append(
            f"主频{dom_freqs[max_freq_axis]:.1f}Hz ({max_freq_axis.upper()}轴)"
        )

        if label == "bad":
            explanation_parts.append("检测到异常振动模式，建议检查刀具状态")
        else:
            explanation_parts.append("振动模式正常")

        return {
            "prediction": label,
            "confidence": confidence,
            "features": {k: round(v, 6) for k, v in features.items()},
            "explanation": "；".join(explanation_parts),
        }

    def get_process_baseline(self, process: str, machine: str = "M01") -> dict:
        loader = self._get_bosch_loader()
        if loader is None:
            return {
                "process": process,
                "machine": machine,
                "rms_ranges": {},
                "dominant_frequencies": {},
                "energy_distribution": {},
                "sample_count": 0,
                "warning": "bosch_cnc_loader 模块不可用",
            }
        samples = loader.load_dataset(
            machines=[machine], processes=[process], labels=["good"]
        )

        if not samples:
            return {
                "process": process,
                "machine": machine,
                "rms_ranges": {},
                "dominant_frequencies": {},
                "energy_distribution": {},
                "sample_count": 0,
                "warning": f"No good samples found for {machine}/{process}",
            }

        axis_data: dict[str, list[float]] = {"x_rms": [], "y_rms": [], "z_rms": []}
        axis_dom_freqs: dict[str, list[float]] = {
            "x_dom_freq": [], "y_dom_freq": [], "z_dom_freq": []
        }
        axis_energies: dict[str, list[float]] = {
            "x_energy_ratio": [], "y_energy_ratio": [], "z_energy_ratio": []
        }

        for sample in samples:
            feats = loader.extract_features(sample["data"])
            for ax in ["x", "y", "z"]:
                axis_data[f"{ax}_rms"].append(feats.get(f"time_{ax}_rms", 0))
                axis_dom_freqs[f"{ax}_dom_freq"].append(feats.get(f"freq_{ax}_dominant_freq", 0))
                axis_energies[f"{ax}_energy_ratio"].append(feats.get(f"cross_{ax}_energy_ratio", 0))

        rms_ranges = {}
        for key, values in axis_data.items():
            if values:
                rms_ranges[key] = {
                    "min": round(float(np.min(values)), 6),
                    "max": round(float(np.max(values)), 6),
                    "mean": round(float(np.mean(values)), 6),
                    "std": round(float(np.std(values)), 6),
                }

        dominant_frequencies = {}
        for key, values in axis_dom_freqs.items():
            if values:
                dominant_frequencies[key] = {
                    "min": round(float(np.min(values)), 2),
                    "max": round(float(np.max(values)), 2),
                    "mean": round(float(np.mean(values)), 2),
                }

        energy_distribution = {}
        for key, values in axis_energies.items():
            if values:
                energy_distribution[key] = {
                    "min": round(float(np.min(values)), 6),
                    "max": round(float(np.max(values)), 6),
                    "mean": round(float(np.mean(values)), 6),
                }

        return {
            "process": process,
            "machine": machine,
            "rms_ranges": rms_ranges,
            "dominant_frequencies": dominant_frequencies,
            "energy_distribution": energy_distribution,
            "sample_count": len(samples),
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

    def get_uniwear_material_params(self) -> dict:
        return {
            "tc4": {
                "taylor_n": 0.14, "taylor_C": 110.0,
                "usui_A": 0.028, "usui_B": 620.0,
                "hardness_factor": 1.85,
                "name": "Titanium TC4 (Uniwear-NUAA)",
                "dataset": "nuaa",
                "experiments": ["W1", "W2", "W3", "W4", "W5", "W6", "W7", "W8", "W9"],
            },
            "hrc52": {
                "taylor_n": 0.17, "taylor_C": 160.0,
                "usui_A": 0.020, "usui_B": 720.0,
                "hardness_factor": 1.6,
                "name": "Stainless Steel HRC52 (Uniwear-PHM2010)",
                "dataset": "phm2010",
                "experiments": ["c1", "c4", "c6"],
            },
        }

    def train_with_uniwear_data(
        self,
        data_dir: str = "python/data/uniwear",
        model_type: str = "random_forest",
        test_size: float = 0.2,
    ) -> dict:
        try:
            from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
            from sklearn.linear_model import LinearRegression
            from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
            from sklearn.model_selection import train_test_split
            from sklearn.preprocessing import StandardScaler
        except ImportError:
            self._logger.error("机器学习依赖未安装，请安装 scikit-learn")
            return {"error": "scikit-learn not installed"}

        from app.data.uniwear_loader import UniwearDataLoader, UniwearDataset, NUAA_SIGNAL_COLUMNS, PHM2010_SIGNAL_COLUMNS

        loader = UniwearDataLoader(data_dir=data_dir)
        self._uniwear_loader = loader

        results: dict = {"datasets": {}}

        ds_configs = [
            (UniwearDataset.NUAA, NUAA_SIGNAL_COLUMNS, "tc4"),
            (UniwearDataset.PHM2010, PHM2010_SIGNAL_COLUMNS, "hrc52"),
        ]

        for ds, signal_cols, material_key in ds_configs:
            try:
                df = loader.load_dataset(ds)

                if "tool_wear" not in df.columns:
                    results["datasets"][ds.value] = {"error": "No tool_wear column"}
                    continue

                feature_cols = [c for c in signal_cols if c in df.columns and c != "timestamp"]
                if not feature_cols:
                    results["datasets"][ds.value] = {"error": "No valid feature columns"}
                    continue

                df_clean = df.dropna(subset=feature_cols + ["tool_wear"])
                X = df_clean[feature_cols].values.astype(np.float64)
                y = df_clean["tool_wear"].values.astype(np.float64)

                if len(X) < 10:
                    results["datasets"][ds.value] = {
                        "error": f"Insufficient samples: {len(X)}"
                    }
                    continue

                X_train, X_test, y_train, y_test = train_test_split(
                    X, y, test_size=test_size, random_state=42
                )

                scaler = StandardScaler()
                X_train_scaled = scaler.fit_transform(X_train)
                X_test_scaled = scaler.transform(X_test)

                if model_type == "random_forest":
                    model = RandomForestRegressor(
                        n_estimators=100, max_depth=10, random_state=42, n_jobs=-1
                    )
                elif model_type == "gradient_boosting":
                    model = GradientBoostingRegressor(
                        n_estimators=100, max_depth=5, learning_rate=0.1, random_state=42
                    )
                elif model_type == "linear":
                    model = LinearRegression()
                else:
                    raise ValueError(f"刀具磨损预测失败：不支持的模型类型 '{model_type}'。支持的模型类型包括：'LNN'（神经逻辑网络）、'CTC'（连续时间分类）、'CFC'（连续-离散混合模型）。请调用 GET /api/v1/lnn/models 查看支持的模型类型列表，或检查 model_type 参数配置。")

                model.fit(X_train_scaled, y_train)
                y_pred = model.predict(X_test_scaled)

                mae = round(float(mean_absolute_error(y_test, y_pred)), 6)
                rmse = round(float(np.sqrt(mean_squared_error(y_test, y_pred))), 6)
                r2 = round(float(r2_score(y_test, y_pred)), 4)

                self._uniwear_models[material_key] = model
                self._uniwear_scalers[material_key] = scaler

                feature_importance = []
                if hasattr(model, "feature_importances_"):
                    importances = model.feature_importances_.tolist()
                    feature_importance = sorted(
                        [
                            {"feature": feature_cols[i] if i < len(feature_cols) else f"f{i}",
                             "importance": round(imp, 6)}
                            for i, imp in enumerate(importances)
                        ],
                        key=lambda x: x["importance"],
                        reverse=True,
                    )[:15]

                results["datasets"][ds.value] = {
                    "material": material_key,
                    "model_type": model_type,
                    "train_samples": len(X_train),
                    "test_samples": len(X_test),
                    "features": len(feature_cols),
                    "mae": mae,
                    "rmse": rmse,
                    "r2": r2,
                    "feature_importance": feature_importance,
                }

                self._logger.info(
                    "Uniwear %s training: MAE=%.6f, RMSE=%.6f, R²=%.4f",
                    ds.value, mae, rmse, r2,
                )
            except Exception as e:
                self._logger.error("Uniwear training failed for %s: %s", ds.value, e)
                results["datasets"][ds.value] = {"error": str(e)}

        return results

    def predict_wear_from_signals(
        self,
        signal_features: dict[str, float],
        material: str = "tc4",
    ) -> dict:
        model = self._uniwear_models.get(material)
        scaler = self._uniwear_scalers.get(material)

        if model is None or scaler is None:
            return {
                "error": f"Model not trained for {material}. Call train_with_uniwear_data() first.",
                "predicted_wear": None,
                "confidence": 0.0,
            }

        feature_order = list(signal_features.keys())
        X = np.array([[signal_features[k] for k in feature_order]], dtype=np.float64)
        X_scaled = scaler.transform(X)

        predicted = float(model.predict(X_scaled)[0])

        if hasattr(model, "predict_proba"):
            confidence = float(np.max(model.predict_proba(X_scaled)))
        else:
            confidence = max(0.6, min(0.95, 1.0 - abs(predicted) * 0.1))

        return {
            "predicted_wear": round(predicted, 6),
            "confidence": round(confidence, 4),
            "material": material,
            "features_used": feature_order,
        }

    def cross_dataset_analysis(self) -> dict:
        if not self._bosch_model:
            bosch_status = "not_trained"
        else:
            bosch_status = "trained"

        uniwear_status = {
            k: "trained" for k in self._uniwear_models
        } if self._uniwear_models else {"tc4": "not_trained", "hrc52": "not_trained"}

        analysis = {
            "bosch_cnc": {"status": bosch_status, "data_type": "vibration_classification"},
            "uniwear": {
                "status": uniwear_status,
                "data_type": "wear_regression",
                "materials": {
                    "tc4": {
                        "source": "NUAA",
                        "experiment_count": 9,
                        "signal_types": "force/vibration/power",
                    },
                    "hrc52": {
                        "source": "PHM2010",
                        "experiment_count": 3,
                        "signal_types": "force/vibration/acoustic_emission",
                    },
                },
            },
            "cross_validation_strategy": [
                "Use Bosch vibration features with Uniwear wear regression to estimate wear",
                "Cross-validate Bosch good/bad labels against Uniwear predicted wear thresholds",
                "Use Uniwear TC4/HRC52 models for material-specific wear predictions in Bosch data",
            ],
            "material_specific_thresholds": {
                "tc4": self.get_replacement_threshold("titanium_tc4"),
                "hrc52": self.get_replacement_threshold("stainless_hrc52"),
                "default": self.default_replacement_threshold,
            },
        }

        return analysis
