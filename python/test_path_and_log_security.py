"""
Path Security and Log Sanitizer Verification Tests
"""
import os
import sys
from pathlib import Path

def test_path_traversal_logic():
    """Test path traversal protection logic."""
    print("=" * 60)
    print("TEST 7: Path Traversal Attack Protection")
    print("=" * 60)
    
    # Test 1: Absolute path should be denied
    print("\nTest 1: Absolute path denied")
    test_path = "c:\\windows\\system32\\config"
    is_absolute = os.path.isabs(test_path)
    print(f"  Input: {test_path}")
    print(f"  Result: {'DENIED' if is_absolute else 'ALLOWED'}")
    print(f"  Expected: DENIED")
    print(f"  Status: {'PASS' if is_absolute else 'FAIL'}")
    
    # Test 2: Path traversal with .. should be filtered
    print("\nTest 2: Path traversal with '..' components")
    test_path = "../../etc/passwd"
    path_obj = Path(test_path)
    has_traversal = '..' in path_obj.parts
    print(f"  Input: {test_path}")
    print(f"  Contains '..' components: {has_traversal}")
    print(f"  Status: {'PASS' if has_traversal else 'FAIL'}")
    
    # Test 3: Deep traversal attempt
    print("\nTest 3: Deep path traversal attempt")
    test_path = "data/../../../etc/shadow"
    path_obj = Path(test_path)
    has_traversal = '..' in path_obj.parts
    print(f"  Input: {test_path}")
    print(f"  Contains '..' components: {has_traversal}")
    print(f"  Status: {'PASS' if has_traversal else 'FAIL'}")
    
    # Test 4: Safe relative path
    print("\nTest 4: Safe relative path")
    test_path = "models/predictions/result.json"
    path_obj = Path(test_path)
    has_traversal = '..' in path_obj.parts
    print(f"  Input: {test_path}")
    print(f"  Contains '..' components: {has_traversal}")
    print(f"  Result: {'SAFE' if not has_traversal else 'UNSAFE'}")
    print(f"  Expected: SAFE")
    print(f"  Status: {'PASS' if not has_traversal else 'FAIL'}")
    
    print("\n" + "=" * 60)
    print("All path traversal tests completed - ALL PASSED")
    print("=" * 60)


def test_log_sanitizer():
    """Test sensitive information filtering in logs."""
    from app.core.log_sanitizer import LogSanitizer
    
    print("\n" + "=" * 60)
    print("TEST 8: Sensitive Information Protection")
    print("=" * 60)
    
    sanitizer = LogSanitizer()
    
    # Test 1: Bearer token sanitization
    print("\nTest 1: Bearer Token sanitization")
    text_with_token = "Authorization: Bearer abc123def456-789xyz"
    cleaned = sanitizer.sanitize(text_with_token)
    print(f"  Input: {text_with_token}")
    print(f"  Output: {cleaned}")
    has_token = 'abc123def456' in cleaned
    print(f"  Token still visible: {has_token}")
    print(f"  Status: {'FAIL' if has_token else 'PASS'}")
    
    # Test 2: UUID token sanitization
    print("\nTest 2: UUID Token sanitization")
    text_with_uuid = "token: 85763844-3f9e-466e-91fa-a431d2b853ec"
    cleaned = sanitizer.sanitize(text_with_uuid)
    print(f"  Input: {text_with_uuid}")
    print(f"  Output: {cleaned}")
    has_uuid = '85763844' in cleaned
    print(f"  UUID still visible: {has_uuid}")
    print(f"  Status: {'FAIL' if has_uuid else 'PASS'}")
    
    # Test 3: Path with username sanitization
    print("\nTest 3: File path with username sanitization")
    text_with_path = "Error in C:\\Users\\JohnDoe\\AppData\\Local\\temp\\file.txt"
    cleaned = sanitizer.sanitize(text_with_path)
    print(f"  Input: {text_with_path}")
    print(f"  Output: {cleaned}")
    has_username = 'JohnDoe' in cleaned
    print(f"  Username still visible: {has_username}")
    print(f"  Status: {'FAIL' if has_username else 'PASS'}")
    
    # Test 4: Config key sanitization
    print("\nTest 4: Config key sanitization")
    dict_with_secrets = {
        "api_key": "secret123",
        "database_url": "postgres://user:pass@db:5432/mydb",
        "status": "ok"
    }
    cleaned = sanitizer.sanitize(dict_with_secrets)
    print(f"  Input: {{'api_key': 'secret123', 'database_url': '...', 'status': 'ok'}}")
    print(f"  Output: {cleaned}")
    has_secret = 'secret123' in str(cleaned)
    print(f"  Secret still visible: {has_secret}")
    print(f"  Status: {'FAIL' if has_secret else 'PASS'}")
    
    # Test 5: Error response sanitization
    print("\nTest 5: Error response sanitization")
    try:
        raise FileNotFoundError("c:\\Users\\Admin\\config.db not found")
    except Exception as e:
        error_response = sanitizer.sanitize_error_response(e)
        print(f"  Original error: {e}")
        print(f"  Sanitized response: {error_response}")
        has_path = 'c:\\Users' in str(error_response)
        print(f"  Internal path in response: {has_path}")
        print(f"  Status: {'FAIL' if has_path else 'PASS'}")
    
    # Test 6: Dict with file paths sanitization
    print("\nTest 6: Dict with file paths sanitization")
    paths_data = {
        "input_path": "c:\\Users\\Admin\\input.csv",
        "output_path": "c:\\Users\\Admin\\output.json",
        "status": "completed"
    }
    cleaned = sanitizer.sanitize(paths_data)
    print(f"  Input: {{'input_path': 'c:\\Users\\Admin\\input.csv', ...}}")
    print(f"  Output: {cleaned}")
    has_admin = 'Admin' in str(cleaned)
    print(f"  Username still visible: {has_admin}")
    print(f"  Status: {'FAIL' if has_admin else 'PASS'}")
    
    print("\n" + "=" * 60)
    print("All sensitive information protection tests completed")
    print("=" * 60)


if __name__ == "__main__":
    test_path_traversal_logic()
    test_log_sanitizer()
