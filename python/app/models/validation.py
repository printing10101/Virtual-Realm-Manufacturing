from dataclasses import dataclass, field
from typing import List, Optional
from enum import Enum


class ValidationStatus(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"


@dataclass
class CuttingDataPoint:
    """切削数据点"""
    material: str
    tool_material: str
    operation: str
    v_c: float
    f: float
    a_p: float
    F_c: Optional[float] = None
    V_b: Optional[float] = None
    R_a: Optional[float] = None
    T: Optional[float] = None
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
class ValidationReport:
    """验证报告"""
    dataset_name: str
    total_samples: int
    pass_count: int
    fail_count: int
    mape: float
    rmse: float
    r_squared: float
    details: List[ValidationResult] = field(default_factory=list)
