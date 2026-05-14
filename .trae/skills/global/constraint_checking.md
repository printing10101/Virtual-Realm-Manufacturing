---
skill_id: constraint_checking
name: 工艺参数约束校验
version: 1.0.0
applicable_tasks: ["prediction", "optimization", "analysis"]
required_context: ["material", "tool_type", "parameters"]
tags: ["constraint", "validation", "safety", "manufacturing"]
parameters:
  max_spindle_speed: 60000
  max_feed_rate: 10000
  max_depth_of_cut: 5.0
  max_cutting_force: 2000
  min_surface_roughness: 0.2
---

# 工艺参数约束校验技能

## 适用场景
当需要验证切削参数的工艺可行性时使用此技能，确保生成的参数在设备和工艺安全范围内。

## 输入参数
- material: 工件材料（如"45钢"、"铝合金6061"、"钛合金TC4"）
- tool_type: 刀具类型（如"硬质合金铣刀"、"CBN车刀"、"涂层钻头"）
- parameters: 待校验的切削参数
  - v: 切削速度 (m/min)
  - f: 进给率 (mm/r)
  - ap: 切削深度 (mm)
  - ae: 切削宽度 (mm，可选)
- operation: 加工工序（如"粗加工"、"精加工"、"半精加工"）

## 材料约束表
| 材料 | 最低切削速度 | 最高切削速度 | 推荐进给范围 |
|------|------------|------------|------------|
| 45钢 | 80 | 350 | 0.08-0.35 |
| 铝合金6061 | 200 | 1200 | 0.05-0.50 |
| 钛合金TC4 | 30 | 120 | 0.05-0.20 |
| 不锈钢304 | 50 | 200 | 0.08-0.30 |
| 铸铁HT250 | 60 | 250 | 0.10-0.40 |

## 执行步骤
1. 根据material参数查找材料约束表
2. 校验切削速度 v 是否在材料允许范围内
3. 校验进给率 f 是否在推荐范围内
4. 校验切削深度 ap 是否超过刀具最大允许值
5. 检查切削力估算是否超过安全阈值
6. 校验表面粗糙度预估是否满足精加工要求

## 输出格式
```json
{
  "passed": true,
  "checks": {
    "speed": {"passed": true, "value": 180.5, "range": [80, 350]},
    "feed_rate": {"passed": true, "value": 0.15, "range": [0.08, 0.35]},
    "depth_of_cut": {"passed": true, "value": 1.5, "max": 5.0},
    "cutting_force": {"passed": true, "value": 850, "max": 2000}
  },
  "warnings": [],
  "suggestions": []
}
```

## 常见错误处理
- 如果 material 不在支持列表中，返回错误并列出支持的材料
- 如果约束校验失败，返回具体的超标项和调整建议
- 如果缺少必要参数，返回缺失参数列表
