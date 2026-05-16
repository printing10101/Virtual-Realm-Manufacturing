"""CNC后处理器抽象基类——定义统一的G代码生成接口规范。

所有控制器专用后处理器必须继承此基类并实现全部抽象方法，
确保上层调用方无需关注控制器差异。
"""

from __future__ import annotations

import datetime
from abc import ABC, abstractmethod
from typing import Tuple


class BasePostProcessor(ABC):
    """CNC后处理器抽象基类。

    为不同CNC控制器提供统一的NC代码生成接口。
    子类需实现所有抽象方法以适配特定控制器的G代码方言。

    Attributes:
        decimal_places: 数值保留的小数位数
        safe_z_height: 安全Z轴高度(mm)
        rapid_feed: 快速进给速度(mm/min)
    """

    def __init__(
        self,
        decimal_places: int = 3,
        safe_z_height: float = 50.0,
        rapid_feed: float = 10000,
    ) -> None:
        self.decimal_places = decimal_places
        self.safe_z_height = safe_z_height
        self.rapid_feed = rapid_feed

    def _fmt(self, value: float) -> str:
        """将数值格式化为指定小数位数的字符串。"""
        return f"{value:.{self.decimal_places}f}"

    @abstractmethod
    def format_header(self, program_number: int = 1) -> str:
        """生成控制器特定的程序头。

        包含程序号、日期、安全启动指令（如取消补偿、回参考点等）。

        Args:
            program_number: 程序号，默认1

        Returns:
            程序头NC代码字符串
        """

    @abstractmethod
    def format_tool_change(
        self,
        tool_id: int,
        length_comp: float = 0.0,
        radius_comp: float = 0.0,
    ) -> str:
        """生成换刀指令。

        Args:
            tool_id: 刀具ID/编号
            length_comp: 刀具长度补偿值
            radius_comp: 刀具半径补偿值

        Returns:
            换刀NC代码字符串
        """

    @abstractmethod
    def format_arc(
        self,
        start: Tuple[float, float, float],
        end: Tuple[float, float, float],
        center: Tuple[float, float, float],
        clockwise: bool = True,
    ) -> str:
        """生成圆弧插补指令。

        Args:
            start: 起点坐标 (x, y, z)
            end: 终点坐标 (x, y, z)
            center: 圆心坐标 (x, y, z)
            clockwise: True为顺时针(G02)，False为逆时针(G03)

        Returns:
            圆弧插补NC代码字符串
        """

    @abstractmethod
    def format_coolant(self, state: str) -> str:
        """生成冷却液控制指令。

        Args:
            state: 冷却液状态，"on"开启，"off"关闭

        Returns:
            冷却液控制NC代码字符串
        """

    @abstractmethod
    def format_tool_compensation(
        self,
        length_offset: int = 0,
        radius_offset: int = 0,
    ) -> str:
        """生成刀具长度和半径补偿指令。

        Args:
            length_offset: 长度补偿寄存器号
            radius_offset: 半径补偿寄存器号

        Returns:
            刀具补偿NC代码字符串
        """

    @abstractmethod
    def format_cycle_drill(
        self,
        x: float,
        y: float,
        z: float,
        depth: float,
        dwell: float = 0.0,
    ) -> str:
        """生成钻孔固定循环指令。

        Args:
            x: 孔位X坐标
            y: 孔位Y坐标
            z: 孔位Z坐标（起始高度）
            depth: 钻孔深度
            dwell: 孔底暂停时间(秒)

        Returns:
            钻孔循环NC代码字符串
        """

    @abstractmethod
    def format_footer(self) -> str:
        """生成程序结束部分。

        包含主轴停止、冷却液关闭、回参考点、程序结束等指令。

        Returns:
            程序结束NC代码字符串
        """

    @staticmethod
    def _date_string() -> str:
        """获取当前日期字符串，用于程序头注释。"""
        return datetime.date.today().strftime("%Y-%m-%d")
