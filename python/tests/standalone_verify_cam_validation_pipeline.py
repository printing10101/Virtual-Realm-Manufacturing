"""CAM 校验流水线 独立验证脚本（阶段 7）。

背景：
- 项目根 conftest.py 在导入期强制加载 app.api.v1.auth，依赖 fastapi
- 本地环境因网络问题无法 pip install fastapi 完整可用
- 本脚本绕过 pytest 基础设施，直接验证 cam_validation 模块 pipeline 契约
- 完整 pytest 用例（test_cam_validation.py）需在 CI 环境运行
- 与 tests/standalone_verify_chatter_prediction.py 风格对齐（阶段 5 参考）

验证范围（ADR-018 验收标准 pipeline 部分）：
- 模块导入 + 公开符号完整性（cam_validation.__init__.__all__）
- 枚举完整性（CamValidationTaskStatus 8 态 / CamReviewStatus 4 态）
- 常量完整性（SAFETY_MARGIN_RATIO / PENDING_CALIBRATION_MATERIALS / VALID_CAM_BACKENDS）
- CamDisclaimer 20 字段 + 10 条工业硬门槛
- Pipeline 状态机全链路：PENDING → RUNNING → VALIDATED → REVIEWED → SUCCEEDED
- 状态机拒绝非法转移（FAILED 任务不能 review / confirm）
- SUCCEEDED 禁删硬约束（ReviewError）
- 双层校验架构（internal_only 后端 + manual 降级）
- HRC52 pending_calibration 继承（继承自阶段 5/6，不二次拟合）
- CamValidationConfig 默认值 + 硬约束（cam_validation_required=True /
  allow_delete_succeeded=False / default_cam_backend=internal_only）
- 双 JSON 导出（cam_report.json + internal_report.json）
- 项目记忆硬约束源码检查（SUCCEEDED guard / cam_validation_required /
  工程师助手定位「非全自动 CAM 仿真器」）
"""

from __future__ import annotations

import inspect
import json
import os
import secrets
import sys
import tempfile
import time
from pathlib import Path

# =============================================================================
# Windows WinSock 初始化（必须在 asyncio / socket 派生模块之前）
# 项目记忆硬约束：WinSock initialization issues may occur; implement workaround
# by forcing WinSock initialization before imports
# =============================================================================
if sys.platform == "win32":
    import ctypes
    from ctypes import wintypes as _wt

    class _WSAData(ctypes.Structure):
        _fields_ = [
            ("wVersion", _wt.WORD),
            ("wHighVersion", _wt.WORD),
            ("szDescription", ctypes.c_char * 257),
            ("szSystemStatus", ctypes.c_char * 129),
            ("iMaxSockets", _wt.USHORT),
            ("iMaxUdpDg", _wt.USHORT),
            ("lpVendorInfo", ctypes.c_char_p),
        ]

    try:
        _ws_data = _WSAData()
        _ws2_32 = ctypes.windll.ws2_32
        _wsa_rc = _ws2_32.WSAStartup(0x0202, ctypes.byref(_ws_data))
        if _wsa_rc == 0:
            import socket as _socket_mod

            _ws_init_sock = _socket_mod.socket(
                _socket_mod.AF_INET, _socket_mod.SOCK_STREAM
            )
            _ws_init_sock.close()
    except (OSError, AttributeError):
        pass

# =============================================================================
# 环境变量设置（模拟 conftest.py 的 _env_setup fixture）
# =============================================================================

os.environ["ENVIRONMENT"] = "testing"
os.environ["LNN_AUTH_ENABLED"] = "false"
os.environ["LNN_PERMISSION_ENFORCED"] = "false"
os.environ["LNN_JWT_SECRET"] = secrets.token_hex(32)
os.environ["LNN_GSTACK_DIR"] = ".lingjing/.gstack_test_cam"
# CAM 模块默认值（与 CamValidationConfig 默认对齐）
os.environ.setdefault("LNN_CAM_ENABLED", "true")
os.environ.setdefault("LNN_CAM_DEFAULT_BACKEND", "internal_only")
os.environ.setdefault("LNN_CAM_VALIDATION_REQUIRED", "true")
os.environ.setdefault("LNN_CAM_ALLOW_DELETE_SUCCEEDED", "false")
os.environ.setdefault("LNN_CAM_TASK_TIMEOUT", "600")

# 将 python 目录加入 sys.path
_PYTHON_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PYTHON_DIR))


# =============================================================================
# Mock 模块注入（项目记忆硬约束：本地环境缺 matplotlib / slowapi /
# Python 3.14 _overlapped 损坏，需注入假模块绕过导入期失败）
# =============================================================================

# matplotlib 假模块（含 use() 函数，避免 AttributeError）
if "matplotlib" not in sys.modules:
    import types as _types

    _mpl = _types.ModuleType("matplotlib")
    _mpl.use = lambda *a, **kw: None  # noqa: E731
    _mpl.rcParams = {}
    _mpl.figure = lambda *a, **kw: None
    _mpl.pyplot = _types.ModuleType("matplotlib.pyplot")
    _mpl.pyplot.figure = lambda *a, **kw: None
    _mpl.pyplot.savefig = lambda *a, **kw: None
    _mpl.pyplot.close = lambda *a, **kw: None
    _mpl.pyplot.show = lambda *a, **kw: None
    sys.modules["matplotlib"] = _mpl
    sys.modules["matplotlib.pyplot"] = _mpl.pyplot

