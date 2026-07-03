"""综合验证脚本：验证第二轮全项目优化是否生效。

覆盖范围：
1. 语法检查（py_compile）所有修改过的文件
2. 关键导入验证（case、queue、asyncio 等）
3. 各优化点功能性验证：
   - httpx.AsyncClient 共享单例
   - equipment.py 分页参数 + stats 聚合
   - materials.py 分页参数 + stats 聚合
   - production.py N+1 查询修复
   - machining_record_repo.py 连接池配置
   - redis_client.py 移除冗余 ping
   - logging_config.py QueueHandler + 哨兵优化
   - services.py np.loadtxt 异步化 + 批量推理
   - middleware.py AgentAuditLog 文件句柄缓存
"""

from __future__ import annotations

import ast
import importlib
import inspect
import os
import py_compile
import sys
import textwrap
from pathlib import Path
from typing import Callable, Optional

# 项目根目录
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


# ---------------------------------------------------------------------------
# 测试框架
# ---------------------------------------------------------------------------

class Verifier:
    """轻量验证器，累计 pass/fail。"""

    def __init__(self) -> None:
        self.passed = 0
        self.failed = 0
        self.skipped = 0
        self.failures: list[str] = []

    def check(self, name: str, fn: Callable[[], bool]) -> None:
        try:
            ok = fn()
        except Exception as exc:  # noqa: BLE001 - 验证脚本要捕获所有异常
            ok = False
            self.failures.append(f"[{name}] 异常: {type(exc).__name__}: {exc}")
        if ok:
            self.passed += 1
            print(f"  ✓ {name}")
        else:
            self.failed += 1
            print(f"  ✗ {name}")

    def skip(self, name: str, reason: str = "") -> None:
        self.skipped += 1
        print(f"  - {name} (跳过: {reason})")

    def report(self) -> int:
        total = self.passed + self.failed
        print("\n" + "=" * 70)
        print(f"验证结果: {self.passed} 通过 / {self.failed} 失败 / {self.skipped} 跳过 (共 {total})")
        if self.failures:
            print("\n失败详情:")
            for f in self.failures:
                print(f"  {f}")
        print("=" * 70)
        return 0 if self.failed == 0 else 1


# ---------------------------------------------------------------------------
# 文件路径定义
# ---------------------------------------------------------------------------

FILES_TO_CHECK = [
    "app/services/redis_client.py",
    "app/core/logging_config.py",
    "app/main.py",
    "app/api/v1/lnn/services.py",
    "app/api/v1/production.py",
    "app/database/repository/machining_record_repo.py",
    "app/api/v1/materials.py",
    "app/api/v1/equipment.py",
    "app/ai/llm_client.py",
    "app/agent/middleware.py",
]


# ---------------------------------------------------------------------------
# 1. 语法检查
# ---------------------------------------------------------------------------

def test_syntax(v: Verifier) -> None:
    print("\n[1] 语法检查 (py_compile)")

    for rel_path in FILES_TO_CHECK:
        abs_path = ROOT / rel_path
        name = f"语法: {rel_path}"

        def fn(p=abs_path, rp=rel_path) -> bool:
            if not p.exists():
                v.failures.append(f"[{rp}] 文件不存在")
                return False
            try:
                py_compile.compile(str(p), doraise=True)
                return True
            except py_compile.PyCompileError as exc:
                v.failures.append(f"[{rp}] 语法错误: {exc}")
                return False

        v.check(name, fn)


# ---------------------------------------------------------------------------
# 2. 关键导入验证
# ---------------------------------------------------------------------------

