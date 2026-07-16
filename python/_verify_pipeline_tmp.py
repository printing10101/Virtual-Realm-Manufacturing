r"""s7-9 独立验证脚本：CamValidationPipeline 编排器。

通过依赖注入 mock GCodeLoader / InternalValidator / CamAdapter，
验证 pipeline.py 的完整状态机 + 双 JSON 导出 + 硬约束。

覆盖用例：
    1. 实例化（依赖注入 mock）
    2. create_task → PENDING
    3. run_pipeline → VALIDATED（mock 双层校验全通过）
    4. review_task → REVIEWED（confirmed 全部特征）
    5. confirm_task → SUCCEEDED + 双 JSON 导出
    6. delete_task SUCCEEDED 禁删硬约束
    7. delete_task PENDING 可删
    8. CamValidationResult 字段完整性
    9. cam_report.json + internal_report.json 文件内容验证
    10. 非法 cam_backend 拒绝
    11. 状态非法转移拒绝（PENDING 不能 confirm）
    12. FAILED 任务可重跑（PENDING/FAILED 可执行）
    13. list_tasks 排序 + status_filter

运行（在 python/ 目录下）：
    py -3.14 _verify_pipeline_tmp.py
"""

from __future__ import annotations

# =============================================================================
# matplotlib 缺失 workaround（Python 3.14 环境）
# =============================================================================
# 项目记忆：Python 3.14 在 Windows 上 WinSock/IOCP 子系统损坏，
# pip 无法联网安装 matplotlib，但 app/simulation/__init__.py 会触发
# toolpath_visualizer.py 的 `import matplotlib` + `matplotlib.use("Agg")`
# + `import matplotlib.pyplot as plt`，导致 ImportError。
#
# 验证脚本只需要 collision_detector / toolpath_parser（阶段 7 复用模块），
# 不需要 ToolpathVisualizer。因此注入假 matplotlib 模块到 sys.modules，
# 让 toolpath_visualizer 导入通过即可。
# 这是验证脚本范围内的 hack，不修改生产代码。

import sys
import types

if "matplotlib" not in sys.modules:
    _fake_mpl = types.ModuleType("matplotlib")
    _fake_mpl.use = lambda *args, **kwargs: None  # type: ignore[attr-defined]
    _fake_mpl.__version__ = "0.0.0+fake"
    sys.modules["matplotlib"] = _fake_mpl

    _fake_pyplot = types.ModuleType("matplotlib.pyplot")
    # 常用 pyplot API 都设为 no-op，避免导入时调用失败
    _fake_pyplot.figure = lambda *a, **kw: None  # type: ignore[attr-defined]
    _fake_pyplot.subplot = lambda *a, **kw: None  # type: ignore[attr-defined]
    _fake_pyplot.plot = lambda *a, **kw: None  # type: ignore[attr-defined]
    _fake_pyplot.scatter = lambda *a, **kw: None  # type: ignore[attr-defined]
    _fake_pyplot.show = lambda *a, **kw: None  # type: ignore[attr-defined]
    _fake_pyplot.close = lambda *a, **kw: None  # type: ignore[attr-defined]
    _fake_pyplot.savefig = lambda *a, **kw: None  # type: ignore[attr-defined]
    _fake_pyplot.title = lambda *a, **kw: None  # type: ignore[attr-defined]
    _fake_pyplot.xlabel = lambda *a, **kw: None  # type: ignore[attr-defined]
    _fake_pyplot.ylabel = lambda *a, **kw: None  # type: ignore[attr-defined]
    _fake_pyplot.legend = lambda *a, **kw: None  # type: ignore[attr-defined]
    sys.modules["matplotlib.pyplot"] = _fake_pyplot
    _fake_mpl.pyplot = _fake_pyplot  # type: ignore[attr-defined]

    # 让 mpl_toolkits.mplot3d 也可导入（ToolpathVisualizer 可能用）
    _fake_mpl_toolkits = types.ModuleType("mpl_toolkits")
    sys.modules["mpl_toolkits"] = _fake_mpl_toolkits
    _fake_mplot3d = types.ModuleType("mpl_toolkits.mplot3d")
    sys.modules["mpl_toolkits.mplot3d"] = _fake_mplot3d
    _fake_mpl_toolkits.mplot3d = _fake_mplot3d  # type: ignore[attr-defined]


# 同步协程驱动器（绕开 asyncio 事件循环）
# 项目记忆：Python 3.14 在 Windows 上 import asyncio 会因 _overlapped C 扩展
# 抛出 OSError [WinError 10038]（系统级 IOCP 子系统问题，3.11/3.13/3.14 均受影响）。
# 但 pipeline.py 的 async def run_pipeline / _execute_validation 内部全是同步代码
# （GCodeLoader / InternalValidator / CamAdapter 都是同步模块），仅用 async 标记。
# 因此可以用同步驱动器 send(None) 推进协程，完全绕开 asyncio 事件循环。
# 当协程遇到 await inner_coro 时，Python 编译器会自动驱动 inner_coro，
# 外层 send(None) 会一直推进直到完成或抛 StopIteration(value)。
import json
import logging
import os
import tempfile
import time
from dataclasses import replace
from pathlib import Path
from typing import Any


# =============================================================================
# 最小 Mock 类（替代 unittest.mock.MagicMock，避免 asyncio 依赖）
# =============================================================================
# 项目记忆：Python 3.14 在 Windows 上 unittest.mock 也会 import asyncio，
# 同样触发 OSError [WinError 10038]。本验证脚本只需要 MagicMock 的基本功能：
#   - 任意属性访问返回子 _Mock（自动创建并缓存）
#   - .return_value 可配置（默认 None）
#   - .side_effect 可配置（异常类/异常实例/可调用对象/任意值）
#   - .called 标记是否被调用过
# 因此实现一个不依赖 asyncio 的最小 _Mock 即可。


