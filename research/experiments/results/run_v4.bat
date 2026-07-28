@echo off
title ablation v4 launcher

set PYTHON_EXE=C:\Users\Lenovo\AppData\Local\Programs\Python\Python311\python.exe
set WD=c:\Users\Lenovo\Desktop\灵境制造（上线版）
set RESULTS_DIR=c:\Users\Lenovo\Desktop\灵境制造（上线版）\research\experiments\results

for /f "tokens=2 delims==" %%a in ('wmic os get localdatetime /value') do set ldt=%%a
set TS=%ldt:~0,8%_%ldt:~8,6%

set LOG=%RESULTS_DIR%\ablation_v4_%TS%.log
set ERR=%RESULTS_DIR%\ablation_v4_%TS%.err.log
set PIDFILE=%RESULTS_DIR%\ablation_v4_%TS%.pid

cd /d "%WD%"

echo Working dir: %CD%
echo Python: %PYTHON_EXE%
echo Log: %LOG%
echo.
echo Starting ablation v4 experiment...
echo Resume mode: skipping Full + A1 (already completed)
echo Estimated time: ~80 hours
echo.
echo DO NOT CLOSE this window. You can minimize it.
echo.

%PYTHON_EXE% -u "%WD%\research\papers\论文相关\脚本\ablation_experiment.py" --dataset synthetic --ablations Full A1 A2 A3 A4_lam0.01 A4_lam0.05 A4_lam0.1 A4_lam0.5 A4_lam1.0 A6_fixed0.0 A6_fixed0.25 A6_fixed0.5 A6_fixed0.75 A6_fixed1.0 A7_MLP A7_CNN --stage1_epochs 30 --stage2_epochs 60 --output_dir "research\papers\论文相关\脚本\results\ablation" --resume > "%LOG%" 2> "%ERR%"

echo.
echo ============================================================
echo  Experiment finished at %date% %time%
echo  Log: %LOG%
echo ============================================================
pause
