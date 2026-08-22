@echo off
REM ============================================
REM .dsh-workspaces/dev-web.bat
REM 主工作区模式启动脚本
REM 启动 engineering/src 完整前端（包含 DSH 注入）
REM ============================================

echo.
echo ================================
echo   灵境制造 - 主工作区模式
echo ================================
echo.
echo [模式] 全栈开发模式（包含 window.__DSH_BOOT__）
echo [入口] engineering/src/
echo [工具] Vue Devtools + HMR
echo.

REM 启动主工作区前端
echo [启动] 启动 Vite 开发服务器（工程模式）...
echo [地址] http://localhost:3080
echo.

cd engineering
cd src
pnpm run dev
pause