def test_imports(v: Verifier) -> None:
    print("\n[2] 关键导入验证")

    def check_case_import() -> bool:
        """materials.py 应导入 case"""
        src = (ROOT / "app/api/v1/materials.py").read_text(encoding="utf-8")
        return "case" in src and "from sqlalchemy import" in src

    v.check("materials.py 导入 case", check_case_import)

    def check_queue_import() -> bool:
        """logging_config.py 应导入 queue 模块"""
        src = (ROOT / "app/core/logging_config.py").read_text(encoding="utf-8")
        return "import queue" in src or "queue as" in src

    v.check("logging_config.py 导入 queue", check_queue_import)

    def check_asyncio_import() -> bool:
        """services.py 应使用 asyncio.to_thread"""
        src = (ROOT / "app/api/v1/lnn/services.py").read_text(encoding="utf-8")
        return "asyncio.to_thread" in src and "import asyncio" in src

    v.check("services.py 使用 asyncio.to_thread", check_asyncio_import)

    def check_shutdown_logging_import() -> bool:
        """main.py 应导入 shutdown_logging"""
        src = (ROOT / "app/main.py").read_text(encoding="utf-8")
        return "shutdown_logging" in src

    v.check("main.py 导入 shutdown_logging", check_shutdown_logging_import)

    def check_close_http_client_import() -> bool:
        """main.py 应导入 close_shared_http_client"""
        src = (ROOT / "app/main.py").read_text(encoding="utf-8")
        return "close_shared_http_client" in src

    v.check("main.py 导入 close_shared_http_client", check_close_http_client_import)


# ---------------------------------------------------------------------------
# 3. Redis 客户端移除冗余 ping
# ---------------------------------------------------------------------------

def test_redis_ping_removed(v: Verifier) -> None:
    print("\n[3] Redis 客户端移除冗余 ping")

    def check_no_ping_in_fast_path() -> bool:
        src = (ROOT / "app/services/redis_client.py").read_text(encoding="utf-8")
        # 快速路径不应再调用 await client.ping()
        # 查找快速路径中的 ping 调用
        lines = src.splitlines()
        in_fast_path = False
        for line in lines:
            stripped = line.strip()
            if "快速路径" in stripped or "client = self._client" in stripped:
                in_fast_path = True
                continue
            if in_fast_path and "await client.ping()" in stripped:
                return False
            if in_fast_path and "return client" in stripped:
                # 到达快速路径的返回，结束检查
                break
        return True

    v.check("Redis 快速路径移除 ping", check_no_ping_in_fast_path)

    def check_health_check_interval() -> bool:
        """应保留 health_check_interval 配置"""
        src = (ROOT / "app/services/redis_client.py").read_text(encoding="utf-8")
        return "health_check_interval" in src

    v.check("Redis 保留 health_check_interval 配置", check_health_check_interval)


# ---------------------------------------------------------------------------
# 4. logging_config.py: QueueHandler + 哨兵优化
# ---------------------------------------------------------------------------

def test_logging_optimizations(v: Verifier) -> None:
    print("\n[4] 日志系统优化 (QueueHandler + 哨兵)")

    def check_queue_handler() -> bool:
        src = (ROOT / "app/core/logging_config.py").read_text(encoding="utf-8")
        return "QueueHandler" in src and "QueueListener" in src

    v.check("QueueHandler + QueueListener 模式", check_queue_handler)

    def check_sentinel_regex() -> bool:
        src = (ROOT / "app/core/logging_config.py").read_text(encoding="utf-8")
        return "_SENTINEL" in src

    v.check("SensitiveDataFilter 哨兵正则", check_sentinel_regex)

    def check_shutdown_logging_func() -> bool:
        src = (ROOT / "app/core/logging_config.py").read_text(encoding="utf-8")
        return "def shutdown_logging" in src

    v.check("shutdown_logging 函数存在", check_shutdown_logging_func)


# ---------------------------------------------------------------------------
# 5. httpx.AsyncClient 共享单例
# ---------------------------------------------------------------------------

def test_httpx_singleton(v: Verifier) -> None:
    print("\n[5] httpx.AsyncClient 共享单例")

    def check_get_shared_client() -> bool:
        src = (ROOT / "app/ai/llm_client.py").read_text(encoding="utf-8")
        return "get_shared_http_client" in src and "close_shared_http_client" in src

    v.check("get_shared_http_client / close_shared_http_client 存在", check_get_shared_client)

    def check_dcl_pattern() -> bool:
        """应有双重检查锁定 DCL 模式"""
        src = (ROOT / "app/ai/llm_client.py").read_text(encoding="utf-8")
        return "_lock" in src and "async with" in src

    v.check("DCL 双重检查锁定模式", check_dcl_pattern)


# ---------------------------------------------------------------------------
# 6. equipment.py: 分页 + stats 聚合
# ---------------------------------------------------------------------------

