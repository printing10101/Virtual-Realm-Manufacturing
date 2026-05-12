@echo off
cd /d c:\Users\Lenovo\Desktop\灵境制造（上线版）\python
python run_8step_test.py > test_output.txt 2>&1
type test_output.txt
