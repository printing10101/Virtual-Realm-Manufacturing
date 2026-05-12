# Auto-run test script with embedded storage-path
import subprocess
import sys
import os

root_dir = r"c:\Users\Lenovo\Desktop\灵境制造（上线版）"
os.chdir(root_dir)

result = subprocess.run(
    ["trae-sandbox", "--storage-path", root_dir, "--", "python", "tests/run_agent_tests.py"],
    capture_output=True,
    text=True
)
print(result.stdout)
print(result.stderr)
sys.exit(result.returncode)
