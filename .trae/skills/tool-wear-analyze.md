# 刀具磨损分析技能 (Tool Wear Analyze Skill)

## 元数据

| 字段 | 值 |
|------|-----|
| 技能名称 | 刀具磨损分析 |
| 英文名称 | Tool Wear Analyze |
| 适用场景 | 刀具磨损曲线预测、剩余寿命估算、加工参数优化建议、实测数据校准、振动信号异常检测 |
| 前置条件 | 1. FastAPI服务已启动；2. 刀具磨损预测器已初始化（ToolWearPredictor）；3. 已知加工材料和刀具类型 |
| API端点 | POST /api/v1/wear/predict, POST /api/v1/wear/remaining-life, POST /api/v1/wear/suggest, POST /api/v1/wear/calibrate |
| 依赖模块 | tool_wear_predictor.py, models/validation.py (WearCurve, WearDataPoint, WearPhase), bosch_cnc_loader.py, uniwear_loader.py |

---

## 一、磨损阶段识别

### 1.1 三阶段定义

| 阶段 | 编码 | 磨损量范围 (VB) | 特征描述 | 磨损速率 |
|------|------|----------------|---------|---------|
| 初期磨损 | INITIAL | VB < 0.05 mm | 刀具刃口快速磨合，磨损速率较高但持续时间短 | 快速下降 |
| 稳定磨损 | STEADY | 0.05 <= VB < 0.2 mm | 磨损速率稳定，刀具进入正常工作状态 | 缓慢恒定 |
| 快速磨损 | ACCELERATED | VB >= 0.2 mm | 磨损加速，接近刀具寿命终点，需准备换刀 | 指数增长 |

### 1.2 阶段转换判定阈值

```python
# tool_wear_predictor.py 中的阶段判定逻辑
USUI_TAYLOR_SWITCH_THRESHOLD = 0.2  # Usui/Taylor模型切换阈值

def _determine_phase(self, vb: float) -> WearPhase:
    if vb < 0.05:
        return WearPhase.INITIAL       # 初期磨损
    elif vb < 0.2:
        return WearPhase.STEADY        # 稳定磨损
    else:
        return WearPhase.ACCELERATED   # 快速磨损
```

### 1.3 识别算法

阶段识别基于当前磨损量（VB值）直接判定：
1. 读取当前磨损量 `current_wear`（单位：mm）
2. 与阈值比较：0.05mm 和 0.2mm
3. 返回对应的 `WearPhase` 枚举值
4. 磨损曲线中每个数据点独立标记阶段

---

## 二、LTC模型在时序磨损预测中的应用

### 2.1 LTC模型技术优势

| 特性 | 说明 | 优势 |
|------|------|------|
| 长序列支持 | temporal_horizon > 1000 | 可处理长时间跨度磨损数据 |
| 记忆机制 | memory_state 指数衰减更新 | 捕捉磨损历史趋势信息 |
| 时序建模 | 逐时间步处理，聚合时序状态 | 适应磨损非线性变化特征 |
| 多步预测 | predict_sequence(future_steps) | 预测未来磨损趋势 |

### 2.2 与传统方法对比

| 方法 | 精度 | 适用范围 | 计算复杂度 | 说明 |
|------|------|---------|-----------|------|
| Usui磨损率模型 | 中等 | VB < 0.2mm | 低 | 基于热激活理论，物理意义明确 |
| Taylor刀具寿命模型 | 中等 | VB >= 0.2mm | 低 | 经典经验公式，需材料修正 |
| 混合自适应模型 | 高 | 全范围 | 中 | 动态权重组合Usui和Taylor |
| LTC神经网络 | 高 | 长序列 | 高 | 数据驱动，需训练数据 |
| 机器学习(RF/XGB) | 高 | 有标签数据 | 中 | 依赖特征工程 |

### 2.3 适用工况范围

