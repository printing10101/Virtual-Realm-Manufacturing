@echo off
REM 灵境制造 Tauri 桌面应用启动脚本
REM 使用说明：双击运行或命令行执行

echo ========================================
echo 灵境制造 V4 - Tauri 桌面应用启动器
echo ========================================
echo.

REM 检查桌面运行时 Python 是否存在
if not exist "engineering\python\desktop_runtime\runtime\python.exe" (
    echo [错误] 未找到 desktop_runtime Python
    echo 请确认工程侧代码已同步到工作目录
    pause
    exit /b 1
)

echo [1/3] 启动后端服务...
cd engineering\python
start /b desktop_runtime\runtime\python.exe start_server.py
cd ..\..

echo [2/3] 等待后端就绪 (5 秒)...
timeout /t 5 /nobreak >nul

echo [3/3] 启动 Tauri 桌面应用...
cd engineering\src-tauri
start "" "pnpm tauri dev"

echo.
echo ========================================
echo 启动命令已执行
echo - 后端服务正在 127.0.0.1:8765 运行
echo - Tauri 桌面应用将通过 pnpm tauri dev 启动
echo - 首次启动需要构建前端，可能需要 60 秒以上
echo ========================================
echo.

REM 检查应用是否成功启动
timeout /t 10 /nobreak >nul
netstat -ano | findstr :1420 >nul
if %errorlevel% neq 0 (
    echo [警告] 前端未正常启动，请检查 pnpm tauri dev 控制台输出
) else (
    echo [成功] 前端服务已启动在 http://localhost:1420
)

exit /b 0
