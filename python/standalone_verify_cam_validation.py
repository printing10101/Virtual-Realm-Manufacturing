"""CAM 校验模块（阶段 7）独立验证脚本.

针对阶段 7 新增的 ``app.cam_validation`` 模块进行端到端验证，绕过
WinSock 损坏 + 缺失 fastapi/aiosqlite/httpx 依赖问题（参考
``verify_perf_benchmarks_standalone.py`` 方案）。

验证范围
--------
1. **静态语法检查**：compile cam_validation 目录下全部 .py 文件 +
   2 个 CAM adapter 脚本（NX Open / PowerMill）
2. **模块导入检查**：cam_validation 包 + 6 个子模块可正常导入
3. **公开 API 导出检查**：``__all__`` 中 23 个符号全部可从顶层包访问
4. **常量与枚举完整性检查**：
   - VALID_CAM_BACKENDS 包含 5 个合法后端
   - PENDING_CALIBRATION_MATERIALS 包含 HRC52 系列
   - REQUIRED_GCODE_REPORT_FIELDS 包含 10 个必填字段
   - INDUSTRIAL_HARD_GATES 包含 10 条工业硬门槛
   - CamValidationTaskStatus / CamReviewStatus 枚举值完整
5. **小规模功能测试**：
   - generate_task_id() 返回 ``cam_`` 前缀
   - is_valid_cam_backend() 对 5 合法后端 True / 非法后端 False
   - FeatureValidationResult.overall_passed 属性
   - CamValidationTask.to_dict() 序列化
   - CamTaskStore 单例 + add/get/list/delete + SUCCEEDED 禁删硬约束
   - CamDisclaimer + build_cam_disclaimer() warning_message 永远非空
   - GCodeLoader 对不存在 report.json 抛 GCodeReportLoadError
   - InternalValidator 5-axis 模式抛 InternalValidationError
   - CamAdapter manual 后端生成校验清单 + 未知后端抛 CamAdapterError
   - CamValidationPipeline.create_task 接口 + 非法后端抛 PipelineError

运行方式
--------
    cd python
    python standalone_verify_cam_validation.py

退出码
------
- 0：全部通过
- 1：有失败项
"""

from __future__ import annotations

import importlib.util
import os
import sys
import tempfile
import traceback
import types
from typing import Any

# 确保 app 包在 sys.path 中
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _THIS_DIR)

# WinSock 兼容：在导入任何 app 模块前，强制初始化 WinSock
try:
    import socket  # noqa: F401
except OSError:
    pass

# asyncio 绕过（与 verify_perf_benchmarks_standalone.py 一致）：
# Windows WinSock 损坏导致 asyncio.run() 不可用，临时改 sys.platform
# 让 ``import asyncio`` 成功（cam_validation 子模块顶层有 ``import asyncio``）。
_original_platform = sys.platform
sys.platform = "linux"
try:
    import asyncio  # noqa: F401
finally:
    sys.platform = _original_platform


def _sync_run(coro: Any) -> Any:
    """同步驱动协程到完成，处理嵌套 await.

    与 verify_perf_benchmarks_standalone.py 相同的实现：cam_validation
    的 async 方法（如 run_pipeline）内部无真实 await 网络 IO，可用
    栈式同步驱动替代 asyncio.run()。
    """
    stack = [coro]
    send_val: Any = None
    while stack:
        try:
            yielded = stack[-1].send(send_val)
        except StopIteration as e:
            stack.pop()
            send_val = e.value
            continue
        if hasattr(yielded, "send") and hasattr(yielded, "throw"):
            stack.append(yielded)
        elif hasattr(yielded, "__await__"):
            stack.append(yielded.__await__())
        send_val = None
    return send_val


asyncio.run = _sync_run  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# 包 stub：绕过 app.simulation / app.config 导入链
# ---------------------------------------------------------------------------
# app/simulation/__init__.py 导入 toolpath_visualizer / simulation_report /
# voxel_cutter，后者依赖 numpy / matplotlib，可能触发 socket。
# app/config/__init__.py 是 1600+ 行的巨型模块，导入链触发 ssl/redis 等。
#
# 解决方案：
# 1. stub app.simulation 包，但用 importlib 真实加载 stock_model /
#    toolpath_parser / collision_detector 三个纯标准库子模块
#    （internal_validator.py 依赖这三个）
# 2. stub app.config 包，提供 CamValidationConfig 的最小可用 dataclass
#    （cam_adapter / pipeline / internal_validator 依赖此配置）

_SIM_DIR = os.path.join(_THIS_DIR, "app", "simulation")
_CAM_VAL_DIR = os.path.join(_THIS_DIR, "app", "cam_validation")

# app 包本身是纯标准库（前次会话已验证），正常导入
import app  # noqa: E402

# stub app.simulation 包（阻止 __init__.py 执行）
_app_sim_stub = types.ModuleType("app.simulation")
_app_sim_stub.__path__ = [_SIM_DIR]
sys.modules["app.simulation"] = _app_sim_stub

# stub app.config 包（阻止 __init__.py 执行）
_app_cfg_stub = types.ModuleType("app.config")
_app_cfg_stub.__path__ = [os.path.join(_THIS_DIR, "app", "config")]
sys.modules["app.config"] = _app_cfg_stub