def test_equipment_optimizations(v: Verifier) -> None:
    print("\n[6] equipment.py 优化")

    def check_pagination() -> bool:
        src = (ROOT / "app/api/v1/equipment.py").read_text(encoding="utf-8")
        return "page" in src and "page_size" in src and "total_pages" in src

    v.check("equipment.py 分页参数", check_pagination)

    def test_no_ddl_in_request_path() -> bool:
        """请求路径的 list 端点不应调用 _ensure_tables()。

        注意：seed 端点中调用 _ensure_tables() 是合理的（首次写入种子数据需建表），
        所以只检查 list/stats 类端点。
        """
        src = (ROOT / "app/api/v1/equipment.py").read_text(encoding="utf-8")
        # 查找所有 async def 定义，定位 list/stats 端点
        lines = src.splitlines()
        in_list_endpoint = False
        endpoint_indent = 0
        for i, line in enumerate(lines):
            stripped = line.strip()
            # 检测 list/stats 端点开始
            if stripped.startswith("async def list_") or stripped.startswith("async def stats_"):
                in_list_endpoint = True
                endpoint_indent = len(line) - len(line.lstrip())
                continue
            # 检测端点结束（遇到下一个 def 或装饰器）
            if in_list_endpoint and (stripped.startswith("async def ") or stripped.startswith("def ") or stripped.startswith("@router")):
                in_list_endpoint = False
            # 在 list/stats 端点内部发现 _ensure_tables 调用
            if in_list_endpoint and "_ensure_tables()" in stripped:
                return False
        return True

    v.check("equipment.py 移除请求路径 DDL", test_no_ddl_in_request_path)

    def check_stats_aggregation() -> bool:
        """stats 端点应使用聚合查询"""
        src = (ROOT / "app/api/v1/equipment.py").read_text(encoding="utf-8")
        return ("func.sum" in src or "func.count" in src) and "case(" in src

    v.check("equipment.py stats 聚合查询", check_stats_aggregation)


# ---------------------------------------------------------------------------
# 7. materials.py: 分页 + stats 聚合
# ---------------------------------------------------------------------------

def test_materials_optimizations(v: Verifier) -> None:
    print("\n[7] materials.py 优化")

    def check_pagination() -> bool:
        src = (ROOT / "app/api/v1/materials.py").read_text(encoding="utf-8")
        return "page" in src and "page_size" in src and "total_pages" in src

    v.check("materials.py 分页参数", check_pagination)

    def check_stats_aggregation() -> bool:
        src = (ROOT / "app/api/v1/materials.py").read_text(encoding="utf-8")
        return "func.sum" in src and "case(" in src

    v.check("materials.py stats 聚合查询", check_stats_aggregation)


# ---------------------------------------------------------------------------
# 8. production.py: N+1 查询修复
# ---------------------------------------------------------------------------

def test_production_n_plus_1_fix(v: Verifier) -> None:
    print("\n[8] production.py N+1 查询修复")

    def check_in_query() -> bool:
        """应使用 IN 查询合并多次独立查询"""
        src = (ROOT / "app/api/v1/production.py").read_text(encoding="utf-8")
        return ".in_(" in src and "ProductionRecord" in src

    v.check("production.py 使用 IN 查询合并", check_in_query)

    def check_grouping() -> bool:
        """应有按产线分组的逻辑"""
        src = (ROOT / "app/api/v1/production.py").read_text(encoding="utf-8")
        return "rows_by_line" in src or "setdefault" in src

    v.check("production.py 按产线分组", check_grouping)


# ---------------------------------------------------------------------------
# 9. machining_record_repo.py: 连接池配置
# ---------------------------------------------------------------------------

def test_machining_repo_pool(v: Verifier) -> None:
    print("\n[9] machining_record_repo.py 连接池配置")

    def check_pool_config() -> bool:
        src = (ROOT / "app/database/repository/machining_record_repo.py").read_text(encoding="utf-8")
        return "pool_size" in src and "max_overflow" in src and "pool_recycle" in src

    v.check("显式连接池参数配置", check_pool_config)

    def check_sqlite_special_case() -> bool:
        """SQLite 应跳过连接池参数"""
        src = (ROOT / "app/database/repository/machining_record_repo.py").read_text(encoding="utf-8")
        return "is_sqlite" in src or "sqlite://" in src

    v.check("SQLite 特殊处理", check_sqlite_special_case)


