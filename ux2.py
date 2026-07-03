# -*- coding: utf-8 -*-
import io, os
base = os.path.join("c:", os.sep, "Users", "Lenovo", "Desktop", "\u7075\u5883\u5236\u9020\uff08\u4e0a\u7ebf\u7248\uff09")
path = os.path.join(base, "src", "views", "UXDemo.vue")
with io.open(path, "r", encoding="utf-8") as f:
    text = f.read()

q = chr(34)
sq = chr(39)
lt = chr(60)
gt = chr(62)

# title attributes
text = text.replace("title=" + q + "\u5f15\u5bfc\u6b65\u9aa4\u6570" + q, ":title=" + q + "t(" + sq + "uxDemo.statTourSteps" + sq + ")" + q)
text = text.replace("title=" + q + "\u793a\u4f8b\u5de5\u7a0b\u6570" + q, ":title=" + q + "t(" + sq + "uxDemo.statExampleCount" + sq + ")" + q)
text = text.replace("title=" + q + "\u6ce8\u518c\u547d\u4ee4\u6570" + q, ":title=" + q + "t(" + sq + "uxDemo.statCommandCount" + sq + ")" + q)

# h4 sectionFeatures
text = text.replace(lt + "h4" + gt + "\u5df2\u5b9e\u73b0\u529f\u80fd" + lt + "/h4" + gt, lt + "h4" + gt + "{{ t(" + sq + "uxDemo.sectionFeatures" + sq + ") }}" + lt + "/h4" + gt)

# label attributes
text = text.replace("label=" + q + "\u5f15\u5bfc\u6d41\u7a0b" + q, ":label=" + q + "t(" + sq + "uxDemo.featureTourLabel" + sq + ")" + q)
text = text.replace("label=" + q + "\u793a\u4f8b\u5de5\u7a0b\u5e93" + q, ":label=" + q + "t(" + sq + "uxDemo.featureGalleryLabel" + sq + ")" + q)
text = text.replace("label=" + q + "\u547d\u4ee4\u9762\u677f" + q, ":label=" + q + "t(" + sq + "uxDemo.featureCommandLabel" + sq + ")" + q)

# tagCompleted (3 times)
text = text.replace("\u5df2\u5b8c\u6210", "{{ t(" + sq + "uxDemo.tagCompleted" + sq + ") }}")

# feature descriptions
text = text.replace("5\u4e2a\u6b65\u9aa4\u3001\u8fdb\u5ea6\u8bb0\u5fc6\u3001\u54cd\u5e94\u5f0f\u8bbe\u8ba1", "{{ t(" + sq + "uxDemo.featureTourDesc" + sq + ") }}")
text = text.replace("12\u4e2a\u793a\u4f8b\u3001\u641c\u7d22\u8fc7\u6ee4\u3001\u4ee3\u7801\u9884\u89c8\u3001\u4e00\u952e\u590d\u5236", "{{ t(" + sq + "uxDemo.featureGalleryDesc" + sq + ") }}")
text = text.replace("\u5feb\u6377\u952e\u5524\u8d77\u3001\u6a21\u7cca\u641c\u7d22\u3001\u667a\u80fd\u6392\u5e8f\u3001\u4f7f\u7528\u9891\u7387\u8bb0\u5fc6", "{{ t(" + sq + "uxDemo.featureCommandDesc" + sq + ") }}")

# sectionGalleryPreview
text = text.replace(lt + "h3" + gt + "\u793a\u4f8b\u5de5\u7a0b\u5e93\u9884\u89c8" + lt + "/h3" + gt, lt + "h3" + gt + "{{ t(" + sq + "uxDemo.sectionGalleryPreview" + sq + ") }}" + lt + "/h3" + gt)

with io.open(path, "w", encoding="utf-8") as f:
    f.write(text)
print("Template part 2 done")
