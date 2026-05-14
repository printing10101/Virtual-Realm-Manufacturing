---
skill_id: error_handling
name: 错误处理与恢复
version: 1.0.0
applicable_tasks: ["*"]
required_context: ["error", "retry_count"]
tags: ["error", "recovery", "retry", "circuit_breaker"]
---

# 错误处理与恢复技能

## 适用场景
当任务执行过程中出现错误时，使用此技能进行标准化错误处理和自动恢复。

## 输入参数
- error: 错误对象或错误信息
- retry_count: 当前重试次数
- max_retries: 最大重试次数（默认3）
- task_context: 任务上下文信息

## 执行步骤
1. 识别错误类型（可恢复/不可恢复）
2. 对于可恢复错误，根据错误类别选择恢复策略
3. 执行熔断检查，避免级联故障
4. 记录错误日志并生成恢复建议
5. 如果需要重试，计算退避延迟并调度重试

## 错误分类与策略
| 错误类型 | 恢复策略 | 退避延迟 |
|---------|---------|---------|
| 参数校验失败 | 不重试，返回错误 | N/A |
| 模型加载失败 | 重试3次 | 600s / 1800s / 3600s |
| 推理超时 | 降级到简化模型 | N/A |
| 数据不可用 | 重试5次 | 300s 指数退避 |
| 连接中断 | 重试3次 | 120s 固定间隔 |

## 输出格式
```json
{
  "recoverable": true,
  "strategy": "retry",
  "retry_delay_seconds": 600,
  "suggestion": "模型加载临时失败，建议600秒后重试",
  "fallback_action": "use_cached_model"
}
```

## 常见错误处理
- 如果错误持续发生超过阈值，触发人工介入通知
- 如果熔断器打开，暂停该类型任务30分钟
