# 灵境制造（上线版）— Agent 协作指南

AI 驱动的制造智能桌面应用：**图纸 → 3D 模型 → 工艺规划 → NC 代码** 全流程智能化。
Tauri(Rust) + Vue3 + Python/FastAPI 全栈 monorepo。当前分支为 `main`（2026-08-19 分支收敛：refactor 已并入 main，旧 main 存档于 tag `backup/main-2026-08-03`）。

## 仓库地图

| 路径 | 内容 |
|---|---|
| `engineering/python/app/` | **工程侧主代码**（FastAPI 后端）：`api/` 路由、`ai/`（lnn 等）、`cad/` `dxf/` `step_import/` 图纸解析、`gcode_generation/` `postprocessor/`（11 种后处理器）、`process_planning/` `cam_validation/` 工艺、`rag/` 知识库、`simulation/`、`workflow/` `tasks/` `pipelines/`、`plugins/`、`agent/`、`services/` `infrastructure/` 等 70+ 模块 |
| `engineering/python/plugins/` | 业务插件（`data_flywheel` 等），绝对导入 `from plugins.xxx import ...` |
| `engineering/python/tests/` | **工程侧测试（CI 默认收集目标）**：unit/integration/api/plugins/security/e2e/architecture 等 |
| `engineering/python/app/**/tests/` | 模块自测，**不进入默认 CI 收集**，显式路径才跑 |
| `research/` | 科研侧（torch 训练/模型/量化），**独立环境**，`cd research && pytest tests/` |
| `engineering/src/` | Vue3 前端（src/stores、src/components 等） |
| `engineering/src-tauri/` | Tauri/Rust 桌面壳 |
| `rust/` | Rust 组件（后处理器等） |
| `scripts/` | 构建/工具脚本（version_sync、check_api_docs_sync 等，CI 门禁用） |
| `docs/` `docs-site/` | 文档；`PROJECT_OVERVIEW.md`、`REFACTOR_PLAN_V2.6.1.md`（重构计划） |
| `tests/` | 顶层少量 E2E（version_consistency 等） |

## 测试命令（必须按此跑）

```bash
unset PYTHONPATH                       # 坑1：桌面宿主环境注入的 PYTHONPATH 可能遮蔽 tests.utils 命名空间
python -m pytest                       # 坑2：用系统 Python 3.11；.venv 的 pydantic_core 已损坏
python -m pytest -m unit               # 快速：只跑单元测试
python -m pytest engineering/python/tests/unit/test_data_flywheel_plugin.py  # 单文件
cd research && pytest tests/           # 科研侧（独立环境，先装 research/requirements.txt）
```

pytest 配置见 `pytest.ini`：testpaths=engineering/python/tests，`--import-mode=importlib`，根 conftest.py 已在最早时机注入 `engineering/python/` 到 sys.path。
常用 markers：`unit` `integration` `api` `plugins` `regression` `e2e` `contracts` `lnn` `slow` `skip_ci`。

## 已知坑

1. **PYTHONPATH 遮蔽**：桌面宿主环境注入的 PYTHONPATH 可能含额外目录 → `ModuleNotFoundError('tests.utils')`。跑 pytest 前必须 `unset PYTHONPATH`。
2. **.venv 的 pydantic_core 损坏**：用系统 Python 3.11（anaconda/.venv 均不可靠），`python -m pytest` 而不是 `pytest`。
3. research/ 与 engineering/ 物理解耦中：工程侧 pytest 已排除 research/、shared/、app（norecursedirs + collect_ignore 双重防护）；改测试收集逻辑时不要破坏此防护。
4. 新模块自测若留在 `app/**/tests/`，必须用绝对导入（`from app.xxx import yyy`）。
5. 错误消息格式约定：`[错误类型] 具体描述。建议操作：[具体步骤]`。

## 开发约定

- **完整实现**：功能必须完整交付，拒绝 90% 半成品；≤30 分钟 TODO 必须当场做掉。
- **测试不延期**：新功能同步写测试，Bug 修复带复现测试，覆盖率 ≥80% 才可合并。
- **边缘情况**：已知边界必须在本次实现处理，不留 "TODO: 后续处理"。
- **文档同步**：API/配置/架构变更必须同步更新 docs；CI 有 check_api_docs_sync 门禁。
- **提交规范**：Conventional Commits（commitlint + husky 门禁），如 `feat(ci): ...`、`chore(git): ...`。
- **版本一致性**：`VERSION` / `version.py` / package.json 等由 `scripts/version_sync.py` 保障，CI 门禁。
