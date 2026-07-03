import os

filepath = os.path.join('src', 'examples', 'ExampleGallery.vue')
with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

original = content
changes = []

# === Template part 2 ===

# 1. btnCopyCode - replace all occurrences
old = '\u590d\u5236\u4ee3\u7801'
new = "{{ t('exampleGallery.btnCopyCode') }}"
n = content.count(old)
content = content.replace(old, new)
if n: changes.append(f'btnCopyCode: {n}')

# 2. btnCopy - 14-space indent button text
old = '\n              \u590d\u5236\n            </el-button>'
new = "\n              {{ t('exampleGallery.btnCopy') }}\n            </el-button>"
n = content.count(old)
content = content.replace(old, new)
if n: changes.append(f'btnCopy: {n}')

# 3. btnPreview - 14-space indent button text
old = '\n              \u9884\u89c8\n            </el-button>'
new = "\n              {{ t('exampleGallery.btnPreview') }}\n            </el-button>"
n = content.count(old)
content = content.replace(old, new)
if n: changes.append(f'btnPreview: {n}')

# 4. btnClose - 10-space indent button text
old = '\n          \u5173\u95ed\n        </el-button>'
new = "\n          {{ t('exampleGallery.btnClose') }}\n        </el-button>"
n = content.count(old)
content = content.replace(old, new)
if n: changes.append(f'btnClose: {n}')

# 5. btnImport
old = '\n          \u5bfc\u5165\u5230\u9879\u76ee\n        </el-button>'
new = "\n          {{ t('exampleGallery.btnImport') }}\n        </el-button>"
n = content.count(old)
content = content.replace(old, new)
if n: changes.append(f'btnImport: {n}')

# 6. downloadCount with interpolation
old = '{{ selectedExample.downloadCount }} \u6b21\u4e0b\u8f7d'
new = "{{ t('exampleGallery.downloadCount', { count: selectedExample.downloadCount }) }}"
n = content.count(old)
content = content.replace(old, new)
if n: changes.append(f'downloadCount: {n}')

# 7. updatedAt with interpolation
old = '\u66f4\u65b0\u4e8e {{ formatDate(selectedExample.updatedAt) }}'
new = "{{ t('exampleGallery.updatedAt', { date: formatDate(selectedExample.updatedAt) }) }}"
n = content.count(old)
content = content.replace(old, new)
if n: changes.append(f'updatedAt: {n}')

# 8. useCasesTitle
old = '<h4>\u5e94\u7528\u573a\u666f</h4>'
new = "<h4>{{ t('exampleGallery.useCasesTitle') }}</h4>"
n = content.count(old)
content = content.replace(old, new)
if n: changes.append(f'useCasesTitle: {n}')

# === Script part ===

# 9. useI18n import
old = "import { ref, computed } from 'vue'"
new = "import { ref, computed } from 'vue'\nimport { useI18n } from 'vue-i18n'"
n = content.count(old)
content = content.replace(old, new)
if n: changes.append(f'useI18n import: {n}')

# 10. const { t } = useI18n()
old = "import { exampleProjects, getCategories, getDifficulties } from './data'\n\n// \u72b6\u6001"
new = "import { exampleProjects, getCategories, getDifficulties } from './data'\n\nconst { t } = useI18n()\n\n// \u72b6\u6001"
n = content.count(old)
content = content.replace(old, new)
if n: changes.append(f'const t: {n}')

# 11. getDifficultyLabel
old = "  const labelMap = {\n    beginner: '\u5165\u95e8',\n    intermediate: '\u4e2d\u7ea7',\n    advanced: '\u9ad8\u7ea7'\n  }"
new = "  const labelMap = {\n    beginner: t('exampleGallery.difficultyBeginner'),\n    intermediate: t('exampleGallery.difficultyIntermediate'),\n    advanced: t('exampleGallery.difficultyAdvanced')\n  }"
n = content.count(old)
content = content.replace(old, new)
if n: changes.append(f'difficultyLabel: {n}')

# 12. getCategoryLabel
old = "  const categoryMap = {\n    basic: '\u57fa\u7840\u793a\u4f8b',\n    modeling: '3D\u5efa\u6a21',\n    toolpath: '\u5de5\u5177\u8def\u5f84',\n    simulation: '\u4eff\u771f\u6a21\u62df',\n    ai: 'AI\u529f\u80fd',\n    advanced: '\u9ad8\u7ea7\u5e94\u7528'\n  }"
new = "  const categoryMap = {\n    basic: t('exampleGallery.categoryBasic'),\n    modeling: t('exampleGallery.categoryModeling'),\n    toolpath: t('exampleGallery.categoryToolpath'),\n    simulation: t('exampleGallery.categorySimulation'),\n    ai: t('exampleGallery.categoryAi'),\n    advanced: t('exampleGallery.categoryAdvanced')\n  }"
n = content.count(old)
content = content.replace(old, new)
if n: changes.append(f'categoryLabel: {n}')

# 13. msgCopied
old = "ElMessage.success('\u4ee3\u7801\u5df2\u590d\u5236\u5230\u526a\u8d34\u677f')"
new = "ElMessage.success(t('exampleGallery.msgCopied'))"
n = content.count(old)
content = content.replace(old, new)
if n: changes.append(f'msgCopied: {n}')

# 14. msgCopyFailed
old = "ElMessage.error('\u590d\u5236\u5931\u8d25\uff0c\u8bf7\u624b\u52a8\u590d\u5236')"
new = "ElMessage.error(t('exampleGallery.msgCopyFailed'))"
n = content.count(old)
content = content.replace(old, new)
if n: changes.append(f'msgCopyFailed: {n}')

# 15. msgImported
old = "ElMessage.success(`\u793a\u4f8b \"${example.name}\" \u5df2\u5bfc\u5165\u5230\u9879\u76ee`)"
new = "ElMessage.success(t('exampleGallery.msgImported', { name: example.name }))"
n = content.count(old)
content = content.replace(old, new)
if n: changes.append(f'msgImported: {n}')

if content != original:
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    print('Replacements done:')
    for c in changes:
        print(f'  - {c}')
    print(f'Total groups: {len(changes)}')
else:
    print('No changes made')
