---
skill_id: lnn_predict
name: LNN 切削参数预测
version: 1.0.0
applicable_tasks: ["prediction", "optimization", "lnn_inference"]
required_context: ["material", "tool_type", "operation"]
tags: ["lnn", "prediction", "cutting", "manufacturing"]
---

# LNN 切削参数预测技能

## 适用场景
当需要预测最优切削参数时使用此技能，基于液态神经网络（LNN）模型进行高精度参数预测。

## 输入参数
- material: 工件材料（如"45钢"、"铝合金6061"、"钛合金TC4"）
- tool_type: 刀具类型（如"硬质合金铣刀"、"CBN车刀"、"涂层钻头"）
- operation: 加工工序（如"粗加工"、"精加工"、"半精加工"）
- constraints: 可选约束条件（如最大切削力、最小表面粗糙度）
- optimization_goal: 优化目标（"max_efficiency" | "max_quality" | "min_cost"）

## 模型选择策略
| 输入特征数 | 数据规模 | 推荐模型 |
|-----------|---------|---------|
| ≤3 | <1000条 | CFC（Closed-Form Continuous） |
| 3-8 | 1000-10000条 | LTC（Liquid Time-Constant） |
| >8 | >10000条 | HybridLNN |

## 执行步骤
1. 根据输入特征自动选择最优模型（CFC/LTC/HybridLNN）
2. 加载对应的模型权重和配置
3. 执行推理，获取预测结果
4. 进行约束校验（切削力、转速、粗糙度）
5. 计算置信度区间
6. 返回带置信度的推荐参数

## 输出格式
```json
{
  "v": 180.5,
  "f": 0.15,
  "ap": 1.5,
  "ae": 0.8,
  "confidence": 0.92,
  "model_used": "CFC",
  "inference_time_ms": 12.3,
  "constraint_check": {
    "passed": true,
    "warnings": []
  },
  "alternative_params": [
    {"v": 170.0, "f": 0.18, "ap": 1.3, "confidence": 0.88}
  ]
}
```

## 常见错误处理
- 如果 material 不在支持列表中，返回错误并提示可用材料
- 如果约束校验失败，返回警告并给出调整建议
- 如果模型加载超时（>30s），返回缓存预测结果
- 如果输入特征缺失，使用默认值填充并给出提示
