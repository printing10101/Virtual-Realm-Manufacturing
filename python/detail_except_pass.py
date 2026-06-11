#!/usr/bin/env python3
"""详细分析所有 except: pass 实例"""
import os
import re
import sys
from pathlib import Path

APP_DIR = Path(r"c:\Users\Lenovo\Desktop\灵境制造（上线版）\python\app")

EXCEPT_PASS_RE = re.compile(r"except[^:\n]*:\s*\n\s*pass\b")
EXCEPT_PASS_INLINE_RE = re.compile(r"except[^:\n]*:\s*pass\b")


def find_files():
    return sorted(p for p in APP_DIR.rglob("*.py") if "__pycache__" not in str(p))


def find_except_pass(content):
    results = []
    lines = content.split("\n")
    # 1) multi-line: except ...:\n<indent>pass
    for m in EXCEPT_PASS_RE.finditer(content):
        line = content[: m.start()].count("\n") + 1
        start = max(0, line - 3)
        end = min(len(lines), line + 3)
        results.append((line, "\n".join(lines[start:end])))
    # 2) inline: except ...: pass
    for m in EXCEPT_PASS_INLINE_RE.finditer(content):
        line = content[: m.start()].count("\n") + 1
        # 避免重复 multi-line
        if any(r[0] == line for r in results):
            continue
        start = max(0, line - 2)
        end = min(len(lines), line + 2)
        results.append((line, "\n".join(lines[start:end])))
    return sorted(results)


def main():
    files = find_files()
    total = 0
    for f in files:
        try:
            text = f.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        rel = f.relative_to(APP_DIR)
        results = find_except_pass(text)
        if not results:
            continue
        total += len(results)
        print(f"\n--- {rel} ({len(results)}) ---")
        for line, ctx in results:
            print(f"  L{line}:")
            for ln in ctx.split("\n"):
                print(f"    | {ln}")
    print(f"\n=== Total: {total} ===")


if __name__ == "__main__":
    main()
