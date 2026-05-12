# LNN模型训练技能 (LNN Train Skill)

## 元数据

| 字段 | 值 |
|------|-----|
| 技能名称 | LNN模型训练 |
| 英文名称 | LNN Train |
| 适用场景 | LNN模型训练（CFC/LTC/HybridLNN）、模型微调、检查点恢复、混合精度训练、GPU加速训练 |
| 前置条件 | 1. PyTorch已安装（torch >= 1.10）；2. CUDA驱动已安装（GPU训练）；3. 训练数据已准备（CSV/TXT/DAT格式） |
| API端点 | POST /api/v1/lnn/train, GET /api/v1/lnn/train/{task_id}/stream |
| 依赖模块 | trainer.py, device_manager.py, dataset.py, dataset_cache.py, evaluator.py, torch_cfc_model.py, torch_ltc_model.py, torch_hybrid_lnn.py |

---

## 一、数据规范

### 1.1 支持的数据集格式

| 格式 | 文件扩展名 | 最大文件大小 | 加载方式 | 用途 |
|------|-----------|------------|---------|------|
| CSV | .csv | 100 MB | np.loadtxt(delimiter=",") | 训练数据，最后一列作为标签 |
| TXT | .txt | 100 MB | np.loadtxt(delimiter=",") | 文本格式训练数据 |
| DAT | .dat | 100 MB | np.loadtxt(delimiter=",") | 二进制文本格式训练数据 |

### 1.2 数据结构要求

训练数据必须为二维数值矩阵，格式为：
```
X_1, X_2, ..., X_n, y
```
其中前n列为输入特征，最后一列为目标标签。

```python
# API端点中的数据加载逻辑
data = np.loadtxt(data_path, delimiter=",")
if data.ndim == 1:
    data = data.reshape(-1, 1)
if data.shape[0] < 2:
    raise ValueError("Need at least 2 samples for train/val split")
if not np.isfinite(data).all():
    raise ValueError("Data contains NaN or Inf values")

X = data[:, :-1]  # 输入特征
y = data[:, -1]   # 目标标签
```

### 1.3 格式优缺点对比

| 格式 | 优点 | 缺点 | 适用场景 |
|------|------|------|---------|
| CSV | 人类可读，编辑方便，兼容性好 | 大文件加载较慢 | 小规模数据集、快速验证 |
| TXT | 灵活，可自定义分隔符 | 需要知道分隔符格式 | 特殊格式数据 |
| DAT | 可存储预处理后的二进制数据 | 不便于人工查看 | 大规模数据集、重复训练 |

### 1.4 HDF5数据集（内部训练）

```python
# dataset.py 中使用 h5py 管理 HDF5 数据集
import h5py

# HDF5 结构：
# /features    (N, input_dim)   输入特征
# /labels      (N,)             目标标签
# /metadata    (Group)          数据集元数据
#   /source    (String)         数据来源
#   /created   (String)         创建时间
```

### 1.5 数据导入错误处理机制

| 错误类型 | 触发条件 | 错误码 | 处理建议 |
|---------|---------|--------|---------|
| DATA_NOT_FOUND | 文件路径不存在 | - | 检查路径是否正确，确认文件存在 |
| INVALID_FILE | 路径指向非文件对象 | - | 确认路径指向文件而非目录 |
| PATH_NOT_ALLOWED | 文件路径在允许目录外 | - | 数据文件必须在配置的storage.output_dir内 |
| UNSUPPORTED_FILE_TYPE | 非.csv/.txt/.dat文件 | - | 转换数据格式为支持类型 |
| FILE_TOO_LARGE | 文件 > 100MB | - | 拆分数据集或优化数据格式 |
| EMPTY_DATA | 数据文件为空 | - | 检查数据文件内容 |
| INSUFFICIENT_DATA | 样本数 < 2 | - | 增加数据样本量 |
| INVALID_DATA_VALUES | 包含NaN或Inf | - | 清理数据中的异常值 |