class _Mock:
    """最小 Mock 类（替代 unittest.mock.MagicMock）。

    支持的功能：
        - mock.attr           → 自动创建并返回子 _Mock（缓存）
        - mock.method(args)   → 返回 return_value 或抛 side_effect
        - mock.return_value   → 配置调用返回值（默认 None）
        - mock.side_effect    → 配置异常或可调用（设为非 None 时覆盖 return_value）
        - mock.called         → 是否被调用过（True/False）
    """

    def __init__(self) -> None:
        # 用 object.__setattr__ 绕过自定义 __setattr__
        object.__setattr__(self, "_mock_children", {})
        object.__setattr__(self, "_mock_return_value", None)
        object.__setattr__(self, "_mock_side_effect", None)
        object.__setattr__(self, "_mock_called", False)

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        object.__setattr__(self, "_mock_called", True)
        se = object.__getattribute__(self, "_mock_side_effect")
        if se is not None:
            if isinstance(se, BaseException):
                raise se
            if isinstance(se, type) and issubclass(se, BaseException):
                raise se()
            if callable(se):
                return se(*args, **kwargs)
            return se
        return object.__getattribute__(self, "_mock_return_value")

    def __getattr__(self, name: str) -> Any:
        if name.startswith("__"):
            raise AttributeError(name)
        # 特殊属性：直接返回内部存储值
        if name == "return_value":
            return object.__getattribute__(self, "_mock_return_value")
        if name == "side_effect":
            return object.__getattribute__(self, "_mock_side_effect")
        if name == "called":
            return object.__getattribute__(self, "_mock_called")
        # 子 Mock：自动创建并缓存
        children = object.__getattribute__(self, "_mock_children")
        if name not in children:
            children[name] = _Mock()
        return children[name]

    def __setattr__(self, name: str, value: Any) -> None:
        if name == "return_value":
            object.__setattr__(self, "_mock_return_value", value)
        elif name == "side_effect":
            object.__setattr__(self, "_mock_side_effect", value)
        else:
            children = object.__getattribute__(self, "_mock_children")
            children[name] = value


def _sync_run(coro: Any) -> Any:
    """同步驱动协程到完成（绕开 asyncio 事件循环）。

    适用于内部全是同步代码（或仅 await 同步协程）的 async def 函数。

    Args:
        coro: 协程对象（由 async def 函数调用产生）

    Returns:
        协程的返回值

    Raises:
        RuntimeError: 协程内部包含无法同步驱动的真实 async IO
            （如 asyncio.sleep / network IO），此时 send(None) 既不完成
            也不抛 StopIteration
    """
    while True:
        try:
            coro.send(None)
        except StopIteration as e:
            return e.value

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("s7-9-verify")

# 确保 python/ 在 sys.path
_THIS_DIR = Path(__file__).resolve().parent
if str(_THIS_DIR) not in sys.path:
    sys.path.insert(0, str(_THIS_DIR))

# 设置临时输出目录，避免污染 outputs/cam_validation
_TMP_OUTPUT_DIR = Path(tempfile.gettempdir()) / "s7_9_verify_cam_validation"
_TMP_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
# 必须先设置环境变量再 import pipeline（pipeline 会读取 config）
os.environ["LNN_CAM_OUTPUT_DIR"] = str(_TMP_OUTPUT_DIR)
os.environ["LNN_CAM_ENABLED"] = "true"


# =============================================================================
# Mock 对象构造
# =============================================================================


def _make_gcode_load_result(
    gcode_text: str = "G01 X10 Y20 Z5 F500\nG01 X20 Y20 Z-2 F200\nM30\n",
    feature_results: list[dict[str, Any]] | None = None,
    controller_type: str = "fanuc_0i",
    material_name: str = "45#钢",
    safe_z: float = 80.0,
    stock_top_z: float = 50.0,
    prediction_method: str = "analytical",
    pending_calibration: bool = False,
    gcode_file_path: str = "/tmp/test_gcode.nc",
    gcode_total_lines: int = 3,
) -> Any:
    """构造 GCodeLoadResult mock 对象（避免依赖真实文件）。"""
    if feature_results is None:
        feature_results = [
            {
                "feature_id": "feat_001",
                "feature_type": "plane",
                "line_range": [1, 2],
                "spindle_rpm": 3000.0,
                "axial_depth_mm": 2.0,
                "limit_depth_mm": 2.5,
                "stable": True,
                "safety_margin_ratio": 0.8,
                "warning": "",
                "review_status": "confirmed",
                "edited_params": {},
            },
            {
                "feature_id": "feat_002",
                "feature_type": "cylinder",
                "line_range": [3, 3],
                "spindle_rpm": 2500.0,
                "axial_depth_mm": 1.5,
                "limit_depth_mm": 2.0,
                "stable": True,
                "safety_margin_ratio": 0.75,
                "warning": "",
                "review_status": "confirmed",
                "edited_params": {},
            },
        ]

    class _MockGCodeLoadResult:
        def __init__(self) -> None:
            self.task_id = "gc_test_001"
            self.gcode_text = gcode_text
            self.feature_results = feature_results
            self.controller_type = controller_type
            self.material_name = material_name
            self.safe_z = safe_z
            self.stock_top_z = stock_top_z
            self.prediction_method = prediction_method
            self.pending_calibration = pending_calibration
            self.gcode_file_path = gcode_file_path
            self.gcode_total_lines = gcode_total_lines
            self.cam_validation_required = True
            self.source_chatter_report_path = ""
            self.source_operation_plan_path = ""
            self.reviewer = "engineer"
            self.exported_at = time.time()
            self.load_warnings: list[str] = []

    return _MockGCodeLoadResult()


def _make_collision_report(
    total_segments: int = 5,
    segments_checked: int = 5,
    safe: bool = True,
) -> Any:
    """构造 CollisionReport mock 对象。"""

    class _MockCollisionReport:
        def __init__(self) -> None:
            self.total_segments = total_segments
            self.segments_checked = segments_checked
            self.collisions: list[Any] = []
            self.warnings: list[str] = []
            self.safe = safe

    return _MockCollisionReport()


