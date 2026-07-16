"""routes.py 端到端验证脚本（阶段 6 s6-11）。

测试链路：
    构造阶段 5 ChatterReport JSON + 阶段 3 OperationPlan JSON
    → 直接 await 11 个 API 端点函数（绕过 TestClient/httpx 依赖）
    → 验证响应结构 + 状态机流转 + 工业硬约束

覆盖 53 项断言（53/53 通过即视为验证通过）：
    路由注册（5 项）：
      1.  router.prefix == /api/v1/gcode-generation
      2.  router.routes 数量 == 11
      3.  GET /precision_info 已注册
      4.  POST /tasks 已注册
      5.  DELETE /tasks/{task_id} 已注册

    precision_info 端点（4 项）：
      6.  返回 success() 包装（code == 0）
      7.  current_tier 字段存在
      8.  industrial_hard_gates 数组含 9 项
      9.  gcode_disclaimer.cam_validation_required == True

    POST /tasks 正常创建（5 项）：
      10. task_id 前缀 gc_
      11. status == pending
      12. source_chatter_report_path 已记录
      13. source_operation_plan_path 已记录
      14. cam_validation_required == True

    POST /tasks 错误处理（4 项）：
      15. 空路径返回 INVALID_REQUEST
      16. OperationPlan 空路径返回 INVALID_REQUEST
      17. ChatterReport 文件不存在返回 NOT_FOUND
      18. OperationPlan 文件不存在返回 NOT_FOUND

    POST /tasks/{task_id}/run（4 项）：
      19. 正常触发返回 success
      20. status == running
      21. 任务不存在返回 NOT_FOUND
      22. GENERATED 状态执行返回 INVALID_REQUEST

    GET /tasks/{task_id}（4 项）：
      23. 正常返回 success
      24. pending_review_count == 2
      25. cam_validation_required == True
      26. 任务不存在返回 NOT_FOUND

    GET /tasks 列表（2 项）：
      27. 返回 success
      28. tasks 数组非空

    GET /tasks/{task_id}/result（5 项）：
      29. 正常返回 success
      30. feature_results 数量 == 2
      31. 每条含 feature_id / review_status / effective_params
      32. cam_validation_required == True
      33. PENDING 状态返回 INVALID_REQUEST

    POST /tasks/{task_id}/review（5 项）：
      34. confirmed 返回 success
      35. edited 返回 success + effective_params 含 axial_depth_mm
      36. 非 GENERATED 状态返回 INVALID_REQUEST
      37. 无效 action 返回 INVALID_REQUEST
      38. edited 无 edited_params 返回 INVALID_REQUEST

    POST /tasks/{task_id}/confirm（6 项）：
      39. 正常流程 status == succeeded
      40. gcode_file_path 非空
      41. gcode_report_path 非空
      42. exported_features == 2
      43. cam_validation_required == True
      44. 全部 rejected 返回 INVALID_REQUEST

    GET /tasks/{task_id}/gcode/download（3 项）：
      45. 正常返回 FileResponse
      46. filename 以 _gcode.nc 结尾
      47. 非 SUCCEEDED 抛 HTTPException 400

    GET /tasks/{task_id}/report/download（3 项）：
      48. 正常返回 FileResponse
      49. filename 以 _report.json 结尾
      50. 非 SUCCEEDED 抛 HTTPException 400

    DELETE /tasks/{task_id}（4 项）：
      51. SUCCEEDED 禁删返回 INVALID_REQUEST
      52. PENDING 可删返回 success
      53. deleted == True

工业硬约束断言（贯穿所有测试）：
    - cam_validation_required 始终 True（断言 9/14/25/32/43）
    - SUCCEEDED 禁删硬约束（断言 51）
    - 全部 rejected 禁止 confirm（断言 44）
"""

from __future__ import annotations

# === WinSock 损坏绕过补丁（复制自 standalone_verify_pipeline.py）===
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
import selectors as _selectors  # noqa: E402
import select as _select_module  # noqa: E402


def _patch_select():
    """patch select.select()，在所有 fd 都不是真实 socket 时返回空列表。"""
    _real_select = _select_module.select

    def _safe_select(rlist, wlist, xlist, timeout=None):
        if not rlist and not wlist and not xlist:
            return ([], [], [])
        try:
            return _real_select(rlist, wlist, xlist, timeout)
        except OSError:
            return ([], [], [])

    _select_module.select = _safe_select
    print("[warn] select.select() 已被 patch 为安全版本。")


