# 工艺优化技能 (Process Optimize Skill)

## 元数据

| 字段 | 值 |
|------|-----|
| 技能名称 | 工艺优化 |
| 英文名称 | Process Optimize |
| 适用场景 | 多工序联合优化、加工参数调优、能耗最小化、刀具寿命最大化、表面质量控制 |
| 前置条件 | 1. FastAPI服务已启动；2. HybridLNN模型已注册；3. 工作流编排器已初始化（WorkflowLNNOrchestrator）；4. 已知加工材料、刀具类型和机床参数 |
| API端点 | POST /api/v1/lnn/predict (HybridLNN模型), POST /api/v1/wear/suggest (参数调整) |
| 依赖模块 | torch_hybrid_lnn.py, workflow_orchestrator.py, tool_wear_predictor.py, task_router.py, engine.py, preprocessing.py |

---

## 一、HybridLNN多工序联合优化

### 1.1 模型架构设计

```
输入层 (batch_size, seq_len, input_size)
    │
    ▼
┌─────────────────────────────────┐
│ CNN特征提取层                     │
│ ┌───────────────────────────┐   │
│ │ Conv1d (in→h/4, k=5)      │   │
│ │ BatchNorm1d + ReLU         │   │
│ │ MaxPool1d (stride=2)       │   │
│ ├───────────────────────────┤   │
│ │ Conv1d (h/4→h/2, k=5)     │   │
│ │ BatchNorm1d + ReLU         │   │
│ │ MaxPool1d (stride=2)       │   │
│ ├───────────────────────────┤   │
│ │ Conv1d (h/2→h, k=5)       │   │
│ │ BatchNorm1d + ReLU         │   │
│ │ AdaptiveAvgPool1d(1)       │   │
│ └───────────────────────────┘   │
└─────────────────────────────────┘
    │
    ▼ CNN输出 (batch_size, hidden_size)
    │ (扩展为seq_len维度)
    ▼
┌─────────────────────────────────┐
│ LTC时序建模层                     │
│ ┌───────────────────────────┐   │
│ │ LTCCell(input→hidden)      │   │
│ │ 逐时间步处理，维护hidden_state │   │
│ └───────────────────────────┘   │
└─────────────────────────────────┘
    │
    ▼ LTC输出序列 (batch_size, seq_len, hidden_size)
    │ (均值池化)
    ▼
┌─────────────────────────────────┐
│ 全连接输出层                      │
│ ┌───────────────────────────┐   │
│ │ Linear(hidden→hidden/2)    │   │
│ │ ReLU + Dropout             │   │
│ │ Linear(hidden/2→output)    │   │
│ └───────────────────────────┘   │
└─────────────────────────────────┘
    │
    ▼
输出层 (batch_size, output_size)
```

### 1.2 CNN特征提取层

```python
# torch_hybrid_lnn.py 中的CNN构建
def _build_cnn(self, input_channels, hidden_size, num_layers=3):
    kernel_sizes = [5, 5, 5, 3, 3][:max(num_layers, 3)]
    filter_sizes = [hidden_size // 4, hidden_size // 2, hidden_size] + \
                   [hidden_size] * (max(num_layers, 3) - 3)

    layers = []
    in_channels = input_channels
    for i, (kernel_size, out_channels) in enumerate(zip(kernel_sizes, filter_sizes)):
        layers.append(nn.Conv1d(in_channels, out_channels, kernel_size, padding=kernel_size // 2))
        layers.append(nn.BatchNorm1d(out_channels))
        layers.append(nn.ReLU())
        if i < len(kernel_sizes) - 1:
            layers.append(nn.MaxPool1d(2, stride=2, padding=0))
        in_channels = out_channels
    layers.append(nn.AdaptiveAvgPool1d(1))
    return nn.Sequential(*layers)
```

