import io, os

BASE = r"C:\Users\Lenovo\Desktop\灵境制造（上线版）\engineering\python\app"
TARGETS = [
    r"api\v1\auth.py",
    r"api\v1\process_explainer.py",
    r"api\v1\signal_fusion_kb.py",
    r"api\v1\agent_gateway\inference.py",
    r"api\v1\agent_gateway\training.py",
    r"api\v1\nl2cad\routes.py",
]

LINE = "from __future__ import annotations\n"

for rel in TARGETS:
    path = os.path.join(BASE, rel)
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    # normalize: split lines keeping line endings
    lines = content.split("\n")
    new_lines = []
    removed = 0
    for ln in lines:
        # match exact statement (strip trailing spaces for compare)
        if ln.rstrip() == "from __future__ import annotations" and removed == 0:
            removed += 1
            continue
        new_lines.append(ln)
    if removed:
        new_content = "\n".join(new_lines)
        # avoid trailing newline duplication if original ended with single \n
        with open(path, "w", encoding="utf-8") as f:
            f.write(new_content)
        print(f"REMOVED future import from {rel}")
    else:
        print(f"WARN: future import line NOT FOUND in {rel} (already removed or different format)")
print("DONE")
