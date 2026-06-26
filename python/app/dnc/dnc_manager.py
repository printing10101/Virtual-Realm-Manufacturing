"""
DNC 管理器

统一管理 OPC UA 和 MTConnect 连接，提供高层 API。
"""

import logging
import threading
from typing import Optional, Dict, Any, List
from datetime import datetime
from enum import Enum

from .opcu_client import OPCUAClient
from .mtconnect_client import MTConnectClient

logger = logging.getLogger(__name__)


class ProtocolType(str, Enum):
    OPC_UA = "opcua"
    MTCONNECT = "mtconnect"


class DNCManager:
    """DNC 机床通信管理器"""

    def __init__(self):
        self.connections: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.Lock()

    async def add_machine(
        self,
        machine_id: str,
        protocol: ProtocolType,
        endpoint: str,
        **kwargs
    ) -> bool:
        """添加机床连接"""
        try:
            if protocol == ProtocolType.OPC_UA:
                client = OPCUAClient(
                    endpoint=endpoint,
                    username=kwargs.get("username"),
                    password=kwargs.get("password"),
                )
                success = await client.connect()
            elif protocol == ProtocolType.MTCONNECT:
                client = MTConnectClient(
                    agent_url=endpoint,
                    device_name=kwargs.get("device_name", "Device"),
                )
                success = await client.connect()
            else:
                logger.error(f"不支持的协议: {protocol}")
                return False

            if success:
                with self._lock:
                    self.connections[machine_id] = {
                        "client": client,
                        "protocol": protocol,
                        "endpoint": endpoint,
                        "connected_at": datetime.now().isoformat(),
                    }
                logger.info(f"机床 {machine_id} 已添加 ({protocol.value})")
            return success

        except Exception as e:
            logger.error(f"添加机床失败: {e}")
            raise

    async def remove_machine(self, machine_id: str):
        """移除机床连接"""
        with self._lock:
            if machine_id not in self.connections:
                return
            conn = self.connections[machine_id]
            del self.connections[machine_id]
        
        try:
            await conn["client"].disconnect()
            logger.info(f"机床 {machine_id} 已移除")
        except Exception as e:
            logger.error(f"断开机床 {machine_id} 连接失败: {e}")
            raise

    async def get_machine_status(self, machine_id: str) -> Dict[str, Any]:
        """获取机床状态"""
        if machine_id not in self.connections:
            return {"error": f"机床 {machine_id} 未连接"}

        client = self.connections[machine_id]["client"]
        protocol = self.connections[machine_id]["protocol"]

        if protocol == ProtocolType.OPC_UA:
            return await client.get_machine_status()
        else:
            return await client.get_current_status()

    async def send_nc_program(self, machine_id: str, program_path: str, program_name: str) -> bool:
        """发送 NC 程序到机床"""
        if machine_id not in self.connections:
            logger.error(f"机床 {machine_id} 未连接")
            return False

        client = self.connections[machine_id]["client"]
        protocol = self.connections[machine_id]["protocol"]

        if protocol == ProtocolType.OPC_UA:
            return await client.send_nc_program(program_path, program_name)
        else:
            logger.warning("MTConnect 不支持直接传输 NC 程序")
            return False

    async def get_all_machines_status(self) -> Dict[str, Dict[str, Any]]:
        """获取所有机床状态"""
        result = {}
        for machine_id in self.connections:
            result[machine_id] = await self.get_machine_status(machine_id)
        return result

    def list_machines(self) -> List[Dict[str, str]]:
        """列出所有已连接的机床"""
        return [
            {
                "machine_id": mid,
                "protocol": conn["protocol"].value,
                "endpoint": conn["endpoint"],
                "connected_at": conn["connected_at"],
            }
            for mid, conn in self.connections.items()
        ]

    async def disconnect_all(self):
        """断开所有连接"""
        for machine_id in list(self.connections.keys()):
            await self.remove_machine(machine_id)


# 全局单例
dnc_manager = DNCManager()
