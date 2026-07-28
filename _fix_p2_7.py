"""P2-7 批量修复脚本：datetime.now() → datetime.now(timezone.utc)

策略：
  1. 替换 datetime.now().isoformat() → datetime.now(timezone.utc).isoformat()
  2. 替换 datetime.now().timestamp() → datetime.now(timezone.utc).timestamp()
  3. 替换比较/算术运算中的 datetime.now() → datetime.now(timezone.utc)
  4. 保留 strftime() 调用（用于文件名/显示）
  5. 自动添加 timezone 到 import 语句
  6. 跳过测试文件（test_*.py）
"""
from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import List, Tuple

ROOT = Path(r"c:\Users\Lenovo\Desktop\灵境制造（上线版）")
APP_DIR = ROOT / "engineering" / "python" / "app"


def find_files_with_datetime_now() -> List[Path]:
    """扫描所有含 datetime.now() 的 Python 文件。"""
    hits: List[Path] = []
    for py in APP_DIR.rglob("*.py"):
        if py.name.startswith("test_"):
            continue
        try:
            text = py.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        if "datetime.now()" in text:
            hits.append(py)
    return hits


def fix_content(content: str) -> Tuple[str, int]:
    """修复文件内容，返回 (新内容, 修改次数)。"""
    original = content
    count = 0

    # 1. isoformat() 调用
    new_content, n = re.subn(
        r"datetime\.now\(\)\.isoformat\(\)",
        "datetime.now(timezone.utc).isoformat()",
        content,
    )
    count += n
    content = new_content

    # 2. timestamp() 调用
    new_content, n = re.subn(
        r"datetime\.now\(\)\.timestamp\(\)",
        "datetime.now(timezone.utc).timestamp()",
        content,
    )
    count += n
    content = new_content

    # 3. 比较运算: datetime.now() < / > / <= / >=
    new_content, n = re.subn(
        r"datetime\.now\(\)\s*([<>]=?)",
        r"datetime.now(timezone.utc) \1",
        content,
    )
    count += n
    content = new_content

    # 4. 反向比较: < / > / <= / >= datetime.now()
    new_content, n = re.subn(
        r"([<>]=?)\s*datetime\.now\(\)",
        r"\1 datetime.now(timezone.utc)",
        content,
    )
    count += n
    content = new_content

    # 5. 算术运算: datetime.now() + / - timedelta
    new_content, n = re.subn(
        r"datetime\.now\(\)\s*([+\-])",
        r"datetime.now(timezone.utc) \1",
        content,
    )
    count += n
    content = new_content

    new_content, n = re.subn(
        r"([+\-])\s*datetime\.now\(\)",
        r"\1 datetime.now(timezone.utc)",
        content,
    )
    count += n
    content = new_content

    # 6. 裸 datetime.now() 赋值/参数: ts = datetime.now()
    new_content, n = re.subn(
        r"=\s*datetime\.now\(\)(?!\.)",
        "= datetime.now(timezone.utc)",
        content,
    )
    count += n
    content = new_content

    if content == original:
        return content, 0

    # 7. 修复 import 语句（如果内容被修改但 timezone 未导入）
    if "timezone.utc" in content and not _has_timezone_import(content):
        content = _add_timezone_to_import(content)

    return content, count


def _has_timezone_import(content: str) -> bool:
    """检查是否已导入 timezone。"""
    patterns = [
        r"from\s+datetime\s+import\s+[^\n]*\btimezone\b",
        r"import\s+datetime[^\n]*\btimezone\b",
        r"from\s+datetime\s+import\s+datetime\s+as\s+\w+[^\n]*,\s*timezone\b",
    ]
    for pat in patterns:
        if re.search(pat, content):
            return True
    return False


def _add_timezone_to_import(content: str) -> str:
    """在 datetime import 语句中添加 timezone。"""
    # 模式 A: from datetime import datetime, timedelta, ...
    m = re.search(r"from\s+datetime\s+import\s+([^\n]+)", content)
    if m:
        imports = m.group(1)
        if "timezone" not in imports:
            new_imports = imports.rstrip() + ", timezone"
            content = content.replace(
                f"from datetime import {imports}",
                f"from datetime import {new_imports}",
                1,
            )
            return content

    # 模式 B: import datetime
    if re.search(r"^import\s+datetime\s*$", content, re.MULTILINE):
        content = content.replace(
            "import datetime\n",
            "import datetime\nfrom datetime import timezone\n",
            1,
        )
        return content

    # 模式 C: 没有任何 datetime import（异常情况，加在文件顶部）
    content = "from datetime import timezone\n" + content
    return content


def main() -> int:
    files = find_files_with_datetime_now()
    print(f"=== P2-7 批量修复 ===")
    print(f"发现 {len(files)} 个文件含 datetime.now()")
    print()

    modified: List[str] = []
    skipped: List[str] = []
    total_fixes = 0

    for py in files:
        try:
            original = py.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as e:
            skipped.append(f"READ-ERROR: {py.relative_to(ROOT)}: {e}")
            continue

        new_content, n = fix_content(original)
        if n == 0:
            skipped.append(f"NO-CHANGE: {py.relative_to(ROOT)}")
            continue

        try:
            py.write_text(new_content, encoding="utf-8")
            modified.append(f"MODIFIED ({n} fixes): {py.relative_to(ROOT)}")
            total_fixes += n
        except OSError as e:
            skipped.append(f"WRITE-ERROR: {py.relative_to(ROOT)}: {e}")

    print(f"=== 修改汇总 (共 {total_fixes} 处) ===")
    for line in modified:
        print(f"  {line}")
    print()
    if skipped:
        print(f"=== 跳过 ===")
        for line in skipped:
            print(f"  {line}")
        print()

    # 残留检查
    print(f"=== 残留 datetime.now() 调用 ===")
    remaining = 0
    for py in APP_DIR.rglob("*.py"):
        if py.name.startswith("test_"):
            continue
        try:
            text = py.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        # 排除 strftime 调用（保留用于文件名）
        matches = re.findall(r"datetime\.now\(\)(?!.*strftime)", text)
        if matches:
            remaining += len(matches)
            print(f"  {py.relative_to(ROOT)}: {len(matches)} 处")
    print(f"总计残留: {remaining} 处")
    return 0


if __name__ == "__main__":
    sys.exit(main())
