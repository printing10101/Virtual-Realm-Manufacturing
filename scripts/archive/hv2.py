import io

path = r'c:\Users\Lenovo\Desktop\灵境制造（上线版）\src\components\HighlightViewer.vue'

with io.open(path, 'r', encoding='utf-8') as f:
    text = f.read()

replacements = [
    ('<span class="label">描述:</span>',
     "<span class=\"label\">{{ t('highlightViewer.labelDescription') }}:</span>"),
    ('<span class="label">AI 重要度:</span>',
     "<span class=\"label\">{{ t('highlightViewer.labelAiImportance') }}:</span>"),
    ('<span class="label">原因:</span>',
     "<span class=\"label\">{{ t('highlightViewer.labelReason') }}:</span>"),
    ('<span class="label">类别:</span>',
     "<span class=\"label\">{{ t('highlightViewer.labelCategory') }}:</span>"),
    ('<h4>AI 关注特征</h4>',
     "<h4>{{ t('highlightViewer.aiFeaturesTitle') }}</h4>"),
    ('          >\n          显示悬停提示\n        </label>',
     "          >\n          {{ t('highlightViewer.showTooltip') }}\n        </label>"),
    ('          >\n          显示特征列表\n        </label>',
     "          >\n          {{ t('highlightViewer.showFeatureList') }}\n        </label>"),
    ('          >\n          多窗口同步\n        </label>',
     "          >\n          {{ t('highlightViewer.syncEnabled') }}\n        </label>"),
    ('>清除选择</button>',
     ">{{ t('highlightViewer.clearSelection') }}</button>"),
    ('        已选中: {{ selectedFeature.name }}\n',
     "        {{ t('highlightViewer.selected') }}: {{ selectedFeature.name }}\n"),
    ('<span>重要度: {{ (selectedFeature.aiInfo.importance * 100).toFixed(0) }}%</span>',
     "<span>{{ t('highlightViewer.importance') }}: {{ (selectedFeature.aiInfo.importance * 100).toFixed(0) }}%</span>"),
    ("import { useFeatureHighlight, type FeatureInfo } from '@/composables/useFeatureHighlight'\n",
     "import { useFeatureHighlight, type FeatureInfo } from '@/composables/useFeatureHighlight'\nimport { useI18n } from 'vue-i18n'\n"),
    ('const canvasContainerRef = ref<HTMLElement>()\n',
     "const canvasContainerRef = ref<HTMLElement>()\nconst { t } = useI18n()\n"),
]

count = 0
for old, new in replacements:
    if old in text:
        text = text.replace(old, new, 1)
        count += 1
        print(f'OK [{count}]: replaced')
    else:
        print(f'MISS: {old[:60]!r}')

with io.open(path, 'w', encoding='utf-8', newline='\n') as f:
    f.write(text)

print(f'\nTotal replacements: {count}/{len(replacements)}')
