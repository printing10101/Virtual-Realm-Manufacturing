import io
path = r'c:\Users\Lenovo\Desktop\灵境制造（上线版）\src\components\HighlightViewer.vue'
with io.open(path, 'r', encoding='utf-8') as f:
    text = f.read()
old = '          清除选择\n        </button>'
new = "          {{ t('highlightViewer.clearSelection') }}\n        </button>"
if old in text:
    text = text.replace(old, new, 1)
    with io.open(path, 'w', encoding='utf-8', newline='\n') as f:
        f.write(text)
    print('OK: replaced clearSelection')
else:
    print('MISS')
