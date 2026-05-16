import subprocess
import sys
import os

# Change directory
os.chdir(r"c:\Users\Lenovo\Desktop\灵境制造（上线版）")

# Get Python executable path
python_exe = sys.executable

# Run test script directly
proc = subprocess.Popen(
    [python_exe, "run_full_tests.py"],
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
    text=True,
    cwd=r"c:\Users\Lenovo\Desktop\灵境制造（上线版）",
)

output, _ = proc.communicate()
print(output)
print(f"\nExit code: {proc.returncode}")
