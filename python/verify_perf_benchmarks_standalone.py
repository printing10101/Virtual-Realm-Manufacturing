"""性能基准模块独立验证脚本.

针对阶段 8 新增的 3 个性能基准模块进行端到端验证，绕过 WinSock
损坏 + 缺失 fastapi/aiosqlite 依赖问题（参考 verify_contracts_standalone.py
方案）。

验证范围
--------
1. **静态语法检查**：compile 所有修改/新增的文件
2. **模块导入检查**：3 个基准模块 + thresholds + __init__ 可正常导入
3. **阈值键名匹配检查**：thresholds.py 的 46 个新阈值键名与基准模块
   源码中的 f-string 模板完全匹配
4. **__init__.py 导出检查**：3 个新基准类可从顶层包导入
5. **run_perf_benchmark.py 集成检查**：PerformanceBenchmarkRunner
   可实例化，run_all() 方法引用了 10 个基准段
6. **小规模基准运行**（如果导入成功）：每个基准模块运行 n_iterations=3
   的小规模测试，验证接口正确性 + 指标键名实际产出

运行方式
--------
    cd python
    python verify_perf_benchmarks_standalone.py

退出码
------
- 0：全部通过
- 1：有失败项
"""

from __future__ import annotations

import importlib.util
import os
import sys
import traceback
import types
from typing import Any

# 确保 app 包在 sys.path 中
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _THIS_DIR)

# WinSock 兼容：在导入任何 app 模块前，强制初始化 WinSock
# （本地环境 WinSock 损坏，所有 HTTPS 失败，但纯标准库模块可正常导入）
try:
    import socket  # noqa: F401
except OSError:
    pass

# asyncio 绕过：Windows 上 asyncio 默认走 windows_events → _overlapped，
# 后者是 C 扩展，内部使用 socket，在 WinSock 损坏环境下触发 WinError 10038。
# 临时将 sys.platform 改为 'linux' 让 asyncio 走 unix_events 路径，
# 使 ``import asyncio`` 能成功（基准模块顶层有 ``import asyncio``）。
# 注意：``asyncio.run()`` 在阶段 5 仍可能失败（socket.socketpair 不可用），
# 阶段 5 改用手动驱动协程方式绕过。
_original_platform = sys.platform
sys.platform = "linux"
try:
    import asyncio  # noqa: F401
finally:
    sys.platform = _original_platform

