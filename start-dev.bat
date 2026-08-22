@echo off
REM 灵境制造 - 分离开发模式启动脚本
REM 启动前后端独立服务（适合开发调试）

cd /d "%~dp0engineering"

echo ========================================
echo 灵境制造 - 开发模式启动脚本
echo ========================================
echo 模式：前端 + 后端分离启动
echo.

REM ========== 后端启动 =========
echo [1/2] 启动后端服务 (FastAPI)...
echo.

cd python

REM 检查虚拟环境
if not exist ".venv\Scripts\activate.bat" (
    echo [ERROR] 虚拟环境 .venv 不存在
    echo 请先运行：python -m venv .venv
    echo         pip install -r requirements.txt
    pause
    exit /b 1
)

echo [INFO] 激活虚拟环境...
call .venv\Scripts\activate.bat

REM 启动后端
echo [INFO] 启动后端服务...
echo [INFO] 地址：http://localhost:8765
echo [INFO] API 文档：http://localhost:8765/docs
echo.

start "灵境制造 - 后端" cmd /k "python start_server.py"

REM ========== 前端启动 =========
echo [INFO] 等待 3 秒后端启动...
timeout /t 3 /nobreak >nul

cd ..
echo.
echo [2/2] 启动前端服务 (Vue3 + Vite)...
echo [INFO] 地址：http://localhost:1420
echo [INFO] 完整应用：http://localhost:1420/web
echo.

start "灵境制造 - 前端" cmd /k "pnpm dev"

echo.
echo ========================================
echo 启动完成！
echo ========================================
echo.
echo 后端：http://localhost:8765
echo 前端：http://localhost:1420
echo 完整应用：http://localhost:1420/web
echo.
echo 两个窗口会分别运行前后端服务
echo 关闭窗口即可停止服务
echo.
pause