| 层类型 | 参数 | 作用 |
|--------|------|------|
| Conv1d | kernel_size=5/3, padding=kernel//2 | 提取局部空间特征 |
| BatchNorm1d | out_channels | 归一化，加速收敛 |
| ReLU | - | 非线性激活 |
| MaxPool1d | kernel=2, stride=2 | 降采样，减少参数量 |
| AdaptiveAvgPool1d | output_size=1 | 全局平均池化，固定输出维度 |

### 1.3 LTC时序建模层

```python
# LTCCell逐时间步处理
self.ltc_cells = nn.ModuleList([
    LTCCell(ltc_config.input_size if i == 0 else ltc_config.hidden_size, ltc_config.hidden_size)
    for i in range(ltc_config.num_layers)
])

# 前向传播中的时序处理
for t in range(seq_len):
    ltc_input = cnn_features[:, t, :]
    new_hidden = []
    layer_input = ltc_input
    for i, cell in enumerate(self.ltc_cells):
        h = hidden_state[i]
        h_new = cell(layer_input, h, dt)  # dt为时间步长
        new_hidden.append(h_new)
        layer_input = h_new
    hidden_state = torch.stack(new_hidden, dim=0)
```

### 1.4 工序间约束传递机制

```python
# workflow_orchestrator.py 中的上下文传递
context: Dict[str, Any] = {}
for step in plan.steps:
    if step.step_type == "data_preprocessing":
        step.result = self._execute_preprocessing_step(task, context)
    elif step.step_type == "lnn_inference":
        step.result = self._execute_inference_step(step, task, context)
    elif step.step_type == "result_postprocessing":
        step.result = self._execute_postprocessing_step(step, task, context)
    context[step.output_key] = step.result  # 结果存入上下文供后续步骤使用
```

约束传递流程：
1. **数据预处理**：将用户输入标准化为模型可接受的格式
2. **模型推理**：基于路由决策选择最优LNN模型，利用上下文中的预处理结果
3. **后处理验证**：验证推理结果是否满足工艺约束（表面粗糙度、切削力等）
4. **降级机制**：若步骤失败且启用fallback，切换至规则引擎

### 1.5 并行计算策略

| 策略 | 说明 | 配置 |
|------|------|------|
| 并发训练限制 | 最多3个训练任务同时运行 | MAX_CONCURRENT_TRAINING_TASKS = 3 |
| DataLoader并行 | 多进程加载数据 | num_workers = get_optimal_num_workers() |
| GPU批处理 | 在GPU上并行处理batch | batch_size自动优化 |
| Pin Memory | GPU训练时启用pin_memory加速数据传输 | pin_memory = device.type == "cuda" |

---

## 二、优化目标

### 2.1 最小化加工时间

目标函数：
```
min T = L / (f * n)
```

其中：
- T：加工时间（min）
- L：加工长度（mm）
- f：进给量（mm/r）
- n：主轴转速（r/min）

切削速度与主轴转速关系：
```
n = 1000 * v_c / (π * D)
```

其中：
- v_c：切削速度（m/min）
- D：刀具直径（mm）

### 2.2 最大化刀具寿命

刀具寿命模型（Taylor修正）：
```
V * T^n = C_eff
```

其中：
- V：切削速度（m/min）
- T：刀具寿命（min）
- n：Taylor指数（材料依赖，0.12-0.40）
- C_eff = C / (wear_factor^0.5)：修正后的Taylor常数

寿命扩展百分比计算：
```python
# suggest_parameter_adjustment() 中的寿命扩展估算
speed_factor = (1.0 - speed_reduction) ** (-1.0 / n)
estimated_life_extension = (speed_factor - 1.0) * 100.0
```

### 2.3 最小化能耗

能耗计算：
```
E = P * T
```

其中：
- E：总能耗（kWh）
- P：切削功率（kW），P = F_c * v_c / 60000
- T：加工时间（min）

能耗优化策略：
1. 降低切削速度 → 降低功率但增加时间
2. 优化进给量 → 平衡材料去除率和切削力
3. 选择合适背吃刀量 → 减少走刀次数

