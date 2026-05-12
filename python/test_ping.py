import urllib.request, json
try:
    r = urllib.request.urlopen("http://127.0.0.1:8000/api/health/ping", timeout=5)
    print(f"OK: {r.status} {r.read().decode()}")
except Exception as e:
    print(f"FAIL: {e}")
