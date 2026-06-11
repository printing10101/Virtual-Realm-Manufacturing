"""验收检测脚本：覆盖所有用户验收要求

运行方式（在 python/ 目录下）：
    python verify_security_fix.py
"""
import sys
from pathlib import Path

# 强制 stdout 使用 utf-8 编码，避免 Windows 终端 gbk 编码问题
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass

sys.path.insert(0, str(Path(__file__).resolve().parent))

# 仅使用 ASCII 字符，避免任何终端编码问题
PASS = "[PASS]"
FAIL = "[FAIL]"
OK = "[OK]"

# ---------------------------------------------------------------------------
# 1. 静态扫描：检测 eval() / exec() 真实调用
# ---------------------------------------------------------------------------
print("=" * 60)
print("[1] Static scan: detect eval/exec real calls")
print("=" * 60)

import ast

target = Path("app/rules/safety_constraint_rules.py")
if not target.exists():
    # 兼容从其它目录调用
    target = Path(__file__).resolve().parent / "app/rules/safety_constraint_rules.py"

source = target.read_text(encoding="utf-8")
tree = ast.parse(source, filename=str(target))
offenders = []
for node in ast.walk(tree):
    if isinstance(node, ast.Call):
        func = node.func
        if isinstance(func, ast.Name) and func.id in {"eval", "exec", "compile"}:
            offenders.append(f"line {node.lineno}: {func.id}(...)")
        if isinstance(func, ast.Attribute) and func.attr in {"eval", "exec"}:
            offenders.append(f"line {node.lineno}: {func.attr}(...)")

if offenders:
    print(f"  {FAIL}: found {len(offenders)} executable entry points")
    for o in offenders:
        print(f"     - {o}")
    sys.exit(1)
else:
    print(f"  {PASS}: no eval/exec/compile real calls")

# ---------------------------------------------------------------------------
# 2. 检测安全方案导入
# ---------------------------------------------------------------------------
print()
print("=" * 60)
print("[2] Security scheme presence")
print("=" * 60)

import re

has_ast = bool(re.search(r"^import ast|^from ast", source, re.MULTILINE))
has_simpleeval = "simpleeval" in source
has_safe_eval_def = bool(re.search(r"def\s+\w*eval\w*", source))

print(f"  import ast:                {has_ast}")
print(f"  simpleeval import:         {has_simpleeval}")
print(f"  def *eval* function:       {has_safe_eval_def}")

if has_ast or has_simpleeval or has_safe_eval_def:
    print(f"  {PASS}: at least one security scheme is in place")
else:
    print(f"  {FAIL}: no security scheme found")
    sys.exit(1)

# ---------------------------------------------------------------------------
# 3. 用户验收用例
# ---------------------------------------------------------------------------
print()
print("=" * 60)
print("[3] User acceptance test cases")
print("=" * 60)

from app.rules.safety_constraint_rules import safe_eval_math_expression

# 3.1 正常表达式
r1 = safe_eval_math_expression("10.5+20.3*2")
print(f"  10.5+20.3*2  -> {r1}  (expected 51.1)")
if r1 == 51.1:
    print(f"  {PASS}: normal expression")
else:
    print(f"  {FAIL}: normal expression")
    sys.exit(1)

# 3.2 恶意代码
r2 = safe_eval_math_expression("__import__('os').system('echo hack')")
print(f"  malicious code  -> {r2}  (expected 0.0)")
if r2 == 0.0:
    print(f"  {PASS}: malicious payload rejected")
else:
    print(f"  {FAIL}: malicious payload not rejected")
    sys.exit(1)

# 3.3 边界条件
boundary_cases = [
    ("", 0.0),
    ("abc", 0.0),
    ("1**2", 0.0),
    ("1/0", 0.0),
    (None, 0.0),
    (123, 0.0),
]
all_ok = True
for expr, expected in boundary_cases:
    actual = safe_eval_math_expression(expr)
    status = OK if actual == expected else FAIL
    if actual != expected:
        all_ok = False
    print(f"  {status} {str(expr)!r:30s} -> {actual} (expected {expected})")
if all_ok:
    print(f"  {PASS}: all boundary cases")
else:
    print(f"  {FAIL}: some boundary cases failed")
    sys.exit(1)

# ---------------------------------------------------------------------------
# 4. 性能 smoke test
# ---------------------------------------------------------------------------
print()
print("=" * 60)
print("[4] Performance smoke test")
print("=" * 60)

import timeit

iterations = 10000
t_safe = timeit.timeit(
    "safe_eval_math_expression('10.5+20.3*2')",
    globals={"safe_eval_math_expression": safe_eval_math_expression},
    number=iterations,
)
print(f"  safe_eval_math_expression: {iterations} iters in {t_safe:.3f}s "
      f"({iterations / t_safe:.0f} ops/s)")
print(f"  {PASS}: performance smoke test completed")

print()
print("=" * 60)
print("All acceptance checks PASSED")
print("=" * 60)
