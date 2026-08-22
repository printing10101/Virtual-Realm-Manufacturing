@echo off
REM ============================================
REM .dsh-workspaces/dev-solo.bat
REM Solo 模式前端设计器启动脚本
REM 启动 src-frontend-only 独立预览服务器
REM ============================================

echo.
echo ================================
echo   灵境制造 - Solo 设计模式
echo ================================
echo.
echo [模式] 前端设计专用模式
echo [入口] src-frontend-only/
echo [同步] 与 engineering/src 自动同步
echo.

REM 检查 Python 环境
py --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [错误] 未检测到 Python 环境
    echo 请先安装 Python 3.11+
    pause
    exit /b 1
)

REM 检查同步状态
echo [检查] 文件同步状态...
if not exist "src-frontend-only" (
    echo [同步] 首次运行，正在同步文件...
    pnpm tsx .dsh-workspaces\dsh-sync.ts --apply
    if %errorlevel% neq 0 (
        echo [错误] 同步失败，请检查文件权限
        pause
        exit /b 1
    )
    echo [同步] 完成
) else (
    REM 检查是否需要更新同步
    pnpm tsx .dsh-workspaces\dsh-sync.ts --apply
)

REM 启动前端预览服务器
echo.
echo [启动] 启动 Vite 开发服务器...
echo [地址] http://localhost:5173
echo [窗口] 全屏编辑器 + 右侧 AI 对话面板
echo.

cd src-frontend-only
pnpm run dev
pause
