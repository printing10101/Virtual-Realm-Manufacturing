@echo off
chcp 65001 >nul
REM ============================================================
REM  灵境制造 (Spirit Realm Manufacturing) — 开发模式启动器
REM  作用：一键配置 MSVC 构建环境 + Python 虚拟环境，拉起完整桌面应用
REM    (前端 Vite :1420  +  Rust 桌面壳  +  Python 后端 sidecar)
REM  说明：本文件为纯 ASCII，所有中文路径均通过 %~dp0 在运行时推导，
REM        避免 .bat 以 GBK 读取 UTF-8 中文路径导致 cd 失败。
REM ============================================================

REM 1) 配置 MSVC 构建环境（Tauri/Rust 桌面壳编译依赖 MSVC 工具链 link.exe + Windows SDK）
call "C:\Program Files\Microsoft Visual Studio\18\Community\VC\Auxiliary\Build\vcvars64.bat"
if errorlevel 1 (
  echo [错误] 无法加载 MSVC 环境 (vcvars64.bat)。
  echo        请确认已安装 Visual Studio 2022/2026 且勾选"使用 C++ 的桌面开发"工作负载。
  pause
  exit /b 1
)

REM 2) 取得本脚本所在目录（engineering/），中文/空格路径均由系统正确解析
set "SCRIPT_DIR=%~dp0"

REM 3) 指向本地 Python 虚拟环境（含全部后端依赖，由 requirements.txt 安装）
set "LINGJING_PYTHON_PATH=%SCRIPT_DIR%python\.venv5\Scripts\python.exe"
if not exist "%LINGJING_PYTHON_PATH%" (
  echo [错误] 未找到后端虚拟环境: %LINGJING_PYTHON_PATH%
  echo        请先创建虚拟环境并安装依赖:
  echo          python -m venv --without-pip python\.venv5
  echo          ... 再用系统 pip 注入完整 pip 后 pip install -r requirements.txt
  pause
  exit /b 1
)

REM 4) 显式指定后端入口脚本（开发模式也可由 CARGO_MANIFEST_DIR 自动推导，这里显式更稳）
set "LINGJING_PYTHON_SCRIPT=%SCRIPT_DIR%python\start_server.py"

REM 5) 进入工程目录并启动
cd /d "%SCRIPT_DIR%"
echo [信息] 启动灵境制造开发模式 (MSVC + Vite + Rust + Python sidecar)...
pnpm tauri dev