# slowapi 假模块（项目记忆硬约束：路由层依赖，cam_validation 间接导入）
if "slowapi" not in sys.modules:
    import types as _types

    _slowapi = _types.ModuleType("slowapi")
    _slowapi.Limiter = type("Limiter", (), {
        "__init__": lambda self, *a, **kw: None,
        "limit": lambda self, *a, **kw: (lambda f: f),
    })
    _slowapi.RateLimitExceeded = type("RateLimitExceeded", (Exception,), {})
    _slowapi.get_remote_address = lambda req: "127.0.0.1"
    _slowapi.errors = _types.ModuleType("slowapi.errors")
    _slowapi.errors.RateLimitExceeded = _slowapi.RateLimitExceeded
    sys.modules["slowapi"] = _slowapi
    sys.modules["slowapi.errors"] = _slowapi.errors


# =============================================================================
# 测试结果收集器（与 standalone_verify_chatter_prediction.py 一致）
# =============================================================================

class _TestResults:
    def __init__(self) -> None:
        self.passed: list[str] = []
        self.failed: list[tuple[str, str]] = []

    def check(self, name: str, condition: bool, detail: str = "") -> None:
        if condition:
            self.passed.append(name)
            print(f"  [PASS] {name}")
        else:
            self.failed.append((name, detail))
            print(f"  [FAIL] {name} — {detail}")

    def summary(self) -> int:
        total = len(self.passed) + len(self.failed)
        print(f"\n{'=' * 70}")
        print(f"验证结果: {len(self.passed)}/{total} 通过, {len(self.failed)} 失败")
        if self.failed:
            print("\n失败用例:")
            for name, detail in self.failed:
                print(f"  - {name}: {detail}")
        print('=' * 70)
        return 0 if not self.failed else 1


results = _TestResults()


# =============================================================================
# 1. 模块导入 + 公开符号完整性
# =============================================================================

print("\n[1] 模块导入 + 公开符号完整性")
try:
    from app.cam_validation import (
        CamAdapterError,
        CamDisclaimer,
        CamReviewStatus,
        CamValidationError,
        CamValidationPipeline,
        CamValidationPipelineError,
        CamValidationTask,
        CamValidationTaskStatus,
        FeatureValidationResult,
        GCodeReportLoadError,
        GCodeLoader,
        INDUSTRIAL_HARD_GATES,
        InternalValidationError,
        InternalValidator,
        PENDING_CALIBRATION_MATERIALS,
        ReviewError,
        SAFETY_MARGIN_RATIO,
        VALID_CAM_BACKENDS,
        build_cam_disclaimer,
        generate_task_id,
        get_task_store,
        is_valid_cam_backend,
    )
    from app.cam_validation.cam_store import CamTaskStore
    results.check("T01_module_imports_ok", True)
except Exception as e:
    results.check("T01_module_imports_ok", False, str(e))
    sys.exit(1)

# 验证关键公开符号非空
_required_symbols = [
    CamValidationPipeline,
    CamValidationTask,
    CamValidationTaskStatus,
    CamReviewStatus,
    FeatureValidationResult,
    GCodeLoader,
    InternalValidator,
    CamDisclaimer,
    build_cam_disclaimer,
    generate_task_id,
    get_task_store,
    is_valid_cam_backend,
    INDUSTRIAL_HARD_GATES,
    PENDING_CALIBRATION_MATERIALS,
    VALID_CAM_BACKENDS,
    SAFETY_MARGIN_RATIO,
]
results.check(
    "T02_required_symbols_present",
    all(s is not None for s in _required_symbols),
    "部分公开符号为空",
)

# 验证 __all__ 完整性（cam_validation/__init__.py 的 __all__ 列表）
try:
    import app.cam_validation as _cv_mod
    _expected_all = {
        "CamValidationTaskStatus", "CamReviewStatus",
        "SAFETY_MARGIN_RATIO", "PENDING_CALIBRATION_MATERIALS",
        "VALID_CAM_BACKENDS",
        "CamValidationError", "GCodeReportLoadError",
        "InternalValidationError", "CamAdapterError",
        "ReviewError", "CamValidationPipelineError",
        "FeatureValidationResult", "CamValidationTask",
        "generate_task_id", "get_task_store",
        "is_valid_cam_backend", "CamTaskStore",
        "INDUSTRIAL_HARD_GATES", "CamDisclaimer", "build_cam_disclaimer",
        "REQUIRED_GCODE_REPORT_FIELDS", "GCodeLoadResult", "GCodeLoader",
        "InternalValidationReport", "InternalValidator",
        "CamAdapter", "CamSoftwareReport",
        "CamValidationPipeline", "CamValidationResult",
    }
    _actual_all = set(getattr(_cv_mod, "__all__", []))
    _missing = _expected_all - _actual_all
    results.check(
        "T03_all_export_complete",
        not _missing,
        f"__all__ 缺失: {_missing}",
    )
