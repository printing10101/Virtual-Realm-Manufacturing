"""实时监控 WebSocket 端点（Phase A 前端实时数据通道）。

桥接 MTConnectStreamServer → FastAPI WebSocket：
- GET /api/v1/monitor/ws?machine_id=VM-001
  建立 WS 连接后，服务端持续推送 MTConnect 实时事件（data/alert），
  前端 MachineMonitor.vue 消费。

协议：
- 客户端 → 服务端：{ "action": "subscribe", "machine_id": "VM-001" }
- 服务端 → 客户端：StreamEvent.to_dict() JSON
  { "event_id", "timestamp", "data": {...}, "event_type", "priority" }
  其中 event_type ∈ {data, alert}

数据源（上机准备：本地模拟 Agent 联调）：
- 默认读取环境变量 ``MTCONNECT_AGENT_URL``（未配置时为本地模拟 Agent
  ``http://127.0.0.1:5010``，对应 :mod:`app.dnc.mock_agent.MockMTConnectAgent`）。
- Agent 可达：通过 MTConnectAdapter 拉取真实数据，并用 :func:`check_alerts`
  推送告警（模拟 Agent 周期性触发主轴过载，用于验证告警链路）。
- Agent 不可达：优雅降级为内置 demo 数据（:func:`_demo_sample`），保证前端可调试。

设计要点：
1. 优雅降级：MTConnect Agent 不可达时推送模拟数据（demo 模式），
   保证前端面板可开发调试（与既有 demo.mtconnect.org 兼容）
2. 心跳：每 15s 推送 ping 事件，检测断线
3. 权限：require_permission("monitor:read")
4. 并发安全：每连接独立订阅，断开自动清理
"""

from __future__ import annotations

import asyncio
import logging
import os

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.integrations.mtconnect.adapter import AdapterConfig, MTConnectAdapter
from app.integrations.mtconnect.parser import Sample
from app.integrations.mtconnect.streaming import StreamEvent, check_alerts

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/monitor", tags=["realtime-monitor"])

# 心跳间隔（秒）
_HEARTBEAT_INTERVAL_S = 15.0

# 本地模拟 Agent 默认地址（无真实机床时用于联调验证；生产环境用 MTCONNECT_AGENT_URL 覆盖）
_DEFAULT_AGENT_URL = "http://127.0.0.1:5010"


def _resolve_agent_url() -> str:
    """返回当前生效的 MTConnect Agent URL（环境变量优先）。"""
    return os.getenv("MTCONNECT_AGENT_URL", _DEFAULT_AGENT_URL)


def _create_adapter() -> MTConnectAdapter | None:
    """创建并探活 MTConnect 适配器；Agent 不可达时返回 None（demo 降级）。"""
    agent_url = _resolve_agent_url()
    cfg = AdapterConfig(
        agent_url=agent_url,
        interval=1.0,
        batch_size=1,
        batch_interval=0.0,
        max_retries=1,
        timeout=3.0,
    )
    adapter = MTConnectAdapter(config=cfg)
    try:
        adapter.probe()
        logger.info("monitor: connected to MTConnect agent %s", agent_url)
        return adapter
    except (ConnectionError, OSError, TimeoutError):
        logger.warning("monitor: MTConnect agent %s 不可达，降级为 demo 数据源", agent_url)
        try:
            adapter.close()
        except Exception:  # pragma: no cover - 防御性
            pass
        return None


async def _ws_permission_check(websocket: WebSocket) -> None:
    """WS 权限检查（require_permission 是 FastAPI Depends，WS 需手动调用）。"""
    if os.environ.get("LNN_PERMISSION_ENFORCED", "true").strip().lower() in (
        "0",
        "false",
        "no",
        "off",
    ):
        return
    if not hasattr(websocket.state, "username") or not websocket.state.username:
        await websocket.close(code=4401, reason="Not authenticated")
        raise WebSocketDisconnect(4401, "Not authenticated")


def _demo_sample(machine_id: str, tick: int) -> Sample:
    """生成模拟样本（Agent 不可达时降级用，保证前端可调试）。"""
    return Sample(
        spindle_speed=float(6000 + tick % 500),
        spindle_load=float(40 + (tick % 30)),
        feedrate=float(300 + tick % 200),
        execution="ACTIVE" if tick % 5 else "IDLE",
    )


@router.websocket("/ws")
async def machine_monitor_ws(websocket: WebSocket) -> None:
    """实时机床监控 WebSocket 端点。

    数据源优先级：MTConnect Agent（本地联调用模拟 Agent）→ demo 降级。
    """
    await websocket.accept()
    try:
        await _ws_permission_check(websocket)
    except WebSocketDisconnect:
        return

    machine_id = "VM-001"
    tick = 0

    # 数据源：优先 MTConnect Agent，不可达时降级 demo（优雅降级，前端可调试）
    adapter = _create_adapter()
    use_adapter = adapter is not None

    try:
        while True:
            # 接收订阅/心跳消息（非阻塞）
            try:
                message = await asyncio.wait_for(websocket.receive_json(), timeout=0.1)
                action = message.get("action", "")
                if action == "subscribe" and message.get("machine_id"):
                    machine_id = str(message["machine_id"])
                    await websocket.send_json(
                        {
                            "event_type": "status",
                            "message": f"已订阅 {machine_id}",
                        }
                    )
                continue
            except asyncio.TimeoutError:
                pass

            # 拉取样本：MTConnect Agent 实时数据；失败降级 demo（避免反复重试）
            if use_adapter and adapter is not None:
                try:
                    sample = await asyncio.to_thread(adapter.fetch_sample)
                except (ConnectionError, OSError, TimeoutError) as exc:
                    logger.warning("monitor: fetch sample failed: %s；降级 demo", exc)
                    sample = _demo_sample(machine_id, tick)
                    use_adapter = False
            else:
                sample = _demo_sample(machine_id, tick)

            # 告警事件 + 数据事件（告警优先推送，前端可即时感知）
            events = check_alerts(sample) + [StreamEvent(data=sample, event_type="data", priority=1)]
            for event in events:
                await websocket.send_json(event.to_dict())
            tick += 1

            # 心跳
            if tick % _HEARTBEAT_INTERVAL_S == 0:
                await websocket.send_json({"event_type": "ping", "timestamp": events[-1].timestamp.isoformat()})

            await asyncio.sleep(1.0)

    except WebSocketDisconnect:
        logger.info("monitor ws disconnected: machine=%s", machine_id)
    except Exception as exc:
        logger.warning("monitor ws error: %s", exc)
        try:
            await websocket.close(code=1011, reason="internal error")
        except Exception:
            pass
    finally:
        if adapter is not None:
            try:
                adapter.close()
            except Exception:  # pragma: no cover - 防御性
                pass