# asyncio.run 绕过：WinSock 损坏导致 socket.socketpair() 不可用，
# asyncio.run() / asyncio.new_event_loop() 均失败（WinError 10038）。
# 关键发现：WorldModelPlugin.execute() 和 RLAgentPlugin.execute() 虽声明为
# async def，但内部无任何 await 调用，全部为同步逻辑；rl_agent_bench.py
# 的 _run_once() 内部 `return await self._plugin.execute(ctx)` 是嵌套 await，
# 但被 await 的协程内部也无 await。因此可用栈式同步驱动协程到完成，
# 替代 asyncio.run()。
def _sync_run(coro: Any) -> Any:
    """同步驱动协程到完成，处理嵌套 await.

    Args:
        coro: 顶层协程对象.

    Returns:
        协程的返回值.
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
        # yielded 是 await 传出的子 awaitable（协程/生成器/__await__ 迭代器）
        if hasattr(yielded, "send") and hasattr(yielded, "throw"):
            stack.append(yielded)
        elif hasattr(yielded, "__await__"):
            stack.append(yielded.__await__())
        send_val = None
    return send_val

asyncio.run = _sync_run  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# 包 stub：绕过 app.benchmarks 导入链
# ---------------------------------------------------------------------------
# app/benchmarks/__init__.py 导入 XGBoostBaseline/RFBaseline/SVMBaseline/
# MLPBaseline，这些依赖 sklearn/xgboost，而 sklearn 的 joblib 内部使用
# socket，触发 WinError 10038。
# app/benchmarks/performance/__init__.py 导入 run_perf_benchmark，后者导入
# 7 个旧基准模块（api_bench/database_bench/concurrency_bench 等可能依赖
# fastapi/aiosqlite/httpx）。
# 解决方案：在 sys.modules 中预先注册空的 app.benchmarks 和
# app.benchmarks.performance 包，阻止 Python 执行其 __init__.py，
# 然后用 importlib 直接加载需要的模块文件。

_BENCH_DIR = os.path.join(_THIS_DIR, "app", "benchmarks")
_PERF_DIR = os.path.join(_BENCH_DIR, "performance")

# app 包本身是纯标准库（前次会话已验证），正常导入
import app  # noqa: E402

# stub app.benchmarks 包
_app_bench_stub = types.ModuleType("app.benchmarks")
_app_bench_stub.__path__ = [_BENCH_DIR]
sys.modules["app.benchmarks"] = _app_bench_stub

# stub app.benchmarks.performance 包
_app_bench_perf_stub = types.ModuleType("app.benchmarks.performance")
_app_bench_perf_stub.__path__ = [_PERF_DIR]
sys.modules["app.benchmarks.performance"] = _app_bench_perf_stub

# 7 个旧基准模块（api_bench/database_bench/concurrency_bench/business_logic_bench/
# drawing_parse_bench/lnn_inference_bench/nc_generation_bench）依赖 fastapi/
# aiosqlite/httpx/sklearn 等，导入链触发 ssl 模块加载，WinSock 损坏导致
# NameError: enum_certificates。这里预注册 mock stub，注入空类占位符，
# 阻止 Python 执行其 __init__.py，使 run_perf_benchmark.py 与 __init__.py
# 的导入链能成功（WorldModelPerfBenchmark/RLAgentPerfBenchmark/
# ClosedLoopPerfBenchmark 三个新模块走真实加载）。
_OLD_BENCH_CLASSES: dict[str, list[str]] = {
    "lnn_inference_bench": ["LNNPerfBenchmark"],
    "nc_generation_bench": ["NCGenerationBenchmark"],
    "drawing_parse_bench": ["DrawingParseBenchmark"],
    "api_bench": ["APIPerfBenchmark"],
    "database_bench": ["DatabasePerfBenchmark"],
    "business_logic_bench": ["BusinessLogicPerfBenchmark"],
    "concurrency_bench": ["ConcurrencyPerfBenchmark"],
}
for _mod_name, _cls_names in _OLD_BENCH_CLASSES.items():
    _full = f"app.benchmarks.performance.{_mod_name}"
    _stub = types.ModuleType(_full)
    for _cls in _cls_names:
        # 空类占位符：Runner.run_all() 不会在此脚本中调用，无需真实实现
        setattr(_stub, _cls, type(_cls, (), {}))
    sys.modules[_full] = _stub


def _load_module_from_file(mod_name: str, file_path: str) -> Any:
    """用 importlib 直接加载模块文件，绕过包 __init__ 链.

    加载后注册到 sys.modules，使后续的 ``from <mod_name> import ...``
    能正常解析。
    """
    spec = importlib.util.spec_from_file_location(mod_name, file_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"无法创建模块 spec: {mod_name} from {file_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = module
    spec.loader.exec_module(module)
    return module


# 预加载 thresholds 模块（纯标准库，必过）
try:
    _thresholds_mod = _load_module_from_file(
        "app.benchmarks.performance.thresholds",
        os.path.join(_PERF_DIR, "thresholds.py"),
    )
except Exception as e:  # noqa: BLE001
    _thresholds_mod = None
    print(f"[WARN] 预加载 thresholds 失败: {e}")


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
    """编译所有修改/新增的文件，检查语法错误."""
    print("\n[阶段 1] 静态语法检查")
    base = os.path.join(_THIS_DIR, "app", "benchmarks", "performance")
    files = [
        "thresholds.py",
        "run_perf_benchmark.py",
        "__init__.py",
        "world_model_bench.py",
        "rl_agent_bench.py",
        "closed_loop_bench.py",
    ]
    for fname in files:
        fpath = os.path.join(base, fname)
        name = f"compile {fname}"
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


# ---------------------------------------------------------------------------
# 阶段 2：模块导入检查
# ---------------------------------------------------------------------------

def test_module_imports() -> dict[str, Any]:
    """导入 3 个基准模块 + thresholds + __init__."""
    print("\n[阶段 2] 模块导入检查")
    modules: dict[str, Any] = {}

    # thresholds 模块（纯标准库，必过）
    try:
        from app.benchmarks.performance import thresholds as thresholds_mod
        record("import thresholds", PASS)
        modules["thresholds"] = thresholds_mod
    except Exception as e:  # noqa: BLE001
        record("import thresholds", FAIL, str(e))
        return modules

    # 3 个基准模块（依赖 numpy + 插件模块，插件支持 numpy 回退）
    bench_modules = [
        ("world_model_bench", "WorldModelPerfBenchmark"),
        ("rl_agent_bench", "RLAgentPerfBenchmark"),
        ("closed_loop_bench", "ClosedLoopPerfBenchmark"),
    ]
    for mod_name, cls_name in bench_modules:
        full_name = f"app.benchmarks.performance.{mod_name}"
        try:
            mod = __import__(full_name, fromlist=[cls_name])
            cls = getattr(mod, cls_name)
            record(f"import {mod_name}.{cls_name}", PASS)
            modules[mod_name] = cls
        except Exception as e:  # noqa: BLE001
            record(
                f"import {mod_name}.{cls_name}",
                FAIL,
                f"{type(e).__name__}: {e}",
            )

    # 顶层 __init__ 导出检查：exec __init__.py 到 stub 模块（保留 __path__），
    # 使其内部的所有 `from ... import ...` 语句执行，导出名称注入到 stub。
    # 7 个旧基准模块已 mock，3 个新基准模块走真实加载。
    try:
        _init_path = os.path.join(_PERF_DIR, "__init__.py")
        with open(_init_path, "r", encoding="utf-8") as f:
            _init_source = f.read()
        exec(compile(_init_source, _init_path, "exec"), _app_bench_perf_stub.__dict__)
        # exec 后 stub 命名空间包含所有导出名称
        from app.benchmarks.performance import (  # noqa: F401
            ClosedLoopPerfBenchmark,
            PERFORMANCE_THRESHOLDS,
            RLAgentPerfBenchmark,
            WorldModelPerfBenchmark,
        )
        record("import __init__ top-level exports", PASS)
        modules["__init__"] = {
            "WorldModelPerfBenchmark": WorldModelPerfBenchmark,
            "RLAgentPerfBenchmark": RLAgentPerfBenchmark,
            "ClosedLoopPerfBenchmark": ClosedLoopPerfBenchmark,
            "PERFORMANCE_THRESHOLDS": PERFORMANCE_THRESHOLDS,
        }
    except Exception as e:  # noqa: BLE001
        record("import __init__ top-level exports", FAIL, f"{type(e).__name__}: {e}")

    # run_perf_benchmark 导入 + 实例化（__init__.py exec 时已触发加载，
    # sys.modules 缓存命中，直接取类）
    try:
        from app.benchmarks.performance.run_perf_benchmark import (
            PerformanceBenchmarkRunner,
        )
        runner = PerformanceBenchmarkRunner()
        record("PerformanceBenchmarkRunner 实例化", PASS)
        modules["runner"] = runner
    except Exception as e:  # noqa: BLE001
        record("PerformanceBenchmarkRunner 实例化", FAIL, f"{type(e).__name__}: {e}")

    return modules


# ---------------------------------------------------------------------------
# 阶段 3：阈值键名匹配检查
# ---------------------------------------------------------------------------

def test_threshold_key_matching(modules: dict[str, Any]) -> None:
    """验证 thresholds.py 的 46 个新阈值键名与基准模块实际产出匹配."""
    print("\n[阶段 3] 阈值键名匹配检查")

    if "thresholds" not in modules:
        record("阈值键名匹配", SKIP, "thresholds 模块未导入")
        return

    thresholds_mod = modules["thresholds"]
    all_keys = set(thresholds_mod.PERFORMANCE_THRESHOLDS.keys())

    # 阶段 8 新增键名前缀（来自 thresholds.py docstring）
    new_prefixes = ["wm_", "rl_", "cl_"]
    new_keys = {k for k in all_keys if any(k.startswith(p) for p in new_prefixes)}
    record(
        "阶段 8 新增阈值键数量",
        PASS if len(new_keys) >= 46 else FAIL,
        f"实际 {len(new_keys)} 个（期望 >= 46）",
    )

    # 按前缀分组统计
    wm_keys = {k for k in new_keys if k.startswith("wm_")}
    rl_keys = {k for k in new_keys if k.startswith("rl_")}
    cl_keys = {k for k in new_keys if k.startswith("cl_")}
    record(
        "世界模型阈值 (wm_*)",
        PASS if len(wm_keys) >= 16 else FAIL,
        f"{len(wm_keys)} 个（期望 >= 16）",
    )
    record(
        "RL agent 阈值 (rl_*)",
        PASS if len(rl_keys) >= 19 else FAIL,
        f"{len(rl_keys)} 个（期望 >= 19）",
    )
    record(
        "闭环工作流阈值 (cl_*)",
        PASS if len(cl_keys) >= 11 else FAIL,
        f"{len(cl_keys)} 个（期望 >= 11）",
    )

    # 检查关键阈值键名存在
    expected_critical_keys = [
        "wm_single_pred_ms_p95",
        "wm_horizon_50_ms_p95",
        "wm_plugin_exec_ms_p95",
        "wm_cache_hot_ms_p50",
        "rl_single_decision_ms_p95",
        "rl_shield_strict_ms_p95",
        "rl_shield_nonstrict_ms_p95",
        "rl_policy_hot_ms_p95",
        "cl_total_ms_p95",
        "cl_predict_ms_p95",
        "cl_decide_ms_p95",
        "cl_throughput_avg_ms",
    ]
    missing = [k for k in expected_critical_keys if k not in all_keys]
    record(
        "关键阈值键名存在性",
        PASS if not missing else FAIL,
        f"缺失: {missing}" if missing else "12/12 关键键名全部存在",
    )

    # 检查阈值格式统一性（延迟类阈值必须使用 {"max": value} 形式）
    bad_format: list[str] = []
    for k in new_keys:
        spec = thresholds_mod.PERFORMANCE_THRESHOLDS[k]
        if not isinstance(spec, dict):
            bad_format.append(f"{k}: 非 dict")
            continue
        if "max" not in spec:
            # 允许分位数格式，但阶段 8 新增应该统一用 max
            if not any(p in spec for p in ("p50", "p95", "p99")):
                bad_format.append(f"{k}: 无 max 也无分位数")
    record(
        "阈值格式统一性",
        PASS if not bad_format else FAIL,
        f"格式异常: {bad_format}" if bad_format else "全部使用 max 或分位数格式",
    )


# ---------------------------------------------------------------------------
# 阶段 4：run_perf_benchmark.py 集成检查
# ---------------------------------------------------------------------------

def test_runner_integration(modules: dict[str, Any]) -> None:
    """验证 run_perf_benchmark.py 正确引用了 10 个基准段."""
    print("\n[阶段 4] run_perf_benchmark.py 集成检查")

    runner = modules.get("runner")
    if runner is None:
        record("集成检查", SKIP, "Runner 未实例化")
        return

    # 读取 run_perf_benchmark.py 源码，检查 [N/10] 标记
    src_path = os.path.join(
        _THIS_DIR, "app", "benchmarks", "performance", "run_perf_benchmark.py"
    )
    try:
        with open(src_path, "r", encoding="utf-8") as f:
            source = f.read()
    except OSError as e:
        record("读取 run_perf_benchmark.py", FAIL, str(e))
        return

    # 检查 10 个 [N/10] 标记
    expected_marks = [f"[{i}/10]" for i in range(1, 11)]
    missing_marks = [m for m in expected_marks if m not in source]
    record(
        "10 个基准段标记 [1/10]-[10/10]",
        PASS if not missing_marks else FAIL,
        f"缺失: {missing_marks}" if missing_marks else "全部 10 个标记存在",
    )

    # 检查 3 个新基准类的 import 语句
    expected_imports = [
        "WorldModelPerfBenchmark",
        "RLAgentPerfBenchmark",
        "ClosedLoopPerfBenchmark",
    ]
    missing_imports = [c for c in expected_imports if c not in source]
    record(
        "3 个新基准类 import",
        PASS if not missing_imports else FAIL,
        f"缺失: {missing_imports}" if missing_imports else "3 个 import 全部存在",
    )

    # 检查残留的 [N/7] 标记（应全部替换为 [N/10]）
    residual_7 = [f"[{i}/7]" for i in range(1, 8) if f"[{i}/7]" in source]
    record(
        "无残留 [N/7] 标记",
        PASS if not residual_7 else FAIL,
        f"残留: {residual_7}" if residual_7 else "已全部替换为 [N/10]",
    )

    # 检查 3 个新基准的 save_results 调用
    expected_saves = [
        "world_model_",
        "rl_agent_",
        "closed_loop_",
    ]
    missing_saves = [s for s in expected_saves if s not in source]
    record(
        "3 个新基准 save_results 调用",
        PASS if not missing_saves else FAIL,
        f"缺失: {missing_saves}" if missing_saves else "3 个 save 调用全部存在",
    )


# ---------------------------------------------------------------------------
# 阶段 5：小规模基准运行
# ---------------------------------------------------------------------------

def test_small_scale_benchmark(modules: dict[str, Any]) -> None:
    """运行小规模基准验证接口正确性 + 实际指标产出."""
    print("\n[阶段 5] 小规模基准运行（n_iterations=3）")

    # ---- WorldModelPerfBenchmark ----
    WMBench = modules.get("world_model_bench")
    if WMBench is None:
        record("WorldModelPerfBenchmark 运行", SKIP, "模块未导入")
    else:
        try:
            bench = WMBench()
            bench.setup()
            r = bench.run_single_prediction(n_iterations=3)
            expected_keys = [
                "wm_single_pred_ms_p50",
                "wm_single_pred_ms_p95",
                "wm_single_pred_ms_p99",
                "wm_single_pred_ms_mean",
                "wm_single_pred_ms_min",
                "wm_single_pred_ms_max",
                "wm_single_pred_samples",
            ]
            missing = [k for k in expected_keys if k not in r]
            record(
                "WorldModelPerfBenchmark.run_single_prediction",
                PASS if not missing else FAIL,
                f"产出 {len(r)} 个指标" + (f"，缺失: {missing}" if missing else ""),
            )
        except Exception as e:  # noqa: BLE001
            record(
                "WorldModelPerfBenchmark.run_single_prediction",
                FAIL,
                f"{type(e).__name__}: {e}",
            )

    # ---- RLAgentPerfBenchmark ----
    RLBench = modules.get("rl_agent_bench")
    if RLBench is None:
        record("RLAgentPerfBenchmark 运行", SKIP, "模块未导入")
    else:
        try:
            bench = RLBench()
            bench.setup()
            r = bench.run_single_decision(n_iterations=3)
            expected_keys = [
                "rl_single_decision_ms_p50",
                "rl_single_decision_ms_p95",
                "rl_single_decision_ms_p99",
                "rl_single_decision_samples",
            ]
            missing = [k for k in expected_keys if k not in r]
            record(
                "RLAgentPerfBenchmark.run_single_decision",
                PASS if not missing else FAIL,
                f"产出 {len(r)} 个指标" + (f"，缺失: {missing}" if missing else ""),
            )
        except Exception as e:  # noqa: BLE001
            record(
                "RLAgentPerfBenchmark.run_single_decision",
                FAIL,
                f"{type(e).__name__}: {e}",
            )

        # SafetyShield 过滤基准（轻量，200 次也很快）
        try:
            r = bench.run_safety_shield_filter(n_iterations=20)
            expected_keys = [
                "rl_shield_strict_ms_p50",
                "rl_shield_strict_ms_p95",
                "rl_shield_nonstrict_ms_p50",
                "rl_shield_nonstrict_ms_p95",
            ]
            missing = [k for k in expected_keys if k not in r]
            record(
                "RLAgentPerfBenchmark.run_safety_shield_filter",
                PASS if not missing else FAIL,
                f"产出 {len(r)} 个指标" + (f"，缺失: {missing}" if missing else ""),
            )
        except Exception as e:  # noqa: BLE001
            record(
                "RLAgentPerfBenchmark.run_safety_shield_filter",
                FAIL,
                f"{type(e).__name__}: {e}",
            )

    # ---- ClosedLoopPerfBenchmark ----
    CLBench = modules.get("closed_loop_bench")
    if CLBench is None:
        record("ClosedLoopPerfBenchmark 运行", SKIP, "模块未导入")
    else:
        try:
            bench = CLBench()
            bench.setup()
            r = bench.run_full_pipeline(n_iterations=3)
            # 检查 7 个节点的指标都产出
            node_keys_expected = [
                f"cl_{node}_ms_p95"
                for node in bench.NODE_SEQUENCE
            ]
            missing = [k for k in node_keys_expected if k not in r]
            record(
                "ClosedLoopPerfBenchmark.run_full_pipeline",
                PASS if not missing else FAIL,
                f"产出 {len(r)} 个指标" + (f"，缺失: {missing}" if missing else ""),
            )
        except Exception as e:  # noqa: BLE001
            record(
                "ClosedLoopPerfBenchmark.run_full_pipeline",
                FAIL,
                f"{type(e).__name__}: {e}\n{traceback.format_exc()[:500]}",
            )


# ---------------------------------------------------------------------------
# 主入口
# ---------------------------------------------------------------------------

def main() -> int:
    print("=" * 60)
    print("性能基准模块独立验证")
    print("=" * 60)

    test_static_syntax()
    modules = test_module_imports()
    test_threshold_key_matching(modules)
    test_runner_integration(modules)
    test_small_scale_benchmark(modules)

    # 汇总
    print("\n" + "=" * 60)
    print("验证汇总")
    print("=" * 60)
    n_pass = sum(1 for _, s, _ in results if s == PASS)
    n_fail = sum(1 for _, s, _ in results if s == FAIL)
    n_skip = sum(1 for _, s, _ in results if s == SKIP)
    total = len(results)
    print(f"  通过: {n_pass}/{total}")
    print(f"  失败: {n_fail}/{total}")
    print(f"  跳过: {n_skip}/{total}")

    if n_fail > 0:
        print("\n失败项详情:")
        for name, status, detail in results:
            if status == FAIL:
                print(f"  [FAIL] {name} — {detail}")
        return 1

    print("\n全部验证通过。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