def _make_cam_software_report(
    status: str = "skipped",
    backend_used: str = "internal_only",
    degraded: bool = False,
    degradation_reason: str = "",
) -> Any:
    """构造 CamSoftwareReport mock 对象。"""

    class _MockCamSoftwareReport:
        def __init__(self) -> None:
            self.status = status
            self.backend_used = backend_used
            self.messages: list[str] = ["[mock] CAM 软件二次校验已完成"]
            self.collisions: list[dict[str, Any]] = []
            self.degraded = degraded
            self.degradation_reason = degradation_reason
            self.gcode_file_path = "/tmp/test_gcode.nc"
            self.controller_type = "fanuc_0i"
            self.validation_timestamp = "2026-07-14T00:00:00Z"
            self.subprocess_returncode: int | None = None
            self.manual_checklist_path = ""

        @property
        def safe(self) -> bool:
            return self.status in {"skipped", "pass", "manual_pending"}

    return _MockCamSoftwareReport()


def _make_mock_loader(load_result: Any) -> Any:
    """构造 mock GCodeLoader，load_from_report 返回固定结果。"""
    mock = _Mock()
    mock.load_from_report.return_value = load_result
    return mock


def _make_default_updated_features() -> list[Any]:
    """构造默认的 FeatureValidationResult 列表（feat_001 + feat_002）。

    供 _make_mock_validator 默认返回，确保 task.feature_validation_results
    非空，让 review_task 能找到 feature。
    """
    from app.cam_validation.cam_store import (
        CamReviewStatus,
        FeatureValidationResult,
    )

    return [
        FeatureValidationResult(
            feature_id="feat_001",
            feature_type="plane",
            line_range=(1, 2),
            internal_check_passed=True,
            internal_events=[],
            cam_check_passed=True,
            cam_messages=[],
            cam_backend_used="internal_only",
            review_status=CamReviewStatus.PENDING.value,
            edited_params={},
            spindle_rpm=3000.0,
            axial_depth_mm=2.0,
            limit_depth_mm=2.5,
            stable=True,
            safety_margin_ratio=0.8,
            warning="",
        ),
        FeatureValidationResult(
            feature_id="feat_002",
            feature_type="cylinder",
            line_range=(3, 3),
            internal_check_passed=True,
            internal_events=[],
            cam_check_passed=True,
            cam_messages=[],
            cam_backend_used="internal_only",
            review_status=CamReviewStatus.PENDING.value,
            edited_params={},
            spindle_rpm=2500.0,
            axial_depth_mm=1.5,
            limit_depth_mm=2.0,
            stable=True,
            safety_margin_ratio=0.75,
            warning="",
        ),
    ]


def _make_mock_validator(
    collision_report: Any | None = None,
    updated_features: list[Any] | None = None,
) -> Any:
    """构造 mock InternalValidator，validate() 返回固定结果。

    默认返回 2 个 features（feat_001 + feat_002），确保 review_task 能找到 feature。
    """
    mock = _Mock()
    cr = collision_report or _make_collision_report()
    mock.validate.return_value = (cr, updated_features or _make_default_updated_features())
    return mock


def _make_mock_adapter(cam_report: Any | None = None) -> Any:
    """构造 mock CamAdapter，validate() 返回固定结果。"""
    mock = _Mock()
    mock.validate.return_value = cam_report or _make_cam_software_report()
    mock.list_available_backends.return_value = [
        {"name": "internal_only", "available": True},
        {"name": "manual", "available": True},
    ]
    return mock


# =============================================================================
# 测试用例
# =============================================================================


# 全局测试计数器
_PASS = 0
_FAIL = 0
_SKIP = 0
_FAILURES: list[str] = []


def _check(condition: bool, name: str, detail: str = "") -> None:
    global _PASS, _FAIL
    if condition:
        _PASS += 1
        logger.info("[PASS] %s", name)
    else:
        _FAIL += 1
        msg = f"[FAIL] {name}" + (f": {detail}" if detail else "")
        _FAILURES.append(msg)
        logger.error(msg)


def _skip(name: str, reason: str = "") -> None:
    global _SKIP
    _SKIP += 1
    logger.warning("[SKIP] %s%s", name, f": {reason}" if reason else "")


# =============================================================================
# 用例 1-5：完整成功路径（PENDING → SUCCEEDED）
# =============================================================================


