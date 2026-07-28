@echo off
REM ablation v4 启动器（独立 cmd 窗口，脱离 IDE，可跨夜运行）
REM 使用 --resume 跳过已完成的配置（如 Full）

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

echo === ablation v4 启动 (resume 模式) ===
echo PY=%PY%
echo SCRIPT=%SCRIPT%
echo LOG=%LOG%
echo ERR=%ERR%
echo.

REM 写入 PID 文件（使用 PowerShell 获取 PID）
powershell -NoProfile -Command "$proc = Start-Process -FilePath '%PY%' -ArgumentList '-u','%SCRIPT%','--dataset','synthetic','--ablations','Full','A1','A2','A3','A4_lam0.01','A4_lam0.05','A4_lam0.1','A4_lam0.5','A4_lam1.0','A6_fixed0.0','A6_fixed0.25','A6_fixed0.5','A6_fixed0.75','A6_fixed1.0','A7_MLP','A7_CNN','--stage1_epochs','30','--stage2_epochs','60','--output_dir','research\papers\论文相关\脚本\results\ablation','--resume' -WorkingDirectory '%WD%' -RedirectStandardOutput '%LOG%' -RedirectStandardError '%ERR%' -WindowStyle Minimized -PassThru; $proc.Id | Out-File -Encoding ascii -NoNewline '%PIDFILE%'; Write-Host ('PID=' + $proc.Id)"

echo.
echo 启动完成。PID 已写入: %PIDFILE%
echo 监控: %PY% %RESULTS_DIR%\_monitor_v4.py
echo.
pause
