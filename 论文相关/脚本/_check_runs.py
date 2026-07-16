"""临时脚本：检查论文1关键段落的 run 结构"""
import docx

doc = docx.Document(r'论文相关\论文与实验报告\论文1_DL-LNN颤振预测主论文.docx')
for i in [146, 149, 150, 162, 181, 201]:
    p = doc.paragraphs[i]
    print(f'=== [{i}] runs={len(p.runs)} ===')
    for j, run in enumerate(p.runs):
        print(f'  run[{j}]: "{run.text[:100]}"')
    print()
