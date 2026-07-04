"""
Sidecar 启动包装器

该模块作为 PyInstaller 打包的入口，负责：
1. 解析命令行参数
2. 启动 uvicorn 监听
3. 写入 state 文件（供 Tauri Rust 端读取）
4. 处理优雅退出信号

被 PyInstaller 编译后，路径为：
    dist/lingjing-backend/lingjing-backend(.exe)
"""

from __future__ import annotations

import argparse
import json
import os
import signal
import sys
import time
from pathlib import Path


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Lingjing Backend Sidecar")
    p.add_argument("--host", default=os.environ.get("LNN_HOST", "127.0.0.1"))
    p.add_argument("--port", type=int, default=int(os.environ.get("LNN_PORT", "8765")))
    p.add_argument("--workers", type=int, default=1)
    p.add_argument("--log-level", default="info")
    p.add_argument(
        "--state-file",
        default=os.environ.get(
            "LNN_STATE_FILE",
            str(Path(os.environ.get("LNN_LOG_DIR", ".")) / "sidecar.json"),
        ),
    )
    return p.parse_args()


def write_state(args: argparse.Namespace, status: str, extra: dict | None = None) -> None:
    payload = {
        "status": status,
        "pid": os.getpid(),
        "host": args.host,
        "port": args.port,
        "ts": int(time.time()),
    }
    if extra:
        payload.update(extra)
    try:
        Path(args.state_file).parent.mkdir(parents=True, exist_ok=True)
        Path(args.state_file).write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    except Exception as exc:  # noqa: BLE001
        print(f"[sidecar] 写入 state 文件失败: {exc}", file=sys.stderr)


def main() -> int:
    args = parse_args()

    # 切换工作目录到打包时的资源目录
    bundle_dir = getattr(sys, "_MEIPASS", None)
    if bundle_dir:
        # 让 alembic/config 等相对路径文件可被找到
        os.chdir(bundle_dir)

    write_state(args, "starting")

    # 注册信号处理
    def _handle_signal(signum, _frame):  # noqa: ANN001
        write_state(args, "stopping", {"signal": signum})
        # 抛 KeyboardInterrupt 让 uvicorn 优雅退出
        raise KeyboardInterrupt()

    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, _handle_signal)
    if hasattr(signal, "SIGINT"):
        signal.signal(signal.SIGINT, _handle_signal)
    if hasattr(signal, "SIGBREAK"):
        signal.signal(signal.SIGBREAK, _handle_signal)

    # 设置 JWT 密钥（必须在导入 app.main 之前，因为 app.auth.security 强制要求此环境变量）
    # 参考 start_server.py 的实现模式：开发/桌面 sidecar 环境下自动生成随机密钥
    import secrets as _secrets
    if not os.environ.get("LNN_JWT_SECRET"):
        os.environ["LNN_JWT_SECRET"] = _secrets.token_urlsafe(32)

    # 注入 nlopt/casadi stub 模块（必须在导入 app.main 之前）
    # 原因：cadquery 2.7.0 将 nlopt/casadi 声明为硬依赖，
    #   - cadquery/occ_impl/sketch_solver.py 顶部 `import nlopt`
    #   - cadquery/occ_impl/solver.py 顶部 `import casadi as ca`
    # cadquery/__init__.py → from .sketch import Sketch → from .occ_impl.sketch_solver import ...
    # 形成 import cadquery 即触发 nlopt 导入的硬链。
    # 桌面 sidecar 不使用 sketch solver 求解功能，PyInstaller excludes 排除 nlopt/casadi
    # （DLL 依赖不完整），这里注入 stub 让 cadquery 能正常导入。
    # 实际调用求解功能时会抛 RuntimeError，给出明确提示。
    import types as _types

    def _make_unavailable_stub(mod_name: str):
        mod = _types.ModuleType(mod_name)
        mod.__doc__ = (
            f"Stub for {mod_name} injected by sidecar_main.py. "
            f"{mod_name} is excluded from the desktop sidecar build; "
            f"sketch solver functionality is unavailable."
        )

        def _unavailable(*args, **kwargs):
            raise RuntimeError(
                f"{mod_name} is not available in the desktop sidecar build. "
                f"Install {mod_name} or run with system Python to use this functionality."
            )

        def __getattr__(attr):
            return _unavailable

        mod.__getattr__ = __getattr__
        return mod

    for _stub_name in ("nlopt", "casadi"):
        if _stub_name not in sys.modules:
            sys.modules[_stub_name] = _make_unavailable_stub(_stub_name)

    # 延迟导入以加快启动反馈
    try:
        import uvicorn
        from app.main import app
    except Exception as exc:  # noqa: BLE001
        print(f"[sidecar] 导入 app.main 失败: {exc}", file=sys.stderr)
        write_state(args, "failed", {"error": str(exc)})
        return 1

    write_state(args, "running")

    config = uvicorn.Config(
        app=app,
        host=args.host,
        port=args.port,
        log_level=args.log_level,
        workers=args.workers,
        access_log=False,
    )
    server = uvicorn.Server(config)

    try:
        server.run()
    except KeyboardInterrupt:
        pass
    except Exception as exc:  # noqa: BLE001
        write_state(args, "failed", {"error": str(exc)})
        return 1
    finally:
        write_state(args, "stopped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