```python
# 支持的材料（12种）
supported_materials = [
    "aluminum_6061", "aluminum_7075",    # 铝合金
    "steel_45", "steel_4140",             # 钢
    "stainless_304", "stainless_316", "stainless_hrc52",  # 不锈钢
    "titanium_ti64", "titanium_tc4",      # 钛合金
    "inconel_718",                         # 镍基合金
    "cast_iron", "brass"                  # 铸铁/黄铜
]

# 支持的刀具（7种）
supported_tools = [
    "carbide", "coated_carbide",  # 硬质合金/涂层硬质合金
    "cermet", "ceramic",          # 金属陶瓷/陶瓷
    "cbn", "pcd",                 # 立方氮化硼/聚晶金刚石
    "hss"                         # 高速钢
]
```

---

## 三、混合磨损预测模型

### 3.1 Usui磨损率模型

**公式**：dW/dt = A * exp(-B/T) * σ * v

| 参数 | 含义 | 单位 | 说明 |
|------|------|------|------|
| A | 磨损系数 | - | 材料和刀具依赖 |
| B | 激活能常数 | K | 温度相关参数 |
| T | 切削温度 | K | 由切削参数计算 |
| σ | 接触压力 | MPa | feed_rate * depth_of_cut * hardness_factor |
| v | 滑动速度 | m/s | cutting_speed * 16.667 |

```python
def _usui_wear_rate(self, cutting_speed, feed_rate, depth_of_cut, temperature, material, tool):
    thermal_energy = material.usui_B / max(temperature, 300.0)
    exponential = math.exp(-thermal_energy)
    contact_pressure = feed_rate * depth_of_cut * material.hardness_factor * 100.0
    sliding_velocity = cutting_speed * 16.667
    rate = material.usui_A * exponential * contact_pressure * sliding_velocity
    rate *= tool["wear_factor"]
    return max(1e-6, min(0.01, rate))
```

### 3.2 Taylor刀具寿命模型

**公式**：V * T^n = C

| 参数 | 含义 | 单位 | 说明 |
|------|------|------|------|
| V | 切削速度 | m/min | 加工参数 |
| T | 刀具寿命 | min | 预测目标 |
| n | Taylor指数 | - | 材料依赖（0.12-0.40） |
| C | Taylor常数 | - | 材料和刀具依赖 |

```python
def _taylor_wear_rate(self, current_vb, cutting_speed, feed_rate, depth_of_cut, material, tool):
    effective_C = material.taylor_C / (tool["wear_factor"] ** 0.5)
    effective_n = material.taylor_n
    feed_correction = 1.0 + (feed_rate - 0.2) * 0.8
    depth_correction = 1.0 + (depth_of_cut - 1.0) * 0.15
    corrected_speed = cutting_speed * feed_correction * depth_correction
    equivalent_life = (effective_C / max(corrected_speed, 1.0)) ** (1.0 / effective_n)
    wear_progress = current_vb / self.default_replacement_threshold
    acceleration = 1.0 + 2.0 * (wear_progress ** 2)
    wear_rate = (current_vb / max(equivalent_life, 1.0)) * acceleration
    wear_rate *= material.hardness_factor * 0.01
    return max(1e-5, min(0.02, wear_rate))
```

### 3.3 混合自适应模型

**公式**：wear_rate = w * Usui + (1-w) * Taylor

权重计算：
```python
# VB < 0.2mm: Usui主导
if current_vb < USUI_TAYLOR_SWITCH_THRESHOLD:
    usui_weight = 1.0 - (current_vb / USUI_TAYLOR_SWITCH_THRESHOLD)
    usui_weight = max(0.3, min(0.9, usui_weight))  # 限制在[0.3, 0.9]
    wear_rate = usui_weight * usui_rate + (1.0 - usui_weight) * taylor_rate

# VB >= 0.2mm: Taylor主导
else:
    progress = (current_vb - USUI_TAYLOR_SWITCH_THRESHOLD) / (wear_threshold - USUI_TAYLOR_SWITCH_THRESHOLD)
    taylor_weight = max(0.6, min(0.95, 0.5 + 0.45 * progress))
    wear_rate = taylor_weight * taylor_rate + (1.0 - taylor_weight) * usui_rate
```