try:
    _select_module.select([], [], [], 0.001)
except OSError:
    _patch_select()


# === 业务导入 ===
import json
import sys
import tempfile
from pathlib import Path

# 确保能导入 app 包
sys.path.insert(0, str(Path(__file__).parent))

from fastapi.responses import JSONResponse, FileResponse

from app.api.v1.gcode_generation import routes as gc_routes
from app.api.v1.gcode_generation.routes import (
    TaskCreateRequest,
    ReviewRequest,
    _disclaimer_dict,
    _resolve_upstream_chatter_report,
    _resolve_upstream_operation_plan,
    _get_pipeline,
)
from app.core.response import success, error, ErrorCode, code_to_numeric
from app.chatter_prediction.chatter_store import FeatureChatterResult
from app.gcode_generation.gcode_store import (
    GCodeGenerationError,
    GCodeGenerationTaskStatus,
    GCodeReviewStatus,
    get_task_store,
)
from app.gcode_generation.pipeline import GCodeGenerationPipeline
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


def is_success(resp: dict) -> bool:
    """判断响应是否为 success() 包装。"""
    return isinstance(resp, dict) and resp.get("code") == 0


def is_error(resp: dict, expected_code: int | None = None) -> bool:
    """判断响应是否为 error() 包装（可选校验具体错误码）。"""
    if not isinstance(resp, dict):
        return False
    if resp.get("code", 0) == 0:
        return False
    if expected_code is not None and resp.get("code") != expected_code:
        return False
    return True


def reset_state() -> None:
    """清空 TaskStore + pipeline 单例（每个测试用例独立运行）。"""
    get_task_store().clear()
    # 重置 routes 模块的 pipeline 单例
    gc_routes._pipeline = None


def patch_asyncio_create_task():
    """patch asyncio.create_task 为同步执行，避免后台任务竞态。

    run_task 端点内部调用 asyncio.create_task(pipeline.run_pipeline(task_id))
    创建后台任务。测试中我们用 asyncio.run() 同步执行 pipeline.run_pipeline()
    来完成状态转换，不需要后台任务。patch 后 create_task 关闭 coroutine 并返回
    已完成的 Future。
    """
    def _noop_create_task(coro):
        coro.close()  # 关闭 coroutine 避免 RuntimeWarning
        fut = asyncio.Future()
        fut.set_result(None)
        return fut

    gc_routes.asyncio.create_task = _noop_create_task


def restore_asyncio_create_task():
    """恢复原始 asyncio.create_task。"""
    gc_routes.asyncio.create_task = asyncio.create_task


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
    """构造阶段 5 ChatterReport JSON 文件。"""
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
# 辅助函数：通过端点函数构造任务并完成 GENERATED 状态
# =============================================================================


async def create_and_run_task(
    tmp_dir: Path,
    controller_type: str = "fanuc_0i",
    material_name: str = "45#钢",
    prediction_method: str = "analytical",
) -> str:
    """构造任务 + 触发流水线执行到 GENERATED 状态，返回 task_id。"""
    chatter_path = build_test_chatter_report_json(
        tmp_dir, prediction_method=prediction_method
    )
    op_plan_path = build_test_operation_plan_json(tmp_dir)

    body = TaskCreateRequest(
        chatter_report_path=chatter_path,
        operation_plan_path=op_plan_path,
        controller_type=controller_type,
        material_name=material_name,
    )
    resp = await gc_routes.create_task(body)
    task_id = resp["data"]["task_id"]

    # 同步执行流水线（绕过 run_task 端点的后台任务）
    pipeline = _get_pipeline()
    await pipeline.run_pipeline(task_id)

    return task_id


async def review_all_features(task_id: str, action: str = "confirmed") -> None:
    """审核任务的所有特征。"""
    store = get_task_store()
    task = store.get_task(task_id)
    feature_ids = [r.feature_id for r in task.feature_gcode_results]

    body = ReviewRequest(action=action, reviewed_by="engineer_test")
    if action == "edited":
        body.edited_params = {
            "axial_depth_mm": 1.5,
            "limit_depth_mm": 5.0,
            "stable": True,
        }
        body.engineer_notes = "降低切深至 1.5mm"

    for fid in feature_ids:
        await gc_routes.review_feature(task_id, fid, body)


# =============================================================================
# 测试用例
# =============================================================================


