"""pipeline.py 端到端验证脚本（阶段 6 s6-8v）。

测试链路：
    构造阶段 5 ChatterReport JSON + 阶段 3 OperationPlan JSON
    → GCodeGenerationPipeline.create_task() 创建 PENDING 任务
    → run_pipeline() 异步执行 PENDING → RUNNING → GENERATED（或 FAILED）
    → review_feature() 工程师审核 GENERATED → REVIEWED
    → confirm_task() REVIEWED → SUCCEEDED + 导出 G 代码文件 + 审核 JSON
    → export_gcode() 获取文件路径
    → delete_task() SUCCEEDED 禁删硬约束

覆盖 22 项断言（22/22 通过即视为验证通过）：
    1.  create_task 正常创建 PENDING 任务（task_id 前缀 "gc_"）
    2.  create_task 空路径 → GCodeGenerationPipelineError
    3.  run_pipeline 正常流程 → GENERATED
    4.  run_pipeline 含 unstable 特征 → FAILED
    5.  run_pipeline ChatterReport 不存在 → FAILED
    6.  run_pipeline 任务不存在 → GCodeGenerationPipelineError
    7.  run_pipeline 状态不允许执行 → GCodeGenerationPipelineError
    8.  review_feature confirmed → REVIEWED
    9.  review_feature edited 修改切深 + 备注
    10. review_feature 非 GENERATED 状态 → GCodeReviewError
    11. review_feature 无效审核状态 → GCodeReviewError
    12. review_feature edited 无 edited_params → GCodeReviewError
    13. review_feature 未知 feature_id → GCodeReviewError
    14. confirm_task 正常流程 → SUCCEEDED + 导出文件
    15. confirm_task 非 REVIEWED → GCodeGenerationPipelineError
    16. confirm_task 全部 rejected → GCodeReviewError
    17. export_gcode 获取文件路径
    18. export_gcode 非 SUCCEEDED → GCodeGenerationPipelineError
    19. delete_task SUCCEEDED 禁删硬约束
    20. delete_task PENDING 可删
    21. disclaimer cam_validation_required 始终 True
    22. disclaimer prediction_method 继承阶段 5
"""

from __future__ import annotations

# === WinSock 损坏绕过补丁（复制自 run_pytest.py，必须在 import asyncio 之前执行）===
# 本机 _overlapped 模块因系统级 WinSock 损坏无法导入（WinError 10038），
# 导致 asyncio.windows_events → _overlapped 导入链失败。
# 此外，socket.socketpair() 也会失败，导致 SelectorEventLoop._make_self_pipe() 崩溃。
# 此处注入 _overlapped 空实现 + 用 os.pipe() 替代 socket.socketpair()。
import sys as _sys
import types as _types
import os as _os

try:
    import _overlapped  # noqa: F401
except OSError:
    _patch = _types.ModuleType("_overlapped")
    _patch.Overlapped = type("Overlapped", (), {})
    _sys.modules["_overlapped"] = _patch
    print("[warn] _overlapped 模块加载失败，已注入空实现绕过 WinSock 损坏。")

# _asyncio 兜底
try:
    import _asyncio  # noqa: F401
except OSError:
    _asyncio_patch = _types.ModuleType("_asyncio")
    _sys.modules["_asyncio"] = _asyncio_patch

# 现在 asyncio 可以安全导入
import asyncio  # noqa: E402

# 强制使用 SelectorEventLoop（ProactorEventLoop 依赖 _overlapped 完整实现）
if _sys.platform == "win32":
    try:
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    except Exception:
        pass

# === socket.socketpair mock（WinSock 损坏环境下必需）===
# SelectorEventLoop._make_self_pipe() 调用 socket.socketpair() 创建自管道，
# 但 WinSock 损坏会导致 socket() 失败。self-pipe 是单向通信，用 os.pipe() 可替代。
import socket as _socket_module


class _PipeSocket:
    """用 os.pipe() 模拟 socketpair 的一端。"""

    def __init__(self, fd: int, *, is_reader: bool) -> None:
        self._fd = fd
        self._is_reader = is_reader
        self._closed = False

    def fileno(self) -> int:
        return self._fd

    def setblocking(self, flag: bool) -> None:  # noqa: ARG002
        pass

    def settimeout(self, timeout) -> None:  # noqa: ARG002
        pass

    def recv(self, bufsize: int) -> bytes:
        if self._closed:
            raise OSError("socket closed")
        return _os.read(self._fd, bufsize)

    def send(self, data: bytes) -> int:
        if self._closed:
            raise OSError("socket closed")
        return _os.write(self._fd, data)

    def close(self) -> None:
        if not self._closed:
            try:
                _os.close(self._fd)
            except OSError:
                pass
            self._closed = True


def _mock_socketpair(*args, **kwargs):  # noqa: ARG001
    r_fd, w_fd = _os.pipe()
    return _PipeSocket(r_fd, is_reader=True), _PipeSocket(w_fd, is_reader=False)


# 探测真实 socketpair 是否可用；不可用则注入 mock
try:
    _probe_s, _probe_c = _socket_module.socketpair()
    _probe_s.close()
    _probe_c.close()
