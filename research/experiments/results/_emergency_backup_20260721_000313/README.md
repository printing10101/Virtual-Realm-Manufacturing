# 实验紧急备份快照

**备份时间**: 2026-07-21 00:08:35 +08:00
**备份目的**: 保证未来 10 小时内若实验进程异常终止，所有已完成数据可恢复

---

## 1. 实验当前状态

### 实验 1: DL-LNN 消融实验 v4 (PID 8776)

- **脚本**: `research/papers/论文相关/脚本/ablation_experiment.py`
- **启动时间**: 2026-07-19 20:22:11
- **进程状态**: 活跃运行中 (CPU=53905s, 内存=530MB, Responding=True)
- **GPU**: 91% 利用率, 40°C

**进度**: 5/16 配置已完成 (31.25%)
**当前正在跑**: A4_lam0.05 (6/16) - 阶段一
**Checkpoint 最后更新**: 2026-07-20 23:25:02

| # | 配置 | MAE | R² | PCC | MAPE | 耗时 | 状态 |
|---|---|---|---|---|---|---|---|
| 1 | Full | 0.3716 | 0.9966 | 0.8057 | 20.14 | 6.75h | ✅ 完成 |
| 2 | A1 (去 L_phys) | 0.3833 | 0.9963 | 0.8188 | 18.78 | 5.99h | ✅ 完成 |
| 3 | **A2 (去 L_pcc)** | **0.2397** | **0.9983** | **0.9524** | **5.75** | 5.50h | ✅ 完成 (最佳) |
| 4 | A3 (单阶段) | 0.3625 | 0.9967 | 0.8500 | 15.50 | 8.07h | ✅ 完成 |
| 5 | A4_lam0.01 | 0.2469 | 0.9982 | 0.9219 | 8.75 | 18.97h | ✅ 完成 |
| 6 | A4_lam0.05 | - | - | - | - | - | 🔄 阶段一 |
| 7-16 | 其余 10 个 | - | - | - | - | - | ⏳ 待运行 |

**关键发现**:
- A2 (去 L_pcc) 性能最优, 反超 Full → 论文中需讨论 L_pcc 在合成数据上是否冲突
- A4_lam0.01 耗时 19h, 是其他配置的 3 倍 → GPU 与 LOMO 抢占严重

### 实验 2: LOMO 跨材料泛化 (PID 29356)

- **脚本**: `research/papers/论文相关/脚本/lomo_loco_experiment.py`
- **启动时间**: 2026-07-19 20:34:51
- **进程状态**: 活跃运行中 (CPU=52984s, 内存=560MB, Responding=True)

**进度**: 4/5 fold 已完成 (80%)
**当前正在跑**: 304_SS (fold 5)
**Checkpoint 最后更新**: 2026-07-19 23:54:20

⚠️ **警告**: Checkpoint 24+ 小时未更新！可能 fold 5 卡住或在进行超长训练。
进程仍消耗 CPU/GPU, 但无进度信号。

| Fold | 材料 | 硬度 | MAE | R² | PCC | 状态 |
|---|---|---|---|---|---|---|
| 1 | 6061-T6 | 95 | 6.347 | **-0.073** | 0.146 | ❌ 失败 |
| 2 | TC4 | 350 | 1.626 | 0.865 | 0.657 | ✅ OK |
| 3 | HRC52 | 520 | 1.980 | 0.764 | 0.632 | ✅ OK |
| 4 | **45_Steel** | 200 | **0.948** | **0.974** | **0.814** | ✅ 最佳 |
| 5 | 304_SS | 180 | - | - | - | 🔄 运行中 |

**关键发现**:
- 6061-T6 完全失败 (R²<0) → 硬度 95 太低, ks_scale 偏离训练分布
- 45_Steel 最佳 → 硬度 200 是 ks_scale=1.0 的中心点
- **这正是贝叶斯 UQ 论文要解决的问题**: 用不确定性标识 OOD 样本

---

## 2. 备份文件清单

```
_emergency_backup_20260721_000313/
├── README.md                                  (本文件)
├── backup_manifest.json                       (备份元数据)
├── backup_timestamp.txt                       (时间戳)
├── ablation_v4/
│   ├── ablation_v4_20260719_202211.log        (6291 bytes, v4 运行日志)
│   ├── ablation_v4_20260719_202211.err.log    (0 bytes, 无错误)
│   └── ablation_checkpoint_synthetic.json     (4502 bytes, 5 个已完成配置)
├── lomo_loco/
│   ├── lomo_ckpt_DL-LNN_physics_aware.json    (1659 bytes, 4 个已完成 fold)
│   ├── ar02_run_20260716_222924.log           (历史日志)
│   ├── ar02_run_20260717_131655.log
│   ├── ar02_run_20260717_154116.log
│   ├── ar02_run_20260717_223939.log
│   ├── ar02_run_20260718_154203.log
│   ├── ar02_run_20260719_200331.log
│   └── ar02_run_20260719_203451.log           (0 bytes, 当前 run)
└── snapshots/
    ├── process_status.txt                     (进程快照)
    └── experiment_snapshot.json               (完整指标快照)
```

