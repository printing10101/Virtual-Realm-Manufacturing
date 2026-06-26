"""DNC 传输核心实现

本模块提供 DNC (Direct Numerical Control) 传输功能，支持通过串口 (RS232) 和 TCP Socket
发送 G-code 到机床。支持 Fanuc、Siemens、Heidenhain 三种控制器类型。

主要功能:
- 串口传输: 使用 pyserial 库（可选依赖）
- TCP 传输: 使用标准库 socket
- 控制器协议适配: 根据不同控制器类型添加相应的头部和尾部标记
"""

from __future__ import annotations

import logging
import socket
import time
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Optional

# pyserial 是可选依赖，只在需要串口时导入
try:
    import serial
    SERIAL_AVAILABLE = True
except ImportError:
    SERIAL_AVAILABLE = False

logger = logging.getLogger(__name__)


class DNCStatus(Enum):
    """DNC 传输状态枚举"""
    IDLE = "idle"
    CONNECTING = "connecting"
    TRANSFERRING = "transferring"
    COMPLETE = "complete"
    ERROR = "error"


class ControllerType(Enum):
    """CNC 控制器类型"""
    FANUC = "fanuc"
    SIEMENS = "siemens"
    HEIDENHAIN = "heidenhain"


class Protocol(Enum):
    """传输协议类型"""
    SERIAL = "serial"
    TCP = "tcp"


@dataclass
class DNCConfig:
    """DNC 传输配置"""
    controller_type: ControllerType = ControllerType.FANUC
    protocol: Protocol = Protocol.TCP
    host: str = "localhost"
    port: int = 8193  # Fanuc 默认端口
    baud_rate: int = 9600
    timeout: float = 30.0  # 传输超时（秒）
    chunk_size: int = 1024  # 每次发送的字节数
    tcp_send_delay: float = 0.01  # TCP 发送间隔（秒），避免机床缓冲区溢出
    serial_send_delay: float = 0.05  # 串口发送间隔（秒），等待机床处理


@dataclass
class DNCTarget:
    """DNC 传输目标"""
    host: str
    port: int
    protocol: Protocol
    controller_type: ControllerType
    baud_rate: int = 9600


@dataclass
class DNCResult:
    """DNC 传输结果"""
    success: bool
    bytes_sent: int
    duration_seconds: float
    error_message: Optional[str] = None


