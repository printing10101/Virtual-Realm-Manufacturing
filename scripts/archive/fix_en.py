# -*- coding: utf-8 -*-
import io, os
base = os.path.join("c:", os.sep, "Users", "Lenovo", "Desktop", "\u7075\u5883\u5236\u9020\uff08\u4e0a\u7ebf\u7248\uff09")
path = os.path.join(base, "src", "locales", "en.ts")
with io.open(path, "r", encoding="utf-8") as f:
    text = f.read()

lines = text.split("\n")
new_lines = []
for i, line in enumerate(lines):
    stripped = line.strip()
    # Skip standalone comma line that appears between "  }," and "// === UXDemo"
    if stripped == "," and i > 0 and lines[i-1].strip() == "}," and i + 1 < len(lines) and "UXDemo" in lines[i+1]:
        print("Removed extra comma at line " + str(i + 1))
        continue
    new_lines.append(line)

new_text = "\n".join(new_lines)
with io.open(path, "w", encoding="utf-8") as f:
    f.write(new_text)
print("Fix complete")