---

## 二、数据预处理

### 2.1 缺失值处理

```python
# 训练数据加载时的处理流程
# 1. 检查数据中是否存在NaN/Inf值
if not np.isfinite(data).all():
    raise ValueError("Data contains NaN or Inf values")

# 2. 推荐的数据清理方式
import numpy as np
data = np.loadtxt(data_path, delimiter=",")
data = np.nan_to_num(data, nan=0.0, posinf=1e10, neginf=-1e10)  # 替换异常值
```

### 2.2 异常值检测与修正流程

```python
# 基于Z-score的异常值检测
def detect_outliers(data, threshold=3.0):
    """检测并返回异常值索引"""
    mean = np.mean(data, axis=0)
    std = np.std(data, axis=0)
    z_scores = np.abs((data - mean) / (std + 1e-8))
    return np.where(z_scores > threshold)

# 异常值修正策略
# 1. 删除：异常值比例 < 5% 时删除对应行
# 2. 截断：将超出阈值的数据截断到阈值边界
# 3. 替换：使用中位数或均值替换
```

### 2.3 特征标准化/归一化

```python
# 训练管道中使用StandardScaler进行标准化
from sklearn.preprocessing import StandardScaler

scaler = StandardScaler()
X_train_scaled = scaler.fit_transform(X_train)
X_test_scaled = scaler.transform(X_test)
```

| 方法 | 公式 | 适用场景 |
|------|------|---------|
| StandardScaler | z = (x - μ) / σ | 特征服从正态分布 |
| MinMaxScaler | x' = (x - min) / (max - min) | 特征范围已知且有界 |
| RobustScaler | x' = (x - median) / IQR | 特征含较多异常值 |

### 2.4 数据平衡策略

```python
# 数据划分：80/20 训练/验证集
from sklearn.model_selection import train_test_split

X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42
)
```

| 策略 | 说明 | 适用场景 |
|------|------|---------|
| Random Split | 随机划分80/20 | 数据集分布均匀 |
| Stratified Split | 分层抽样，保持类别比例 | 类别不平衡数据集 |
| Cross Validation | K折交叉验证 | 小样本数据集 |

---

## 三、训练参数配置

### 3.1 学习率配置

| 参数 | 推荐范围 | 默认值 | 调整策略 |
|------|---------|--------|---------|
| learning_rate | 0.0001 - 0.1 | 0.001 | 初始使用0.001，loss不下降时降低10倍 |

```python
# LNNHyperparameters 校验规则
# learning_rate: gt=0, lt=1 (必须在0到1之间)
```

### 3.2 Batch Size选择

| 硬件条件 | 推荐batch_size | 说明 |
|---------|---------------|------|
| CPU训练 | 32 | 默认值，内存占用较小 |
| GPU训练（< 8GB VRAM） | 32-64 | 根据GPU内存动态调整 |
| GPU训练（>= 8GB VRAM） | 64-256 | 利用更大batch加速训练 |
| GPU训练（>= 16GB VRAM） | 256-512 | 充分利用GPU并行能力 |

```python
# 自动优化batch size（GPU模式）
if device.type == "cuda":
    batch_size = get_optimal_batch_size(device, batch_size)
```

### 3.3 Epoch数设置

| 参数 | 推荐范围 | 默认值 | 说明 |
|------|---------|--------|------|
| epochs | 10 - 500 | 100 | 配合早停机制使用，避免过拟合 |
| early_stopping_patience | 3 - 20 | 5 | 验证loss连续N轮不下降则停止 |

```python
# early_stopping_patience 工作原理
if val_loss < self.best_val_loss:
    self.best_val_loss = val_loss
    self.patience_counter = 0
    self.best_model_state = self._save_model_state()
else:
    self.patience_counter += 1
    if self.patience_counter >= self.early_stopping_patience:
        logger.info("Early stopping at epoch %s", epoch + 1)
        break
```

### 3.4 优化器适用场景对比

