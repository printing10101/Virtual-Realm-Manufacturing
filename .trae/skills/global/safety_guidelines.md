---
skill_id: safety_guidelines
name: 安全操作指南
version: 1.0.0
applicable_tasks: ["*"]
required_context: []
tags: ["safety", "guidelines", "operation", "compliance"]
---

# 安全操作指南

## 适用场景
在所有制造任务执行过程中应用，确保操作符合安全规范。

## 安全等级定义
| 等级 | 描述 | 适用场景 |
|------|------|---------|
| S0 | 完全安全 | 纯数据分析、历史查询 |
| S1 | 低风险 | 参数预测、离线推理 |
| S2 | 中等风险 | 在线优化、实时控制 |
| S3 | 高风险 | 自动加工、刀具更换 |
| S4 | 禁止 | 可能造成人身伤害的操作 |

## 执行步骤
1. 评估当前任务的安全等级
2. 根据安全等级决定是否需要人工确认
3. 检查设备状态和防护装置
4. 确认紧急停机机制可用
5. 执行任务并持续监控

## 安全规则清单
- S1及以上操作需记录操作日志
- S2及以上操作需获得人工确认
- S3操作需双人确认
- S4操作严格禁止，不得通过API执行
- 所有操作必须保留审计追踪
- 异常检测触发自动停机

## 输出格式
```json
{
  "safety_level": "S1",
  "requires_approval": false,
  "restrictions": [],
  "mandatory_checks": ["log_operation", "monitor_status"],
  "emergency_stop_enabled": true
}
```

## 常见错误处理
- 如果安全等级无法判定，默认采用S3保守策略
- 如果紧急停机不可用，自动拒绝S2以上操作
- 如果人工确认超时（>300s），自动终止任务
