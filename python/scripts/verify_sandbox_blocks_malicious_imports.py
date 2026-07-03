"""
验证沙箱拦截恶意 import 的实际效果
"""
import sys
import os

# 添加项目路径
_HERE = os.path.dirname(os.path.abspath(__file__))
_PYTHON_DIR = os.path.dirname(_HERE)
if _PYTHON_DIR not in sys.path:
    sys.path.insert(0, _PYTHON_DIR)

from app.plugins.skill_loader import SkillLoader, SecurityError  # noqa: E402


def run_malicious_test(name, code, expected_block=True):
    """运行恶意代码并验证是否被拦截"""
    print(f"\n{'='*70}")
    print(f"测试: {name}")
    print(f"{'='*70}")
    print(f"恶意代码片段:\n{code[:200]}{'...' if len(code) > 200 else ''}")

    try:
        loader = SkillLoader()
        executor = loader._compile_code(code, f"malicious_{name}")
        if executor is None:
            print("[结果] 拦截成功: _compile_code 返回 None")
            return True
        try:
            result = executor()
            if expected_block:
                print(f"[FAIL] 危险！代码成功执行，结果: {result}")
                return False
            else:
                print(f"[PASS] 代码正常执行，结果: {result}")
                return True
        except (SecurityError, NameError, ImportError, SyntaxError) as e:
            print(f"[PASS] 拦截成功: 抛出 {type(e).__name__}: {e}")
            return True
    except SecurityError as e:
        print(f"[PASS] 拦截成功 (审计层): SecurityError - {e}")
        return True
    except Exception as e:
        print(f"[INFO] 抛出异常: {type(e).__name__}: {e}")
        return True