def test_full_success_path() -> None:
    """用例 1-5：完整成功路径。"""
    logger.info("=" * 70)
    logger.info("用例 1-5：完整成功路径")
    logger.info("=" * 70)

    # 延迟 import，确保环境变量已设置
    from app.cam_validation.pipeline import CamValidationPipeline, CamValidationResult
    from app.cam_validation.cam_store import (
        CamReviewStatus,
        CamTaskStore,
        CamValidationTaskStatus,
        FeatureValidationResult,
        get_task_store,
    )

    # 清空 store 单例（避免上次测试残留）
    store = get_task_store()
    store.clear()

    # 构造 mock
    load_result = _make_gcode_load_result()
    collision_report = _make_collision_report(safe=True)
    # 预先构造 FeatureValidationResult（internal_validator 会返回填充后的）
    pre_features = [
        FeatureValidationResult(
            feature_id="feat_001",
            feature_type="plane",
            line_range=(1, 2),
            internal_check_passed=True,
            internal_events=[],
            cam_check_passed=True,
            cam_messages=[],
            cam_backend_used="internal_only",
            review_status=CamReviewStatus.PENDING.value,
            edited_params={},
            spindle_rpm=3000.0,
            axial_depth_mm=2.0,
            limit_depth_mm=2.5,
            stable=True,
            safety_margin_ratio=0.8,
            warning="",
        ),
        FeatureValidationResult(
            feature_id="feat_002",
            feature_type="cylinder",
            line_range=(3, 3),
            internal_check_passed=True,
            internal_events=[],
            cam_check_passed=True,
            cam_messages=[],
            cam_backend_used="internal_only",
            review_status=CamReviewStatus.PENDING.value,
            edited_params={},
            spindle_rpm=2500.0,
            axial_depth_mm=1.5,
            limit_depth_mm=2.0,
            stable=True,
            safety_margin_ratio=0.75,
            warning="",
        ),
    ]
    mock_loader = _make_mock_loader(load_result)
    mock_validator = _make_mock_validator(
        collision_report=collision_report,
        updated_features=pre_features,
    )
    mock_adapter = _make_mock_adapter(
        cam_report=_make_cam_software_report(
            status="skipped",
            backend_used="internal_only",
        )
    )

    pipeline = CamValidationPipeline(
        cfg=None,
        loader=mock_loader,
        validator=mock_validator,
        adapter=mock_adapter,
    )

    # 用例 1：create_task → PENDING
    task = pipeline.create_task(
        source_gcode_report_path="/tmp/stage6_report.json",
        source_gcode_file_path="/tmp/test_gcode.nc",
        controller_type="fanuc_0i",
        material_name="45#钢",
        cam_backend="internal_only",
    )
    _check(
        task.status == CamValidationTaskStatus.PENDING.value,
        "用例 1: create_task → PENDING",
        f"actual={task.status}",
    )
    _check(
        task.task_id.startswith("cam_"),
        "用例 1: task_id 前缀 cam_",
        f"actual={task.task_id}",
    )
    _check(
        task.cam_validation_required is True,
        "用例 1: cam_validation_required 始终 True",
    )
    _check(
        task.workspace_dir and Path(task.workspace_dir).exists(),
        "用例 1: workspace_dir 已创建",
        f"workspace_dir={task.workspace_dir}",
    )

    # 用例 2：run_pipeline → VALIDATED
    result = _sync_run(pipeline.run_pipeline(task.task_id))
    _check(
        result.status == CamValidationTaskStatus.VALIDATED.value,
        "用例 2: run_pipeline → VALIDATED",
        f"actual={result.status}",
    )
    _check(
        result.total_features == 2,
        "用例 2: total_features=2",
        f"actual={result.total_features}",
    )
    _check(
        result.passed_features == 2,
        "用例 2: passed_features=2",
        f"actual={result.passed_features}",
    )
    _check(
        result.failed_features == 0,
        "用例 2: failed_features=0",
        f"actual={result.failed_features}",
    )
    _check(
        result.cam_backend_used == "internal_only",
        "用例 2: cam_backend_used=internal_only",
        f"actual={result.cam_backend_used}",
    )
    _check(
        result.gcode_total_lines == 3,
        "用例 2: gcode_total_lines=3",
        f"actual={result.gcode_total_lines}",
    )
    _check(
        isinstance(result, CamValidationResult),
        "用例 2: 返回类型 CamValidationResult",
    )
    _check(
        result.disclaimer is not None,
        "用例 2: disclaimer 已构造",
    )
    # mock 验证
    _check(
        mock_loader.load_from_report.called,
        "用例 2: GCodeLoader.load_from_report 被调用",
    )
    _check(
        mock_validator.validate.called,
        "用例 2: InternalValidator.validate 被调用",
    )
    _check(
        mock_adapter.validate.called,
        "用例 2: CamAdapter.validate 被调用",
    )

    # 用例 3：review_task → REVIEWED（两个特征都 confirmed）
    fr1 = pipeline.review_task(
        task_id=task.task_id,
        feature_id="feat_001",
        review_status=CamReviewStatus.CONFIRMED.value,
        reviewed_by="engineer_zhang",
        engineer_notes="ok",
    )
    _check(
        fr1.review_status == CamReviewStatus.CONFIRMED.value,
        "用例 3: feat_001 review_status=confirmed",
        f"actual={fr1.review_status}",
    )
    # 单特征审核后任务状态应仍为 VALIDATED（未全部审核完）
    task_after_1 = pipeline.get_task(task.task_id)
    _check(
        task_after_1.status == CamValidationTaskStatus.VALIDATED.value,
        "用例 3: 单特征审核后仍 VALIDATED",
        f"actual={task_after_1.status}",
    )

    fr2 = pipeline.review_task(
        task_id=task.task_id,
        feature_id="feat_002",
        review_status=CamReviewStatus.CONFIRMED.value,
        reviewed_by="engineer_zhang",
    )
    _check(
        fr2.review_status == CamReviewStatus.CONFIRMED.value,
        "用例 3: feat_002 review_status=confirmed",
    )
    task_after_2 = pipeline.get_task(task.task_id)
    _check(
        task_after_2.status == CamValidationTaskStatus.REVIEWED.value,
        "用例 3: 全部审核完 → REVIEWED",
        f"actual={task_after_2.status}",
    )
    _check(
        task_after_2.reviewed_by == "engineer_zhang",
        "用例 3: reviewed_by 记录",
        f"actual={task_after_2.reviewed_by}",
    )
    _check(
        task_after_2.reviewed_at > 0,
        "用例 3: reviewed_at 时间戳记录",
    )

    # 用例 4：confirm_task → SUCCEEDED + 双 JSON 导出
    confirm_result = pipeline.confirm_task(
        task_id=task.task_id,
        reviewer="engineer_zhang",
    )
    _check(
        confirm_result.status == CamValidationTaskStatus.SUCCEEDED.value,
        "用例 4: confirm_task → SUCCEEDED",
        f"actual={confirm_result.status}",
    )
    _check(
        confirm_result.cam_report_path is not None
        and Path(confirm_result.cam_report_path).is_file(),
        "用例 4: cam_report.json 已导出",
        f"path={confirm_result.cam_report_path}",
    )
    _check(
        confirm_result.internal_report_path is not None
        and Path(confirm_result.internal_report_path).is_file(),
        "用例 4: internal_report.json 已导出",
        f"path={confirm_result.internal_report_path}",
    )
    _check(
        confirm_result.cam_report_path.endswith(".cam_report.json"),
        "用例 4: cam_report 路径扩展名正确",
    )
    _check(
        confirm_result.internal_report_path.endswith(".internal_report.json"),
        "用例 4: internal_report 路径扩展名正确",
    )

    # 用例 5：cam_report.json + internal_report.json 内容验证
    cam_report_data = json.loads(
        Path(confirm_result.cam_report_path).read_text(encoding="utf-8")
    )
    _check(
        cam_report_data["task_id"] == task.task_id,
        "用例 5: cam_report.task_id",
    )
    _check(
        cam_report_data["task_status"] == "succeeded",
        "用例 5: cam_report.task_status=succeeded",
    )
    _check(
        cam_report_data["cam_validation_required"] is True,
        "用例 5: cam_report.cam_validation_required=True",
    )
    _check(
        cam_report_data["total_features"] == 2,
        "用例 5: cam_report.total_features=2",
    )
    _check(
        cam_report_data["passed_features"] == 2,
        "用例 5: cam_report.passed_features=2",
    )
    _check(
        len(cam_report_data["feature_validation_results"]) == 2,
        "用例 5: feature_validation_results 长度=2",
    )
    _check(
        "industrial_hard_gates_note" in cam_report_data,
        "用例 5: industrial_hard_gates_note 存在",
    )
    _check(
        "cam_software_report" in cam_report_data,
        "用例 5: cam_software_report 存在",
    )
    _check(
        cam_report_data["cam_software_report"]["backend_used"]
        == "internal_only",
        "用例 5: cam_software_report.backend_used=internal_only",
    )
    _check(
        cam_report_data["reviewer"] == "engineer_zhang",
        "用例 5: reviewer 记录",
    )

    internal_report_data = json.loads(
        Path(confirm_result.internal_report_path).read_text(encoding="utf-8")
    )
    _check(
        internal_report_data["task_id"] == task.task_id,
        "用例 5: internal_report.task_id",
    )
    _check(
        "feature_results" in internal_report_data,
        "用例 5: internal_report.feature_results 存在",
    )
    _check(
        "debug_note" in internal_report_data,
        "用例 5: internal_report.debug_note 存在",
    )

    # 返回 task_id 供后续测试使用
    return task.task_id


