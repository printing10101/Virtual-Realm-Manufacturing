@echo off
cd /d c:\Users\Lenovo\Desktop\灵境制造（上线版）
python -m pytest tests/test_agent_integration_pytest.py -v -s > test_output.txt 2>&1
type test_output.txt
