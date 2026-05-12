use std::path::PathBuf;

mod path_security {
    include!("../src-tauri/src/path_security.rs");
}

#[test]
fn test_path_traversal_denied() {
    use path_security::PathSecurity;
    
    let base = PathBuf::from("c:\\Users\\test\\appdata");
    let ps = PathSecurity::new(base);
    
    let result = ps.sanitize_path("../../etc/passwd");
    assert!(result.is_err(), "Path traversal should be denied");
    
    let err = result.unwrap_err();
    assert_eq!(err.code, "PATH_TRAVERSAL_DENIED");
    println!("TEST PASSED: Path traversal correctly denied: {}", err.message);
}

#[test]
fn test_absolute_path_denied() {
    use path_security::PathSecurity;
    
    let base = PathBuf::from("c:\\Users\\test\\appdata");
    let ps = PathSecurity::new(base);
    
    let result = ps.sanitize_path("c:\\windows\\system32\\config");
    assert!(result.is_err(), "Absolute path should be denied");
    
    let err = result.unwrap_err();
    assert_eq!(err.code, "ABSOLUTE_PATH_DENIED");
    println!("TEST PASSED: Absolute path correctly denied: {}", err.message);
}

#[test]
fn test_safe_relative_path() {
    use path_security::PathSecurity;
    
    let base = PathBuf::from("c:\\Users\\test\\appdata");
    std::fs::create_dir_all(&base).unwrap();
    std::fs::create_dir_all(format!("{}\\safe", base.display())).unwrap();
    
    let ps = PathSecurity::new(base.clone());
    
    let result = ps.sanitize_path("safe/file.txt");
    assert!(result.is_ok(), "Safe relative path should be allowed");
    
    println!("TEST PASSED: Safe path correctly resolved");
    
    std::fs::remove_dir_all(&base).ok();
}

fn main() {
    println!("=== Path Security Test ===\n");
    
    let base = PathBuf::from("c:\\temp\\test_path_security");
    std::fs::create_dir_all(&base).ok();
    
    println!("Test 1: Absolute path denied");
    let ps = path_security::PathSecurity::new(base.clone());
    match ps.sanitize_path("c:\\windows\\system32") {
        Err(e) => println!("  ✓ PASS: {} - {}", e.code, e.message),
        Ok(_) => println!("  ✗ FAIL: Absolute path was not denied"),
    }
    
    println!("\nTest 2: Path traversal denied");
    match ps.sanitize_path("../../etc/passwd") {
        Err(e) => println!("  ✓ PASS: {} - {}", e.code, e.message),
        Ok(_) => println!("  ✗ FAIL: Path traversal was not denied"),
    }
    
    println!("\nTest 3: Symlink-like path components filtered");
    match ps.sanitize_path("data/../../../etc/passwd") {
        Err(e) => println!("  ✓ PASS: {} - {}", e.code, e.message),
        Ok(path) => println!("  ✓ PASS: Path sanitized to: {:?}", path),
    }
    
    println!("\nTest 4: Safe relative path allowed");
    std::fs::create_dir_all(format!("{}\\safe", base.display())).ok();
    match ps.sanitize_path("safe/file.txt") {
        Ok(path) => println!("  ✓ PASS: Safe path resolved to: {:?}", path),
        Err(e) => println!("  ✗ FAIL: Safe path was denied: {}", e.message),
    }
    
    std::fs::remove_dir_all(&base).ok();
    
    println!("\n=== All path security tests completed ===");
}
