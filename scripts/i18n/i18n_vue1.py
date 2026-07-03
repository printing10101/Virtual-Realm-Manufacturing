# -*- coding: utf-8 -*-
import os
BASE = r'c:\Users\Lenovo\Desktop\灵境制造（上线版）'
VUE = os.path.join(BASE, 'src', 'components', 'nl2cad', 'NLInputPanel.vue')

with open(VUE, 'r', encoding='utf-8') as f:
    content = f.read()

replacements = [
    ('<p>\u4f60\u597d\uff01\u6211\u662f\u7075\u5883\u5236\u9020AI\u52a9\u624b\u3002</p>', "<p>{{ t('nlInputPanel.welcomeGreeting') }}</p>"),
    ('<p>\u8bf7\u63cf\u8ff0\u4f60\u60f3\u8981\u521b\u5efa\u7684\u96f6\u4ef6\uff0c\u4f8b\u5982\uff1a\u201c\u521b\u5efa\u4e00\u4e2a\u957f50mm\u3001\u5bbd30mm\u3001\u9ad820mm\u7684\u957f\u65b9\u4f53\uff0c\u56db\u4e2a\u89d2\u5012\u5706\u89d2R2\u201d\u3002</p>', "<p>{{ t('nlInputPanel.welcomeHint') }}</p>"),
    ('<p>\u6211\u5df2\u7406\u89e3\u4f60\u7684\u63cf\u8ff0\uff0c\u63d0\u53d6\u5230\u4ee5\u4e0b\u53c2\u6570\uff1a</p>', "<p>{{ t('nlInputPanel.paramsExtracted') }}</p>"),
    ('<span class="param-label">\u5f62\u72b6\u7c7b\u578b:</span>', '<span class="param-label">{{ t(\'nlInputPanel.shapeTypeLabel\') }}</span>'),
    ('\u957f {{ msg.params.dimensions.length }}mm', "{{ t('nlInputPanel.dimLength') }} {{ msg.params.dimensions.length }}mm"),
    ('\u00d7 \u5bbd {{ msg.params.dimensions.width }}mm', "\u00d7 {{ t('nlInputPanel.dimWidth') }} {{ msg.params.dimensions.width }}mm"),
    ('\u00d7 \u9ad8 {{ msg.params.dimensions.height }}mm', "\u00d7 {{ t('nlInputPanel.dimHeight') }} {{ msg.params.dimensions.height }}mm"),
    ('\u534a\u5f84 {{ msg.params.dimensions.radius }}mm', "{{ t('nlInputPanel.dimRadius') }} {{ msg.params.dimensions.radius }}mm"),
    ('<span class="param-label">\u7279\u5f81:</span>', '<span class="param-label">{{ t(\'nlInputPanel.featuresLabel\') }}</span>'),
    ('<span class="param-label">\u6750\u6599:</span>', '<span class="param-label">{{ t(\'nlInputPanel.materialLabel\') }}</span>'),
    ('<span class="param-label">\u7f6e\u4fe1\u5ea6:</span>', '<span class="param-label">{{ t(\'nlInputPanel.confidenceLabel\') }}</span>'),
    ('<el-icon><Check /></el-icon>\u786e\u8ba4\u751f\u6210', "<el-icon><Check /></el-icon>{{ t('nlInputPanel.confirmGenerate') }}"),
    ('<el-icon><Edit /></el-icon>\u7f16\u8f91\u53c2\u6570', "<el-icon><Edit /></el-icon>{{ t('nlInputPanel.editParams') }}"),
    ('<p>\u6a21\u578b\u5df2\u751f\u6210\uff01</p>', "<p>{{ t('nlInputPanel.modelGenerated') }}</p>"),
    ("{{ msg.modelName || '\u96f6\u4ef6\u6a21\u578b' }}", "{{ msg.modelName || t('nlInputPanel.defaultModelName') }}"),
    ('<el-icon><View /></el-icon>\u57283D\u89c6\u53e3\u67e5\u770b', "<el-icon><View /></el-icon>{{ t('nlInputPanel.viewIn3D') }}"),
    ('<el-icon><Download /></el-icon>\u4e0b\u8f7d', "<el-icon><Download /></el-icon>{{ t('nlInputPanel.download') }}"),
    ('placeholder="\u63cf\u8ff0\u4f60\u60f3\u8981\u521b\u5efa\u7684\u96f6\u4ef6..."', ":placeholder=\"t('nlInputPanel.inputPlaceholder')\""),
    ('\u793a\u4f8b: \u957f\u65b9\u4f53', "{{ t('nlInputPanel.exampleBox') }}"),
    ('\u793a\u4f8b: \u5706\u67f1\u4f53', "{{ t('nlInputPanel.exampleCylinder') }}"),
    ('\u793a\u4f8b: \u7403\u4f53', "{{ t('nlInputPanel.exampleSphere') }}"),
]

count = 0
for old, new in replacements:
    if old in content:
        content = content.replace(old, new, 1)
        count += 1
    else:
        print(f"WARNING: not found: {repr(old[:60])}")

with open(VUE, 'w', encoding='utf-8') as f:
    f.write(content)
print(f'Part 1: {count} replacements done')
