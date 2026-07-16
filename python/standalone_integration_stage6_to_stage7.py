"""阶段 6 → 阶段 7 端到端联调脚本原型（P1-2）.

将真实阶段 6 产物（gc_*.report.json + gc_*.nc）作为输入，调用
``CamValidationPipeline`` 四步链（create_task → run_pipeline →
review_task → confirm_task），生成 cam_report.json + internal_report.json，
并校验最终产物的字段完整性。

本脚本与 ``standalone_verify_cam_validation.py`` 共享同一套环境 hack：
    - WinSock 绕过：临时改 sys.platform 让 ``import asyncio`` 成功
    - ``_sync_run`` 替代 ``asyncio.run()``：cam_validation 内部 async
      方法无真实网络 IO，可用栈式同步驱动
    - app.simulation / app.config 包 stub：绕过 numpy/matplotlib/redis
      等重依赖导入链
    - 真实加载 simulation 三个纯标准库子模块（stock_model /
      toolpath_parser / collision_detector）

运行方式
--------
    cd python
    python standalone_integration_stage6_to_stage7.py

退出码
------
- 0：联调成功，cam_report.json 字段完整性校验全部通过
- 1：联调失败（含字段完整性校验失败）
"""

from __future__ import annotations

import importlib.util
import json
import os
import sys
import time
import traceback
import types
from typing import Any

# =============================================================================
# 路径 + WinSock + asyncio 兼容 hack（与 standalone_verify_cam_validation.py 一致）
# =============================================================================

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _THIS_DIR)

# WinSock 兼容：在导入任何 app 模块前，强制初始化 WinSock
try:
    import socket  # noqa: F401
except OSError:
    pass

# asyncio 绕过：Windows WinSock 损坏导致 asyncio.run() 不可用
_original_platform = sys.platform
sys.platform = "linux"
try:
    import asyncio  # noqa: F401
finally:
    sys.platform = _original_platform


