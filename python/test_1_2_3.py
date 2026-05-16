import urllib.request
import json
import time

# Test 1: Start training
print("=" * 50)
print("TEST 1+2+3: Training + SSE Event Stream")
print("=" * 50)

body = json.dumps(
    {
        "model_name": "cfc",
        "data_path": "C:\\Users\\Lenovo\\AppData\\Local\\Temp\\uniwear.csv",
        "hyperparameters": {
            "learning_rate": 0.001,
            "epochs": 15,
            "batch_size": 32,
            "optimizer": "adam",
        },
        "device": "cpu",
    }
).encode()

start1 = time.time()
req = urllib.request.Request(
    "http://localhost:8000/api/v1/lnn/train",
    data=body,
    headers={"Content-Type": "application/json"},
    method="POST",
)
resp = urllib.request.urlopen(req)
elapsed1 = time.time() - start1
result = json.loads(resp.read())
resp.close()

job_id = result["data"]["job_id"]
print(f"[TEST 1] Response time: {elapsed1:.2f}s (requirement: <3s)")
print(f"[TEST 1] Job ID: {job_id}")
print(f"[TEST 1] Status: {result['data']['status']}")
print(
    f"TEST 1: {'PASS' if elapsed1 < 3 and result['data']['status'] == 'queued' else 'FAIL'}"
)

# Test 2: SSE Connection
print("\n[TEST 2] Connecting to SSE stream...")
start2 = time.time()
req2 = urllib.request.Request(
    f"http://localhost:8000/api/v1/jobs/{job_id}/stream",
    headers={"Accept": "text/event-stream"},
)
resp2 = urllib.request.urlopen(req2)
elapsed2 = time.time() - start2
print(f"[TEST 2] Connection established in {elapsed2:.2f}s (requirement: <5s)")
print(f"[TEST 2] Status code: {resp2.status} (requirement: no 4xx/5xx)")
pass2 = elapsed2 < 5 and resp2.status == 200
print(f"TEST 2: {'PASS' if pass2 else 'FAIL'}")

# Test 3: Event Sequence
print("\n[TEST 3] Capturing event sequence...")
events = []
event_types = []
deadline = time.time() + 60  # max 60 seconds
current_event = None
current_data = []

while time.time() < deadline:
    line = resp2.readline()
    if not line:
        break
    decoded = line.decode("utf-8").rstrip("\n").rstrip("\r")

    if decoded.startswith("event: "):
        if current_event:
            events.append({"type": current_event, "data": "".join(current_data)})
            event_types.append(current_event)
        current_event = decoded[7:]
        current_data = []
    elif decoded.startswith("data: "):
        current_data.append(decoded[6:])
    elif decoded == "" and current_event:
        events.append({"type": current_event, "data": "".join(current_data)})
        event_types.append(current_event)
        current_event = None
        current_data = []

if current_event:
    events.append({"type": current_event, "data": "".join(current_data)})
    event_types.append(current_event)

resp2.close()

print(f"\n[TEST 3] Captured {len(events)} events")
print(f"[TEST 3] Event types in order: {' → '.join(event_types)}")

# Validate sequence
valid_sequence = True
expected_order = ["queued", "started"]

# Check queued first
if len(event_types) < 1 or event_types[0] != "queued":
    valid_sequence = False
    print("  FAIL: First event should be 'queued'")

# Check started second
if len(event_types) < 2 or event_types[1] != "started":
    valid_sequence = False
    print("  FAIL: Second event should be 'started'")

# Check progress events (at least 3)
progress_count = sum(1 for t in event_types if t == "progress")
print(f"  Progress events: {progress_count} (requirement: >=3)")
if progress_count < 3:
    valid_sequence = False
    print(f"  FAIL: Need at least 3 progress events, got {progress_count}")

# Check complete
if event_types[-1] != "complete" and event_types[-1] != "failed":
    valid_sequence = False
    print(
        f"  FAIL: Last event should be 'complete' or 'failed', got '{event_types[-1]}'"
    )

# Verify progress events have data
for e in events:
    if e["type"] == "progress":
        try:
            d = json.loads(e["data"])
            print(f"  Progress: {d.get('percent', '?')}% - {d.get('message', '')}")
        except:
            pass

# Print detailed results
for i, e in enumerate(events):
    print(f"  [{i + 1}] event: {e['type']}")

if event_types[-1] == "complete":
    print(f"\nTEST 3: {'PASS' if valid_sequence else 'FAIL'}")
else:
    print(f"\nTEST 3: FAIL (Task ended with '{event_types[-1]}' instead of 'complete')")

print("\n" + "=" * 50)
print(
    f"SUMMARY: Test 1 {'PASS' if elapsed1 < 3 else 'FAIL'} | Test 2 {'PASS' if pass2 else 'FAIL'} | Test 3 {'PASS' if valid_sequence and event_types[-1] == 'complete' else 'FAIL'}"
)
print("=" * 50)