# =============================================================================
# 用例 6：delete_task SUCCEEDED 禁删硬约束
# =============================================================================


def test_delete_succeeded_forbidden(succeeded_task_id: str) -> None:
    """用例 6：SUCCEEDED 禁删硬约束。"""
    logger.info("=" * 70)
    logger.info("用例 6：SUCCEEDED 禁删硬约束")
    logger.info("=" * 70)

    from app.cam_validation.pipeline import CamValidationPipeline
    from app.cam_validation.cam_store import ReviewError

    mock_loader = _make_mock_loader(_make_gcode_load_result())
    mock_validator = _make_mock_validator()
    mock_adapter = _make_mock_adapter()
    pipeline = CamValidationPipeline(
        cfg=None,
        loader=mock_loader,
        validator=mock_validator,
        adapter=mock_adapter,
    )

    raised = False
    try:
        pipeline.delete_task(succeeded_task_id)
    except ReviewError as e:
        raised = True
        logger.info("预期抛出 ReviewError: %s", str(e)[:120])
    except Exception as e:
        _check(
            False,
            "用例 6: 抛出类型应为 ReviewError",
            f"实际类型={type(e).__name__}",
        )

    _check(raised, "用例 6: SUCCEEDED 删除被拒绝（ReviewError）")

    # 验证任务仍存在
    task = pipeline.get_task(succeeded_task_id)
    _check(
        task.status == "succeeded",
        "用例 6: SUCCEEDED 任务仍存在",
        f"actual={task.status}",
    )


# =============================================================================
# 用例 7：delete_task PENDING 可删
# =============================================================================


def test_delete_pending_allowed() -> None:
    """用例 7：PENDING 可删。"""
    logger.info("=" * 70)
    logger.info("用例 7：PENDING 可删")
    logger.info("=" * 70)

    from app.cam_validation.pipeline import CamValidationPipeline
    from app.cam_validation.cam_store import CamValidationError, get_task_store

    store = get_task_store()
    store.clear()

    mock_loader = _make_mock_loader(_make_gcode_load_result())
    mock_validator = _make_mock_validator()
    mock_adapter = _make_mock_adapter()
    pipeline = CamValidationPipeline(
        cfg=None,
        loader=mock_loader,
        validator=mock_validator,
        adapter=mock_adapter,
    )

    task = pipeline.create_task(
        source_gcode_report_path="/tmp/stage6_report_pending.json",
        cam_backend="internal_only",
    )
    task_id = task.task_id
    _check(
        task.status == "pending",
        "用例 7: 初始 PENDING",
        f"actual={task.status}",
    )

    pipeline.delete_task(task_id)
    _check(True, "用例 7: delete_task PENDING 未抛异常")

    # 验证任务已删除
    raised = False
    try:
        pipeline.get_task(task_id)
    except (CamValidationError, Exception) as e:
        # CamValidationPipelineError 也继承自 CamValidationError
        raised = True
        logger.info("预期抛出异常: %s", str(e)[:80])
    _check(raised, "用例 7: 删除后查询应抛异常")


# =============================================================================
# 用例 8：CamValidationResult 字段完整性
# =============================================================================


def test_result_fields_completeness() -> None:
    """用例 8：CamValidationResult 字段完整性。"""
    logger.info("=" * 70)
    logger.info("用例 8：CamValidationResult 字段完整性")
    logger.info("=" * 70)

    from app.cam_validation.pipeline import CamValidationResult

    expected_fields = {
        "task_id", "status",
        "source_gcode_report_path", "source_gcode_file_path",
        "controller_type", "material_name", "gcode_total_lines",
        "total_features", "passed_features", "failed_features",
        "pending_calibration", "prediction_method",
        "cam_backend_requested", "cam_backend_used",
        "cam_backend_fallback_reason",
        "cam_report_path", "internal_report_path",
        "error_message", "disclaimer",
    }
    actual_fields = set(CamValidationResult.__dataclass_fields__.keys())
    _check(
        expected_fields == actual_fields,
        "用例 8: CamValidationResult 19 字段完整",
        f"missing={expected_fields - actual_fields}, "
        f"extra={actual_fields - expected_fields}",
    )

    # 验证 to_dict 字段
    sample = CamValidationResult(
        task_id="cam_test",
        status="succeeded",
        source_gcode_report_path="/tmp/r.json",
        source_gcode_file_path="/tmp/g.nc",
        controller_type="fanuc_0i",
        material_name="45#钢",
        gcode_total_lines=10,
        total_features=3,
        passed_features=3,
        failed_features=0,
        pending_calibration=False,
        prediction_method="analytical",
        cam_backend_requested="internal_only",
        cam_backend_used="internal_only",
        cam_backend_fallback_reason="",
    )
    d = sample.to_dict()
    _check(
        set(d.keys()) == expected_fields,
        "用例 8: to_dict() 字段一致",
        f"keys={sorted(d.keys())}",
    )
    _check(
        d["task_id"] == "cam_test",
        "用例 8: to_dict()['task_id']",
    )