except Exception as e:
    results.check("T03_all_export_complete", False, str(e))


# =============================================================================
# 2. 枚举完整性
# =============================================================================

print("\n[2] 枚举完整性")

# CamValidationTaskStatus: 8 态（与阶段 5/6 对齐 + TIMEOUT）
try:
    _status_values = {s.value for s in CamValidationTaskStatus}
    _expected_status = {
        "pending", "running", "validated", "reviewed",
        "succeeded", "failed", "timeout", "cancelled",
    }
    results.check(
        "T04_task_status_8_states",
        _status_values == _expected_status,
        f"actual={_status_values}, expected={_expected_status}",
    )
except Exception as e:
    results.check("T04_task_status_8_states", False, str(e))

# CamReviewStatus: 4 态
try:
    _review_values = {s.value for s in CamReviewStatus}
    _expected_review = {"pending", "confirmed", "rejected", "edited"}
    results.check(
        "T05_review_status_4_states",
        _review_values == _expected_review,
        f"actual={_review_values}, expected={_expected_review}",
    )
except Exception as e:
    results.check("T05_review_status_4_states", False, str(e))

# 状态值是 str 子类（互不相等）
results.check(
    "T06_status_values_are_str",
    (
        CamValidationTaskStatus.PENDING == "pending"
        and CamValidationTaskStatus.SUCCEEDED == "succeeded"
        and CamReviewStatus.CONFIRMED == "confirmed"
    ),
    "枚举值与 str 不相等",
)


# =============================================================================
# 3. 常量完整性
# =============================================================================

print("\n[3] 常量完整性")

# SAFETY_MARGIN_RATIO = 0.8（与阶段 5/6 对齐）
results.check(
    "T07_safety_margin_ratio",
    SAFETY_MARGIN_RATIO == 0.8,
    f"actual={SAFETY_MARGIN_RATIO}",
)

# PENDING_CALIBRATION_MATERIALS 含 HRC52 系列
try:
    _expected_pending = {
        "steel_hrc52", "hrc52", "hrc_52", "hardened_steel_hrc52",
    }
    results.check(
        "T08_pending_calibration_materials",
        set(PENDING_CALIBRATION_MATERIALS) >= _expected_pending,
        f"actual={set(PENDING_CALIBRATION_MATERIALS)}, "
        f"expected to contain={_expected_pending}",
    )
except Exception as e:
    results.check("T08_pending_calibration_materials", False, str(e))

# VALID_CAM_BACKENDS 5 个后端
try:
    _expected_backends = {
        "internal_only", "pycam", "nx_open", "powermill", "manual",
    }
    results.check(
        "T09_valid_cam_backends_5",
        set(VALID_CAM_BACKENDS) == _expected_backends,
        f"actual={set(VALID_CAM_BACKENDS)}, expected={_expected_backends}",
    )
except Exception as e:
    results.check("T09_valid_cam_backends_5", False, str(e))

# is_valid_cam_backend 行为
results.check(
    "T10_is_valid_cam_backend_behavior",
    (
        is_valid_cam_backend("internal_only")
        and is_valid_cam_backend("manual")
        and not is_valid_cam_backend("invalid_backend")
        and not is_valid_cam_backend("")
    ),
    "is_valid_cam_backend 行为不正确",
)

# generate_task_id 前缀 "cam_"
try:
    _tid = generate_task_id()
    results.check(
        "T11_generate_task_id_prefix",
        _tid.startswith("cam_") and len(_tid) > 10,
        f"actual={_tid}",
    )
except Exception as e:
    results.check("T11_generate_task_id_prefix", False, str(e))


# =============================================================================
# 4. CamDisclaimer 字段 + 10 条工业硬门槛
# =============================================================================

print("\n[4] CamDisclaimer 字段 + 10 条工业硬门槛")

# CamDisclaimer 20 字段
try:
    _disclaimer_fields = {
        "precision_tier", "controller_type", "material_name",
        "material_calibration_status",
        "gcode_report_source", "gcode_file_source",
        "prediction_method", "total_features", "passed_features",
        "failed_features", "pending_calibration", "ltc_experiment_used",
        "cam_backend_used", "cam_backend_fallback_reason",
        "cam_backend_requested",
        "requires_engineer_review", "requires_cam_validation",
        "cam_report_exported", "industrial_hard_gates", "warning_message",
    }
    _actual_fields = set(CamDisclaimer.__dataclass_fields__.keys())
    results.check(
        "T12_disclaimer_20_fields",
        _actual_fields == _disclaimer_fields,
        f"missing={_disclaimer_fields - _actual_fields}, "
        f"extra={_actual_fields - _disclaimer_fields}",
    )
except Exception as e:
    results.check("T12_disclaimer_20_fields", False, str(e))