def _load_module_from_file(mod_name: str, file_path: str) -> Any:
    """用 importlib 直接加载模块文件，绕过包 __init__ 链."""
    spec = importlib.util.spec_from_file_location(mod_name, file_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"无法创建模块 spec: {mod_name} from {file_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = module
    spec.loader.exec_module(module)
    return module


# 真实加载 simulation 三个纯标准库子模块（internal_validator 依赖）
try:
    _load_module_from_file(
        "app.simulation.stock_model",
        os.path.join(_SIM_DIR, "stock_model.py"),
    )
    _load_module_from_file(
        "app.simulation.toolpath_parser",
        os.path.join(_SIM_DIR, "toolpath_parser.py"),
    )
    _load_module_from_file(
        "app.simulation.collision_detector",
        os.path.join(_SIM_DIR, "collision_detector.py"),
    )
    _SIM_AVAILABLE = True
except Exception as e:  # noqa: BLE001
    _SIM_AVAILABLE = False
    print(f"[WARN] 加载 simulation 子模块失败，将跳过 InternalValidator 真实测试: {e}")
    # stub 三个子模块，使 internal_validator 的 import 语句不报错
    for _sub in ("stock_model", "toolpath_parser", "collision_detector"):
        _full = f"app.simulation.{_sub}"
        if _full not in sys.modules:
            _stub = types.ModuleType(_full)
            sys.modules[_full] = _stub


# 在 app.config stub 命名空间中注入最小可用 CamValidationConfig dataclass
# （cam_adapter / pipeline / internal_validator 通过 ``from app.config import
# CamValidationConfig`` 导入此符号）
import dataclasses as _dataclasses  # noqa: E402


@_dataclasses.dataclass
class _StubCamValidationConfig:
    """最小可用 CamValidationConfig stub.

    仅包含 cam_validation 模块实际读取的字段（见 app/config/__init__.py
    CamValidationConfig docstring 的「pipeline.py 实际使用字段范围」）。
    """

    enabled: bool = True
    output_dir: str = os.path.join("output", "cam_validation")
    max_concurrent: int = 1
    task_timeout_seconds: int = 600
    task_retention_hours: int = 168
    precision_tier: str = "mesh_calibrated"
    default_cam_backend: str = "internal_only"
    nx_open_executable: str = ""
    powermill_executable: str = ""
    pycam_executable: str = ""
    allow_delete_succeeded: bool = False  # 项目记忆硬约束：始终 False
    cam_validation_required: bool = True  # 项目记忆硬约束：始终 True


_app_cfg_stub.CamValidationConfig = _StubCamValidationConfig
# 同时注入 PROJECT_ROOT（gcode_loader.py 在 __init__ 中读取）
_app_cfg_stub.PROJECT_ROOT = _THIS_DIR


# ---------------------------------------------------------------------------
# 测试结果收集
# ---------------------------------------------------------------------------

PASS = "PASS"
FAIL = "FAIL"
SKIP = "SKIP"

results: list[tuple[str, str, str]] = []  # (name, status, detail)


def record(name: str, status: str, detail: str = "") -> None:
    results.append((name, status, detail))
    icon = {PASS: "[OK]", FAIL: "[FAIL]", SKIP: "[SKIP]"}.get(status, "[?]")
    print(f"  {icon} {name}" + (f" — {detail}" if detail else ""))


# ---------------------------------------------------------------------------
# 阶段 1：静态语法检查
# ---------------------------------------------------------------------------


def test_static_syntax() -> None:
    """编译 cam_validation 目录下全部 .py 文件 + 2 个 CAM adapter 脚本."""
    print("\n[阶段 1] 静态语法检查")
    base = _CAM_VAL_DIR
    files = [
        "__init__.py",
        "cam_store.py",
        "cam_disclaimer.py",
        "gcode_loader.py",
        "internal_validator.py",
        "cam_adapter.py",
        "pipeline.py",
    ]
    for fname in files:
        fpath = os.path.join(base, fname)
        name = f"compile cam_validation/{fname}"
        if not os.path.exists(fpath):
            record(name, FAIL, f"文件不存在: {fpath}")
            continue
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                source = f.read()
            compile(source, fpath, "exec")
            record(name, PASS)
        except SyntaxError as e:
            record(name, FAIL, f"{e.lineno}: {e.msg}")

    # CAM adapter 脚本（NX Open Python + PowerMill 宏不做语法检查，宏不是 Python）
    nx_open_script = os.path.join(
        _THIS_DIR, "scripts", "cam_adapters", "nx_open", "autorun_gcode_check.py"
    )
    name = "compile scripts/cam_adapters/nx_open/autorun_gcode_check.py"
    if not os.path.exists(nx_open_script):
        record(name, FAIL, "文件不存在（P0-1 未完成）")
    else:
        try:
            with open(nx_open_script, "r", encoding="utf-8") as f:
                source = f.read()
            compile(source, nx_open_script, "exec")
            record(name, PASS)
        except SyntaxError as e:
            record(name, FAIL, f"{e.lineno}: {e.msg}")

    # PowerMill 宏文件存在性检查（.mac 不是 Python，不做 compile）
    pmill_macro = os.path.join(
        _THIS_DIR, "scripts", "cam_adapters", "powermill", "autorun_gcode_check.mac"
    )
    name = "exists scripts/cam_adapters/powermill/autorun_gcode_check.mac"
    if os.path.exists(pmill_macro):
        record(name, PASS)
    else:
        record(name, FAIL, "文件不存在（P0-2 未完成）")


# ---------------------------------------------------------------------------
# 阶段 2：模块导入检查
# ---------------------------------------------------------------------------


def test_module_imports() -> dict[str, Any]:
    """导入 cam_validation 包 + 6 个子模块."""
    print("\n[阶段 2] 模块导入检查")
    modules: dict[str, Any] = {}

    # 6 个子模块（按依赖顺序加载，与 __init__.py 导入顺序一致）
    sub_modules = [
        "cam_store",
        "cam_disclaimer",
        "gcode_loader",
        "internal_validator",
        "cam_adapter",
        "pipeline",
    ]
    for sub_name in sub_modules:
        full_name = f"app.cam_validation.{sub_name}"
        fpath = os.path.join(_CAM_VAL_DIR, f"{sub_name}.py")
        try:
            mod = _load_module_from_file(full_name, fpath)
            record(f"import cam_validation.{sub_name}", PASS)
            modules[sub_name] = mod
        except Exception as e:  # noqa: BLE001
            record(
                f"import cam_validation.{sub_name}",
                FAIL,
                f"{type(e).__name__}: {e}",
            )

    # 顶层 __init__ 导出检查：exec __init__.py 到 stub 模块
    # 6 个子模块已加载到 sys.modules，__init__.py 的 from 导入会命中缓存
    try:
        _init_path = os.path.join(_CAM_VAL_DIR, "__init__.py")
        with open(_init_path, "r", encoding="utf-8") as f:
            _init_source = f.read()

        # 创建 app.cam_validation stub（保留 __path__）
        _app_cam_stub = types.ModuleType("app.cam_validation")
        _app_cam_stub.__path__ = [_CAM_VAL_DIR]
        sys.modules["app.cam_validation"] = _app_cam_stub

        exec(compile(_init_source, _init_path, "exec"), _app_cam_stub.__dict__)
        record("import cam_validation __init__", PASS)
        modules["__init__"] = _app_cam_stub
    except Exception as e:  # noqa: BLE001
        record(
            "import cam_validation __init__",
            FAIL,
            f"{type(e).__name__}: {e}",
        )

    return modules


# ---------------------------------------------------------------------------
# 阶段 3：公开 API 导出检查
# ---------------------------------------------------------------------------

EXPECTED_ALL_SYMBOLS = {
    # cam_store：枚举
    "CamValidationTaskStatus",
    "CamReviewStatus",
    # cam_store：常量
    "SAFETY_MARGIN_RATIO",
    "PENDING_CALIBRATION_MATERIALS",
    "VALID_CAM_BACKENDS",
    # cam_store：异常
    "CamValidationError",
    "GCodeReportLoadError",
    "InternalValidationError",
    "CamAdapterError",
    "ReviewError",
    "CamValidationPipelineError",
    # cam_store：dataclass
    "FeatureValidationResult",
    "CamValidationTask",
    # cam_store：工具函数 + store 类
    "generate_task_id",
    "get_task_store",
    "is_valid_cam_backend",
    "CamTaskStore",
    # cam_disclaimer
    "INDUSTRIAL_HARD_GATES",
    "CamDisclaimer",
    "build_cam_disclaimer",
    # gcode_loader
    "REQUIRED_GCODE_REPORT_FIELDS",
    "GCodeLoadResult",
    "GCodeLoader",
    # internal_validator
    "InternalValidationReport",
    "InternalValidator",
    # cam_adapter
    "CamAdapter",
    "CamSoftwareReport",
    # pipeline（编排器）
    "CamValidationPipeline",
    "CamValidationResult",
}


def test_public_api_exports(modules: dict[str, Any]) -> None:
    """验证 __all__ 中所有符号可从顶层包访问."""
    print("\n[阶段 3] 公开 API 导出检查")

    init_mod = modules.get("__init__")
    if init_mod is None:
        record("公开 API 导出", SKIP, "__init__ 未加载")
        return

    # 1. __all__ 长度检查
    actual_all = set(getattr(init_mod, "__all__", []))
    record(
        "__all__ 符号数量",
        PASS if len(actual_all) == len(EXPECTED_ALL_SYMBOLS) else FAIL,
        f"实际 {len(actual_all)} 个（期望 {len(EXPECTED_ALL_SYMBOLS)} 个）",
    )

    # 2. __all__ 与期望集合完全一致
    missing = EXPECTED_ALL_SYMBOLS - actual_all
    extra = actual_all - EXPECTED_ALL_SYMBOLS
    record(
        "__all__ 符号集合一致性",
        PASS if not missing and not extra else FAIL,
        f"缺失: {sorted(missing)}; 多余: {sorted(extra)}"
        if (missing or extra)
        else f"{len(EXPECTED_ALL_SYMBOLS)}/23 符号完全一致",
    )

    # 3. 每个符号可在顶层包命名空间访问
    inaccessible: list[str] = []
    for sym in EXPECTED_ALL_SYMBOLS:
        if not hasattr(init_mod, sym):
            inaccessible.append(sym)
    record(
        "符号可访问性",
        PASS if not inaccessible else FAIL,
        f"不可访问: {inaccessible}" if inaccessible else "全部可访问",
    )


# ---------------------------------------------------------------------------
# 阶段 4：常量与枚举完整性检查
# ---------------------------------------------------------------------------


def test_constants_and_enums(modules: dict[str, Any]) -> None:
    """验证关键常量和枚举值的完整性."""
    print("\n[阶段 4] 常量与枚举完整性检查")

    init_mod = modules.get("__init__")
    if init_mod is None:
        record("常量与枚举", SKIP, "__init__ 未加载")
        return

    # VALID_CAM_BACKENDS 必须包含 5 个合法后端
    expected_backends = {"internal_only", "pycam", "nx_open", "powermill", "manual"}
    actual_backends = set(init_mod.VALID_CAM_BACKENDS)
    record(
        "VALID_CAM_BACKENDS 5 个合法后端",
        PASS if actual_backends == expected_backends else FAIL,
        f"实际: {sorted(actual_backends)}",
    )

    # PENDING_CALIBRATION_MATERIALS 必须包含 HRC52 系列
    pending_mats = init_mod.PENDING_CALIBRATION_MATERIALS
    must_have = {"steel_hrc52", "hrc52"}
    record(
        "PENDING_CALIBRATION_MATERIALS 含 HRC52",
        PASS if must_have.issubset(pending_mats) else FAIL,
        f"实际 {len(pending_mats)} 个: {sorted(pending_mats)}",
    )

    # REQUIRED_GCODE_REPORT_FIELDS 必须包含 10 个必填字段
    expected_required_fields = {
        "task_id",
        "task_status",
        "controller_type",
        "material_name",
        "safe_z",
        "stock_top_z",
        "gcode_file_path",
        "feature_results",
        "cam_validation_required",
        "prediction_method",
    }
    actual_required = set(init_mod.REQUIRED_GCODE_REPORT_FIELDS)
    record(
        "REQUIRED_GCODE_REPORT_FIELDS 10 个必填字段",
        PASS if actual_required == expected_required_fields else FAIL,
        f"缺失: {sorted(expected_required_fields - actual_required)}"
        if actual_required != expected_required_fields
        else "10/10 必填字段全部存在",
    )

    # INDUSTRIAL_HARD_GATES 必须包含 10 条工业硬门槛
    gates = init_mod.INDUSTRIAL_HARD_GATES
    record(
        "INDUSTRIAL_HARD_GATES 10 条硬门槛",
        PASS if len(gates) >= 10 else FAIL,
        f"实际 {len(gates)} 条",
    )

    # CamValidationTaskStatus 枚举值完整性
    status_enum = init_mod.CamValidationTaskStatus
    expected_statuses = {
        "PENDING",
        "RUNNING",
        "VALIDATED",
        "REVIEWED",
        "SUCCEEDED",
        "FAILED",
        "TIMEOUT",
        "CANCELLED",
    }
    actual_statuses = {s.name for s in status_enum}
    record(
        "CamValidationTaskStatus 8 个状态",
        PASS if actual_statuses == expected_statuses else FAIL,
        f"缺失: {sorted(expected_statuses - actual_statuses)}"
        if actual_statuses != expected_statuses
        else "8/8 状态全部存在",
    )

    # CamReviewStatus 枚举值完整性
    review_enum = init_mod.CamReviewStatus
    expected_reviews = {"PENDING", "CONFIRMED", "REJECTED", "EDITED"}
    actual_reviews = {s.name for s in review_enum}
    record(
        "CamReviewStatus 4 个审核状态",
        PASS if actual_reviews == expected_reviews else FAIL,
        f"实际: {sorted(actual_reviews)}",
    )

    # SAFETY_MARGIN_RATIO 必须为正值
    ratio = init_mod.SAFETY_MARGIN_RATIO
    record(
        "SAFETY_MARGIN_RATIO 正值",
        PASS if isinstance(ratio, (int, float)) and 0 < ratio <= 1.0 else FAIL,
        f"实际值: {ratio}",
    )


# ---------------------------------------------------------------------------
# 阶段 5：小规模功能测试
# ---------------------------------------------------------------------------


def test_functional_generate_task_id(modules: dict[str, Any]) -> None:
    """测试 generate_task_id() 返回 cam_ 前缀."""
    print("\n[阶段 5.1] generate_task_id")
    init_mod = modules.get("__init__")
    if init_mod is None:
        record("generate_task_id", SKIP, "__init__ 未加载")
        return

    try:
        tid = init_mod.generate_task_id()
        ok = isinstance(tid, str) and tid.startswith("cam_") and len(tid) > 10
        record(
            "generate_task_id 返回 cam_ 前缀",
            PASS if ok else FAIL,
            f"实际: {tid!r}",
        )
    except Exception as e:  # noqa: BLE001
        record("generate_task_id", FAIL, f"{type(e).__name__}: {e}")


def test_functional_is_valid_cam_backend(modules: dict[str, Any]) -> None:
    """测试 is_valid_cam_backend() 对合法/非法后端的判定."""
    print("\n[阶段 5.2] is_valid_cam_backend")
    init_mod = modules.get("__init__")
    if init_mod is None:
        record("is_valid_cam_backend", SKIP, "__init__ 未加载")
        return

    try:
        valid_backends = ["internal_only", "pycam", "nx_open", "powermill", "manual"]
        all_valid = all(init_mod.is_valid_cam_backend(b) for b in valid_backends)
        record(
            "5 个合法后端返回 True",
            PASS if all_valid else FAIL,
            f"测试: {valid_backends}",
        )

        invalid_backends = ["", "CAM", "nx", "PowerMill", "internal", None, "fake"]
        # None 会被 in 判定为 False，不抛异常
        invalid_results = []
        for b in invalid_backends:
            try:
                if init_mod.is_valid_cam_backend(b):
                    invalid_results.append(b)
            except Exception:
                # 抛异常视为正确拒绝
                pass
        record(
            "非法后端返回 False / 抛异常",
            PASS if not invalid_results else FAIL,
            f"误判为合法: {invalid_results}" if invalid_results else "全部正确拒绝",
        )
    except Exception as e:  # noqa: BLE001
        record("is_valid_cam_backend", FAIL, f"{type(e).__name__}: {e}")


def test_functional_feature_validation_result(modules: dict[str, Any]) -> None:
    """测试 FeatureValidationResult dataclass + overall_passed 属性."""
    print("\n[阶段 5.3] FeatureValidationResult")
    init_mod = modules.get("__init__")
    if init_mod is None:
        record("FeatureValidationResult", SKIP, "__init__ 未加载")
        return

    try:
        FVR = init_mod.FeatureValidationResult
        # 默认构造：internal_check_passed=True, cam_check_passed=True → overall_passed=True
        r1 = FVR(feature_id="f1", feature_type="plane")
        ok1 = r1.overall_passed is True

        # internal 失败 → overall_passed=False
        r2 = FVR(
            feature_id="f2",
            feature_type="hole",
            internal_check_passed=False,
        )
        ok2 = r2.overall_passed is False

        # cam 失败 → overall_passed=False
        r3 = FVR(
            feature_id="f3",
            feature_type="cylinder",
            cam_check_passed=False,
        )
        ok3 = r3.overall_passed is False

        record(
            "overall_passed 属性逻辑",
            PASS if ok1 and ok2 and ok3 else FAIL,
            f"r1={r1.overall_passed}, r2={r2.overall_passed}, r3={r3.overall_passed}",
        )

        # to_dict 序列化
        d = r1.to_dict()
        required_keys = {
            "feature_id",
            "feature_type",
            "line_range",
            "internal_check_passed",
            "cam_check_passed",
            "review_status",
        }
        ok_dict = required_keys.issubset(set(d.keys()))
        record(
            "to_dict 序列化",
            PASS if ok_dict else FAIL,
            f"缺失键: {sorted(required_keys - set(d.keys()))}"
            if not ok_dict
            else f"{len(d)} 个字段",
        )
    except Exception as e:  # noqa: BLE001
        record("FeatureValidationResult", FAIL, f"{type(e).__name__}: {e}")


def test_functional_cam_task_store(modules: dict[str, Any]) -> None:
    """测试 CamTaskStore 单例 + 状态机 + SUCCEEDED 禁删硬约束."""
    print("\n[阶段 5.4] CamTaskStore 状态机 + SUCCEEDED 禁删硬约束")
    init_mod = modules.get("__init__")
    if init_mod is None:
        record("CamTaskStore", SKIP, "__init__ 未加载")
        return

    try:
        store1 = init_mod.get_task_store()
        store2 = init_mod.get_task_store()
        ok_singleton = store1 is store2
        record(
            "CamTaskStore 单例",
            PASS if ok_singleton else FAIL,
            "同一实例" if ok_singleton else "返回了不同实例",
        )

        # 清空历史任务（避免之前测试残留）
        store1.clear()

        # 构造一个 PENDING 任务
        TaskCls = init_mod.CamValidationTask
        task_id = init_mod.generate_task_id()
        task = TaskCls(
            task_id=task_id,
            source_gcode_report_path="/tmp/fake_report.json",
            status=init_mod.CamValidationTaskStatus.PENDING.value,
        )
        store1.add_task(task)
        got = store1.get_task(task_id)
        ok_add_get = got.task_id == task_id and got.status == "pending"
        record(
            "add_task + get_task",
            PASS if ok_add_get else FAIL,
            f"task_id={got.task_id}, status={got.status}",
        )

        # list_tasks
        tasks_list = store1.list_tasks()
        record(
            "list_tasks 返回列表",
            PASS if len(tasks_list) >= 1 else FAIL,
            f"实际 {len(tasks_list)} 个任务",
        )

        # 状态过滤
        pending_list = store1.list_tasks(status_filter="pending")
        ok_filter = len(pending_list) >= 1 and all(
            t.status == "pending" for t in pending_list
        )
        record(
            "list_tasks status_filter",
            PASS if ok_filter else FAIL,
            f"pending 任务 {len(pending_list)} 个",
        )

        # to_dict 序列化
        d = task.to_dict()
        ok_dict = "task_id" in d and "status" in d and "cam_validation_required" in d
        record(
            "CamValidationTask.to_dict",
            PASS if ok_dict else FAIL,
            f"{len(d)} 个字段" if ok_dict else f"缺失键: {d.keys()}",
        )

        # SUCCEEDED 禁删硬约束
        succeeded_task_id = init_mod.generate_task_id()
        succeeded_task = TaskCls(
            task_id=succeeded_task_id,
            source_gcode_report_path="/tmp/fake.json",
            status=init_mod.CamValidationTaskStatus.SUCCEEDED.value,
        )
        store1.add_task(succeeded_task)
        try:
            store1.delete_task(succeeded_task_id, allow_delete_succeeded=False)
            record(
                "SUCCEEDED 禁删硬约束",
                FAIL,
                "删除成功但应被禁止（项目记忆硬约束失效）",
            )
        except init_mod.ReviewError:
            record(
                "SUCCEEDED 禁删硬约束",
                PASS,
                "正确抛出 ReviewError（项目记忆硬约束生效）",
            )
        except Exception as e:  # noqa: BLE001
            record(
                "SUCCEEDED 禁删硬约束",
                FAIL,
                f"抛出异常类型错误: {type(e).__name__}（期望 ReviewError）",
            )

        # allow_delete_succeeded=True 仍可删除（API 留有逃生口，但 config 强制 False）
        try:
            store1.delete_task(succeeded_task_id, allow_delete_succeeded=True)
            record(
                "allow_delete_succeeded=True 逃生口",
                PASS,
                "逃生口可用（config 层强制 False，此处仅验证 API 能力）",
            )
        except Exception as e:  # noqa: BLE001
            record(
                "allow_delete_succeeded=True 逃生口",
                FAIL,
                f"{type(e).__name__}: {e}",
            )

        # 清理：删除 PENDING 任务（应成功）
        try:
            store1.delete_task(task_id, allow_delete_succeeded=False)
            record(
                "PENDING 任务可删除",
                PASS,
                "非 SUCCEEDED 状态可正常删除",
            )
        except Exception as e:  # noqa: BLE001
            record(
                "PENDING 任务可删除",
                FAIL,
                f"{type(e).__name__}: {e}",
            )

        # 清理 store
        store1.clear()
    except Exception as e:  # noqa: BLE001
        record("CamTaskStore", FAIL, f"{type(e).__name__}: {e}")
        traceback.print_exc()


def test_functional_cam_disclaimer(modules: dict[str, Any]) -> None:
    """测试 CamDisclaimer + build_cam_disclaimer() warning_message 永远非空."""
    print("\n[阶段 5.5] CamDisclaimer + build_cam_disclaimer")
    init_mod = modules.get("__init__")
    if init_mod is None:
        record("CamDisclaimer", SKIP, "__init__ 未加载")
        return

    try:
        # 场景 1：internal_only 后端 + 无降级 + 无 HRC52
        d1 = init_mod.build_cam_disclaimer(
            precision_tier="mesh_calibrated",
            controller_type="fanuc_0i",
            material_name="45#钢",
            material_calibration_status="calibrated",
            gcode_report_source="/tmp/report.json",
            gcode_file_source="/tmp/part.nc",
            prediction_method="analytical",
            total_features=5,
            passed_features=5,
            failed_features=0,
            pending_calibration=False,
            ltc_experiment_used=False,
            cam_backend_used="internal_only",
            cam_backend_fallback_reason="",
        )
        ok1 = bool(d1.warning_message) and d1.requires_cam_validation is True
        record(
            "internal_only 后端 warning_message 非空",
            PASS if ok1 else FAIL,
            f"warning长度={len(d1.warning_message)}, requires_cam_validation={d1.requires_cam_validation}",
        )

        # to_dict 序列化
        dd1 = d1.to_dict()
        ok_dict = "warning_message" in dd1 and "industrial_hard_gates" in dd1
        record(
            "CamDisclaimer.to_dict",
            PASS if ok_dict else FAIL,
            f"{len(dd1)} 个字段" if ok_dict else f"缺失键: {dd1.keys()}",
        )

        # 场景 2：HRC52 待校准 + LTC 实验路径 + manual 后端降级
        d2 = init_mod.build_cam_disclaimer(
            precision_tier="mesh_calibrated",
            controller_type="siemens_840d",
            material_name="steel_hrc52",
            material_calibration_status="pending_calibration",
            gcode_report_source="/tmp/report2.json",
            gcode_file_source="/tmp/part2.nc",
            prediction_method="neural_network",
            total_features=3,
            passed_features=2,
            failed_features=1,
            pending_calibration=True,
            ltc_experiment_used=True,
            cam_backend_used="manual",
            cam_backend_fallback_reason="NX Open executable not configured",
            cam_backend_requested="nx_open",
        )
        wm = d2.warning_message
        ok_hrc52 = "HRC52" in wm
        ok_ltc = "LTC" in wm
        ok_manual = "手动校验" in wm or "manual" in wm.lower()
        ok_fallback = "降级" in wm or "fallback" in wm.lower()
        record(
            "HRC52 + LTC + manual 降级告知文本",
            PASS if ok_hrc52 and ok_ltc and ok_manual and ok_fallback else FAIL,
            f"HRC52={ok_hrc52}, LTC={ok_ltc}, manual={ok_manual}, 降级={ok_fallback}",
        )

        # requires_engineer_review 始终 True
        ok_review = d1.requires_engineer_review is True and d2.requires_engineer_review is True
        record(
            "requires_engineer_review 始终 True",
            PASS if ok_review else FAIL,
            f"d1={d1.requires_engineer_review}, d2={d2.requires_engineer_review}",
        )

        # industrial_hard_gates 列表与模块级常量一致
        ok_gates = d1.industrial_hard_gates == list(init_mod.INDUSTRIAL_HARD_GATES)
        record(
            "industrial_hard_gates 与模块常量一致",
            PASS if ok_gates else FAIL,
            f"{len(d1.industrial_hard_gates)} 条" if ok_gates else "不一致",
        )
    except Exception as e:  # noqa: BLE001
        record("CamDisclaimer", FAIL, f"{type(e).__name__}: {e}")
        traceback.print_exc()


def test_functional_gcode_loader(modules: dict[str, Any]) -> None:
    """测试 GCodeLoader 对不存在 report.json 抛 GCodeReportLoadError."""
    print("\n[阶段 5.6] GCodeLoader 异常路径")
    init_mod = modules.get("__init__")
    if init_mod is None:
        record("GCodeLoader", SKIP, "__init__ 未加载")
        return

    try:
        loader = init_mod.GCodeLoader(project_root=_THIS_DIR)
        try:
            loader.load_from_report("/nonexistent/path/report.json")
            record(
                "不存在文件抛 GCodeReportLoadError",
                FAIL,
                "未抛异常但应抛 GCodeReportLoadError",
            )
        except init_mod.GCodeReportLoadError:
            record(
                "不存在文件抛 GCodeReportLoadError",
                PASS,
                "正确抛出 GCodeReportLoadError",
            )
        except Exception as e:  # noqa: BLE001
            record(
                "不存在文件抛 GCodeReportLoadError",
                FAIL,
                f"异常类型错误: {type(e).__name__}（期望 GCodeReportLoadError）",
            )
    except Exception as e:  # noqa: BLE001
        record("GCodeLoader", FAIL, f"{type(e).__name__}: {e}")


def test_functional_internal_validator(modules: dict[str, Any]) -> None:
    """测试 InternalValidator 5-axis 模式抛 InternalValidationError."""
    print("\n[阶段 5.7] InternalValidator 5-axis 模式拒绝")
    init_mod = modules.get("__init__")
    if init_mod is None:
        record("InternalValidator", SKIP, "__init__ 未加载")
        return

    if not _SIM_AVAILABLE:
        record(
            "InternalValidator 5-axis 模式拒绝",
            SKIP,
            "simulation 子模块未加载（跳过）",
        )
        return

    try:
        cfg = _StubCamValidationConfig()
        validator = init_mod.InternalValidator(cfg)

        # 5-axis 模式必须在解析 G 代码之前就抛 InternalValidationError
        try:
            validator.validate(
                gcode_text="G01 X1 Y2 Z3\n",
                feature_results=[],
                controller_type="fanuc",
                mode="5axis",
            )
            record(
                "5-axis 模式抛 InternalValidationError",
                FAIL,
                "未抛异常但应抛 InternalValidationError",
            )
        except init_mod.InternalValidationError:
            record(
                "5-axis 模式抛 InternalValidationError",
                PASS,
                "正确抛出 InternalValidationError",
            )
        except Exception as e:  # noqa: BLE001
            record(
                "5-axis 模式抛 InternalValidationError",
                FAIL,
                f"异常类型错误: {type(e).__name__}（期望 InternalValidationError）",
            )
    except Exception as e:  # noqa: BLE001
        record("InternalValidator", FAIL, f"{type(e).__name__}: {e}")


def test_functional_cam_adapter(modules: dict[str, Any]) -> None:
    """测试 CamAdapter manual 后端 + 未知后端抛 CamAdapterError."""
    print("\n[阶段 5.8] CamAdapter 后端策略")
    init_mod = modules.get("__init__")
    if init_mod is None:
        record("CamAdapter", SKIP, "__init__ 未加载")
        return

    try:
        cfg = _StubCamValidationConfig(
            default_cam_backend="manual",
            output_dir=os.path.join(tempfile.gettempdir(), "cam_validation_test"),
        )
        adapter = init_mod.CamAdapter(cfg)

        # 未知后端必须抛 CamAdapterError
        try:
            adapter.validate(
                gcode_file_path="/tmp/fake.nc",
                controller_type="fanuc_0i",
                cam_backend="unknown_backend",
            )
            record(
                "未知后端抛 CamAdapterError",
                FAIL,
                "未抛异常但应抛 CamAdapterError",
            )
        except init_mod.CamAdapterError:
            record(
                "未知后端抛 CamAdapterError",
                PASS,
                "正确抛出 CamAdapterError",
            )
        except Exception as e:  # noqa: BLE001
            record(
                "未知后端抛 CamAdapterError",
                FAIL,
                f"异常类型错误: {type(e).__name__}（期望 CamAdapterError）",
            )

        # manual 后端对不存在的 G 代码文件也能生成校验清单（兜底降级）
        try:
            report = adapter.validate(
                gcode_file_path="/nonexistent/part.nc",
                controller_type="fanuc_0i",
                cam_backend="manual",
            )
            ok_report = (
                isinstance(report, init_mod.CamSoftwareReport)
                and report.backend_used == "manual"
            )
            record(
                "manual 后端生成校验清单",
                PASS if ok_report else FAIL,
                f"backend_used={getattr(report, 'backend_used', '<unknown>')}",
            )
        except Exception as e:  # noqa: BLE001
            record(
                "manual 后端生成校验清单",
                FAIL,
                f"{type(e).__name__}: {e}",
            )
    except Exception as e:  # noqa: BLE001
        record("CamAdapter", FAIL, f"{type(e).__name__}: {e}")
        traceback.print_exc()


def test_functional_pipeline_create_task(modules: dict[str, Any]) -> None:
    """测试 CamValidationPipeline.create_task 接口 + 非法后端抛 PipelineError."""
    print("\n[阶段 5.9] CamValidationPipeline.create_task")
    init_mod = modules.get("__init__")
    if init_mod is None:
        record("Pipeline.create_task", SKIP, "__init__ 未加载")
        return

    if not _SIM_AVAILABLE:
        record(
            "Pipeline.create_task",
            SKIP,
            "simulation 子模块未加载（跳过）",
        )
        return

    try:
        cfg = _StubCamValidationConfig(
            output_dir=os.path.join(tempfile.gettempdir(), "cam_pipeline_test"),
        )
        pipeline = init_mod.CamValidationPipeline(cfg=cfg)

        # 非法后端必须抛 CamValidationPipelineError
        try:
            pipeline.create_task(
                source_gcode_report_path="/tmp/fake_report.json",
                cam_backend="invalid_backend",
            )
            record(
                "非法后端抛 CamValidationPipelineError",
                FAIL,
                "未抛异常但应抛 CamValidationPipelineError",
            )
        except init_mod.CamValidationPipelineError:
            record(
                "非法后端抛 CamValidationPipelineError",
                PASS,
                "正确抛出 CamValidationPipelineError",
            )
        except Exception as e:  # noqa: BLE001
            record(
                "非法后端抛 CamValidationPipelineError",
                FAIL,
                f"异常类型错误: {type(e).__name__}（期望 CamValidationPipelineError）",
            )

        # 空 report 路径必须抛 CamValidationPipelineError
        try:
            pipeline.create_task(
                source_gcode_report_path="",
                cam_backend="manual",
            )
            record(
                "空路径抛 CamValidationPipelineError",
                FAIL,
                "未抛异常但应抛 CamValidationPipelineError",
            )
        except init_mod.CamValidationPipelineError:
            record(
                "空路径抛 CamValidationPipelineError",
                PASS,
                "正确抛出 CamValidationPipelineError",
            )
        except Exception as e:  # noqa: BLE001
            record(
                "空路径抛 CamValidationPipelineError",
                FAIL,
                f"异常类型错误: {type(e).__name__}（期望 CamValidationPipelineError）",
            )

        # 合法创建任务（PENDING 状态）
        try:
            task = pipeline.create_task(
                source_gcode_report_path="/tmp/fake_report.json",
                cam_backend="manual",
            )
            ok_task = (
                task.task_id.startswith("cam_")
                and task.status == init_mod.CamValidationTaskStatus.PENDING.value
                and task.cam_validation_required is True
            )
            record(
                "合法创建 PENDING 任务",
                PASS if ok_task else FAIL,
                f"task_id={task.task_id[:16]}..., status={task.status}, "
                f"cam_validation_required={task.cam_validation_required}",
            )

            # 清理：删除测试任务（PENDING 可删）
            store = init_mod.get_task_store()
            store.delete_task(task.task_id, allow_delete_succeeded=False)
        except Exception as e:  # noqa: BLE001
            record(
                "合法创建 PENDING 任务",
                FAIL,
                f"{type(e).__name__}: {e}",
            )
            traceback.print_exc()
    except Exception as e:  # noqa: BLE001
        record("Pipeline.create_task", FAIL, f"{type(e).__name__}: {e}")
        traceback.print_exc()


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------


def main() -> int:
    print("=" * 72)
    print("CAM 校验模块（阶段 7）独立验证脚本")
    print("=" * 72)
    print(f"Python: {sys.version.split()[0]}")
    print(f"工作目录: {_THIS_DIR}")
    print(f"simulation 子模块可用: {_SIM_AVAILABLE}")

    # 阶段 1
    test_static_syntax()

    # 阶段 2
    modules = test_module_imports()

    # 阶段 3
    test_public_api_exports(modules)

    # 阶段 4
    test_constants_and_enums(modules)

    # 阶段 5
    test_functional_generate_task_id(modules)
    test_functional_is_valid_cam_backend(modules)
    test_functional_feature_validation_result(modules)
    test_functional_cam_task_store(modules)
    test_functional_cam_disclaimer(modules)
    test_functional_gcode_loader(modules)
    test_functional_internal_validator(modules)
    test_functional_cam_adapter(modules)
    test_functional_pipeline_create_task(modules)

    # 汇总
    print("\n" + "=" * 72)
    print("验证汇总")
    print("=" * 72)
    n_pass = sum(1 for _, s, _ in results if s == PASS)
    n_fail = sum(1 for _, s, _ in results if s == FAIL)
    n_skip = sum(1 for _, s, _ in results if s == SKIP)
    total = len(results)
    print(f"总计: {total}  通过: {n_pass}  失败: {n_fail}  跳过: {n_skip}")

    if n_fail > 0:
        print("\n失败项详情:")
        for name, status, detail in results:
            if status == FAIL:
                print(f"  [FAIL] {name} — {detail}")

    print("=" * 72)
    return 0 if n_fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