| 优化器 | 类名 | 特点 | 适用场景 | 默认参数 |
|--------|------|------|---------|---------|
| Adam | torch.optim.Adam | 自适应学习率，收敛快 | 通用场景，推荐首选 | lr=0.001 |
| AdamW | torch.optim.AdamW | Adam + 权重衰减 | 需要正则化时 | lr=0.001 |
| SGD | torch.optim.SGD | 经典优化器，可控性强 | 需要精细调参时 | lr=0.001, momentum=0.9 |
| RMSprop | torch.optim.RMSprop | 适合RNN/时序模型 | 时序预测任务 | lr=0.001 |

```python
# _create_optimizer() 实现
if optimizer_type == "adam":
    return torch.optim.Adam(self.model.parameters(), lr=self.learning_rate)
elif optimizer_type == "adamw":
    return torch.optim.AdamW(self.model.parameters(), lr=self.learning_rate)
elif optimizer_type == "sgd":
    return torch.optim.SGD(self.model.parameters(), lr=self.learning_rate, momentum=0.9)
elif optimizer_type == "rmsprop":
    return torch.optim.RMSprop(self.model.parameters(), lr=self.learning_rate)
```

### 3.5 损失函数选择

| 损失函数 | 类型 | 适用任务 | 说明 |
|---------|------|---------|------|
| cross_entropy | nn.CrossEntropyLoss | 多分类任务 | 含softmax，适用于分类 |
| bce_with_logits | nn.BCEWithLogitsLoss | 二分类任务 | 含sigmoid，数值稳定性好 |
| bce | nn.BCELoss | 二分类任务 | 输入需预先经过sigmoid |
| mse | nn.MSELoss | 回归任务 | 均方误差，对异常值敏感 |
| mae | nn.L1Loss | 回归任务 | 平均绝对误差，对异常值鲁棒 |

### 3.6 学习率调度器

| 调度器 | 类型 | 参数 | 适用场景 |
|--------|------|------|---------|
| StepLR | step | step_size=30, gamma=0.1 | 固定步长衰减 |
| CosineAnnealingLR | cosine | T_max=epochs, eta_min=0 | 平滑衰减，推荐首选 |
| ReduceLROnPlateau | reduce_on_plateau | mode=min, factor=0.1, patience=10 | 根据验证loss自适应调整 |
| ExponentialLR | exponential | gamma=0.95 | 指数衰减 |

---

## 四、训练监控

### 4.1 Loss曲线绘制标准

```python
# 训练历史记录结构
self.training_history: Dict[str, List[float]] = {
    "train_loss": [],          # 每轮训练损失
    "val_loss": [],            # 每轮验证损失
    "train_accuracy": [],      # 每轮训练准确率
    "val_accuracy": [],        # 每轮验证准确率
    "learning_rate": [],       # 每轮学习率
}
```

绘制标准：
- X轴：Epoch数
- Y轴：Loss值（对数刻度，范围1e-4到1e2）
- 训练集和验证集loss用不同颜色区分
- 标注早停触发点（如有）

### 4.2 验证集评估指标

```python
# 训练完成后的验证评估
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score

# MSE (Mean Squared Error)
MSE = mean((y_true - y_pred) ** 2)

# MAE (Mean Absolute Error)
MAE = mean(|y_true - y_pred|)

# R² (R-squared)
SS_res = sum((y_true - y_pred) ** 2)
SS_tot = sum((y_true - mean(y_true)) ** 2)
R² = 1 - SS_res / SS_tot
```

| 指标 | 计算方式 | 理想值 | 说明 |
|------|---------|--------|------|
| MSE | mean((y_true - y_pred)²) | 接近0 | 对异常值敏感 |
| MAE | mean(\|y_true - y_pred\|) | 接近0 | 对异常值鲁棒 |
| R² | 1 - SS_res/SS_tot | 接近1 | 解释方差比例 |
| Accuracy | correct_predictions / total | 接近1 | 分类任务准确率 |

### 4.3 早停机制

