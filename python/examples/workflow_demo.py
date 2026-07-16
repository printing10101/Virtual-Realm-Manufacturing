"""lomo SDK 端到端工作流演示（p5-8）.

本脚本演示一个完整的 LTC 颤振预测训练工作流，覆盖 SDK 的所有核心能力：
    1. 构造 WorkflowSpec（DAG 形态：6 节点线性链）
    2. 校验 spec（client.workflows.validate）
    3. 提交运行（client.workflows.run）
    4. 订阅 SSE 事件流直到终态（client.workflows.subscribe）
    5. 查询最终状态（client.workflows.get_status）
    6. 从工作流 outputs 提取 model_uri，创建实验快照
    7. 失败时演示断点续跑（client.workflows.resume）

工作流 DAG 结构（与 app.workflows.engine 的 6 节点线性链对齐）::

    data_preprocess -> feature_extract -> train_ltc -> evaluate -> save_model
                                     -> record_metrics

对应研究背景: LTC（Liquid Time-Constant）网络在切削颤振预测中的应用，
数据源为 PHM2010 公开数据集 + 自采 6061-T6 工业数据。

运行前置条件:
    - 后端服务已启动
    - 后端已注册上述 task_type 的节点处理器
    - 数据集 phm2010_demo/v1.0.0 已通过 quickstart.py 创建

运行方式::

    python examples/workflow_demo.py --owner alice
    python examples/workflow_demo.py --owner alice --validate-only
    python examples/workflow_demo.py --owner alice --resume <run_id>
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lomo import LomoClient
from lomo.exceptions import LomoError, LomoValidationError


# ---------------------------------------------------------------------------
# 工作流常量
# ---------------------------------------------------------------------------

TERMINAL_EVENTS = {"workflow_completed", "workflow_failed", "workflow_cancelled"}

DEFAULT_WAIT_TIMEOUT = 3600.0  # 训练工作流最长等待 1 小时


def build_ltc_train_spec(
    dataset_id: str,
    dataset_version: str = "1.0.0",
    hyperparams: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """构造 LTC 训练 + 评估 WorkflowSpec.

    DAG 结构（6 节点线性链）::

        n1 data_preprocess
        n2 feature_extract
        n3 train_ltc
        n4 evaluate
        n5 save_model
        n6 record_metrics

    与 ``app.workflows.engine`` 注册的 task_type 严格对齐。
    """
    hp = hyperparams or {"lr": 1e-3, "hidden_size": 32, "epochs": 50, "seed": 42}
    dataset_uri = f"dataset://{dataset_id}/{dataset_version}"

    return {
        "name": "ltc_chatter_train",
        "version": "1.0.0",
        "nodes": [
            {
                "node_id": "n1",
                "task_type": "data_preprocess",
                "params": {"dataset_uri": dataset_uri, "split_ratio": 0.8},
                "inputs": {"dataset": dataset_uri},
                "retry": 1,
                "timeout_seconds": 600,
            },
            {
                "node_id": "n2",
                "task_type": "feature_extract",
                "params": {"window_size": 1024, "overlap": 0.5},
                "inputs": {"preprocessed": "artifact://n1/output"},
                "retry": 1,
                "timeout_seconds": 900,
            },
            {
                "node_id": "n3",
                "task_type": "train_ltc",
                "params": hp,
                "inputs": {"features": "artifact://n2/output"},
                "retry": 0,
                "timeout_seconds": 3600,
            },
            {
                "node_id": "n4",
                "task_type": "evaluate",
                "params": {"metrics": ["mae", "rmse", "r2", "f1"]},
                "inputs": {"model": "artifact://n3/output"},
                "retry": 0,
                "timeout_seconds": 600,
            },
            {
                "node_id": "n5",
                "task_type": "save_model",
                "params": {"registry": "model://ltc/"},
                "inputs": {"model": "artifact://n3/output", "metrics": "artifact://n4/output"},
                "retry": 1,
                "timeout_seconds": 300,
            },
            {
                "node_id": "n6",
                "task_type": "record_metrics",
                "params": {"tracker": "mlflow"},
                "inputs": {"metrics": "artifact://n4/output", "model": "artifact://n5/output"},
                "retry": 1,
                "timeout_seconds": 120,
            },
        ],
        "edges": [
            {"upstream": "n1", "downstream": "n2"},
            {"upstream": "n2", "downstream": "n3"},
            {"upstream": "n3", "downstream": "n4"},
            {"upstream": "n3", "downstream": "n5"},
            {"upstream": "n4", "downstream": "n5"},
            {"upstream": "n5", "downstream": "n6"},
            {"upstream": "n4", "downstream": "n6"},
        ],
        "inputs": {
            "dataset": {
                "name": "phm2010",
                "type": "dataset",
                "uri": dataset_uri,
                "metadata": {"source": "PHM2010"},
            }
        },
        "outputs": {
            "model_uri": "artifact://n5/output",
            "metrics": "artifact://n4/output",
        },
        "metadata": {
            "research_topic": "LTC chatter prediction",
            "dataset_source": "PHM2010 + 6061-T6 self-collected",
        },
    }


def subscribe_until_terminal(
    client: LomoClient,
    run_id: str,
    *,
    wait_timeout: float = DEFAULT_WAIT_TIMEOUT,
) -> tuple[str | None, dict[str, Any] | None]:
    """订阅工作流事件流直到终态。

    返回:
        (final_event, final_data) — final_event 为 None 表示流被远端关闭
        且未发出终态事件。
    """
    deadline = time.time() + wait_timeout
    final_event: str | None = None
    final_data: dict[str, Any] | None = None

    for ev in client.workflows.subscribe(run_id):
        if time.time() > deadline:
            print(f"[超时] 等待 {wait_timeout}s 未收到终态事件，停止订阅")
            return final_event, final_data

        event_type = ev.get("event")
        data = ev.get("data", {})

        if event_type == "node_started":
            print(f"  [节点开始] {data.get('node_id')}  task={data.get('task_type')}")
        elif event_type == "node_completed":
            print(f"  [节点完成] {data.get('node_id')}  耗时={data.get('duration_seconds')}s")
        elif event_type == "node_failed":
            print(f"  [节点失败] {data.get('node_id')}  error={data.get('error')}")
        elif event_type == "node_skipped":
            print(f"  [节点跳过] {data.get('node_id')}  reason={data.get('reason')}")
        elif event_type in TERMINAL_EVENTS:
            print(f"  [工作流终态] {event_type}  data={data}")
            final_event = event_type
            final_data = data
            break
        else:
            print(f"  [事件] {event_type}  data={data}")

    return final_event, final_data


def extract_model_uri(status: dict[str, Any]) -> str | None:
    """从工作流状态中提取 model_uri.

    优先级：
        1. status['outputs']['model_uri']
        2. status['outputs']['model_uri']['uri']
    """
    outputs = status.get("outputs") or {}
    if not isinstance(outputs, dict):
        return None
    v = outputs.get("model_uri")
    if isinstance(v, str) and v.startswith("model://"):
        return v
    if isinstance(v, dict):
        uri = v.get("uri") or v.get("model_uri")
        if isinstance(uri, str) and uri.startswith("model://"):
            return uri
    return None


def run_workflow(
    client: LomoClient,
    spec: dict[str, Any],
    owner: str,
    *,
    inputs: dict[str, Any] | None = None,
    wait_timeout: float = DEFAULT_WAIT_TIMEOUT,
    notes: str = "",
) -> int:
    """端到端运行工作流：校验 → 提交 → 订阅 → 快照。"""
    # 1. 校验
    print("\n[1/4] 校验 WorkflowSpec ...")
    try:
        validation = client.workflows.validate(spec)
    except LomoValidationError as e:
        print(f"[校验失败] {e}  detail={e.detail}")
        return 1
    if isinstance(validation, dict) and validation.get("errors"):
        print(f"[校验失败] {validation}")
        return 1
    print(f"  -> 校验通过：{validation}")

    # 2. 提交运行
    print("\n[2/4] 提交工作流运行 ...")
    run_id = client.workflows.run(spec=spec, inputs=inputs, owner_id=owner)
    if not run_id:
        print("[错误] 后端未返回 workflow_run_id")
        return 1
    print(f"  -> run_id={run_id}")

    # 3. 订阅事件流
    print(f"\n[3/4] 订阅事件流（超时 {wait_timeout}s）...")
    final_event, _ = subscribe_until_terminal(client, run_id, wait_timeout=wait_timeout)

    # 4. 查询最终状态 + 创建快照
    print("\n[4/4] 查询最终状态 ...")
    status = client.workflows.get_status(run_id)
    overall_status = status.get("status") if isinstance(status, dict) else None
    print(f"  -> status={overall_status}  final_event={final_event}")

    if final_event != "workflow_completed":
        print(f"\n[工作流未成功] 可用 `lomo workflow status {run_id}` 查看详情")
        print(f"  断点续跑：python examples/workflow_demo.py --resume {run_id} --owner {owner}")
        return 1

    model_uri = extract_model_uri(status or {})
    if not model_uri:
        print("\n[警告] 无法从 outputs 提取 model_uri，跳过快照创建")
        print(f"  手动创建：lomo snapshot create --model-uri <uri> --by {owner}")
        return 0

    print(f"\n  提取 model_uri={model_uri}")
    snapshot = client.snapshots.create(
        model_uri=model_uri,
        created_by=owner,
        config={
            "workflow_spec": spec,  # 嵌入 spec 以支持一键复现
            "hyperparams": spec["nodes"][2]["params"],
        },
        dataset_versions=[spec["inputs"]["dataset"]["uri"]],
        metrics=status.get("outputs", {}).get("metrics", {}) if isinstance(status, dict) else {},
        notes=notes or f"LTC 颤振预测训练 (run_id={run_id})",
    )
    snapshot_id = snapshot.get("snapshot_id") if isinstance(snapshot, dict) else None
    print(f"  -> snapshot_id={snapshot_id}")
    print(f"\n  一键复现：python examples/reproduce_demo.py --snapshot-id {snapshot_id} --owner {owner}")
    return 0


def resume_workflow(
    client: LomoClient,
    run_id: str,
    spec: dict[str, Any],
    owner: str,
    *,
    wait_timeout: float = DEFAULT_WAIT_TIMEOUT,
) -> int:
    """断点续跑工作流。"""
    print(f"\n[断点续跑] run_id={run_id}")
    try:
        result = client.workflows.resume(run_id, spec=spec, owner_id=owner)
    except LomoError as e:
        print(f"[续跑失败] {type(e).__name__}: {e}")
        return 1
    print(f"  -> resume 结果：{result}")

    print(f"\n[订阅事件流] 超时 {wait_timeout}s")
    final_event, _ = subscribe_until_terminal(client, run_id, wait_timeout=wait_timeout)
    status = client.workflows.get_status(run_id)
    print(f"\n  最终状态：status={status.get('status') if isinstance(status, dict) else None}")
    print(f"  final_event={final_event}")
    return 0 if final_event == "workflow_completed" else 1


def main() -> int:
    parser = argparse.ArgumentParser(
        description="lomo SDK 端到端工作流演示（LTC 颤振预测训练）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--base-url", default=os.getenv("LOMO_BASE_URL", "http://127.0.0.1:8000"))
    parser.add_argument("--owner", default="demo_user", help="工作流发起人 ID")
    parser.add_argument("--token", default=os.getenv("LOMO_TOKEN"))
    parser.add_argument("--dataset-id", default="phm2010_demo", help="训练数据集 ID")
    parser.add_argument("--dataset-version", default="1.0.0")
    parser.add_argument("--lr", type=float, default=1e-3)
    parser.add_argument("--hidden-size", type=int, default=32)
    parser.add_argument("--epochs", type=int, default=50)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--wait-timeout", type=float, default=DEFAULT_WAIT_TIMEOUT)
    parser.add_argument("--validate-only", action="store_true", help="仅校验 spec，不提交运行")
    parser.add_argument("--resume", metavar="RUN_ID", help="断点续跑指定 run_id")
    parser.add_argument("--notes", default="", help="快照备注")
    args = parser.parse_args()

    spec = build_ltc_train_spec(
        dataset_id=args.dataset_id,
        dataset_version=args.dataset_version,
        hyperparams={
            "lr": args.lr,
            "hidden_size": args.hidden_size,
            "epochs": args.epochs,
            "seed": args.seed,
        },
    )

    try:
        with LomoClient(base_url=args.base_url, token=args.token) as client:
            if args.validate_only:
                print("[仅校验模式]")
                validation = client.workflows.validate(spec)
                print(f"校验结果：{validation}")
                return 0

            if args.resume:
                return resume_workflow(
                    client, args.resume, spec, args.owner, wait_timeout=args.wait_timeout
                )

            return run_workflow(
                client, spec, args.owner, wait_timeout=args.wait_timeout, notes=args.notes
            )
    except LomoError as e:
        print(f"\n[SDK 错误] {type(e).__name__}: {e}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
