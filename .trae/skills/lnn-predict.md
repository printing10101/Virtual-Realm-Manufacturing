# LNN切削参数预测技能 (LNN Predict Skill)

## 元数据

| 字段 | 值 |
|------|-----|
| 技能名称 | LNN切削参数预测 |
| 英文名称 | LNN Predict |
| 适用场景 | 切削加工参数预测（切削速度v、进给量f、背吃刀量ap、主轴转速n）、切削力预测、刀具磨损预测、表面粗糙度预测 |
| 前置条件 | 1. FastAPI服务已启动（python/app/main.py）；2. 模型已在注册表中注册（LNNModelRegistry）；3. PyTorch已安装（torch >= 1.10） |
| API端点 | POST /api/v1/lnn/predict |
| 依赖模块 | predictor.py, registry.py, cfc_model.py, ltc_model.py, hybrid_lnn.py, parameter_models.py |

---

## 一、支持的模型类型

### 1.1 模型类型总览

| 模型类型 | 类名 | 特点 | 适用任务 | 目标延迟 |
|---------|------|------|---------|---------|
| CFC | CFCModel | 基于无上下文文法网络，优化快速推理场景，响应时间 < 100ms | 切削参数预测、快速分类、模式识别 | < 100ms |
| LTC | LTCModel | 液体时间常数网络，支持序列长度 > 1000，含记忆机制 | 刀具磨损时序预测、趋势分析 | 依赖序列长度 |
| HybridLNN | HybridLNNModel | CNN + LNN融合，支持多模态输入（图像+结构化数据） | 复杂工艺规划、多任务预测 | 依赖输入规模 |

### 1.2 CFC模型特性

- 网络结构：多层全连接网络，使用He初始化（std = sqrt(2/(fan_in+1e-8))）
- 激活函数：ReLU（隐藏层）、线性（输出层）、Softmax（可选分类任务）
- Dropout率：默认0.1
- 支持torch转换：`to_torch()` 方法可转为PyTorch模型

### 1.3 LTC模型特性

- 网络结构：时序处理网络，含记忆单元（memory_size默认512）
- 时间视野（temporal_horizon）：默认1000
- 记忆更新机制：指数衰减（0.9 * old_memory + 0.1 * new_memory）
- 支持多步时序预测：`predict_sequence(x, future_steps)`
- 激活函数：ReLU
- 支持torch转换：`to_torch()` 方法可转为PyTorch模型

### 1.4 HybridLNN模型特性

- CNN层：默认3层卷积（filters=[32,64,128], kernel_sizes=[3,3,3]），含BatchNorm和MaxPool
- LNN层：全连接层，使用Xavier初始化（limit = sqrt(6/(fan_in+fan_out))）
- 融合方式：concat（默认）、add、attention
- 支持多模态预测：`predict_multimodal(structured_data, image_data)`

---

## 二、输入参数规范

### 2.1 API请求参数

