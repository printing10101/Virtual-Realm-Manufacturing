# -*- coding: utf-8 -*-
import io, os
base = os.path.join("c:", os.sep, "Users", "Lenovo", "Desktop", "\u7075\u5883\u5236\u9020\uff08\u4e0a\u7ebf\u7248\uff09")
path = os.path.join(base, "src", "views", "UXDemo.vue")
with io.open(path, "r", encoding="utf-8") as f:
    text = f.read()

sq = chr(39)
t_prefix = "t(" + sq + "uxDemo."
t_suffix = sq + ")"

# start-simulation
text = text.replace("name: " + sq + "\u542f\u52a8\u4eff\u771f" + sq + ",", "name: " + t_prefix + "cmdStartSimulationName" + t_suffix + ",")
text = text.replace("description: " + sq + "\u5f00\u59cb\u52a0\u5de5\u8fc7\u7a0b\u4eff\u771f\u6a21\u62df" + sq + ",", "description: " + t_prefix + "cmdStartSimulationDesc" + t_suffix + ",")
text = text.replace("category: " + sq + "\u4eff\u771f" + sq + ",", "category: " + t_prefix + "categorySimulation" + t_suffix + ",")
text = text.replace("ElMessage.success(" + sq + "\u542f\u52a8\u4eff\u771f\u529f\u80fd\u5df2\u89e6\u53d1" + sq + ")", "ElMessage.success(" + t_prefix + "msgStartSimulationTriggered" + t_suffix + ")")

# ai-feature-recognition
text = text.replace("name: " + sq + "AI\u7279\u5f81\u8bc6\u522b" + sq + ",", "name: " + t_prefix + "cmdAiFeatureName" + t_suffix + ",")
text = text.replace("description: " + sq + "\u4f7f\u7528AI\u81ea\u52a8\u8bc6\u522b\u52a0\u5de5\u7279\u5f81" + sq + ",", "description: " + t_prefix + "cmdAiFeatureDesc" + t_suffix + ",")
text = text.replace("category: " + sq + "AI" + sq + ",", "category: " + t_prefix + "categoryAI" + t_suffix + ",")
text = text.replace("ElMessage.success(" + sq + "AI\u7279\u5f81\u8bc6\u522b\u529f\u80fd\u5df2\u89e6\u53d1" + sq + ")", "ElMessage.success(" + t_prefix + "msgAiFeatureTriggered" + t_suffix + ")")

# view-examples
text = text.replace("name: " + sq + "\u67e5\u770b\u793a\u4f8b" + sq + ",", "name: " + t_prefix + "cmdViewExamplesName" + t_suffix + ",")
text = text.replace("description: " + sq + "\u6d4f\u89c8\u793a\u4f8b\u5de5\u7a0b\u5e93" + sq + ",", "description: " + t_prefix + "cmdViewExamplesDesc" + t_suffix + ",")
text = text.replace("category: " + sq + "\u5e2e\u52a9" + sq + ",", "category: " + t_prefix + "categoryHelp" + t_suffix + ",")
text = text.replace("ElMessage.success(" + sq + "\u67e5\u770b\u793a\u4f8b\u529f\u80fd\u5df2\u89e6\u53d1" + sq + ")", "ElMessage.success(" + t_prefix + "msgViewExamplesTriggered" + t_suffix + ")")

# open-settings
text = text.replace("name: " + sq + "\u7cfb\u7edf\u8bbe\u7f6e" + sq + ",", "name: " + t_prefix + "cmdOpenSettingsName" + t_suffix + ",")
text = text.replace("description: " + sq + "\u6253\u5f00\u7cfb\u7edf\u8bbe\u7f6e\u9875\u9762" + sq + ",", "description: " + t_prefix + "cmdOpenSettingsDesc" + t_suffix + ",")
text = text.replace("category: " + sq + "\u7cfb\u7edf" + sq + ",", "category: " + t_prefix + "categorySystem" + t_suffix + ",")
text = text.replace("ElMessage.success(" + sq + "\u7cfb\u7edf\u8bbe\u7f6e\u529f\u80fd\u5df2\u89e6\u53d1" + sq + ")", "ElMessage.success(" + t_prefix + "msgOpenSettingsTriggered" + t_suffix + ")")

# ElMessage success - tour completed
text = text.replace("ElMessage.success(" + sq + "\u5f15\u5bfc\u6d41\u7a0b\u5df2\u5b8c\u6210\uff01" + sq + ")", "ElMessage.success(" + t_prefix + "msgTourCompleted" + t_suffix + ")")

# ElMessage info - tour skipped (template string)
old_info = "ElMessage.info(`\u5f15\u5bfc\u6d41\u7a0b\u5df2\u8df3\u8fc7\uff08\u4ece\u7b2c ${index + 1} \u6b65\uff09`)"
new_info = "ElMessage.info(t(" + sq + "uxDemo.msgTourSkipped" + sq + ", { step: index + 1 }))"
text = text.replace(old_info, new_info)

with io.open(path, "w", encoding="utf-8") as f:
    f.write(text)
print("Commands 5-8 + ElMessage replaced")
