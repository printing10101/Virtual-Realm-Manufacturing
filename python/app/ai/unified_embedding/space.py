"""512-Dimensional Unified Manufacturing Semantic Embedding Space.

Space structure:
  [0:64)    Material    - material properties (hardness, conductivity, ductility)
  [64:192)  Process     - machining methods (turning, milling, drilling, grinding)
  [192:224) Precision   - dimensional tolerance grades (IT5-IT12)
  [224:352) State       - equipment/tool real-time status (vibration, temp, wear)
  [352:384) Risk        - safety risk levels (probability and severity)
  [384:512) Reserved    - future extensions and system optimization
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Optional, Sequence, Tuple

import numpy as np

TOTAL_DIMS: int = 512

MATERIAL_OFFSET: int = 0
MATERIAL_DIMS: int = 64

PROCESS_OFFSET: int = 64
PROCESS_DIMS: int = 128

PRECISION_OFFSET: int = 192
PRECISION_DIMS: int = 32

STATE_OFFSET: int = 224
STATE_DIMS: int = 128

RISK_OFFSET: int = 352
RISK_DIMS: int = 32

RESERVED_OFFSET: int = 384
RESERVED_DIMS: int = 128


class SemanticAxis:
    """Base class for a semantic axis in the embedding space."""

    def __init__(self, name: str, offset: int, dims: int, description: str):
        self.name = name
        self.offset = offset
        self.dims = dims
        self.description = description
        self._sub_axes: Dict[str, Tuple[int, int]] = {}

    def register_sub_axis(self, name: str, offset: int, length: int):
        self._sub_axes[name] = (self.offset + offset, length)

    def get_sub_axis(self, name: str) -> Tuple[int, int]:
        return self._sub_axes[name]

    @property
    def slice(self) -> slice:
        return slice(self.offset, self.offset + self.dims)

    def extract(self, embedding: np.ndarray) -> np.ndarray:
        if embedding.ndim == 1:
            return embedding[self.slice]
        return embedding[:, self.slice]

    def encode(self, values: np.ndarray) -> np.ndarray:
        clamped = np.clip(values, -1.0, 1.0)
        return clamped.astype(np.float32)

    def validate(self, embedding: np.ndarray) -> Dict[str, float]:
        segment = self.extract(embedding)
        return {
            f"{self.name}_mean": float(np.mean(segment)),
            f"{self.name}_std": float(np.std(segment)),
            f"{self.name}_norm": float(np.linalg.norm(segment)),
        }

    def __repr__(self) -> str:
        return f"SemanticAxis({self.name}, [{self.offset}:{self.offset + self.dims}])"


class MaterialAxis(SemanticAxis):
    """Material properties axis (64 dims).

    Sub-axes:
        [0:16)   hardness          (HB / 500 normalized to [-1,1])
        [16:24)  thermal_conductivity (W/(m·K) / 400 normalized to [-1,1])
        [24:32)  ductility         (elongation% / 50 normalized to [-1,1])
        [32:40)  tensile_strength  (MPa / 2000 normalized to [-1,1])
        [40:48)  density           (g/cm³ / 20 normalized to [-1,1])
        [48:56)  elastic_modulus   (GPa / 500 normalized to [-1,1])
        [56:64)  reserved
    """

    ITEM_HARDNESS = "hardness"
    ITEM_THERMAL = "thermal_conductivity"
    ITEM_DUCTILITY = "ductility"
    ITEM_TENSILE = "tensile_strength"
    ITEM_DENSITY = "density"
    ITEM_ELASTIC = "elastic_modulus"

    def __init__(self):
        super().__init__("material", MATERIAL_OFFSET, MATERIAL_DIMS, "Material properties")
        self.register_sub_axis(self.ITEM_HARDNESS, 0, 16)
        self.register_sub_axis(self.ITEM_THERMAL, 16, 8)
        self.register_sub_axis(self.ITEM_DUCTILITY, 24, 8)
        self.register_sub_axis(self.ITEM_TENSILE, 32, 8)
        self.register_sub_axis(self.ITEM_DENSITY, 40, 8)
        self.register_sub_axis(self.ITEM_ELASTIC, 48, 8)
        self.register_sub_axis("reserved", 56, 8)

    def encode_material(
        self,
        hardness_hb: float = 0.0,
        thermal_conductivity: float = 0.0,
        ductility_pct: float = 0.0,
        tensile_strength_mpa: float = 0.0,
        density_gcm3: float = 0.0,
        elastic_modulus_gpa: float = 0.0,
    ) -> np.ndarray:
        vector = np.zeros(MATERIAL_DIMS, dtype=np.float32)
        vector[0:16] = np.clip(hardness_hb / 500.0 * 2.0 - 1.0, -1.0, 1.0)
        vector[16:24] = np.clip(thermal_conductivity / 400.0 * 2.0 - 1.0, -1.0, 1.0)
        vector[24:32] = np.clip(ductility_pct / 50.0 * 2.0 - 1.0, -1.0, 1.0)
        vector[32:40] = np.clip(tensile_strength_mpa / 2000.0 * 2.0 - 1.0, -1.0, 1.0)
        vector[40:48] = np.clip(density_gcm3 / 20.0 * 2.0 - 1.0, -1.0, 1.0)
        vector[48:56] = np.clip(elastic_modulus_gpa / 500.0 * 2.0 - 1.0, -1.0, 1.0)
        return vector


class ProcessAxis(SemanticAxis):
    """Process methods axis (128 dims).

    Sub-axes:
        [0:32)    process_type_onehot   (turning, milling, drilling, grinding, boring, ...)
        [32:64)   parameter_range       (feed_rate, depth_of_cut, spindle_speed)
        [64:96)   operation_sequence    (sequence encoding via positional + type encoding)
        [96:128)  tool_geometry         (tool diameter, length, nose radius, etc.)
    """

    ITEM_TYPE = "process_type"
    ITEM_PARAMS = "parameter_range"
    ITEM_SEQUENCE = "operation_sequence"
    ITEM_TOOL = "tool_geometry"

    PROCESS_TYPES = [
        "turning", "milling", "drilling", "grinding", "boring",
        "reaming", "tapping", "broaching", "planing", "shaping",
        "honing", "lapping", "edm", "ecm", "laser_cutting",
        "plasma_cutting", "waterjet", "additive", "forging", "casting",
        "welding", "heat_treatment", "surface_treatment", "coating",
        "polishing", "threading", "knurling", "grooving", "parting", "facing",
        "chamfering", "undercutting",
    ]

    def __init__(self):
        super().__init__("process", PROCESS_OFFSET, PROCESS_DIMS, "Machining methods")
        self.register_sub_axis(self.ITEM_TYPE, 0, 32)
        self.register_sub_axis(self.ITEM_PARAMS, 32, 32)
        self.register_sub_axis(self.ITEM_SEQUENCE, 64, 32)
        self.register_sub_axis(self.ITEM_TOOL, 96, 32)

    def encode_process_type(self, process_name: str) -> np.ndarray:
        vector = np.zeros(32, dtype=np.float32)
        process_lower = process_name.lower().replace(" ", "_").replace("-", "_")
        if process_lower in self.PROCESS_TYPES:
            idx = self.PROCESS_TYPES.index(process_lower)
            vector[idx] = 1.0
        else:
            best_match = None
            for i, pt in enumerate(self.PROCESS_TYPES):
                if pt in process_lower or process_lower in pt:
                    vector[i] = 0.8
                    best_match = True
                    break
            if not best_match:
                vector[0] = 0.5
        return vector

    def encode_parameters(
        self,
        feed_rate: float = 0.0,
        depth_of_cut: float = 0.0,
        spindle_speed: float = 0.0,
        step_over: float = 0.0,
    ) -> np.ndarray:
        vector = np.zeros(32, dtype=np.float32)
        vector[0:8] = np.clip(feed_rate / 2000.0 * 2.0 - 1.0, -1.0, 1.0)
        vector[8:16] = np.clip(depth_of_cut / 50.0 * 2.0 - 1.0, -1.0, 1.0)
        vector[16:24] = np.clip(spindle_speed / 30000.0 * 2.0 - 1.0, -1.0, 1.0)
        vector[24:32] = np.clip(step_over / 100.0 * 2.0 - 1.0, -1.0, 1.0)
        return vector

    def encode_sequence(self, operations: Sequence[Dict[str, float]]) -> np.ndarray:
        vector = np.zeros(32, dtype=np.float32)
        n_ops = min(len(operations), 8)
        for i, op in enumerate(operations[:n_ops]):
            pos = i * 4
            process_type_encoded = self.encode_process_type(op.get("type", "turning"))
            type_score = float(np.sum(process_type_encoded)) / 32.0
            position_weight = 1.0 - (i / n_ops) if n_ops > 0 else 0.0
            vector[pos:pos + 4] = type_score * position_weight
        return vector

    def encode_tool_geometry(
        self,
        tool_diameter: float = 0.0,
        tool_length: float = 0.0,
        nose_radius: float = 0.0,
        num_flutes: int = 2,
    ) -> np.ndarray:
        vector = np.zeros(32, dtype=np.float32)
        vector[0:8] = np.clip(tool_diameter / 200.0 * 2.0 - 1.0, -1.0, 1.0)
        vector[8:16] = np.clip(tool_length / 500.0 * 2.0 - 1.0, -1.0, 1.0)
        vector[16:24] = np.clip(nose_radius / 10.0 * 2.0 - 1.0, -1.0, 1.0)
        vector[24:32] = np.clip(num_flutes / 12.0 * 2.0 - 1.0, -1.0, 1.0)
        return vector


class PrecisionAxis(SemanticAxis):
    """Dimensional precision axis (32 dims).

    IT grade mapping: IT5=0.0, IT6=0.2, IT7=0.4, IT8=0.6, IT9=0.8, IT10=1.0, IT11=1.2, IT12=1.4
    Values are normalized to [-1, 1] where -1 = IT5 (highest precision) and 1 = IT12 (lowest).

    Sub-axes:
        [0:8)    dimensional_tolerance
        [8:16)   surface_roughness    (Ra in μm, normalized)
        [16:24)  geometric_tolerance  (flatness, cylindricity, etc.)
        [24:32)  positional_tolerance (concentricity, symmetry, etc.)
    """

    IT_GRADE_MAP = {
        "IT5": -1.00, "IT6": -0.714, "IT7": -0.429, "IT8": -0.143,
        "IT9": 0.143, "IT10": 0.429, "IT11": 0.714, "IT12": 1.000,
    }

    IT_NUMERIC_MAP = {
        5: -1.00, 6: -0.714, 7: -0.429, 8: -0.143,
        9: 0.143, 10: 0.429, 11: 0.714, 12: 1.000,
    }

    ITEM_DIMENSIONAL = "dimensional_tolerance"
    ITEM_SURFACE = "surface_roughness"
    ITEM_GEOMETRIC = "geometric_tolerance"
    ITEM_POSITIONAL = "positional_tolerance"

    def __init__(self):
        super().__init__("precision", PRECISION_OFFSET, PRECISION_DIMS, "Dimensional tolerance")
        self.register_sub_axis(self.ITEM_DIMENSIONAL, 0, 8)
        self.register_sub_axis(self.ITEM_SURFACE, 8, 8)
        self.register_sub_axis(self.ITEM_GEOMETRIC, 16, 8)
        self.register_sub_axis(self.ITEM_POSITIONAL, 24, 8)

    @classmethod
    def it_grade_to_value(cls, grade: str) -> float:
        if grade in cls.IT_GRADE_MAP:
            return cls.IT_GRADE_MAP[grade]
        if grade.startswith("IT"):
            try:
                num = int(grade[2:])
                return cls.IT_NUMERIC_MAP.get(num, 0.0)
            except (ValueError, IndexError):
                pass
        return 0.0

    def encode_precision(
        self,
        it_grade: str = "IT8",
        surface_roughness_ra: float = 3.2,
        geometric_tolerance: float = 0.02,
        positional_tolerance: float = 0.05,
    ) -> np.ndarray:
        vector = np.zeros(PRECISION_DIMS, dtype=np.float32)
        grade_val = self.it_grade_to_value(it_grade)
        vector[0:8] = grade_val
        vector[8:16] = np.clip(surface_roughness_ra / 25.0 * 2.0 - 1.0, -1.0, 1.0)
        vector[16:24] = np.clip(geometric_tolerance / 0.5 * 2.0 - 1.0, -1.0, 1.0)
        vector[24:32] = np.clip(positional_tolerance / 1.0 * 2.0 - 1.0, -1.0, 1.0)
        return vector


class StateAxis(SemanticAxis):
    """Equipment/tool real-time status axis (128 dims).

    Sub-axes:
        [0:32)    vibration          (3-axis vibration, FFT features)
        [32:64)   temperature        (spindle, tool, coolant temperatures)
        [64:96)   tool_wear          (flank wear, crater wear, edge condition)
        [96:128)  operating_state    (power, load, duty cycle, runtime)
    """

    ITEM_VIBRATION = "vibration"
    ITEM_TEMPERATURE = "temperature"
    ITEM_TOOL_WEAR = "tool_wear"
    ITEM_OPERATING = "operating_state"

    def __init__(self):
        super().__init__("state", STATE_OFFSET, STATE_DIMS, "Equipment status")
        self.register_sub_axis(self.ITEM_VIBRATION, 0, 32)
        self.register_sub_axis(self.ITEM_TEMPERATURE, 32, 32)
        self.register_sub_axis(self.ITEM_TOOL_WEAR, 64, 32)
        self.register_sub_axis(self.ITEM_OPERATING, 96, 32)

    def encode_state(
        self,
        vibration_x: float = 0.0,
        vibration_y: float = 0.0,
        vibration_z: float = 0.0,
        spindle_temp: float = 25.0,
        tool_temp: float = 25.0,
        coolant_temp: float = 20.0,
        flank_wear: float = 0.0,
        crater_wear: float = 0.0,
        edge_condition: float = 1.0,
        spindle_power: float = 0.0,
        spindle_load: float = 0.0,
        duty_cycle: float = 0.0,
        runtime_hours: float = 0.0,
    ) -> np.ndarray:
        vector = np.zeros(STATE_DIMS, dtype=np.float32)
        vector[0:8] = np.clip(vibration_x / 50.0 * 2.0 - 1.0, -1.0, 1.0)
        vector[8:16] = np.clip(vibration_y / 50.0 * 2.0 - 1.0, -1.0, 1.0)
        vector[16:24] = np.clip(vibration_z / 50.0 * 2.0 - 1.0, -1.0, 1.0)
        vector[24:32] = 0.0
        vector[32:40] = np.clip(spindle_temp / 200.0 * 2.0 - 1.0, -1.0, 1.0)
        vector[40:48] = np.clip(tool_temp / 500.0 * 2.0 - 1.0, -1.0, 1.0)
        vector[48:56] = np.clip(coolant_temp / 100.0 * 2.0 - 1.0, -1.0, 1.0)
        vector[56:64] = 0.0
        vector[64:80] = np.clip(flank_wear / 0.6 * 2.0 - 1.0, -1.0, 1.0)
        vector[80:88] = np.clip(crater_wear / 0.3 * 2.0 - 1.0, -1.0, 1.0)
        vector[88:96] = np.clip(edge_condition * 2.0 - 1.0, -1.0, 1.0)
        vector[96:104] = np.clip(spindle_power / 30.0 * 2.0 - 1.0, -1.0, 1.0)
        vector[104:112] = np.clip(spindle_load / 100.0 * 2.0 - 1.0, -1.0, 1.0)
        vector[112:120] = np.clip(duty_cycle / 100.0 * 2.0 - 1.0, -1.0, 1.0)
        vector[120:128] = np.clip(runtime_hours / 10000.0 * 2.0 - 1.0, -1.0, 1.0)
        return vector

    def encode_sensor_fusion(self, sensor_readings: Dict[str, float]) -> np.ndarray:
        return self.encode_state(
            vibration_x=sensor_readings.get("vibration_x", 0.0),
            vibration_y=sensor_readings.get("vibration_y", 0.0),
            vibration_z=sensor_readings.get("vibration_z", 0.0),
            spindle_temp=sensor_readings.get("spindle_temp", 25.0),
            tool_temp=sensor_readings.get("tool_temp", 25.0),
            coolant_temp=sensor_readings.get("coolant_temp", 20.0),
            flank_wear=sensor_readings.get("flank_wear", 0.0),
            crater_wear=sensor_readings.get("crater_wear", 0.0),
            edge_condition=sensor_readings.get("edge_condition", 1.0),
            spindle_power=sensor_readings.get("spindle_power", 0.0),
            spindle_load=sensor_readings.get("spindle_load", 0.0),
            duty_cycle=sensor_readings.get("duty_cycle", 0.0),
            runtime_hours=sensor_readings.get("runtime_hours", 0.0),
        )


class RiskAxis(SemanticAxis):
    """Safety risk axis (32 dims).

    Sub-axes:
        [0:8)    collision_risk      (probability of tool-workpiece collision)
        [8:16)   tool_breakage_risk  (probability of catastrophic tool failure)
        [16:24)  thermal_risk        (overheating, thermal runaway)
        [24:32)  quality_risk        (scrap probability, rework likelihood)
    """

    ITEM_COLLISION = "collision_risk"
    ITEM_BREAKAGE = "tool_breakage_risk"
    ITEM_THERMAL = "thermal_risk"
    ITEM_QUALITY = "quality_risk"

    def __init__(self):
        super().__init__("risk", RISK_OFFSET, RISK_DIMS, "Safety risk")
        self.register_sub_axis(self.ITEM_COLLISION, 0, 8)
        self.register_sub_axis(self.ITEM_BREAKAGE, 8, 16)
        self.register_sub_axis(self.ITEM_THERMAL, 16, 24)
        self.register_sub_axis(self.ITEM_QUALITY, 24, 32)

    def encode_risk(
        self,
        collision_prob: float = 0.0,
        breakage_prob: float = 0.0,
        thermal_risk: float = 0.0,
        quality_risk: float = 0.0,
    ) -> np.ndarray:
        vector = np.zeros(RISK_DIMS, dtype=np.float32)
        vector[0:8] = np.clip(collision_prob, 0.0, 1.0)
        vector[8:16] = np.clip(breakage_prob, 0.0, 1.0)
        vector[16:24] = np.clip(thermal_risk, 0.0, 1.0)
        vector[24:32] = np.clip(quality_risk, 0.0, 1.0)
        return vector


@dataclass
class EmbeddingSpace:
    """The 512-dimensional unified manufacturing semantic embedding space.

    Attributes:
        total_dims: Total embedding dimensions (512).
        material: Material properties axis.
        process: Process methods axis.
        precision: Dimensional precision axis.
        state: Equipment/tool state axis.
        risk: Safety risk axis.
        reserved_offset: Start of reserved dimensions.
        reserved_dims: Number of reserved dimensions.

    Example:
        >>> space = EmbeddingSpace()
        >>> emb = space.create_empty()
        >>> emb.shape
        (512,)
    """

    total_dims: int = TOTAL_DIMS
    material: MaterialAxis = field(default_factory=MaterialAxis)
    process: ProcessAxis = field(default_factory=ProcessAxis)
    precision: PrecisionAxis = field(default_factory=PrecisionAxis)
    state: StateAxis = field(default_factory=StateAxis)
    risk: RiskAxis = field(default_factory=RiskAxis)
    reserved_offset: int = RESERVED_OFFSET
    reserved_dims: int = RESERVED_DIMS

    def create_empty(self) -> np.ndarray:
        return np.zeros(self.total_dims, dtype=np.float32)

    def compose(
        self,
        material_vec: Optional[np.ndarray] = None,
        process_vec: Optional[np.ndarray] = None,
        precision_vec: Optional[np.ndarray] = None,
        state_vec: Optional[np.ndarray] = None,
        risk_vec: Optional[np.ndarray] = None,
        reserved_vec: Optional[np.ndarray] = None,
    ) -> np.ndarray:
        embedding = self.create_empty()
        if material_vec is not None:
            embedding[MATERIAL_OFFSET:MATERIAL_OFFSET + MATERIAL_DIMS] = material_vec[:MATERIAL_DIMS]
        if process_vec is not None:
            embedding[PROCESS_OFFSET:PROCESS_OFFSET + PROCESS_DIMS] = process_vec[:PROCESS_DIMS]
        if precision_vec is not None:
            embedding[PRECISION_OFFSET:PRECISION_OFFSET + PRECISION_DIMS] = precision_vec[:PRECISION_DIMS]
        if state_vec is not None:
            embedding[STATE_OFFSET:STATE_OFFSET + STATE_DIMS] = state_vec[:STATE_DIMS]
        if risk_vec is not None:
            embedding[RISK_OFFSET:RISK_OFFSET + RISK_DIMS] = risk_vec[:RISK_DIMS]
        if reserved_vec is not None:
            embedding[RESERVED_OFFSET:RESERVED_OFFSET + RESERVED_DIMS] = reserved_vec[:RESERVED_DIMS]
        return embedding

    def decompose(self, embedding: np.ndarray) -> Dict[str, np.ndarray]:
        return {
            "material": embedding[MATERIAL_OFFSET:MATERIAL_OFFSET + MATERIAL_DIMS].copy(),
            "process": embedding[PROCESS_OFFSET:PROCESS_OFFSET + PROCESS_DIMS].copy(),
            "precision": embedding[PRECISION_OFFSET:PRECISION_OFFSET + PRECISION_DIMS].copy(),
            "state": embedding[STATE_OFFSET:STATE_OFFSET + STATE_DIMS].copy(),
            "risk": embedding[RISK_OFFSET:RISK_OFFSET + RISK_DIMS].copy(),
            "reserved": embedding[RESERVED_OFFSET:RESERVED_OFFSET + RESERVED_DIMS].copy(),
        }

    def validate(self, embedding: np.ndarray) -> Dict[str, float]:
        if embedding.shape[-1] != self.total_dims:
            raise ValueError(
                f"嵌入空间维度验证失败：期望维度为 {self.total_dims}，实际维度为 {embedding.shape[-1]}。"
                f"请确保编码器输出维度与 UnifiedEmbeddingSpace 的总维度一致。"
            )
        metrics = {}
        metrics.update(self.material.validate(embedding))
        metrics.update(self.process.validate(embedding))
        metrics.update(self.precision.validate(embedding))
        metrics.update(self.state.validate(embedding))
        metrics.update(self.risk.validate(embedding))
        reserved = embedding[RESERVED_OFFSET:RESERVED_OFFSET + RESERVED_DIMS]
        metrics["reserved_mean"] = float(np.mean(reserved))
        metrics["reserved_std"] = float(np.std(reserved))
        metrics["total_norm"] = float(np.linalg.norm(embedding))
        return metrics

    def normalize(self, embedding: np.ndarray) -> np.ndarray:
        if embedding.ndim == 1:
            norm = np.linalg.norm(embedding)
            if norm > 1e-10:
                return embedding / norm
            return embedding
        if embedding.ndim == 2:
            norms = np.linalg.norm(embedding, axis=1, keepdims=True)
            norms = np.where(norms < 1e-10, 1.0, norms)
            return embedding / norms
        raise ValueError(
            f"嵌入归一化失败：输入维度为 {embedding.ndim}，期望1维或2维。"
        )

    def similarity(self, a: np.ndarray, b: np.ndarray) -> float:
        a_norm = a / (np.linalg.norm(a) + 1e-10)
        b_norm = b / (np.linalg.norm(b) + 1e-10)
        return float(np.dot(a_norm, b_norm))

    def axis_similarity(self, a: np.ndarray, b: np.ndarray) -> Dict[str, float]:
        return {
            "material": self.similarity(
                a[MATERIAL_OFFSET:MATERIAL_OFFSET + MATERIAL_DIMS],
                b[MATERIAL_OFFSET:MATERIAL_OFFSET + MATERIAL_DIMS],
            ),
            "process": self.similarity(
                a[PROCESS_OFFSET:PROCESS_OFFSET + PROCESS_DIMS],
                b[PROCESS_OFFSET:PROCESS_OFFSET + PROCESS_DIMS],
            ),
            "precision": self.similarity(
                a[PRECISION_OFFSET:PRECISION_OFFSET + PRECISION_DIMS],
                b[PRECISION_OFFSET:PRECISION_OFFSET + PRECISION_DIMS],
            ),
            "state": self.similarity(
                a[STATE_OFFSET:STATE_OFFSET + STATE_DIMS],
                b[STATE_OFFSET:STATE_OFFSET + STATE_DIMS],
            ),
            "risk": self.similarity(
                a[RISK_OFFSET:RISK_OFFSET + RISK_DIMS],
                b[RISK_OFFSET:RISK_OFFSET + RISK_DIMS],
            ),
        }

    def to_schema(self) -> dict:
        axes = {}
        for axis in [self.material, self.process, self.precision, self.state, self.risk]:
            sub_axes = {}
            for name, (offset, length) in axis._sub_axes.items():
                sub_axes[name] = {"offset": offset, "length": length}
            axes[axis.name] = {
                "offset": axis.offset,
                "dims": axis.dims,
                "description": axis.description,
                "sub_axes": sub_axes,
            }
        return {
            "total_dims": self.total_dims,
            "axes": axes,
            "reserved": {
                "offset": self.reserved_offset,
                "dims": self.reserved_dims,
                "description": "Future extensions and system optimization",
            },
        }


_embedding_space: Optional[EmbeddingSpace] = None


def get_embedding_space() -> EmbeddingSpace:
    global _embedding_space
    if _embedding_space is None:
        _embedding_space = EmbeddingSpace()
    return _embedding_space