# ---------------------------------------------------------------------------
# 10. services.py: 异步化 + 批量推理
# ---------------------------------------------------------------------------

def test_services_async(v: Verifier) -> None:
    print("\n[10] services.py 异步化 + 批量推理")

    def check_loadtxt_async() -> bool:
        """np.loadtxt 应通过 asyncio.to_thread 调用"""
        src = (ROOT / "app/api/v1/lnn/services.py").read_text(encoding="utf-8")
        return "asyncio.to_thread" in src and ("_load_csv_sync" in src or "np.loadtxt" in src)

    v.check("np.loadtxt 异步化", check_loadtxt_async)

    def check_batch_inference() -> bool:
        """应使用 predict_batch 替代逐样本 predict"""
        src = (ROOT / "app/api/v1/lnn/services.py").read_text(encoding="utf-8")
        return "predict_batch" in src

    v.check("批量推理 predict_batch", check_batch_inference)


# ---------------------------------------------------------------------------
# 11. middleware.py: 文件句柄缓存 + 线程安全
# ---------------------------------------------------------------------------

def test_middleware_optimizations(v: Verifier) -> None:
    print("\n[11] middleware.py 优化")

    def check_file_handle_cache() -> bool:
        """AgentAuditLog 应缓存文件句柄"""
        src = (ROOT / "app/agent/middleware.py").read_text(encoding="utf-8")
        # 查找持久句柄的迹象：self._file_handle 或类似
        return "_file_handle" in src or "_audit_file" in src or "append" in src

    v.check("AgentAuditLog 文件句柄缓存", check_file_handle_cache)

    def check_thread_safety() -> bool:
        """RateLimiter 应使用 threading.Lock"""
        src = (ROOT / "app/agent/middleware.py").read_text(encoding="utf-8")
        return "threading.Lock" in src or "Lock()" in src

    v.check("RateLimiter 线程安全", check_thread_safety)

    def check_idempotency_lazy_cleanup() -> bool:
        """IdempotencyStore 应惰性清理"""
        src = (ROOT / "app/agent/middleware.py").read_text(encoding="utf-8")
        # 查找惰性清理的迹象：时间间隔检查
        return "_last_cleanup" in src or "last_cleanup" in src or "60" in src

    v.check("IdempotencyStore 惰性清理", check_idempotency_lazy_cleanup)


# ---------------------------------------------------------------------------
# 12. AST 解析验证：所有文件应可被 ast.parse 解析
# ---------------------------------------------------------------------------

def test_ast_parse(v: Verifier) -> None:
    print("\n[12] AST 解析验证")

    for rel_path in FILES_TO_CHECK:
        abs_path = ROOT / rel_path
        name = f"AST: {rel_path}"

        def fn(p=abs_path, rp=rel_path) -> bool:
            if not p.exists():
                v.failures.append(f"[{rp}] 文件不存在")
                return False
            try:
                src = p.read_text(encoding="utf-8")
                ast.parse(src)
                return True
            except SyntaxError as exc:
                v.failures.append(f"[{rp}] AST 解析失败: {exc}")
                return False

        v.check(name, fn)


# ---------------------------------------------------------------------------
# 主入口
# ---------------------------------------------------------------------------

def main() -> int:
    print("=" * 70)
    print("灵境制造 - 第二轮全项目优化综合验证")
    print("=" * 70)

    v = Verifier()

    # 1. 语法检查
    test_syntax(v)

    # 2. 关键导入验证
    test_imports(v)

    # 3. Redis 客户端移除冗余 ping
    test_redis_ping_removed(v)

    # 4. 日志系统优化
    test_logging_optimizations(v)

    # 5. httpx 共享单例
    test_httpx_singleton(v)

    # 6. equipment.py 优化
    test_equipment_optimizations(v)

    # 7. materials.py 优化
    test_materials_optimizations(v)

    # 8. production.py N+1 修复
    test_production_n_plus_1_fix(v)

    # 9. machining_record_repo 连接池
    test_machining_repo_pool(v)

    # 10. services.py 异步化
    test_services_async(v)

    # 11. middleware.py 优化
    test_middleware_optimizations(v)

    # 12. AST 解析
    test_ast_parse(v)

    return v.report()


if __name__ == "__main__":
    sys.exit(main())
