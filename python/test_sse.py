import urllib.request
import time

job_id = "lnn_training-ea5323933d1b"
uri = f"http://localhost:8000/api/v1/jobs/{job_id}/stream"

start = time.time()
try:
    req = urllib.request.Request(uri, headers={"Accept": "text/event-stream"})
    resp = urllib.request.urlopen(req, timeout=5)
    elapsed = time.time() - start
    print(f"Status: {resp.status}, Connect time: {elapsed:.2f}s")

    if resp.status == 200:
        count = 0
        deadline = time.time() + 8
        while time.time() < deadline and count < 15:
            line = resp.readline()
            if line:
                decoded = line.decode("utf-8").rstrip("\n").rstrip("\r")
                if decoded:
                    count += 1
                    print(f"[{count}] {decoded}")
    resp.close()
except Exception as e:
    print(f"ERROR: {e}")
