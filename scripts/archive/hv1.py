import os

# === Add highlightViewer namespace to zh-CN.ts ===
zh_path = os.path.join('src', 'locales', 'zh-CN.ts')
with open(zh_path, 'r', encoding='utf-8') as f:
    zh = f.read()

zh_old = 'msgImported: "\u793a\u4f8b {name} \u5df2\u5bfc\u5165\u5230\u9879\u76ee",\n  },\n}'
zh_new = 'msgImported: "\u793a\u4f8b {name} \u5df2\u5bfc\u5165\u5230\u9879\u76ee",\n  },\n  // === HighlightViewer.vue ===\n  highlightViewer: {\n    labelDescription: "\u63cf\u8ff0",\n    labelAiImportance: "AI \u91cd\u8981\u5ea6",\n    labelReason: "\u539f\u56e0",\n    labelCategory: "\u7c7b\u522b",\n    aiFeaturesTitle: "AI \u5173\u6ce8\u7279\u5f81",\n    showTooltip: "\u663e\u793a\u60ac\u505c\u63d0\u793a",\n    showFeatureList: "\u663e\u793a\u7279\u5f81\u5217\u8868",\n    syncEnabled: "\u591a\u7a97\u53e3\u540c\u6b65",\n    clearSelection: "\u6e05\u9664\u9009\u62e9",\n    selected: "\u5df2\u9009\u4e2d",\n    importance: "\u91cd\u8981\u5ea6",\n  },\n}'

if zh_old in zh:
    zh = zh.replace(zh_old, zh_new)
    with open(zh_path, 'w', encoding='utf-8') as f:
        f.write(zh)
    print('zh-CN.ts: highlightViewer namespace added (11 keys)')
else:
    print('zh-CN.ts: Pattern not found!')

# === Add highlightViewer namespace to en.ts ===
en_path = os.path.join('src', 'locales', 'en.ts')
with open(en_path, 'r', encoding='utf-8') as f:
    en = f.read()

en_old = 'msgImported: "Example {name} imported to project",\n  },\n}'
en_new = 'msgImported: "Example {name} imported to project",\n  },\n  // === HighlightViewer.vue ===\n  highlightViewer: {\n    labelDescription: "Description",\n    labelAiImportance: "AI Importance",\n    labelReason: "Reason",\n    labelCategory: "Category",\n    aiFeaturesTitle: "AI Focus Features",\n    showTooltip: "Show Hover Tooltip",\n    showFeatureList: "Show Feature List",\n    syncEnabled: "Multi-Window Sync",\n    clearSelection: "Clear Selection",\n    selected: "Selected",\n    importance: "Importance",\n  },\n}'

if en_old in en:
    en = en.replace(en_old, en_new)
    with open(en_path, 'w', encoding='utf-8') as f:
        f.write(en)
    print('en.ts: highlightViewer namespace added (11 keys)')
else:
    print('en.ts: Pattern not found!')