except OSError as _probe_err:
    _socket_module.socketpair = _mock_socketpair
    print(f"[warn] socket.socketpair() 探测失败 ({_probe_err!s})，已注入 os.pipe() 替代实现。")


# === Fake Selector 绕过 select.select() 调用 ===
# WinSock 损坏环境下，select.select() 也会失败（WinError 10038）。
# 由于 pipeline.run_pipeline() 是 async 但无 await 语句，
# 事件循环的 selector 永远不会被真正使用——只需要返回空就绪列表即可。
import selectors as _selectors
import select as _select_module


def _patch_select():
    """patch select.select()，在所有 fd 都不是真实 socket 时返回空列表。"""
    _real_select = _select_module.select

    def _safe_select(rlist, wlist, xlist, timeout=None):
        # 若三个列表都为空，直接返回
        if not rlist and not wlist and not xlist:
            return ([], [], [])
        # 否则尝试真实 select；失败时返回空列表（绕过 WinSock 损坏）
        try:
            return _real_select(rlist, wlist, xlist, timeout)
        except OSError:
            return ([], [], [])

    # 仅 patch select 模块的 select 函数
    # 注意：不要 patch selectors.select，否则会覆盖 selectors.py 顶层 `import select`
    # 后绑定的 select 名字（指向 select 模块），导致 `select.select(...)` 调用失败。
    _select_module.select = _safe_select
    print("[warn] select.select() 已被 patch 为安全版本。")


# 仅在真实 select.select() 不可用时注入
try:
    _select_module.select([], [], [], 0.001)
except OSError:
    _patch_select()


import json
import sys
import tempfile
from pathlib import Path

# 确保能导入 app 包
sys.path.insert(0, str(Path(__file__).parent))

from app.chatter_prediction.chatter_store import FeatureChatterResult
from app.gcode_generation.gcode_store import (
    GCodeGenerationError,
    GCodeGenerationTaskStatus,
    GCodeReviewStatus,
    TaskStore,
    get_task_store,
)
from app.gcode_generation.pipeline import (
    GCodeGenerationPipeline,
    GCodeGenerationResult,
    GCodeReviewError,
)
from app.process_planning.operation_sequencer import Operation, OperationPlan


# =============================================================================
# 测试工具
# =============================================================================

PASS = 0
FAIL = 0


def check(name: str, condition: bool, detail: str = "") -> None:
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  [PASS] {name}")
    else:
        FAIL += 1
        print(f"  [FAIL] {name} {detail}")


def reset_task_store() -> None:
    """清空 TaskStore 单例（每个测试用例独立运行）。"""
    store = get_task_store()
    store.clear()


# =============================================================================
# 测试数据构造
# =============================================================================


def build_test_operation_plan() -> OperationPlan:
    """构造测试用 OperationPlan（2 个 stable 工序：平面 + 孔）。"""
    operations = [
        Operation(
            seq=1,
            name="OP01-平面A",
            feature_name="face_A",
            machining_method="精铣平面",
            surface="A",
            tolerance_grade="IT7",
            tool_type="立铣刀",
            cutting_params={
                "tool_diameter": 10.0,
                "material": "45#钢",
                "radius_comp": "G41",
            },
            estimated_time_min=3.5,
            notes="精加工",
        ),
        Operation(
            seq=2,
            name="OP02-孔B",
            feature_name="hole_B",
            machining_method="钻孔",
            surface="A",
            tolerance_grade="IT8",
            tool_type="麻花钻",
            cutting_params={
                "tool_diameter": 8.0,
                "material": "45#钢",
                "radius_comp": "G40",
            },
            estimated_time_min=2.0,
            notes="钻孔",
        ),
    ]
    return OperationPlan(
        operations=operations,
        setups=[],
        estimated_time_min=5.5,
        face_change_count=0,
        fixture_recommendations=[],
    )


