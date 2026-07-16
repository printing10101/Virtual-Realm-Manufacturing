"""lomo SDK 一键复现演示（p5-8）.

本脚本演示实验快照的一键复现能力（snapshot.reproduce）：
    1. 查询快照详情（client.snapshots.get）
    2. 一键复现：后端根据 snapshot.config['workflow_spec'] 重建并启动新运行
       （client.snapshots.reproduce）
    3. 订阅新运行的事件流直到终态
    4. 对比原始快照 metrics 与新运行 metrics（学术复现验证）

学术复现意义:
    - 验证实验结果可复现性（消除随机种子 / 环境差异影响）
    - 在代码 / 数据 / 配置变更后，快速回归验证模型性能
    - 配合 MLflow run_id 实现完整溯源链（snapshot → original_run → reproduce_run）

前置条件:
    - workflow_demo.py 已成功执行并创建快照
    - 快照创建时 config 中嵌入了完整的 workflow_spec

运行方式::

    python examples/reproduce_demo.py --snapshot-id <id> --owner alice
    python examples/reproduce_demo.py --snapshot-id <id> --owner alice --compare-only
    python examples/reproduce_demo.py --list --owner alice
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lomo import LomoClient
from lomo.exceptions import LomoError, LomoNotFoundError, LomoValidationError


TERMINAL_EVENTS = {"workflow_completed", "workflow_failed", "workflow_cancelled"}
DEFAULT_WAIT_TIMEOUT = 3600.0


def subscribe_until_terminal(
    client: LomoClient,
    run_id: str,
    *,
    wait_timeout: float = DEFAULT_WAIT_TIMEOUT,
    verbose: bool = True,
) -> tuple[str | None, dict[str, Any] | None]:
    """订阅事件流直到终态。verbose=False 时仅打印关键事件。"""
    deadline = time.time() + wait_timeout
    final_event: str | None = None
    final_data: dict[str, Any] | None = None

    for ev in client.workflows.subscribe(run_id):
        if time.time() > deadline:
            if verbose:
                print(f"[超时] 等待 {wait_timeout}s 未收到终态事件")
            return final_event, final_data

        event_type = ev.get("event")
        data = ev.get("data", {}) or {}

        if verbose:
            if event_type == "node_completed":
                print(f"  [节点完成] {data.get('node_id')}  耗时={data.get('duration_seconds')}s")
            elif event_type == "node_failed":
                print(f"  [节点失败] {data.get('node_id')}  error={data.get('error')}")
            elif event_type in TERMINAL_EVENTS:
                print(f"  [工作流终态] {event_type}")

        if event_type in TERMINAL_EVENTS:
            final_event = event_type
            final_data = data
            break

    return final_event, final_data


def list_snapshots(client: LomoClient, owner: str) -> int:
    """列出指定 owner 的快照，便于查找 snapshot_id。"""
    print(f"\n=== 列出 {owner} 的实验快照 ===")
    result = client.snapshots.list(created_by=owner, detail=False)
    items = result.get("items", []) if isinstance(result, dict) else []

    if not items:
        print("  暂无快照记录")
        return 0

    print(f"共 {len(items)} 条：")
    for s in items:
        print(
            "  snapshot_id={sid}  model={m}  created_at={ts}  notes={nt}".format(
                sid=s.get("snapshot_id"),
                m=s.get("model_uri"),
                ts=s.get("created_at"),
                nt=(s.get("notes") or "")[:60],
            )
        )
    return 0


def compare_metrics(original: dict[str, Any], reproduced: dict[str, Any]) -> None:
    """对比原始快照与复现运行的 metrics。"""
    print("\n=== 指标对比（学术复现验证）===")
    orig_metrics = original.get("metrics", {}) or {}
    repro_metrics = reproduced.get("outputs", {}).get("metrics", {}) or {}

    if not orig_metrics and not repro_metrics:
        print("  双方均无 metrics，跳过对比")
        return

    all_keys = sorted(set(orig_metrics.keys()) | set(repro_metrics.keys()))
    print(f"  {'metric':<20} {'original':<15} {'reproduced':<15} {'delta':<15}")
    print(f"  {'-'*20} {'-'*15} {'-'*15} {'-'*15}")
    for k in all_keys:
        o = orig_metrics.get(k)
        r = repro_metrics.get(k)
        if o is None:
            delta = "(new)"
            o_str = "(missing)"
            r_str = f"{r:.6f}" if isinstance(r, (int, float)) else str(r)
        elif r is None:
            delta = "(missing)"
            o_str = f"{o:.6f}" if isinstance(o, (int, float)) else str(o)
            r_str = "(missing)"
        elif isinstance(o, (int, float)) and isinstance(r, (int, float)):
            delta_val = r - o
            delta = f"{delta_val:+.6f}"
            o_str = f"{o:.6f}"
            r_str = f"{r:.6f}"
        else:
            delta = "(non-numeric)"
            o_str = str(o)
            r_str = str(r)
        print(f"  {k:<20} {o_str:<15} {r_str:<15} {delta:<15}")


def reproduce_snapshot(
    client: LomoClient,
    snapshot_id: str,
    owner: str,
    *,
    wait_timeout: float = DEFAULT_WAIT_TIMEOUT,
    compare_only: bool = False,
) -> int:
    """一键复现快照。"""
    print(f"\n=== 一键复现快照 {snapshot_id} ===")

    # 1. 查询快照详情
    print("\n[1/3] 查询快照详情 ...")
    try:
        snapshot = client.snapshots.get(snapshot_id)
    except LomoNotFoundError as e:
        print(f"[快照未找到] {e}  code={e.code}")
        return 1

    print(
        "  model_uri={m}  created_by={cb}  git_sha={gs}".format(
            m=snapshot.get("model_uri"),
            cb=snapshot.get("created_by"),
            gs=(snapshot.get("git_sha") or "")[:12],
        )
    )

    config = snapshot.get("config", {}) or {}
    workflow_spec = config.get("workflow_spec")
    if not workflow_spec:
        print("\n[错误] 快照 config 中未嵌入 workflow_spec，无法一键复现")
        print("  创建快照时需在 config['workflow_spec'] 中提供完整 WorkflowSpec")
        return 1

    if compare_only:
        print("\n[仅对比模式] 跳过复现运行，仅展示原始 metrics")
        compare_metrics(snapshot, {"outputs": {"metrics": {}}})
        return 0

    # 2. 一键复现
    print("\n[2/3] 调用 snapshot.reproduce 启动新工作流运行 ...")
    try:
        new_run_id = client.snapshots.reproduce(snapshot_id)
    except LomoValidationError as e:
        print(f"[复现失败] workflow_spec 反序列化失败: {e}")
        return 1
    except LomoNotFoundError as e:
        print(f"[快照未找到] {e}")
        return 1

    if not new_run_id:
        print("[错误] 后端未返回 workflow_run_id")
        return 1
    print(f"  -> new_run_id={new_run_id}")

    # 3. 订阅事件流
    print(f"\n[3/3] 订阅事件流（超时 {wait_timeout}s）...")
    final_event, _ = subscribe_until_terminal(
        client, new_run_id, wait_timeout=wait_timeout, verbose=True
    )

    new_status = client.workflows.get_status(new_run_id)
    print(f"\n  最终状态：{new_status.get('status') if isinstance(new_status, dict) else None}")
    print(f"  final_event={final_event}")

    if final_event != "workflow_completed":
        print("\n[复现未成功] 可用以下命令查看详情：")
        print(f"  lomo workflow status {new_run_id}")
        return 1

    # 4. 指标对比
    compare_metrics(snapshot, new_status or {})

    # 5. 可选：为新运行创建快照（形成复现链）
    print("\n=== 为复现运行创建新快照 ===")
    new_snapshot = client.snapshots.create(
        model_uri=snapshot.get("model_uri"),
        created_by=owner,
        config={
            "workflow_spec": workflow_spec,
            "reproduced_from": snapshot_id,
            "original_mlflow_run_id": snapshot.get("mlflow_run_id"),
        },
        dataset_versions=snapshot.get("dataset_versions", []),
        metrics=(
            new_status.get("outputs", {}).get("metrics", {})
            if isinstance(new_status, dict)
            else {}
        ),
        notes=f"复现自 snapshot={snapshot_id} (run_id={new_run_id})",
    )
    new_snapshot_id = (
        new_snapshot.get("snapshot_id") if isinstance(new_snapshot, dict) else None
    )
    print(f"  -> new_snapshot_id={new_snapshot_id}")
    print(f"\n  复现链：{snapshot_id} -> {new_snapshot_id}")
    print(f"  MLflow 溯源：{snapshot.get('mlflow_run_id')} -> {new_snapshot.get('mlflow_run_id')}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="lomo SDK 一键复现演示（实验快照复现 + 指标对比）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--base-url", default=os.getenv("LOMO_BASE_URL", "http://127.0.0.1:8000"))
    parser.add_argument("--owner", default="demo_user", help="复现运行的发起人 ID")
    parser.add_argument("--token", default=os.getenv("LOMO_TOKEN"))
    parser.add_argument("--snapshot-id", help="要复现的快照 ID")
    parser.add_argument("--wait-timeout", type=float, default=DEFAULT_WAIT_TIMEOUT)
    parser.add_argument(
        "--compare-only",
        action="store_true",
        help="仅展示原始快照 metrics，不触发复现运行",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="列出指定 owner 的所有快照（用于查找 snapshot_id）",
    )
    args = parser.parse_args()

    if args.list and not args.snapshot_id:
        try:
            with LomoClient(base_url=args.base_url, token=args.token) as client:
                return list_snapshots(client, args.owner)
        except LomoError as e:
            print(f"\n[SDK 错误] {type(e).__name__}: {e}")
            return 1

    if not args.snapshot_id:
        parser.error("--snapshot-id 是必需的（除非使用 --list）")

    try:
        with LomoClient(base_url=args.base_url, token=args.token) as client:
            return reproduce_snapshot(
                client,
                args.snapshot_id,
                args.owner,
                wait_timeout=args.wait_timeout,
                compare_only=args.compare_only,
            )
    except LomoError as e:
        print(f"\n[SDK 错误] {type(e).__name__}: {e}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
