# -*- coding: utf-8 -*-
import io, os
base = os.path.join("c:", os.sep, "Users", "Lenovo", "Desktop", "\u7075\u5883\u5236\u9020\uff08\u4e0a\u7ebf\u7248\uff09")
path = os.path.join(base, "src", "views", "UXDemo.vue")
with io.open(path, "r", encoding="utf-8") as f:
    text = f.read()

sq = chr(39)

# Fix 1: tourStep5Desc - replace the partially-replaced string
old1 = "description: " + sq + "\u5f15\u5bfc{{ t(" + sq + "uxDemo.tagCompleted" + sq + ") }}\uff01\u60a8\u53ef\u4ee5\u968f\u65f6\u4ece\u5e2e\u52a9\u83dc\u5355\u91cd\u65b0{{ t(" + sq + "uxDemo.btnStartTour" + sq + ") }}\u3002\u73b0\u5728\u8ba9\u6211\u4eec\u5f00\u59cb\u63a2\u7d22\u7cfb\u7edf\u7684\u5f3a\u5927\u529f\u80fd\u5427\uff01" + sq
new1 = "description: t(" + sq + "uxDemo.tourStep5Desc" + sq + ")"
if old1 in text:
    text = text.replace(old1, new1)
    print("Fix 1 applied")
else:
    print("Fix 1 pattern not found, trying alternative...")
    # Try to find the line and show it
    for line in text.split("\n"):
        if "tourStep5Desc" in line or ("\u5f15\u5bfc{{" in line and "tagCompleted" in line):
            print("Found line: " + repr(line))

# Fix 2: msgTourCompleted
old2 = "ElMessage.success(" + sq + "\u5f15\u5bfc\u6d41\u7a0b{{ t(" + sq + "uxDemo.tagCompleted" + sq + ") }}\uff01" + sq + ")"
new2 = "ElMessage.success(t(" + sq + "uxDemo.msgTourCompleted" + sq + "))"
if old2 in text:
    text = text.replace(old2, new2)
    print("Fix 2 applied")
else:
    print("Fix 2 pattern not found, trying alternative...")
    for line in text.split("\n"):
        if "\u5f15\u5bfc\u6d41\u7a0b{{" in line and "tagCompleted" in line:
            print("Found line: " + repr(line))

with io.open(path, "w", encoding="utf-8") as f:
    f.write(text)
print("Fixes applied")
