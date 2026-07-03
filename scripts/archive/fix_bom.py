import os

for filename in ['zh-CN.ts', 'en.ts']:
    filepath = os.path.join('src', 'locales', filename)
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    old = '},\n\ufeff,\n  // === ExampleGallery.vue ==='
    new = '},\n  // === ExampleGallery.vue ==='
    
    if old in content:
        content = content.replace(old, new)
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f'{filename}: Fixed BOM line')
    else:
        print(f'{filename}: Pattern not found, checking repr...')
        # Find the BOM line
        lines = content.split('\n')
        for i, line in enumerate(lines):
            if '\ufeff' in line and ',' in line:
                print(f'  Line {i+1}: {repr(line)}')
