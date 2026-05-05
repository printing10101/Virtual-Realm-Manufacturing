from dataclasses import dataclass, field
from enum import StrEnum


class ValidationStatus(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"


class WearPhase(StrEnum):
    INITIAL = "initial"
    STEADY = "steady"
    ACCELERATED = "accelerated"


class UrgencyLevel(StrEnum):
    NORMAL = "normal"
    WARNING = "warning"
    CRITICAL = "critical"


class AdjustmentSuggestionItem:
    """单个参数调整建议"""
    param_type: str
    current_value: float
    suggested_value: float
    adjustment_delta: float
    expected_effect: str

    def __init__(self, param_type: str, current_value: float, suggested_value: float,
                 adjustment_delta: float, expected_effect: str):
        self.param_type = param_type
        self.current_value = current_value
        self.suggested_value = suggested_value
        self.adjustment_delta = adjustment_delta
        self.expected_effect = expected_effect

    def to_dict(self) -> dict:
        return {
            "param_type": self.param_type,
            "current_value": self.current_value,
            "suggested_value": self.suggested_value,
            "adjustment_delta": self.adjustment_delta,
            "expected_effect": self.expected_effect
        }


@dataclass
class CuttingDataPoint:
    """切削数据点"""
    material: str
    tool_material: str
    operation: str
    v_c: float
    f: float
    a_p: float
    F_c: float | None = None
    V_b: float | None = None
    R_a: float | None = None
    T: float | None = None
    source: str = ""


@dataclass
class ValidationResult:
    """单个验证结果"""
    metric_name: str
    predicted_value: float
    actual_value: float
    error: float
    error_percent: float
    status: ValidationStatus
    threshold: float


@dataclass
class WearDataPoint:
    """刀具磨损数据点"""
    time: float
    vb: float
    wear_rate: float
    phase: WearPhase


@dataclass
class WearCurve:
    """刀具磨损曲线"""
    data_points: list
    total_life: float
    time_to_threshold: float
    wear_rate_avg: float
    confidence: float

    def to_dict(self) -> dict:
        return {
            "data_points": [
                {
                    "time": dp.time,
                    "vb": dp.vb,
                    "wear_rate": dp.wear_rate,
                    "phase": dp.phase.value if isinstance(dp.phase, WearPhase) else dp.phase
                }
                for dp in self.data_points
            ],
            "total_life": self.total_life,
            "time_to_threshold": self.time_to_threshold,
            "wear_rate_avg": self.wear_rate_avg,
            "confidence": self.confidence
        }


@dataclass
class AdjustmentSuggestion:
    """参数调整建议"""
    current_wear: float
    remaining_life: float
    urgency: UrgencyLevel
    suggestions: list

    def to_dict(self) -> dict:
        return {
            "current_wear": self.current_wear,
            "remaining_life": self.remaining_life,
            "urgency": self.urgency.value if isinstance(self.urgency, UrgencyLevel) else self.urgency,
            "suggestions": [s.to_dict() if hasattr(s, 'to_dict') else s for s in self.suggestions]
        }


@dataclass
class ValidationReport:
    """验证报告"""
    dataset_name: str
    total_samples: int
    pass_count: int
    fail_count: int
    mape: float
    rmse: float
    r_squared: float
    details: list[ValidationResult] = field(default_factory=list)
