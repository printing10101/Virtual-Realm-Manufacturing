@echo off
set ROOT=c:\Users\Lenovo\Desktop\灵境制造（上线版）
cd /d "%ROOT%\python"
trae-sandbox --storage-path "%ROOT%" -- python "test_runner.py"
