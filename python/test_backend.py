#!/usr/bin/env python
"""
Python backend comprehensive test script.
Validates system environment, dependencies, service startup, and API connectivity.
"""

from __future__ import annotations

import sys
import subprocess
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

try:
    import httpx
except ImportError:
    print("FATAL: httpx is required but not installed.")
    sys.exit(1)


def test_core_imports() -> bool:
    """Test 1/5: Verify core third-party dependency modules."""
    print("\n=== Test 1/5: Core Module Import Verification ===")
    modules = ["fastapi", "uvicorn", "pydantic", "chromadb", "httpx"]
    all_pass = True

    for mod in modules:
        try:
            __import__(mod)
            print(f"  \033[92m\u2713\033[0m {mod}")
        except ImportError as e:
            print(f"  \033[91m\u2717\033[0m {mod}: {e}")
            all_pass = False

    status = "\033[92m\u2713 PASS\033[0m" if all_pass else "\033[91m\u2717 FAIL\033[0m"
    print(f"Result: {status}")
    return all_pass


def test_app_imports() -> bool:
    """Test 2/5: Verify project internal module accessibility."""
    print("\n=== Test 2/5: Application Module Import Verification ===")
    python_dir = Path(__file__).parent
    if str(python_dir) not in sys.path:
        sys.path.insert(0, str(python_dir))

    app_modules = [
        "app.main",
        "app.config",
        "app.ai.agents",
        "app.ai.workflow",
        "app.cad.generator",
        "app.rag.knowledge_base",
    ]
    all_pass = True

    for mod in app_modules:
        try:
            __import__(mod)
            print(f"  \033[92m\u2713\033[0m {mod}")
        except Exception as e:
            err_msg = str(e)[:50]
            print(f"  \033[91m\u2717\033[0m {mod}: {err_msg}")
            all_pass = False

    status = "\033[92m\u2713 PASS\033[0m" if all_pass else "\033[91m\u2717 FAIL\033[0m"
    print(f"Result: {status}")
    return all_pass


def test_server_health() -> bool:
    """Test 3/5: Verify FastAPI server startup and health check."""
    print("\n=== Test 3/5: FastAPI Server Startup Verification ===")
    python_dir = Path(__file__).parent
    port = 8765

    server = None
    try:
        server = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "app.main:app",
                "--host",
                "127.0.0.1",
                "--port",
                str(port),
            ],
            cwd=str(python_dir),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        print(f"  Starting uvicorn on port {port}...")
        time.sleep(3)

        try:
            with httpx.Client(timeout=10) as client:
                resp = client.get(f"http://127.0.0.1:{port}/health")
                if resp.status_code == 200:
                    print("  \033[92m\u2713\033[0m Health check returned 200")
                    print("  \033[92m\u2713 PASS\033[0m")
                    return True
                else:
                    print(
                        f"  \033[91m\u2717\033[0m Health check returned {resp.status_code}"
                    )
                    print("  \033[91m\u2717 FAIL\033[0m")
                    return False
        except Exception as e:
            print(f"  \033[91m\u2717\033[0m Failed to connect: {e}")
            print("  \033[91m\u2717 FAIL\033[0m")
            return False
    finally:
        if server is not None:
            server.terminate()
            try:
                server.wait(timeout=5)
            except subprocess.TimeoutExpired:
                server.kill()
            print("  Server process terminated.")


def test_api_endpoints() -> bool:
    """Test 4/5: Verify key API endpoint accessibility."""
    print("\n=== Test 4/5: API Endpoint Verification ===")
    python_dir = Path(__file__).parent
    port = 8766
    endpoints = ["/health", "/api/ollama/status", "/api/ollama/models"]

    server = None
    try:
        server = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "app.main:app",
                "--host",
                "127.0.0.1",
                "--port",
                str(port),
            ],
            cwd=str(python_dir),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        print(f"  Starting uvicorn on port {port}...")
        time.sleep(3)

        all_pass = True
        with httpx.Client(timeout=10) as client:
            for ep in endpoints:
                try:
                    resp = client.get(f"http://127.0.0.1:{port}{ep}")
                    if resp.status_code in (200, 201):
                        print(f"  \033[92m\u2713\033[0m {ep} -> {resp.status_code}")
                    else:
                        print(f"  \033[91m\u2717\033[0m {ep} -> {resp.status_code}")
                        all_pass = False
                except Exception as e:
                    print(f"  \033[91m\u2717\033[0m {ep} -> Error: {str(e)[:50]}")
                    all_pass = False

        status = (
            "\033[92m\u2713 PASS\033[0m" if all_pass else "\033[91m\u2717 FAIL\033[0m"
        )
        print(f"Result: {status}")
        return all_pass
    finally:
        if server is not None:
            server.terminate()
            try:
                server.wait(timeout=5)
            except subprocess.TimeoutExpired:
                server.kill()
            print("  Server process terminated.")


def test_ollama_connection() -> bool:
    """Test 5/5: Verify Ollama service connectivity."""
    print("\n=== Test 5/5: Ollama Service Connection Verification ===")
    try:
        with httpx.Client(timeout=5) as client:
            resp = client.get("http://localhost:11434/api/tags")
            if resp.status_code == 200:
                data = resp.json()
                models = data.get("models", [])
                model_names = [m.get("name", "unknown") for m in models]
                print("  \033[92m\u2713\033[0m Connected to Ollama successfully")
                print(
                    f"  \033[92m\u2713\033[0m Installed models: {', '.join(model_names)}"
                )
                print("  \033[92m\u2713 PASS\033[0m")
                return True
            else:
                print(
                    f"  \033[91m\u2717\033[0m Ollama returned status {resp.status_code}"
                )
                print("  \033[91m\u2717 FAIL\033[0m")
                return False
    except Exception as e:
        print(f"  \033[91m\u2717\033[0m Failed to connect to Ollama: {e}")
        print("  \033[91m\u2717 FAIL\033[0m")
        return False


def main() -> int:
    """Run all tests and generate summary report."""
    print("=" * 60)
    print("  Python Backend Test Suite")
    print("=" * 60)

    tests = [
        ("Core Module Import", test_core_imports),
        ("Application Module Import", test_app_imports),
        ("Server Startup", test_server_health),
        ("API Endpoints", test_api_endpoints),
        ("Ollama Connection", test_ollama_connection),
    ]

    results: dict[str, bool] = {}
    for name, test_func in tests:
        results[name] = test_func()

    # Print summary table
    print("\n" + "=" * 60)
    print("  Test Summary")
    print("=" * 60)

    passed = 0
    for name, result in results.items():
        status_str = (
            "\033[92m\u2713 Pass\033[0m" if result else "\033[91m\u2717 Fail\033[0m"
        )
        print(f"  {name}: {status_str}")
        if result:
            passed += 1

    total = len(tests)
    print(f"\n  Total: {passed}/{total} passed")
    print("=" * 60)

    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