---

## 3. 恢复指南

### 场景 A: 实验正常完成, 无需恢复
直接使用原始路径的 checkpoint 文件:
- v4: `research/papers/论文相关/脚本/results/ablation/ablation_checkpoint_synthetic.json`
- LOMO: `research/papers/论文相关/脚本/results/lomo_loco_ar02_full/lomo_ckpt_DL-LNN_physics_aware.json`

### 场景 B: 实验异常终止, 需要恢复

#### B.1 恢复 v4 消融实验

```powershell
cd "c:\Users\Lenovo\Desktop\灵境制造（上线版）"
# --resume 会自动跳过已完成的 5 个配置, 从 A4_lam0.05 继续
python research/papers/论文相关/脚本/ablation_experiment.py `
    --dataset synthetic `
    --ablations Full A1 A2 A3 A4_lam0.01 A4_lam0.05 A4_lam0.1 A4_lam0.5 A4_lam1.0 A6_fixed0.0 A6_fixed0.25 A6_fixed0.5 A6_fixed0.75 A6_fixed1.0 A7_MLP A7_CNN `
    --stage1_epochs 30 `
    --stage2_epochs 60 `
    --output_dir research\papers\论文相关\脚本\results\ablation `
    --resume
```

#### B.2 恢复 LOMO 实验

⚠️ LOMO 脚本 **可能不支持 --resume** (需检查 `lomo_loco_experiment.py` 是否有该参数)
若不支持, 整个 5-fold 重新开始, 约 12-15h

```powershell
cd "c:\Users\Lenovo\Desktop\灵境制造（上线版）"
python research/papers/论文相关/脚本/lomo_loco_experiment.py `
    --protocol LOMO `
    --models DL-LNN `
    --dataset synthetic_multi `
    --output_dir "research\papers\论文相关\脚本\results\lomo_loco_ar02_full" `
    --physics_aware
```

#### B.3 后续: 贝叶斯 UQ 路线

仅在 v4 全部完成后执行 (需 Full 权重):
```powershell
python research/papers/论文相关/脚本/bayesian_uq/rerun_full_save_weights.py  # ~6h
python research/papers/论文相关/脚本/bayesian_uq/bayesian_uq_experiment.py   # ~30min
```

---

## 4. 重要观察与待办

### 待办优先级

1. **立即检查 LOMO fold 5 是否卡住** (24h 未更新 checkpoint)
   - 建议用 `py-spy dump --pid 29356` 查看 Python 调用栈
   - 若卡住, 终止后用 B.2 流程恢复
   - 若只是日志缓冲问题, 等待即可

2. **持续监控 v4 进度** (每 6h 检查一次 checkpoint 时间戳)
   - A4 系列剩余 4 个, 每个 6-19h
   - A6 系列 5 个, A7 系列 2 个
   - 总剩余时间: 72-96h (3-4 天)

3. **v4 全部跑完后** (预计 7/24-7/25)
   - 立即运行 `rerun_full_save_weights.py` 保存 Full 权重 (~6h)
   - 然后运行 `bayesian_uq_experiment.py` 进行 MC Dropout UQ 实验

### 学术观察 (供论文撰写参考)

- **A2 反常优于 Full**: 在合成数据上 L_pcc 与 L_data 冲突, 提示论文需在真实数据验证
- **A4_lam0.01 ≈ A2**: λ₃=0.01 (接近 0) 性能接近去除 L_pcc, 符合理论预期
- **LOMO 6061-T6 完全失败**: 硬度 95 远低于训练分布中心 (200-350)
  → 这是贝叶斯 UQ 论文的核心动机: 用不确定性检测 OOD
- **LOMO 45_Steel 最佳**: 硬度 200 = 训练分布中心, 符合预期

---

## 5. 验证

本备份已通过以下验证:
- ✅ JSON 文件可解析 (ablation_checkpoint, lomo_ckpt, experiment_snapshot)
- ✅ 进程仍在运行 (PID 8776, 29356 均未退出)
- ✅ Checkpoint 文件非空 (v4=4502B, LOMO=1659B)
- ✅ 日志文件最近 1 小时内有更新 (v4 日志 23:29 最后 flush)

**最后验证时间**: 2026-07-21 00:08:35
