"""验证表格[8] 的 4.6% 是否为假阳性。"""
import docx

DOC_PATH = r'论文相关\论文与实验报告\论文1_DL-LNN颤振预测主论文.docx'
doc = docx.Document(DOC_PATH)

t = doc.tables[8]
print(f'表格[8]: {len(t.rows)} 行 × {len(t.columns)} 列')
print('=' * 80)
for r_idx, row in enumerate(t.rows):
    cells = [cell.text.strip() for cell in row.cells]
    print(f'行[{r_idx}]: {cells}')
