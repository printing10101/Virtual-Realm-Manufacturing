"""独立验证脚本：绕过 WinSock 损坏 + 缺失依赖，验证 P5 契约层测试逻辑.

背景
----
本机 WinSock 损坏导致：
1. pip / conda 无法联网安装 fastapi / aiosqlite / pytest_asyncio
2. sqlalchemy 导入 asyncio → _overlapped 触发 OSError [WinError 10038]
3. P5 完整测试无法在本地运行

本脚本绕过策略：
- 注入 _overlapped 桩（复用 conftest.py 绕过方案）
- 仅验证 app.contracts.* 契约层（纯标准库实现，不依赖 fastapi/sqlalchemy）
- 复现 TestContractsInteroperability 类 7 个测试方法的逻辑

验证范围
--------
- test_task_workflow_contract_construction
- test_dataset_contract_construction
- test_plugin_contract_construction
- test_world_model_contract_construction
- test_rl_agent_contract_construction
- test_explainability_contract_construction
- test_observability_contract_construction

不在此脚本验证范围（需 DB/fastapi/plugins）：
- TestClosedLoopWorkflowEndToEnd（需 DAGStore + WorkflowRunner）
- TestWorldModelRLAgentIntegration（需真实插件）
- TestSafetyShieldHardConstraints（需 RLAgentPlugin）
- TestPhase1To8SnapshotIntegration（需 SnapshotStore + DB）
- TestClosedLoopFailurePropagation（需 WorkflowRunner）
"""
from __future__ import annotations

import sys
import types
from pathlib import Path

# === 1. WinSock 损坏绕过：注入 _overlapped 桩 ===
try:
    import _overlapped  # noqa: F401
except OSError:
    _patch = types.ModuleType("_overlapped")
    _patch.Overlapped = type("Overlapped", (), {})
    sys.modules["_overlapped"] = _patch
    print("[warn] _overlapped 桩已注入（WinSock 损坏绕过）")

# === 2. 将 python/ 加入 sys.path ===
_PYTHON_ROOT = Path(__file__).resolve().parent
if str(_PYTHON_ROOT) not in sys.path:
    sys.path.insert(0, str(_PYTHON_ROOT))


def _run_test(test_name: str, test_fn) -> bool:
    """运行单个测试函数，返回是否通过."""
    try:
        test_fn()
        print(f"  [PASS] {test_name}")
        return True
    except Exception as exc:
        print(f"  [FAIL] {test_name}: {type(exc).__name__}: {exc}")
        return False


def test_task_workflow_contract_construction():
    from app.contracts.task import (
        Artifact,
        TaskResult,
        TaskStatus,
        WorkflowEdge,
        WorkflowNode,
        WorkflowSpec,
    )

    node = WorkflowNode(node_id="n1", task_type="test_task")
    edge = WorkflowEdge(upstream="n1", downstream="n2")
    spec = WorkflowSpec(
        name="contract_test",
        version="1.0.0",
        nodes=[node],
        edges=[edge],
    )
    assert spec.name == "contract_test"
    assert len(spec.nodes) == 1

    artifact = Artifact(name="out", type="metrics", uri="metrics://test")
    result = TaskResult(
        status=TaskStatus.COMPLETED,
        outputs={"out": artifact},
    )
    assert result.status == TaskStatus.COMPLETED


def test_dataset_contract_construction():
    from app.contracts.dataset import DatasetSchema, DatasetStatus

    schema = DatasetSchema(
        fields={"col": {"type": "float", "required": True}},
        primary_key=["col"],
    )
    assert "col" in schema.fields
    assert DatasetStatus.DRAFT.value == "draft"


def test_plugin_contract_construction():
    from app.contracts.plugin import BUILTIN_CAPABILITIES, PluginManifest

    assert "task:submit" in BUILTIN_CAPABILITIES
    manifest = PluginManifest(
        id="test_plugin",
        name="测试插件",
        version="1.0.0",
        description="测试插件",
        author="test",
        license="MIT",
        entrypoint="test:plugin",
    )
    assert manifest.id == "test_plugin"
    assert manifest.entrypoint == "test:plugin"