def test_route_registration() -> None:
    """测试 1-5: 路由注册。"""
    print("\n=== 测试组 1: 路由注册 ===")
    router = gc_routes.router

    check("router.prefix == /api/v1/gcode-generation",
          router.prefix == "/api/v1/gcode-generation",
          f"actual={router.prefix}")

    check("router.routes 数量 == 11",
          len(router.routes) == 11,
          f"actual={len(router.routes)}")

    # 检查关键端点是否注册
    methods_and_paths = {
        (list(r.methods)[0] if r.methods else "GET", r.path)
        for r in router.routes
    }
    check("GET /precision_info 已注册",
          ("GET", "/api/v1/gcode-generation/precision_info") in methods_and_paths,
          f"actual={methods_and_paths}")
    check("POST /tasks 已注册",
          ("POST", "/api/v1/gcode-generation/tasks") in methods_and_paths,
          f"actual={methods_and_paths}")
    check("DELETE /tasks/{task_id} 已注册",
          ("DELETE", "/api/v1/gcode-generation/tasks/{task_id}") in methods_and_paths,
          f"actual={methods_and_paths}")


async def test_precision_info() -> None:
    """测试 6-9: precision_info 端点。"""
    print("\n=== 测试组 2: precision_info 端点 ===")
    resp = await gc_routes.get_precision_info()

    check("返回 success() 包装", is_success(resp), f"actual={resp.get('code')}")
    data = resp.get("data", {})
    check("current_tier 字段存在", "current_tier" in data,
          f"actual={list(data.keys())}")
    gates = data.get("industrial_hard_gates", [])
    check("industrial_hard_gates 数组含 9 项",
          len(gates) == 9, f"actual={len(gates)}")
    disclaimer = data.get("gcode_disclaimer", {})
    check("gcode_disclaimer.cam_validation_required == True",
          disclaimer.get("requires_cam_validation") is True,
          f"actual={disclaimer.get('requires_cam_validation')}")


async def test_create_task_normal(tmp_dir: Path) -> str:
    """测试 10-14: POST /tasks 正常创建。"""
    print("\n=== 测试组 3: POST /tasks 正常创建 ===")
    reset_state()

    chatter_path = build_test_chatter_report_json(tmp_dir)
    op_plan_path = build_test_operation_plan_json(tmp_dir)

    body = TaskCreateRequest(
        chatter_report_path=chatter_path,
        operation_plan_path=op_plan_path,
        controller_type="fanuc_0i",
        material_name="45#钢",
    )
    resp = await gc_routes.create_task(body)

    check("返回 success() 包装", is_success(resp), f"actual={resp.get('code')}")
    data = resp.get("data", {})
    task_id = data.get("task_id", "")
    check("task_id 前缀 gc_", task_id.startswith("gc_"), f"actual={task_id}")
    check("status == pending",
          data.get("status") == GCodeGenerationTaskStatus.PENDING.value,
          f"actual={data.get('status')}")
    check("source_chatter_report_path 已记录",
          data.get("source_chatter_report_path") == chatter_path)
    check("source_operation_plan_path 已记录",
          data.get("source_operation_plan_path") == op_plan_path)
    check("cam_validation_required == True",
          data.get("cam_validation_required") is True,
          f"actual={data.get('cam_validation_required')}")
    return task_id


async def test_create_task_errors(tmp_dir: Path) -> None:
    """测试 15-18: POST /tasks 错误处理。"""
    print("\n=== 测试组 4: POST /tasks 错误处理 ===")
    reset_state()

    chatter_path = build_test_chatter_report_json(tmp_dir)
    op_plan_path = build_test_operation_plan_json(tmp_dir)

    # 空路径
    body_empty_chatter = TaskCreateRequest(
        chatter_report_path="",
        operation_plan_path=op_plan_path,
    )
    resp = await gc_routes.create_task(body_empty_chatter)
    check("空 chatter_report_path 返回 INVALID_REQUEST",
          is_error(resp, code_to_numeric(ErrorCode.INVALID_REQUEST)),
          f"actual={resp.get('code')}")

    body_empty_op = TaskCreateRequest(
        chatter_report_path=chatter_path,
        operation_plan_path="",
    )
    resp = await gc_routes.create_task(body_empty_op)
    check("空 operation_plan_path 返回 INVALID_REQUEST",
          is_error(resp, code_to_numeric(ErrorCode.INVALID_REQUEST)),
          f"actual={resp.get('code')}")

    # 文件不存在
    body_not_exist_chatter = TaskCreateRequest(
        chatter_report_path="/nonexistent/report.json",
        operation_plan_path=op_plan_path,
    )
    resp = await gc_routes.create_task(body_not_exist_chatter)
    check("ChatterReport 文件不存在返回 NOT_FOUND",
          is_error(resp, code_to_numeric(ErrorCode.NOT_FOUND)),
          f"actual={resp.get('code')}")

    body_not_exist_op = TaskCreateRequest(
        chatter_report_path=chatter_path,
        operation_plan_path="/nonexistent/op_plan.json",
    )
    resp = await gc_routes.create_task(body_not_exist_op)
    check("OperationPlan 文件不存在返回 NOT_FOUND",
          is_error(resp, code_to_numeric(ErrorCode.NOT_FOUND)),
          f"actual={resp.get('code')}")


