---
skill_id: thermal_modeling
name: 切削热力耦合建模
version: 1.0.0
applicable_tasks: ["analysis", "prediction", "optimization"]
required_context: ["material", "cutting_params", "thermal_data"]
tags: ["thermal", "modeling", "fea", "cutting", "simulation"]
---

# 切削热力耦合建模技能（代理专长）

## 适用场景
当需要进行切削过程的热力耦合分析、温度场预测或热变形补偿时，具有此专长的代理使用本技能。

## 输入参数
- material: 工件材料及其热物理属性
  - thermal_conductivity: 导热系数 (W/m·K)
  - specific_heat: 比热容 (J/kg·K)
  - density: 密度 (kg/m³)
  - thermal_expansion: 热膨胀系数 (1/K)
- cutting_params: 切削参数（v, f, ap）
- thermal_data: 实测温度数据（可选，用于模型校准）
- tool_geometry: 刀具几何参数
  - rake_angle: 前角 (°)
  - clearance_angle: 后角 (°)
  - nose_radius: 刀尖半径 (mm)
- cooling_method: 冷却方式（"dry" | "flood" | "mql" | "cryogenic"）

## 热传导模型
```
Q_total = Q_shear + Q_friction
其中:
  Q_shear = Fs × Vs  (剪切面产热)
  Q_friction = Ff × Vchip  (摩擦面产热)

温度分布满足:
  ∂T/∂t = α × ∇²T + q̇/(ρ·cp)
```

## 执行步骤
1. 根据材料属性和切削参数计算剪切面产热量
2. 计算刀-屑接触面摩擦产热量
3. 确定热分配系数（刀具/切屑/工件的热分配比）
4. 建立有限差分或有限元热传导模型
5. 求解稳态/瞬态温度场分布
6. 计算热变形量并对加工精度进行补偿计算
7. 如果有实测温度数据，校准模型参数

## 输出格式
```json
{
  "thermal_analysis": {
    "max_temperature_degC": 680.5,
    "temperature_at_cutting_edge": 650.2,
    "temperature_at_workpiece_surface": 320.8,
    "heat_partition": {
      "chip": 0.65,
      "tool": 0.25,
      "workpiece": 0.10
    }
  },
  "thermal_deformation": {
    "workpiece_expansion_um": 15.3,
    "tool_elongation_um": 8.7,
    "total_error_um": 24.0,
    "compensation_vector": {"x": -12.5, "y": -8.2, "z": -17.0}
  },
  "cooling_effectiveness": {
    "method": "flood",
    "temperature_reduction_degC": 120.5,
    "recommendation": "当前冷却方式有效，温度在安全范围内"
  }
}
```

## 常见错误处理
- 如果材料热属性不完整，使用同类材料默认值但降低精度置信度
- 如果冷却方式不支持，返回支持列表并提示选择合适的冷却方式
- 如果温度超过材料熔点或软化点，触发安全警告
- 如果网格收敛失败，自动调整网格密度并重试
