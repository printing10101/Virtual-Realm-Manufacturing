@echo off
title 灵境制造 - 一键启动

echo ========================================
echo 灵境制造 - 一键启动脚本
echo ========================================
echo.

REM 设置目录
set PROG_DIR=%~dp0
set ENG_DIR=%PROG_DIR%engineering
set PYTHON_DIR=%ENG_DIR%python

REM 检查 Python 环境
echo [1/4] 检查 Python 环境...
where python >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [错误] Python 未安装或未添加到 PATH
    echo 请先安装 Python 3.11+: https://www.python.org/downloads/
    pause
    exit /b 1
)
echo [OK] Python 已安装

REM 检查或创建虚拟环境
echo.
echo [2/4] 检查 Python 虚拟环境...
if not exist "%PYTHON_DIR%\.venv\Scripts\python.exe" (
    echo [INFO] 虚拟环境不存在，正在创建...
    python -m venv "%PYTHON_DIR%\.venv"
    echo [INFO] 虚拟环境创建成功
)

REM 激活虚拟环境并安装依赖
echo.
echo [3/4] 安装/更新后端依赖...
call "%PYTHON_DIR%\.venv\Scripts\activate.bat" >nul 2>&1

if not exist "%PYTHON_DIR%\requirements.txt" (
    echo [错误] requirements.txt 不存在
    pause
    exit /b 1
)

call "%PYTHON_DIR%\.venv\Scripts\pip.exe install --upgrade pip -q"
call "%PYTHON_DIR%\.venv\Scripts\pip.exe install -r "%PYTHON_DIR%\requirements.txt" -q"
echo [OK] 依赖安装完成

REM 检查或安装前端依赖
echo.
echo [4/4] 检查前端依赖...
cd "%ENG_DIR%"

if not exist "package.json" (
    echo [错误] package.json 不存在
    pause
    exit /b 1
)

if not exist "node_modules" (
    echo [INFO] 前端依赖不存在，正在安装 pnpm...
    call npm install -g pnpm -q
)

call pnpm install --prefer-offline -q

echo.
echo ========================================
echo 环境准备完成！正在启动应用...
echo ========================================
echo.

REM 启动后端
echo [启动] 后端服务 (FastAPI)...
start "灵境制造 - 后端" cmd /k "cd /d %PYTHON_DIR% && .\.venv\Scripts\activate.bat && set LNN_ENV=dev && set SERVER_HOST=127.0.0.1 && set SERVER_PORT=8765 && python start_server.py"

REM 等待后端启动
timeout /t 4 /nobreak >nul

REM 启动前端
echo [启动] 前端服务 (Vue3 + Vite)...
start "灵境制造 - 前端" cmd /k "cd /d %ENG_DIR% && pnpm dev"

REM 等待前端启动
timeout /t 3 /nobreak >nul

REM 打开浏览器
echo [完成] 打开浏览器...
start msedge http://localhost:1420/web

echo.
echo ========================================
echo ✓ 灵境制造已启动！
echo ========================================
echo.
echo 服务地址:
echo   - 后端 API: http://localhost:8765
echo   - 前端 Web: http://localhost:1420
echo   - 应用界面：http://localhost:1420/web
echo.
echo 任务栏窗口:
echo   - [灵境制造 - 后端] FastAPI 服务
echo   - [灵境制造 - 前端] Vite 开发服务
echo.
echo 提示：关闭窗口可停止相应服务
echo ========================================
echo.
pause