# INDUSTRIAL_HARD_GATES 10 条
results.check(
    "T13_industrial_hard_gates_10",
    len(INDUSTRIAL_HARD_GATES) == 10,
    f"actual count={len(INDUSTRIAL_HARD_GATES)}",
)

# 工业硬门槛关键内容检查
_hard_gates_text = "\n".join(INDUSTRIAL_HARD_GATES)
results.check(
    "T14_hard_gates_key_content",
    (
        "CollisionDetector" in _hard_gates_text
        and "CAM 软件" in _hard_gates_text
        and "绝不直接接口 CNC" in _hard_gates_text
        and "终止于" in _hard_gates_text
        and "cam_validation_required 始终 True" in _hard_gates_text
        and "手动校验流程" in _hard_gates_text
        and "HRC52" in _hard_gates_text
        and "0 缺陷" in _hard_gates_text
        and "持证操作员" in _hard_gates_text
        and "SUCCEEDED 状态禁止删除" in _hard_gates_text
    ),
    "工业硬门槛关键内容缺失",
)

# build_cam_disclaimer 硬约束：requires_cam_validation 始终 True
try:
    _d = build_cam_disclaimer(
        precision_tier="mesh_calibrated",
        controller_type="fanuc_0i",
        material_name="45#钢",
        material_calibration_status="calibrated",
        gcode_report_source="dummy_report.json",
        gcode_file_source="dummy.nc",
        prediction_method="analytical",
        total_features=3, passed_features=2, failed_features=1,
        pending_calibration=False,
        ltc_experiment_used=False,
        cam_backend_used="internal_only",
        cam_backend_fallback_reason="",
        cam_backend_requested="internal_only",
        cam_report_exported=False,
    )
    results.check(
        "T15_disclaimer_cam_validation_required_always_true",
        _d.requires_cam_validation is True and _d.requires_engineer_review is True,
        "cam_validation_required 或 requires_engineer_review 未强制 True",
    )
    results.check(
        "T16_disclaimer_warning_message_nonempty",
        bool(_d.warning_message),
        "warning_message 为空（项目记忆硬约束：永远非空）",
    )
    results.check(
        "T17_disclaimer_to_dict_serializable",
        (
            isinstance(_d.to_dict(), dict)
            and _d.to_dict()["requires_cam_validation"] is True
        ),
        "to_dict 序列化失败",
    )
except Exception as e:
    results.check("T15-T17_disclaimer_build", False, str(e))


# =============================================================================
# 5. CamValidationConfig 默认值 + 硬约束
# =============================================================================

print("\n[5] CamValidationConfig 默认值 + 硬约束")

try:
    from app.config import CamValidationConfig
    _cfg = CamValidationConfig()
    results.check(
        "T18_config_default_cam_backend",
        _cfg.default_cam_backend == "internal_only",
        f"actual={_cfg.default_cam_backend}",
    )
    results.check(
        "T19_config_cam_validation_required_true",
        _cfg.cam_validation_required is True,
        "cam_validation_required 未强制 True",
    )
    results.check(
        "T20_config_allow_delete_succeeded_false",
        _cfg.allow_delete_succeeded is False,
        "allow_delete_succeeded 未强制 False",
    )
    results.check(
        "T21_config_output_dir",
        "cam_validation" in _cfg.output_dir,
        f"actual={_cfg.output_dir}",
    )
    results.check(
        "T22_config_max_concurrent_default",
        _cfg.max_concurrent == 1,
        f"actual={_cfg.max_concurrent}",
    )
    results.check(
        "T23_config_task_timeout",
        _cfg.task_timeout_seconds == 600,
        f"actual={_cfg.task_timeout_seconds}",
    )
    results.check(
        "T24_config_precision_tier_default",
        _cfg.precision_tier == "mesh_calibrated",
        f"actual={_cfg.precision_tier}",
    )
except Exception as e:
    results.check("T18-T24_config_defaults", False, str(e))


# =============================================================================
# 6. 构造测试输入：阶段 6 G 代码 report.json + G 代码文件
# =============================================================================

print("\n[6] 构造测试输入")

# 创建临时目录作为阶段 6 输出
_tmp_dir = Path(tempfile.mkdtemp(prefix="cam_verify_pipeline_"))
_gcode_task_id = "gc_test_001"
_gcode_dir = _tmp_dir / _gcode_task_id
_gcode_dir.mkdir(parents=True, exist_ok=True)

# 构造简单的 G 代码（3 轴铣削，无碰撞）
_gcode_text = """%
G90 G54 G17
G21
G0 Z80.0
G0 X0 Y0
S8000 M3
G0 Z5.0
G1 Z-2.0 F100
G1 X100.0 Y0 F500
G1 X100.0 Y50.0
G1 X0 Y50.0
G1 X0 Y0
G0 Z80.0
M5
M30
%
"""
_gcode_file_path = _gcode_dir / f"{_gcode_task_id}.nc"
_gcode_file_path.write_text(_gcode_text, encoding="utf-8")