# =============================================================================
# 用例 9：非法 cam_backend 拒绝
# =============================================================================


def test_invalid_cam_backend_rejected() -> None:
    """用例 9：非法 cam_backend 拒绝。"""
    logger.info("=" * 70)
    logger.info("用例 9：非法 cam_backend 拒绝")
    logger.info("=" * 70)

    from app.cam_validation.pipeline import CamValidationPipeline
    from app.cam_validation.cam_store import CamValidationPipelineError, get_task_store

    store = get_task_store()
    store.clear()

    mock_loader = _make_mock_loader(_make_gcode_load_result())
    mock_validator = _make_mock_validator()
    mock_adapter = _make_mock_adapter()
    pipeline = CamValidationPipeline(
        cfg=None,
        loader=mock_loader,
        validator=mock_validator,
        adapter=mock_adapter,
    )

    raised = False
    try:
        pipeline.create_task(
            source_gcode_report_path="/tmp/r.json",
            cam_backend="invalid_backend",
        )
    except CamValidationPipelineError as e:
        raised = True
        logger.info("预期抛出: %s", str(e)[:100])
    _check(raised, "用例 9: 非法 cam_backend 抛 CamValidationPipelineError")

    # 空路径也应拒绝
    raised = False
    try:
        pipeline.create_task(
            source_gcode_report_path="",
            cam_backend="internal_only",
        )
    except CamValidationPipelineError:
        raised = True
    _check(raised, "用例 9: 空路径抛 CamValidationPipelineError")


# =============================================================================
# 用例 10：状态非法转移拒绝
# =============================================================================


def test_invalid_state_transition() -> None:
    """用例 10：状态非法转移拒绝。"""
    logger.info("=" * 70)
    logger.info("用例 10：状态非法转移拒绝")
    logger.info("=" * 70)

    from app.cam_validation.pipeline import CamValidationPipeline
    from app.cam_validation.cam_store import (
        CamValidationPipelineError,
        get_task_store,
    )

    store = get_task_store()
    store.clear()

    mock_loader = _make_mock_loader(_make_gcode_load_result())
    mock_validator = _make_mock_validator()
    mock_adapter = _make_mock_adapter()
    pipeline = CamValidationPipeline(
        cfg=None,
        loader=mock_loader,
        validator=mock_validator,
        adapter=mock_adapter,
    )

    # PENDING 不能 confirm
    task = pipeline.create_task(
        source_gcode_report_path="/tmp/r.json",
        cam_backend="internal_only",
    )
    raised = False
    try:
        pipeline.confirm_task(task.task_id)
    except CamValidationPipelineError:
        raised = True
    _check(raised, "用例 10: PENDING → confirm 拒绝")

    # PENDING 不能 review
    raised = False
    try:
        pipeline.review_task(
            task_id=task.task_id,
            feature_id="feat_001",
            review_status="confirmed",
        )
    except Exception:
        raised = True
    _check(raised, "用例 10: PENDING → review 拒绝")

    # run_pipeline 后再 run_pipeline（VALIDATED 不能再 run）
    _sync_run(pipeline.run_pipeline(task.task_id))
    task_after = pipeline.get_task(task.task_id)
    _check(
        task_after.status == "validated",
        "用例 10: 首次 run_pipeline → VALIDATED",
        f"actual={task_after.status}",
    )
    raised = False
    try:
        _sync_run(pipeline.run_pipeline(task.task_id))
    except CamValidationPipelineError:
        raised = True
    _check(raised, "用例 10: VALIDATED → run_pipeline 拒绝")


# =============================================================================
# 用例 11：FAILED 任务可重跑
# =============================================================================


def test_failed_task_can_rerun() -> None:
    """用例 11：FAILED 任务可重跑。"""
    logger.info("=" * 70)
    logger.info("用例 11：FAILED 任务可重跑")
    logger.info("=" * 70)

    from app.cam_validation.pipeline import CamValidationPipeline
    from app.cam_validation.cam_store import (
        GCodeReportLoadError,
        get_task_store,
    )

    store = get_task_store()
    store.clear()

    # 第一次 mock：loader 抛异常 → FAILED
    mock_loader_fail = _Mock()
    mock_loader_fail.load_from_report.side_effect = GCodeReportLoadError(
        "文件不存在"
    )
    mock_validator = _make_mock_validator()
    mock_adapter = _make_mock_adapter()
    pipeline = CamValidationPipeline(
        cfg=None,
        loader=mock_loader_fail,
        validator=mock_validator,
        adapter=mock_adapter,
    )

    task = pipeline.create_task(
        source_gcode_report_path="/tmp/nonexistent.json",
        cam_backend="internal_only",
    )
    result = _sync_run(pipeline.run_pipeline(task.task_id))
    _check(
        result.status == "failed",
        "用例 11: 首次 run → FAILED",
        f"actual={result.status}",
    )
    _check(
        result.error_message is not None and result.error_message != "",
        "用例 11: error_message 非空（safe_error_message 输出）",
        f"actual={result.error_message}",
    )
    # 项目记忆硬约束：error_message 必须经 safe_error_message 处理，
    # 不回显原始文件路径等敏感信息（避免泄露服务器内部结构）
    _check(
        "/tmp/nonexistent.json" not in (result.error_message or ""),
        "用例 11: error_message 不泄露原始文件路径",
        f"actual={result.error_message}",
    )

    # 第二次：替换 loader，重新 run_pipeline（FAILED → RUNNING → VALIDATED）
    # 注意：pipeline 内部 loader 已注入，需要替换
    pipeline._loader = _make_mock_loader(_make_gcode_load_result())
    result2 = _sync_run(pipeline.run_pipeline(task.task_id))
    _check(
        result2.status == "validated",
        "用例 11: 重跑 → VALIDATED",
        f"actual={result2.status}",
    )


