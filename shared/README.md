# `shared/` — 科研侧与工程侧共享薄契约层

## 定位

`shared/` 是「灵境制造」项目科研侧（`research/`）与工程侧（`engineering/`）**唯一共享的代码入口**，定义跨模块的数据契约、模型接口和常量。

- **零重依赖**：仅 `stdlib` + `typing_extensions`，严禁 `torch` / `numpy` / `pydantic` / `scikit-learn`
- **双向安装**：`engineering/` 和 `research/` 各自 `pip install -e shared/` 引用
- **契约边界**：本包只定义数据结构和接口签名，不含任何业务逻辑

## 安装

```bash
pip install -e shared/
```

## 契约清单

| 模块 | 导出内容 | 用途 |
|------|----------|------|
| `shared.lnn.types` | `FeatureChatterResult` / `ChatterPredictionTaskStatus` / `ChatterReviewStatus` / `PredictionMethod` | 颤振预测结果类型（阶段 5 输出） |
| `shared.lnn.model_card` | `ModelCard` | 模型卡（D-2 学术诚信：git_sha + data_hash 强制） |
| `shared.lnn.artifact` | `ModelArtifactSpec` | 模型产物规格（ONNX + model_card + preprocessor + schemas） |
| `shared.lnn.protocols` | `ChatterPredictorProtocol` / `ModelLoaderProtocol` | 运行时鸭子类型接口 |
| `shared.data.contracts` | `MachineParams` / `ToolParams` / `ChatterParams` / `MaterialParams` / `CuttingParams` / `ChatterReport` | 数据契约（阶段 4 → 5 → 6） |
| `shared.data.dataset` | `DatasetSpec` | 数据集规格（D-2 学术诚信：hash 强制） |
| `shared.constants.materials` | `DEFAULT_CONFIDENCE` / `PENDING_CALIBRATION_MATERIALS` / `CUTTING_FORCE_COEFF_TABLE` | 材料常量 |
| `shared.constants.precision` | `PrecisionTier` enum / `SAFETY_MARGIN_RATIO` | 精度档位 |
| `shared.constants.gates` | `INDUSTRIAL_HARD_GATES` / `REQUIRES_ENGINEER_REVIEW` / `REQUIRES_CAM_VALIDATION` | 工业硬门槛 |

## 核心约束

1. **D-2 学术诚信**：`ModelCard.git_sha` / `ModelCard.data_hash` / `DatasetSpec.hash` 强制非空，保证实验可复现
2. **工程优先**：`cam_validation_required` 始终为 `True`，`ChatterReport` 仅供阶段 6 参考，不可直接用于机床
3. **K_s 直传**：`cutting_force_coeff` 直接传递，不二次拟合
4. **HRC52 降级**：`pending_calibration` 材料强制降低置信度（0.8 → 0.5）
5. **契约变更**：任何字段变更需走 ADR 评审（与 ADR-005 一致）

## 目录结构

```
shared/
├── __init__.py
├── pyproject.toml
├── README.md
├── lnn/
│   ├── __init__.py
│   ├── types.py          # FeatureChatterResult 等枚举与数据类
│   ├── model_card.py     # ModelCard（D-2 学术诚信）
│   ├── artifact.py       # ModelArtifactSpec
│   └── protocols.py      # ChatterPredictorProtocol / ModelLoaderProtocol
├── data/
│   ├── __init__.py
│   ├── contracts.py      # ChatterParams / ChatterReport / MaterialParams 等
│   └── dataset.py        # DatasetSpec
└── constants/
    ├── __init__.py
    ├── materials.py       # DEFAULT_CONFIDENCE / K_s 表
    ├── precision.py       # PrecisionTier / SAFETY_MARGIN_RATIO
    └── gates.py           # INDUSTRIAL_HARD_GATES
```

## 相关 ADR

- [ADR-005](../docs/adr/ADR-005-核心架构契约设计.md) — 核心架构契约设计
- [ADR-013](../docs/adr/ADR-013-颤振预测接入.md) — 颤振预测三路径策略
- [ADR-020](../docs/adr/ADR-020-GUSH3R借鉴思路落地实践方案.md) — GUSH3R 借鉴思路落地
- [解耦设计 spec](../docs/superpowers/specs/2026-07-15-research-engineering-decoupling-design.md) — 科研/工程解耦完整设计
