"""P2-7 修复验证脚本：py_compile 所有修改的文件。"""
import py_compile
import sys
from pathlib import Path

ROOT = Path(r"c:\Users\Lenovo\Desktop\灵境制造（上线版）")
APP_DIR = ROOT / "engineering" / "python" / "app"

files = list(APP_DIR.rglob("*.py"))
errors = []
ok = 0
for py in files:
    if py.name.startswith("test_"):
        continue
    try:
        py_compile.compile(str(py), doraise=True)
        ok += 1
    except py_compile.PyCompileError as e:
        errors.append(f"{py.relative_to(ROOT)}: {e}")

print(f"=== P2-7 验证 ===")
print(f"成功编译: {ok} 个文件")
if errors:
    print(f"失败: {len(errors)} 个文件")
    for err in errors:
        print(f"  {err}")
    sys.exit(1)
else:
    print("全部通过")
    sys.exit(0)