```json
{
  "input_data": [float, ...],
  "model_name": "string",
  "return_confidence": false
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| input_data | list[float] | 是 | 预测输入数据数组，维度需与模型input_features数量匹配 |
| model_name | string | 是 | 模型名称，如 "cutting_force"、"wear_prediction"、"surface_roughness" |
| return_confidence | bool | 否 | 是否返回置信度，默认false |

### 2.2 切削参数约束

| 参数 | 数据类型 | 取值范围 | 单位 | 说明 |
|------|---------|---------|------|------|
| cutting_speed | float | [50, 500] | m/min | 切削速度，必须在有效区间内 |
| feed_rate | float | [0.05, 1.0] | mm/r | 进给量，超出范围可能导致模型预测不准确 |
| depth_of_cut | float | > 0 | mm | 背吃刀量 |
| spindle_speed | float | > 0 | r/min | 主轴转速 |

### 2.3 已注册模型输入特征

| 模型名称 | 模型类型 | 输入特征 | 输出特征 |
|---------|---------|---------|---------|
| cutting_force | CFC | force_x, force_y, force_z, spindle_speed, feed_rate | predicted_cutting_force |
| wear_prediction | LTC | vb, time, spindle_speed, feed_rate, depth_of_cut | predicted_wear |
| surface_roughness | HybridLNN | roughness_ra, cutting_speed, feed_rate, tool_wear | predicted_surface_roughness |
| temperature | CFC | temp_zone1, temp_zone2, coolant_flow, cutting_time | predicted_temperature |

### 2.4 支持的输入数据类型

```python
# predictor.py 支持的输入类型
# - numpy.ndarray：直接作为输入
# - dict：自动提取数值特征（DataPreprocessor.extract_numeric_features）
# - list/tuple：转换为numpy数组
# - torch.Tensor：detach后转为numpy
# - int/float：包装为单元素数组
```

---

## 三、输出结果规范

### 3.1 API响应格式

```json
{
  "code": 0,
  "data": {
    "value": [float, ...],
    "confidence": 0.92,
    "inference_time": 12.5,
    "model_info": {
      "name": "cutting_force",
      "version": "1.0.0",
      "last_updated": "2026-05-10T12:00:00"
    }
  },
  "message": "Prediction completed successfully"
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| value | float/list[float] | 预测结果值，单元素数组自动展开为标量 |
| confidence | float | 预测置信度（0-1），仅当return_confidence=true时返回 |
| inference_time | float | 推理耗时，单位毫秒 |
| model_info.name | string | 模型名称 |
| model_info.version | string | 模型版本 |
| model_info.last_updated | string | 最后更新时间（ISO 8601格式） |

### 3.2 置信度计算体系

```python
# predictor.py 中的置信度计算逻辑
def _compute_confidence(self, output) -> float:
    if isinstance(output, torch.Tensor):
        if output.dim() == 0:
            return 0.9  # 标量输出固定置信度
        probs = torch.softmax(output, dim=-1) if output.dim() > 1 else output
        max_prob = probs.max().item()
        return min(max(max_prob, 0.0), 1.0)
    return 0.9  # 非Tensor输出默认置信度
```

| 场景 | 置信度计算方式 | 典型值范围 |
|------|--------------|-----------|
| 标量输出 | 固定值 | 0.9 |
| 分类输出 | softmax最大概率 | 0.5-0.99 |
| 回归输出 | 固定值 | 0.9 |

---

## 四、模型选择与路由

### 4.1 自动匹配算法

模型选择由 `HybridInferenceEngine` 的 `TaskRouter` 负责：

```python
# core.py 中的路由逻辑
# 任务类别推断基于关键词匹配：
# - 时序预测关键词：["predict", "forecast", "trend", "时间序列", "预测"]
# - 规则验证关键词：["rule", "check", "validate", "规则", "验证", "检查"]
# - NLP关键词：["explain", "summarize", "翻译", "解释", "分析"]
# - 默认归类为回归任务
```

| 任务类别 | 对应模型 | 触发条件 |
|---------|---------|---------|
| TIME_SERIES | LTC | 描述含预测、趋势等时序关键词 |
| REGRESSION | CFC | 默认任务类型 |
| RULE_BASED | Rule Engine | 描述含验证、检查等关键词 |
| NLP | LLM | 描述含解释、分析等关键词 |

### 4.2 模型切换触发条件

- **LNN不可用**：自动降级到规则引擎（FallbackStrategy.RULE_ENGINE）
- **置信度过低**：当 confidence < fallback_threshold（默认0.50）时触发降级
- **超时**：步骤执行超过 timeout_ms 时触发降级
- **模型未加载**：自动从注册表加载，加载失败时降级

### 4.3 特征重要性评估

LTC模型通过 `predict_sequence` 评估时序特征重要性：
- 使用注意力机制聚合时序状态（可替换为加权平均）
- 多步预测时观察预测值随时间步的变化趋势
- 特征重要性通过 `feature_importances_` 属性获取（需ML模型训练）

---

## 五、约束校验

### 5.1 切削功率计算

```
P = F_c * v_c / 60000 （kW）
```

其中：
- F_c：切削力（N）
- v_c：切削速度（m/min）

### 5.2 安全阈值

| 约束项 | 安全阈值 | 校验方式 |
|--------|---------|---------|
| 切削速度 | [50, 500] m/min | Pydantic field_validator |
| 进给量 | [0.05, 1.0] mm/r | Pydantic field_validator |
| 表面粗糙度（标准） | Ra <= 3.2 um | 工艺规范要求 |
| 表面粗糙度（精密） | Ra <= 1.6 um | 工艺规范要求 |

### 5.3 输入维度校验

```python
# API端点中的维度校验
expected_dim = len(model_info.input_features)
input_len = len(request.input_data)
if input_len != expected_dim and input_len % expected_dim != 0:
    raise ValueError(f"输入维度不匹配: 期望{expected_dim}维或其倍数，实际{input_len}维")
```

---

## 六、调用示例

### 6.1 cURL请求示例

```bash
# 基础预测请求
curl -X POST http://localhost:8765/api/v1/lnn/predict \
  -H "Content-Type: application/json" \
  -d '{
    "input_data": [120.0, 0.2, 1.5, 800.0],
    "model_name": "cutting_force",
    "return_confidence": true
  }'

# 批量预测（多行数据拼接为单维度数组）
curl -X POST http://localhost:8765/api/v1/lnn/predict \
  -H "Content-Type: application/json" \
  -d '{
    "input_data": [120.0, 0.2, 1.5, 800.0, 150.0, 0.3, 2.0, 1000.0],
    "model_name": "cutting_force",
    "return_confidence": false
  }'
```

### 6.2 Python代码示例

```python
from app.ai.lnn.inference.predictor import LNNPredictor
from app.ai.lnn.inference.registry import LNNModelRegistry

# 从注册表创建预测器
registry = LNNModelRegistry()
predictor = LNNPredictor.from_registry(
    registry=registry,
    model_name="cutting_force",
    use_amp=True,
    auto_device=True,
)

# 单样本预测
result = predictor.predict(
    input_data=[120.0, 0.2, 1.5, 800.0],
    return_confidence=True,
)
print(f"预测值: {result.value}, 置信度: {result.confidence}, 耗时: {result.inference_time}ms")

# 批量预测
results = predictor.predict_batch(
    batch_data=[[120.0, 0.2, 1.5], [150.0, 0.3, 2.0]],
    batch_size=32,
)

# 流式预测
data_stream = [[120.0, 0.2], [130.0, 0.25], [140.0, 0.3]]
for result in predictor.predict_streaming(data_stream, return_confidence=True):
    print(result.to_dict())
```

---

## 七、输出格式完整示例

### 7.1 成功响应示例

```json
{
  "code": 0,
  "data": {
    "value": 245.67,
    "confidence": 0.92,
    "inference_time": 8.3,
    "model_info": {
      "name": "cutting_force",
      "version": "1.0.0",
      "last_updated": "2026-05-10T12:00:00"
    }
  },
  "message": "Prediction completed successfully"
}
```

### 7.2 错误响应示例

```json
{
  "code": 40401,
  "data": null,
  "message": "Model 'unknown_model' not found in registry"
}
```

### 7.3 预测器统计信息

```python
stats = predictor.get_statistics()
# 返回示例：
{
    "total_inferences": 1000,
    "total_inference_time_ms": 8500.0,
    "average_inference_time_ms": 8.5,
    "max_inference_time_ms": 25.3,
    "min_inference_time_ms": 2.1,
    "peak_memory_mb": 256.5,
    "current_memory_mb": 128.3,
}
```

---

## 八、FAQ

**Q1: 输入数据维度不匹配怎么办？**
A: 检查模型的 `input_features` 数量，确保 `len(input_data)` 等于该数量或是其整数倍（支持批量输入）。调用 `GET /api/v1/lnn/models/{model_name}/info` 查看模型的输入维度要求。

**Q2: 如何在CPU和GPU之间切换？**
A: `LNNPredictor` 默认启用自动设备选择（`auto_device=True`），会自动选择GPU（CUDA）> MPS > CPU。也可在初始化时指定 `device` 参数强制使用特定设备。

**Q3: 为什么置信度返回为0.0？**
A: 需要在请求中设置 `return_confidence: true`。默认情况下，API不会返回置信度以节省响应体大小。

**Q4: 量化模型（_int8后缀）能否用于预测？**
A: 可以。量化模型通过 `get_quantized_model_name(base_name)` 自动注册到注册表中，使用方式与基础模型完全相同。量化模型推理速度更快，但精度略有下降。

**Q5: 预测失败时如何排查？**
A: 检查以下几点：1) 模型是否已正确注册（`GET /api/v1/lnn/models`）；2) 模型文件是否存在且完整（`POST /api/v1/lnn/models/{name}/validate`）；3) 输入数据维度是否匹配；4) GPU显存是否充足（`GET /api/v1/lnn/device/status`）。

**Q6: 如何获取推理性能统计？**
A: 调用 `predictor.get_statistics()` 获取总推理次数、平均耗时、最大/最小耗时、峰值内存等信息。API暂不提供此统计的独立端点。

**Q7: CFC、LTC、HybridLNN三种模型如何选择？**
A: - CFC：适用于快速推理场景（<100ms），如实时切削参数预测
       - LTC：适用于时序预测，支持长序列（>1000），如刀具磨损趋势分析
       - HybridLNN：适用于多模态输入场景，需要同时处理图像和结构化数据
