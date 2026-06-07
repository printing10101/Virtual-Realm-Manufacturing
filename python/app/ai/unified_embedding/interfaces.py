"""Three-layer interface definitions for LLM+LNN+JEPA hybrid architecture.

Cognitive Layer (LLM-powered): process knowledge understanding, natural language interaction
Perception Layer (JEPA-powered): visual understanding, world model, sensor fusion
Execution Layer (LNN-powered): time-series prediction, real-time control

Interface protocols:
    Cognitive → Perception: RESTful API, HTTPS, <100ms
    Perception → Execution:   gRPC, binary stream, <50ms
    Execution → Cognitive:    WebSocket, continuous stream, >=10Hz
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

import numpy as np


class LayerType(str, Enum):
    COGNITIVE = "cognitive"
    PERCEPTION = "perception"
    EXECUTION = "execution"


class ProcessCategory(str, Enum):
    TURNING = "turning"
    MILLING = "milling"
    DRILLING = "drilling"
    GRINDING = "grinding"
    BORING = "boring"
    EDM = "edm"
    ADDITIVE = "additive"
    HYBRID = "hybrid"


class QualityLevel(str, Enum):
    IT5 = "IT5"
    IT6 = "IT6"
    IT7 = "IT7"
    IT8 = "IT8"
    IT9 = "IT9"
    IT10 = "IT10"
    IT11 = "IT11"
    IT12 = "IT12"


class SurfaceFinishGrade(str, Enum):
    N1 = "N1"
    N2 = "N2"
    N3 = "N3"
    N4 = "N4"
    N5 = "N5"
    N6 = "N6"
    N7 = "N7"
    N8 = "N8"
    N9 = "N9"
    N10 = "N10"
    N11 = "N11"
    N12 = "N12"


class SensorType(str, Enum):
    ACCELEROMETER = "accelerometer"
    THERMOCOUPLE = "thermocouple"
    DYNAMOMETER = "dynamometer"
    ACOUSTIC_EMISSION = "acoustic_emission"
    LASER_DISPLACEMENT = "laser_displacement"
    VISION_CAMERA = "vision_camera"
    CURRENT_PROBE = "current_probe"
    PRESSURE_SENSOR = "pressure_sensor"


class FeatureExtractionAlgorithm(str, Enum):
    VGG16 = "vgg16"
    RESNET50 = "resnet50"
    EFFICIENTNET = "efficientnet"
    VIT = "vit"
    POINTNET = "pointnet"
    DGCNN = "dgcnn"
    FPN = "fpn"
    CUSTOM_CNN = "custom_cnn"


class EventSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
    EMERGENCY = "emergency"


class EventType(str, Enum):
    TOOL_WEAR_THRESHOLD = "tool_wear_threshold"
    VIBRATION_ANOMALY = "vibration_anomaly"
    TEMPERATURE_ANOMALY = "temperature_anomaly"
    COLLISION_DETECTED = "collision_detected"
    SURFACE_QUALITY_DEGRADATION = "surface_quality_degradation"
    SPINDLE_OVERLOAD = "spindle_overload"
    COOLANT_FAILURE = "coolant_failure"
    DIMENSIONAL_DEVIATION = "dimensional_deviation"


class AdjustmentPriority(str, Enum):
    IMMEDIATE = "immediate"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass
class DimensionalTolerance:
    nominal_mm: float
    upper_deviation_mm: float
    lower_deviation_mm: float
    it_grade: QualityLevel = QualityLevel.IT8

    def validate(self) -> List[str]:
        errors = []
        if self.nominal_mm <= 0:
            errors.append(f"nominal_mm must be positive, got {self.nominal_mm}")
        if self.upper_deviation_mm < self.lower_deviation_mm:
            errors.append(
                f"upper_deviation ({self.upper_deviation_mm}) must be >= lower_deviation ({self.lower_deviation_mm})"
            )
        return errors


@dataclass
class SurfaceRoughnessSpec:
    ra_um: float
    rz_um: Optional[float] = None
    rmax_um: Optional[float] = None
    grade: SurfaceFinishGrade = SurfaceFinishGrade.N6

    def validate(self) -> List[str]:
        errors = []
        if self.ra_um < 0.01 or self.ra_um > 50.0:
            errors.append(f"ra_um must be in [0.01, 50.0], got {self.ra_um}")
        if self.rz_um is not None and (self.rz_um < 0.04 or self.rz_um > 200.0):
            errors.append(f"rz_um must be in [0.04, 200.0], got {self.rz_um}")
        return errors


@dataclass
class QualityRequirements:
    dimensional_tolerances: List[DimensionalTolerance] = field(default_factory=list)
    surface_roughness: Optional[SurfaceRoughnessSpec] = None
    geometric_tolerances_mm: Dict[str, float] = field(default_factory=dict)
    max_burr_height_mm: float = 0.1
    target_quality_level: QualityLevel = QualityLevel.IT8

    def validate(self) -> List[str]:
        errors = []
        for i, tol in enumerate(self.dimensional_tolerances):
            for e in tol.validate():
                errors.append(f"dimensional_tolerances[{i}]: {e}")
        if self.surface_roughness:
            errors.extend(self.surface_roughness.validate())
        for key, val in self.geometric_tolerances_mm.items():
            if val <= 0:
                errors.append(f"geometric_tolerance '{key}' must be positive, got {val}")
        if not (0.0 <= self.max_burr_height_mm <= 5.0):
            errors.append(f"max_burr_height_mm must be in [0, 5.0], got {self.max_burr_height_mm}")
        return errors


@dataclass
class SensorConfig:
    sensor_type: SensorType
    installation_position: str
    sampling_frequency_hz: float
    measurement_range: Tuple[float, float]
    resolution: float
    axis: str = "Z"

    def validate(self) -> List[str]:
        errors = []
        valid_positions = {"spindle", "tool_holder", "worktable", "bed", "column", "coolant_line", "enclosure"}
        if self.installation_position not in valid_positions:
            errors.append(
                f"installation_position must be one of {valid_positions}, got '{self.installation_position}'"
            )
        if self.sampling_frequency_hz <= 0 or self.sampling_frequency_hz > 100000:
            errors.append(f"sampling_frequency_hz must be in (0, 100000], got {self.sampling_frequency_hz}")
        if self.measurement_range[0] >= self.measurement_range[1]:
            errors.append(f"measurement_range must have min < max, got {self.measurement_range}")
        return errors


@dataclass
class CuttingParameters:
    feed_rate_mm_min: float
    depth_of_cut_mm: float
    spindle_speed_rpm: float
    step_over_mm: float = 0.0
    cutting_speed_m_min: float = 0.0
    coolant_on: bool = True
    approach_distance_mm: float = 5.0
    retract_distance_mm: float = 5.0

    def validate(self) -> List[str]:
        errors = []
        if not (0.1 <= self.feed_rate_mm_min <= 10000.0):
            errors.append(f"feed_rate_mm_min must be in [0.1, 10000.0], got {self.feed_rate_mm_min}")
        if not (0.01 <= self.depth_of_cut_mm <= 100.0):
            errors.append(f"depth_of_cut_mm must be in [0.01, 100.0], got {self.depth_of_cut_mm}")
        if not (100 <= self.spindle_speed_rpm <= 100000):
            errors.append(f"spindle_speed_rpm must be in [100, 100000], got {self.spindle_speed_rpm}")
        if not (0.0 <= self.step_over_mm <= 100.0):
            errors.append(f"step_over_mm must be in [0.0, 100.0], got {self.step_over_mm}")
        return errors


@dataclass
class PointCloudData:
    points: np.ndarray
    normals: Optional[np.ndarray] = None
    colors: Optional[np.ndarray] = None
    point_count: int = 0
    bounding_box: Optional[Dict[str, float]] = None
    source_format: str = "numpy"

    def __post_init__(self):
        if isinstance(self.points, list):
            self.points = np.array(self.points, dtype=np.float32)
        self.point_count = len(self.points)

    def serialize(self) -> bytes:
        return self.points.astype(np.float32).tobytes()

    @classmethod
    def deserialize(cls, data: bytes, point_count: int) -> "PointCloudData":
        points = np.frombuffer(data, dtype=np.float32).reshape(point_count, 3)
        return cls(points=points, point_count=point_count)


@dataclass
class GeometryInput:
    point_cloud: Optional[PointCloudData] = None
    stl_path: Optional[str] = None
    step_path: Optional[str] = None
    parametric_model: Optional[Dict[str, Any]] = None
    stock_dimensions_mm: Optional[Tuple[float, float, float]] = None
    material: str = "steel"

    def validate(self) -> List[str]:
        errors = []
        if (
            self.point_cloud is None
            and self.stl_path is None
            and self.step_path is None
            and self.parametric_model is None
        ):
            errors.append("At least one of point_cloud, stl_path, step_path, or parametric_model must be provided")
        if self.stl_path is not None and not self.stl_path.endswith(".stl"):
            errors.append(f"stl_path must end with .stl, got '{self.stl_path}'")
        if self.step_path is not None and not self.step_path.endswith((".step", ".stp")):
            errors.append(f"step_path must end with .step/.stp, got '{self.step_path}'")
        return errors


@dataclass
class RealTimeState:
    timestamp: float = field(default_factory=time.time)
    spindle_speed_rpm: float = 0.0
    spindle_load_pct: float = 0.0
    feed_rate_mm_min: float = 0.0
    vibration_x: float = 0.0
    vibration_y: float = 0.0
    vibration_z: float = 0.0
    spindle_temp_c: float = 25.0
    tool_temp_c: float = 25.0
    coolant_temp_c: float = 20.0
    cutting_force_x_n: float = 0.0
    cutting_force_y_n: float = 0.0
    cutting_force_z_n: float = 0.0
    tool_wear_mm: float = 0.0
    acoustic_emission_rms: float = 0.0
    position_x_mm: float = 0.0
    position_y_mm: float = 0.0
    position_z_mm: float = 0.0
    duty_cycle_pct: float = 0.0

    def validate(self) -> List[str]:
        errors = []
        if self.spindle_speed_rpm < 0:
            errors.append(f"spindle_speed_rpm must be >= 0, got {self.spindle_speed_rpm}")
        if not (0 <= self.spindle_load_pct <= 150):
            errors.append(f"spindle_load_pct must be in [0, 150], got {self.spindle_load_pct}")
        if not (0 <= self.tool_wear_mm <= 5.0):
            errors.append(f"tool_wear_mm must be in [0, 5.0], got {self.tool_wear_mm}")
        return errors

    def to_dict(self) -> Dict[str, float]:
        return asdict(self)

    def to_numpy(self) -> np.ndarray:
        return np.array([
            self.spindle_speed_rpm, self.spindle_load_pct, self.feed_rate_mm_min,
            self.vibration_x, self.vibration_y, self.vibration_z,
            self.spindle_temp_c, self.tool_temp_c, self.coolant_temp_c,
            self.cutting_force_x_n, self.cutting_force_y_n, self.cutting_force_z_n,
            self.tool_wear_mm, self.acoustic_emission_rms,
            self.position_x_mm, self.position_y_mm, self.position_z_mm,
            self.duty_cycle_pct,
        ], dtype=np.float32)


@dataclass
class AnomalyEvent:
    event_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    event_type: EventType = EventType.VIBRATION_ANOMALY
    severity: EventSeverity = EventSeverity.WARNING
    timestamp: float = field(default_factory=time.time)
    description: str = ""
    source_sensor: Optional[SensorType] = None
    measured_value: float = 0.0
    threshold_value: float = 0.0
    duration_ms: float = 0.0
    related_positions: Optional[List[Tuple[float, float, float]]] = None

    def validate(self) -> List[str]:
        errors = []
        if self.duration_ms < 0:
            errors.append(f"duration_ms must be >= 0, got {self.duration_ms}")
        return errors


@dataclass
class AdjustmentSuggestion:
    suggestion_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    timestamp: float = field(default_factory=time.time)
    description: str = ""
    suggested_parameters: Dict[str, float] = field(default_factory=dict)
    confidence: float = 0.0
    priority: AdjustmentPriority = AdjustmentPriority.MEDIUM
    reasoning: str = ""
    expected_improvement: Dict[str, float] = field(default_factory=dict)
    alternatives: List[Dict[str, Any]] = field(default_factory=list)

    def validate(self) -> List[str]:
        errors = []
        if not (0.0 <= self.confidence <= 1.0):
            errors.append(f"confidence must be in [0.0, 1.0], got {self.confidence}")
        return errors


@dataclass
class FeedbackSignal:
    suggestions: List[AdjustmentSuggestion] = field(default_factory=list)
    overall_confidence: float = 0.0
    execution_priority: AdjustmentPriority = AdjustmentPriority.MEDIUM
    estimated_impact: str = ""
    requires_halt: bool = False

    def validate(self) -> List[str]:
        errors = []
        for i, s in enumerate(self.suggestions):
            for e in s.validate():
                errors.append(f"suggestions[{i}]: {e}")
        if not (0.0 <= self.overall_confidence <= 1.0):
            errors.append(f"overall_confidence must be in [0.0, 1.0], got {self.overall_confidence}")
        return errors


class CognitiveToPerceptionRequest:
    """Cognitive layer → Perception layer interface.

    Protocol: RESTful API over HTTPS
    Response time: <100ms
    """

    def __init__(
        self,
        process_intent: str,
        quality_requirements: QualityRequirements,
        material_spec: Optional[Dict[str, Any]] = None,
        request_id: Optional[str] = None,
        max_tokens: int = 512,
    ):
        self.request_id = request_id or uuid.uuid4().hex[:16]
        self.process_intent = process_intent
        self.quality_requirements = quality_requirements
        self.material_spec = material_spec or {}
        self.max_tokens = max_tokens
        self.timestamp = time.time()

    def validate(self) -> List[str]:
        errors = []
        if not self.process_intent or len(self.process_intent) > 512:
            errors.append(
                f"process_intent must be 1-512 characters, got {len(self.process_intent) if self.process_intent else 0}"
            )
        errors.extend(self.quality_requirements.validate())
        return errors

    def to_json(self) -> str:
        return json.dumps({
            "request_id": self.request_id,
            "process_intent": self.process_intent,
            "quality_requirements": {
                "dimensional_tolerances": [
                    asdict(t) for t in self.quality_requirements.dimensional_tolerances
                ],
                "surface_roughness": asdict(self.quality_requirements.surface_roughness)
                if self.quality_requirements.surface_roughness else None,
                "geometric_tolerances_mm": self.quality_requirements.geometric_tolerances_mm,
                "max_burr_height_mm": self.quality_requirements.max_burr_height_mm,
                "target_quality_level": self.quality_requirements.target_quality_level.value,
            },
            "material_spec": self.material_spec,
            "max_tokens": self.max_tokens,
            "timestamp": self.timestamp,
        }, ensure_ascii=False)

    @classmethod
    def from_json(cls, data: str) -> "CognitiveToPerceptionRequest":
        d = json.loads(data)
        qr_data = d["quality_requirements"]
        tols = [DimensionalTolerance(**t) for t in qr_data.get("dimensional_tolerances", [])]
        sr = None
        if qr_data.get("surface_roughness"):
            sr = SurfaceRoughnessSpec(**qr_data["surface_roughness"])
        qr = QualityRequirements(
            dimensional_tolerances=tols,
            surface_roughness=sr,
            geometric_tolerances_mm=qr_data.get("geometric_tolerances_mm", {}),
            max_burr_height_mm=qr_data.get("max_burr_height_mm", 0.1),
            target_quality_level=QualityLevel(qr_data.get("target_quality_level", "IT8")),
        )
        return cls(
            process_intent=d["process_intent"],
            quality_requirements=qr,
            material_spec=d.get("material_spec", {}),
            request_id=d.get("request_id"),
        )


@dataclass
class CognitiveToPerceptionResponse:
    """Perception layer → Cognitive layer (response to perception task config)."""

    request_id: str
    sensor_configs: List[SensorConfig] = field(default_factory=list)
    feature_algorithm: FeatureExtractionAlgorithm = FeatureExtractionAlgorithm.RESNET50
    sampling_frequency_hz: float = 100.0
    region_of_interest: Optional[Dict[str, Any]] = None
    preprocessing_pipeline: List[str] = field(default_factory=list)
    estimated_processing_time_ms: float = 0.0
    embedding_projection: Optional[List[float]] = None

    def validate(self) -> List[str]:
        errors = []
        for i, sc in enumerate(self.sensor_configs):
            for e in sc.validate():
                errors.append(f"sensor_configs[{i}]: {e}")
        if self.sampling_frequency_hz <= 0 or self.sampling_frequency_hz > 100000:
            errors.append(f"sampling_frequency_hz must be in (0, 100000], got {self.sampling_frequency_hz}")
        return errors

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False, default=str)

    @classmethod
    def from_json(cls, data: str) -> "CognitiveToPerceptionResponse":
        d = json.loads(data)
        d["sensor_configs"] = [SensorConfig(**s) for s in d.get("sensor_configs", [])]
        d["feature_algorithm"] = FeatureExtractionAlgorithm(
            d.get("feature_algorithm", "resnet50")
        )
        return cls(**d)


@dataclass
class PerceptionToExecutionRequest:
    """Perception layer → Execution layer interface.

    Protocol: gRPC with binary stream
    Response time: <50ms
    """

    request_id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])
    geometry: GeometryInput = field(default_factory=GeometryInput)
    cutting_parameters: CuttingParameters = field(default_factory=lambda: CuttingParameters(
        feed_rate_mm_min=500.0, depth_of_cut_mm=2.0, spindle_speed_rpm=8000.0
    ))
    material_spec: Dict[str, Any] = field(default_factory=dict)
    tool_spec: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)

    def validate(self) -> List[str]:
        errors = []
        errors.extend(self.geometry.validate())
        errors.extend(self.cutting_parameters.validate())
        return errors

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        if self.geometry.point_cloud is not None:
            d["geometry"]["point_cloud"]["points"] = (
                self.geometry.point_cloud.points.tolist()
            )
        return d


@dataclass
class MonitoringPointConfig:
    sensor_type: SensorType
    installation_position: str
    sampling_frequency_hz: float
    data_format: str = "float32"
    channel_count: int = 1

    def validate(self) -> List[str]:
        errors = []
        if self.installation_position not in {"spindle", "tool_holder", "worktable", "bed", "column", "coolant_line"}:
            errors.append(f"Invalid installation_position: {self.installation_position}")
        if self.sampling_frequency_hz <= 0 or self.sampling_frequency_hz > 100000:
            errors.append(f"sampling_frequency_hz must be in (0, 100000], got {self.sampling_frequency_hz}")
        return errors


@dataclass
class PredictionBaseline:
    expected_surface_roughness_ra: float
    expected_tool_wear_rate_um_per_min: float
    expected_cutting_force_n: float
    expected_power_consumption_kw: float
    tolerance_range: Dict[str, Tuple[float, float]] = field(default_factory=dict)
    control_thresholds: Dict[str, float] = field(default_factory=dict)
    confidence: float = 0.0

    def validate(self) -> List[str]:
        errors = []
        if self.expected_surface_roughness_ra < 0:
            errors.append(f"expected_surface_roughness_ra must be >= 0, got {self.expected_surface_roughness_ra}")
        if not (0.0 <= self.confidence <= 1.0):
            errors.append(f"confidence must be in [0.0, 1.0], got {self.confidence}")
        return errors


@dataclass
class PerceptionToExecutionResponse:
    """Execution layer → Perception layer (monitoring config + prediction baseline)."""

    request_id: str
    monitoring_points: List[MonitoringPointConfig] = field(default_factory=list)
    prediction_baseline: Optional[PredictionBaseline] = None
    toolpath_segments: int = 0
    estimated_cycle_time_s: float = 0.0
    embedding_projection: Optional[List[float]] = None

    def validate(self) -> List[str]:
        errors = []
        for i, mp in enumerate(self.monitoring_points):
            for e in mp.validate():
                errors.append(f"monitoring_points[{i}]: {e}")
        if self.prediction_baseline:
            errors.extend(self.prediction_baseline.validate())
        return errors


@dataclass
class ExecutionToCognitiveRequest:
    """Execution layer → Cognitive layer interface.

    Protocol: WebSocket, continuous data stream
    Update frequency: >=10Hz
    """

    stream_id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])
    real_time_state: RealTimeState = field(default_factory=RealTimeState)
    anomaly_events: List[AnomalyEvent] = field(default_factory=list)
    session_id: Optional[str] = None
    batch_sequence: int = 0
    timestamp: float = field(default_factory=time.time)

    def validate(self) -> List[str]:
        errors = []
        errors.extend(self.real_time_state.validate())
        for i, evt in enumerate(self.anomaly_events):
            for e in evt.validate():
                errors.append(f"anomaly_events[{i}]: {e}")
        return errors


@dataclass
class ExecutionToCognitiveResponse:
    """Cognitive layer → Execution layer (feedback for plan adjustment)."""

    stream_id: str
    feedback: FeedbackSignal = field(default_factory=FeedbackSignal)
    timestamp: float = field(default_factory=time.time)

    def validate(self) -> List[str]:
        return self.feedback.validate()


class MachiningProcessFlow:
    """Orchestrates the three-layer machining process flow with validation at each step."""

    def __init__(self):
        self.flow_id = uuid.uuid4().hex[:16]
        self.steps: List[Dict[str, Any]] = []
        self.errors: List[str] = []

    def step_cognitive_to_perception(
        self,
        process_intent: str,
        quality_requirements: QualityRequirements,
        material_spec: Optional[Dict[str, Any]] = None,
    ) -> Tuple[CognitiveToPerceptionRequest, List[str]]:
        req = CognitiveToPerceptionRequest(
            process_intent=process_intent,
            quality_requirements=quality_requirements,
            material_spec=material_spec,
        )
        errors = req.validate()
        self.steps.append({
            "step": "cognitive_to_perception",
            "request_id": req.request_id,
            "timestamp": req.timestamp,
            "valid": len(errors) == 0,
        })
        if errors:
            self.errors.extend(errors)
        return req, errors

    def step_perception_to_execution(
        self,
        geometry: GeometryInput,
        cutting_parameters: CuttingParameters,
        material_spec: Optional[Dict[str, Any]] = None,
        tool_spec: Optional[Dict[str, Any]] = None,
    ) -> Tuple[PerceptionToExecutionRequest, List[str]]:
        req = PerceptionToExecutionRequest(
            geometry=geometry,
            cutting_parameters=cutting_parameters,
            material_spec=material_spec or {},
            tool_spec=tool_spec or {},
        )
        errors = req.validate()
        self.steps.append({
            "step": "perception_to_execution",
            "request_id": req.request_id,
            "timestamp": req.timestamp,
            "valid": len(errors) == 0,
        })
        if errors:
            self.errors.extend(errors)
        return req, errors

    def step_execution_to_cognitive(
        self,
        real_time_state: RealTimeState,
        anomaly_events: Optional[List[AnomalyEvent]] = None,
    ) -> Tuple[ExecutionToCognitiveRequest, List[str]]:
        req = ExecutionToCognitiveRequest(
            real_time_state=real_time_state,
            anomaly_events=anomaly_events or [],
        )
        errors = req.validate()
        self.steps.append({
            "step": "execution_to_cognitive",
            "stream_id": req.stream_id,
            "timestamp": req.timestamp,
            "valid": len(errors) == 0,
        })
        if errors:
            self.errors.extend(errors)
        return req, errors

    def get_flow_report(self) -> Dict[str, Any]:
        return {
            "flow_id": self.flow_id,
            "total_steps": len(self.steps),
            "valid_steps": sum(1 for s in self.steps if s["valid"]),
            "invalid_steps": sum(1 for s in self.steps if not s["valid"]),
            "error_count": len(self.errors),
            "errors": self.errors,
            "steps": self.steps,
        }