class DNCTransfer:
    """DNC 传输核心类
    
    支持通过串口和 TCP 发送 G-code 到机床。
    
    示例::
    
        transfer = DNCTransfer()
        target = DNCTarget(
            host="192.168.1.100",
            port=8193,
            protocol=Protocol.TCP,
            controller_type=ControllerType.FANUC
        )
        result = transfer.send_file(Path("program.nc"), target)
    """
    
    def __init__(self, config: Optional[DNCConfig] = None) -> None:
        """初始化 DNC 传输模块
        
        Args:
            config: DNC 配置，如果未提供则使用默认配置
        """
        self.config = config or DNCConfig()
        self._status = DNCStatus.IDLE
        self._socket: Optional[socket.socket] = None
        self._serial: Optional["serial.Serial"] = None
        
    @property
    def status(self) -> DNCStatus:
        """获取当前传输状态"""
        return self._status
    
    def send_gcode(self, gcode: str, target: DNCTarget) -> DNCResult:
        """发送 G-code 字符串到目标机床
        
        Args:
            gcode: G-code 内容字符串
            target: 传输目标配置
            
        Returns:
            DNCResult: 传输结果
        """
        start_time = time.time()
        bytes_sent = 0
        
        try:
            self._status = DNCStatus.CONNECTING
            logger.info("开始连接到 %s:%s (协议: %s)", 
                       target.host, target.port, target.protocol.value)
            
            # 建立连接
            if target.protocol == Protocol.TCP:
                self._connect_tcp(target)
            elif target.protocol == Protocol.SERIAL:
                self._connect_serial(target)
            else:
                raise ValueError(f"不支持的协议: {target.protocol}")
            
            self._status = DNCStatus.TRANSFERRING
            logger.info("连接成功，开始传输 G-code")
            
            # 准备 G-code（添加控制器特定的头部和尾部）
            prepared_gcode = self._prepare_gcode(gcode, target.controller_type)
            
            # 发送数据
            if target.protocol == Protocol.TCP:
                bytes_sent = self._send_tcp(prepared_gcode.encode("utf-8"))
            else:
                bytes_sent = self._send_serial(prepared_gcode.encode("utf-8"))
            
            self._status = DNCStatus.COMPLETE
            duration = time.time() - start_time
            logger.info("传输完成: %d 字节, 耗时 %.2f 秒", bytes_sent, duration)
            
            return DNCResult(
                success=True,
                bytes_sent=bytes_sent,
                duration_seconds=duration
            )
            
        except Exception as e:
            self._status = DNCStatus.ERROR
            duration = time.time() - start_time
            error_msg = f"传输失败: {str(e)}"
            logger.error(error_msg)
            
            return DNCResult(
                success=False,
                bytes_sent=bytes_sent,
                duration_seconds=duration,
                error_message=error_msg
            )
        finally:
            self._disconnect()
    
    def send_file(self, file_path: Path, target: DNCTarget) -> DNCResult:
        """发送 G-code 文件到目标机床
        
        Args:
            file_path: G-code 文件路径
            target: 传输目标配置
            
        Returns:
            DNCResult: 传输结果
        """
        logger.info("读取文件: %s", file_path)
        
        if not file_path.exists():
            return DNCResult(
                success=False,
                bytes_sent=0,
                duration_seconds=0.0,
                error_message=f"文件不存在: {file_path}"
            )
        
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                gcode = f.read()
            return self.send_gcode(gcode, target)
        except UnicodeDecodeError:
            # 尝试使用其他编码
            with open(file_path, "r", encoding="gbk") as f:
                gcode = f.read()
            return self.send_gcode(gcode, target)
        except Exception as e:
            return DNCResult(
                success=False,
                bytes_sent=0,
                duration_seconds=0.0,
                error_message=f"读取文件失败: {str(e)}"
            )
    
    def test_connection(self, target: DNCTarget) -> bool:
        """测试与目标机床的连接
        
        Args:
            target: 传输目标配置
            
        Returns:
            bool: 连接是否成功
        """
        try:
            self._status = DNCStatus.CONNECTING
            logger.info("测试连接到 %s:%s", target.host, target.port)
            
            if target.protocol == Protocol.TCP:
                self._connect_tcp(target)
            elif target.protocol == Protocol.SERIAL:
                self._connect_serial(target)
            else:
                raise ValueError(f"不支持的协议: {target.protocol}")
            
            self._disconnect()
            self._status = DNCStatus.IDLE
            logger.info("连接测试成功")
            return True
            
        except Exception as e:
            self._status = DNCStatus.ERROR
            logger.error("连接测试失败: %s", str(e))
            self._disconnect()
            return False
    
    def _connect_tcp(self, target: DNCTarget) -> None:
        """建立 TCP 连接"""
        try:
            self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._socket.settimeout(self.config.timeout)
            self._socket.connect((target.host, target.port))
            logger.debug("TCP 连接已建立")
        except socket.error as e:
            raise ConnectionError(f"TCP 连接失败: {str(e)}")
    
    def _connect_serial(self, target: DNCTarget) -> None:
        """建立串口连接"""
        if not SERIAL_AVAILABLE:
            raise RuntimeError(
                "pyserial 未安装。请运行: pip install pyserial"
            )
        
        try:
            # 对于串口，host 应该是串口名称（如 COM1 或 /dev/ttyUSB0）
            self._serial = serial.Serial(
                port=target.host,
                baudrate=target.baud_rate,
                timeout=self.config.timeout,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                xonxoff=True  # 启用 XON/XOFF 流控
            )
            logger.debug("串口连接已建立: %s @ %d", target.host, target.baud_rate)
        except serial.SerialException as e:
            raise ConnectionError(f"串口连接失败: {str(e)}")
    
    def _send_tcp(self, data: bytes) -> int:
        """通过 TCP 发送数据"""
        if not self._socket:
            raise RuntimeError("TCP 连接未建立")
        
        total_sent = 0
        data_len = len(data)
        
        while total_sent < data_len:
            chunk = data[total_sent:total_sent + self.config.chunk_size]
            sent = self._socket.send(chunk)
            if sent == 0:
                raise ConnectionError("TCP 连接中断")
            total_sent += sent
            logger.debug("已发送 %d/%d 字节", total_sent, data_len)
            
            # 使用配置的延迟时间，避免机床缓冲区溢出
            if self.config.tcp_send_delay > 0:
                time.sleep(self.config.tcp_send_delay)
        
        return total_sent
    
    def _send_serial(self, data: bytes) -> int:
        """通过串口发送数据"""
        if not self._serial:
            raise RuntimeError("串口连接未建立")
        
        total_sent = 0
        data_len = len(data)
        
        while total_sent < data_len:
            chunk = data[total_sent:total_sent + self.config.chunk_size]
            sent = self._serial.write(chunk)
            total_sent += sent
            logger.debug("已发送 %d/%d 字节", total_sent, data_len)
            
            # 使用配置的延迟时间，等待机床处理
            if self.config.serial_send_delay > 0:
                time.sleep(self.config.serial_send_delay)
        
        return total_sent
    
    def _disconnect(self) -> None:
        """断开所有连接"""
        if self._socket:
            try:
                self._socket.close()
                logger.debug("TCP 连接已关闭")
            except Exception as e:
                logger.warning("关闭 TCP 连接时出错: %s", e)
            finally:
                self._socket = None
        
        if self._serial:
            try:
                self._serial.close()
                logger.debug("串口连接已关闭")
            except Exception as e:
                logger.warning("关闭串口连接时出错: %s", e)
            finally:
                self._serial = None
        
        self._status = DNCStatus.IDLE
    
    def _prepare_gcode(self, gcode: str, controller_type: ControllerType) -> str:
        """根据控制器类型准备 G-code
        
        添加控制器特定的头部和尾部标记。
        
        Args:
            gcode: 原始 G-code 内容
            controller_type: 控制器类型
            
        Returns:
            str: 处理后的 G-code
        """
        # 清理输入
        gcode = gcode.strip()
        
        if controller_type == ControllerType.FANUC:
            # Fanuc 使用 % 开始和结束
            if not gcode.startswith("%"):
                gcode = "%" + gcode
            if not gcode.endswith("%"):
                gcode = gcode + "%"
            # 确保以换行符结束
            if not gcode.endswith("\n"):
                gcode += "\n"
                
        elif controller_type == ControllerType.SIEMENS:
            # Siemens 使用 % 开始和结束
            if not gcode.startswith("%"):
                gcode = "%" + gcode
            if not gcode.endswith("%"):
                gcode = gcode + "%"
            if not gcode.endswith("\n"):
                gcode += "\n"
                
        elif controller_type == ControllerType.HEIDENHAIN:
            # Heidenhain 使用 BEGIN PGM 和 END PGM
            if not gcode.startswith("BEGIN PGM"):
                gcode = "BEGIN PGM\n" + gcode
            if not gcode.endswith("END PGM"):
                if not gcode.endswith("\n"):
                    gcode += "\n"
                gcode += "END PGM\n"
        
        return gcode


__all__ = [
    "DNCTransfer",
    "DNCConfig",
    "DNCStatus",
    "DNCTarget",
    "DNCResult",
    "ControllerType",
    "Protocol",
]
