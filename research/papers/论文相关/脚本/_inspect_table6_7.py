"""检查表格[6] LOMO 和 表格[7] LOCO 的结构。"""
import docx

DOC_PATH = r'论文相关\论文与实验报告\论文1_DL-LNN颤振预测主论文.docx'
doc = docx.Document(DOC_PATH)

for t_idx in [6, 7]:
    t = doc.tables[t_idx]
    print(f'\n表格[{t_idx}]: {len(t.rows)} 行 × {len(t.columns)} 列')
    print('=' * 90)
    for r_idx, row in enumerate(t.rows):
        cells = [cell.text.strip() for cell in row.cells]
        print(f'行[{r_idx}]: {cells}')
