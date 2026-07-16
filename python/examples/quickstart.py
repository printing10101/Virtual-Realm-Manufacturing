"""lomo SDK 快速入门示例（p5-8）.

对应 docs/development/core-contracts-design.md 第 10 章阶段 5 验收标准：
    "外部 Python 脚本可调用 SDK 跑通完整工作流"

本脚本演示 lomo SDK 的最小可用调用链：
    1. 创建客户端（同步 + 异步两种用法）
    2. 创建数据集并提交版本
    3. 流式读取数据集内容
    4. 列出工作流 / 提交运行 / 查询状态
    5. 创建实验快照

运行前置条件:
    - 后端服务已启动（默认 http://127.0.0.1:8000）
    - 可选：通过环境变量 LOMO_BASE_URL / LOMO_TOKEN 配置
    - lomo 包已安装：``pip install -e python/``

运行方式::

    python examples/quickstart.py
    python examples/quickstart.py --base-url http://127.0.0.1:8000 --owner alice

注意:
    本示例默认使用 PHM2010 切削力数据集作为演示场景，与项目研究背景
    （LTC 颤振预测）保持一致。所有数据均为演示用占位数据，不会真正
    训练模型；如需端到端训练，请参考 workflow_demo.py。
"""
from __future__ import annotations

import argparse
import os
import sys
from typing import Any

# 确保可以从 python/ 目录导入 lomo 包（开发模式）
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lomo import LomoClient
from lomo.exceptions import (
    LomoAuthError,
    LomoConnectionError,
    LomoError,
    LomoNotFoundError,
    LomoTimeoutError,
    LomoValidationError,
)


# ---------------------------------------------------------------------------
# 演示数据：PHM2010 切削力数据集 schema
# ---------------------------------------------------------------------------

PHM2010_SCHEMA: dict[str, Any] = {
    "fields": {
        "sample_id": {"type": "int", "required": True, "description": "样本 ID"},
        "force_x": {"type": "float", "required": True, "description": "X 向切削力 (N)"},
        "force_y": {"type": "float", "required": True, "description": "Y 向切削力 (N)"},
        "force_z": {"type": "float", "required": True, "description": "Z 向切削力 (N)"},
        "tool_wear": {"type": "float", "required": False, "description": "刀具磨损量 (mm)"},
        "label": {"type": "int", "required": False, "description": "颤振标签 0/1"},
    },
    "primary_key": ["sample_id"],
    "metadata": {
        "source": "PHM2010",
        "unit": "N",
        "sampling_rate_hz": 2048,
    },
}

DEMO_RECORDS: list[dict[str, Any]] = [
    {"sample_id": 1, "force_x": 120.5, "force_y": 45.2, "force_z": 310.8, "tool_wear": 0.12, "label": 0},
    {"sample_id": 2, "force_x": 135.7, "force_y": 48.9, "force_z": 325.4, "tool_wear": 0.14, "label": 0},
    {"sample_id": 3, "force_x": 280.1, "force_y": 92.3, "force_z": 510.6, "tool_wear": 0.21, "label": 1},
    {"sample_id": 4, "force_x": 310.4, "force_y": 105.8, "force_z": 545.2, "tool_wear": 0.23, "label": 1},
]


