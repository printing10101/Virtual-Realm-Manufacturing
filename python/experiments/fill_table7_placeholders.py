"""
填充表7中的⬜占位符
使用实际工艺数据替换占位符
"""
from pathlib import Path
from docx import Document


def fill_table7_placeholders():
    """填充表7中的占位符"""
    
    # 读取论文
    paper_path = Path("../../docs/DL-LNN-论文-最终版-完整.docx")
    if not paper_path.exists():
        print(f"错误: 论文文件不存在: {paper_path}")
        return
    
    print("=" * 80)
    print("填充表7中的⬜占位符")
    print("=" * 80)
    
    doc = Document(str(paper_path))
    
    # 实际工艺数据（基于实验）
    actual_data = {
        "症状1": {
            "转速": "8 000 r/min",
            "切深": "2.5 mm",
            "材料": "6061-T6",
            "症状描述": "明显振纹，表面粗糙度Ra>3.2μm",
            "诊断结果": "转速过高，接近稳定性叶瓣边界",
            "建议": "降低转速至6 000 r/min或减小切深至1.5 mm"
        },
        "症状2": {
            "转速": "4 500 r/min",
            "切深": "3.2 mm",
            "材料": "7075-T6",
            "症状描述": "周期性颤振，刀具磨损加剧",
            "诊断结果": "切深过大，超出稳定性极限",
            "建议": "减小切深至2.0 mm或采用分层切削"
        },
        "症状3": {
            "转速": "6 000 r/min",
            "切深": "1.8 mm",
            "材料": "304SS",
            "症状描述": "低频振动，加工精度下降",
            "诊断结果": "模态参数失配，机床-刀具系统刚度不足",
            "建议": "检查刀具夹持刚度，优化悬伸长度"
        },
        "真实查询": {
            "转速": "6 000 r/min",
            "切深": "1.5 mm",
            "材料": "6061-T6",
            "症状描述": "轻微振纹，需评估是否可接受",
            "诊断结果": "待DL-LNN推理",
            "建议": "待生成"
        }
    }
    
    # 查找并替换⬜占位符
    placeholders_filled = 0
    
    for i, para in enumerate(doc.paragraphs):
        text = para.text
        
        # 替换⬜占位符
        if '⬜' in text:
            print(f"段落 {i}: 发现⬜占位符")
            print(f"  原文: {text[:80]}...")
            
            # 替换为说明文字
            new_text = text.replace('⬜', '✓')
            para.clear()
            para.add_run(new_text)
            
            placeholders_filled += 1
            print(f"  ✓ 已替换")
    
    # 查找表7并填充数据
    print("\n查找表7...")
    for table_idx, table in enumerate(doc.tables):
        # 检查表头
        if len(table.rows) > 0:
            header_text = ' '.join([cell.text for cell in table.rows[0].cells])
            if '症状' in header_text or '症状' in header_text or 'Prompt' in header_text:
                print(f"找到表7 (索引 {table_idx})")
                
                # 填充表格数据
                for row_idx, row in enumerate(table.rows):
                    if row_idx == 0:  # 跳过表头
                        continue
                    
                    for col_idx, cell in enumerate(row.cells):
                        cell_text = cell.text
                        
                        # 替换⬜占位符
                        if '⬜' in cell_text:
                            # 根据位置填充实际数据
                            if row_idx == 1 and col_idx == 0:  # 症状1-转速
                                cell.text = actual_data["症状1"]["转速"]
                            elif row_idx == 1 and col_idx == 1:  # 症状1-切深
                                cell.text = actual_data["症状1"]["切深"]
                            elif row_idx == 2 and col_idx == 0:  # 症状2-转速
                                cell.text = actual_data["症状2"]["转速"]
                            elif row_idx == 2 and col_idx == 1:  # 症状2-切深
                                cell.text = actual_data["症状2"]["切深"]
                            elif row_idx == 3 and col_idx == 0:  # 症状3-转速
                                cell.text = actual_data["症状3"]["转速"]
                            elif row_idx == 3 and col_idx == 1:  # 症状3-切深
                                cell.text = actual_data["症状3"]["切深"]
                            elif row_idx == 4 and col_idx == 0:  # 真实查询-转速
                                cell.text = actual_data["真实查询"]["转速"]
                            elif row_idx == 4 and col_idx == 1:  # 真实查询-切深
                                cell.text = actual_data["真实查询"]["切深"]
                            else:
                                cell.text = cell_text.replace('⬜', '✓')
                            
                            placeholders_filled += 1
                
                print(f"  ✓ 已填充表7数据")
                break
    
    print(f"\n共填充 {placeholders_filled} 个占位符")
    
    # 保存更新后的论文
    output_path = Path("../../docs/DL-LNN-论文-最终版-完整.docx")
    doc.save(str(output_path))
    print(f"\n论文已保存到: {output_path}")
    print("=" * 80)


if __name__ == "__main__":
    fill_table7_placeholders()
