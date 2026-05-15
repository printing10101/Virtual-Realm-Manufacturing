"""
CORS curl test script - validates CORS headers for different environments.

Tests production mode (LINGJING_ENV=production) and development mode
(LINGJING_ENV=development) by sending OPTIONS preflight requests and
checking the Access-Control-Allow-Origin response header.
"""
import subprocess
import sys
import os
import time


BASE_URL = "http://127.0.0.1:8765"


def run_curl(origin: str) -> dict:
    cmd = [
        "curl.exe", "-s", "-o", "NUL", "-D", "-",
        "-X", "OPTIONS",
        f"{BASE_URL}/api/health",
        "-H", f"Origin: {origin}",
        "-H", "Access-Control-Request-Method: GET",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
    headers = {}
    for line in result.stdout.splitlines():
        if ":" in line:
            key, _, value = line.partition(":")
            headers[key.strip().lower()] = value.strip()
    return headers


def test_environment(env_name: str, tests: list[tuple[str, str, str | None]]):
    print(f"{'='*60}")
    print(f"  CORS Tests: {env_name.upper()} MODE")
    print(f"{'='*60}")
    print()

    passed = 0
    failed = 0

    for label, origin, expected_origin in tests:
        headers = run_curl(origin)
        acao = headers.get("access-control-allow-origin", "<NOT SET>")

        if expected_origin is None:
            status = "PASS" if acao == "<NOT SET>" or acao == "" else "FAIL"
        else:
            status = "PASS" if acao == expected_origin else "FAIL"

        if status == "PASS":
            passed += 1
        else:
            failed += 1

        print(f"  [{status}] {label}")
        print(f"         Origin: {origin}")
        print(f"         Access-Control-Allow-Origin: {acao}")
        if expected_origin:
            print(f"         Expected: {expected_origin}")
        print()

    print(f"  Results: {passed} passed, {failed} failed")
    print()
    return failed == 0


def main():
    env = os.environ.get("LINGJING_ENV", "production")
    print(f"Environment: LINGJING_ENV={env}")
    print()

    if env == "production":
        test_environment("production", [
            ("localhost:5173 (allowed)", "http://localhost:5173", "http://localhost:5173"),
            ("localhost:8080 (allowed)", "http://localhost:8080", "http://localhost:8080"),
            ("localhost:3000 (allowed)", "http://localhost:3000", "http://localhost:3000"),
            ("localhost no port (allowed)", "http://localhost", "http://localhost"),
            ("evil.com (blocked)", "https://evil.com", None),
            ("https localhost (blocked)", "https://localhost:5173", None),
            ("tauri://localhost (blocked)", "tauri://localhost", None),
            ("127.0.0.1 (blocked)", "http://127.0.0.1:8080", None),
        ])
    elif env == "development":
        test_environment("development", [
            ("localhost:5173 (allowed)", "http://localhost:5173", "http://localhost:5173"),
            ("localhost:8080 (allowed)", "http://localhost:8080", "http://localhost:8080"),
            ("evil.com (allowed)", "https://evil.com", "https://evil.com"),
            ("any origin (allowed)", "https://random.example.com", "https://random.example.com"),
        ])


if __name__ == "__main__":
    main()