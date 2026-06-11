#!/usr/bin/env python3
"""扫描代码库统计异常处理情况"""
import os
import re
import sys
from pathlib import Path

APP_DIR = Path(r"c:\Users\Lenovo\Desktop\灵境制造（上线版）\python\app")
CORE_DIRS = {
    "lnn": APP_DIR / "ai" / "lnn",
    "simulation": APP_DIR / "simulation",
    "process_planning": None,  # 通过搜索定位
}

EXCEPT_EXCEPTION_RE = re.compile(r"except\s+Exception\b")
# 匹配 "except ... :\n    pass" 或 "except ...: pass"
EXCEPT_PASS_RE = re.compile(r"except[^:\n]*:\s*\n\s*pass\b", re.MULTILINE)
# 单行版本
EXCEPT_PASS_INLINE_RE = re.compile(r"except[^:\n]*:\s*pass\b")


def find_files():
    return [p for p in APP_DIR.rglob("*.py") if "__pycache__" not in str(p)]


def main():
    files = find_files()
    print(f"扫描 {len(files)} 个 Python 文件")

    except_pass_files = []
    except_exception_files = []
    per_dir_count = {}

    for f in files:
        rel = f.relative_to(APP_DIR)
        text = f.read_text(encoding="utf-8", errors="ignore")
        exc_pass_matches = list(EXCEPT_PASS_RE.finditer(text)) + list(EXCEPT_PASS_INLINE_RE.finditer(text))
        # 去重 - 按行号
        seen = set()
        for m in exc_pass_matches:
            line = text[: m.start()].count("\n") + 1
            seen.add(line)
        if seen:
            except_pass_files.append((str(rel), sorted(seen)))
        exc_exc = list(EXCEPT_EXCEPTION_RE.finditer(text))
        if exc_exc:
            lines = sorted({text[: m.start()].count("\n") + 1 for m in exc_exc})
            except_exception_files.append((str(rel), lines))
            # 按顶层目录分组
            top = rel.parts[0] if rel.parts else "?"
            per_dir_count.setdefault(top, 0)
            per_dir_count[top] += len(exc_exc)

    print(f"\n[EXCEPT: PASS] 出现文件: {len(except_pass_files)}")
    total_pass = 0
    for path, lines in except_pass_files:
        total_pass += len(lines)
        print(f"  {path}: {len(lines)} 处 (行: {lines[:5]}{'...' if len(lines) > 5 else ''})")
    print(f"  总计: {total_pass} 处")

    print(f"\n[EXCEPT EXCEPTION] 出现文件: {len(except_exception_files)}")
    total_exc = sum(len(lines) for _, lines in except_exception_files)
    print(f"  总计: {total_exc} 处")

    print("\n按顶层目录统计 except Exception:")
    for d, c in sorted(per_dir_count.items(), key=lambda x: -x[1]):
        print(f"  {d}: {c}")


if __name__ == "__main__":
    main()
