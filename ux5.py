# -*- coding: utf-8 -*-
import io, os
base = os.path.join("c:", os.sep, "Users", "Lenovo", "Desktop", "\u7075\u5883\u5236\u9020\uff08\u4e0a\u7ebf\u7248\uff09")
path = os.path.join(base, "src", "views", "UXDemo.vue")
with io.open(path, "r", encoding="utf-8") as f:
    text = f.read()

sq = chr(39)
t_prefix = "t(" + sq + "uxDemo."
t_suffix = sq + ")"

# new-project
text = text.replace("name: " + sq + "\u65b0\u5efa\u9879\u76ee" + sq + ",", "name: " + t_prefix + "cmdNewProjectName" + t_suffix + ",")
text = text.replace("description: " + sq + "\u521b\u5efa\u4e00\u4e2a\u65b0\u7684\u5de5\u7a0b\u9879\u76ee" + sq + ",", "description: " + t_prefix + "cmdNewProjectDesc" + t_suffix + ",")
text = text.replace("category: " + sq + "\u6587\u4ef6" + sq + ",", "category: " + t_prefix + "categoryFile" + t_suffix + ",")
text = text.replace("ElMessage.success(" + sq + "\u65b0\u5efa\u9879\u76ee\u529f\u80fd\u5df2\u89e6\u53d1" + sq + ")", "ElMessage.success(" + t_prefix + "msgNewProjectTriggered" + t_suffix + ")")

# open-project
text = text.replace("name: " + sq + "\u6253\u5f00\u9879\u76ee" + sq + ",", "name: " + t_prefix + "cmdOpenProjectName" + t_suffix + ",")
text = text.replace("description: " + sq + "\u6253\u5f00\u5df2\u6709\u7684\u5de5\u7a0b\u9879\u76ee" + sq + ",", "description: " + t_prefix + "cmdOpenProjectDesc" + t_suffix + ",")
text = text.replace("ElMessage.success(" + sq + "\u6253\u5f00\u9879\u76ee\u529f\u80fd\u5df2\u89e6\u53d1" + sq + ")", "ElMessage.success(" + t_prefix + "msgOpenProjectTriggered" + t_suffix + ")")

# save-project
text = text.replace("name: " + sq + "\u4fdd\u5b58\u9879\u76ee" + sq + ",", "name: " + t_prefix + "cmdSaveProjectName" + t_suffix + ",")
text = text.replace("description: " + sq + "\u4fdd\u5b58\u5f53\u524d\u5de5\u7a0b\u9879\u76ee" + sq + ",", "description: " + t_prefix + "cmdSaveProjectDesc" + t_suffix + ",")
text = text.replace("ElMessage.success(" + sq + "\u4fdd\u5b58\u9879\u76ee\u529f\u80fd\u5df2\u89e6\u53d1" + sq + ")", "ElMessage.success(" + t_prefix + "msgSaveProjectTriggered" + t_suffix + ")")

# export-gcode
text = text.replace("name: " + sq + "\u5bfc\u51faG\u4ee3\u7801" + sq + ",", "name: " + t_prefix + "cmdExportGCodeName" + t_suffix + ",")
text = text.replace("description: " + sq + "\u5c06\u5de5\u5177\u8def\u5f84\u5bfc\u51fa\u4e3aG\u4ee3\u7801\u6587\u4ef6" + sq + ",", "description: " + t_prefix + "cmdExportGCodeDesc" + t_suffix + ",")
text = text.replace("category: " + sq + "\u5de5\u5177\u8def\u5f84" + sq + ",", "category: " + t_prefix + "categoryToolpath" + t_suffix + ",")
text = text.replace("ElMessage.success(" + sq + "\u5bfc\u51faG\u4ee3\u7801\u529f\u80fd\u5df2\u89e6\u53d1" + sq + ")", "ElMessage.success(" + t_prefix + "msgExportGCodeTriggered" + t_suffix + ")")

with io.open(path, "w", encoding="utf-8") as f:
    f.write(text)
print("Commands 1-4 replaced")
