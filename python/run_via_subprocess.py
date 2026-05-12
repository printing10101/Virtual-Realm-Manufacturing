"""Run tests via subprocess to bypass terminal issue."""
import subprocess, sys, os
from pathlib import Path

os.chdir(r"c:\Users\Lenovo\Desktop\灵境制造（上线版）")
result = subprocess.run(
    [sys.executable, "-m", "pytest", "tests/test_agent_integration_pytest.py", "-v", "-s"],
    capture_output=True,
    text=True,
    cwd=r"c:\Users\Lenovo\Desktop\灵境制造（上线版）"
)
print("STDOUT:")
print(result.stdout)
print("\nSTDERR:")
print(result.stderr)
print(f"\nReturn code: {result.returncode}")