### 2.4 多目标优化权重分配

```python
# 多目标加权和方法
# 用户可自定义权重
weights = {
    "time_weight": 0.3,        # 加工时间权重
    "tool_life_weight": 0.4,   # 刀具寿命权重
    "energy_weight": 0.3,      # 能耗权重
}

# 综合目标函数
objective = (time_weight * normalized_time +
             tool_life_weight * (1 - normalized_tool_life) +
             energy_weight * normalized_energy)
```

权重分配策略：

| 场景 | time_weight | tool_life_weight | energy_weight | 说明 |
|------|------------|-----------------|---------------|------|
| 批量生产 | 0.5 | 0.2 | 0.3 | 优先考虑加工效率 |
| 精密加工 | 0.2 | 0.5 | 0.3 | 优先考虑表面质量和刀具寿命 |
| 绿色制造 | 0.3 | 0.3 | 0.4 | 优先考虑能耗最小化 |
| 均衡模式 | 0.33 | 0.34 | 0.33 | 三目标均衡 |

---

## 三、约束条件

### 3.1 表面粗糙度约束

| 加工等级 | Ra上限值 | 适用场景 |
|---------|---------|---------|
| 粗加工 | Ra <= 12.5 um | 毛坯初加工 |
| 半精加工 | Ra <= 6.3 um | 中等精度要求 |
| 精加工 | Ra <= 3.2 um | 标准加工（默认要求） |
| 精密加工 | Ra <= 1.6 um | 高精度配合面 |
| 超精密加工 | Ra <= 0.8 um | 特殊精密要求 |

表面粗糙度经验公式：
```
Ra = f² / (8 * r_ε)
```

其中：
- f：进给量（mm/r）
- r_ε：刀尖圆弧半径（mm）

### 3.2 切削力安全阈值

```
P_cutting = F_c * v_c / 60000 <= P_machine_max
```

其中：
- P_cutting：切削功率（kW）
- F_c：主切削力（N）
- v_c：切削速度（m/min）
- P_machine_max：机床最大功率（kW）

切削力约束范围：
- 最大切削力不超过机床额定功率的80%
- 进给力不超过进给系统额定推力的70%
- 背向力不超过机床刚性允许范围

### 3.3 振动幅值允许区间

```python
# 工艺基线中的振动RMS范围（来自Bosch数据集）
{
    "rms_ranges": {
        "x_rms": {"min": 0.05, "max": 0.50, "mean": 0.20, "std": 0.08},
        "y_rms": {"min": 0.03, "max": 0.40, "mean": 0.15, "std": 0.06},
        "z_rms": {"min": 0.04, "max": 0.45, "mean": 0.18, "std": 0.07},
    },
    "dominant_frequencies": {
        "x_dom_freq": {"min": 100, "max": 2000, "mean": 800},
        "y_dom_freq": {"min": 100, "max": 2000, "mean": 750},
        "z_dom_freq": {"min": 100, "max": 2000, "mean": 850},
    },
    "energy_distribution": {
        "x_energy_ratio": {"min": 0.25, "max": 0.45, "mean": 0.35},
        "y_energy_ratio": {"min": 0.20, "max": 0.40, "mean": 0.30},
        "z_energy_ratio": {"min": 0.25, "max": 0.45, "mean": 0.35},
    }
}
```

### 3.4 约束优先级排序

| 优先级 | 约束类型 | 违反后果 | 处理方式 |
|--------|---------|---------|---------|
| P0（最高） | 机床功率限制 | 设备损坏 | 硬约束，不可违反 |
| P1 | 振动幅值上限 | 加工质量严重下降 | 硬约束，不可违反 |
| P2 | 表面粗糙度上限 | 工件不合格 | 软约束，允许轻微偏差 |
| P3（最低） | 刀具磨损阈值 | 刀具提前更换 | 软约束，可通过参数调整 |

---