def test_world_model_contract_construction():
    from app.contracts.world_model import (
        DEFAULT_STATE_DIM,
        StateField,
        WorldModelPredictRequest,
    )

    assert DEFAULT_STATE_DIM == 8
    assert StateField.SPINDLE_SPEED == "spindle_speed"

    request = WorldModelPredictRequest(
        current_state={"spindle_speed": 8000.0},
        candidate_action={"spindle_speed_delta": 0.0},
        horizon=10,
    )
    assert request.horizon == 10


def test_rl_agent_contract_construction():
    from app.contracts.rl_agent import (
        DEFAULT_ACTION_DIM,
        OptimizationTarget,
        PolicyAlgorithm,
        RLActRequest,
        TrainingStatus,
    )

    assert DEFAULT_ACTION_DIM == 4
    assert PolicyAlgorithm.is_valid(PolicyAlgorithm.PPO)
    assert OptimizationTarget.default() == OptimizationTarget.BALANCE
    assert TrainingStatus.is_terminal(TrainingStatus.COMPLETED)
    assert not TrainingStatus.is_terminal(TrainingStatus.RUNNING)

    request = RLActRequest(
        current_state={"spindle_speed": 8000.0},
        candidate_actions=[{"spindle_speed_delta": 0.0}],
        optimization_target=OptimizationTarget.MINIMIZE_CHATTER,
    )
    assert request.optimization_target == OptimizationTarget.MINIMIZE_CHATTER


def test_explainability_contract_construction():
    from app.contracts.explainability import (
        ComparisonType,
        ExplanationType,
        ProjectionMethod,
    )

    assert ExplanationType.is_valid(ExplanationType.HIDDEN_STATE)
    assert ProjectionMethod.default() == ProjectionMethod.PCA
    assert ComparisonType.is_valid(ComparisonType.SAME_MODEL_DIFF_INPUT)

    all_types = ExplanationType.all()
    assert len(all_types) == 4
    assert set(all_types) == {
        ExplanationType.HIDDEN_STATE,
        ExplanationType.GATE_DYNAMICS,
        ExplanationType.COUNTERFACTUAL,
        ExplanationType.CONFIDENCE,
    }


def test_observability_contract_construction():
    from datetime import datetime

    from app.contracts.observability import ExperimentSnapshot

    snapshot = ExperimentSnapshot(
        snapshot_id="snap-001",
        created_at=datetime(2026, 1, 1, 0, 0, 0),
        created_by="test_user",
        git_sha="abc123",
        code_dirty=False,
        config={"lr": 0.001},
        dataset_versions=[],
        model_uri="model://test",
        metrics={"accuracy": 0.95},
        environment={"python": "3.13"},
    )
    assert snapshot.snapshot_id == "snap-001"
    assert snapshot.metrics["accuracy"] == 0.95
    assert snapshot.git_sha == "abc123"


def main() -> int:
    print("=" * 70)
    print("P5 契约层独立验证（绕过 WinSock 损坏 + 缺失依赖）")
    print("=" * 70)
    print()

    tests = [
        ("test_task_workflow_contract_construction", test_task_workflow_contract_construction),
        ("test_dataset_contract_construction", test_dataset_contract_construction),
        ("test_plugin_contract_construction", test_plugin_contract_construction),
        ("test_world_model_contract_construction", test_world_model_contract_construction),
        ("test_rl_agent_contract_construction", test_rl_agent_contract_construction),
        ("test_explainability_contract_construction", test_explainability_contract_construction),
        ("test_observability_contract_construction", test_observability_contract_construction),
    ]

    passed = 0
    failed = 0
    for name, fn in tests:
        if _run_test(name, fn):
            passed += 1
        else:
            failed += 1

    print()
    print("=" * 70)
    print(f"结果: {passed} 通过 / {failed} 失败 / {len(tests)} 总计")
    print("=" * 70)
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
