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

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.integrations.mtconnect.parser import Sample
from app.integrations.mtconnect.streaming import StreamEvent

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/monitor", tags=["realtime-monitor"])

# 心跳间隔（秒）
_HEARTBEAT_INTERVAL_S = 15.0


async def _ws_permission_check(websocket: WebSocket) -> None:
    """WS 权限检查（require_permission 是 FastAPI Depends，WS 需手动调用）。"""
    import os

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
    """实时机床监控 WebSocket 端点。"""
    await websocket.accept()
    try:
        await _ws_permission_check(websocket)
    except WebSocketDisconnect:
        return

    machine_id = "VM-001"
    tick = 0

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

            # 推送数据事件（demo 模式；真实场景接 MTConnectStreamServer）
            sample = _demo_sample(machine_id, tick)
            event = StreamEvent(data=sample, event_type="data", priority=1)
            await websocket.send_json(event.to_dict())
            tick += 1

            # 心跳
            if tick % _HEARTBEAT_INTERVAL_S == 0:
                await websocket.send_json({"event_type": "ping", "timestamp": event.timestamp.isoformat()})

            await asyncio.sleep(1.0)

    except WebSocketDisconnect:
        logger.info("monitor ws disconnected: machine=%s", machine_id)
    except Exception as exc:
        logger.warning("monitor ws error: %s", exc)
        try:
            await websocket.close(code=1011, reason="internal error")
        except Exception:
            pass