## 四、评估指标

### 4.1 MSE（均方误差）

```
MSE = (1/n) * Σ(y_true - y_pred)²
```

| 范围 | 评价 |
|------|------|
| MSE < 0.01 | 优秀 |
| 0.01 <= MSE < 0.1 | 良好 |
| 0.1 <= MSE < 1.0 | 可接受 |
| MSE >= 1.0 | 需要优化 |

### 4.2 MAE（平均绝对误差）

```
MAE = (1/n) * Σ|y_true - y_pred|
```

| 范围 | 评价 |
|------|------|
| MAE < 0.05 | 优秀 |
| 0.05 <= MAE < 0.2 | 良好 |
| 0.2 <= MAE < 0.5 | 可接受 |
| MAE >= 0.5 | 需要优化 |

### 4.3 R²（决定系数）

```
SS_res = Σ(y_true - y_pred)²
SS_tot = Σ(y_true - mean(y_true))²
R² = 1 - SS_res / SS_tot
```

```python
# 训练完成后的R²计算
ss_res = np.sum((targets - preds) ** 2)
ss_tot = np.sum((targets - np.mean(targets)) ** 2)
r2_score = float(1.0 - ss_res / ss_tot) if ss_tot > 0 else 0.0
```

| 范围 | 解读 |
|------|------|
| R² >= 0.95 | 模型拟合极好 |
| 0.90 <= R² < 0.95 | 模型拟合良好 |
| 0.80 <= R² < 0.90 | 模型拟合可接受 |
| R² < 0.80 | 模型需要改进 |
| R² < 0 | 模型不如均值预测 |

### 4.4 工艺合格率统计

合格率计算流程：
1. 收集所有加工样本的预测结果和实际结果
2. 对每个样本判定是否满足工艺约束（表面粗糙度、切削力、振动）
3. 合格率 = 满足约束的样本数 / 总样本数

```python
# 合格率计算示例
def calculate_process_pass_rate(predictions, constraints):
    passed = 0
    for pred in predictions:
        if (pred.surface_roughness <= constraints.max_roughness and
            pred.cutting_force <= constraints.max_force and
            pred.vibration <= constraints.max_vibration):
            passed += 1
    return passed / len(predictions)
```

| 合格率 | 评价 |
|--------|------|
| >= 99% | 优秀 |
| 95% - 99% | 良好 |
| 90% - 95% | 可接受 |
| < 90% | 需要优化工艺参数 |

---

## 五、工作流编排

### 5.1 工作流执行计划

```python
# 标准工作流步骤
steps = [
    WorkflowStep(
        name="preprocess",
        step_type="data_preprocessing",
        output_key="preprocessed_data",
        timeout_ms=1000,
    ),
    WorkflowStep(
        name="lnn_inference",
        step_type="lnn_inference",
        model_name="CFC-Fast",  # 由路由决策动态选择
        input_mapping={"data": "preprocessed_data"},
        output_key="inference_result",
        timeout_ms=300000,
        retry_count=3,
    ),
    WorkflowStep(
        name="postprocess",
        step_type="result_postprocessing",
        input_mapping={"result": "inference_result"},
        output_key="final_result",
        timeout_ms=1000,
    ),
]
```

### 5.2 降级策略

| 策略 | 触发条件 | 行为 |
|------|---------|------|
| RULE_ENGINE | LNN不可用或置信度过低 | 切换至规则引擎推理 |
| DEFAULT_OUTPUT | 规则引擎也不可用 | 返回默认输出 |
| CACHED_RESULT | 有历史缓存结果 | 使用缓存结果 |
| ERROR_RAISE | 所有降级均失败 | 抛出错误 |

### 5.3 任务路由决策

