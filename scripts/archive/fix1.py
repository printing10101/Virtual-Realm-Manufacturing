import os
VUE = os.path.join(r'c:\Users\Lenovo\Desktop\灵境制造（上线版）', 'src', 'components', 'nl2cad', 'NLInputPanel.vue')
with open(VUE, 'r', encoding='utf-8') as f:
    content = f.read()
old = '<p>\u8bf7\u63cf\u8ff0\u4f60\u60f3\u8981\u521b\u5efa\u7684\u96f6\u4ef6\uff0c\u4f8b\u5982\uff1a"\u521b\u5efa\u4e00\u4e2a\u957f50mm\u3001\u5bbd30mm\u3001\u9ad820mm\u7684\u957f\u65b9\u4f53\uff0c\u56db\u4e2a\u89d2\u5012\u5706\u89d2R2"\u3002</p>'
new = "<p>{{ t('nlInputPanel.welcomeHint') }}</p>"
if old in content:
    content = content.replace(old, new, 1)
    with open(VUE, 'w', encoding='utf-8') as f:
        f.write(content)
    print('welcomeHint replaced')
else:
    print('still not found, trying with curly quotes')
    old2 = '<p>\u8bf7\u63cf\u8ff0\u4f60\u60f3\u8981\u521b\u5efa\u7684\u96f6\u4ef6\uff0c\u4f8b\u5982\uff1a\u201c\u521b\u5efa\u4e00\u4e2a\u957f50mm\u3001\u5bbd30mm\u3001\u9ad820mm\u7684\u957f\u65b9\u4f53\uff0c\u56db\u4e2a\u89d2\u5012\u5706\u89d2R2\u201d\u3002</p>'
    if old2 in content:
        content = content.replace(old2, new, 1)
        with open(VUE, 'w', encoding='utf-8') as f:
            f.write(content)
        print('welcomeHint replaced (curly quotes)')
    else:
        print('not found with any quote type')