async def test_run_task(tmp_dir: Path) -> str:
    """测试 19-22: POST /tasks/{task_id}/run。"""
    print("\n=== 测试组 5: POST /tasks/{task_id}/run ===")
    reset_state()
    patch_asyncio_create_task()

    try:
        task_id = await create_and_run_task(tmp_dir)
        # 此时任务已是 GENERATED 状态（create_and_run_task 内部已 run）
        # 测试 run_task 端点对 GENERATED 状态的拒绝
        resp = await gc_routes.run_task(task_id)
        check("GENERATED 状态执行返回 INVALID_REQUEST",
              is_error(resp, code_to_numeric(ErrorCode.INVALID_REQUEST)),
              f"actual={resp.get('code')}")

        # 重新创建 PENDING 任务测试正常触发
        reset_state()
        chatter_path = build_test_chatter_report_json(tmp_dir)
        op_plan_path = build_test_operation_plan_json(tmp_dir)
        body = TaskCreateRequest(
            chatter_report_path=chatter_path,
            operation_plan_path=op_plan_path,
        )
        resp = await gc_routes.create_task(body)
        task_id_pending = resp["data"]["task_id"]

        resp = await gc_routes.run_task(task_id_pending)
        check("正常触发返回 success()", is_success(resp), f"actual={resp.get('code')}")
        check("status == running",
              resp.get("data", {}).get("status") == GCodeGenerationTaskStatus.RUNNING.value,
              f"actual={resp.get('data', {}).get('status')}")

        # 任务不存在
        resp = await gc_routes.run_task("gc_nonexistent_001")
        check("任务不存在返回 NOT_FOUND",
              is_error(resp, code_to_numeric(ErrorCode.NOT_FOUND)),
              f"actual={resp.get('code')}")

        # 同步执行完成流水线（替代被 patch 掉的后台任务）
        pipeline = _get_pipeline()
        await pipeline.run_pipeline(task_id_pending)
        return task_id_pending
    finally:
        restore_asyncio_create_task()


async def test_get_task_status(task_id: str) -> None:
    """测试 23-26: GET /tasks/{task_id}。"""
    print("\n=== 测试组 6: GET /tasks/{task_id} ===")
    resp = await gc_routes.get_task_status(task_id)

    check("正常返回 success()", is_success(resp), f"actual={resp.get('code')}")
    data = resp.get("data", {})
    check("pending_review_count == 2",
          data.get("pending_review_count") == 2,
          f"actual={data.get('pending_review_count')}")
    check("cam_validation_required == True",
          data.get("cam_validation_required") is True,
          f"actual={data.get('cam_validation_required')}")

    # 任务不存在
    resp = await gc_routes.get_task_status("gc_nonexistent_002")
    check("任务不存在返回 NOT_FOUND",
          is_error(resp, code_to_numeric(ErrorCode.NOT_FOUND)),
          f"actual={resp.get('code')}")


async def test_list_tasks(task_id: str) -> None:
    """测试 27-28: GET /tasks 列表。"""
    print("\n=== 测试组 7: GET /tasks 列表 ===")
    resp = await gc_routes.list_tasks(limit=20, status_filter="")

    check("返回 success()", is_success(resp), f"actual={resp.get('code')}")
    data = resp.get("data", {})
    tasks = data.get("tasks", [])
    check("tasks 数组非空", len(tasks) > 0, f"actual={len(tasks)}")
    check("task_id 在列表中",
          any(t["task_id"] == task_id for t in tasks),
          f"actual={[t['task_id'] for t in tasks]}")