def build_test_operation_plan_json(tmp_dir: Path) -> str:
    """将 OperationPlan 序列化为 JSON 文件。"""
    plan = build_test_operation_plan()
    plan_dict = plan.to_dict()
    plan_path = tmp_dir / "op_plan.json"
    plan_path.write_text(
        json.dumps(plan_dict, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return str(plan_path)


def build_test_chatter_report_json(
    tmp_dir: Path,
    features: list[FeatureChatterResult] | None = None,
    material_id: str = "steel_45",
    prediction_method: str = "analytical",
    task_status: str = "succeeded",
) -> str:
    """构造阶段 5 ChatterReport JSON 文件。

    必填字段：task_id / task_status / prediction_method / feature_results / material_id
    """
    if features is None:
        features = [
            FeatureChatterResult(
                feature_id="face_A",
                feature_type="plane",
                material_id=material_id,
                spindle_rpm=3000.0,
                axial_depth_mm=2.0,
                limit_depth_mm=5.0,
                stable=True,
                stability_margin=0.4,
                method=prediction_method,
                ltc_active=False,
                confidence=0.9,
            ),
            FeatureChatterResult(
                feature_id="hole_B",
                feature_type="hole",
                material_id=material_id,
                spindle_rpm=2500.0,
                axial_depth_mm=4.5,
                limit_depth_mm=5.0,
                stable=True,
                stability_margin=0.9,
                method=prediction_method,
                ltc_active=False,
                confidence=0.85,
            ),
        ]

    report = {
        "task_id": "ch_test_001",
        "task_status": task_status,
        "prediction_method": prediction_method,
        "material_id": material_id,
        "feature_results": [f.to_dict() for f in features],
    }
    report_path = tmp_dir / "chatter_report.json"
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return str(report_path)


# =============================================================================
# 测试用例
# =============================================================================


def test_create_task_normal(tmp_dir: Path) -> str:
    """测试 1: create_task 正常创建 PENDING 任务。"""
    print("\n=== 测试 1: create_task 正常创建 PENDING 任务 ===")
    reset_task_store()

    chatter_path = build_test_chatter_report_json(tmp_dir)
    op_plan_path = build_test_operation_plan_json(tmp_dir)

    pipeline = GCodeGenerationPipeline()
    task = pipeline.create_task(
        source_chatter_report_path=chatter_path,
        source_operation_plan_path=op_plan_path,
        controller_type="fanuc_0i",
        material_name="45#钢",
    )
    check("task_id 前缀为 gc_", task.task_id.startswith("gc_"),
          f"actual={task.task_id}")
    check("status == pending", task.status == GCodeGenerationTaskStatus.PENDING.value,
          f"actual={task.status}")
    check("controller_type == fanuc_0i", task.controller_type == "fanuc_0i")
    check("material_name == 45#钢", task.material_name == "45#钢")
    check("workspace_dir 非空", bool(task.workspace_dir),
          f"actual={task.workspace_dir}")
    check("workspace_dir 已创建", Path(task.workspace_dir).exists())
    check("source_chatter_report_path 已记录",
          task.source_chatter_report_path == chatter_path)
    check("source_operation_plan_path 已记录",
          task.source_operation_plan_path == op_plan_path)
    return task.task_id


def test_create_task_invalid_input() -> None:
    """测试 2: create_task 空路径 → GCodeGenerationPipelineError。"""
    print("\n=== 测试 2: create_task 空路径 → GCodeGenerationPipelineError ===")
    reset_task_store()

    pipeline = GCodeGenerationPipeline()
    from app.gcode_generation.gcode_store import GCodeGenerationPipelineError

    try:
        pipeline.create_task(
            source_chatter_report_path="",
            source_operation_plan_path="op.json",
        )
        check("空 chatter_report_path 应抛错", False)
    except GCodeGenerationPipelineError:
        check("空 chatter_report_path 正确抛 GCodeGenerationPipelineError", True)

    try:
        pipeline.create_task(
            source_chatter_report_path="report.json",
            source_operation_plan_path="",
        )
        check("空 operation_plan_path 应抛错", False)
    except GCodeGenerationPipelineError:
        check("空 operation_plan_path 正确抛 GCodeGenerationPipelineError", True)


def test_run_pipeline_normal(tmp_dir: Path) -> str:
    """测试 3: run_pipeline 正常流程 → GENERATED。"""
    print("\n=== 测试 3: run_pipeline 正常流程 → GENERATED ===")
    reset_task_store()

    chatter_path = build_test_chatter_report_json(tmp_dir)
    op_plan_path = build_test_operation_plan_json(tmp_dir)

    pipeline = GCodeGenerationPipeline()
    task = pipeline.create_task(
        source_chatter_report_path=chatter_path,
        source_operation_plan_path=op_plan_path,
    )
    result = asyncio.run(pipeline.run_pipeline(task.task_id))

    check("result.task_id 匹配", result.task_id == task.task_id)
    check("result.status == generated",
          result.status == GCodeGenerationTaskStatus.GENERATED.value,
          f"actual={result.status}")
    check("result.total_features == 2", result.total_features == 2,
          f"actual={result.total_features}")
    check("result.stable_features == 2", result.stable_features == 2,
          f"actual={result.stable_features}")
    check("result.unstable_features == 0", result.unstable_features == 0,
          f"actual={result.unstable_features}")
    check("result.pending_calibration == False",
          not result.pending_calibration)
    check("result.prediction_method == analytical",
          result.prediction_method == "analytical",
          f"actual={result.prediction_method}")
    check("result.error_message 为空", not result.error_message)
    check("result.disclaimer 非空", result.disclaimer is not None)
    check("disclaimer.cam_validation_required 始终 True",
          result.disclaimer.requires_cam_validation is True)
    check("gcode_file_path 为空（未确认）", not result.gcode_file_path)
    return task.task_id


def test_run_pipeline_unstable_feature(tmp_dir: Path) -> str:
    """测试 4: run_pipeline 含 unstable 特征 → FAILED。"""
    print("\n=== 测试 4: run_pipeline 含 unstable 特征 → FAILED ===")
    reset_task_store()

    features = [
        FeatureChatterResult(
            feature_id="face_A",
            feature_type="plane",
            material_id="steel_45",
            spindle_rpm=3000.0,
            axial_depth_mm=2.0,
            limit_depth_mm=5.0,
            stable=True,
            stability_margin=0.4,
            method="analytical",
            ltc_active=False,
            confidence=0.9,
        ),
        FeatureChatterResult(
            feature_id="cylinder_C",
            feature_type="cylinder",
            material_id="steel_45",
            spindle_rpm=2000.0,
            axial_depth_mm=6.0,
            limit_depth_mm=5.0,
            stable=False,  # unstable
            stability_margin=1.2,
            method="analytical",
            ltc_active=False,
            confidence=0.8,
        ),
    ]
    chatter_path = build_test_chatter_report_json(
        tmp_dir, features=features
    )
    op_plan_path = build_test_operation_plan_json(tmp_dir)

    pipeline = GCodeGenerationPipeline()
    task = pipeline.create_task(
        source_chatter_report_path=chatter_path,
        source_operation_plan_path=op_plan_path,
    )
    result = asyncio.run(pipeline.run_pipeline(task.task_id))

    check("result.status == failed",
          result.status == GCodeGenerationTaskStatus.FAILED.value,
          f"actual={result.status}")
    check("result.unstable_features == 1",
          result.unstable_features == 1,
          f"actual={result.unstable_features}")
    check("result.error_message 含「不稳定」",
          "不稳定" in (result.error_message or ""),
          f"actual={result.error_message}")
    return task.task_id


def test_run_pipeline_chatter_report_not_exist(tmp_dir: Path) -> str:
    """测试 5: run_pipeline ChatterReport 不存在 → FAILED。"""
    print("\n=== 测试 5: run_pipeline ChatterReport 不存在 → FAILED ===")
    reset_task_store()

    op_plan_path = build_test_operation_plan_json(tmp_dir)

    pipeline = GCodeGenerationPipeline()
    task = pipeline.create_task(
        source_chatter_report_path="/nonexistent/report.json",
        source_operation_plan_path=op_plan_path,
    )
    result = asyncio.run(pipeline.run_pipeline(task.task_id))

    check("result.status == failed",
          result.status == GCodeGenerationTaskStatus.FAILED.value,
          f"actual={result.status}")
    check("result.error_message 非空", bool(result.error_message))
    return task.task_id


def test_run_pipeline_task_not_exist() -> None:
    """测试 6: run_pipeline 任务不存在 → GCodeGenerationPipelineError。"""
    print("\n=== 测试 6: run_pipeline 任务不存在 → GCodeGenerationPipelineError ===")
    reset_task_store()

    from app.gcode_generation.gcode_store import GCodeGenerationPipelineError

    pipeline = GCodeGenerationPipeline()
    try:
        asyncio.run(pipeline.run_pipeline("gc_nonexistent_001"))
        check("任务不存在应抛错", False)
    except GCodeGenerationPipelineError:
        check("任务不存在正确抛 GCodeGenerationPipelineError", True)


def test_run_pipeline_invalid_status(tmp_dir: Path) -> None:
    """测试 7: run_pipeline 状态不允许执行 → GCodeGenerationPipelineError。"""
    print("\n=== 测试 7: run_pipeline 状态不允许执行 → GCodeGenerationPipelineError ===")
    reset_task_store()

    from app.gcode_generation.gcode_store import GCodeGenerationPipelineError

    chatter_path = build_test_chatter_report_json(tmp_dir)
    op_plan_path = build_test_operation_plan_json(tmp_dir)

    pipeline = GCodeGenerationPipeline()
    task = pipeline.create_task(
        source_chatter_report_path=chatter_path,
        source_operation_plan_path=op_plan_path,
    )
    # 先执行一次到 GENERATED
    asyncio.run(pipeline.run_pipeline(task.task_id))
    # 再次执行应失败
    try:
        asyncio.run(pipeline.run_pipeline(task.task_id))
        check("GENERATED 状态再次执行应抛错", False)
    except GCodeGenerationPipelineError as e:
        check("GENERATED 状态再次执行正确抛 GCodeGenerationPipelineError", True,
              f"msg={e}")


def test_review_feature_confirmed(tmp_dir: Path) -> str:
    """测试 8: review_feature confirmed → REVIEWED。"""
    print("\n=== 测试 8: review_feature confirmed → REVIEWED ===")
    reset_task_store()

    chatter_path = build_test_chatter_report_json(tmp_dir)
    op_plan_path = build_test_operation_plan_json(tmp_dir)

    pipeline = GCodeGenerationPipeline()
    task = pipeline.create_task(
        source_chatter_report_path=chatter_path,
        source_operation_plan_path=op_plan_path,
    )
    asyncio.run(pipeline.run_pipeline(task.task_id))

    # 审核 face_A → confirmed
    fr1 = pipeline.review_feature(
        task_id=task.task_id,
        feature_id="face_A",
        review_status=GCodeReviewStatus.CONFIRMED.value,
        reviewed_by="engineer_01",
    )
    check("face_A review_status == confirmed",
          fr1.review_status == GCodeReviewStatus.CONFIRMED.value)

    # 审核 hole_B → confirmed
    fr2 = pipeline.review_feature(
        task_id=task.task_id,
        feature_id="hole_B",
        review_status=GCodeReviewStatus.CONFIRMED.value,
        reviewed_by="engineer_01",
    )
    check("hole_B review_status == confirmed",
          fr2.review_status == GCodeReviewStatus.CONFIRMED.value)

    # 全部审核完毕 → REVIEWED
    task_after = get_task_store().get_task(task.task_id)
    check("task.status == reviewed",
          task_after.status == GCodeGenerationTaskStatus.REVIEWED.value,
          f"actual={task_after.status}")
    check("task.reviewed_by == engineer_01",
          task_after.reviewed_by == "engineer_01")
    return task.task_id


def test_review_feature_edited(tmp_dir: Path) -> None:
    """测试 9: review_feature edited 修改切深 + 备注。"""
    print("\n=== 测试 9: review_feature edited 修改切深 + 备注 ===")
    reset_task_store()

    chatter_path = build_test_chatter_report_json(tmp_dir)
    op_plan_path = build_test_operation_plan_json(tmp_dir)

    pipeline = GCodeGenerationPipeline()
    task = pipeline.create_task(
        source_chatter_report_path=chatter_path,
        source_operation_plan_path=op_plan_path,
    )
    asyncio.run(pipeline.run_pipeline(task.task_id))

    fr = pipeline.review_feature(
        task_id=task.task_id,
        feature_id="face_A",
        review_status=GCodeReviewStatus.EDITED.value,
        reviewed_by="engineer_02",
        edited_params={
            "axial_depth_mm": 1.5,
            "limit_depth_mm": 5.0,
            "stable": True,
        },
        engineer_notes="降低切深至 1.5mm 提高稳定性",
    )
    check("face_A review_status == edited",
          fr.review_status == GCodeReviewStatus.EDITED.value)
    check("face_A.edited_params 含 axial_depth_mm=1.5",
          fr.edited_params.get("axial_depth_mm") == 1.5,
          f"actual={fr.edited_params}")
    check("face_A.edited_params 含 engineer_notes",
          "engineer_notes" in fr.edited_params)
    check("face_A.stable 仍为 True（edited_params.stable=True）",
          fr.stable is True)


def test_review_feature_invalid_status(tmp_dir: Path) -> None:
    """测试 10: review_feature 非 GENERATED 状态 → GCodeReviewError。"""
    print("\n=== 测试 10: review_feature 非 GENERATED 状态 → GCodeReviewError ===")
    reset_task_store()

    chatter_path = build_test_chatter_report_json(tmp_dir)
    op_plan_path = build_test_operation_plan_json(tmp_dir)

    pipeline = GCodeGenerationPipeline()
    task = pipeline.create_task(
        source_chatter_report_path=chatter_path,
        source_operation_plan_path=op_plan_path,
    )
    # PENDING 状态审核应失败
    try:
        pipeline.review_feature(
            task_id=task.task_id,
            feature_id="face_A",
            review_status=GCodeReviewStatus.CONFIRMED.value,
        )
        check("PENDING 状态审核应抛错", False)
    except GCodeReviewError:
        check("PENDING 状态审核正确抛 GCodeReviewError", True)


def test_review_feature_invalid_review_status(tmp_dir: Path) -> None:
    """测试 11: review_feature 无效审核状态 → GCodeReviewError。"""
    print("\n=== 测试 11: review_feature 无效审核状态 → GCodeReviewError ===")
    reset_task_store()

    chatter_path = build_test_chatter_report_json(tmp_dir)
    op_plan_path = build_test_operation_plan_json(tmp_dir)

    pipeline = GCodeGenerationPipeline()
    task = pipeline.create_task(
        source_chatter_report_path=chatter_path,
        source_operation_plan_path=op_plan_path,
    )
    asyncio.run(pipeline.run_pipeline(task.task_id))

    try:
        pipeline.review_feature(
            task_id=task.task_id,
            feature_id="face_A",
            review_status="invalid_status",
        )
        check("无效审核状态应抛错", False)
    except GCodeReviewError:
        check("无效审核状态正确抛 GCodeReviewError", True)


def test_review_feature_edited_without_params(tmp_dir: Path) -> None:
    """测试 12: review_feature edited 无 edited_params → GCodeReviewError。"""
    print("\n=== 测试 12: review_feature edited 无 edited_params → GCodeReviewError ===")
    reset_task_store()

    chatter_path = build_test_chatter_report_json(tmp_dir)
    op_plan_path = build_test_operation_plan_json(tmp_dir)

    pipeline = GCodeGenerationPipeline()
    task = pipeline.create_task(
        source_chatter_report_path=chatter_path,
        source_operation_plan_path=op_plan_path,
    )
    asyncio.run(pipeline.run_pipeline(task.task_id))

    try:
        pipeline.review_feature(
            task_id=task.task_id,
            feature_id="face_A",
            review_status=GCodeReviewStatus.EDITED.value,
            edited_params=None,
        )
        check("edited 无 edited_params 应抛错", False)
    except GCodeReviewError:
        check("edited 无 edited_params 正确抛 GCodeReviewError", True)


def test_review_feature_unknown_feature_id(tmp_dir: Path) -> None:
    """测试 13: review_feature 未知 feature_id → GCodeReviewError。"""
    print("\n=== 测试 13: review_feature 未知 feature_id → GCodeReviewError ===")
    reset_task_store()

    chatter_path = build_test_chatter_report_json(tmp_dir)
    op_plan_path = build_test_operation_plan_json(tmp_dir)

    pipeline = GCodeGenerationPipeline()
    task = pipeline.create_task(
        source_chatter_report_path=chatter_path,
        source_operation_plan_path=op_plan_path,
    )
    asyncio.run(pipeline.run_pipeline(task.task_id))

    try:
        pipeline.review_feature(
            task_id=task.task_id,
            feature_id="nonexistent_feature",
            review_status=GCodeReviewStatus.CONFIRMED.value,
        )
        check("未知 feature_id 应抛错", False)
    except GCodeReviewError:
        check("未知 feature_id 正确抛 GCodeReviewError", True)


def test_confirm_task_normal(tmp_dir: Path) -> str:
    """测试 14: confirm_task 正常流程 → SUCCEEDED + 导出文件。"""
    print("\n=== 测试 14: confirm_task 正常流程 → SUCCEEDED + 导出文件 ===")
    reset_task_store()

    chatter_path = build_test_chatter_report_json(tmp_dir)
    op_plan_path = build_test_operation_plan_json(tmp_dir)

    pipeline = GCodeGenerationPipeline()
    task = pipeline.create_task(
        source_chatter_report_path=chatter_path,
        source_operation_plan_path=op_plan_path,
        controller_type="fanuc_0i",
    )
    asyncio.run(pipeline.run_pipeline(task.task_id))
    pipeline.review_feature(
        task_id=task.task_id,
        feature_id="face_A",
        review_status=GCodeReviewStatus.CONFIRMED.value,
    )
    pipeline.review_feature(
        task_id=task.task_id,
        feature_id="hole_B",
        review_status=GCodeReviewStatus.CONFIRMED.value,
    )

    result = pipeline.confirm_task(task.task_id, reviewer="engineer_03")

    check("result.status == succeeded",
          result.status == GCodeGenerationTaskStatus.SUCCEEDED.value,
          f"actual={result.status}")
    check("result.gcode_file_path 非空", bool(result.gcode_file_path),
          f"actual={result.gcode_file_path}")
    check("result.gcode_report_path 非空", bool(result.gcode_report_path),
          f"actual={result.gcode_report_path}")
    check("gcode_file_path 以 .nc 结尾（fanuc）",
          result.gcode_file_path.endswith(".nc"),
          f"actual={result.gcode_file_path}")
    check("gcode_report_path 以 .report.json 结尾",
          result.gcode_report_path.endswith(".report.json"),
          f"actual={result.gcode_report_path}")
    check("gcode 文件已写入磁盘",
          Path(result.gcode_file_path).exists())
    check("report JSON 文件已写入磁盘",
          Path(result.gcode_report_path).exists())

    # 验证 report JSON 内容
    report_data = json.loads(
        Path(result.gcode_report_path).read_text(encoding="utf-8")
    )
    check("report.task_id 匹配", report_data["task_id"] == task.task_id)
    check("report.task_status == succeeded",
          report_data["task_status"] == "succeeded")
    check("report.cam_validation_required == True",
          report_data["cam_validation_required"] is True)
    check("report.reviewer == engineer_03",
          report_data["reviewer"] == "engineer_03")
    check("report.feature_results 数量 == 2",
          len(report_data["feature_results"]) == 2,
          f"actual={len(report_data['feature_results'])}")
    check("report.industrial_hard_gates_note 非空",
          bool(report_data["industrial_hard_gates_note"]))
    return task.task_id


def test_confirm_task_invalid_status(tmp_dir: Path) -> None:
    """测试 15: confirm_task 非 REVIEWED → GCodeGenerationPipelineError。"""
    print("\n=== 测试 15: confirm_task 非 REVIEWED → GCodeGenerationPipelineError ===")
    reset_task_store()

    from app.gcode_generation.gcode_store import GCodeGenerationPipelineError

    chatter_path = build_test_chatter_report_json(tmp_dir)
    op_plan_path = build_test_operation_plan_json(tmp_dir)

    pipeline = GCodeGenerationPipeline()
    task = pipeline.create_task(
        source_chatter_report_path=chatter_path,
        source_operation_plan_path=op_plan_path,
    )
    asyncio.run(pipeline.run_pipeline(task.task_id))
    # GENERATED 状态确认应失败（未审核）
    try:
        pipeline.confirm_task(task.task_id)
        check("GENERATED 状态确认应抛错", False)
    except GCodeGenerationPipelineError:
        check("GENERATED 状态确认正确抛 GCodeGenerationPipelineError", True)


def test_confirm_task_all_rejected(tmp_dir: Path) -> None:
    """测试 16: confirm_task 全部 rejected → GCodeReviewError。"""
    print("\n=== 测试 16: confirm_task 全部 rejected → GCodeReviewError ===")
    reset_task_store()

    chatter_path = build_test_chatter_report_json(tmp_dir)
    op_plan_path = build_test_operation_plan_json(tmp_dir)

    pipeline = GCodeGenerationPipeline()
    task = pipeline.create_task(
        source_chatter_report_path=chatter_path,
        source_operation_plan_path=op_plan_path,
    )
    asyncio.run(pipeline.run_pipeline(task.task_id))
    pipeline.review_feature(
        task_id=task.task_id,
        feature_id="face_A",
        review_status=GCodeReviewStatus.REJECTED.value,
    )
    pipeline.review_feature(
        task_id=task.task_id,
        feature_id="hole_B",
        review_status=GCodeReviewStatus.REJECTED.value,
    )

    try:
        pipeline.confirm_task(task.task_id)
        check("全部 rejected 应抛错", False)
    except GCodeReviewError:
        check("全部 rejected 正确抛 GCodeReviewError", True)


def test_export_gcode(tmp_dir: Path) -> str:
    """测试 17: export_gcode 获取文件路径。"""
    print("\n=== 测试 17: export_gcode 获取文件路径 ===")
    reset_task_store()

    chatter_path = build_test_chatter_report_json(tmp_dir)
    op_plan_path = build_test_operation_plan_json(tmp_dir)

    pipeline = GCodeGenerationPipeline()
    task = pipeline.create_task(
        source_chatter_report_path=chatter_path,
        source_operation_plan_path=op_plan_path,
    )
    asyncio.run(pipeline.run_pipeline(task.task_id))
    pipeline.review_feature(
        task_id=task.task_id,
        feature_id="face_A",
        review_status=GCodeReviewStatus.CONFIRMED.value,
    )
    pipeline.review_feature(
        task_id=task.task_id,
        feature_id="hole_B",
        review_status=GCodeReviewStatus.CONFIRMED.value,
    )
    pipeline.confirm_task(task.task_id)

    file_path = pipeline.export_gcode(task.task_id)
    check("export_gcode 返回非空路径", bool(file_path))
    check("文件存在", Path(file_path).exists())
    check("文件以 .nc 结尾", file_path.endswith(".nc"))
    return task.task_id


def test_export_gcode_invalid_status(tmp_dir: Path) -> None:
    """测试 18: export_gcode 非 SUCCEEDED → GCodeGenerationPipelineError。"""
    print("\n=== 测试 18: export_gcode 非 SUCCEEDED → GCodeGenerationPipelineError ===")
    reset_task_store()

    from app.gcode_generation.gcode_store import GCodeGenerationPipelineError

    chatter_path = build_test_chatter_report_json(tmp_dir)
    op_plan_path = build_test_operation_plan_json(tmp_dir)

    pipeline = GCodeGenerationPipeline()
    task = pipeline.create_task(
        source_chatter_report_path=chatter_path,
        source_operation_plan_path=op_plan_path,
    )
    asyncio.run(pipeline.run_pipeline(task.task_id))
    # GENERATED 状态导出应失败
    try:
        pipeline.export_gcode(task.task_id)
        check("GENERATED 状态导出应抛错", False)
    except GCodeGenerationPipelineError:
        check("GENERATED 状态导出正确抛 GCodeGenerationPipelineError", True)


def test_delete_task_succeeded_forbidden(task_id_succeeded: str) -> None:
    """测试 19: delete_task SUCCEEDED 禁删硬约束。"""
    print("\n=== 测试 19: delete_task SUCCEEDED 禁删硬约束 ===")
    reset_task_store()
    # 注：TaskStore 已被前一个测试清空，需重新构造 SUCCEEDED 任务
    # 这里用直接注入方式：先创建任务，再标记为 SUCCEEDED
    # 实际通过 confirm_task 路径完成 SUCCEEDED 状态
    # 此处用前序测试的 task_id 不可行（TaskStore 已清空）
    # 改为：通过 confirm_task 走完整流程
    tmp_dir = Path(tempfile.mkdtemp(prefix="gcode_test_19_"))
    chatter_path = build_test_chatter_report_json(tmp_dir)
    op_plan_path = build_test_operation_plan_json(tmp_dir)

    pipeline = GCodeGenerationPipeline()
    task = pipeline.create_task(
        source_chatter_report_path=chatter_path,
        source_operation_plan_path=op_plan_path,
    )
    asyncio.run(pipeline.run_pipeline(task.task_id))
    pipeline.review_feature(
        task_id=task.task_id,
        feature_id="face_A",
        review_status=GCodeReviewStatus.CONFIRMED.value,
    )
    pipeline.review_feature(
        task_id=task.task_id,
        feature_id="hole_B",
        review_status=GCodeReviewStatus.CONFIRMED.value,
    )
    pipeline.confirm_task(task.task_id)

    from app.gcode_generation.gcode_store import ReviewError
    try:
        pipeline.delete_task(task.task_id)
        check("SUCCEEDED 状态删除应抛错", False)
    except ReviewError:
        check("SUCCEEDED 状态删除正确抛 ReviewError（禁删硬约束）", True)


def test_delete_task_pending_ok(tmp_dir: Path) -> None:
    """测试 20: delete_task PENDING 可删。"""
    print("\n=== 测试 20: delete_task PENDING 可删 ===")
    reset_task_store()

    chatter_path = build_test_chatter_report_json(tmp_dir)
    op_plan_path = build_test_operation_plan_json(tmp_dir)

    pipeline = GCodeGenerationPipeline()
    task = pipeline.create_task(
        source_chatter_report_path=chatter_path,
        source_operation_plan_path=op_plan_path,
    )
    pipeline.delete_task(task.task_id)

    # 删除后再次 get_task 应抛错
    try:
        get_task_store().get_task(task.task_id)
        check("删除后 get_task 应抛错", False)
    except GCodeGenerationError:
        check("PENDING 删除成功 + get_task 抛 GCodeGenerationError", True)


def test_disclaimer_cam_validation(tmp_dir: Path) -> None:
    """测试 21: disclaimer cam_validation_required 始终 True。"""
    print("\n=== 测试 21: disclaimer cam_validation_required 始终 True ===")
    reset_task_store()

    chatter_path = build_test_chatter_report_json(tmp_dir)
    op_plan_path = build_test_operation_plan_json(tmp_dir)

    pipeline = GCodeGenerationPipeline()
    task = pipeline.create_task(
        source_chatter_report_path=chatter_path,
        source_operation_plan_path=op_plan_path,
    )
    result = asyncio.run(pipeline.run_pipeline(task.task_id))

    check("disclaimer 非空", result.disclaimer is not None)
    check("disclaimer.requires_cam_validation == True",
          result.disclaimer.requires_cam_validation is True)
    check("disclaimer.requires_engineer_review == True",
          result.disclaimer.requires_engineer_review is True)
    check("disclaimer.warning_message 非空",
          bool(result.disclaimer.warning_message))


def test_disclaimer_prediction_method(tmp_dir: Path) -> None:
    """测试 22: disclaimer prediction_method 继承阶段 5。"""
    print("\n=== 测试 22: disclaimer prediction_method 继承阶段 5 ===")
    reset_task_store()

    # 使用 neural_network 预测方法（LTC 实验性路径）
    chatter_path = build_test_chatter_report_json(
        tmp_dir, prediction_method="neural_network"
    )
    op_plan_path = build_test_operation_plan_json(tmp_dir)

    pipeline = GCodeGenerationPipeline()
    task = pipeline.create_task(
        source_chatter_report_path=chatter_path,
        source_operation_plan_path=op_plan_path,
    )
    result = asyncio.run(pipeline.run_pipeline(task.task_id))

    check("disclaimer.prediction_method == neural_network",
          result.disclaimer.prediction_method == "neural_network",
          f"actual={result.disclaimer.prediction_method}")
    check("disclaimer.warning_message 含「实验性」",
          "实验性" in result.disclaimer.warning_message,
          f"actual={result.disclaimer.warning_message}")


# =============================================================================
# 主入口
# =============================================================================


def main() -> int:
    print("=" * 70)
    print("pipeline.py 端到端验证（阶段 6 s6-8v）")
    print("=" * 70)

    tmp_dir = Path(tempfile.mkdtemp(prefix="gcode_pipeline_verify_"))
    print(f"临时目录: {tmp_dir}")

    # 测试 1: create_task 正常创建
    test_create_task_normal(tmp_dir)

    # 测试 2: create_task 空路径
    test_create_task_invalid_input()

    # 测试 3: run_pipeline 正常流程
    test_run_pipeline_normal(tmp_dir)

    # 测试 4: run_pipeline 含 unstable 特征
    test_run_pipeline_unstable_feature(tmp_dir)

    # 测试 5: run_pipeline ChatterReport 不存在
    test_run_pipeline_chatter_report_not_exist(tmp_dir)

    # 测试 6: run_pipeline 任务不存在
    test_run_pipeline_task_not_exist()

    # 测试 7: run_pipeline 状态不允许执行
    test_run_pipeline_invalid_status(tmp_dir)

    # 测试 8: review_feature confirmed
    test_review_feature_confirmed(tmp_dir)

    # 测试 9: review_feature edited
    test_review_feature_edited(tmp_dir)

    # 测试 10: review_feature 非 GENERATED 状态
    test_review_feature_invalid_status(tmp_dir)

    # 测试 11: review_feature 无效审核状态
    test_review_feature_invalid_review_status(tmp_dir)

    # 测试 12: review_feature edited 无 edited_params
    test_review_feature_edited_without_params(tmp_dir)

    # 测试 13: review_feature 未知 feature_id
    test_review_feature_unknown_feature_id(tmp_dir)

    # 测试 14: confirm_task 正常流程
    test_confirm_task_normal(tmp_dir)

    # 测试 15: confirm_task 非 REVIEWED
    test_confirm_task_invalid_status(tmp_dir)

    # 测试 16: confirm_task 全部 rejected
    test_confirm_task_all_rejected(tmp_dir)

    # 测试 17: export_gcode 获取文件路径
    test_export_gcode(tmp_dir)

    # 测试 18: export_gcode 非 SUCCEEDED
    test_export_gcode_invalid_status(tmp_dir)

    # 测试 19: delete_task SUCCEEDED 禁删硬约束
    test_delete_task_succeeded_forbidden("dummy")

    # 测试 20: delete_task PENDING 可删
    test_delete_task_pending_ok(tmp_dir)

    # 测试 21: disclaimer cam_validation_required 始终 True
    test_disclaimer_cam_validation(tmp_dir)

    # 测试 22: disclaimer prediction_method 继承阶段 5
    test_disclaimer_prediction_method(tmp_dir)

    print("\n" + "=" * 70)
    print(f"总计: {PASS} 通过, {FAIL} 失败")
    print("=" * 70)
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
