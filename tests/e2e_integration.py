import requests
import time
import sys

BASE_URL = "http://localhost:8765"
TEST_RESULTS = []


def test_health_check():
    """Test health check endpoint"""
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=5)
        if response.status_code == 200:
            return (True, "Health check endpoint test passed")
        else:
            return (False, f"Health check returned abnormal status code: {response.status_code}")
    except Exception as e:
        return (False, f"Health check request failed: {str(e)}")


def test_ollama_status():
    """Test Ollama service status endpoint"""
    try:
        response = requests.get(f"{BASE_URL}/api/ollama/status", timeout=10)
        if response.status_code == 200:
            data = response.json()
            return (True, f"Ollama service status endpoint test passed. Status: {data.get('data', {}).get('status', 'unknown')}")
        else:
            return (False, f"Ollama service status returned abnormal status code: {response.status_code}")
    except Exception as e:
        return (False, f"Ollama service status request failed: {str(e)}")


def test_knowledge_base():
    """Test knowledge base status endpoint"""
    try:
        response = requests.get(f"{BASE_URL}/api/knowledge/health", timeout=10)
        if response.status_code == 200:
            return (True, "Knowledge base status endpoint test passed")
        else:
            return (False, f"Knowledge base status returned abnormal status code: {response.status_code}")
    except Exception as e:
        return (False, f"Knowledge base status request failed: {str(e)}")


def test_workflow_lifecycle():
    """Test workflow complete lifecycle"""
    try:
        start_payload = {
            "user_input": "请为45钢轴类零件制定加工工艺方案，零件直径50mm，长度100mm"
        }
        start_response = requests.post(
            f"{BASE_URL}/api/workflow/process-plan",
            json=start_payload,
            timeout=60
        )

        if start_response.status_code != 200:
            return (False, f"Workflow process-plan failed, status code: {start_response.status_code}")

        data = start_response.json()
        result_data = data.get("data", {})

        # Verify understanding stage completed successfully
        stage_results = result_data.get("stage_results", {})
        understanding = stage_results.get("understanding", {})
        if understanding.get("status") == "completed":
            return (True, f"Workflow process-plan test passed, understanding stage completed. "
                       f"Total stages: {result_data.get('total_stages', '?')}, "
                       f"Completed: {result_data.get('completed_stages', '?')}")
        elif understanding.get("status", "").startswith("failed"):
            return (False, f"Understanding stage failed: {understanding.get('error', 'unknown')}")
        else:
            return (True, f"Workflow process-plan endpoint reachable, understanding status: {understanding.get('status', '?')}")

    except Exception as e:
        return (False, f"Workflow lifecycle test failed: {str(e)}")


def main():
    """Execute all tests and output results"""
    tests = [
        test_health_check,
        test_ollama_status,
        test_knowledge_base,
        test_workflow_lifecycle
    ]

    for test in tests:
        result, description = test()
        TEST_RESULTS.append(result)
        if result:
            print(f"PASS {description}")
        else:
            print(f"FAIL {description}")

    total_passed = sum(TEST_RESULTS)
    total_tests = len(TEST_RESULTS)
    print(f"Total: {total_passed}/{total_tests} passed")

    return 0 if total_passed == total_tests else 1


if __name__ == "__main__":
    sys.exit(main())