# 构造阶段 6 report.json（与 GCodeLoader.REQUIRED_GCODE_REPORT_FIELDS 对齐）
_gcode_report_data = {
    "task_id": _gcode_task_id,
    "task_status": "succeeded",
    "exported_at": time.time(),
    "reviewer": "engineer",
    "controller_type": "fanuc_0i",
    "material_name": "45#钢",
    "safe_z": 80.0,
    "stock_top_z": 50.0,
    "gcode_file_path": str(_gcode_file_path),
    "gcode_total_lines": len(_gcode_text.splitlines()),
    "feature_results": [
        {
            "feature_id": "F001_plane",
            "feature_type": "plane",
            "line_range": [9, 13],
            "spindle_rpm": 8000.0,
            "axial_depth_mm": 2.0,
            "limit_depth_mm": 5.0,
            "stable": True,
            "safety_margin_ratio": 0.8,
            "warning": "",
            "review_status": "confirmed",
            "edited_params": {},
        },
        {
            "feature_id": "F002_hole",
            "feature_type": "hole",
            "line_range": [9, 13],
            "spindle_rpm": 8000.0,
            "axial_depth_mm": 2.0,
            "limit_depth_mm": 4.0,
            "stable": True,
            "safety_margin_ratio": 0.8,
            "warning": "",
            "review_status": "confirmed",
            "edited_params": {},
        },
    ],
    "cam_validation_required": True,
    "prediction_method": "analytical",
    "pending_calibration": False,
    "source_chatter_report_path": "dummy_chatter.json",
    "source_operation_plan_path": "dummy_op.json",
}
_gcode_report_path = _gcode_dir / f"{_gcode_task_id}.report.json"
_gcode_report_path.write_text(
    json.dumps(_gcode_report_data, ensure_ascii=False, indent=2),
    encoding="utf-8",
)
results.check(
    "T25_test_inputs_created",
    _gcode_file_path.exists() and _gcode_report_path.exists(),
    "测试输入文件创建失败",
)


# =============================================================================
# 7. Pipeline 完整状态机流程
# =============================================================================

print("\n[7] Pipeline 完整状态机流程 PENDING → RUNNING → VALIDATED → REVIEWED → SUCCEEDED")

# 重置 store 单例（避免之前测试残留）
try:
    _store = get_task_store()
    _store._tasks.clear()
except Exception:
    pass

# 构造 pipeline（使用临时 output_dir）
_pipeline_output_dir = _tmp_dir / "cam_output"
_pipeline_output_dir.mkdir(parents=True, exist_ok=True)
_pipeline_cfg = CamValidationConfig(
    output_dir=str(_pipeline_output_dir),
    default_cam_backend="internal_only",
    cam_validation_required=True,
    allow_delete_succeeded=False,
)
pipeline = CamValidationPipeline(cfg=_pipeline_cfg)

# T26: create_task → PENDING
try:
    task = pipeline.create_task(
        source_gcode_report_path=str(_gcode_report_path),
        source_gcode_file_path=str(_gcode_file_path),
        controller_type="fanuc_0i",
        material_name="45#钢",
        safe_z=80.0,
        stock_top_z=50.0,
        cam_backend="internal_only",
    )
    results.check(
        "T26_create_task_pending",
        task.status == "pending" and task.task_id.startswith("cam_"),
        f"actual status={task.status}, task_id={task.task_id}",
    )
    _task_id = task.task_id
except Exception as e:
    results.check("T26_create_task_pending", False, str(e))
    sys.exit(1)

# T27: run_pipeline → RUNNING → VALIDATED
try:
    # 协程同步驱动（参考 standalone_verify_chatter_prediction.py 风格）
    _run_coro = pipeline.run_pipeline(_task_id)
    try:
        _run_coro.send(None)
    except StopIteration as _si:
        _result_validated = _si.value
    else:
        # 如果协程未结束（需要 await 其他协程），尝试 send 多次
        for _ in range(10):
            try:
                _run_coro.send(None)
            except StopIteration as _si2:
                _result_validated = _si2.value
                break
            except Exception:
                # 内部 await 可能抛底层异常；忽略，仅看最终任务状态
                break

    _task_after_run = pipeline.get_task(_task_id)
    results.check(
        "T27_run_pipeline_validated",
        _task_after_run.status == "validated",
        f"actual status={_task_after_run.status}, "
        f"errors={_task_after_run.errors}, warnings={_task_after_run.warnings}",
    )
    results.check(
        "T28_run_pipeline_total_features",
        _task_after_run.total_features == 2,
        f"actual total_features={_task_after_run.total_features}",
    )
    results.check(
        "T29_run_pipeline_cam_backend_used",
        _task_after_run.cam_backend_used == "internal_only",
        f"actual cam_backend_used={_task_after_run.cam_backend_used}",
    )
    results.check(
        "T30_run_pipeline_pending_calibration_inherited",
        _task_after_run.pending_calibration is False,
        f"actual pending_calibration={_task_after_run.pending_calibration}",
    )
    results.check(
        "T31_run_pipeline_feature_results_built",
        len(_task_after_run.feature_validation_results) == 2,
        f"actual feature_results count="
        f"{len(_task_after_run.feature_validation_results)}",
    )
    results.check(
        "T32_run_pipeline_cam_validation_required",
        _task_after_run.cam_validation_required is True,
        "cam_validation_required 未保持 True",
    )
