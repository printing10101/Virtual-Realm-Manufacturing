import subprocess
import sys

result = subprocess.run(
    [sys.executable, "run_integration_tests_standalone.py"],
    capture_output=True,
    text=True,
    cwd=r"c:\Users\Lenovo\Desktop\灵境制造（上线版）",
    env={**__import__('os').environ}
)

print("STDOUT:")
print(result.stdout)
print("\nSTDERR:")
print(result.stderr)
print(f"\nReturn code: {result.returncode}")