def demo_sync_client(base_url: str, owner: str, token: str | None) -> None:
    """演示同步客户端的完整调用链。"""
    print("\n=== 同步客户端演示 ===")
    print(f"base_url={base_url}  owner={owner}")

    try:
        with LomoClient(base_url=base_url, token=token) as client:
            # 1. 创建数据集
            print("\n[1/5] 创建数据集 phm2010_demo ...")
            ds = client.datasets.create(
                name="phm2010_demo",
                schema=PHM2010_SCHEMA,
                owner_id=owner,
                description="PHM2010 切削力数据集（lomo SDK 快速入门演示）",
            )
            dataset_id = ds["dataset_id"]
            print(f"  -> dataset_id={dataset_id}  status={ds.get('status')}")

            # 2. 提交版本
            print("\n[2/5] 提交版本 v1.0.0 ...")
            version = client.datasets.commit_version(
                dataset_id,
                records=DEMO_RECORDS,
                version="1.0.0",
                lineage={
                    "target": f"dataset://phm2010_demo/1.0.0",
                    "source_type": "manual",
                    "source_ref": f"manual://{owner}",
                    "inputs": [],
                    "outputs": [f"dataset://phm2010_demo/1.0.0"],
                    "operation": "ingest",
                    "metadata": {"row_count": len(DEMO_RECORDS)},
                },
            )
            print(
                "  -> version={ver}  row_count={n}  content_hash={h}".format(
                    ver=version.get("version"),
                    n=version.get("row_count"),
                    h=version.get("content_hash", "")[:12],
                )
            )

            # 3. 流式读取
            print("\n[3/5] 流式读取数据集（前 3 行）...")
            count = 0
            for row in client.datasets.read(dataset_id, version="1.0.0"):
                print(f"  -> row[{count}] = {row}")
                count += 1
                if count >= 3:
                    break
            print(f"  -> 共读取 {count} 行（演示截断）")

            # 4. 列出工作流
            print("\n[4/5] 列出最近 5 个工作流运行 ...")
            runs = client.workflows.list(limit=5, offset=0)
            items = runs.get("items", []) if isinstance(runs, dict) else []
            if not items:
                print("  -> 暂无工作流运行记录")
            for r in items:
                print(
                    "  -> run_id={rid}  status={st}  name={nm}".format(
                        rid=r.get("workflow_run_id"),
                        st=r.get("status"),
                        nm=r.get("spec", {}).get("name", "?"),
                    )
                )

            # 5. 创建实验快照（占位 model_uri，仅演示 API 调用）
            print("\n[5/5] 创建实验快照 ...")
            snapshot = client.snapshots.create(
                model_uri="model://ltc/0.0.1-demo",
                created_by=owner,
                config={
                    "hyperparams": {"lr": 1e-3, "hidden_size": 32},
                    "seed": 42,
                },
                dataset_versions=[f"dataset://phm2010_demo/1.0.0"],
                metrics={"demo": 1.0},
                notes="lomo SDK 快速入门演示快照（非真实训练结果）",
            )
            print(f"  -> snapshot_id={snapshot.get('snapshot_id')}")

    except LomoAuthError as e:
        print(f"\n[鉴权失败] {e}  code={e.code}  request_id={e.request_id}")
        print("请检查 LOMO_TOKEN 环境变量或 --token 参数")
    except LomoValidationError as e:
        print(f"\n[参数错误] {e}  detail={e.detail}")
    except LomoNotFoundError as e:
        print(f"\n[资源未找到] {e}  code={e.code}")
    except LomoTimeoutError as e:
        print(f"\n[请求超时] {e}")
        print("请检查后端服务是否启动：uvicorn app.main:app --reload")
    except LomoConnectionError as e:
        print(f"\n[网络错误] {e}")
        print("请检查后端服务是否启动：uvicorn app.main:app --reload")
    except LomoError as e:
        print(f"\n[SDK 错误] {type(e).__name__}: {e}")


def demo_async_client(base_url: str, owner: str, token: str | None) -> None:
    """演示异步客户端的最小调用（适用于 asyncio 应用 / Jupyter Notebook）。"""
    import asyncio

    from lomo import AsyncLomoClient

    print("\n=== 异步客户端演示 ===")

    async def _run() -> None:
        async with AsyncLomoClient(base_url=base_url, token=token) as client:
            # 异步列出数据集
            result = await client.datasets.list(owner_id=owner, limit=5)
            items = result.get("items", []) if isinstance(result, dict) else []
            print(f"异步列出数据集：共 {len(items)} 条")
            for d in items:
                print(f"  -> dataset_id={d.get('dataset_id')}  name={d.get('name')}")

            # 异步列出快照
            snaps = await client.snapshots.list(created_by=owner, detail=False)
            snap_items = snaps.get("items", []) if isinstance(snaps, dict) else []
            print(f"异步列出快照：共 {len(snap_items)} 条")

    try:
        asyncio.run(_run())
    except LomoError as e:
        print(f"\n[异步 SDK 错误] {type(e).__name__}: {e}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="lomo SDK 快速入门示例",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--base-url",
        default=os.getenv("LOMO_BASE_URL", "http://127.0.0.1:8000"),
        help="后端服务地址（默认读取 LOMO_BASE_URL 环境变量）",
    )
    parser.add_argument(
        "--owner",
        default="demo_user",
        help="数据集 / 快照的 owner_id（默认 demo_user）",
    )
    parser.add_argument(
        "--token",
        default=os.getenv("LOMO_TOKEN"),
        help="Bearer token（默认读取 LOMO_TOKEN 环境变量）",
    )
    parser.add_argument(
        "--skip-async",
        action="store_true",
        help="跳过异步客户端演示（适用于 WinSock 异常环境）",
    )
    args = parser.parse_args()

    demo_sync_client(args.base_url, args.owner, args.token)

    if not args.skip_async:
        demo_async_client(args.base_url, args.owner, args.token)

    print("\n快速入门演示完成。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
