import os
import glob

root = r"c:\Users\Lenovo\Desktop\灵境制造（上线版）\python\app"
results = []
for path in glob.glob(os.path.join(root, "**", "*.py"), recursive=True):
    if "__init__.py" in path or "tests" in path or "test_" in path:
        continue
    try:
        with open(path, "r", encoding="utf-8") as f:
            line_count = sum(1 for _ in f)
        rel = path.replace(root, "")
        results.append((line_count, rel))
    except Exception:
        pass

results.sort(reverse=True)
for lines, path in results[:30]:
    print(f"{lines:6d}  {path}")
