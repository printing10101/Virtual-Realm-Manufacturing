"""Backend pytest conftest - shared fixtures for organized test framework."""

from __future__ import annotations

import json
import random
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Generator

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


@pytest.fixture(autouse=True)
def _env_setup(monkeypatch):
    """Ensure test environment variables are set before each test."""
    monkeypatch.setenv("LNN_AUTH_ENABLED", "false")
    monkeypatch.setenv("AGENT_AUTH_ENABLED", "false")
    monkeypatch.setenv("LNN_PERMISSION_ENFORCED", "false")
    monkeypatch.setenv("LNN_GSTACK_DIR", ".lingjing/.gstack_test")
    monkeypatch.setenv("ENVIRONMENT", "testing")
    yield


# ---------------------------------------------------------------------------
# 集成测试专用 Fixtures
# ---------------------------------------------------------------------------


@dataclass
class MaterialSpec:
    """材料规格数据类."""

    name: str
    density: float  # g/cm³
    hardness_hb: float
    tensile_strength: float  # MPa
    machinability: float  # 0-1 可加工性
    thermal_conductivity: float  # W/(m·K)
    cutting_speed_range: tuple[float, float]  # m/min
    feed_range: tuple[float, float]  # mm/r
    depth_of_cut_range: tuple[float, float]  # mm


@dataclass
class SensorDataStream:
    """模拟传感器数据流."""

    timestamp: float
    vibration_x: float
    vibration_y: float
    vibration_z: float
    temperature: float
    acoustic_emission: float
    spindle_speed: float
    feed_rate: float
    cutting_force: float


@dataclass
class ProcessCard:
    """工艺卡片数据结构."""

    material: str
    part_name: str
    operations: list[dict[str, Any]] = field(default_factory=list)
    cutting_parameters: dict[str, Any] = field(default_factory=dict)
    estimated_time: float = 0.0  # hours
    batch_size: int = 1


@dataclass
class RiskItem:
    """风险条目."""

    risk_id: str
    category: str  # 安全/质量/效率/设备
    description: str
    severity: str  # 高/中/低
    probability: str  # 高/中/低
    mitigation: str


# 材料数据 fixtures
@pytest.fixture
def material_steel_45() -> MaterialSpec:
    """45号钢材料参数."""
    return MaterialSpec(
        name="45号钢",
        density=7.85,
        hardness_hb=197,
        tensile_strength=600,
        machinability=0.65,
        thermal_conductivity=50.2,
        cutting_speed_range=(100, 250),
        feed_range=(0.1, 0.5),
        depth_of_cut_range=(0.5, 5.0),
    )


@pytest.fixture
def material_tc4() -> MaterialSpec:
    """TC4钛合金材料参数."""
    return MaterialSpec(
        name="TC4钛合金",
        density=4.43,
        hardness_hb=330,
        tensile_strength=895,
        machinability=0.22,
        thermal_conductivity=7.2,
        cutting_speed_range=(30, 80),
        feed_range=(0.05, 0.15),
        depth_of_cut_range=(0.3, 2.5),
    )


@pytest.fixture
def material_aluminum_6061() -> MaterialSpec:
    """6061铝合金材料参数."""
    return MaterialSpec(
        name="6061铝合金",
        density=2.70,
        hardness_hb=95,
        tensile_strength=310,
        machinability=0.90,
        thermal_conductivity=167,
        cutting_speed_range=(200, 600),
        feed_range=(0.1, 1.0),
        depth_of_cut_range=(0.5, 6.0),
    )


# 三视图模拟数据 fixtures
@pytest.fixture
def standard_3view_images(temp_dir) -> dict[str, str]:
    """生成标准三视图模拟图像文件（PNG占位）. 实际测试中应替换为真实工程图."""
    views = {}
    for view_name in ["front", "side", "top"]:
        filepath = temp_dir / f"{view_name}_view.png"
        # 创建最小的PNG文件作为占位符
        _write_minimal_png(filepath, 1920, 1080)
        views[view_name] = str(filepath)
    return views


# IT8公差数据 fixtures
@pytest.fixture
def it8_tolerance_data() -> dict[str, Any]:
    """IT8级公差数值范围."""
    return {
        "grade": "IT8",
        "nominal_ranges": {
            "1-3mm": 0.014,
            "3-6mm": 0.018,
            "6-10mm": 0.022,
            "10-18mm": 0.027,
            "18-30mm": 0.033,
            "30-50mm": 0.039,
            "50-80mm": 0.046,
            "80-120mm": 0.054,
            "120-180mm": 0.063,
            "180-250mm": 0.072,
        },
    }


