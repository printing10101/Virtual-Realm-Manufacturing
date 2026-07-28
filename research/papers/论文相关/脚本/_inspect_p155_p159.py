"""检查 [155] 和 [159] 段落的内容和 runs 结构。"""
import docx

DOC_PATH = r'论文相关\论文与实验报告\论文1_DL-LNN颤振预测主论文.docx'
doc = docx.Document(DOC_PATH)

for idx in [153, 154, 155, 156, 157, 158, 159, 160]:
    p = doc.paragraphs[idx]
    text = p.text
    print(f"\n[{idx}] style={p.style.name}, runs={len(p.runs)}")
    print(f"  text: {text[:200]}")
    if ' - ' in text:
        parts = text.split(' - ')
        print(f"  含 ' - ' 分隔，共 {len(parts)} 部分")
        for i, part in enumerate(parts):
            print(f"    [{i}]: {part[:80]}")