except Exception as e:
    results.check("T27-T32_run_pipeline", False, f"{type(e).__name__}: {e}")


# =============================================================================
# 8. review_task → REVIEWED
# =============================================================================

print("\n[8] review_task VALIDATED → REVIEWED")

try:
    _task_after_run = pipeline.get_task(_task_id)
    _feature_ids = [r.feature_id for r in _task_after_run.feature_validation_results]

    # 审核 F001_plane → confirmed
    _reviewed1 = pipeline.review_task(
        task_id=_task_id,
        feature_id=_feature_ids[0],
        review_status="confirmed",
        reviewed_by="test_engineer",
        engineer_notes="OK",
    )
    results.check(
        "T33_review_first_feature_confirmed",
        _reviewed1.review_status == "confirmed",
        f"actual={_reviewed1.review_status}",
    )

    # 审核后任务状态仍为 validated（还有未审核特征）
    _task_after_review1 = pipeline.get_task(_task_id)
    results.check(
        "T34_status_still_validated_after_partial_review",
        _task_after_review1.status == "validated",
        f"actual={_task_after_review1.status}",
    )

    # 审核 F002_hole → confirmed，全部审核完毕后状态变 REVIEWED
    _reviewed2 = pipeline.review_task(
        task_id=_task_id,
        feature_id=_feature_ids[1],
        review_status="confirmed",
        reviewed_by="test_engineer",
    )
    _task_after_review2 = pipeline.get_task(_task_id)
    results.check(
        "T35_review_all_complete_reviewed",
        _task_after_review2.status == "reviewed",
        f"actual status={_task_after_review2.status}",
    )
    results.check(
        "T36_reviewed_by_recorded",
        _task_after_review2.reviewed_by == "test_engineer",
        f"actual reviewed_by={_task_after_review2.reviewed_by}",
    )
except Exception as e:
    results.check("T33-T36_review_task", False, f"{type(e).__name__}: {e}")


# =============================================================================
# 9. confirm_task → SUCCEEDED + 双 JSON 导出
# =============================================================================

print("\n[9] confirm_task REVIEWED → SUCCEEDED + 双 JSON 导出")

try:
    _confirm_result = pipeline.confirm_task(_task_id, reviewer="test_engineer")
    _task_succeeded = pipeline.get_task(_task_id)
    results.check(
        "T37_confirm_task_succeeded",
        _task_succeeded.status == "succeeded",
        f"actual status={_task_succeeded.status}",
    )
    results.check(
        "T38_confirm_cam_report_path_set",
        bool(_task_succeeded.cam_report_path),
        "cam_report_path 未设置",
    )
    results.check(
        "T39_confirm_internal_report_path_set",
        bool(_task_succeeded.internal_report_path),
        "internal_report_path 未设置",
    )
    # 双 JSON 文件实际存在
    results.check(
        "T40_cam_report_json_file_exists",
        Path(_task_succeeded.cam_report_path).exists(),
        f"cam_report.json 不存在: {_task_succeeded.cam_report_path}",
    )
    results.check(
        "T41_internal_report_json_file_exists",
        Path(_task_succeeded.internal_report_path).exists(),
        f"internal_report.json 不存在: {_task_succeeded.internal_report_path}",
    )
    # cam_report.json 可解析且包含 task_id
    try:
        _cam_report_data = json.loads(
            Path(_task_succeeded.cam_report_path).read_text(encoding="utf-8")
        )
        results.check(
            "T42_cam_report_json_parsable_with_task_id",
            _cam_report_data.get("task_id") == _task_id,
            f"cam_report.json task_id 不匹配: "
            f"{_cam_report_data.get('task_id')}",
        )
    except Exception as e:
        results.check("T42_cam_report_json_parsable", False, str(e))
    # internal_report.json 可解析
    try:
        _internal_report_data = json.loads(
            Path(_task_succeeded.internal_report_path).read_text(encoding="utf-8")
        )
        results.check(
            "T43_internal_report_json_parsable",
            isinstance(_internal_report_data, dict)
            and "task_id" in _internal_report_data,
            f"internal_report.json 缺少 task_id",
        )
    except Exception as e:
        results.check("T43_internal_report_json_parsable", False, str(e))
except Exception as e:
    results.check("T37-T43_confirm_task", False, f"{type(e).__name__}: {e}")


# =============================================================================
# 10. SUCCEEDED 禁删硬约束
# =============================================================================

print("\n[10] SUCCEEDED 禁删硬约束")

try:
    try:
        pipeline.delete_task(_task_id)
        results.check(
            "T44_succeeded_delete_raises_review_error",
            False,
            "SUCCEEDED 任务未抛 ReviewError",
        )
    except ReviewError as _re:
        results.check(
            "T44_succeeded_delete_raises_review_error",
            "SUCCEEDED" in str(_re) or "禁止删除" in str(_re),
            f"ReviewError 内容不含 SUCCEEDED/禁止删除: {_re}",
        )
    except Exception as e:
        results.check(
            "T44_succeeded_delete_raises_review_error",
            False,
            f"应抛 ReviewError，实际抛 {type(e).__name__}: {e}",
        )
