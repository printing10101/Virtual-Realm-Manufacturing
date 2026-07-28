"""读取表格[5] 完整内容，规划 v0.4 更新。"""
import docx

DOC_PATH = r'论文相关\论文与实验报告\论文1_DL-LNN颤振预测主论文.docx'
doc = docx.Document(DOC_PATH)

table5 = doc.tables[5]
print(f"表格[5] {len(table5.rows)} 行 × {len(table5.columns)} 列")
print("=" * 100)

for r_idx, row in enumerate(table5.rows):
    print(f"行[{r_idx}]:")
    for c_idx, cell in enumerate(row.cells):
        print(f"  列[{c_idx}]: {cell.text}")

# v0.4 正确数据（来自 all_experiments_results.json）
print("\n" + "=" * 100)
print("v0.4 正确数据（all_experiments_results.json）")
print("=" * 100)
v04_data = {
    "SVR":         {"syn": 2.1332, "ind": 1.3029},
    "Random Forest": {"syn": 1.3528, "ind": 1.0576},
    "XGBoost":     {"syn": 1.2144, "ind": 1.1051},
    "GP":          {"syn": 2.6367, "ind": 2.4488},
    "BPNN":        {"syn": 0.5231, "ind": 1.2225},
    "LSTM":        {"syn": 0.5663, "ind": 0.9496},
    "Transformer": {"syn": 1.1246, "ind": 6.3370},
    "PINN":        {"syn": 0.5076, "ind": 0.9560},
    "DL-LNN（本文）": {"syn": 0.3222, "ind": 0.9289, "pcc": "0.9953 / 0.997"},
}

for name, vals in v04_data.items():
    print(f"  {name}: Synthetic={vals['syn']}, Industrial={vals['ind']}")
