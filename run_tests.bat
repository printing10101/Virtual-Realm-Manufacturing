@echo off
setlocal enabledelayedexpansion
set ROOT=%~dp0
trae-sandbox --storage-path "%ROOT%" -- python "%ROOT%tests\run_agent_tests.py"
