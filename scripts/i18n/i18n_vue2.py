# -*- coding: utf-8 -*-
import os
BASE = r'c:\Users\Lenovo\Desktop\灵境制造（上线版）'
VUE = os.path.join(BASE, 'src', 'components', 'nl2cad', 'NLInputPanel.vue')

with open(VUE, 'r', encoding='utf-8') as f:
    content = f.read()

replacements = [
    ('title="\u7f16\u8f91\u6a21\u578b\u53c2\u6570"', ":title=\"t('nlInputPanel.editModelParamsTitle')\""),
    ('label="\u5f62\u72b6\u7c7b\u578b"', ":label=\"t('nlInputPanel.shapeTypeFormLabel')\""),
    ('label="\u957f\u65b9\u4f53"', ":label=\"t('nlInputPanel.optionBox')\""),
    ('label="\u5706\u67f1\u4f53"', ":label=\"t('nlInputPanel.optionCylinder')\""),
    ('label="\u7403\u4f53"', ":label=\"t('nlInputPanel.optionSphere')\""),
    ('label="\u5706\u9525\u4f53"', ":label=\"t('nlInputPanel.optionCone')\""),
    ('label="\u957f\u5ea6 (mm)"', ":label=\"t('nlInputPanel.lengthLabel')\""),
    ('label="\u5bbd\u5ea6 (mm)"', ":label=\"t('nlInputPanel.widthLabel')\""),
    ('label="\u9ad8\u5ea6 (mm)"', ":label=\"t('nlInputPanel.heightLabel')\""),
    ('label="\u534a\u5f84 (mm)"', ":label=\"t('nlInputPanel.radiusLabel')\""),
    ('label="\u6750\u6599"', ":label=\"t('nlInputPanel.materialFormLabel')\""),
    ('placeholder="\u53ef\u9009"', ":placeholder=\"t('nlInputPanel.materialPlaceholder')\""),
]

count = 0
for old, new in replacements:
    if old in content:
        content = content.replace(old, new, 1)
        count += 1
    else:
        print(f"WARNING: not found: {repr(old[:60])}")

# Button texts
old_cancel = '        \u53d6\u6d88\n        '
new_cancel = "        {{ t('common.cancel') }}\n        "
if old_cancel in content:
    content = content.replace(old_cancel, new_cancel, 1)
    count += 1

old_confirm = '        \u786e\u8ba4\u4fee\u6539\n        '
new_confirm = "        {{ t('nlInputPanel.confirmEdit') }}\n        "
if old_confirm in content:
    content = content.replace(old_confirm, new_confirm, 1)
    count += 1

# Add useI18n import
old_import = "import {\n  extractParams as apiExtractParams,\n  generateModel as apiGenerateModel,\n} from '@/api/nl2cad'"
new_import = old_import + "\nimport { useI18n } from 'vue-i18n'"
if old_import in content:
    content = content.replace(old_import, new_import, 1)
    count += 1

# Add const { t } = useI18n()
old_emit = "const emit = defineEmits<{"
new_emit = "const { t } = useI18n()\n\nconst emit = defineEmits<{"
if old_emit in content:
    content = content.replace(old_emit, new_emit, 1)
    count += 1

# Replace getShapeLabel function
old_shape = "function getShapeLabel(type: string): string {\n  const map: Record<string, string> = {\n    box: '\u957f\u65b9\u4f53',\n    cylinder: '\u5706\u67f1\u4f53',\n    sphere: '\u7403\u4f53',\n    cone: '\u5706\u9525\u4f53',\n  }\n  return map[type] || type\n}"
new_shape = "function getShapeLabel(type: string): string {\n  const map: Record<string, string> = {\n    box: t('nlInputPanel.shapeBox'),\n    cylinder: t('nlInputPanel.shapeCylinder'),\n    sphere: t('nlInputPanel.shapeSphere'),\n    cone: t('nlInputPanel.shapeCone'),\n  }\n  return map[type] || type\n}"
if old_shape in content:
    content = content.replace(old_shape, new_shape, 1)
    count += 1

# Replace getFeatureLabel function
old_feat = "function getFeatureLabel(type: string): string {\n  const map: Record<string, string> = {\n    chamfer: '\u5012\u89d2',\n    fillet: '\u5706\u89d2',\n    hole: '\u5b54',\n    slot: '\u69fd',\n  }\n  return map[type] || type\n}"
new_feat = "function getFeatureLabel(type: string): string {\n  const map: Record<string, string> = {\n    chamfer: t('nlInputPanel.featureChamfer'),\n    fillet: t('nlInputPanel.featureFillet'),\n    hole: t('nlInputPanel.featureHole'),\n    slot: t('nlInputPanel.featureSlot'),\n  }\n  return map[type] || type\n}"
if old_feat in content:
    content = content.replace(old_feat, new_feat, 1)
    count += 1

# Replace error messages
old_err1 = "content: '\u62b1\u6b49\uff0c\u6211\u6682\u65f6\u65e0\u6cd5\u7406\u89e3\u4f60\u7684\u63cf\u8ff0\u3002\u8bf7\u5c1d\u8bd5\u66f4\u8be6\u7ec6\u5730\u63cf\u8ff0\u96f6\u4ef6\u7684\u5f62\u72b6\u548c\u5c3a\u5bf8\u3002',"
new_err1 = "content: t('nlInputPanel.errorUnderstand'),"
if old_err1 in content:
    content = content.replace(old_err1, new_err1, 1)
    count += 1

old_model = "modelName: '\u96f6\u4ef6\u6a21\u578b',"
new_model = "modelName: t('nlInputPanel.defaultModelName'),"
if old_model in content:
    content = content.replace(old_model, new_model, 1)
    count += 1

old_err2 = "content: '\u6a21\u578b\u751f\u6210\u5931\u8d25\uff0c\u8bf7\u7a0d\u540e\u91cd\u8bd5\u3002',"
new_err2 = "content: t('nlInputPanel.errorGenerateFailed'),"
if old_err2 in content:
    content = content.replace(old_err2, new_err2, 1)
    count += 1

with open(VUE, 'w', encoding='utf-8') as f:
    f.write(content)
print(f'Part 2: {count} replacements done')
