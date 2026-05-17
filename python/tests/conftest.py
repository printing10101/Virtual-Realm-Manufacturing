"""Backend pytest conftest - shared fixtures for organized test framework."""

from __future__ import annotations

import sys
import tempfile
import time
from pathlib import Path
from typing import Generator
from dataclasses import dataclass

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


@pytest.fixture(autouse=True)
def _env_setup(monkeypatch):
    """Ensure test environment variables are set before each test."""
    monkeypatch.setenv("LNN_AUTH_ENABLED", "false")
    monkeypatch.setenv("AGENT_AUTH_ENABLED", "false")
    monkeypatch.setenv("LNN_PERMISSION_ENFORCED", "false")
    monkeypatch.setenv("LNN_GSTACK_DIR", ".lingjing/.gstack_test")
    yield


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
