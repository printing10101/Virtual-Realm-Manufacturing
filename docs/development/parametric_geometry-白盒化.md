# P1-2 parametric_geometry 两轮审核状态机白盒化

**创建日期**: 2026-08-20  
**状态**: 🟡 白盒模块 + 测试已落地；委托接线待文件锁解除

---

## 🎯 目标

将 `parametric_geometry` 的「状态流转判定」抽取为纯 Python 白盒模块
（P1-1 方法论复用），使核心审核逻辑零框架依赖、CI 可独立跑全量覆盖。

## 📦 已交付

### 白盒模块
`app/parametric_geometry/_review_state_machine.py`（纯 stdlib，零框架依赖）：

| 函数 | 对应 pipeline 委托点 |
|---|---|
| `can_execute(status)` | `run_pipeline` 的状态允许性检查 |
| `can_review(status)` | `review_step_feature` 的状态允许性检查 |
| `can_finalize(status)` | `finalize_step` 的状态允许性检查 |
| `can_transition(cur, target)` | 状态机转移规则表 |
| `all_features_reviewed(statuses)` | `review_step_feature` 的全审核判定 |
| `next_status_after_review(all_done, cur)` | 审核后的新状态计算 |
| `is_terminal(status)` | 终态判定 |
| `is_valid_review_status / is_valid_task_status` | 枚举校验 |
| `assert_transition_allowed / assert_review_status_valid` | 断言式校验 |

状态常量与 `step_store.py` 的 `ParametricGeometryTaskStatus` /
`StepReviewStatus` 枚举**逐值对齐**（测试锁定防漂移）。

### 测试
`engineering/python/tests/unit/test_parametric_review_state_machine.py`
（~45 用例）：枚举对齐 / 各状态允许性 / 转移规则 / 审核完成判定 / 校验函数。

## 🔧 待接线（文件锁解除后执行，委托路径保留框架调用）

### pipeline.py 委托（3 处）
```python
# 1. run_pipeline 执行检查（原：task.status not in (pending, failed)）
from app.parametric_geometry._review_state_machine import can_execute
if not can_execute(task.status):
    raise ParametricGeometryError(...)

# 2. review_step_feature 审核检查（原：task.status != step_generated）
from app.parametric_geometry._review_state_machine import (
    can_review, all_features_reviewed, next_status_after_review,
    is_valid_review_status,
)
if not can_review(task.status):
    raise StepReviewError(...)
if not is_valid_review_status(review_status):
    raise StepReviewError(...)
all_reviewed = all_features_reviewed(
    [f.review_status for f in task.input_features]
)
new_status = next_status_after_review(all_reviewed, task.status)

# 3. finalize_step 最终化检查（原：task.status != reviewed）
from app.parametric_geometry._review_state_machine import can_finalize
if not can_finalize(task.status):
    raise ParametricGeometryError(...)
```

### 导出
`app/parametric_geometry/__init__.py` 追加：
```python
from app.parametric_geometry._review_state_machine import (
    ST_PENDING, ST_RUNNING, ST_STEP_GENERATED, ST_REVIEWED,
    ST_SUCCEEDED, ST_FAILED, ST_CANCELLED,
    can_execute, can_review, can_finalize, all_features_reviewed,
    next_status_after_review, is_terminal,
)
```

## ✅ 验收标准（门禁）

1. ruff check app/parametric_geometry/ 全绿
2. mypy 0 错误（白盒模块无 torch）
3. `_review_state_machine.py` 行覆盖 **100%**
4. 既有 parametric_geometry 测试（委托后行为不变）全绿
5. 状态机常量与枚举逐值对齐（测试已锁定）

## 📝 变更日志

### v1.0 (2026-08-20)
- 白盒模块 `_review_state_machine.py` 落地
- 测试 `test_parametric_review_state_machine.py` 落地（~45 用例）
- 待办：pipeline.py 委托接线 + 导出（文件锁解除后）
