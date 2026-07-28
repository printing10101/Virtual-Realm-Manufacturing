@echo off
REM ablation v4 启动器（用 start /MIN 启动最小化 cmd 窗口）
REM 比 CREATE_NEW_CONSOLE 更原生稳定，窗口最小化在任务栏
REM 关闭窗口才会终止进程，最小化状态不会误关

set PY=C:\Users\Lenovo\AppData\Local\Programs\Python\Python311\python.exe
set SCRIPT=c:\Users\Lenovo\Desktop\灵境制造（上线版）\research\papers\论文相关\脚本\ablation_experiment.py
set WD=c:\Users\Lenovo\Desktop\灵境制造（上线版）
set RESULTS_DIR=c:\Users\Lenovo\Desktop\灵境制造（上线版）\research\experiments\results

REM 生成时间戳
for /f "tokens=2 delims==" %%a in ('wmic os get localdatetime /value') do set ldt=%%a
set TS=%ldt:~0,8%_%ldt:~8,6%

set LOG=%RESULTS_DIR%\ablation_v4_%TS%.log
set ERR=%RESULTS_DIR%\ablation_v4_%TS%.err.log
set PIDFILE=%RESULTS_DIR%\ablation_v4_%TS%.pid

echo === 启动 ablation v4 (resume 模式) ===
echo 时间戳: %TS%
echo 日志: %LOG%
echo 错误: %ERR%
echo.

REM 用 start /MIN 启动新的最小化 cmd 窗口
REM 标题设为 AblationV4 方便识别
REM 新窗口内的进程独立运行，关闭本窗口不影响
start "AblationV4" /MIN cmd /k "%PY% -u \"%SCRIPT%\" --dataset synthetic --ablations Full A1 A2 A3 A4_lam0.01 A4_lam0.05 A4_lam0.1 A4_lam0.5 A4_lam1.0 A6_fixed0.0 A6_fixed0.25 A6_fixed0.5 A6_fixed0.75 A6_fixed1.0 A7_MLP A7_CNN --stage1_epochs 30 --stage2_epochs 60 --output_dir \"research\papers\论文相关\脚本\results\ablation\" --resume > \"%LOG%\" 2> \"%ERR%\""

REM 等待 PID 写入（通过 powershell 获取）
timeout /t 5 /nobreak >nul

REM 获取新进程的 PID
for /f "tokens=2" %%p in ('tasklist /fi "imagename eq python.exe" /fo list ^| findstr "PID"') do set NEWPID=%%p

echo %NEWPID% > "%PIDFILE%"
echo.
echo === 启动完成 ===
echo PID=%NEWPID%
echo PID_FILE=%PIDFILE%
echo.
echo 监控命令:
echo   %PY% "%RESULTS_DIR%\_monitor_v4.py"
echo.
echo 注意: 新窗口已最小化到任务栏，标题为 "AblationV4"
echo       请勿关闭该最小化窗口，否则实验会终止
echo.
pause