# 加工参数 fixtures
@pytest.fixture
def machining_params_steel() -> dict[str, Any]:
    """45号钢加工参数集."""
    return {
        "cutting_speed": 150.0,  # m/min
        "feed_rate": 0.2,  # mm/r
        "depth_of_cut": 2.0,  # mm
        "spindle_speed": 4775,  # r/min
        "coolant": True,
        "tool_material": "硬质合金",
        "tool_diameter": 10.0,  # mm
    }


@pytest.fixture
def machining_params_tc4() -> dict[str, Any]:
    """TC4钛合金加工参数集."""
    return {
        "cutting_speed": 50.0,
        "feed_rate": 0.08,
        "depth_of_cut": 1.0,
        "spindle_speed": 1592,
        "coolant": True,
        "tool_material": "硬质合金涂层",
        "tool_diameter": 10.0,
    }


# 传感器数据流 fixtures
@pytest.fixture
def normal_sensor_stream() -> list[SensorDataStream]:
    """正常加工状态传感器数据流（10秒，1kHz采样率）."""
    data = []
    base_time = time.time()
    for i in range(10000):  # 10秒 * 1kHz
        t = float(i) / 1000.0
        data.append(
            SensorDataStream(
                timestamp=base_time + t,
                vibration_x=0.5 + random.gauss(0, 0.05),
                vibration_y=0.4 + random.gauss(0, 0.04),
                vibration_z=0.3 + random.gauss(0, 0.03),
                temperature=35.0 + random.gauss(0, 0.1),
                acoustic_emission=0.02 + random.gauss(0, 0.002),
                spindle_speed=4775 + random.gauss(0, 5),
                feed_rate=0.2 + random.gauss(0, 0.01),
                cutting_force=150 + random.gauss(0, 5),
            )
        )
    return data


@pytest.fixture
def anomaly_sensor_stream() -> list[SensorDataStream]:
    """异常加工状态传感器数据流（刀具磨损/振动异常）."""
    data = []
    base_time = time.time()
    for i in range(10000):
        t = float(i) / 1000.0
        is_anomaly = i > 5000  # 5秒后开始异常
        vibration_mult = 3.0 if is_anomaly else 1.0
        temp_trend = 35.0 + (t * 0.5 if is_anomaly else 0)
        data.append(
            SensorDataStream(
                timestamp=base_time + t,
                vibration_x=(0.5 + random.gauss(0, 0.05)) * vibration_mult,
                vibration_y=(0.4 + random.gauss(0, 0.04)) * vibration_mult,
                vibration_z=(0.3 + random.gauss(0, 0.03)) * vibration_mult,
                temperature=temp_trend + random.gauss(0, 0.15),
                acoustic_emission=0.06 + random.gauss(0, 0.005),
                spindle_speed=4775 + random.gauss(0, 5),
                feed_rate=0.2 + random.gauss(0, 0.01),
                cutting_force=180 + random.gauss(0, 10),
            )
        )
    return data


# 生产批次数据 fixtures
@pytest.fixture
def production_batch_100() -> dict[str, Any]:
    """100件生产批次管理信息."""
    return {
        "batch_id": "BATCH-2026-001",
        "quantity": 100,
        "material": "45号钢",
        "part_name": "法兰盘-FL-001",
        "order_date": "2026-06-04",
        "due_date": "2026-06-18",
        "priority": "normal",
        "sub_batches": [
            {"sub_id": "BATCH-2026-001-A", "quantity": 50, "machine": "CNC-01"},
            {"sub_id": "BATCH-2026-001-B", "quantity": 50, "machine": "CNC-02"},
        ],
    }


# 工艺路线 fixtures
@pytest.fixture
def sample_process_card() -> ProcessCard:
    """标准工艺卡片样例."""
    card = ProcessCard(
        material="45号钢",
        part_name="法兰盘-FL-001",
        batch_size=100,
    )
    card.operations = [
        {"step": 1, "operation": "下料", "machine": "锯床GZ4230", "description": "按毛坯尺寸下料", "time_min": 2},
        {"step": 2, "operation": "粗车外圆", "machine": "数控车床CK6150", "description": "粗车外圆至Φ102mm", "time_min": 8},
        {"step": 3, "operation": "粗车端面", "machine": "数控车床CK6150", "description": "粗车两端面", "time_min": 5},
        {"step": 4, "operation": "钻孔", "machine": "加工中心VMC850", "description": "钻4×Φ8mm通孔", "time_min": 10},
        {"step": 5, "operation": "精车外圆", "machine": "数控车床CK6150", "description": "精车外圆至Φ100mm(IT8)", "time_min": 12},
        {"step": 6, "operation": "铰孔", "machine": "加工中心VMC850", "description": "铰孔至Φ8H8", "time_min": 8},
        {"step": 7, "operation": "检验", "machine": "三坐标测量机", "description": "全尺寸检验", "time_min": 15},
    ]
    card.cutting_parameters = {
        "rough_turning": {"v": 120, "f": 0.3, "ap": 2.0, "n": 800},
        "finish_turning": {"v": 180, "f": 0.1, "ap": 0.5, "n": 1200},
        "drilling": {"v": 25, "f": 0.15, "n": 1000},
        "reaming": {"v": 8, "f": 0.3, "n": 320},
    }
    card.estimated_time = sum(op["time_min"] for op in card.operations) / 60.0
    return card


