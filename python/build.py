#!/usr/bin/env python
import argparse
import subprocess
import sys
import os


def main():
    parser = argparse.ArgumentParser(description="PyInstaller 打包脚本")
    parser.add_argument("--name", default="lingjing-ai", help="输出文件名")
    parser.add_argument("--onefile", action="store_true", help="打包为单个可执行文件")
    parser.add_argument("--noconsole", action="store_true", help="不显示控制台窗口")
    args = parser.parse_args()

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--name", args.name,
        "--distpath", "dist",
        "--workpath", "build",
        "app/main.py"
    ]

    if args.onefile:
        cmd.insert(3, "--onefile")
    if args.noconsole:
        cmd.insert(3, "--noconsole")

    print(f"执行命令: {' '.join(cmd)}")
    subprocess.run(cmd, check=True)
    print("打包完成！输出目录: dist/")


if __name__ == "__main__":
    main()
