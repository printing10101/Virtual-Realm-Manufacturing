"""Start the FastAPI server for testing"""

import subprocess
import sys
import os

os.chdir(os.path.dirname(os.path.abspath(__file__)))
cmd = [
    sys.executable,
    "-m",
    "uvicorn",
    "app.main:app",
    "--host",
    "0.0.0.0",
    "--port",
    "8000",
]
print(f"Starting: {' '.join(cmd)}")
subprocess.run(cmd)
