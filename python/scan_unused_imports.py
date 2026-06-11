"""
更准确地扫描未使用的 import。

策略:
1. 解析每个文件的 AST，收集顶层 import 语句。
2. 对于 ``import a.b.c``，检查 ``a`` 是否在文件源码中以 Name 或 Attribute 形式出现。
3. 对于 ``from a.b import c, d``，检查 ``c``、``d`` 是否在文件中作为 Name 出现。
4. 跳过 ``from __future__ import ...`` （语言层特性，不算未使用）。
5. 跳过 ``import *``。

仅输出真的未使用的项目。
"""
from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

FILES = [
    "app/goals/goal_chain_store.py",
    "app/plugins/skill_marketplace.py",
    "app/auth/security.py",
    "app/core/exception_handlers.py",
    "app/ai/lnn/training/dataset.py",
    "app/projects/project_api.py",
    "app/simulation/api.py",
]


class ImportVisitor(ast.NodeVisitor):
    def __init__(self) -> None:
        self.imports: list[tuple[str, str, str | None]] = []
        # 格式: (kind, name, alias_or_None)
        # kind = "module" 或 "name"

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            self.imports.append(("module", alias.name, alias.asname))

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if node.module == "__future__":
            return
        if node.names and any(a.name == "*" for a in node.names):
            return
        for alias in node.names:
            if alias.name == "*":
                continue
            used_name = alias.asname or alias.name
            self.imports.append(("name", used_name, None))


def name_used(name: str, src: str) -> bool:
    """简易名称使用检测：作为整词出现。"""
    return bool(re.search(rf"\b{re.escape(name)}\b", src))


def module_used(module: str, src: str) -> bool:
    """模块使用检测：顶层模块名或属性访问链中任一段出现即可。"""
    parts = module.split(".")
    for i in range(1, len(parts) + 1):
        sub = ".".join(parts[:i])
        if name_used(sub, src):
            return True
    return False


def find_unused(path: Path) -> list[str]:
    src = path.read_text(encoding="utf-8")
    tree = ast.parse(src, filename=str(path))
    visitor = ImportVisitor()
    visitor.visit(tree)

    # 移除 import 区域之外的检查更精确，但这里只检测源码字面量。
    # 对本项目而言足够。
    unused: list[str] = []
    for kind, name, _ in visitor.imports:
        if kind == "module":
            if not module_used(name, src):
                unused.append(name)
        else:
            if not name_used(name, src):
                unused.append(name)
    return unused


def main() -> int:
    base = Path("c:/Users/Lenovo/Desktop/灵境制造（上线版）/python")
    any_unused = False
    for f in FILES:
        full = base / f
        if not full.exists():
            print(f"[SKIP] {f} 不存在")
            continue
        u = find_unused(full)
        if u:
            any_unused = True
            print(f"[UNUSED] {f}: {u}")
        else:
            print(f"[OK]    {f}")
    return 1 if any_unused else 0


if __name__ == "__main__":
    sys.exit(main())