```python
# 任务类别推断逻辑
def _infer_task_category(self, description: str) -> TaskCategory:
    desc_lower = description.lower()
    temporal_keywords = ["predict", "forecast", "trend", "时间序列", "预测"]
    rule_keywords = ["rule", "check", "validate", "规则", "验证", "检查"]
    nlp_keywords = ["explain", "summarize", "翻译", "解释", "分析"]

    if any(kw in desc_lower for kw in temporal_keywords):
        return TaskCategory.TIME_SERIES
    if any(kw in desc_lower for kw in rule_keywords):
        return TaskCategory.RULE_BASED
    if any(kw in desc_lower for kw in nlp_keywords):
        return TaskCategory.NLP
    return TaskCategory.REGRESSION
```

### 5.4 置信度阈值

```python
# fallback_threshold 默认值
self._fallback_threshold = 0.50  # 低于此值触发降级

# 置信度提取
def _extract_confidence(self, result: WorkflowResult) -> float:
    output = result.output
    if isinstance(output, dict):
        context = output.get("context", {})
        inference_result = context.get("inference_result")
        if inference_result and hasattr(inference_result, "confidence"):
            return inference_result.confidence
    return 1.0
```

---

## 六、调用示例

### 6.1 Python代码示例 — 工作流编排

```python
from app.ai.lnn.workflow.workflow_orchestrator import WorkflowLNNOrchestrator
from app.ai.lnn.config.config_manager import YAMLConfigManager

# 初始化编排器
config = YAMLConfigManager(config_path="config/lnn_workflow.yaml")
orchestrator = WorkflowLNNOrchestrator(config=config)

# 执行优化工作流
user_input = {
    "task_description": "优化steel_45材料的切削参数，目标：最小化加工时间，最大化刀具寿命",
    "input_data": {
        "material": "steel_45",
        "tool_type": "carbide",
        "cutting_speed": 150.0,
        "feed_rate": 0.2,
        "depth_of_cut": 1.5,
    },
    "precision_requirement": 0.9,
    "time_sensitivity": 0.7,
    "max_latency_ms": 1000,
}

result = orchestrator.execute_workflow(user_input)
print(f"成功: {result.success}")
print(f"耗时: {result.total_time_ms}ms")
print(f"降级触发: {result.fallback_triggered}")
```

### 6.2 参数调整建议 — API调用

```bash
curl -X POST http://localhost:8765/api/v1/wear/suggest \
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

### 6.3 工艺基线查询 — API调用

```python
from app.services.tool_wear_predictor import ToolWearPredictor