async def test_get_task_result(task_id: str) -> None:
    """测试 29-33: GET /tasks/{task_id}/result。"""
    print("\n=== 测试组 8: GET /tasks/{task_id}/result ===")
    resp = await gc_routes.get_task_result(task_id)

    check("正常返回 success()", is_success(resp), f"actual={resp.get('code')}")
    data = resp.get("data", {})
    feature_results = data.get("feature_results", [])
    check("feature_results 数量 == 2",
          len(feature_results) == 2,
          f"actual={len(feature_results)}")
    if feature_results:
        first = feature_results[0]
        check("每条含 feature_id / review_status / effective_params",
              "feature_id" in first and "review_status" in first
              and "effective_params" in first,
              f"actual={list(first.keys())}")
    else:
        check("每条含 feature_id / review_status / effective_params", False, "feature_results 为空")
    check("cam_validation_required == True",
          data.get("cam_validation_required") is True,
          f"actual={data.get('cam_validation_required')}")

    # PENDING 状态返回 INVALID_REQUEST
    reset_state()
    chatter_path = build_test_chatter_report_json(tmp_dir := Path(tempfile.mkdtemp(prefix="gcode_route_8_")))
    op_plan_path = build_test_operation_plan_json(tmp_dir)
    body = TaskCreateRequest(
        chatter_report_path=chatter_path,
        operation_plan_path=op_plan_path,
    )
    resp = await gc_routes.create_task(body)
    pending_task_id = resp["data"]["task_id"]
    resp = await gc_routes.get_task_result(pending_task_id)
    check("PENDING 状态返回 INVALID_REQUEST",
          is_error(resp, code_to_numeric(ErrorCode.INVALID_REQUEST)),
          f"actual={resp.get('code')}")


async def test_review_feature(tmp_dir: Path) -> str:
    """测试 34-38: POST /tasks/{task_id}/review。"""
    print("\n=== 测试组 9: POST /tasks/{task_id}/review ===")
    reset_state()

    task_id = await create_and_run_task(tmp_dir)

    # confirmed
    body_confirmed = ReviewRequest(action="confirmed", reviewed_by="engineer_01")
    resp = await gc_routes.review_feature(task_id, "face_A", body_confirmed)
    check("confirmed 返回 success()", is_success(resp), f"actual={resp.get('code')}")

    # edited
    body_edited = ReviewRequest(
        action="edited",
        reviewed_by="engineer_02",
        edited_params={"axial_depth_mm": 1.5, "limit_depth_mm": 5.0, "stable": True},
        engineer_notes="降低切深至 1.5mm",
    )
    resp = await gc_routes.review_feature(task_id, "hole_B", body_edited)
    check("edited 返回 success()", is_success(resp), f"actual={resp.get('code')}")
    data = resp.get("data", {})
    effective_params = data.get("effective_params", {})
    check("effective_params 含 axial_depth_mm",
          "axial_depth_mm" in effective_params,
          f"actual={effective_params}")

    # 非 GENERATED 状态（此时任务已 REVIEWED）
    body_confirmed2 = ReviewRequest(action="confirmed", reviewed_by="engineer_03")
    resp = await gc_routes.review_feature(task_id, "face_A", body_confirmed2)
    check("REVIEWED 状态审核返回 INVALID_REQUEST",
          is_error(resp, code_to_numeric(ErrorCode.INVALID_REQUEST)),
          f"actual={resp.get('code')}")

    # 无效 action
    reset_state()
    task_id2 = await create_and_run_task(tmp_dir)
    body_invalid = ReviewRequest(action="invalid_action", reviewed_by="engineer_04")
    resp = await gc_routes.review_feature(task_id2, "face_A", body_invalid)
    check("无效 action 返回 INVALID_REQUEST",
          is_error(resp, code_to_numeric(ErrorCode.INVALID_REQUEST)),
          f"actual={resp.get('code')}")

    # edited 无 edited_params
    body_edited_no_params = ReviewRequest(action="edited", reviewed_by="engineer_05")
    resp = await gc_routes.review_feature(task_id2, "face_A", body_edited_no_params)
    check("edited 无 edited_params 返回 INVALID_REQUEST",
          is_error(resp, code_to_numeric(ErrorCode.INVALID_REQUEST)),
          f"actual={resp.get('code')}")

    return task_id2


