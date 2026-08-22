@echo off
REM ============================================================================
REM 灵境制造 - 自动接线一键执行脚本
REM 用途：运行 scripts/wiring_apply.py 完成功能缺口 + 路线图全部接线
REM       （修复 2 个路径 BUG / 删 4 个垃圾文件 / 7 处 __init__ 导出 /
REM        路由注册 / 生命周期委托 / bridge feed 修复）
REM 安全：每文件先写 .bak 备份，幂等可重复运行，失败明确报错
REM ============================================================================
cd /d "%~dp0"

echo [1/3] 检查 Python 启动器...

where py >nul 2>nul
if %errorlevel% neq 0 (
    echo [错误] 未找到 Python 启动器 py。
    echo        请安装 Python 3.11（勾选 py launcher）后重试，
    echo        或改用: python scripts\wiring_apply.py --apply
    pause
    exit /b 1
)

echo [2/3] 执行自动接线（--apply 实际修改文件，每步 .bak 备份）...
py -3.11 scripts\wiring_apply.py --apply
if %errorlevel% neq 0 (
    echo.
    echo [警告] 接线过程中存在未应用的改动（见上方 ❌ 输出），请修复后重新运行。
    pause
    exit /b 1
)

echo.
echo [3/3] 接线完成！
echo.
echo 下一步：按脚本上方 S6 提示运行门禁验证：
echo   cd engineering/python ^&^& py -3.11 -m pytest tests/unit/... （12 个测试文件）
echo   ruff check app/  /  mypy  /  vitest（前端 9 文件）  /  vue-tsc
echo 验证通过后可提交（建议 3 个 commit：feat(python) / feat(api) / feat(frontend)）
pause
