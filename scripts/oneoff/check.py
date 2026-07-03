# -*- coding: utf-8 -*-
import io, os
base = os.path.join("c:", os.sep, "Users", "Lenovo", "Desktop", "\u7075\u5883\u5236\u9020\uff08\u4e0a\u7ebf\u7248\uff09")
path = os.path.join(base, "src", "views", "UXDemo.vue")
with io.open(path, "r", encoding="utf-8") as f:
    lines = f.readlines()

remaining = []
in_comment_block = False
for i, line in enumerate(lines, 1):
    stripped = line.strip()
    if in_comment_block:
        if "*/" in stripped:
            in_comment_block = False
        continue
    if stripped.startswith("/*"):
        if "*/" not in stripped:
            in_comment_block = True
        continue
    if stripped.startswith("//") or stripped.startswith("<!--"):
        continue
    for c in line:
        if "\u4e00" <= c <= "\u9fff":
            remaining.append((i, line.rstrip()))
            break

print("Remaining lines with Chinese (non-comment): " + str(len(remaining)))
for ln, content in remaining:
    print("  Line " + str(ln) + ": " + content)
