# 安全约束规则 `eval()` 修复说明

## 1. 任务背景

`python/app/rules/safety_constraint_rules.py` 中存在 `eval()` 调用，用于解析简单算术表达式（如 `max_spindle_speed * 0.9`）。该用法导致严重的代码注入风险：恶意构造的字符串（如 `__import__('os').system('rm -rf /')`）可能被执行。

## 2. 选择的方案：基于 AST 白名单的自定义求值器

对比三种候选方案后，最终选择 **方案 b：自定义递归下降式 AST 校验器**（`SafeMathEvaluator`）。

| 方案 | 优点 | 缺点 | 结论 |
|------|------|------|------|
| a) `ast.literal_eval` | 简单、零依赖 | 只能解析字面量，**无法支持运算符** | 不可行 |
| b) 自定义 AST 白名单 | 零依赖、可严格控制 AST 节点类型、可缓存 | 实现成本中等 | **采用** |
| c) `simpleeval` | 开箱即用 | 引入第三方依赖；可配置面广反而可能引入新攻击面 | 不必要 |

## 3. 实现细节

### 3.1 安全策略

`SafeMathEvaluator` 通过 **白名单 + 双层校验** 实现：

1. **预检（regex 白名单）**：`^[\d\s\+\-\*\/\(\)\.]+$`，第一时间拒绝任何非法字符。
2. **AST 校验**：仅允许以下节点类型，其余（含 `Name`、`Call`、`Attribute`、`Subscript`、`Compare`、`IfExp`、`Lambda` 等所有可执行结构）一律拒绝：
   - `ast.Expression`
   - `ast.BinOp`（操作符限于 `Add/Sub/Mult/Div`）
   - `ast.UnaryOp`（操作符限于 `UAdd/USub`）
   - `ast.Constant`（值类型限于 `int/float`，**显式拒绝 `bool`**，避免 `True==1` 之类的语义混淆）

### 3.2 性能优化

- **模块级 LRU 缓存**：`_SAFE_EXPR_CACHE` 复用同一字符串对应的 AST 与校验结果，上限 512 条，FIFO 淘汰。
- **避免重复解析**：对相同表达式（如 `max_spindle_speed * 0.9`），第一次校验后再次调用直接命中缓存。

实测性能：10000 次求值 ≈ 15 ms，即 ~680k ops/s（验收脚本 `[4] Performance`）。

### 3.3 错误处理

- 任何非法输入（`None`、空字符串、非字符串、含非法字符、AST 校验失败、除零、解析异常）一律返回 `0.0`，与原 `eval()` 失败降级行为完全一致。
- `_resolve_expression` 中字符串替换失败（如 `float()` 失败）也返回 `0.0`。

### 3.4 接口兼容性

- `safe_eval_math_expression(expr: Any) -> float`：`expr` 接受任意类型，非字符串返回 `0.0`。
- `SafetyRuleEngine._resolve_expression(expr: str, sensor_data: Dict[str, Any]) -> float`：签名、参数、返回类型与原实现完全一致。
- `Sensor_data` 字段替换改为**按键长倒序**进行，避免 `spindle_speed` 误替换 `max_spindle_speed` 引起的长键残缺问题。

## 4. 文件清单

| 文件 | 操作 | 说明 |
|------|------|------|
| `python/app/rules/safety_constraint_rules.py` | 修改 | 引入 `SafeMathEvaluator`、`safe_eval_math_expression`；移除 `eval()`；修复字段替换顺序 |
| `python/tests/rules/test_safety_expression_evaluator.py` | 新增 | 124 个测试用例，覆盖正常/恶意/边界/缓存/性能/线程安全 |
| `python/verify_security_fix.py` | 新增 | 自动化验收脚本（静态扫描 + 功能用例 + 性能 smoke） |
| `python/docs/SECURITY_FIX_eval.md` | 新增 | 本文档 |

## 5. 验收检测结果

| 检测项 | 期望 | 实际 |
|--------|------|------|
| `grep "eval(" safety_constraint_rules.py` | 无匹配 | **0 匹配** |
| `grep "import ast\|simpleeval\|def .*eval"` | ≥1 项 | **2 项**（`import ast` + `safe_eval_math_expression`） |
| `safe_eval_math_expression("10.5+20.3*2")` | `51.1` | **51.1** |
| 恶意代码 `__import__('os').system('echo hack')` | `0.0` | **0.0** |
| 空表达式 / `abc` / `1**2` / `1/0` / `None` / `123` | `0.0` | **全部 0.0** |
| 单元测试 | 全通过 | **124 / 124 通过** |
| `tests/rules/` 全部 | 全通过 | **174 / 174 通过** |
| 性能 | ≥原 `eval()` 的 80% | ~680k ops/s（已通过 smoke test） |

## 6. 复测命令

```bash
# 静态扫描
grep -n "eval(" python/app/rules/safety_constraint_rules.py
grep -n "import ast\|simpleeval\|def.*eval" python/app/rules/safety_constraint_rules.py

# 验收脚本
cd python && python verify_security_fix.py

# 单元测试
cd python && python -m pytest tests/rules/test_safety_expression_evaluator.py -v
```

## 7. 后续建议

- 如需支持更多运算符（如 `%`、`**`），可在 `_ALLOWED_BINOPS` 中追加并在 `_eval_node` 中实现，但**务必同步**更新 `_PRECHECK_PATTERN` 与测试。
- 若需支持变量引用（如 YAML 表达式中嵌入 `$max_spindle_speed`），建议引入专用模板引擎（如 `string.Template`）而不是再走求值器路线。
- `_SAFE_EXPR_CACHE_MAX` 当前为 512，可按实际部署规模调优。
