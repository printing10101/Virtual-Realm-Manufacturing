#!/usr/bin/env python3
"""构建桌面端嵌入式 Python 运行时（阶段 2 桌面开箱即用）。

把独立 Python 发行版（python-build-standalone，即 uv 下载的完整版）与
后端依赖（site-packages）、后端代码组装为**完全自包含**的目录，
供 Tauri ``bundle.resources`` 打包——目标机器无需预装任何 Python。

目录结构（产出）::

    <runtime-dir>/
    ├── runtime/            # 自包含 Python（python.exe + 标准库 + 依赖）
    │   └── Lib/site-packages/   # 全部第三方依赖（onnxruntime-only，无 torch）
    ├── backend/            # 后端源码（app/、start_server.py、alembic、config）
    │   └── start_server.py
    └── runtime.json        # 元信息（版本、构建时间）

用法::

    # 本机（Windows）：
    python scripts/build_desktop_runtime.py
    # 指定来源：
    python scripts/build_desktop_runtime.py \\
        --python-src <uv-python-dir> --site-packages <venv>/Lib/site-packages \\
        --backend-src ../.. --runtime-dir ../desktop_runtime
    # 无本地依赖缓存时用 pip 安装（CI 用）：
    python scripts/build_desktop_runtime.py --install-deps

依赖来源：显式 --site-packages 参数复制；否则默认 pip 安装 requirements.txt（CI 与本机一致，避免宿主 venv 污染）。
"""
from __future__ import annotations

import argparse
import json
import platform
import shutil
import subprocess
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]  # engineering/python
ENGINEERING = PROJECT_ROOT.parent                    # engineering


def log(msg: str) -> None:
    print(f"[build-runtime] {msg}", flush=True)


def find_uv_python() -> Path | None:
    """探测 uv 下载的完整版 Python（python-build-standalone，优先非 install_only）"""
    if sys.platform == "win32":
        base = Path.home() / "AppData/Roaming/uv/python"
        if base.is_dir():
            candidates = sorted(base.iterdir(), reverse=True)
            # 优先完整版（含 Scripts/pip），install_only 仅作回退
            for p in candidates:
                if (p / "python.exe").exists() and (p / "Scripts").is_dir():
                    return p
            for p in candidates:
                if (p / "python.exe").exists():
                    return p
    else:
        base = Path.home() / ".local/share/uv/python"
        if base.is_dir():
            candidates = sorted(base.iterdir(), reverse=True)
            for p in candidates:
                if (p / "bin" / "python3").exists() and (p / "bin" / "pip").exists():
                    return p
            for p in candidates:
                if (p / "bin" / "python3").exists():
                    return p
    return None


def copy_tree(src: Path, dst: Path, ignore: tuple[str, ...] = ()) -> int:
    """复制目录树，返回复制的文件数"""
    count = 0

    def _ignore(d: str, names: list[str]) -> list[str]:
        return [n for n in names if n in ignore]

    for root, _dirs, files in shutil.os.walk(src, topdown=True):
        rel = Path(root).relative_to(src)
        for f in files:
            s = Path(root) / f
            d = dst / rel / f
            d.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(s, d)
            count += 1
    return count


