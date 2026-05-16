import requests
import os

print("=== TEST 9: Frontend-Backend Integration Chain ===\n")

BASE_URL = "http://127.0.0.1:8001"

# Read token - try multiple locations
token_path = None
for path in [".lnn_token", "python/.lnn_token", os.path.expanduser("~/.lnn_token")]:
    if os.path.exists(path):
        token_path = path
        break

if not token_path:
    print("Warning: No token file found, using placeholder")
    token = "test-token"
else:
    with open(token_path) as f:
        token = f.read().strip()
    print(f"Token loaded from: {token_path}\n")

headers = {"Authorization": f"Bearer {token}"}

all_pass = True


def test(name, url, expected=200, use_auth=False, method="GET"):
    global all_pass
    print(f"{name}:")
    try:
        hdrs = headers.copy() if use_auth else {}
        if method == "GET":
            r = requests.get(url, headers=hdrs, timeout=5)
        elif method == "POST":
            r = requests.post(url, headers=hdrs, json={}, timeout=5)

        status = r.status_code
        print(f"   Status: {status} (expected: {expected})")

        if status == 200:
            try:
                data = r.json()
                if "data" in data:
                    if isinstance(data["data"], dict) and "models" in data["data"]:
                        print(f"   Models: {len(data['data']['models'])} available")
                    elif isinstance(data["data"], list):
                        print(f"   Items: {len(data['data'])}")
            except:
                pass

        passed = status == expected
        print(f"   Result: {'PASS' if passed else 'FAIL'}")
        if not passed:
            all_pass = False
    except requests.exceptions.ConnectionError:
        print("   Connection refused - server not running")
        print("   Result: FAIL (server down)")
        all_pass = False
    except Exception as e:
        print(f"   Error: {e}")
        print("   Result: FAIL")
        all_pass = False
    print()


# Run tests
test("1. Health Check", f"{BASE_URL}/api/health", expected=200)
test(
    "2. Model List (with auth)",
    f"{BASE_URL}/api/v1/lnn/models",
    expected=200,
    use_auth=True,
)
test(
    "3. Task List (with auth)",
    f"{BASE_URL}/api/v1/lnn/tasks",
    expected=200,
    use_auth=True,
)
test("4. Unauthorized Access", f"{BASE_URL}/api/v1/lnn/models", expected=401)
test("5. OpenAPI Docs (public)", f"{BASE_URL}/api/openapi.json", expected=200)

print("=" * 60)
if all_pass:
    print("=== ALL INTEGRATION TESTS PASSED ===")
else:
    print("=== SOME TESTS FAILED (check server status) ===")
print("=" * 60)