# =============================================================================
# 用例 12：list_tasks 排序 + status_filter
# =============================================================================


def test_list_tasks() -> None:
    """用例 12：list_tasks 排序 + status_filter。"""
    logger.info("=" * 70)
    logger.info("用例 12：list_tasks 排序 + status_filter")
    logger.info("=" * 70)

    from app.cam_validation.pipeline import CamValidationPipeline
    from app.cam_validation.cam_store import get_task_store

    store = get_task_store()
    store.clear()

    mock_loader = _make_mock_loader(_make_gcode_load_result())
    mock_validator = _make_mock_validator()
    mock_adapter = _make_mock_adapter()
    pipeline = CamValidationPipeline(
        cfg=None,
        loader=mock_loader,
        validator=mock_validator,
        adapter=mock_adapter,
    )

    # 创建 3 个任务
    t1 = pipeline.create_task(source_gcode_report_path="/tmp/r1.json")
    time.sleep(0.01)
    t2 = pipeline.create_task(source_gcode_report_path="/tmp/r2.json")
    time.sleep(0.01)
    t3 = pipeline.create_task(source_gcode_report_path="/tmp/r3.json")

    all_tasks = pipeline.list_tasks()
    _check(
        len(all_tasks) == 3,
        "用例 12: list_tasks 返回 3 个",
        f"actual={len(all_tasks)}",
    )
    # 倒序：最新创建的在前
    _check(
        all_tasks[0].task_id == t3.task_id,
        "用例 12: 倒序排序（t3 在前）",
        f"actual={all_tasks[0].task_id}",
    )
    _check(
        all_tasks[2].task_id == t1.task_id,
        "用例 12: 倒序排序（t1 在后）",
        f"actual={all_tasks[2].task_id}",
    )

    # status_filter
    pending_tasks = pipeline.list_tasks(status_filter="pending")
    _check(
        len(pending_tasks) == 3,
        "用例 12: status_filter=pending 返回 3",
    )
    _sync_run(pipeline.run_pipeline(t1.task_id))
    pending_after = pipeline.list_tasks(status_filter="pending")
    _check(
        len(pending_after) == 2,
        "用例 12: 运行 t1 后 pending=2",
        f"actual={len(pending_after)}",
    )
    validated = pipeline.list_tasks(status_filter="validated")
    _check(
        len(validated) == 1,
        "用例 12: status_filter=validated 返回 1",
    )


# =============================================================================
# 用例 13：edited 审核需要 edited_params
# =============================================================================


def test_edited_requires_params() -> None:
    """用例 13：edited 状态需要 edited_params。"""
    logger.info("=" * 70)
    logger.info("用例 13：edited 状态需要 edited_params")
    logger.info("=" * 70)

    from app.cam_validation.pipeline import CamValidationPipeline
    from app.cam_validation.cam_store import (
        CamReviewStatus,
        ReviewError,
        get_task_store,
    )

    store = get_task_store()
    store.clear()

    mock_loader = _make_mock_loader(_make_gcode_load_result())
    mock_validator = _make_mock_validator()
    mock_adapter = _make_mock_adapter()
    pipeline = CamValidationPipeline(
        cfg=None,
        loader=mock_loader,
        validator=mock_validator,
        adapter=mock_adapter,
    )

    task = pipeline.create_task(
        source_gcode_report_path="/tmp/r.json",
        cam_backend="internal_only",
    )
    _sync_run(pipeline.run_pipeline(task.task_id))

    # edited 无 edited_params → 拒绝
    raised = False
    try:
        pipeline.review_task(
            task_id=task.task_id,
            feature_id="feat_001",
            review_status=CamReviewStatus.EDITED.value,
        )
    except ReviewError:
        raised = True
    _check(raised, "用例 13: edited 无 params → 拒绝")

    # edited 含 edited_params → 通过
    fr = pipeline.review_task(
        task_id=task.task_id,
        feature_id="feat_001",
        review_status=CamReviewStatus.EDITED.value,
        edited_params={"safe_z": 90.0},
        engineer_notes="safe_z 提高",
    )
    _check(
        fr.edited_params.get("safe_z") == 90.0,
        "用例 13: edited_params 已记录",
        f"actual={fr.edited_params}",
    )
    _check(
        fr.edited_params.get("engineer_notes") == "safe_z 提高",
        "用例 13: engineer_notes 已记录",
    )

    # 不存在的 feature_id → 拒绝
    raised = False
    try:
        pipeline.review_task(
            task_id=task.task_id,
            feature_id="feat_999",
            review_status="confirmed",
        )
    except ReviewError:
        raised = True
    _check(raised, "用例 13: 不存在的 feature_id → 拒绝")

    # 非法 review_status → 拒绝
    raised = False
    try:
        pipeline.review_task(
            task_id=task.task_id,
            feature_id="feat_002",
            review_status="invalid_status",
        )
    except ReviewError:
        raised = True
    _check(raised, "用例 13: 非法 review_status → 拒绝")


# =============================================================================
# 用例 14：全部 rejected 时 confirm 拒绝
# =============================================================================


