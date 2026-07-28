"""P1-6 扫描脚本：分析所有 except Exception 调用点的上下文。

分类策略：
  - file_io: 文件读写 → OSError
  - json_parse: JSON解析 → json.JSONDecodeError
  - network: 网络请求 → requests.RequestException
  - subprocess_op: 子进程 → subprocess.SubprocessError
  - import_op: 导入 → ImportError
  - value_convert: 类型转换/数值 → ValueError, TypeError
  - dict_access: 字典访问 → KeyError
  - list_access: 列表访问 → IndexError
  - attribute_access: 属性访问 → AttributeError
  - generic: 通用兜底（保留）
"""
from __future__ import annotations

import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import List, Tuple

ROOT = Path(r"c:\Users\Lenovo\Desktop\灵境制造（上线版）")
APP_DIR = ROOT / "engineering" / "python" / "app"


def classify_context(try_block: str) -> str:
    """根据 try 块内容判断异常类型。"""
    # 强信号模式
    if re.search(r"\bjson\.(loads|load)\b", try_block):
        return "json_parse"
    if re.search(r"\bjson\.dump\b", try_block):
        return "json_parse+file_io"
    if re.search(r"\bsubprocess\.(run|Popen|call|check_output)\b", try_block):
        return "subprocess_op"
    if re.search(r"\brequests\.(get|post|put|delete|patch|request)\b", try_block):
        return "network"
    if re.search(r"\bhttpx\.(get|post|Client)\b", try_block):
        return "network"
    if re.search(r"^\s*import\s+\w+|^\s*from\s+\w+\s+import", try_block, re.MULTILINE):
        return "import_op"
    if re.search(r"\bint\(|\bfloat\(|\bstr\(", try_block):
        return "value_convert"
    if re.search(r"\bopen\s*\(", try_block):
        return "file_io"
    if re.search(r"\.get\(|\[\s*['\"]", try_block):
        return "dict_access"
    return "generic"


def scan_file(py: Path) -> List[Tuple[int, str, str, str]]:
    """扫描单个文件，返回 [(行号, except子句, try块内容, 分类)]。"""
    try:
        text = py.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []

    lines = text.splitlines(keepends=True)
    results: List[Tuple[int, str, str, str]] = []

    for i, line in enumerate(lines):
        # 匹配 except Exception 或 except Exception as e
        m = re.match(r"^(\s*)except\s+Exception(\s+as\s+\w+)?\s*:", line)
        if not m:
            continue

        indent = m.group(1)
        # 向上查找对应的 try 块
        try_start = None
        brace_depth = 0
        for j in range(i - 1, -1, -1):
            prev = lines[j]
            stripped = prev.lstrip()
            if stripped.startswith("try:") and len(prev) - len(prev.lstrip()) == len(indent):
                try_start = j
                break

        if try_start is None:
            results.append((i + 1, line.rstrip(), "", "unknown"))
            continue

        # 提取 try 块内容（从 try: 下一行到 except 行）
        try_block = "".join(lines[try_start + 1 : i])
        category = classify_context(try_block)
        results.append((i + 1, line.rstrip(), try_block[:200], category))

    return results


def main() -> int:
    print("=== P1-6 except Exception 扫描 ===")
    all_results: List[Tuple[Path, int, str, str, str]] = []
    for py in APP_DIR.rglob("*.py"):
        if py.name.startswith("test_"):
            continue
        for line_no, except_clause, try_block, category in scan_file(py):
            all_results.append((py, line_no, except_clause, try_block, category))

    print(f"总计: {len(all_results)} 处 except Exception")
    print()

    # 按分类统计
    by_cat: dict = defaultdict(list)
    for py, line_no, except_clause, try_block, cat in all_results:
        by_cat[cat].append((py, line_no, except_clause))

    print("=== 分类统计 ===")
    for cat, items in sorted(by_cat.items(), key=lambda x: -len(x[1])):
        print(f"{cat}: {len(items)} 处")
    print()

    # 输出可安全收窄的明细
    safe_cats = {"json_parse", "json_parse+file_io", "subprocess_op", "import_op"}
    print("=== 可安全收窄的调用点 ===")
    for cat in safe_cats:
        if cat in by_cat:
            print(f"\n--- {cat} ({len(by_cat[cat])} 处) ---")
            for py, line_no, except_clause in by_cat[cat]:
                rel = py.relative_to(ROOT)
                print(f"  {rel}:{line_no}: {except_clause.strip()}")

    # 输出 generic 类别（需人工判断）
    print(f"\n=== generic 类别（{len(by_cat.get('generic', []))} 处，需人工判断） ===")
    for py, line_no, except_clause in by_cat.get("generic", [])[:20]:
        rel = py.relative_to(ROOT)
        print(f"  {rel}:{line_no}: {except_clause.strip()}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
