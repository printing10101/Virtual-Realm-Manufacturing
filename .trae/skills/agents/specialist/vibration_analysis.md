---
skill_id: vibration_analysis
name: 振动频谱分析
version: 1.0.0
applicable_tasks: ["analysis", "prediction", "vibration_analysis"]
required_context: ["vibration_signal", "sampling_rate"]
tags: ["vibration", "spectrum", "fft", "anomaly", "sensor"]
---

# 振动频谱分析技能（代理专长）

## 适用场景
当需要对机械振动信号进行深度频谱分析、识别异常振动模式或诊断设备故障时，具有此专长的代理使用本技能。

## 输入参数
- vibration_signal: 振动信号时间序列（加速度，m/s²）
- sampling_rate: 采样率（Hz）
- analysis_type: 分析类型（"fft" | "wavelet" | "hilbert" | "full_spectrum"）
- frequency_range: 关注的频率范围（[low, high]，可选）

## 振动故障特征频率表
| 故障类型 | 特征频率关系 | 典型频段 |
|---------|-------------|---------|
| 主轴不平衡 | 1× 转频 | 10-200 Hz |
| 不对中 | 1×, 2×, 3× 转频 | 10-500 Hz |
| 滚动轴承内圈 | BPFI ± n× 转频 | 500-5000 Hz |
| 滚动轴承外圈 | BPFO ± n× 转频 | 500-5000 Hz |
| 齿轮啮合 | n× 齿数×转频 | 100-10000 Hz |
| 刀具颤振 | 刀具通过频率附近 | 100-2000 Hz |

## 执行步骤
1. 对振动信号进行预处理（去趋势、加窗、零均值化）
2. 执行FFT获取功率谱密度
3. 提取峰值频率、谐波关系和边频带特征
4. 与已知故障特征频率库进行匹配
5. 如需更深分析，执行小波变换获取时频图
6. 计算振动烈度指标（RMS、峰值、峭度、包络谱）
7. 返回故障诊断结果和置信度

## 输出格式
```json
{
  "analysis_type": "full_spectrum",
  "dominant_frequencies": [
    {"freq_hz": 25.3, "amplitude": 0.82, "harmonic_of": "spindle_1x"},
    {"freq_hz": 50.6, "amplitude": 0.45, "harmonic_of": "spindle_2x"},
    {"freq_hz": 420.0, "amplitude": 0.31, "type": "bearing_bpfi"}
  ],
  "vibration_severity": {
    "rms": 2.35,
    "peak": 8.91,
    "crest_factor": 3.79,
    "iso_10816_level": "acceptable"
  },
  "diagnosis": {
    "primary_fault": "轻微主轴不平衡",
    "secondary_fault": null,
    "confidence": 0.85,
    "recommended_action": "计划下次停机时进行动平衡校正"
  }
}
```

## 常见错误处理
- 如果采样率低于关注频率的2倍（奈奎斯特），提示信号混叠风险
- 如果信号长度不足（<1024点），降低频率分辨率并降低置信度
- 如果无法匹配任何已知故障模式，报告为"未分类异常"
