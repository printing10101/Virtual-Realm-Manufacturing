"""解析 run_3datasets.log 提取 DL-LNN 阶段二最终 PCC 值"""
import re

with open(r'python\experiments\results\run_3datasets.log', 'r', encoding='utf-8', errors='ignore') as f:
    content = f.read()

# 清理 PowerShell 序列化噪声
lines = content.split('\n')
clean_lines = []
for line in lines:
    # 跳过 PowerShell XML 噪声行
    if '<Obj S=' in line or '<S N=' in line or '<Props>' in line:
        continue
    clean_lines.append(line)
clean_content = '\n'.join(clean_lines)

# 找到所有 DL-LNN 训练块
# 搜索 "训练模型: DL-LNN" 或 "数据集:" 附近的内容
pattern = r'数据集:\s*(\w+).*?训练模型:\s*DL-LNN.*?阶段二：物理残差微调.*?(?=训练模型:|数据集:|实验\d|$)'
matches = re.findall(pattern, clean_content, re.DOTALL)

# 更简单的方式：找所有 PCC 值，特别是阶段二最后的
pcc_pattern = r'PCC:\s*([\d.]+)'
all_pcc = re.findall(pcc_pattern, clean_content)
print(f"共找到 {len(all_pcc)} 个 PCC 值")
if all_pcc:
    print(f"前10个: {all_pcc[:10]}")
    print(f"后10个: {all_pcc[-10:]}")
    # 转为 float 找最大值
    pcc_floats = [float(p) for p in all_pcc]
    print(f"最大 PCC: {max(pcc_floats):.4f}")
    print(f"最小 PCC: {min(pcc_floats):.4f}")

# 找 "DL-LNN 评估结果" 附近的内容
eval_pattern = r'DL-LNN\s*评估结果:.*?(?=训练模型:|={3,}|$)'
eval_matches = re.findall(eval_pattern, clean_content, re.DOTALL)
print(f"\n找到 {len(eval_matches)} 个 DL-LNN 评估结果块")
for i, m in enumerate(eval_matches):
    print(f"\n=== 评估块 {i+1} ===")
    print(m[:500])
