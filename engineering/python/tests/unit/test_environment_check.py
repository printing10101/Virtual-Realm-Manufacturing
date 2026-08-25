"""
环境检查测试

确保测试环境配置正确，避免 PYTHONPATH 遮蔽导致 flaky 测试。
"""

import sys
import subprocess
from pathlib import Path
import os


def test_python_version():
    """测试必须使用 Python 3.14"""
    python_exe = Path(r"C:\Users\Lenovo\AppData\Local\Programs\Python\Python314\python.exe")
    
    assert python_exe.exists(), f"❌ Python 3.14 not found at {python_exe}"
    
    # 验证版本
    result = subprocess.run(
        [str(python_exe), "--version"],
        capture_output=True,
        text=True,
    )
    
    version_output = result.stdout.strip()
    assert "Python 3.14" in version_output, f"❌ Expected Python 3.14, got: {version_output}"
    print(f"✓ Python version: {version_output}")


def test_no_pythonpath_shading():
    """测试无 PYTHONPATH 遮蔽"""
    # 测试在 unset PYTHONPATH 环境下运行
    if os.name == "nt":
        # Windows
        env = os.environ.copy()
        env.pop("PYTHONPATH", None)
    else:
        # Unix
        env = {**os.environ, "PYTHONPATH": ""}
    
    # 运行一个简单的模块导入测试
    result = subprocess.run(
        [
            str(Path(r"C:\Users\Lenovo\AppData\Local\Programs\Python\Python314\python.exe")),
            "-c",
            "import sys; sys.path.insert(0, 'engineering/python'); from app.core.exceptions import ValidationException; print('OK')",
        ],
        capture_output=True,
        text=True,
        env=env,
        cwd=Path.cwd(),
    )
    
    assert result.returncode == 0, f"❌ Module import failed: {result.stderr}"
    assert "OK" in result.stdout, f"❌ Unexpected output: {result.stdout}"
    print(f"✓ Module import works: {result.stdout.strip()}")


def test_ocp_loaded():
    """测试 OCP 依赖正常加载"""
    result = subprocess.run(
        [
            str(Path(r"C:\Users\Lenovo\AppData\Local\Programs\Python\Python314\python.exe")),
            "-c",
            "import cadquery; print('OCP loaded successfully')",
        ],
        capture_output=True,
        text=True,
        cwd=Path.cwd(),
    )
    
    assert result.returncode == 0, f"❌ OCP failed to load: {result.stderr}"
    print(f"✓ OCP loaded: {result.stdout.strip()}")


def test_desktop_runtime_python():
    """测试桌面运行时 Python 可用"""
    desktop_runtime_python = Path("engineering/python/desktop_runtime/runtime/python.exe")
    
    assert desktop_runtime_python.exists(), f"❌ Desktop runtime not found at {desktop_runtime_python}"
    
    # 验证版本
    result = subprocess.run(
        [str(desktop_runtime_python), "--version"],
        capture_output=True,
        text=True,
    )
    
    version_output = result.stdout.strip()
    print(f"✓ Desktop runtime Python: {version_output}")
    
    # 验证包含正确的 Python 版本
    assert "Python 3.12" in version_output, f"Expected Python 3.12.x in desktop runtime, got: {version_output}"


def test_key_modules_import():
    """测试关键模块导入"""
    modules_to_test = [
        "app.core.exceptions",
        "app.core.circuit_breaker",
        "app.core.middleware",
        "app.ai.llm.provider_base",
    ]
    
    for module in modules_to_test:
        result = subprocess.run(
            [
                str(Path(r"C:\Users\Lenovo\AppData\Local\Programs\Python\Python314\python.exe")),
                "-c",
                f"import sys; sys.path.insert(0, 'engineering/python'); import {module}; print('OK')",
            ],
            capture_output=True,
            text=True,
            cwd=Path.cwd(),
        )
        
        assert result.returncode == 0, f"❌ {module} import failed: {result.stderr}"
        print(f"✓ Module import: {module}")


def test_exceptions_import():
    """测试所有异常类可正常导入"""
    exceptions_to_test = [
        "ValidationException",
        "NotFoundException",
        "LLMException",
        "LLMTimeoutException",
        "CircuitBreakerOpenException",
        "CadException",
        "NCCodeException",
    ]
    
    for exc_name in exceptions_to_test:
        result = subprocess.run(
            [
                str(Path(r"C:\Users\Lenovo\AppData\Local\Programs\Python\Python314\python.exe")),
                "-c",
                f"import sys; sys.path.insert(0, 'engineering/python'); from app.core.exceptions import {exc_name}; print('OK')",
            ],
            capture_output=True,
            text=True,
            cwd=Path.cwd(),
        )
        
        assert result.returncode == 0, f"❌ {exc_name} import failed: {result.stderr}"
        print(f"✓ Import: {exc_name}")


if __name__ == "__main__":
    print("=" * 80)
    print("🔍 Running environment checks")
    print("=" * 80)
    
    test_python_version()
    test_no_pythonpath_shading()
    test_ocp_loaded()
    test_desktop_runtime_python()
    test_key_modules_import()
    test_exceptions_import()
    
    print("=" * 80)
    print("✅ All environment checks passed!")
    print("=" * 80)