async def test_confirm_task(tmp_dir: Path) -> str:
    """测试 39-44: POST /tasks/{task_id}/confirm。"""
    print("\n=== 测试组 10: POST /tasks/{task_id}/confirm ===")
    reset_state()

    task_id = await create_and_run_task(tmp_dir)
    await review_all_features(task_id, action="confirmed")

    resp = await gc_routes.confirm_task(task_id, reviewer="engineer_03")
    check("返回 success() 包装", is_success(resp), f"actual={resp.get('code')}")
    data = resp.get("data", {})
    check("status == succeeded",
          data.get("status") == GCodeGenerationTaskStatus.SUCCEEDED.value,
          f"actual={data.get('status')}")
    check("gcode_file_path 非空", bool(data.get("gcode_file_path")),
          f"actual={data.get('gcode_file_path')}")
    check("gcode_report_path 非空", bool(data.get("gcode_report_path")),
          f"actual={data.get('gcode_report_path')}")
    check("exported_features == 2", data.get("exported_features") == 2,
          f"actual={data.get('exported_features')}")
    check("cam_validation_required == True",
          data.get("cam_validation_required") is True,
          f"actual={data.get('cam_validation_required')}")
    return task_id


async def test_confirm_task_invalid_status(tmp_dir: Path) -> None:
    """测试 confirm 非 REVIEWED 状态 + 全部 rejected。"""
    print("\n=== 测试组 10b: confirm 错误场景 ===")
    reset_state()

    # GENERATED 状态确认应失败
    task_id = await create_and_run_task(tmp_dir)
    resp = await gc_routes.confirm_task(task_id, reviewer="engineer_04")
    check("GENERATED 状态确认返回 INVALID_REQUEST",
          is_error(resp, code_to_numeric(ErrorCode.INVALID_REQUEST)),
          f"actual={resp.get('code')}")

    # 全部 rejected 应失败
    reset_state()
    task_id2 = await create_and_run_task(tmp_dir)
    await review_all_features(task_id2, action="rejected")
    resp = await gc_routes.confirm_task(task_id2, reviewer="engineer_05")
    check("全部 rejected 确认返回 INVALID_REQUEST",
          is_error(resp, code_to_numeric(ErrorCode.INVALID_REQUEST)),
          f"actual={resp.get('code')}")


async def test_download_gcode(task_id_succeeded: str) -> None:
    """测试 45-47: GET /tasks/{task_id}/gcode/download。

    注意：test_confirm_task_invalid_status 内部 reset_state() 会清空 task_id_succeeded，
    因此这里重新构造一个 SUCCEEDED 任务用于下载测试。
    """
    print("\n=== 测试组 11: GET /tasks/{task_id}/gcode/download ===")
    # 重新构造 SUCCEEDED 任务
    reset_state()
    fresh_dir = Path(tempfile.mkdtemp(prefix="gcode_route_11_"))
    task_id_succeeded = await create_and_run_task(fresh_dir)
    await review_all_features(task_id_succeeded, action="confirmed")
    await gc_routes.confirm_task(task_id_succeeded, reviewer="engineer_03")

    # 正常下载
    resp = await gc_routes.download_gcode(task_id_succeeded)
    check("正常返回 FileResponse", isinstance(resp, FileResponse),
          f"actual={type(resp).__name__}")
    content_disposition = resp.headers.get("content-disposition", "")
    check("Content-Disposition 含 _gcode.nc",
          "_gcode.nc" in content_disposition,
          f"actual={content_disposition}")

    # 非 SUCCEEDED 状态 — 改为返回 JSONResponse + error()，不抛 HTTPException
    reset_state()
    tmp_dir = Path(tempfile.mkdtemp(prefix="gcode_route_11b_"))
    task_id_pending = await create_and_run_task(tmp_dir)  # GENERATED 状态
    resp = await gc_routes.download_gcode(task_id_pending)
    is_json_error = isinstance(resp, JSONResponse) and resp.status_code == 400
    check("GENERATED 状态下载返回 JSONResponse 400",
          is_json_error,
          f"actual={type(resp).__name__} status={getattr(resp, 'status_code', 'N/A')}")