# NC代码安全规则 fixtures
@pytest.fixture
def nc_validation_rules() -> dict[str, Any]:
    """NC代码验证规则集."""
    return {
        "mandatory_codes": ["G21", "G90", "M30"],
        "forbidden_patterns": [
            r"M00",  # 不应有无条件停止
        ],
        "safety_checks": {
            "spindle_speed_max": 8000,
            "feed_rate_max": 1000,
            "rapid_height_min": 5.0,
        },
    }


# 风险评估模板
@pytest.fixture
def risk_assessment_template() -> list[RiskItem]:
    """加工风险评估模板."""
    return [
        RiskItem("R01", "安全", "切屑飞溅伤害", "高", "中", "使用防护罩，佩戴防护眼镜"),
        RiskItem("R02", "质量", "刀具磨损导致尺寸超差", "中", "中", "定期检测刀具磨损，设置刀具寿命管理"),
        RiskItem("R03", "质量", "切削热导致工件变形", "中", "低", "充分使用切削液，控制切削参数"),
        RiskItem("R04", "设备", "主轴过载", "中", "低", "监控主轴负载率，合理设置切削参数"),
        RiskItem("R05", "效率", "工艺路线不合理导致工时增加", "低", "低", "优化工序顺序，减少换刀次数"),
    ]


# --- 辅助工具 ---


def _write_minimal_png(filepath: Path, width: int, height: int) -> None:
    """生成最小合法PNG文件."""
    import struct
    import zlib

    def chunk(chunk_type: bytes, data: bytes) -> bytes:
        c = chunk_type + data
        return struct.pack(">I", len(data)) + c + struct.pack(">I", zlib.crc32(c) & 0xFFFFFFFF)

    ihdr_data = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    raw_data = b""
    for y in range(height):
        raw_data += b"\x00" + b"\xff\xff\xff" * width
    idat_data = zlib.compress(raw_data)

    png = (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", ihdr_data)
        + chunk(b"IDAT", idat_data)
        + chunk(b"IEND", b"")
    )
    filepath.write_bytes(png)


@pytest.fixture
def high_precision_timer():
    """高精度计时器 fixture - 精度>=1ms."""

    class HighPrecisionTimer:
        def __init__(self):
            self._start = 0.0
            self._end = 0.0

        def __enter__(self):
            self._start = time.perf_counter()
            return self

        def __exit__(self, *args):
            self._end = time.perf_counter()

        @property
        def elapsed_ms(self) -> float:
            return (self._end - self._start) * 1000.0

        @property
        def elapsed_s(self) -> float:
            return self._end - self._start

        def reset(self):
            self._start = time.perf_counter()
            self._end = 0.0

        def stop(self):
            self._end = time.perf_counter()

    return HighPrecisionTimer()


@pytest.fixture
def test_report_collector():
    """测试报告收集器."""

    class ReportCollector:
        def __init__(self):
            self.results: list[dict[str, Any]] = []
            self.performance_metrics: dict[str, list[float]] = {}

        def add_result(self, test_name: str, passed: bool, details: str = "", metrics: dict[str, Any] | None = None):
            self.results.append({
                "test": test_name,
                "passed": passed,
                "details": details,
                "metrics": metrics or {},
                "timestamp": time.time(),
            })

        def record_metric(self, name: str, value: float):
            if name not in self.performance_metrics:
                self.performance_metrics[name] = []
            self.performance_metrics[name].append(value)

        def get_summary(self) -> dict[str, Any]:
            total = len(self.results)
            passed = sum(1 for r in self.results if r["passed"])
            return {
                "total": total,
                "passed": passed,
                "failed": total - passed,
                "pass_rate": passed / total if total > 0 else 0.0,
                "metrics_avg": {k: sum(v) / len(v) for k, v in self.performance_metrics.items()},
            }

        def to_json(self) -> str:
            return json.dumps(self.get_summary(), indent=2, ensure_ascii=False)

    return ReportCollector()


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """Provide a temporary directory that is cleaned up after the test."""
    with tempfile.TemporaryDirectory() as tmp:
        yield Path(tmp)


