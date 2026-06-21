# XM-100 知识图谱加工经验导入报告

- **机床**: XM-100 (Xmaker, Fanuc 0i 兼容)
- **生成时间**: 2026-06-21 03:39:22

## 1. 导入的加工记录

| 记录ID | 刀具 | 材料 | 首次合格 | Process更新 | 关系更新 |
|--------|------|------|----------|-------------|----------|
| XM100-REC-001 | tool-endmill_wc_d10 | material-45steel | 是 | 2 | 1 |
| XM100-REC-002 | tool-endmill_wc_taper_d6 | material-aluminum_6061 | 是 | 1 | 1 |
| XM100-REC-003 | tool-endmill_wc_d10 | material-stainless_304 | 否 | 1 | 1 |
| XM100-REC-004 | tool-endmill_wc_micro_d1 | material-abs | 是 | 1 | 1 |
| XM100-REC-005 | tool-facemill_wc_d50 | material-45steel | 是 | 1 | 1 |
| XM100-REC-006 | tool-endmill_wc_taper_d6 | material-brass | 是 | 1 | 1 |
| XM100-REC-007 | tool-endmill_wc_d10 | material-45steel | 是 | 1 | 1 |
| XM100-REC-008 | tool-vbit_wc_60deg | material-wood_walnut | 是 | 1 | 1 |

## 2. 知识图谱规模

- **节点总数**: 27
- **关系总数**: 15
- **节点类型分布**: {'process': 8, 'tool': 5, 'material': 6, 'feature': 8}
- **关系类型分布**: {'APPLIED_TO': 8, 'SUITABLE_FOR': 7}

## 3. 工艺知识问答

**Q: 45钢可以用哪些刀具加工？**

A: 知识图谱中有 2 把刀具适配 45钢：tool-endmill_wc_d10, tool-facemill_wc_d50（可信度分别为 0.75, 0.55）

**Q: φ10立铣刀(tool-endmill_wc_d10)能加工哪些材料？**

A: 知识图谱中该刀具适配 2 种材料：material-45steel, material-stainless_304（可信度分别为 0.75, 0.40）

**Q: XM-100 有哪些锥度球头刀适合五轴加工？**

A: 知识图谱中有 1 把锥度球头刀：tool-endmill_wc_taper_d6，均标记 suitable_for_5axis=true，适合 RTCP/TWP 五轴加工

**Q: 当前知识图谱的规模如何？**

A: 节点 27 个，关系 15 条。节点类型分布: {'process': 8, 'tool': 5, 'material': 6, 'feature': 8}，关系类型分布: {'APPLIED_TO': 8, 'SUITABLE_FOR': 7}

**Q: 哪些工艺已有 XM-100 实测数据？**

A: 有 8 个工艺节点已有实测数据：process-5axis-curve-aluminum(n=1, 合格率=100%); process-5axis-impeller-brass(n=1, 合格率=100%); process-engraving-abs(n=1, 合格率=100%); process-facemill-steel(n=1, 合格率=100%); process-shoulder-mill-steel-finish(n=1, 合格率=100%); process-shoulder-mill-steel-rough(n=2, 合格率=100%); process-slot-mill-304(n=1, 合格率=0%); process-vcarve-wood(n=1, 合格率=100%)

## 4. 说明

- 加工记录为基于 XM-100 能力的模拟数据
- FeedbackUpdater 根据 first_pass_acceptance 调整关系可信度
- 可信度公式: confidence = 0.5 × success_rate + 0.2
- Process 节点累计 sample_count、success_count、avg_surface_roughness