```python
# 早停配置
early_stopping_patience = 5     # 默认耐心值
gradient_clip_value = 1.0       # 默认梯度裁剪阈值
```

早停触发条件：
1. 验证loss连续 `early_stopping_patience` 轮未下降
2. 触发时自动恢复最佳模型状态（best_model_state）
3. 训练日志中记录 "Early stopping at epoch N"

### 4.4 GPU内存监控

```python
# 训练期间GPU内存监控（每10轮检查一次）
if device.type == "cuda" and epoch % 10 == 0:
    mem_used_mb = torch.cuda.memory_allocated(gpu_index) / (1024 ** 2)
    mem_reserved_mb = torch.cuda.memory_reserved(gpu_index) / (1024 ** 2)

# 内存过高时自动清理
if device.type == "cuda" and not check_gpu_memory_safe(threshold_percent=95.0):
    clear_gpu_memory(device)
```

---

## 五、训练流程

### 5.1 完整训练步骤

1. **准备数据文件**：将训练数据保存为CSV/TXT/DAT格式，确保无NaN/Inf值
2. **注册模型**：模型需已在LNNModelRegistry中注册
3. **发起训练请求**：POST /api/v1/lnn/train
4. **监控训练进度**：SSE实时流（GET /api/v1/lnn/train/{task_id}/stream）
5. **查看训练结果**：GET /api/v1/lnn/tasks
6. **保存检查点**：trainer.save_checkpoint(path)

### 5.2 检查点管理

```python
# 检查点保存
checkpoint = {
    "epoch": current_epoch,
    "best_val_loss": best_val_loss,
    "model_state_dict": model.state_dict(),
    "optimizer_state_dict": optimizer.state_dict(),
    "training_history": training_history,
    "model_config": {
        "optimizer_type": "adam",
        "loss_type": "mse",
        "learning_rate": 0.001,
        "gradient_clip_value": 1.0,
        "lr_scheduler_type": "step",
    },
    "metrics": metrics,
    "timestamp": "2026-05-10T12:00:00",
    "device": "cuda",
    "use_amp": True,
    "scaler_state_dict": scaler_state_dict,  # 仅AMP模式下
}
torch.save(checkpoint, path)

# 检查点加载
trainer.load_checkpoint(path)
```

### 5.3 TorchScript导出

```python
# 导出为TorchScript格式（用于生产部署）
save_path = trainer.export_torchscript(
    save_path="models/cutting_force_v1.torchscript.pt",
    example_input=torch.randn(1, model.input_dim, device=device)
)
```

### 5.4 混合精度训练（AMP）

```python
# AMP自动启用条件
use_amp = device.type == "cuda" and torch.cuda.is_available()

# AMP训练循环
if self.use_amp and self.scaler is not None:
    with torch.cuda.amp.autocast():
        outputs = self.model(batch_X)
        loss = self.criterion(outputs, batch_y)
    self.scaler.scale(loss).backward()
    self.scaler.step(self.optimizer)
    self.scaler.update()
```

---

## 六、API调用示例

### 6.1 发起训练请求

```bash
curl -X POST http://localhost:8000/api/v1/lnn/train \
  -H "Content-Type: application/json" \
  -d '{
    "model_name": "cutting_force",
    "data_path": "output/data/cutting_force_train.csv",
    "hyperparameters": {
      "learning_rate": 0.001,
      "epochs": 100,
      "batch_size": 32,
      "optimizer": "adam"
    },
    "device": "auto"
  }'
```

### 6.2 训练响应示例

```json
{
  "code": 0,
  "data": {
    "status": "in_progress",
    "message": "Training task started"
  },
  "message": "Training task started"
}
```

### 6.3 训练完成响应

```json
{
  "code": 0,
  "data": {
    "status": "success",
    "message": "Training completed successfully",
    "metrics": {
      "r2_score": 0.9542,
      "loss": 0.0234,
      "training_time": 45.67,
      "epochs_completed": 85
    }
  },
  "message": "Training completed successfully"
}
```

