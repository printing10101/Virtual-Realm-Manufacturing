import os
BASE = r'c:\Users\Lenovo\Desktop\灵境制造（上线版）'
ZH = os.path.join(BASE, 'src', 'locales', 'zh-CN.ts')
EN = os.path.join(BASE, 'src', 'locales', 'en.ts')

with open(ZH, 'r', encoding='utf-8') as f:
    content = f.read()

zh_ns = """  // === UXDemo.vue UX\u529f\u80fd\u6f14\u793a\u9875\u9762 ===
  uxDemo: {
    pageTitle: "UX \u529f\u80fd\u6f14\u793a",
    btnStartTour: "\u542f\u52a8\u5f15\u5bfc\u6d41\u7a0b",
    btnCommandPalette: "\u547d\u4ee4\u9762\u677f (Ctrl+K)",
    statTourSteps: "\u5f15\u5bfc\u6b65\u9aa4\u6570",
    statExampleCount: "\u793a\u4f8b\u5de5\u7a0b\u6570",
    statCommandCount: "\u6ce8\u518c\u547d\u4ee4\u6570",
    sectionFeatures: "\u5df2\u5b9e\u73b0\u529f\u80fd",
    featureTourLabel: "\u5f15\u5bfc\u6d41\u7a0b",
    featureGalleryLabel: "\u793a\u4f8b\u5de5\u7a0b\u5e93",
    featureCommandLabel: "\u547d\u4ee4\u9762\u677f",
    tagCompleted: "\u5df2\u5b8c\u6210",
    featureTourDesc: "5\u4e2a\u6b65\u9aa4\u3001\u8fdb\u5ea6\u8bb0\u5fc6\u3001\u54cd\u5e94\u5f0f\u8bbe\u8ba1",
    featureGalleryDesc: "12\u4e2a\u793a\u4f8b\u3001\u641c\u7d22\u8fc7\u6ee4\u3001\u4ee3\u7801\u9884\u89c8\u3001\u4e00\u952e\u590d\u5236",
    featureCommandDesc: "\u5feb\u6377\u952e\u5524\u8d77\u3001\u6a21\u7cca\u641c\u7d22\u3001\u667a\u80fd\u6392\u5e8f\u3001\u4f7f\u7528\u9891\u7387\u8bb0\u5fc6",
    sectionGalleryPreview: "\u793a\u4f8b\u5de5\u7a0b\u5e93\u9884\u89c8",
    tourStep1Title: "\u6b22\u8fce\u4f7f\u7528\u7075\u5883\u5236\u9020\u7cfb\u7edf",
    tourStep1Desc: "\u8fd9\u662f\u4e00\u4e2aAI\u9a71\u52a8\u76843D\u5efa\u6a21\u4e0e\u5de5\u827a\u89c4\u5212\u7cfb\u7edf\u3002\u8ba9\u6211\u4eec\u901a\u8fc7\u51e0\u4e2a\u7b80\u5355\u7684\u6b65\u9aa4\u6765\u4e86\u89e3\u4e3b\u8981\u529f\u80fd\u3002",
    tourStep2Title: "\u6587\u4ef6\u7ba1\u7406",
    tourStep2Desc: "\u5728\u8fd9\u91cc\u53ef\u4ee5\u65b0\u5efa\u3001\u6253\u5f00\u3001\u4fdd\u5b58\u5de5\u7a0b\u9879\u76ee\uff0c\u652f\u6301\u5bfc\u5165STEP\u548cDXF\u683c\u5f0f\u6587\u4ef6\u3002",
    tourStep3Title: "\u5bfc\u822a\u83dc\u5355",
    tourStep3Desc: "\u901a\u8fc7\u9876\u90e8\u83dc\u5355\u53ef\u4ee5\u5feb\u901f\u8bbf\u95ee\u5de5\u4f5c\u533a\u3001\u8bbe\u7f6e\u3001\u5de5\u827a\u89c4\u5212\u7b49\u6838\u5fc3\u529f\u80fd\u6a21\u5757\u3002",
    tourStep4Title: "\u547d\u4ee4\u9762\u677f",
    tourStep4Desc: "\u6309 Ctrl+K \u53ef\u4ee5\u5feb\u901f\u5524\u8d77\u547d\u4ee4\u9762\u677f\uff0c\u652f\u6301\u6a21\u7cca\u641c\u7d22\u548c\u667a\u80fd\u6392\u5e8f\uff0c\u63d0\u5347\u64cd\u4f5c\u6548\u7387\u3002",
    tourStep5Title: "\u51c6\u5907\u5f00\u59cb",
    tourStep5Desc: "\u5f15\u5bfc\u5df2\u5b8c\u6210\uff01\u60a8\u53ef\u4ee5\u968f\u65f6\u4ece\u5e2e\u52a9\u83dc\u5355\u91cd\u65b0\u542f\u52a8\u5f15\u5bfc\u6d41\u7a0b\u3002\u73b0\u5728\u8ba9\u6211\u4eec\u5f00\u59cb\u63a2\u7d22\u7cfb\u7edf\u7684\u5f3a\u5927\u529f\u80fd\u5427\uff01",
    cmdNewProjectName: "\u65b0\u5efa\u9879\u76ee",
    cmdNewProjectDesc: "\u521b\u5efa\u4e00\u4e2a\u65b0\u7684\u5de5\u7a0b\u9879\u76ee",
    cmdOpenProjectName: "\u6253\u5f00\u9879\u76ee",
    cmdOpenProjectDesc: "\u6253\u5f00\u5df2\u6709\u7684\u5de5\u7a0b\u9879\u76ee",
    cmdSaveProjectName: "\u4fdd\u5b58\u9879\u76ee",
    cmdSaveProjectDesc: "\u4fdd\u5b58\u5f53\u524d\u5de5\u7a0b\u9879\u76ee",
    cmdExportGCodeName: "\u5bfc\u51faG\u4ee3\u7801",
    cmdExportGCodeDesc: "\u5c06\u5de5\u5177\u8def\u5f84\u5bfc\u51fa\u4e3aG\u4ee3\u7801\u6587\u4ef6",
    cmdStartSimulationName: "\u542f\u52a8\u4eff\u771f",
    cmdStartSimulationDesc: "\u5f00\u59cb\u52a0\u5de5\u8fc7\u7a0b\u4eff\u771f\u6a21\u62df",
    cmdAiFeatureName: "AI\u7279\u5f81\u8bc6\u522b",
    cmdAiFeatureDesc: "\u4f7f\u7528AI\u81ea\u52a8\u8bc6\u522b\u52a0\u5de5\u7279\u5f81",
    cmdViewExamplesName: "\u67e5\u770b\u793a\u4f8b",
    cmdViewExamplesDesc: "\u6d4f\u89c8\u793a\u4f8b\u5de5\u7a0b\u5e93",
    cmdOpenSettingsName: "\u7cfb\u7edf\u8bbe\u7f6e",
    cmdOpenSettingsDesc: "\u6253\u5f00\u7cfb\u7edf\u8bbe\u7f6e\u9875\u9762",
    categoryFile: "\u6587\u4ef6",
    categoryToolpath: "\u5de5\u5177\u8def\u5f84",
    categorySimulation: "\u4eff\u771f",
    categoryAI: "AI",
    categoryHelp: "\u5e2e\u52a9",
    categorySystem: "\u7cfb\u7edf",
    msgNewProjectTriggered: "\u65b0\u5efa\u9879\u76ee\u529f\u80fd\u5df2\u89e6\u53d1",
    msgOpenProjectTriggered: "\u6253\u5f00\u9879\u76ee\u529f\u80fd\u5df2\u89e6\u53d1",
    msgSaveProjectTriggered: "\u4fdd\u5b58\u9879\u76ee\u529f\u80fd\u5df2\u89e6\u53d1",
    msgExportGCodeTriggered: "\u5bfc\u51faG\u4ee3\u7801\u529f\u80fd\u5df2\u89e6\u53d1",
    msgStartSimulationTriggered: "\u542f\u52a8\u4eff\u771f\u529f\u80fd\u5df2\u89e6\u53d1",
    msgAiFeatureTriggered: "AI\u7279\u5f81\u8bc6\u522b\u529f\u80fd\u5df2\u89e6\u53d1",
    msgViewExamplesTriggered: "\u67e5\u770b\u793a\u4f8b\u529f\u80fd\u5df2\u89e6\u53d1",
    msgOpenSettingsTriggered: "\u7cfb\u7edf\u8bbe\u7f6e\u529f\u80fd\u5df2\u89e6\u53d1",
    msgTourCompleted: "\u5f15\u5bfc\u6d41\u7a0b\u5df2\u5b8c\u6210\uff01",
    msgTourSkipped: "\u5f15\u5bfc\u6d41\u7a0b\u5df2\u8df3\u8fc7\uff08\u4ece\u7b2c {step} \u6b65\uff09",
  }"""

idx = content.rstrip().rfind('\n}')
insert_pos = idx + 1
content = content[:insert_pos] + zh_ns + ',\n' + content[insert_pos:]
with open(ZH, 'w', encoding='utf-8') as f:
    f.write(content)
print('zh-CN.ts: uxDemo namespace added')
