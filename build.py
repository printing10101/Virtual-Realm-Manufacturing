#!/usr/bin/env python
"""
Tauri 桌面应用一键构建脚本

完整流程：
1. 检查环境
2. 构建 Python 后端 Sidecar（PyInstaller）-> src-tauri/binaries/
3. 安装前端依赖（npm/pnpm install）
4. 构建前端（vite build）
5. 构建 Tauri 桌面应用（tauri build）

使用方法：
    python build.py
    python build.py --skip-frontend    # 跳过前端（开发调试用）
    python build.py --skip-python      # 跳过 Python 打包（已有 sidecar 时）
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent


def run(cmd: list[str], cwd: Path | None = None, env: dict | None = None) -> int:
    print(f"\n>>> {' '.join(cmd)}")
    # Windows 上需要 shell=True 来执行 .CMD 文件（如 pnpm.CMD）
    result = subprocess.run(cmd, cwd=str(cwd or PROJECT_ROOT), env=env, shell=True)
    return result.returncode


def find_pkg_manager() -> str:
    if shutil.which("pnpm"):
        return "pnpm"
    if shutil.which("npm"):
        return "npm"
    if shutil.which("yarn"):
        return "yarn"
    print("[ERROR] 未找到 pnpm/npm/yarn，请先安装 Node.js 包管理器")
    sys.exit(1)


def build_python_sidecar() -> int:
    print("\n========== 步骤 1/4: 打包 Python 后端 Sidecar ==========")
    return run([sys.executable, "python/scripts/build_backend.py"])


def install_deps(pkg_manager: str) -> int:
    print(f"\n========== 步骤 2/4: 安装前端依赖 ({pkg_manager}) ==========")
    return run([pkg_manager, "install"])


def build_frontend(pkg_manager: str) -> int:
    print(f"\n========== 步骤 3/4: 构建前端 (vite build) ==========")
    return run([pkg_manager, "run", "build"])


def build_tauri(pkg_manager: str) -> int:
    print(f"\n========== 步骤 4/4: 构建 Tauri 桌面应用 ==========")
    # 使用 npx/pnpm 直接调用 @tauri-apps/cli
    return run([pkg_manager, "run", "tauri", "build"])


def main() -> int:
    p = argparse.ArgumentParser(description="Tauri 一键构建")
    p.add_argument("--skip-python", action="store_true")
    p.add_argument("--skip-frontend", action="store_true")
    p.add_argument("--skip-install", action="store_true")
    args = p.parse_args()

    pkg_manager = find_pkg_manager()

    if not args.skip_python:
        rc = build_python_sidecar()
        if rc != 0:
            print(f"[ERROR] Python sidecar 打包失败 (exit={rc})")
            return rc

    if not args.skip_install:
        rc = install_deps(pkg_manager)
        if rc != 0:
            return rc

    if not args.skip_frontend:
        rc = build_frontend(pkg_manager)
        if rc != 0:
            return rc

    rc = build_tauri(pkg_manager)
    if rc != 0:
        print(f"[ERROR] Tauri 构建失败 (exit={rc})")
        return rc

    print("\n========== 构建完成 ==========")
    print("产物位置：src-tauri/target/release/bundle/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
