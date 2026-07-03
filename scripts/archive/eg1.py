# -*- coding: utf-8 -*-
import io, os
base = os.path.join("c:", os.sep, "Users", "Lenovo", "Desktop", "\u7075\u5883\u5236\u9020\uff08\u4e0a\u7ebf\u7248\uff09")
path = os.path.join(base, "src", "examples", "ExampleGallery.vue")
with io.open(path, "r", encoding="utf-8") as f:
    text = f.read()

q = chr(34)
sq = chr(39)

# placeholder attributes
text = text.replace("placeholder=" + q + "\u641c\u7d22\u793a\u4f8b..." + q, ":placeholder=" + q + "t(" + sq + "exampleGallery.placeholderSearch" + sq + ")" + q)
text = text.replace("placeholder=" + q + "\u5206\u7c7b" + q, ":placeholder=" + q + "t(" + sq + "exampleGallery.placeholderCategory" + sq + ")" + q)
text = text.replace("placeholder=" + q + "\u96be\u5ea6" + q, ":placeholder=" + q + "t(" + sq + "exampleGallery.placeholderDifficulty" + sq + ")" + q)
text = text.replace("placeholder=" + q + "\u6392\u5e8f" + q, ":placeholder=" + q + "t(" + sq + "exampleGallery.placeholderSort" + sq + ")" + q)

# sort options (el-option label)
text = text.replace("label=" + q + "\u540d\u79f0" + q + "\n              value=" + q + "name" + q, ":label=" + q + "t(" + sq + "exampleGallery.sortName" + sq + ")" + q + "\n              value=" + q + "name" + q)
text = text.replace("label=" + q + "\u66f4\u65b0\u65f6\u95f4" + q + "\n              value=" + q + "date" + q, ":label=" + q + "t(" + sq + "exampleGallery.sortUpdated" + sq + ")" + q + "\n              value=" + q + "date" + q)
text = text.replace("label=" + q + "\u4e0b\u8f7d\u6b21\u6570" + q + "\n              value=" + q + "downloads" + q, ":label=" + q + "t(" + sq + "exampleGallery.sortDownloads" + sq + ")" + q + "\n              value=" + q + "downloads" + q)
text = text.replace("label=" + q + "\u96be\u5ea6" + q + "\n              value=" + q + "difficulty" + q, ":label=" + q + "t(" + sq + "exampleGallery.sortDifficulty" + sq + ")" + q + "\n              value=" + q + "difficulty" + q)

# table columns
text = text.replace("label=" + q + "\u540d\u79f0" + q + "\n          width=" + q + "200" + q, ":label=" + q + "t(" + sq + "exampleGallery.colName" + sq + ")" + q + "\n          width=" + q + "200" + q)
text = text.replace("label=" + q + "\u63cf\u8ff0" + q + "\n          min-width=" + q + "300" + q, ":label=" + q + "t(" + sq + "exampleGallery.colDescription" + sq + ")" + q + "\n          min-width=" + q + "300" + q)
text = text.replace("label=" + q + "\u5206\u7c7b" + q + "\n          width=" + q + "120" + q, ":label=" + q + "t(" + sq + "exampleGallery.colCategory" + sq + ")" + q + "\n          width=" + q + "120" + q)
text = text.replace("label=" + q + "\u4e0b\u8f7d" + q + "\n          width=" + q + "100" + q, ":label=" + q + "t(" + sq + "exampleGallery.colDownloads" + sq + ")" + q + "\n          width=" + q + "100" + q)
text = text.replace("label=" + q + "\u66f4\u65b0\u65f6\u95f4" + q + "\n          width=" + q + "120" + q, ":label=" + q + "t(" + sq + "exampleGallery.colUpdatedAt" + sq + ")" + q + "\n          width=" + q + "120" + q)
text = text.replace("label=" + q + "\u64cd\u4f5c" + q + "\n          width=" + q + "180" + q, ":label=" + q + "t(" + sq + "exampleGallery.colActions" + sq + ")" + q + "\n          width=" + q + "180" + q)

# tab panes
text = text.replace("label=" + q + "\u8bf4\u660e" + q + "\n            name=" + q + "details" + q, ":label=" + q + "t(" + sq + "exampleGallery.tabDetails" + sq + ")" + q + "\n            name=" + q + "details" + q)
text = text.replace("label=" + q + "\u4ee3\u7801" + q + "\n            name=" + q + "code" + q, ":label=" + q + "t(" + sq + "exampleGallery.tabCode" + sq + ")" + q + "\n            name=" + q + "code" + q)

# preview dialog title
text = text.replace("title=" + q + "\u4ee3\u7801\u9884\u89c8" + q, ":title=" + q + "t(" + sq + "exampleGallery.previewTitle" + sq + ")" + q)

with io.open(path, "w", encoding="utf-8") as f:
    f.write(text)
print("Template part 1 done")