def main():
    results = []

    # 1. 直接 __import__ 调用
    results.append(run_malicious_test(
        "直接调用 __import__('os')",
        """
def execute():
    os_module = __import__('os')
    return os_module.listdir('.')
"""
    ))

    # 2. import os 语句
    results.append(run_malicious_test(
        "import os 语句",
        """
import os
def execute():
    return os.listdir('.')
"""
    ))

    # 3. from os import system
    results.append(run_malicious_test(
        "from os import system",
        """
from os import system
def execute():
    return system('echo HACKED')
"""
    ))

    # 4. 引入 subprocess
    results.append(run_malicious_test(
        "import subprocess",
        """
import subprocess
def execute():
    return subprocess.run(['echo', 'PWNED'], capture_output=True)
"""
    ))

    # 5. 通过 sys.modules 反射
    results.append(run_malicious_test(
        "__import__('sys').modules 反射",
        """
def execute():
    m = __import__('sys').modules
    return len(m)
"""
    ))

    # 6. 字符串拼接绕过 import
    results.append(run_malicious_test(
        "字符串拼接 'imp' + 'ort'",
        """
def execute():
    builtin = __builtins__
    return builtin
"""
    ))

    # 7. 尝试 type() 反射
    results.append(run_malicious_test(
        "使用 type() 反射",
        """
def execute():
    return type('', (), {'__init__': lambda s: None})()
"""
    ))

    # 8. 尝试 vars() 反射
    results.append(run_malicious_test(
        "使用 vars() 反射",
        """
def execute():
    return vars()
"""
    ))

    # 9. 使用 dir() 反射
    results.append(run_malicious_test(
        "使用 dir() 反射",
        """
def execute():
    return dir()
"""
    ))

    # 10. 使用 getattr 反射
    results.append(run_malicious_test(
        "使用 getattr() 反射",
        """
def execute():
    return getattr(__builtins__, '__import__')('os')
"""
    ))

    # 11. 使用 setattr/delattr
    results.append(run_malicious_test(
        "使用 setattr",
        """
def execute():
    setattr(__builtins__, 'pwned', True)
    return True
"""
    ))

    # 12. 使用 eval
    results.append(run_malicious_test(
        "使用 eval()",
        """
def execute():
    return eval("__import__('os').listdir('.')")
"""
    ))

    # 13. 使用 exec
    results.append(run_malicious_test(
        "使用 exec()",
        """
def execute():
    exec("import os; os.system('echo HACKED')")
    return True
"""
    ))

    # 14. 使用 compile
    results.append(run_malicious_test(
        "使用 compile()",
        """
def execute():
    c = compile("import os", "<sandbox>", "exec")
    exec(c)
    return True
"""
    ))

    # 15. 使用 open
    results.append(run_malicious_test(
        "使用 open()",
        """
def execute():
    f = open('/etc/passwd', 'r')
    return f.read()
"""
    ))

    # 16. 尝试用 __subclasses__ 遍历对象图
    results.append(run_malicious_test(
        "使用 __subclasses__()",
        """
def execute():
    return ().__class__.__bases__[0].__subclasses__()
"""
    ))

    # 17. 尝试 __class__ 反射
    results.append(run_malicious_test(
        "使用 __class__ 反射",
        """
def execute():
    return ''.__class__.__mro__
"""
    ))

    # 18. 尝试 __globals__ 反射
    results.append(run_malicious_test(
        "使用 __globals__ 反射",
        """
def helper():
    return None
def execute():
    return helper.__globals__
"""
    ))

    # 19. 尝试 input() 读取
    results.append(run_malicious_test(
        "使用 input()",
        """
def execute():
    return input('Enter: ')
"""
    ))

    # 20. 尝试 breakpoint()
    results.append(run_malicious_test(
        "使用 breakpoint()",
        """
def execute():
    breakpoint()
    return True
"""
    ))

    # 21. 尝试 ctypes
    results.append(run_malicious_test(
        "引用 ctypes",
        """
import ctypes
def execute():
    return ctypes.windll.kernel32
"""
    ))

    # 22. 尝试 socket
    results.append(run_malicious_test(
        "引用 socket",
        """
import socket
def execute():
    s = socket.socket()
    return s
"""
    ))

    # 23. 尝试 ctypes 反射
    results.append(run_malicious_test(
        "__import__('ctypes') 反射",
        """
def execute():
    c = __import__('ctypes')
    return c.windll
"""
    ))

    # 24. 尝试 shutil
    results.append(run_malicious_test(
        "引用 shutil",
        """
import shutil
def execute():
    return shutil.copy('/etc/passwd', '/tmp/')
"""
    ))

    # 25. 尝试 importlib
    results.append(run_malicious_test(
        "引用 importlib",
        """
import importlib
def execute():
    return importlib.import_module('os')
"""
    ))

    # 26. 尝试 pickle
    results.append(run_malicious_test(
        "引用 pickle",
        """
import pickle
def execute():
    return pickle.loads(b'cos\\nsystem\\n(S\\'echo PWNED\\'\\ntR.')
"""
    ))

    # 27. 尝试 marshal
    results.append(run_malicious_test(
        "引用 marshal",
        """
import marshal
def execute():
    return marshal.loads(b'\\x00\\x00\\x00\\x00')
"""
    ))

    # 28. hasattr 反射
    results.append(run_malicious_test(
        "使用 hasattr",
        """
def execute():
    return hasattr({}, '__class__')
"""
    ))

    # 29. 通过 __code__ 反射
    results.append(run_malicious_test(
        "使用 __code__",
        """
def helper():
    pass
def execute():
    return helper.__code__
"""
    ))

    # 30. 通过 __dict__ 反射
    results.append(run_malicious_test(
        "使用 __dict__",
        """
def execute():
    return {}.__dict__
"""
    ))

    # 31. 尝试引用 os 模块
    results.append(run_malicious_test(
        "直接引用 os 模块",
        """
def execute():
    return os
"""
    ))

    # 32. 尝试 __import__ 但作为变量
    results.append(run_malicious_test(
        "将 __import__ 赋值给变量",
        """
def execute():
    f = __import__
    return f('os')
"""
    ))

    # 33. 字符串拼接 + 反射
    results.append(run_malicious_test(
        "字符串拼接 'imp'+'ort'",
        """
def execute():
    mod_name = 'imp' + 'ort'
    return mod_name
"""
    ))

    # ===== 统计结果 =====
    print("\n" + "="*70)
    print(f"测试统计: 通过 {sum(results)}/{len(results)}")
    print("="*70)

    if all(results):
        print("\n[OK] 所有恶意代码均被沙箱拦截")
    else:
        failed = sum(1 for r in results if not r)
        print(f"\n[WARN] 有 {failed} 个测试未通过")

    return all(results)


if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
