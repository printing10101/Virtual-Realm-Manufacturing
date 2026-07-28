@echo off
REM v4 wrapper：任务计划程序调用此 cmd，再启动 Python（避免引号嵌套问题）
REM 所有路径绝对，工作目录设为项目根

cd /d "c:\Users\Lenovo\Desktop\灵境制造（上线版）"

set PYTHON="C:\Users\Lenovo\AppData\Local\Programs\Python\Python311\python.exe"
set SCRIPT="c:\Users\Lenovo\Desktop\灵境制造（上线版）\research\papers\论文相关\脚本\ablation_experiment.py"
set OUTDIR=research\papers\论文相关\脚本\results\ablation

REM 时间戳生成日志文件名
for /f "tokens=2 delims==" %%a in ('wmic os get localdatetime /value') do set ldt=%%a
set TS=%ldt:~0,8%_%ldt:~8,6%
set LOG="c:\Users\Lenovo\Desktop\灵境制造（上线版）\research\experiments\results\ablation_v4_task_%TS%.log"
set ERR="c:\Users\Lenovo\Desktop\灵境制造（上线版）\research\experiments\results\ablation_v4_task_%TS%.err.log"

%PYTHON% -u %SCRIPT% --dataset synthetic --ablations Full A1 A2 A3 A4_lam0.01 A4_lam0.05 A4_lam0.1 A4_lam0.5 A4_lam1.0 A6_fixed0.0 A6_fixed0.25 A6_fixed0.5 A6_fixed0.75 A6_fixed1.0 A7_MLP A7_CNN --stage1_epochs 30 --stage2_epochs 60 --output_dir "%OUTDIR%" --resume > %LOG% 2> %ERR%