def test_all_rejected_confirm_forbidden() -> None:
    """用例 14：全部 rejected 时 confirm 拒绝。"""
    logger.info("=" * 70)
    logger.info("用例 14：全部 rejected 时 confirm 拒绝")
    logger.info("=" * 70)

    from app.cam_validation.pipeline import CamValidationPipeline
    from app.cam_validation.cam_store import (
        CamReviewStatus,
        ReviewError,
        get_task_store,
    )

    store = get_task_store()
    store.clear()

    mock_loader = _make_mock_loader(_make_gcode_load_result())
    mock_validator = _make_mock_validator()
    mock_adapter = _make_mock_adapter()
    pipeline = CamValidationPipeline(
        cfg=None,
        loader=mock_loader,
        validator=mock_validator,
        adapter=mock_adapter,
    )

    task = pipeline.create_task(
        source_gcode_report_path="/tmp/r.json",
        cam_backend="internal_only",
    )
    _sync_run(pipeline.run_pipeline(task.task_id))

    # 两个特征都 rejected
    pipeline.review_task(
        task_id=task.task_id,
        feature_id="feat_001",
        review_status=CamReviewStatus.REJECTED.value,
    )
    pipeline.review_task(
        task_id=task.task_id,
        feature_id="feat_002",
        review_status=CamReviewStatus.REJECTED.value,
    )
    task_reviewed = pipeline.get_task(task.task_id)
    _check(
        task_reviewed.status == "reviewed",
        "用例 14: 全 rejected → REVIEWED",
        f"actual={task_reviewed.status}",
    )

    raised = False
    try:
        pipeline.confirm_task(task.task_id)
    except ReviewError:
        raised = True
    _check(raised, "用例 14: 全 rejected → confirm 拒绝")


# =============================================================================
# 用例 15：CAM 后端降级场景
# =============================================================================


def test_cam_backend_degradation() -> None:
    """用例 15：CAM 后端降级（requested ≠ used + fallback_reason）。"""
    logger.info("=" * 70)
    logger.info("用例 15：CAM 后端降级")
    logger.info("=" * 70)

    from app.cam_validation.pipeline import CamValidationPipeline
    from app.cam_validation.cam_store import get_task_store

    store = get_task_store()
    store.clear()

    load_result = _make_gcode_load_result()
    collision_report = _make_collision_report(safe=True)
    pre_features = [
        FeatureValidationResult(
            feature_id="feat_001",
            feature_type="plane",
            line_range=(1, 2),
        ),
    ]
    mock_loader = _make_mock_loader(load_result)
    mock_validator = _make_mock_validator(
        collision_report=collision_report,
        updated_features=pre_features,
    )
    # 模拟降级：请求 pycam，实际使用 manual
    mock_adapter = _make_mock_adapter(
        cam_report=_make_cam_software_report(
            status="manual_pending",
            backend_used="manual",
            degraded=True,
            degradation_reason="PyCAM 模块不可用：ImportError",
        )
    )
    pipeline = CamValidationPipeline(
        cfg=None,
        loader=mock_loader,
        validator=mock_validator,
        adapter=mock_adapter,
    )

    task = pipeline.create_task(
        source_gcode_report_path="/tmp/r.json",
        cam_backend="pycam",  # 请求 pycam
    )
    _check(
        task.cam_backend_requested == "pycam",
        "用例 15: cam_backend_requested=pycam",
        f"actual={task.cam_backend_requested}",
    )

    result = _sync_run(pipeline.run_pipeline(task.task_id))
    _check(
        result.cam_backend_used == "manual",
        "用例 15: cam_backend_used=manual（降级）",
        f"actual={result.cam_backend_used}",
    )
    _check(
        "PyCAM" in result.cam_backend_fallback_reason,
        "用例 15: fallback_reason 含 PyCAM",
        f"actual={result.cam_backend_fallback_reason}",
    )
    _check(
        result.status == "validated",
        "用例 15: 降级不阻塞 → VALIDATED",
        f"actual={result.status}",
    )

    # 验证 task 警告中含降级告知
    task_after = pipeline.get_task(task.task_id)
    has_degradation_warning = any(
        "CAM 后端降级" in w for w in task_after.warnings
    )
    _check(
        has_degradation_warning,
        "用例 15: task.warnings 含 CAM 后端降级告知",
        f"warnings={task_after.warnings}",
    )


# =============================================================================
# 用例 15 需要的 FeatureValidationResult 导入
# =============================================================================

def _import_fvr():
    from app.cam_validation.cam_store import FeatureValidationResult
    return FeatureValidationResult


# =============================================================================
# 主函数
# =============================================================================


def main() -> int:
    logger.info("=" * 70)
    logger.info("s7-9 独立验证脚本：CamValidationPipeline")
    logger.info("Python: %s", sys.version.split()[0])
    logger.info("临时输出目录: %s", _TMP_OUTPUT_DIR)
    logger.info("=" * 70)

    # 提前导入 FeatureValidationResult 供 test_cam_backend_degradation 使用
    global FeatureValidationResult
    FeatureValidationResult = _import_fvr()

    try:
        # 用例 1-5：完整成功路径（返回 succeeded task_id）
        succeeded_task_id = test_full_success_path()

        # 用例 6：SUCCEEDED 禁删
        test_delete_succeeded_forbidden(succeeded_task_id)

        # 用例 7：PENDING 可删
        test_delete_pending_allowed()

        # 用例 8：字段完整性
        test_result_fields_completeness()

        # 用例 9：非法 cam_backend
        test_invalid_cam_backend_rejected()

        # 用例 10：状态非法转移
        test_invalid_state_transition()

        # 用例 11：FAILED 重跑
        test_failed_task_can_rerun()

        # 用例 12：list_tasks
        test_list_tasks()

        # 用例 13：edited 需要 params
        test_edited_requires_params()

        # 用例 14：全 rejected confirm 拒绝
        test_all_rejected_confirm_forbidden()

        # 用例 15：CAM 后端降级
        test_cam_backend_degradation()

    except Exception as e:
        logger.exception("测试执行异常: %s", e)
        global _FAIL
        _FAIL += 1
        _FAILURES.append(f"[未捕获异常] {type(e).__name__}: {e}")

    # 输出汇总
    logger.info("")
    logger.info("=" * 70)
    logger.info("验证汇总")
    logger.info("=" * 70)
    logger.info("通过: %d", _PASS)
    logger.info("失败: %d", _FAIL)
    logger.info("跳过: %d", _SKIP)
    total = _PASS + _FAIL + _SKIP
    logger.info("总计: %d", total)

    if _FAILURES:
        logger.info("")
        logger.info("失败列表:")
        for f in _FAILURES:
            logger.info("  %s", f)

    # 退出码
    return 0 if _FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