---

## 四、输出字段规范

### 4.1 磨损曲线输出

```python
# WearCurve 数据结构
{
    "data_points": [
        {
            "time": 0.0,        # 时间（秒），保留2位小数
            "vb": 0.0000,       # 磨损量（mm），保留4位小数
            "wear_rate": 0.000001,  # 磨损速率（mm/s），保留6位小数
            "phase": "INITIAL"  # 磨损阶段枚举
        },
        ...
    ],
    "total_life": 300.0,        # 总寿命（秒），保留2位小数
    "time_to_threshold": 285.5, # 到达阈值时间（秒），保留2位小数
    "wear_rate_avg": 0.001234,  # 平均磨损速率（mm/s），保留6位小数
    "confidence": 0.85          # 预测置信度，保留2位小数
}
```

| 字段 | 单位 | 精度 | 说明 |
|------|------|------|------|
| time | 秒(s) | 2位小数 | 从起始时刻的累计时间 |
| vb | 毫米(mm) | 4位小数 | 刀具后刀面磨损量 |
| wear_rate | 毫米/秒(mm/s) | 6位小数 | 当前时刻磨损速率 |
| wear_phase | 枚举 | - | INITIAL/STEADY/ACCELERATED |
| total_life | 秒(s) | 2位小数 | 刀具从初始到更换阈值的总时间 |
| time_to_threshold | 秒(s) | 2位小数 | 从当前磨损到阈值的时间 |
| wear_rate_avg | 毫米/秒(mm/s) | 6位小数 | 全生命周期平均磨损速率 |
| confidence | 无 | 2位小数 | 预测置信度，范围[0.5, 0.98] |

### 4.2 剩余寿命（RUL）计算

```python
def predict_remaining_life(self, current_wear, input_parameters):
    tool = self._get_tool_params(tool_type)
    wear_threshold = tool.get("max_vb", self.default_replacement_threshold)
    remaining_wear = max(0.0, wear_threshold - current_wear)
    
    # 模拟磨损曲线
    simulated_curve = self.predict_wear_curve(temp_params)
    
    # 计算从当前磨损到阈值的时间
    return max(0.0, round(simulated_curve.time_to_threshold - elapsed, 2))
```

### 4.3 参数调整建议输出

```json
{
  "current_wear": 0.1500,
  "remaining_life": 45.32,
  "urgency": "WARNING",
  "suggestions": [
    {
      "param_type": "cutting_speed",
      "current_value": 150.0,
      "suggested_value": 127.5,
      "adjustment_delta": -15.0,
      "expected_effect": "预计延长刀具寿命18.5%"
    },
    {
      "param_type": "feed_rate",
      "current_value": 0.2,
      "suggested_value": 0.180,
      "adjustment_delta": -10.0,
      "expected_effect": "减少切削力，降低磨损率约8.0%"
    },
    {
      "param_type": "coolant_flow",
      "current_value": 10.0,
      "suggested_value": 12.5,
      "adjustment_delta": 25.0,
      "expected_effect": "增强冷却效果，降低切削温度，减缓月牙洼磨损"
    }
  ]
}
```

| 紧急度 | 触发条件 | 速度降幅 | 进给降幅 | 冷却增幅 |
|--------|---------|---------|---------|---------|
| NORMAL | wear_ratio <= 0.5 | 5% | 0% | 10% |
| WARNING | 0.5 < wear_ratio <= 0.8 | 15% | 10% | 25% |
| CRITICAL | wear_ratio > 0.8 | 30% | 20% | 50% |

### 4.4 校准输出

```json
{
  "measured_wear": 0.1200,
  "predicted_wear_at_time": 0.1050,
  "deviation": 0.0150,
  "deviation_percent": 14.29,
  "correction_factor": 1.071,
  "calibrated_curve": {...}
}
```

---

## 五、特征提取

### 5.1 振动信号时域特征