predictor = ToolWearPredictor()
baseline = predictor.get_process_baseline(process="finishing", machine="M01")
print(baseline)
```

---

## 七、输出格式完整示例

### 7.1 工作流执行结果

```json
{
  "workflow_id": "wf_20260510120000_1234",
  "success": true,
  "output": {
    "result": {
      "prediction": [155.0, 0.22, 1.6, 950.0],
      "confidence": 0.92,
      "metadata": {
        "model_used": "CFC-Fast",
        "optimization_target": "minimize_time",
        "constraints_met": true
      }
    },
    "context": {
      "preprocessed_data": {...},
      "inference_result": {...},
      "final_result": {...}
    }
  },
  "total_time_ms": 85.3,
  "steps_result": [
    {"name": "preprocess", "status": "completed", "execution_time_ms": 5.2, "error": null},
    {"name": "lnn_inference", "status": "completed", "execution_time_ms": 75.1, "error": null},
    {"name": "postprocess", "status": "completed", "execution_time_ms": 5.0, "error": null}
  ],
  "fallback_triggered": false,
  "fallback_reason": "",
  "metadata": {
    "routing_decision": {
      "selected_model": "CFC-Fast",
      "selected_engine": "LNN",
      "confidence": 0.92,
      "reasoning": "Regression task, fast inference required"
    },
    "engine_stats": {
      "total_inferences": 1523,
      "lnn_requests": 1200,
      "rule_requests": 323,
      "llm_requests": 0,
      "avg_confidence": 0.88
    }
  },
  "timestamp": 1715328000.0
}
```

### 7.2 优化评估报告

```json
{
  "optimization_summary": {
    "original_params": {
      "cutting_speed": 150.0,
      "feed_rate": 0.2,
      "depth_of_cut": 1.5
    },
    "optimized_params": {
      "cutting_speed": 165.0,
      "feed_rate": 0.22,
      "depth_of_cut": 1.6
    },
    "improvements": {
      "machining_time_reduction": "8.5%",
      "tool_life_extension": "12.3%",
      "energy_savings": "5.2%"
    },
    "constraints_check": {
      "surface_roughness": {"value": 2.8, "limit": 3.2, "passed": true},
      "cutting_force": {"value": 1850.0, "limit": 3000.0, "passed": true},
      "vibration_rms": {"value": 0.18, "limit": 0.50, "passed": true}
    },
    "evaluation_metrics": {
      "MSE": 0.0234,
      "MAE": 0.0891,
      "R2": 0.9542,
      "process_pass_rate": 0.978
    }
  }
}
```

### 7.3 编排器统计信息

```python
stats = orchestrator.get_statistics()
# 返回示例：
{
    "total_workflows": 150,
    "successful_workflows": 142,
    "failed_workflows": 8,
    "fallback_count": 12,
    "success_rate": 0.9467,
    "avg_execution_time_ms": 92.5,
    "engine_stats": {
        "total_inferences": 1523,
        "lnn_requests": 1200,
        "rule_requests": 323,
        "llm_requests": 0,
        "avg_confidence": 0.88,
    }
}
```

---

## 八、FAQ

**Q1: HybridLNN模型何时被选择？**
A: 当任务涉及多模态输入（同时需要处理图像和结构化数据）或多任务预测时，路由决策会自动选择HybridLNN模型。模型类型匹配基于模型名称中的关键词（"hybrid"或"Hybrid"）。

**Q2: 如何配置多目标优化的权重？**
A: 通过工作流编排器的配置管理器设置。在YAML配置文件中定义各目标权重，或在execute_workflow()的input_data中传入weight参数。推荐根据生产场景选择预设权重策略（批量生产/精密加工/绿色制造/均衡模式）。

**Q3: 工作流降级到什么情况下会触发？**
A: 以下情况触发降级：1) LNN模型不可用（未注册或未加载）；2) 推理置信度低于fallback_threshold（默认0.50）；3) 推理步骤执行超时；4) 推理步骤抛出异常。降级策略可通过set_fallback_strategy()方法切换。

**Q4: 工艺合格率如何计算？**
A: 合格率 = 满足所有工艺约束的样本数 / 总样本数。约束包括表面粗糙度（Ra <= 3.2um）、切削力（不超过机床功率限制）、振动幅值（在基线范围内）。可通过evaluate_process()方法批量评估。

**Q5: R²值为负意味着什么？**
A: R² < 0表示模型预测效果比简单使用均值预测还要差。这通常说明：1) 模型未正确训练；2) 输入特征与目标变量相关性极低；3) 数据存在严重噪声或异常值。需要重新检查数据和模型训练流程。

**Q6: 如何在运行时更新工作流配置？**
A: 调用 `orchestrator.update_config(section, key, value)` 动态更新配置。例如：`update_config("workflow", "enable_fallback", False)` 禁用降级机制。更新后可调用 `save_config()` 持久化到文件。

**Q7: 工艺基线数据从哪来？**
A: 工艺基线数据通过 `get_process_baseline(process, machine)` 从Bosch CNC数据集中获取，包含RMS范围、主频范围、能量分布等统计信息。这些数据来自"good"标签的正常加工样本。

**Q8: 工作流执行日志存储在哪里？**
A: 日志默认存储在 `logs/workflows/` 目录下，按日期生成JSONL文件（如 `workflow_2026-05-10.jsonl`）。每条记录包含工作流ID、执行结果、各步骤状态、耗时等信息。可通过 `get_workflow_history(limit)` 查询历史记录。
