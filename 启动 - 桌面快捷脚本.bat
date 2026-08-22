@echo off
title 灵境制造

REM ========== 设置路径 ==========
set PROG_DIR=%~dp0
set ENG_DIR=%PROG_DIR%engineering
set PYTHON_DIR=%ENG_DIR%python
set PORT_BACKEND=8765
set PORT_FRONTEND=1420

echo.
echo =============================================
echo       灵境制造 - 桌面启动器
echo =============================================
echo.

REM ===== 启动后端 =====
echo [1/2] 启动后端服务 (FastAPI)...
cd "%PYTHON_DIR%"
start "灵境制造 - 后端" cmd /k "cd /d %PYTHON_DIR% && .\.venv\Scripts\activate.bat && set LNN_ENV=dev && set SERVER_HOST=127.0.0.1 && set SERVER_PORT=%PORT_BACKEND% && python start_server.py"

echo [提示] 后端正在启动，等待 3 秒...
timeout /t 3 /nobreak >nul

REM ===== 启动前端 =====
echo.
echo [2/2] 启动前端服务 (Vite)...
cd /d "%ENG_DIR%"
start "灵境制造 - 前端" cmd /k "cd /d %ENG_DIR% && pnpm run dev"

echo [提示] 前端正在启动，等待 2 秒...
timeout /t 2 /nobreak >nul

REM ===== 打开浏览器 =====
echo.
echo 应用界面已打开：http://localhost:%PORT_FRONTEND%/web
start msedge http://localhost:%PORT_FRONTEND%/web

echo.
echo =============================================
echo          ✓ 灵境制造已启动！
echo =============================================
echo.
echo 服务地址:
echo   - 后端 API:    http://localhost:%PORT_BACKEND%
echo   - 前端 Web:    http://localhost:%PORT_FRONTEND%
echo   - 应用界面：   http://localhost:%PORT_FRONTEND%/web
echo.
echo 窗口说明:
echo   - [灵境制造 - 后端] FastAPI 服务窗口
echo   - [灵境制造 - 前端] Vite 开发服务窗口
echo.
echo 提示：关闭窗口可停止对应服务
echo =============================================
echo.
pause
