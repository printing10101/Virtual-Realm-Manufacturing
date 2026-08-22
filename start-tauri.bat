@echo off
REM 灵境制造 - Tauri 桌面应用启动脚本
REM Run as Administrator if needed

cd /d "%~dp0engineering"

echo ========================================
echo 灵境制造 - 启动 Tauri 桌面应用
echo ========================================
echo.

REM 检查 pnpm
where pnpm >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] pnpm 未安装，请先安装 Node.js 环境
    pause
    exit /b 1
)

REM 检查 cargo (Rust)
where cargo >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [WARNING] cargo 未安装（Tauri 需要 Rust）
    echo 请从 https://rustup.rs/ 安装 Rust
    echo.
    echo 是否继续尝试启动？(y/n)
    set /p CONTINUE="> "
    if /i not "%CONTINUE%"=="y" (
        exit /b 1
    )
)

echo [INFO] 启动 Tauri 开发模式...
echo [INFO] 前端：http://localhost:1420
echo [INFO] 后端：http://localhost:8765
echo.

REM 启动 Tauri
call pnpm tauri dev

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] Tauri 启动失败
    pause
)
