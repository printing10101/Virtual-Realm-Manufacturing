"""
OPC UA 客户端实现

用于连接支持 OPC UA 协议的数控机床，实现：
- 机床状态实时监控
- NC 程序远程传输
- 加工参数下发
- 报警信息采集
"""

import asyncio
import logging
from typing import Optional, Dict, Any, Callable
from datetime import datetime

try:
    from asyncua import ua, Client
    from asyncua.common.subscription import SubHandler
    OPCUA_AVAILABLE = True
except ImportError:
    OPCUA_AVAILABLE = False
    logging.warning("OPC UA 依赖未安装，请运行: pip install asyncua")

logger = logging.getLogger(__name__)


class OPCUASubscriptionHandler:
    """OPC UA 数据变更订阅处理器"""

    def __init__(self, callback: Optional[Callable] = None):
        self.callback = callback

    def datachange_notification(self, node, val, data):
        """数据变更通知回调"""
        if self.callback:
            self.callback(node.nodeid.to_string(), val, datetime.now())
        logger.debug(f"OPC UA 数据变更: {node.nodeid.to_string()} = {val}")


class OPCUAClient:
    """
    OPC UA 客户端

    用于连接数控机床的 OPC UA 服务器，实现数据读写和订阅。
    """

    def __init__(self, endpoint: str, username: Optional[str] = None, password: Optional[str] = None):
        """
        初始化 OPC UA 客户端

        Args:
            endpoint: OPC UA 服务器端点，如 "opc.tcp://192.168.1.100:4840"
            username: 认证用户名（可选）
            password: 认证密码（可选）
        """
        if not OPCUA_AVAILABLE:
            raise RuntimeError("OPC UA 依赖未安装，请运行: pip install asyncua")

        self.endpoint = endpoint
        self.username = username
        self.password = password
        self.client: Optional[Client] = None
        self.subscription = None
        self.handler: Optional[OPCUASubscriptionHandler] = None
        self.connected = False

    async def connect(self, timeout: float = 10.0) -> bool:
        """
        连接到 OPC UA 服务器

        Args:
            timeout: 连接超时时间（秒），默认 10 秒

        Returns:
            连接成功返回 True，否则返回 False
        """
        try:
            self.client = Client(url=self.endpoint)
            self.client.timeout = timeout

            if self.username and self.password:
                self.client.set_user(self.username)
                self.client.set_password(self.password)

            await asyncio.wait_for(self.client.connect(), timeout=timeout)
            self.connected = True
            logger.info(f"OPC UA 连接成功: {self.endpoint}")
            return True

        except asyncio.TimeoutError:
            logger.error(f"OPC UA 连接超时 ({timeout}s): {self.endpoint}")
            self.connected = False
            return False
        except Exception as e:
            logger.error(f"OPC UA 连接失败: {e}")
            self.connected = False
            return False

    async def _reconnect_if_needed(self) -> bool:
        """如果连接断开，尝试重新连接。

        Returns:
            连接可用返回 True，否则返回 False
        """
        if not self.connected:
            logger.warning("OPC UA 连接已断开，尝试重新连接...")
            return await self.connect()
        return True

    async def disconnect(self):
        """断开 OPC UA 连接"""
        if self.client:
            await self.client.disconnect()
            self.connected = False
            logger.info("OPC UA 连接已断开")

    async def read_node(self, node_id: str) -> Any:
        """
        读取节点值

        Args:
            node_id: OPC UA 节点 ID，如 "ns=2;s=SpindleSpeed"

        Returns:
            节点当前值
        """
        if not await self._reconnect_if_needed():
            raise RuntimeError("OPC UA 未连接且无法重新连接")

        node = self.client.get_node(node_id)
        value = await node.read_value()
        return value

    async def write_node(self, node_id: str, value: Any):
        """
        写入节点值

        Args:
            node_id: OPC UA 节点 ID
            value: 要写入的值
        """
        if not await self._reconnect_if_needed():
            raise RuntimeError("OPC UA 未连接且无法重新连接")

        node = self.client.get_node(node_id)
        await node.write_value(value)
        logger.info(f"OPC UA 写入: {node_id} = {value}")

    async def subscribe(self, node_ids: list[str], callback: Callable):
        """
        订阅节点数据变更

        Args:
            node_ids: 要订阅的节点 ID 列表
            callback: 数据变更回调函数，签名为 callback(node_id, value, timestamp)
        """
        if not await self._reconnect_if_needed():
            raise RuntimeError("OPC UA 未连接且无法重新连接")

        self.handler = OPCUASubscriptionHandler(callback)
        self.subscription = await self.client.create_subscription(500, self.handler)

        nodes = [self.client.get_node(nid) for nid in node_ids]
        await self.subscription.subscribe_data_change(nodes)
        logger.info(f"OPC UA 已订阅 {len(node_ids)} 个节点")

    async def unsubscribe(self):
        """取消订阅"""
        if self.subscription:
            await self.subscription.delete()
            self.subscription = None
            logger.info("OPC UA 订阅已取消")

    async def get_machine_status(self) -> Dict[str, Any]:
        """
        获取机床状态（标准 OPC UA 机床信息模型）

        Returns:
            包含机床状态信息的字典
        """
        status = {
            "timestamp": datetime.now().isoformat(),
            "connected": self.connected,
        }

        if not self.connected:
            return status

        try:
            # 读取标准机床状态节点（根据实际机床 OPC UA 信息模型调整）
            status.update({
                "spindle_speed": await self.safe_read("ns=2;s=SpindleSpeed"),
                "feed_rate": await self.safe_read("ns=2;s=FeedRate"),
                "x_position": await self.safe_read("ns=2;s=PosX"),
                "y_position": await self.safe_read("ns=2;s=PosY"),
                "z_position": await self.safe_read("ns=2;s=PosZ"),
                "machine_mode": await self.safe_read("ns=2;s=MachineMode"),
                "alarm_active": await self.safe_read("ns=2;s=AlarmActive"),
            })
        except Exception as e:
            logger.error(f"获取机床状态失败: {e}")

        return status

    async def safe_read(self, node_id: str) -> Any:
        """安全读取节点，失败时返回 None"""
        try:
            return await self.read_node(node_id)
        except Exception as e:
            logger.warning(f"Failed to read OPC UA node {node_id}: {e}")
            return None

    async def send_nc_program(self, program_path: str, program_name: str) -> bool:
        """
        发送 NC 程序到机床（通过 OPC UA 文件传输）

        Args:
            program_path: 本地 NC 程序文件路径
            program_name: 机床端存储的程序名

        Returns:
            发送成功返回 True
        """
        if not await self._reconnect_if_needed():
            raise RuntimeError("OPC UA 未连接且无法重新连接")

        try:
            # 读取本地文件
            with open(program_path, 'r', encoding='utf-8') as f:
                program_content = f.read()

            # 写入机床 NC 程序存储节点（根据实际机床信息模型调整）
            program_node = self.client.get_node(f"ns=2;s=NCProgram/{program_name}")
            await program_node.write_value(program_content)

            logger.info(f"NC 程序已发送: {program_name}")
            return True

        except Exception as e:
            logger.error(f"发送 NC 程序失败: {e}")
            return False

    def is_connected(self) -> bool:
        """返回连接状态"""
        return self.connected