@dataclass
class Point3D:
    """3D point representation for geometry tests."""

    x: float
    y: float
    z: float = 0.0


@dataclass
class Circle2D:
    """2D circle representation for geometry tests."""

    center_x: float
    center_y: float
    radius: float


@dataclass
class Polygon2D:
    """2D polygon representation for geometry tests."""

    vertices: list[tuple[float, float]]


@pytest.fixture
def sample_circle() -> Circle2D:
    """Sample circle: center at origin, radius 10."""
    return Circle2D(center_x=0.0, center_y=0.0, radius=10.0)


@pytest.fixture
def sample_polygon_square() -> Polygon2D:
    """Sample square polygon: 10x10 centered at origin."""
    return Polygon2D(
        vertices=[
            (-5.0, -5.0),
            (5.0, -5.0),
            (5.0, 5.0),
            (-5.0, 5.0),
        ]
    )


@pytest.fixture
def sample_polygon_triangle() -> Polygon2D:
    """Sample triangle polygon."""
    return Polygon2D(
        vertices=[
            (0.0, 10.0),
            (-8.66, -5.0),
            (8.66, -5.0),
        ]
    )


@pytest.fixture
def sample_gcode_fanuc() -> str:
    """Sample Fanuc G-code for testing."""
    return """%
O0001 (PROGRAM 1 - TEST)
(POST: Fanuc 0i-MF)
G21 G17 G40 G49 G80 G90 G94
G00 G91 G28 Z0.
G00 G91 G28 X0. Y0.
G00 G90 G54 X0. Y0.
G00 G43 Z50.000 H00
M03 S8000
M08
G01 X10.000 Y10.000 F500.000
G01 X20.000 Y20.000 F500.000
M09
M05
G00 G91 G28 Z0.
G00 G91 G28 X0. Y0.
G90
M30
%"""


@pytest.fixture
def sample_gcode_heidenhain() -> str:
    """Sample Heidenhain code for testing."""
    return """0  BEGIN PGM 0001 MM
1  BLK FORM 0.1 Z X+0 Y+0 Z-50
2  BLK FORM 0.2 X+100 Y+100 Z+0
3  ; PROGRAM 1 - TEST
4  ; POST: Heidenhain TNC
5  TOOL CALL 1 Z S8000
6  L  Z+50.000 R0 FMAX
7  L  X+0 Y+0 R0 FMAX
8  M08
9  L  X+10.000 Y+10.000 F500.000
10  M09
11  M05
12  L  Z+50.000 R0 FMAX
13  L  X+0 Y+0 R0 FMAX
14  M30
15  END PGM 0000 MM"""


@pytest.fixture
def sample_gcode_siemens() -> str:
    """Sample Siemens G-code for testing."""
    return """N00010 ; PROGRAM 1 - TEST
N00020 ; POST: Siemens 840D
N00030 G17 G40 G90 G94
N00040 G00 Z50.000
N00050 G00 X0. Y0.
N00060 M03 S8000
N00070 M08
N00080 G01 X10.000 Y10.000 F500.000
N00090 M09
N00100 M05
N00110 G00 Z50.000
N00120 G00 X0. Y0.
N00130 M30"""


@pytest.fixture
def benchmark_gcode_tolerance() -> dict:
    """Default tolerance for G-code regression comparison."""
    return {
        "coordinate_precision": 0.01,
        "feed_rate_tolerance_percent": 5.0,
        "spindle_speed_tolerance_percent": 2.0,
        "ignore_comments": True,
        "ignore_program_numbers": True,
        "ignore_timestamps": True,
    }


@pytest.fixture
def performance_timer():
    """Timer fixture for measuring test execution time."""

    class Timer:
        def __init__(self):
            self.start_time = None
            self.end_time = None

        def __enter__(self):
            self.start_time = time.perf_counter()
            return self

        def __exit__(self, *args):
            self.end_time = time.perf_counter()

        @property
        def elapsed_ms(self) -> float:
            if self.start_time and self.end_time:
                return (self.end_time - self.start_time) * 1000
            return 0.0

        @property
        def elapsed_s(self) -> float:
            return self.elapsed_ms / 1000.0

    return Timer()
