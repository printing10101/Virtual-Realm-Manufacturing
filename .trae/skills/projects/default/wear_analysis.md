---
skill_id: wear_analysis
name: 刀具磨损分析
version: 1.0.0
applicable_tasks: ["analysis", "prediction", "optimization"]
required_context: ["tool_type", "sensor_data"]
tags: ["wear", "analysis", "tool", "maintenance", "sensor"]
---

# 刀具磨损分析技能

## 适用场景
当需要通过传感器数据评估刀具磨损状态、预测剩余寿命或制定换刀策略时使用此技能。

## 输入参数
- tool_type: 刀具类型（如"硬质合金铣刀"、"CBN车刀"）
- sensor_data: 传感器数据（振动、力、温度、声发射）
  - vibration: 振动信号（加速度，m/s²）
  - cutting_force: 切削力信号（N）
  - temperature: 切削温度信号（°C）
  - acoustic_emission: 声发射信号（dB）
- tool_age: 刀具已使用时长（分钟）
- material: 加工材料

## 磨损评估标准
| 磨损等级 | VB值范围 | 状态 | 建议措施 |
|---------|---------|------|---------|
| 1级 | 0-0.1mm | 正常 | 继续使用 |
| 2级 | 0.1-0.2mm | 轻微磨损 | 监控使用 |
| 3级 | 0.2-0.3mm | 中度磨损 | 计划更换 |
| 4级 | 0.3-0.5mm | 严重磨损 | 立即更换 |
| 5级 | >0.5mm | 失效 | 禁止使用 |

## 执行步骤
1. 加载传感器数据并进行预处理（滤波、去噪）
2. 提取时域和频域特征
3. 使用磨损评估模型（CNN-LSTM或Transformer）进行状态分类
4. 计算后刀面磨损量VB的预测值
5. 结合刀具寿命模型预测剩余使用寿命（RUL）
6. 生成换刀策略建议

## 输出格式
```json
{
  "wear_level": 2,
  "vb_predicted": 0.15,
  "vb_confidence_interval": [0.12, 0.18],
  "rul_remaining_minutes": 45.3,
  "tool_status": "轻微磨损",
  "recommendation": "继续使用，建议在30分钟后再次检查",
  "feature_importance": {
    "cutting_force_rms": 0.35,
    "vibration_peak": 0.28,
    "temperature_gradient": 0.22,
    "acoustic_emission": 0.15
  }
}
```

## 常见错误处理
- 如果传感器数据缺失或异常，返回错误并列出需要的数据项
- 如果信号质量过低（SNR<10dB），提示传感器可能需要校准
- 如果刀具类型未在模型库中，使用通用模型并降低置信度
- 如果数据采样率不足，进行插值处理并标记警告