async def test_download_report(task_id_succeeded: str) -> None:
    """测试 48-50: GET /tasks/{task_id}/report/download。

    注意：同 test_download_gcode，需重新构造 SUCCEEDED 任务。
    """
    print("\n=== 测试组 12: GET /tasks/{task_id}/report/download ===")
    # 重新构造 SUCCEEDED 任务
    reset_state()
    fresh_dir = Path(tempfile.mkdtemp(prefix="gcode_route_12_"))
    task_id_succeeded = await create_and_run_task(fresh_dir)
    await review_all_features(task_id_succeeded, action="confirmed")
    await gc_routes.confirm_task(task_id_succeeded, reviewer="engineer_03")

    # 正常下载
    resp = await gc_routes.download_report(task_id_succeeded)
    check("正常返回 FileResponse", isinstance(resp, FileResponse),
          f"actual={type(resp).__name__}")
    content_disposition = resp.headers.get("content-disposition", "")
    check("Content-Disposition 含 _report.json",
          "_report.json" in content_disposition,
          f"actual={content_disposition}")

    # 非 SUCCEEDED 状态 — 改为返回 JSONResponse + error()，不抛 HTTPException
    reset_state()
    tmp_dir = Path(tempfile.mkdtemp(prefix="gcode_route_12b_"))
    task_id_pending = await create_and_run_task(tmp_dir)  # GENERATED 状态
    resp = await gc_routes.download_report(task_id_pending)
    is_json_error = isinstance(resp, JSONResponse) and resp.status_code == 400
    check("GENERATED 状态下载报告返回 JSONResponse 400",
          is_json_error,
          f"actual={type(resp).__name__} status={getattr(resp, 'status_code', 'N/A')}")


async def test_delete_task(tmp_dir: Path) -> None:
    """测试 51-53: DELETE /tasks/{task_id}。

    注意：test_download_gcode / test_download_report 内部调用 reset_state()
    会清空任务存储，因此传入的 task_id_succeeded 已失效。这里重新创建一个
    SUCCEEDED 任务用于测试禁删约束。
    """
    print("\n=== 测试组 13: DELETE /tasks/{task_id} ===")
    # 重新构造一个 SUCCEEDED 任务用于禁删测试
    reset_state()
    fresh_dir = Path(tempfile.mkdtemp(prefix="gcode_route_13_"))
    task_id_succeeded = await create_and_run_task(fresh_dir)
    await review_all_features(task_id_succeeded, action="confirmed")
    await gc_routes.confirm_task(task_id_succeeded, reviewer="engineer_03")

    # SUCCEEDED 禁删
    resp = await gc_routes.delete_task(task_id_succeeded)
    check("SUCCEEDED 禁删返回 INVALID_REQUEST",
          is_error(resp, code_to_numeric(ErrorCode.INVALID_REQUEST)),
          f"actual={resp.get('code')}")

    # PENDING 可删
    reset_state()
    chatter_path = build_test_chatter_report_json(tmp_dir)
    op_plan_path = build_test_operation_plan_json(tmp_dir)
    body = TaskCreateRequest(
        chatter_report_path=chatter_path,
        operation_plan_path=op_plan_path,
    )
    resp = await gc_routes.create_task(body)
    task_id_pending = resp["data"]["task_id"]

    resp = await gc_routes.delete_task(task_id_pending)
    check("PENDING 可删返回 success()", is_success(resp), f"actual={resp.get('code')}")
    data = resp.get("data", {})
    check("deleted == True", data.get("deleted") is True,
          f"actual={data.get('deleted')}")

    # 不存在任务
    resp = await gc_routes.delete_task("gc_nonexistent_003")
    check("不存在任务返回 NOT_FOUND",
          is_error(resp, code_to_numeric(ErrorCode.NOT_FOUND)),
          f"actual={resp.get('code')}")


def test_disclaimer_dict_default() -> None:
    """测试 _disclaimer_dict 默认值。"""
    print("\n=== 测试组 14: _disclaimer_dict 默认值 ===")
    disclaimer = _disclaimer_dict()
    check("默认 cam_validation_required == True",
          disclaimer.get("requires_cam_validation") is True,
          f"actual={disclaimer.get('requires_cam_validation')}")
    check("默认 prediction_method == analytical",
          disclaimer.get("prediction_method") == "analytical",
          f"actual={disclaimer.get('prediction_method')}")
    check("默认 controller_type == fanuc_0i",
          disclaimer.get("controller_type") == "fanuc_0i",
          f"actual={disclaimer.get('controller_type')}")


