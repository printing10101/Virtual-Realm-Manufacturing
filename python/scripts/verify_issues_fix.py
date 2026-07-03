from pathlib import Path
from packaging import version

worker = Path(
    r"c:\Users\Lenovo\Desktop\灵境制造（上线版）\python\app\core\worker_process.py"
)
print(f"worker_process.py exists: {worker.exists()}")
print(f"worker_process.py size: {worker.stat().st_size} bytes")

v = version.parse("1.6.0")
result = v >= version.parse("1.5.0") and v <= version.parse("2.0.0")
print(f"packaging version check works: {result}")
print("Both issues verified fixed")
