---
skill_id: rul_prediction
name: 剩余使用寿命预测
version: 1.0.0
applicable_tasks: ["prediction", "analysis", "rul_prediction"]
required_context: ["degradation_data", "equipment_type"]
tags: ["rul", "prognostics", "maintenance", "lstm", "survival"]
---

# 剩余使用寿命预测技能（代理专长）

## 适用场景
当需要基于设备退化数据预测剩余使用寿命(RUL)，制定预测性维护策略时，具有此专长的代理使用本技能。

## 输入参数
- degradation_data: 退化时间序列数据
  - timestamps: 时间戳列表
  - sensor_readings: 多传感器读数矩阵（时间×传感器）
  - failure_threshold: 失效阈值
- equipment_type: 设备类型（"spindle" | "bearing" | "tool" | "pump" | "motor"）
- current_cycle: 当前运行周期数
- maintenance_history: 历史维修记录（可选）

## 寿命预测模型选择
| 数据特征 | 推荐模型 | 适用条件 |
|---------|---------|---------|
| 单调退化趋势 | 指数退化模型 | 数据量较小 |
| 多传感器融合 | LSTM/GRU | 大量历史数据 |
| 不确定性强 | 粒子滤波 | 物理模型可用 |
| 多工况 | Transformer | 复杂退化模式 |
| 截断数据 | Cox比例风险 | 有删失数据 |

## 执行步骤
1. 对退化数据进行平滑处理和异常值检测
2. 提取退化特征指标（趋势、变点、加速因子）
3. 根据数据特征自动选择最优RUL预测模型
4. 训练/加载模型并进行预测
5. 计算预测不确定性（置信区间、概率密度）
6. 结合维修成本和停机损失，生成最优维护窗口

## 输出格式
```json
{
  "equipment_type": "spindle",
  "current_health_index": 0.72,
  "rul_prediction": {
    "mean_cycles": 342.5,
    "lower_bound": 280.0,
    "upper_bound": 410.0,
    "confidence_level": 0.9
  },
  "degradation_rate": 0.00082,
  "critical_sensors": [
    {"name": "vibration_rms", "contribution": 0.42},
    {"name": "temperature", "contribution": 0.31},
    {"name": "current_draw", "contribution": 0.27}
  ],
  "maintenance_window": {
    "optimal_cycle": 310,
    "urgent_threshold_cycle": 280,
    "estimated_downtime_hours": 4.5,
    "estimated_cost": 2800.0
  }
}
```

## 常见错误处理
- 如果退化数据不足（<50个时间点），提示数据不足并降低置信度
- 如果退化模式发生突变（变点检测），分段预测并标记警告
- 如果传感器数量不足，使用简化模型并列出缺失的理想传感器
- 如果置信区间过宽（>50%均值），建议增加监测频率