def _sync_run(coro: Any) -> Any:
    """同步驱动协程到完成，处理嵌套 await.

    与 standalone_verify_cam_validation.py 相同的实现：cam_validation
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


# =============================================================================
# 包 stub：绕过 app.simulation / app.config 导入链
# =============================================================================

_SIM_DIR = os.path.join(_THIS_DIR, "app", "simulation")
_CAM_VAL_DIR = os.path.join(_THIS_DIR, "app", "cam_validation")

import app  # noqa: E402

# stub app.simulation 包（阻止 __init__.py 执行，避免 numpy/matplotlib 依赖）
_app_sim_stub = types.ModuleType("app.simulation")
_app_sim_stub.__path__ = [_SIM_DIR]
sys.modules["app.simulation"] = _app_sim_stub

# stub app.config 包（阻止 __init__.py 执行，避免 redis/ssl 依赖）
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
except Exception as e:  # noqa: BLE001
    print(f"[FATAL] 加载 simulation 子模块失败，无法继续联调: {e}")
    traceback.print_exc()
    sys.exit(1)


# 注入最小可用 CamValidationConfig stub
import dataclasses as _dataclasses  # noqa: E402


@_dataclasses.dataclass
class _StubCamValidationConfig:
    """最小可用 CamValidationConfig stub（与验证脚本一致）."""

    enabled: bool = True
    output_dir: str = os.path.join("outputs", "cam_validation")
    max_concurrent: int = 1
    task_timeout_seconds: int = 600
    task_retention_hours: int = 168
    precision_tier: str = "mesh_calibrated"
    default_cam_backend: str = "internal_only"
    nx_open_executable: str = ""
    powermill_executable: str = ""
    pycam_executable: str = ""
    allow_delete_succeeded: bool = False
    cam_validation_required: bool = True


_app_cfg_stub.CamValidationConfig = _StubCamValidationConfig
_app_cfg_stub.PROJECT_ROOT = _THIS_DIR


# =============================================================================
# 加载 cam_validation 子模块
# =============================================================================

_SUB_MODULES = [
    "cam_store",
    "cam_disclaimer",
    "gcode_loader",
    "internal_validator",
    "cam_adapter",
    "pipeline",
]
_loaded: dict[str, Any] = {}
for _sub_name in _SUB_MODULES:
    _full_name = f"app.cam_validation.{_sub_name}"
    _fpath = os.path.join(_CAM_VAL_DIR, f"{_sub_name}.py")
    try:
        _loaded[_sub_name] = _load_module_from_file(_full_name, _fpath)
    except Exception as e:  # noqa: BLE001
        print(f"[FATAL] 加载 cam_validation.{_sub_name} 失败: {e}")
        traceback.print_exc()
        sys.exit(1)

cam_store_mod = _loaded["cam_store"]
pipeline_mod = _loaded["pipeline"]
cam_adapter_mod = _loaded["cam_adapter"]
gcode_loader_mod = _loaded["gcode_loader"]

CamValidationPipeline = pipeline_mod.CamValidationPipeline
CamValidationResult = pipeline_mod.CamValidationResult
CamValidationTask = cam_store_mod.CamValidationTask
CamValidationTaskStatus = cam_store_mod.CamValidationTaskStatus
CamReviewStatus = cam_store_mod.CamReviewStatus
FeatureValidationResult = cam_store_mod.FeatureValidationResult
CamSoftwareReport = cam_adapter_mod.CamSoftwareReport


# =============================================================================
# 测试结果收集
# =============================================================================

PASS = "PASS"
FAIL = "FAIL"
results: list[tuple[str, str, str]] = []


def record(name: str, status: str, detail: str = "") -> None:
    results.append((name, status, detail))
    icon = {PASS: "[OK]", FAIL: "[FAIL]"}.get(status, "[?]")
    print(f"  {icon} {name}" + (f" — {detail}" if detail else ""))


# =============================================================================
# 联调主流程
# =============================================================================

# 真实阶段 6 产物输入
_GCODE_TASK_ID = "gc_625e7706-4909-4d55-b625-58ee25f32f5b"
_GCODE_REPORT_PATH = os.path.join(
    _THIS_DIR, "outputs", "gcode", _GCODE_TASK_ID, f"{_GCODE_TASK_ID}.report.json"
)
_GCODE_FILE_PATH = os.path.join(
    _THIS_DIR, "outputs", "gcode", _GCODE_TASK_ID, f"{_GCODE_TASK_ID}.nc"
)


def step_0_check_inputs() -> bool:
    """步骤 0：检查阶段 6 产物文件存在 + 字段完整性."""
    print("\n[步骤 0] 检查阶段 6 产物输入")
    ok = True

    if os.path.exists(_GCODE_REPORT_PATH):
        record("阶段 6 report.json 存在", PASS, _GCODE_REPORT_PATH)
    else:
        record("阶段 6 report.json 存在", FAIL, f"找不到: {_GCODE_REPORT_PATH}")
        ok = False

    if os.path.exists(_GCODE_FILE_PATH):
        record("阶段 6 .nc G 代码文件存在", PASS, _GCODE_FILE_PATH)
    else:
        record("阶段 6 .nc G 代码文件存在", FAIL, f"找不到: {_GCODE_FILE_PATH}")
        ok = False

    if not ok:
        return False

    # 校验 report.json 必填字段（REQUIRED_GCODE_REPORT_FIELDS）
    try:
        with open(_GCODE_REPORT_PATH, "r", encoding="utf-8") as f:
            report_data = json.load(f)
    except Exception as e:  # noqa: BLE001
        record("加载 report.json", FAIL, f"{type(e).__name__}: {e}")
        return False

    required = gcode_loader_mod.REQUIRED_GCODE_REPORT_FIELDS
    missing = [f for f in required if f not in report_data]
    record(
        "REQUIRED_GCODE_REPORT_FIELDS 完整性",
        PASS if not missing else FAIL,
        f"缺失: {missing}" if missing else f"{len(required)} 字段全部存在",
    )
    if missing:
        ok = False

    # 关键字段值打印
    record(
        "report.json 关键字段",
        PASS,
        f"task_id={report_data.get('task_id')} "
        f"controller={report_data.get('controller_type')} "
        f"material={report_data.get('material_name')} "
        f"features={report_data.get('total_features')}",
    )

    return ok


def step_1_create_task(cfg: Any) -> tuple[bool, Any, str]:
    """步骤 1：create_task → PENDING 任务."""
    print("\n[步骤 1] create_task（PENDING）")
    pipeline = CamValidationPipeline(cfg=cfg)

    try:
        task = pipeline.create_task(
            source_gcode_report_path=_GCODE_REPORT_PATH,
            source_gcode_file_path=_GCODE_FILE_PATH,
            controller_type="fanuc_0i",
            material_name="45#钢",
            safe_z=80.0,
            stock_top_z=50.0,
            cam_backend="internal_only",
        )
    except Exception as e:  # noqa: BLE001
        record("create_task", FAIL, f"{type(e).__name__}: {e}")
        traceback.print_exc()
        return False, None, ""

    ok_task = (
        isinstance(task, CamValidationTask)
        and task.task_id.startswith("cam_")
        and task.status == CamValidationTaskStatus.PENDING.value
        and task.cam_validation_required is True
        and task.cam_backend_requested == "internal_only"
    )
    record(
        "create_task 返回 PENDING 任务",
        PASS if ok_task else FAIL,
        f"task_id={task.task_id} status={task.status} "
        f"cam_backend_requested={task.cam_backend_requested}",
    )

    return ok_task, pipeline, task.task_id


def step_2_run_pipeline(pipeline: Any, task_id: str) -> tuple[bool, Any]:
    """步骤 2：run_pipeline → VALIDATED."""
    print("\n[步骤 2] run_pipeline（PENDING → RUNNING → VALIDATED）")
    t0 = time.time()
    try:
        result = _sync_run(pipeline.run_pipeline(task_id))
    except Exception as e:  # noqa: BLE001
        record("run_pipeline", FAIL, f"{type(e).__name__}: {e}")
        traceback.print_exc()
        return False, None
    elapsed_ms = int((time.time() - t0) * 1000)

    if not isinstance(result, CamValidationResult):
        record("run_pipeline 返回 CamValidationResult", FAIL, f"实际类型: {type(result)}")
        return False, None

    # 检查任务状态
    task = pipeline.get_task(task_id)
    ok_status = task.status == CamValidationTaskStatus.VALIDATED.value
    record(
        "任务状态转为 VALIDATED",
        PASS if ok_status else FAIL,
        f"status={task.status} elapsed={elapsed_ms}ms",
    )

    # 检查特征校验结果
    ok_features = (
        task.total_features == 2
        and len(task.feature_validation_results) == 2
        and all(
            isinstance(r, FeatureValidationResult)
            for r in task.feature_validation_results
        )
    )
    record(
        "feature_validation_results 数量",
        PASS if ok_features else FAIL,
        f"total_features={task.total_features} "
        f"passed={task.passed_features} failed={task.failed_features} "
        f"backend_used={result.cam_backend_used}",
    )

    # 检查 internal_only 后端未触发真实 CAM 调用（CamSoftwareReport.status=skipped）
    ok_backend = result.cam_backend_used == "internal_only"
    record(
        "internal_only 后端生效",
        PASS if ok_backend else FAIL,
        f"cam_backend_used={result.cam_backend_used} "
        f"fallback_reason={result.cam_backend_fallback_reason}",
    )

    # 检查 feature_validation_results 字段填充
    sample = task.feature_validation_results[0]
    ok_fields = (
        bool(sample.feature_id)
        and sample.review_status == CamReviewStatus.PENDING.value
        and isinstance(sample.cam_check_passed, bool)
        and isinstance(sample.internal_check_passed, bool)
    )
    record(
        "FeatureValidationResult 字段填充",
        PASS if ok_fields else FAIL,
        f"feature_id={sample.feature_id} review_status={sample.review_status} "
        f"internal_passed={sample.internal_check_passed} "
        f"cam_passed={sample.cam_check_passed}",
    )

    return ok_status and ok_features and ok_backend and ok_fields, result


def step_3_review_features(pipeline: Any, task_id: str) -> bool:
    """步骤 3：review_task 逐个特征审核 → REVIEWED."""
    print("\n[步骤 3] review_task（VALIDATED → REVIEWED）")
    task = pipeline.get_task(task_id)
    feature_ids = [r.feature_id for r in task.feature_validation_results]
    record("待审核特征列表", PASS, f"{feature_ids}")

    all_ok = True
    for fid in feature_ids:
        try:
            reviewed = pipeline.review_task(
                task_id=task_id,
                feature_id=fid,
                review_status=CamReviewStatus.CONFIRMED.value,
                reviewed_by="engineer_zhang",
                engineer_notes=f"联调脚本自动确认特征 {fid}",
            )
        except Exception as e:  # noqa: BLE001
            record(f"review_task({fid})", FAIL, f"{type(e).__name__}: {e}")
            traceback.print_exc()
            all_ok = False
            continue

        ok = (
            isinstance(reviewed, FeatureValidationResult)
            and reviewed.review_status == CamReviewStatus.CONFIRMED.value
        )
        record(
            f"review_task({fid}) → confirmed",
            PASS if ok else FAIL,
            f"feature_id={reviewed.feature_id} status={reviewed.review_status}",
        )
        if not ok:
            all_ok = False

    # 检查任务整体状态转为 REVIEWED
    task = pipeline.get_task(task_id)
    ok_reviewed = task.status == CamValidationTaskStatus.REVIEWED.value
    record(
        "任务状态转为 REVIEWED",
        PASS if ok_reviewed else FAIL,
        f"status={task.status} reviewed_by={task.reviewed_by}",
    )

    return all_ok and ok_reviewed


def step_4_confirm_task(pipeline: Any, task_id: str) -> tuple[bool, Any]:
    """步骤 4：confirm_task → SUCCEEDED + 导出双 JSON."""
    print("\n[步骤 4] confirm_task（REVIEWED → SUCCEEDED + 导出双 JSON）")
    try:
        # confirm_task 是同步方法（非 async），直接调用，无需 _sync_run
        result = pipeline.confirm_task(task_id, reviewer="engineer_zhang")
    except Exception as e:  # noqa: BLE001
        record("confirm_task", FAIL, f"{type(e).__name__}: {e}")
        traceback.print_exc()
        return False, None

    if not isinstance(result, CamValidationResult):
        record("confirm_task 返回 CamValidationResult", FAIL, f"实际类型: {type(result)}")
        return False, None

    task = pipeline.get_task(task_id)
    ok_status = task.status == CamValidationTaskStatus.SUCCEEDED.value
    record(
        "任务状态转为 SUCCEEDED",
        PASS if ok_status else FAIL,
        f"status={task.status}",
    )

    ok_cam_report = (
        result.cam_report_path is not None
        and os.path.exists(result.cam_report_path)
    )
    record(
        "cam_report.json 导出",
        PASS if ok_cam_report else FAIL,
        f"cam_report_path={result.cam_report_path}",
    )

    ok_internal_report = (
        result.internal_report_path is not None
        and os.path.exists(result.internal_report_path)
    )
    record(
        "internal_report.json 导出",
        PASS if ok_internal_report else FAIL,
        f"internal_report_path={result.internal_report_path}",
    )

    return ok_status and ok_cam_report and ok_internal_report, result


def step_5_verify_cam_report(result: Any) -> bool:
    """步骤 5：校验 cam_report.json 字段完整性."""
    print("\n[步骤 5] cam_report.json 字段完整性校验")
    if result.cam_report_path is None or not os.path.exists(result.cam_report_path):
        record("读取 cam_report.json", FAIL, "文件不存在")
        return False

    try:
        with open(result.cam_report_path, "r", encoding="utf-8") as f:
            cam_report = json.load(f)
    except Exception as e:  # noqa: BLE001
        record("解析 cam_report.json", FAIL, f"{type(e).__name__}: {e}")
        return False
    record("解析 cam_report.json", PASS, f"顶层键数={len(cam_report)}")

    # 必填字段（链路最终产物核心字段）
    # 实际字段名以 cam_validation/pipeline.py 的 _export_cam_report 为准：
    #   - source_gcode_file_path（非 gcode_file_path）
    #   - feature_validation_results（非 feature_results）
    #   - industrial_hard_gates_note（顶层字符串，非 disclaimer.warning_message）
    required_top = {
        "task_id",
        "task_status",
        "controller_type",
        "material_name",
        "safe_z",
        "stock_top_z",
        "source_gcode_file_path",
        "feature_validation_results",
        "cam_validation_required",
        "prediction_method",
        "cam_backend_used",
        "industrial_hard_gates_note",
    }
    missing = required_top - set(cam_report.keys())
    record(
        "cam_report 顶层必填字段",
        PASS if not missing else FAIL,
        f"缺失: {sorted(missing)}" if missing else f"{len(required_top)} 字段全部存在",
    )

    # cam_validation_required 硬约束：必须为 True
    ok_hard = cam_report.get("cam_validation_required") is True
    record(
        "cam_validation_required 硬约束",
        PASS if ok_hard else FAIL,
        f"实际值: {cam_report.get('cam_validation_required')}",
    )

    # task_status 必须为 succeeded
    ok_status = cam_report.get("task_status") == "succeeded"
    record(
        "task_status=succeeded",
        PASS if ok_status else FAIL,
        f"实际值: {cam_report.get('task_status')}",
    )

    # feature_validation_results 必须为 list 且数量与阶段 6 一致（2 个）
    fr = cam_report.get("feature_validation_results")
    ok_fr = isinstance(fr, list) and len(fr) == 2
    record(
        "feature_validation_results 数量=2",
        PASS if ok_fr else FAIL,
        f"实际: {len(fr) if isinstance(fr, list) else type(fr).__name__}",
    )

    # 每个特征必须含 feature_id + review_status + cam_check_passed
    ok_feat_fields = True
    for r in fr if isinstance(fr, list) else []:
        if not all(
            k in r for k in ("feature_id", "review_status", "cam_check_passed")
        ):
            ok_feat_fields = False
            break
    record(
        "feature_validation_results[*] 含 feature_id/review_status/cam_check_passed",
        PASS if ok_feat_fields else FAIL,
    )

    # industrial_hard_gates_note 必须存在且非空（工业硬门槛告知）
    hard_gates_note = cam_report.get("industrial_hard_gates_note", "")
    ok_note = isinstance(hard_gates_note, str) and bool(hard_gates_note)
    record(
        "industrial_hard_gates_note 非空",
        PASS if ok_note else FAIL,
        f"长度={len(hard_gates_note) if isinstance(hard_gates_note, str) else 0}",
    )

    # 工业硬门槛告知必须含「CNC 控制器」相关字样
    ok_cnc_note = "CNC" in hard_gates_note or "控制器" in hard_gates_note
    record(
        "industrial_hard_gates_note 含 CNC 控制器边界告知",
        PASS if ok_cnc_note else FAIL,
    )

    # cam_software_report 嵌套对象字段完整性（internal_only 模式）
    cam_sw = cam_report.get("cam_software_report", {})
    ok_cam_sw = (
        isinstance(cam_sw, dict)
        and cam_sw.get("backend_used") == "internal_only"
        and cam_sw.get("status") == "skipped"
        and isinstance(cam_sw.get("messages"), list)
        and len(cam_sw["messages"]) > 0
    )
    record(
        "cam_software_report.internal_only 跳过告知",
        PASS if ok_cam_sw else FAIL,
        f"backend_used={cam_sw.get('backend_used') if isinstance(cam_sw, dict) else None} "
        f"status={cam_sw.get('status') if isinstance(cam_sw, dict) else None}",
    )

    return (
        not missing
        and ok_hard
        and ok_status
        and ok_fr
        and ok_feat_fields
        and ok_note
        and ok_cnc_note
        and ok_cam_sw
    )


def step_6_verify_internal_report(result: Any) -> bool:
    """步骤 6：校验 internal_report.json 字段完整性（调试细节）."""
    print("\n[步骤 6] internal_report.json 字段完整性校验")
    if result.internal_report_path is None or not os.path.exists(
        result.internal_report_path
    ):
        record("读取 internal_report.json", FAIL, "文件不存在")
        return False

    try:
        with open(result.internal_report_path, "r", encoding="utf-8") as f:
            internal_report = json.load(f)
    except Exception as e:  # noqa: BLE001
        record("解析 internal_report.json", FAIL, f"{type(e).__name__}: {e}")
        return False
    record("解析 internal_report.json", PASS, f"顶层键数={len(internal_report)}")

    # internal_report 实际字段（以 _export_internal_report 为准）：
    #   task_id / exported_at / reviewer / controller_type / safe_z / stock_top_z /
    #   stock_dimensions / mode / total_segments / segments_checked /
    #   unattributed_events / all_internal_events / feature_results / warnings / debug_note
    # 注意：internal_report 不含 task_status（与 cam_report 不同）
    expected_keys = {"task_id", "feature_results", "controller_type", "mode"}
    missing = expected_keys - set(internal_report.keys())
    record(
        "internal_report 必填字段",
        PASS if not missing else FAIL,
        f"缺失: {sorted(missing)}" if missing else f"{len(expected_keys)} 字段全部存在",
    )

    # feature_results 数量与阶段 6 一致（2 个）
    fr = internal_report.get("feature_results")
    ok_fr = isinstance(fr, list) and len(fr) == 2
    record(
        "internal_report.feature_results 数量=2",
        PASS if ok_fr else FAIL,
        f"实际: {len(fr) if isinstance(fr, list) else type(fr).__name__}",
    )

    # debug_note 必须存在（说明 internal_report 的调试定位）
    ok_debug = isinstance(internal_report.get("debug_note"), str)
    record(
        "internal_report.debug_note 存在",
        PASS if ok_debug else FAIL,
    )

    return not missing and ok_fr and ok_debug


def step_7_verify_succeeded_no_delete(pipeline: Any, task_id: str) -> bool:
    """步骤 7：SUCCEEDED 禁删硬约束（项目记忆）."""
    print("\n[步骤 7] SUCCEEDED 禁删硬约束校验")
    try:
        pipeline.delete_task(task_id)
        record("SUCCEEDED 任务禁止删除", FAIL, "delete_task 未抛异常")
        return False
    except Exception as e:  # noqa: BLE001
        ok = "succeeded" in str(e).lower() or "禁止" in str(e) or "不允许" in str(e)
        record(
            "SUCCEEDED 任务禁止删除",
            PASS if ok else FAIL,
            f"抛出异常: {type(e).__name__}: {e}",
        )
        return ok


# =============================================================================
# 主入口
# =============================================================================


def main() -> int:
    print("=" * 72)
    print("阶段 6 → 阶段 7 端到端联调脚本原型（P1-2）")
    print("=" * 72)
    print(f"输入阶段 6 产物 task_id: {_GCODE_TASK_ID}")
    print(f"G 代码 report.json: {_GCODE_REPORT_PATH}")
    print(f"G 代码 .nc 文件:    {_GCODE_FILE_PATH}")

    cfg = _StubCamValidationConfig(
        output_dir=os.path.join(_THIS_DIR, "outputs", "cam_validation"),
    )

    # 步骤 0：检查输入
    if not step_0_check_inputs():
        print("\n[ABORT] 阶段 6 产物输入检查失败，终止联调")
        return 1

    # 步骤 1：create_task
    ok1, pipeline, task_id = step_1_create_task(cfg)
    if not ok1:
        print("\n[ABORT] create_task 失败，终止联调")
        return 1

    # 步骤 2：run_pipeline
    ok2, result = step_2_run_pipeline(pipeline, task_id)
    if not ok2:
        print("\n[ABORT] run_pipeline 失败，终止联调")
        return 1

    # 步骤 3：review_task
    ok3 = step_3_review_features(pipeline, task_id)
    if not ok3:
        print("\n[ABORT] review_task 失败，终止联调")
        return 1

    # 步骤 4：confirm_task
    ok4, result = step_4_confirm_task(pipeline, task_id)
    if not ok4:
        print("\n[ABORT] confirm_task 失败，终止联调")
        return 1

    # 步骤 5：cam_report.json 字段完整性
    ok5 = step_5_verify_cam_report(result)

    # 步骤 6：internal_report.json 字段完整性
    ok6 = step_6_verify_internal_report(result)

    # 步骤 7：SUCCEEDED 禁删硬约束
    ok7 = step_7_verify_succeeded_no_delete(pipeline, task_id)

    # 汇总
    print("\n" + "=" * 72)
    print("联调结果汇总")
    print("=" * 72)
    passed = sum(1 for _, s, _ in results if s == PASS)
    failed = sum(1 for _, s, _ in results if s == FAIL)
    for name, status, detail in results:
        icon = {PASS: "[OK]", FAIL: "[FAIL]"}.get(status, "[?]")
        print(f"  {icon} {name}" + (f" — {detail}" if detail else ""))
    print(f"\n总计: {passed} 通过 / {failed} 失败")

    if failed > 0:
        print("\n[FAIL] 阶段 6 → 阶段 7 端到端联调存在失败项")
        return 1

    print("\n[OK] 阶段 6 → 阶段 7 端到端联调全部通过")
    print(f"  任务 ID: {task_id}")
    print(f"  cam_report.json: {result.cam_report_path}")
    print(f"  internal_report.json: {result.internal_report_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
