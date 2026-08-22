@echo off
title 灵境制造 - 启动脚本

cd /d "%~dp0engineering"

echo ========================================
echo 灵境制造 - 本地启动脚本
echo ========================================
echo.

REM ========== 步骤 1: 安装/验证后端依赖 ==========
echo [1/3] 检查后端依赖...

cd python

if not exist ".venv\Scripts\python.exe" (
    echo [错误] 虚拟环境不存在
    echo 请先运行：python -m venv .venv
    echo         pip install -r requirements.txt
    pause
    exit /b 1
)

echo [INFO] 虚拟环境已存在，检查依赖...
call .venv\Scripts\python.exe -m pip show uvicorn fastapi >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [警告] 检测到依赖缺失，正在安装...
    call .venv\Scripts\pip.exe install -r requirements.txt
) else (
    echo [INFO] 依赖已安装
)

REM ========== 步骤 2: 启动后端服务 ==========
echo.
echo [2/3] 启动后端服务...
echo [INFO] 端口：8765

start "灵境制造 - 后端" cmd /k "cd /d %~dp0engineering\python && .\.venv\Scripts\activate.bat && set LNN_ENV=dev && set SERVER_HOST=127.0.0.1 && set SERVER_PORT=8765 && python start_server.py"

REM ========== 步骤 3: 等待并启动前端 ==========
timeout /t 5 /nobreak >nul

cd ..
echo.
echo [3/3] 启动前端服务...
echo [INFO] 端口：1420

netstat -ano | findstr ":1420" >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    start "灵境制造 - 前端" cmd /k "cd /d %~dp0engineering && pnpm dev"
)

REM ========== 步骤 4: 打开浏览器 ==========
timeout /t 3 /nobreak >nul
start msedge http://localhost:1420/web

echo.
echo ========================================
echo 灵境制造 - 启动完成！
echo ========================================
echo.
echo 后端：http://localhost:8765
echo 前端：http://localhost:1420
echo 应用：http://localhost:1420/web
echo.
echo 状态：
echo  - 后端窗口：运行 FastAPI 服务器
echo  - 前端窗口：运行 Vite 开发服务器
echo  - 浏览器：已自动打开主界面
echo.
echo 提示：关闭窗口可停止对应服务
echo ========================================
echo.
pause