### 6.4 SSE实时进度流

```
event: progress
data: {"epoch": 45, "loss": 0.0312, "metrics": {"train_accuracy": 0.9234, "val_accuracy": 0.9012, "train_loss": 0.0298, "val_loss": 0.0312}}

event: progress
data: {"epoch": 46, "loss": 0.0298, "metrics": {"train_accuracy": 0.9256, "val_accuracy": 0.9034, "train_loss": 0.0285, "val_loss": 0.0298}}

event: complete
data: {"status": "completed", "final_loss": 0.0234, "total_time": 45.67}
```

---

## 七、输出格式完整示例

### 7.1 训练摘要

```python
summary = trainer.get_training_summary()
# 返回示例：
{
    "total_epochs": 85,
    "best_val_loss": 0.0234,
    "final_train_loss": 0.0212,
    "final_val_loss": 0.0234,
    "final_train_accuracy": 0.9312,
    "final_val_accuracy": 0.9089,
    "optimizer": "adam",
    "loss_function": "mse",
    "device": "cuda:0",
    "use_amp": True,
    "gpu_name": "NVIDIA RTX 4090",
    "gpu_max_memory_mb": 1024.56,
}
```

### 7.2 设备信息

```bash
curl http://localhost:8000/api/v1/lnn/device/info
```

```json
{
  "code": 0,
  "data": {
    "current_device": {
      "type": "cuda",
      "index": 0,
      "name": "NVIDIA GeForce RTX 4090",
      "total_memory_mb": 24576,
      "available_memory_mb": 20480,
      "cuda_version": "12.1",
      "compute_capability": "8.9",
      "gpu_count": 1
    },
    "available_devices": [...],
    "torch_cuda_available": true,
    "torch_version": "2.1.0",
    "cuda_version": "12.1",
    "cudnn_version": 8900
  },
  "message": "Device info retrieved successfully"
}
```

---

## 八、FAQ

**Q1: 训练数据需要什么样的格式？**
A: 训练数据必须是CSV/TXT/DAT格式，每行为一个样本，列之间用逗号分隔。最后一列作为目标标签（y），前面的列作为输入特征（X）。例如：`120.0,0.2,1.5,245.67` 表示3个输入特征对应1个目标值。

**Q2: 训练过程中如何取消？**
A: 调用 `POST /api/v1/lnn/train/{task_id}/cancel` 发送取消信号。训练会在当前epoch结束后安全退出，并保存已完成的训练进度。

**Q3: 并发训练任务数有限制吗？**
A: 是的，最大并发训练任务数为3（MAX_CONCURRENT_TRAINING_TASKS = 3）。超过限制的任务会排队等待，在SSE流中会收到等待通知。

**Q4: 如何将训练好的模型部署到生产环境？**
A: 使用 `trainer.export_torchscript()` 导出为TorchScript格式（.pt或.torchscript）。导出的模型可在无Python环境下运行，适合生产部署。

**Q5: 混合精度训练（AMP）何时启用？**
A: AMP仅在GPU（CUDA）环境下自动启用。需要torch.cuda.is_available()为True。CPU环境下AMP不会启用。启用后可显著减少GPU显存占用并加速训练。

**Q6: 训练完成后模型自动注册吗？**
A: 训练API不会自动将训练后的模型注册到推理注册表。需要在训练完成后手动保存检查点，然后加载到推理引擎中。

**Q7: 如何选择优化器？**
A: 推荐优先使用Adam优化器（默认），适用于大多数场景。如果模型出现过拟合，可尝试AdamW（含权重衰减）。对于需要精细控制的场景，可使用SGD + momentum。时序预测任务可尝试RMSprop。

**Q8: 数据文件太大（>100MB）怎么办？**
A: 系统限制单次训练文件最大100MB。可以将数据拆分为多个小文件分批训练，或使用HDF5格式（通过内部dataset.py加载）处理大规模数据。
