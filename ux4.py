# -*- coding: utf-8 -*-
import io, os
base = os.path.join("c:", os.sep, "Users", "Lenovo", "Desktop", "\u7075\u5883\u5236\u9020\uff08\u4e0a\u7ebf\u7248\uff09")
path = os.path.join(base, "src", "views", "UXDemo.vue")
with io.open(path, "r", encoding="utf-8") as f:
    text = f.read()

sq = chr(39)
t_prefix = "t(" + sq + "uxDemo."
t_suffix = sq + ")"

# tourSteps - step 1
text = text.replace("title: " + sq + "\u6b22\u8fce\u4f7f\u7528\u7075\u5883\u5236\u9020\u7cfb\u7edf" + sq + ",", "title: " + t_prefix + "tourStep1Title" + t_suffix + ",")
text = text.replace("description: " + sq + "\u8fd9\u662f\u4e00\u4e2aAI\u9a71\u52a8\u76843D\u5efa\u6a21\u4e0e\u5de5\u827a\u89c4\u5212\u7cfb\u7edf\u3002\u8ba9\u6211\u4eec\u901a\u8fc7\u51e0\u4e2a\u7b80\u5355\u7684\u6b65\u9aa4\u6765\u4e86\u89e3\u4e3b\u8981\u529f\u80fd\u3002" + sq + ",", "description: " + t_prefix + "tourStep1Desc" + t_suffix + ",")

# tourSteps - step 2
text = text.replace("title: " + sq + "\u6587\u4ef6\u7ba1\u7406" + sq + ",", "title: " + t_prefix + "tourStep2Title" + t_suffix + ",")
text = text.replace("description: " + sq + "\u5728\u8fd9\u91cc\u53ef\u4ee5\u65b0\u5efa\u3001\u6253\u5f00\u3001\u4fdd\u5b58\u5de5\u7a0b\u9879\u76ee\uff0c\u652f\u6301\u5bfc\u5165STEP\u548cDXF\u683c\u5f0f\u6587\u4ef6\u3002" + sq + ",", "description: " + t_prefix + "tourStep2Desc" + t_suffix + ",")

# tourSteps - step 3
text = text.replace("title: " + sq + "\u5bfc\u822a\u83dc\u5355" + sq + ",", "title: " + t_prefix + "tourStep3Title" + t_suffix + ",")
text = text.replace("description: " + sq + "\u901a\u8fc7\u9876\u90e8\u83dc\u5355\u53ef\u4ee5\u5feb\u901f\u8bbf\u95ee\u5de5\u4f5c\u533a\u3001\u8bbe\u7f6e\u3001\u5de5\u827a\u89c4\u5212\u7b49\u6838\u5fc3\u529f\u80fd\u6a21\u5757\u3002" + sq + ",", "description: " + t_prefix + "tourStep3Desc" + t_suffix + ",")

# tourSteps - step 4
text = text.replace("title: " + sq + "\u547d\u4ee4\u9762\u677f" + sq + ",", "title: " + t_prefix + "tourStep4Title" + t_suffix + ",")
text = text.replace("description: " + sq + "\u6309 Ctrl+K \u53ef\u4ee5\u5feb\u901f\u5524\u8d77\u547d\u4ee4\u9762\u677f\uff0c\u652f\u6301\u6a21\u7cca\u641c\u7d22\u548c\u667a\u80fd\u6392\u5e8f\uff0c\u63d0\u5347\u64cd\u4f5c\u6548\u7387\u3002" + sq + ",", "description: " + t_prefix + "tourStep4Desc" + t_suffix + ",")

# tourSteps - step 5
text = text.replace("title: " + sq + "\u51c6\u5907\u5f00\u59cb" + sq + ",", "title: " + t_prefix + "tourStep5Title" + t_suffix + ",")
text = text.replace("description: " + sq + "\u5f15\u5bfc\u5df2\u5b8c\u6210\uff01\u60a8\u53ef\u4ee5\u968f\u65f6\u4ece\u5e2e\u52a9\u83dc\u5355\u91cd\u65b0\u542f\u52a8\u5f15\u5bfc\u6d41\u7a0b\u3002\u73b0\u5728\u8ba9\u6211\u4eec\u5f00\u59cb\u63a2\u7d22\u7cfb\u7edf\u7684\u5f3a\u5927\u529f\u80fd\u5427\uff01" + sq, "description: " + t_prefix + "tourStep5Desc" + t_suffix)

with io.open(path, "w", encoding="utf-8") as f:
    f.write(text)
print("tourSteps replaced")
