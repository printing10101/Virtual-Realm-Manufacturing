"""
MTConnect 客户端实现

用于连接 MTConnect Agent，实现：
- 机床状态数据采集
- 主轴转速/进给速度监控
- 加工状态跟踪
- 报警信息获取
"""

import logging
import xml.etree.ElementTree as ET
from typing import Optional, Dict, Any
from datetime import datetime
import httpx

logger = logging.getLogger(__name__)


class MTConnectClient:
    """
    MTConnect 客户端

    用于连接 MTConnect Agent 并采集机床数据。
    """

    def __init__(self, agent_url: str, device_name: str = "Device"):
        """
        初始化 MTConnect 客户端

        Args:
            agent_url: MTConnect Agent URL，如 "http://192.168.1.100:5000"
            device_name: 设备名称
        """
        self.agent_url = agent_url.rstrip('/')
        self.device_name = device_name
        self.client: Optional[httpx.AsyncClient] = None
        self.connected = False
        self.sequence = 0

    async def __aenter__(self):
        """异步上下文管理器入口"""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        await self.disconnect()

    async def connect(self) -> bool:
        """
        连接到 MTConnect Agent

        Returns:
            连接成功返回 True
        """
        try:
            self.client = httpx.AsyncClient(timeout=10.0)
            # 测试连接
            response = await self.client.get(f"{self.agent_url}/probe")
            if response.status_code == 200:
                self.connected = True
                logger.info(f"MTConnect 连接成功: {self.agent_url}")
                return True
            else:
                logger.error(f"MTConnect 连接失败: HTTP {response.status_code}")
                await self.client.aclose()
                self.client = None
                return False

        except Exception as e:
            logger.error(f"MTConnect 连接失败: {e}")
            if self.client:
                await self.client.aclose()
                self.client = None
            self.connected = False
            return False

    async def disconnect(self):
        """断开连接"""
        if self.client:
            await self.client.aclose()
            self.connected = False
            logger.info("MTConnect 连接已断开")

    async def get_current_status(self) -> Dict[str, Any]:
        """
        获取当前机床状态

        Returns:
            包含机床状态信息的字典
        """
        if not self.connected:
            return {"connected": False, "timestamp": datetime.now().isoformat()}

        try:
            response = await self.client.get(
                f"{self.agent_url}/current",
                params={"path": f"//Device[@name='{self.device_name}']"}
            )

            if response.status_code != 200:
                return {"connected": False, "error": f"HTTP {response.status_code}"}

            return self._parse_current_response(response.text)

        except Exception as e:
            logger.error(f"获取 MTConnect 状态失败: {e}")
            return {"connected": False, "error": str(e)}

    def _parse_current_response(self, xml_content: str) -> Dict[str, Any]:
        """解析 MTConnect Current 响应"""
        status = {
            "connected": True,
            "timestamp": datetime.now().isoformat(),
        }

        try:
            root = ET.fromstring(xml_content)
            namespaces = {
                'mt': 'urn:mtconnect.org:MTConnect:2.0',
                'm': 'urn:mtconnect.org:MTConnect:2.0'
            }

            # 提取关键数据项
            data_items = {
                'spindle_speed': ('SpindleSpeed', 'ACTUAL'),
                'feed_rate': ('PathFeedrate', 'ACTUAL'),
                'x_position': ('Xabs', 'ACTUAL'),
                'y_position': ('Yabs', 'ACTUAL'),
                'z_position': ('Zabs', 'ACTUAL'),
                'execution_mode': ('Execution', None),
                'controller_mode': ('ControllerMode', None),
                'availability': ('Availability', None),
            }

            for key, (item_type, sub_type) in data_items.items():
                value = self._find_data_item(root, item_type, sub_type, namespaces)
                if value is not None:
                    status[key] = value

        except Exception as e:
            logger.error(f"解析 MTConnect 响应失败: {e}")

        return status

    def _find_data_item(self, root: ET.Element, item_type: str, sub_type: Optional[str], namespaces: Dict) -> Optional[Any]:
        """查找特定类型的数据项"""
        # 简化实现，实际需要根据 MTConnect 标准解析
        for elem in root.iter():
            if item_type in elem.tag:
                if sub_type is None or elem.get('subType') == sub_type:
                    return elem.text
        return None

    async def get_alarms(self) -> list[Dict[str, Any]]:
        """
        获取机床报警信息

        Returns:
            报警信息列表
        """
        if not self.connected:
            return []

        try:
            response = await self.client.get(
                f"{self.agent_url}/current",
                params={"path": f"//Device[@name='{self.device_name}']//Condition"}
            )

            if response.status_code != 200:
                return []

            return self._parse_alarms(response.text)

        except Exception as e:
            logger.error(f"获取报警信息失败: {e}")
            return []

    def _parse_alarms(self, xml_content: str) -> list[Dict[str, Any]]:
        """解析报警信息"""
        alarms = []
        try:
            root = ET.fromstring(xml_content)
            for elem in root.iter():
                if 'Fault' in elem.tag or 'Warning' in elem.tag:
                    alarms.append({
                        "type": "Fault" if "Fault" in elem.tag else "Warning",
                        "code": elem.get('code', ''),
                        "message": elem.text or '',
                        "timestamp": datetime.now().isoformat(),
                    })
        except Exception as e:
            logger.error(f"解析报警信息失败: {e}")

        return alarms

    async def send_nc_program(self, program_content: str, program_name: str) -> bool:
        """
        发送 NC 程序到机床（通过 MTConnect 命令）

        注意：MTConnect 标准不直接支持程序传输，
        实际实现需要机床厂商特定的扩展或配合其他协议。

        Args:
            program_content: NC 程序内容
            program_name: 程序名称

        Returns:
            发送成功返回 True
        """
        logger.warning("MTConnect 标准不支持直接传输 NC 程序，建议使用 OPC UA 或厂商特定接口")
        return False

    def is_connected(self) -> bool:
        """返回连接状态"""
        return self.connected
