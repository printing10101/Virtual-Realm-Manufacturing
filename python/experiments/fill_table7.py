"""
填充论文表7（SLD-as-Prompt模板）中的占位符数据
基于论文中的实验数据和工艺参数
"""
from docx import Document
from pathlib import Path

paper_path = Path("../../docs/DL-LNN-论文-最终版.docx")
if not paper_path.exists():
    paper_path = Path("../../docs/DL-LNN-论文-更新版.docx")

doc = Document(str(paper_path))

print("=" * 80)
print("填充表7 SLD-as-Prompt 模板")
print("=" * 80)

# 表7是第7个表格（索引6）
table7 = doc.tables[6]

print(f"\n原始表格行数: {len(table7.rows)}")
print(f"原始表格列数: {len(table7.columns)}")

# 打印原始内容
print("\n--- 原始内容 ---")
for i, row in enumerate(table7.rows):
    for j, cell in enumerate(row.cells):
        text = cell.text.strip()
        if text and '⬜' in text:
            print(f"  行{i} 列{j}: {text}")

# 定义填充数据（基于论文实验数据）
# 演示样例1：转速过高场景（45#钢，不同工况）
# 演示样例2：切深过大场景（基于6061-T6数据）
# 演示样例3：模态参数失配场景
# 真实查询：基于论文4.4.1节的实际实验数据

updates = {
    # 行1: 演示样例1（转速过高）— User
    (1, 1): "在 n = 8 000 r/min、ap = 1.0 mm 加工 45# 钢出现明显振纹，调低主轴后振纹消失。",
    
    # 行2: 演示样例1（转速过高）— Assistant
    (2, 1): "根据 SLD 推断，n = 8 000 r/min 处于第 2 叶瓣峰值附近；建议将主轴调整至 5 500 r/min（第 2 叶瓣谷值），可避开不稳定区。",
    
    # 行3: 演示样例2（切深过大）— User
    (3, 1): "n = 6 000 r/min 时逐步加大 ap 到 1.8 mm 出现振纹，减小 ap 后消失。",
    
    # 行4: 演示样例2（切深过大）— Assistant
    (4, 1): "SLD 预测当前转速下 a_lim = 1.42 mm，1.8 mm 切深已超过安全区；建议将 ap 控制在 1.2 mm 以内。",
    
    # 行5: 演示样例3（模态参数失配）— User (不变，无占位符)
    
    # 行6: 演示样例3（模态参数失配）— Assistant
    (6, 1): "缺少模态参数时模型退化为粗略 SLD；建议临时使用 4 000 r/min 以下的小切深（< 0.5 mm）试切，并尽快通过锤击法[55]测定 k、m、ζ 后重新校核 SLD。",
    
    # 行7: 真实查询 — User (不变，已有数据)
    
    # 行8: 真实查询 — Assistant（基于论文4.4.1节的实验结果）
    (8, 1): "根据 DL-LNN 分析，n = 6 000 r/min 处于第 2 叶瓣峰值附近，预测极限切深 a_lim ≈ 1.42 mm，当前 ap = 1.5 mm 已超过稳定极限。建议：(1) 将切深降至 1.2 mm 以下（留 15% 安全裕量）；(2) 或调整转速至 5 500 r/min（第 2 叶瓣谷值），该处稳定切深极限更高。",
}

# 应用更新
print("\n--- 应用更新 ---")
for (row_idx, col_idx), new_text in updates.items():
    old_text = table7.rows[row_idx].cells[col_idx].text
    table7.rows[row_idx].cells[col_idx].text = new_text
    print(f"  行{row_idx} 列{col_idx}: 已更新")

# 验证更新结果
print("\n--- 更新后内容 ---")
for i, row in enumerate(table7.rows):
    print(f"\n行 {i}:")
    for j, cell in enumerate(row.cells):
        text = cell.text.strip()
        if text:
            # 检查是否还有占位符
            has_placeholder = '⬜' in text
            marker = " [仍有占位符!]" if has_placeholder else ""
            print(f"  列{j}: {text[:120]}{marker}")

# 保存
output_path = Path("../../docs/DL-LNN-论文-最终版.docx")
doc.save(str(output_path))

print("\n" + "=" * 80)
print(f"表7已更新并保存到: {output_path}")
print("=" * 80)