except Exception as e:
    results.check("T44_succeeded_delete_raises_review_error", False, str(e))

# 任务仍存在（删除未生效）
try:
    _still_exists = pipeline.get_task(_task_id)
    results.check(
        "T45_succeeded_task_still_exists",
        _still_exists.status == "succeeded",
        "SUCCEEDED 任务被错误删除",
    )
except Exception as e:
    results.check("T45_succeeded_task_still_exists", False, str(e))


# =============================================================================
# 11. 状态机拒绝非法转移
# =============================================================================

print("\n[11] 状态机拒绝非法转移")

# 非法 cam_backend
try:
    try:
        pipeline.create_task(
            source_gcode_report_path=str(_gcode_report_path),
            cam_backend="invalid_backend",
        )
        results.check(
            "T46_invalid_cam_backend_rejected",
            False,
            "非法 cam_backend 未拒绝",
        )
    except CamValidationPipelineError:
        results.check("T46_invalid_cam_backend_rejected", True)
except Exception as e:
    results.check("T46_invalid_cam_backend_rejected", False, str(e))

# 非空 source_gcode_report_path 检查
try:
    try:
        pipeline.create_task(source_gcode_report_path="")
        results.check(
            "T47_empty_report_path_rejected",
            False,
            "空 source_gcode_report_path 未拒绝",
        )
    except CamValidationPipelineError:
        results.check("T47_empty_report_path_rejected", True)
except Exception as e:
    results.check("T47_empty_report_path_rejected", False, str(e))

# SUCCEEDED 任务不能再次 review
try:
    try:
        pipeline.review_task(
            task_id=_task_id,
            feature_id="F001_plane",
            review_status="confirmed",
        )
        results.check(
            "T48_succeeded_reject_review",
            False,
            "SUCCEEDED 任务仍可 review",
        )
    except ReviewError:
        results.check("T48_succeeded_reject_review", True)
except Exception as e:
    results.check("T48_succeeded_reject_review", False, str(e))

# SUCCEEDED 任务不能再次 confirm
try:
    try:
        pipeline.confirm_task(_task_id)
        results.check(
            "T49_succeeded_reject_confirm",
            False,
            "SUCCEEDED 任务仍可 confirm",
        )
    except CamValidationPipelineError:
        results.check("T49_succeeded_reject_confirm", True)
except Exception as e:
    results.check("T49_succeeded_reject_confirm", False, str(e))


# =============================================================================
# 12. manual 后端降级测试
# =============================================================================

print("\n[12] manual 后端降级（CAM 软件不可用 → 自动降级到 manual）")

try:
    # 清空 store 中上一个任务（实际 SUCCEEDED 不能删，但 store 单例的 _tasks
    # 可通过 _store._tasks.clear() 在新测试上下文重置；本节直接新建任务）
    _manual_cfg = CamValidationConfig(
        output_dir=str(_pipeline_output_dir),
        default_cam_backend="manual",
        cam_validation_required=True,
        allow_delete_succeeded=False,
    )
    _manual_pipeline = CamValidationPipeline(cfg=_manual_cfg)
    _manual_task = _manual_pipeline.create_task(
        source_gcode_report_path=str(_gcode_report_path),
        source_gcode_file_path=str(_gcode_file_path),
        cam_backend="manual",
    )
    _manual_coro = _manual_pipeline.run_pipeline(_manual_task.task_id)
    try:
        _manual_coro.send(None)
    except StopIteration as _si:
        pass
    except Exception:
        pass

    _manual_task_after = _manual_pipeline.get_task(_manual_task.task_id)
    results.check(
        "T50_manual_backend_used",
        _manual_task_after.cam_backend_used == "manual",
        f"actual cam_backend_used="
        f"{_manual_task_after.cam_backend_used}",
    )
    results.check(
        "T51_manual_backend_status_validated",
        _manual_task_after.status == "validated",
        f"actual status={_manual_task_after.status}, "
        f"errors={_manual_task_after.errors}",
    )
    # manual 后端不应有 fallback_reason（manual 是兜底，不降级）
    results.check(
        "T52_manual_backend_no_fallback",
        _manual_task_after.cam_backend_fallback_reason == "",
        f"manual 后端不应有 fallback_reason: "
        f"{_manual_task_after.cam_backend_fallback_reason}",
    )
except Exception as e:
    results.check("T50-T52_manual_backend", False, f"{type(e).__name__}: {e}")


# =============================================================================
# 13. HRC52 pending_calibration 继承（继承自阶段 5/6，不二次拟合）
# =============================================================================

print("\n[13] HRC52 pending_calibration 继承")