| 特征 | 计算方法 | 说明 |
|------|---------|------|
| RMS | sqrt(mean(x²)) | 反映振动能量水平 |
| Peak | max(\|x\|) | 最大振幅，检测冲击 |
| Kurtosis | mean((x-μ)⁴)/σ⁴ | 峭度，检测异常冲击 |

```python
# Bosch CNC数据加载器中的特征提取
def extract_features(self, data):
    features = {}
    for ax in ["x", "y", "z"]:
        axis_data = data[:, axis_index[ax]]
        # 时域特征
        features[f"time_{ax}_rms"] = np.sqrt(np.mean(axis_data ** 2))
        features[f"time_{ax}_peak"] = np.max(np.abs(axis_data))
        features[f"time_{ax}_kurtosis"] = np.mean((axis_data - np.mean(axis_data)) ** 4) / (np.std(axis_data) ** 4 + 1e-8)
    return features
```

### 5.2 频域特征

| 特征 | 计算方法 | 说明 |
|------|---------|------|
| 主频 (dominant_freq) | FFT后取最大幅值对应频率 | 反映主要振动频率 |
| 功率谱密度 (PSD) | Welch方法估计 | 频率能量分布 |

```python
# 频域特征提取
from scipy import signal
f, Pxx = signal.welch(axis_data, fs=sampling_rate)
dominant_freq = f[np.argmax(Pxx)]
features[f"freq_{ax}_dominant_freq"] = dominant_freq
```

### 5.3 统计特征

| 特征 | 说明 |
|------|------|
| 均值 (mean) | 信号直流分量 |
| 方差 (variance) | 信号波动程度 |
| 分位数 (quantile) | 25%, 50%, 75%分位数 |

### 5.4 跨轴特征

| 特征 | 说明 |
|------|------|
| energy_ratio | 各轴能量占总能量的比例 |

```python
# 跨轴能量比
total_energy = sum(np.sum(data[:, i] ** 2) for i in range(3))
for ax in ["x", "y", "z"]:
    features[f"cross_{ax}_energy_ratio"] = np.sum(data[:, axis_index[ax]] ** 2) / total_energy
```

---

## 六、机器学习模型训练

### 6.1 Bosch CNC数据集（振动异常分类）

```python
# 训练配置
from sklearn.ensemble import RandomForestClassifier
from sklearn.svm import SVC
# 支持模型: random_forest, xgboost, svm

model = RandomForestClassifier(
    n_estimators=100, max_depth=10, random_state=42, n_jobs=-1
)
# 评估指标: accuracy, precision, recall, f1, confusion_matrix
```

### 6.2 Uniwear数据集（磨损回归预测）

| 数据集 | 材料 | 实验数 | 信号类型 | 来源 |
|--------|------|--------|---------|------|
| NUAA | TC4 (钛合金) | 9 (W1-W9) | force/vibration/power | 南京航空航天大学 |
| PHM2010 | HRC52 (不锈钢) | 3 (c1,c4,c6) | force/vibration/acoustic_emission | PHM竞赛 |

```python
# 支持模型: random_forest, gradient_boosting, linear
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.linear_model import LinearRegression
# 评估指标: MAE, RMSE, R²

model = RandomForestRegressor(
    n_estimators=100, max_depth=10, random_state=42, n_jobs=-1
)
```

### 6.3 材料参数

| 材料 | taylor_n | taylor_C | usui_A | usui_B | hardness_factor |
|------|---------|---------|--------|--------|----------------|
| aluminum_6061 | 0.40 | 450.0 | 0.002 | 1200.0 | 0.6 |
| aluminum_7075 | 0.35 | 380.0 | 0.004 | 1100.0 | 0.75 |
| steel_45 | 0.25 | 280.0 | 0.008 | 900.0 | 1.0 |
| steel_4140 | 0.23 | 250.0 | 0.010 | 850.0 | 1.1 |
| stainless_304 | 0.20 | 200.0 | 0.015 | 800.0 | 1.3 |
| stainless_316 | 0.18 | 180.0 | 0.018 | 750.0 | 1.4 |
| stainless_hrc52 | 0.17 | 160.0 | 0.020 | 720.0 | 1.6 |
| titanium_ti64 | 0.15 | 120.0 | 0.025 | 650.0 | 1.8 |
| titanium_tc4 | 0.14 | 110.0 | 0.028 | 620.0 | 1.85 |
| inconel_718 | 0.12 | 90.0 | 0.035 | 600.0 | 2.2 |
| cast_iron | 0.22 | 220.0 | 0.012 | 850.0 | 1.15 |
| brass | 0.38 | 400.0 | 0.003 | 1150.0 | 0.5 |