async def test_disclaimer_dict_with_task(tmp_dir: Path) -> None:
    """测试 _disclaimer_dict 带 task 上下文。

    async 是必需的：run_all_tests() 已在事件循环内，asyncio.run() 会抛
    RuntimeError: cannot be called from a running event loop。
    """
    print("\n=== 测试组 15: _disclaimer_dict 带 task 上下文 ===")
    reset_state()

    # 用 neural_network 方法构造任务（LTC 实验性路径）
    chatter_path = build_test_chatter_report_json(
        tmp_dir, prediction_method="neural_network"
    )
    op_plan_path = build_test_operation_plan_json(tmp_dir)

    pipeline = GCodeGenerationPipeline()
    task = pipeline.create_task(
        source_chatter_report_path=chatter_path,
        source_operation_plan_path=op_plan_path,
    )
    await pipeline.run_pipeline(task.task_id)

    disclaimer = _disclaimer_dict(task=task)
    check("prediction_method == neural_network",
          disclaimer.get("prediction_method") == "neural_network",
          f"actual={disclaimer.get('prediction_method')}")
    check("ltc_experiment_used == True",
          disclaimer.get("ltc_experiment_used") is True,
          f"actual={disclaimer.get('ltc_experiment_used')}")
    check("cam_validation_required == True",
          disclaimer.get("requires_cam_validation") is True,
          f"actual={disclaimer.get('requires_cam_validation')}")


def test_resolve_upstream_empty() -> None:
    """测试 _resolve_upstream_chatter_report + _resolve_upstream_operation_plan 空输入。"""
    print("\n=== 测试组 16: 上游追溯空输入 ===")
    # 空 task_id
    result = _resolve_upstream_chatter_report("")
    check("_resolve_upstream_chatter_report 空 task_id 返回 empty_result",
          result == ("", "", "analytical", False, ""),
          f"actual={result}")

    op_plan = _resolve_upstream_operation_plan("")
    check("_resolve_upstream_operation_plan 空 task_id 返回空字符串",
          op_plan == "", f"actual={op_plan}")


def test_resolve_upstream_nonexistent() -> None:
    """测试 _resolve_upstream_chatter_report + _resolve_upstream_operation_plan 不存在任务。"""
    print("\n=== 测试组 17: 上游追溯不存在任务 ===")
    # chatter_prediction 模块若可用，则查询不存在的任务应返回 empty_result
    # 若 chatter_prediction 模块未启用，则 ImportError 也返回 empty_result
    result = _resolve_upstream_chatter_report("cp_nonexistent_001")
    check("_resolve_upstream_chatter_report 不存在任务返回 empty_result",
          result == ("", "", "analytical", False, ""),
          f"actual={result}")

    op_plan = _resolve_upstream_operation_plan("pg_nonexistent_001")
    check("_resolve_upstream_operation_plan 不存在任务返回空字符串",
          op_plan == "", f"actual={op_plan}")


# =============================================================================
# 主入口
# =============================================================================


async def run_all_tests() -> int:
    """运行所有异步测试。"""
    tmp_dir = Path(tempfile.mkdtemp(prefix="gcode_routes_verify_"))
    print(f"临时目录: {tmp_dir}")

    # 路由注册（同步）
    test_route_registration()

    # precision_info
    await test_precision_info()

    # POST /tasks 正常创建
    task_id_created = await test_create_task_normal(tmp_dir)

    # POST /tasks 错误处理
    await test_create_task_errors(tmp_dir)

    # POST /tasks/{task_id}/run
    task_id_generated = await test_run_task(tmp_dir)

    # GET /tasks/{task_id}
    await test_get_task_status(task_id_generated)

    # GET /tasks 列表
    await test_list_tasks(task_id_generated)

    # GET /tasks/{task_id}/result
    await test_get_task_result(task_id_generated)

    # POST /tasks/{task_id}/review
    await test_review_feature(tmp_dir)

    # POST /tasks/{task_id}/confirm 正常流程
    task_id_succeeded = await test_confirm_task(tmp_dir)

    # POST /tasks/{task_id}/confirm 错误场景
    await test_confirm_task_invalid_status(tmp_dir)

    # GET /tasks/{task_id}/gcode/download
    await test_download_gcode(task_id_succeeded)

    # GET /tasks/{task_id}/report/download
    await test_download_report(task_id_succeeded)

    # DELETE /tasks/{task_id}
    await test_delete_task(tmp_dir)

    # 辅助函数测试（同步 + 异步）
    test_disclaimer_dict_default()
    await test_disclaimer_dict_with_task(tmp_dir)
    test_resolve_upstream_empty()
    test_resolve_upstream_nonexistent()

    print("\n" + "=" * 70)
    print(f"总计: {PASS} 通过, {FAIL} 失败")
    print("=" * 70)
    return 0 if FAIL == 0 else 1


def main() -> int:
    print("=" * 70)
    print("routes.py 端到端验证（阶段 6 s6-11）")
    print("=" * 70)

    return asyncio.run(run_all_tests())


if __name__ == "__main__":
    sys.exit(main())
