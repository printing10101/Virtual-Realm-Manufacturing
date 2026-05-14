---
skill_id: lnn_train
name: LNN 模型训练
version: 1.0.0
applicable_tasks: ["training", "lnn_training", "model_export"]
required_context: ["dataset", "model_config"]
tags: ["lnn", "training", "model", "deep_learning"]
---

# LNN 模型训练技能

## 适用场景
当需要训练新的液态神经网络模型或微调现有模型时使用此技能。

## 输入参数
- dataset: 训练数据集配置
  - path: 数据文件路径
  - format: 数据格式（"csv" | "json" | "parquet"）
  - features: 特征列名列表
  - targets: 目标列名列表
- model_config: 模型配置
  - model_type: 模型类型（"CFC" | "LTC" | "HybridLNN"）
  - hidden_size: 隐藏层大小（默认64）
  - num_layers: 网络层数（默认3）
  - liquid_ode_solver: ODE求解器（"dopri5" | "euler" | "rk4"）
  - mixed_precision: 是否使用混合精度训练（默认true）
- training_config: 训练配置
  - epochs: 训练轮数（默认100）
  - batch_size: 批量大小（默认32）
  - learning_rate: 学习率（默认0.001）
  - optimizer: 优化器（"adam" | "adamw" | "sgd"）
  - early_stopping_patience: 早停耐心值（默认10）
  - validation_split: 验证集比例（默认0.2）

## 训练流程
1. 验证数据集完整性和格式
2. 数据预处理（归一化、缺失值填充、异常值检测）
3. 构建LNN模型架构
4. 配置训练超参数和优化器
5. 启动训练循环，实时记录损失和指标
6. 每个epoch后执行验证评估
7. 早停检查
8. 保存最佳模型和训练日志

## 输出格式
```json
{
  "training_id": "train_20260513_001",
  "status": "completed",
  "metrics": {
    "final_train_loss": 0.023,
    "final_val_loss": 0.031,
    "best_val_loss": 0.028,
    "mae": 0.015,
    "r2_score": 0.94
  },
  "model_path": "models/lnn_cfc_v2.pt",
  "epochs_completed": 87,
  "early_stopped": true,
  "training_time_seconds": 342.5,
  "gpu_memory_peak_mb": 1240
}
```

## 常见错误处理
- 如果数据集路径不存在，返回错误并提示检查路径
- 如果数据格式不支持，返回错误并列出支持格式
- 如果GPU内存不足，自动切换到混合精度或CPU训练
- 如果训练损失不收敛，返回诊断建议（调整学习率、检查数据分布）
- 如果模型过大导致OOM，自动减少hidden_size或batch_size