### 6.4 刀具参数

| 刀具 | wear_factor | max_vb (mm) |
|------|------------|-------------|
| carbide | 1.0 | 0.3 |
| coated_carbide | 0.7 | 0.35 |
| cermet | 0.8 | 0.3 |
| ceramic | 0.6 | 0.35 |
| cbn | 0.4 | 0.4 |
| pcd | 0.3 | 0.35 |
| hss | 1.5 | 0.25 |

---

## 七、API调用示例

### 7.1 磨损曲线预测

```bash
curl -X POST http://localhost:8000/api/v1/wear/predict \
  -H "Content-Type: application/json" \
  -d '{
    "cutting_speed": 150.0,
    "feed_rate": 0.2,
    "depth_of_cut": 1.5,
    "material_type": "steel_45",
    "tool_type": "carbide",
    "current_wear": 0.0,
    "time_step": 1.0,
    "max_time": 300.0
  }'
```

### 7.2 剩余寿命预测

```bash
curl -X POST http://localhost:8000/api/v1/wear/remaining-life \
  -H "Content-Type: application/json" \
  -d '{
    "current_wear": 0.15,
    "cutting_speed": 150.0,
    "feed_rate": 0.2,
    "depth_of_cut": 1.5,
    "material_type": "steel_45",
    "tool_type": "carbide"
  }'
```

### 7.3 参数调整建议

```bash
curl -X POST http://localhost:8000/api/v1/wear/suggest \
  -H "Content-Type: application/json" \
  -d '{
    "current_wear": 0.15,
    "remaining_life": 50.0,
    "cutting_speed": 150.0,
    "feed_rate": 0.2,
    "depth_of_cut": 1.5,
    "coolant_flow": 10.0,
    "material_type": "steel_45",
    "tool_type": "carbide"
  }'
```

### 7.4 实测数据校准

```bash
curl -X POST http://localhost:8000/api/v1/wear/calibrate \
  -H "Content-Type: application/json" \
  -d '{
    "measured_wear": 0.12,
    "elapsed_time": 30.0,
    "cutting_speed": 150.0,
    "feed_rate": 0.2,
    "depth_of_cut": 1.5,
    "material_type": "steel_45",
    "tool_type": "carbide"
  }'
```

---

## 八、输出格式完整示例

### 8.1 磨损曲线预测响应

```json
{
  "code": 0,
  "data": {
    "data_points": [
      {"time": 0.0, "vb": 0.0, "wear_rate": 0.000012, "phase": "INITIAL"},
      {"time": 1.0, "vb": 0.0012, "wear_rate": 0.000013, "phase": "INITIAL"},
      {"time": 5.0, "vb": 0.0058, "wear_rate": 0.000015, "phase": "INITIAL"},
      {"time": 42.0, "vb": 0.0512, "wear_rate": 0.000018, "phase": "STEADY"},
      {"time": 180.0, "vb": 0.1850, "wear_rate": 0.000025, "phase": "STEADY"},
      {"time": 200.0, "vb": 0.2015, "wear_rate": 0.000035, "phase": "ACCELERATED"},
      {"time": 285.0, "vb": 0.2980, "wear_rate": 0.000089, "phase": "ACCELERATED"}
    ],
    "total_life": 285.5,
    "time_to_threshold": 285.5,
    "wear_rate_avg": 0.001051,
    "confidence": 0.85
  },
  "message": "Wear curve predicted successfully"
}
```

