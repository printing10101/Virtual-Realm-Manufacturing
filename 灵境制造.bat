@echo off
title 灵境制造 - 桌面应用

cd /d "%~dp0engineering"

REM 检查 Node 服务是否正在运行
netstat -ano | findstr ":8765" >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo [警告] 端口 8765 已被占用，可能已有后端在服务运行
) else (
    echo [启动] 启动后端服务...
)

REM 检查 Python 虚拟环境
if not exist "python\.venv\Scripts\activate.bat" (
    echo [错误] 虚拟环境不存在，请先运行 pip install -r requirements.txt
    pause
    exit /b 1
)

REM 启动后端服务（新窗口）
start "灵境制造 - 后端" cmd /k "cd python && .\.venv\Scripts\activate.bat && python start_server.py"

REM 等待后端启动完成
timeout /t 3 /nobreak >nul

REM 检查前端是否已运行
netstat -ano | findstr ":1420" >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [启动] 启动前端服务...
    start "灵境制造 - 前端" cmd /k "cd /d %~dp0engineering && pnpm dev"
)

REM 打开浏览器访问应用
timeout /t 2 /nobreak >nul
start msedge http://localhost:1420/web

echo.
echo ========================================
echo 灵境制造 - 启动完成！
echo ========================================
echo.
echo 后端服务：http://localhost:8765
echo 前端服务：http://localhost:1420
echo 应用地址：http://localhost:1420/web
echo.
echo 两个服务窗口会在后台运行
echo 浏览器已自动打开主界面
echo.
echo 关闭窗口即可停止相应服务
echo ========================================
echo.
pause
