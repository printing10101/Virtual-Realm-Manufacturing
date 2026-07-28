@echo off
chcp 65001 >nul
title ablation v4 实验启动器（双击运行）

echo ============================================================
echo  ablation v4 实验启动器
echo  - resume 模式：跳过已完成的 Full + A1
echo  - 直接调用 Python，无窗口（pythonw）
echo  - 输出重定向到日志文件
echo  - 关闭此 cmd 窗口不会终止实验
echo ============================================================
echo.

set PYTHON_EXE=C:\Users\Lenovo\AppData\Local\Programs\Python\Python311\python.exe
set SCRIPT_PATH=c:\Users\Lenovo\Desktop\灵境制造（上线版）\research\papers\论文相关\脚本\ablation_experiment.py
set WD=c:\Users\Lenovo\Desktop\灵境制造（上线版）
set RESULTS_DIR=c:\Users\Lenovo\Desktop\灵境制造（上线版）\research\experiments\results

REM 生成时间戳
for /f "tokens=2 delims==" %%a in ('wmic os get localdatetime /value') do set ldt=%%a
set TS=%ldt:~0,8%_%ldt:~8,6%

set LOG=%RESULTS_DIR%\ablation_v4_%TS%.log
set ERR=%RESULTS_DIR%\ablation_v4_%TS%.err.log
set PIDFILE=%RESULTS_DIR%\ablation_v4_%TS%.pid

cd /d "%WD%"

echo 工作目录: %CD%
echo Python: %PYTHON_EXE%
echo 脚本: %SCRIPT_PATH%
echo 日志: %LOG%
echo.

REM 使用 start 命令启动 python，新窗口最小化但不阻塞当前窗口
REM 关闭当前 cmd 窗口不会影响新启动的 python 进程
start "ablation v4 - 请勿关闭此窗口" /MIN %PYTHON_EXE% -u "%SCRIPT_PATH%" --dataset synthetic --ablations Full A1 A2 A3 A4_lam0.01 A4_lam0.05 A4_lam0.1 A4_lam0.5 A4_lam1.0 A6_fixed0.0 A6_fixed0.25 A6_fixed0.5 A6_fixed0.75 A6_fixed1.0 A7_MLP A7_CNN --stage1_epochs 30 --stage2_epochs 60 --output_dir "research\papers\论文相关\脚本\results\ablation" --resume > "%LOG%" 2> "%ERR%"

REM 等待启动
timeout /t 5 /nobreak >nul

REM 获取新进程 PID
for /f "tokens=2" %%p in ('tasklist /fi "imagename eq python.exe" /fo list ^| findstr "PID"') do set NEWPID=%%p
echo %NEWPID% > "%PIDFILE%"

echo.
echo ============================================================
echo  启动完成！
echo  PID: %NEWPID%
echo  日志: %LOG%
echo  错误: %ERR%
echo ============================================================
echo.
echo  新的 cmd 窗口已最小化到任务栏（标题"ablation v4"）
echo  实验约需 80 小时（3-4 天）
echo.
echo  注意:
echo    1. 请勿关闭标题为"ablation v4"的最小化窗口
echo    2. 系统休眠已禁用（电源方案已修改）
echo    3. 如需中途停止: taskkill /F /PID %NEWPID%
echo.
pause