### 8.2 剩余寿命预测响应

```json
{
  "code": 0,
  "data": {
    "remaining_life": 125.5,
    "current_wear": 0.15,
    "replacement_threshold": 0.3
  },
  "message": "Remaining life predicted successfully"
}
```

### 8.3 跨数据集分析报告

```json
{
  "code": 0,
  "data": {
    "bosch_cnc": {
      "status": "trained",
      "data_type": "vibration_classification"
    },
    "uniwear": {
      "status": {"tc4": "trained", "hrc52": "trained"},
      "data_type": "wear_regression",
      "materials": {
        "tc4": {
          "source": "NUAA",
          "experiment_count": 9,
          "signal_types": "force/vibration/power"
        },
        "hrc52": {
          "source": "PHM2010",
          "experiment_count": 3,
          "signal_types": "force/vibration/acoustic_emission"
        }
      }
    },
    "cross_validation_strategy": [
      "Use Bosch vibration features with Uniwear wear regression to estimate wear",
      "Cross-validate Bosch good/bad labels against Uniwear predicted wear thresholds",
      "Use Uniwear TC4/HRC52 models for material-specific wear predictions in Bosch data"
    ],
    "material_specific_thresholds": {
      "tc4": 0.25,
      "hrc52": 0.28,
      "default": 0.3
    }
  },
  "message": "Cross-dataset analysis completed"
}
```

---

## 九、FAQ

**Q1: 磨损阶段如何判断？**
A: 根据刀具后刀面磨损量VB值判断：VB < 0.05mm为初期磨损（INITIAL），0.05 <= VB < 0.2mm为稳定磨损（STEADY），VB >= 0.2mm为快速磨损（ACCELERATED）。可通过`_determine_phase()`方法自动判定。

**Q2: 不同材料的磨损预测精度差异大吗？**
A: 是的。材料硬度系数（hardness_factor）直接影响预测精度。低硬度材料（如aluminum_6061, hardness_factor=0.6）预测置信度更高（~0.90），高硬度材料（如inconel_718, hardness_factor=2.2）置信度较低（~0.75）。

**Q3: 如何使用实测数据校准预测模型？**
A: 调用 `POST /api/v1/wear/calibrate` 接口，传入实测磨损值（measured_wear）和加工时间（elapsed_time）。系统会计算偏差百分比并生成校正因子（correction_factor），用于后续预测。

**Q4: 刀具更换阈值如何确定？**
A: 默认阈值为0.3mm。根据材料硬度自动调整：hardness_factor > 1.5时阈值为0.25mm；hardness_factor > 1.2时为0.28mm；hardness_factor < 0.7时为0.35mm。也可通过刀具类型的max_vb参数覆盖。

**Q5: 振动信号异常检测需要什么数据？**
A: 需要三轴振动信号数据（X/Y/Z轴），采样率至少10kHz。系统会自动提取时域特征（RMS、峰值、峭度）和频域特征（主频、PSD），使用训练的Bosch CNC分类模型判断异常。

**Q6: 支持哪些材料和刀具组合？**
A: 支持12种材料（铝合金、钢、不锈钢、钛合金、镍基合金、铸铁、黄铜）和7种刀具（硬质合金、涂层硬质合金、金属陶瓷、陶瓷、CBN、PCD、高速钢）。任意组合均可使用，系统自动匹配对应参数。

**Q7: 如何获取支持的磨损模型列表？**
A: 调用 `GET /api/v1/wear/models` 返回Usui磨损率模型、Taylor刀具寿命模型和混合自适应模型的详细信息，包括公式、适用范围和说明。

**Q8: 参数调整建议的紧急度如何判定？**
A: 基于磨损比率（wear_ratio = current_wear / wear_threshold）：wear_ratio <= 0.5为NORMAL，0.5 < wear_ratio <= 0.8为WARNING，wear_ratio > 0.8为CRITICAL。紧急度越高，参数降幅越大。
