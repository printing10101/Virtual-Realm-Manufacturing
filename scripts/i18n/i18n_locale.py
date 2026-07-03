# -*- coding: utf-8 -*-
import os
BASE = r'c:\Users\Lenovo\Desktop\灵境制造（上线版）'

ZH = os.path.join(BASE, 'src', 'locales', 'zh-CN.ts')
EN = os.path.join(BASE, 'src', 'locales', 'en.ts')

with open(ZH, 'r', encoding='utf-8') as f:
    content = f.read()

zh_ns = """  // === NLInputPanel.vue ===
  nlInputPanel: {
    welcomeGreeting: "\u4f60\u597d\uff01\u6211\u662f\u7075\u5883\u5236\u9020AI\u52a9\u624b\u3002",
    welcomeHint: "\u8bf7\u63cf\u8ff0\u4f60\u60f3\u8981\u521b\u5efa\u7684\u96f6\u4ef6\uff0c\u4f8b\u5982\uff1a\"\u521b\u5efa\u4e00\u4e2a\u957f50mm\u3001\u5bbd30mm\u3001\u9ad820mm\u7684\u957f\u65b9\u4f53\uff0c\u56db\u4e2a\u89d2\u5012\u5706\u89d2R2\"\u3002",
    paramsExtracted: "\u6211\u5df2\u7406\u89e3\u4f60\u7684\u63cf\u8ff0\uff0c\u63d0\u53d6\u5230\u4ee5\u4e0b\u53c2\u6570\uff1a",
    shapeTypeLabel: "\u5f62\u72b6\u7c7b\u578b:",
    dimLength: "\u957f",
    dimWidth: "\u5bbd",
    dimHeight: "\u9ad8",
    dimRadius: "\u534a\u5f84",
    featuresLabel: "\u7279\u5f81:",
    materialLabel: "\u6750\u6599:",
    confidenceLabel: "\u7f6e\u4fe1\u5ea6:",
    confirmGenerate: "\u786e\u8ba4\u751f\u6210",
    editParams: "\u7f16\u8f91\u53c2\u6570",
    modelGenerated: "\u6a21\u578b\u5df2\u751f\u6210\uff01",
    defaultModelName: "\u96f6\u4ef6\u6a21\u578b",
    viewIn3D: "\u57283D\u89c6\u53e3\u67e5\u770b",
    download: "\u4e0b\u8f7d",
    inputPlaceholder: "\u63cf\u8ff0\u4f60\u60f3\u8981\u521b\u5efa\u7684\u96f6\u4ef6...",
    exampleBox: "\u793a\u4f8b: \u957f\u65b9\u4f53",
    exampleCylinder: "\u793a\u4f8b: \u5706\u67f1\u4f53",
    exampleSphere: "\u793a\u4f8b: \u7403\u4f53",
    editModelParamsTitle: "\u7f16\u8f91\u6a21\u578b\u53c2\u6570",
    shapeTypeFormLabel: "\u5f62\u72b6\u7c7b\u578b",
    optionBox: "\u957f\u65b9\u4f53",
    optionCylinder: "\u5706\u67f1\u4f53",
    optionSphere: "\u7403\u4f53",
    optionCone: "\u5706\u9525\u4f53",
    lengthLabel: "\u957f\u5ea6 (mm)",
    widthLabel: "\u5bbd\u5ea6 (mm)",
    heightLabel: "\u9ad8\u5ea6 (mm)",
    radiusLabel: "\u534a\u5f84 (mm)",
    materialFormLabel: "\u6750\u6599",
    materialPlaceholder: "\u53ef\u9009",
    confirmEdit: "\u786e\u8ba4\u4fee\u6539",
    errorUnderstand: "\u62b1\u6b49\uff0c\u6211\u6682\u65f6\u65e0\u6cd5\u7406\u89e3\u4f60\u7684\u63cf\u8ff0\u3002\u8bf7\u5c1d\u8bd5\u66f4\u8be6\u7ec6\u5730\u63cf\u8ff0\u96f6\u4ef6\u7684\u5f62\u72b6\u548c\u5c3a\u5bf8\u3002",
    errorGenerateFailed: "\u6a21\u578b\u751f\u6210\u5931\u8d25\uff0c\u8bf7\u7a0d\u540e\u91cd\u8bd5\u3002",
    shapeBox: "\u957f\u65b9\u4f53",
    shapeCylinder: "\u5706\u67f1\u4f53",
    shapeSphere: "\u7403\u4f53",
    shapeCone: "\u5706\u9525\u4f53",
    featureChamfer: "\u5012\u89d2",
    featureFillet: "\u5706\u89d2",
    featureHole: "\u5b54",
    featureSlot: "\u69fd",
  }"""

idx = content.rstrip().rfind('\n}')
insert_pos = idx + 1
content = content[:insert_pos] + zh_ns + ',\n' + content[insert_pos:]
with open(ZH, 'w', encoding='utf-8') as f:
    f.write(content)
print('zh-CN.ts: nlInputPanel namespace added')

with open(EN, 'r', encoding='utf-8') as f:
    content = f.read()

en_ns = """  // === NLInputPanel.vue ===
  nlInputPanel: {
    welcomeGreeting: "Hello! I am the Lingjing Manufacturing AI Assistant.",
    welcomeHint: "Please describe the part you want to create, e.g.: \\"Create a box 50mm long, 30mm wide, 20mm high, with R2 fillets on all four corners\\".",
    paramsExtracted: "I have understood your description and extracted the following parameters:",
    shapeTypeLabel: "Shape Type:",
    dimLength: "L",
    dimWidth: "W",
    dimHeight: "H",
    dimRadius: "R",
    featuresLabel: "Features:",
    materialLabel: "Material:",
    confidenceLabel: "Confidence:",
    confirmGenerate: "Confirm Generate",
    editParams: "Edit Parameters",
    modelGenerated: "Model generated!",
    defaultModelName: "Part Model",
    viewIn3D: "View in 3D Viewport",
    download: "Download",
    inputPlaceholder: "Describe the part you want to create...",
    exampleBox: "Example: Box",
    exampleCylinder: "Example: Cylinder",
    exampleSphere: "Example: Sphere",
    editModelParamsTitle: "Edit Model Parameters",
    shapeTypeFormLabel: "Shape Type",
    optionBox: "Box",
    optionCylinder: "Cylinder",
    optionSphere: "Sphere",
    optionCone: "Cone",
    lengthLabel: "Length (mm)",
    widthLabel: "Width (mm)",
    heightLabel: "Height (mm)",
    radiusLabel: "Radius (mm)",
    materialFormLabel: "Material",
    materialPlaceholder: "Optional",
    confirmEdit: "Confirm Changes",
    errorUnderstand: "Sorry, I cannot understand your description. Please try to describe the shape and dimensions of the part in more detail.",
    errorGenerateFailed: "Model generation failed, please try again later.",
    shapeBox: "Box",
    shapeCylinder: "Cylinder",
    shapeSphere: "Sphere",
    shapeCone: "Cone",
    featureChamfer: "Chamfer",
    featureFillet: "Fillet",
    featureHole: "Hole",
    featureSlot: "Slot",
  }"""

idx = content.rstrip().rfind('\n}')
insert_pos = idx + 1
content = content[:insert_pos] + en_ns + ',\n' + content[insert_pos:]
with open(EN, 'w', encoding='utf-8') as f:
    f.write(content)
print('en.ts: nlInputPanel namespace added')