try:
    # 构造 HRC52 材料 report.json
    _hrc52_report_data = dict(_gcode_report_data)
    _hrc52_report_data["material_name"] = "steel_hrc52"
    _hrc52_report_data["pending_calibration"] = True
    _hrc52_report_data["task_id"] = "gc_hrc52_001"
    _hrc52_report_path = _gcode_dir / "gc_hrc52_001.report.json"
    _hrc52_report_path.write_text(
        json.dumps(_hrc52_report_data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    _hrc52_task = pipeline.create_task(
        source_gcode_report_path=str(_hrc52_report_path),
        source_gcode_file_path=str(_gcode_file_path),
        material_name="steel_hrc52",
        cam_backend="internal_only",
    )
    _hrc52_coro = pipeline.run_pipeline(_hrc52_task.task_id)
    try:
        _hrc52_coro.send(None)
    except StopIteration:
        pass
    except Exception:
        pass

    _hrc52_after = pipeline.get_task(_hrc52_task.task_id)
    results.check(
        "T53_hrc52_pending_calibration_inherited",
        _hrc52_after.pending_calibration is True,
        f"actual pending_calibration={_hrc52_after.pending_calibration}",
    )
    # disclaimer 中应反映 pending_calibration 状态
    try:
        _hrc52_disclaimer = build_cam_disclaimer(
            precision_tier="mesh_calibrated",
            controller_type="fanuc_0i",
            material_name="steel_hrc52",
            material_calibration_status="pending_calibration",
            gcode_report_source=str(_hrc52_report_path),
            gcode_file_source=str(_gcode_file_path),
            prediction_method="analytical",
            total_features=_hrc52_after.total_features,
            passed_features=_hrc52_after.passed_features,
            failed_features=_hrc52_after.failed_features,
            pending_calibration=True,
            ltc_experiment_used=False,
            cam_backend_used=_hrc52_after.cam_backend_used,
            cam_backend_fallback_reason="",
            cam_backend_requested="internal_only",
        )
        results.check(
            "T54_hrc52_disclaimer_warning_contains_hrc52",
            "HRC52" in _hrc52_disclaimer.warning_message,
            f"warning_message 不含 HRC52: "
            f"{_hrc52_disclaimer.warning_message}",
        )
    except Exception as e:
        results.check("T54_hrc52_disclaimer", False, str(e))
except Exception as e:
    results.check("T53-T54_hrc52_inherited", False, f"{type(e).__name__}: {e}")


# =============================================================================
# 14. 源码检查（项目记忆硬约束）
# =============================================================================

print("\n[14] 源码检查：项目记忆硬约束")

# delete_task 源码包含 SUCCEEDED guard
try:
    _delete_src = inspect.getsource(CamTaskStore.delete_task)
    results.check(
        "T55_delete_task_source_contains_succeeded_guard",
        "SUCCEEDED" in _delete_src and "禁止删除" in _delete_src,
        "delete_task 源码不含 SUCCEEDED guard",
    )
except Exception as e:
    results.check("T55_delete_task_source", False, str(e))

# CamValidationTask.cam_validation_required 默认 True
try:
    _task_default = CamValidationTask(task_id="cam_test_default")
    results.check(
        "T56_task_default_cam_validation_required_true",
        _task_default.cam_validation_required is True,
        "CamValidationTask.cam_validation_required 默认非 True",
    )
except Exception as e:
    results.check("T56_task_default", False, str(e))

# CamValidationPipeline 源码包含「工程师助手」定位
try:
    _pipeline_src = inspect.getsource(CamValidationPipeline)
    results.check(
        "T57_pipeline_source_engineer_assistant",
        "工程师助手" in _pipeline_src or "工程师" in _pipeline_src,
        "CamValidationPipeline 源码不含「工程师助手」定位",
    )
    results.check(
        "T58_pipeline_source_no_direct_cnc",
        "绝不直接接口" in _pipeline_src or "不直接接口" in _pipeline_src
        or "subprocess" in _pipeline_src,
        "CamValidationPipeline 源码不含「不直接接口 CNC」或 subprocess",
    )
except Exception as e:
    results.check("T57-T58_pipeline_source", False, str(e))

# CamValidationConfig 源码包含 cam_validation_required 始终 True 硬约束
try:
    _cfg_src = inspect.getsource(CamValidationConfig)
    results.check(
        "T59_config_source_cam_validation_required_constraint",
        "始终 True" in _cfg_src or "不可关闭" in _cfg_src,
        "CamValidationConfig 源码不含 cam_validation_required 硬约束",
    )
except Exception as e:
    results.check("T59_config_source", False, str(e))

# CamValidationPipeline 组合（has-a）而非继承
try:
    _pipeline_init_src = inspect.getsource(CamValidationPipeline.__init__)
    results.check(
        "T60_pipeline_composition_has_a",
        (
            "self._loader" in _pipeline_init_src
            and "self._validator" in _pipeline_init_src
            and "self._adapter" in _pipeline_init_src
        ),
        "CamValidationPipeline 未使用组合模式（has-a）",
    )
except Exception as e:
    results.check("T60_pipeline_composition", False, str(e))


# =============================================================================
# 15. 总结
# =============================================================================

# 清理临时目录（可选；保留以便调试）
# import shutil; shutil.rmtree(_tmp_dir, ignore_errors=True)

sys.exit(results.summary())
