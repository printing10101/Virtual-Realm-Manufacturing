"""
扫描 app/ 目录下所有 .py 文件中未使用的 import。
"""
from __future__ import annotations

import ast
import os
import re
import sys
from pathlib import Path


def find_unused(path: Path) -> list[str]:
    src = path.read_text(encoding="utf-8")
    try:
        tree = ast.parse(src, filename=str(path))
    except SyntaxError:
        return ["<SYNTAX_ERROR>"]
    imports: list[tuple[str, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                imports.append(("module", a.name))
        elif isinstance(node, ast.ImportFrom):
            if node.module == "__future__":
                continue
            for a in node.names:
                if a.name == "*":
                    continue
                imports.append(("name", a.asname or a.name))
    unused: list[str] = []
    for kind, name in imports:
        if kind == "module":
            parts = name.split(".")
            found = False
            for i in range(1, len(parts) + 1):
                if re.search(rf"\b{re.escape('.'.join(parts[:i]))}\b", src):
                    found = True
                    break
            if not found:
                unused.append(name)
        else:
            if not re.search(rf"\b{re.escape(name)}\b", src):
                unused.append(name)
    return unused


def main() -> int:
    base = Path("c:/Users/Lenovo/Desktop/灵境制造（上线版）/python")
    total_files = 0
    for root, _dirs, files in os.walk(base / "app"):
        for f in files:
            if f.endswith(".py") and not f.startswith("test_"):
                full = Path(root) / f
                u = find_unused(full)
                if u:
                    rel = full.relative_to(base)
                    print(f"{rel}: {u}")
                    total_files += 1
    print(f"\nTotal files with unused imports: {total_files}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