def main() -> int:
    parser = argparse.ArgumentParser(description="构建桌面端嵌入式 Python 运行时")
    parser.add_argument("--runtime-dir", type=Path,
                        default=PROJECT_ROOT / "desktop_runtime",
                        help="运行时输出目录（默认 engineering/python/desktop_runtime）")
    parser.add_argument("--python-src", type=Path, default=None,
                        help="完整版 Python 目录（默认自动探测 uv 安装）")
    parser.add_argument("--site-packages", type=Path, default=None,
                        help="已安装依赖的 site-packages 目录（默认相邻 venv）")
    parser.add_argument("--backend-src", type=Path, default=PROJECT_ROOT,
                        help="后端源码根（默认 engineering/python）")
    parser.add_argument("--install-deps", action="store_true",
                        help="[兼容保留] 默认即用 pip 安装 requirements.txt（无 --site-packages 时）")
    parser.add_argument("--pip-index", default="https://mirrors.aliyun.com/pypi/simple/",
                        help="--install-deps 时的 pip 源")
    args = parser.parse_args()

    runtime_dir = args.runtime_dir.resolve()
    runtime_py = runtime_dir / "runtime"
    backend_dst = runtime_dir / "backend"

    # 1. 定位 Python 完整版
    python_src = args.python_src
    if python_src is None:
        python_src = find_uv_python()
    if python_src is None or not (python_src / "python.exe").exists():
        log("ERROR: 未找到完整版 Python（可用 --python-src 指定 python-build-standalone 目录）")
        return 1
    log(f"Python 来源: {python_src}")

    # 2. 复制 Python 运行时（排除冗余目录）
    log("复制 Python 运行时（含标准库）...")
    if runtime_py.exists():
        shutil.rmtree(runtime_py)
    runtime_py.mkdir(parents=True)
    n = copy_tree(python_src, runtime_py,
                  ignore=("__pycache__", "include", "libs", "tcl"))
    log(f"复制 Python 文件 {n} 个")

    # 3. 依赖
    py_exe = runtime_py / ("python.exe" if sys.platform == "win32" else "bin/python3")
    if sys.platform == "win32":
        sp_dst = runtime_py / "Lib/site-packages"
    else:
        lib = runtime_py / "lib"
        pyver_dirs = sorted(lib.glob("python*")) if lib.is_dir() else []
        sp_dst = (pyver_dirs[0] / "site-packages") if pyver_dirs else lib / "site-packages"
    sp_dst.mkdir(parents=True, exist_ok=True)

    if args.site_packages is not None and args.site_packages.is_dir():
        # 显式指定 site-packages → 复制（开发快速路径，调用方对内容负责）
        n = copy_tree(args.site_packages, sp_dst, ignore=("__pycache__",))
        log(f"复制依赖 {n} 个文件（来自 {args.site_packages}）")
    else:
        # 默认（含 --install-deps 兼容标志）：pip 从 requirements.txt 安装。
        # 注意：不复制宿主 venv（2026-08-03 曾因 venv 混入 torch/casadi 等
        # 训练向包污染运行时 → NSIS/WiX 打包失败），requirements.txt 才是真源。
        req = PROJECT_ROOT / "requirements.txt"
        log(f"pip 安装依赖到运行时（requirements.txt 真源，镜像: {args.pip_index}）...")
        r = subprocess.run(
            [str(py_exe), "-m", "pip", "install", "--no-cache-dir",
             "--break-system-packages",  # python-build-standalone 带 PEP668 标记
             "--target", str(sp_dst), "-r", str(req),
             "--index-url", args.pip_index],
        )
        if r.returncode != 0:
            log("ERROR: 依赖安装失败")
            return r.returncode

    # 4. 后端代码
    log("复制后端代码...")
    if backend_dst.exists():
        shutil.rmtree(backend_dst)
    backend_dst.mkdir(parents=True)
    for sub in ("app", "alembic", "config"):
        s = args.backend_src / sub
        if s.is_dir():
            n = copy_tree(s, backend_dst / sub,
                          ignore=("__pycache__", "tests", "data", ".pyc"))
            log(f"复制 {sub}/ {n} 个文件")
    for f in ("start_server.py", "alembic.ini", "requirements.txt"):
        s = args.backend_src / f
        if s.is_file():
            shutil.copy2(s, backend_dst / f)

    # 5. 元信息 + 验证
    info = {
        "schema": 1,
        "python": platform.python_version(),
        "python_exe": "runtime/python.exe" if sys.platform == "win32" else "runtime/bin/python3",
        "backend_dir": "backend",
        "backend_entry": "backend/start_server.py",
        "built_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
    }
    (runtime_dir / "runtime.json").write_text(json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8")

    log("验证运行时...")
    test = subprocess.run(
        [str(py_exe), "-c", "import sys; print(sys.version.split()[0])"],
        capture_output=True, text=True, timeout=30,
    )
    if test.returncode != 0:
        log(f"ERROR: 运行时 Python 不可用\n{test.stderr}")
        return 1
    log(f"运行时 Python: {test.stdout.strip()}")

    # 估算体积
    total = sum(f.stat().st_size for f in runtime_dir.rglob("*") if f.is_file())
    log(f"完成: {runtime_dir}（约 {total / 1024 / 1024:.0f} MB）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
