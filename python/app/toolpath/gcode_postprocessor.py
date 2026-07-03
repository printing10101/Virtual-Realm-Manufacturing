"""G-code 后处理器（简化版，向后兼容保留）。

将刀具路径转换为特定机床控制器支持的 G-code。

.. deprecated::
    本模块为早期独立的简化版后处理器，仅支持 fanuc_0i / siemens_840d /
    heidenhain_tnc 三种控制器的硬编码约束（``CONTROLLER_CONSTRAINTS``）。

    **新代码应使用模块化的 ``app.postprocessor`` 包**：
        - ``app.postprocessor.base``：抽象后处理器基类
        - ``app.postprocessor.registry``：控制器注册表（支持 10+ 控制器）
        - ``app.postprocessor.config_loader``：YAML 配置驱动的控制器约束
        - ``app.postprocessor.fanuc`` / ``siemens`` / ``heidenhain`` / ``knd`` /
          ``gsk`` / ``mitsubishi`` / ``hnc`` / ``fagor`` / ``xmachine``

    模块化系统通过 ``config_loader`` 读取 YAML 配置，避免硬编码约束，
    且已由 212 个测试用例覆盖（核心模块 100% 覆盖）。

    本文件保留仅为向后兼容，供 ``verify_all_fixes.py``、
    ``comprehensive_verify_fixes.py`` 及历史集成测试使用，后续应逐步迁移。
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


# 控制器特定约束配置
CONTROLLER_CONSTRAINTS = {
    "fanuc_0i": {
        "max_spindle_speed": 12000,
        "min_spindle_speed": 50,
        "max_feed_rapid": 24000,  # mm/min
        "max_feed_cutting": 10000,
        "max_travel_x": 850.0,
        "max_travel_y": 500.0,
        "max_travel_z": 500.0,
        "program_number_format": "O{:04d}",
        "requires_percent": True,
        "gcode_format": "fanuc",
        "supported_m_codes": {"M00", "M01", "M03", "M04", "M05", "M06", "M08", "M09", "M30"},
        "supported_g_codes": {"G00", "G01", "G02", "G03", "G04", "G17", "G18", "G19", "G20", "G21", "G28", "G40", "G41", "G42", "G43", "G44", "G49", "G54", "G55", "G56", "G57", "G58", "G59", "G80", "G81", "G82", "G83", "G90", "G91", "G94", "G95"},
    },
    "siemens_840d": {
        "max_spindle_speed": 15000,
        "min_spindle_speed": 10,
        "max_feed_rapid": 30000,
        "max_feed_cutting": 15000,
        "max_travel_x": 1000.0,
        "max_travel_y": 600.0,
        "max_travel_z": 600.0,
        "program_number_format": None,  # Siemens uses program names
        "requires_percent": False,
        "gcode_format": "siemens",
        "supported_m_codes": {"M00", "M01", "M02", "M03", "M04", "M05", "M06", "M08", "M09", "M17", "M30"},
        "supported_g_codes": {"G00", "G01", "G02", "G03", "G04", "G17", "G18", "G19", "G71", "G70", "G40", "G41", "G42", "G53", "G54", "G55", "G56", "G57", "G58", "G59", "G90", "G91", "G94", "G95"},
    },
    "heidenhain_tnc": {
        "max_spindle_speed": 20000,
        "min_spindle_speed": 20,
        "max_feed_rapid": 24000,
        "max_feed_cutting": 12000,
        "max_travel_x": 800.0,
        "max_travel_y": 500.0,
        "max_travel_z": 500.0,
        "program_number_format": None,
        "requires_percent": False,
        "gcode_format": "heidenhain",
        "supported_m_codes": {"M00", "M01", "M02", "M03", "M04", "M05", "M06", "M08", "M09", "M30"},
        "supported_g_codes": {"G00", "G01", "G02", "G03", "G04", "G17", "G18", "G19", "G40", "G41", "G42", "G53", "G54", "G55", "G56", "G57", "G58", "G59", "G90", "G91"},
    },
    "default": {
        "max_spindle_speed": 24000,
        "min_spindle_speed": 50,
        "max_feed_rapid": 24000,
        "max_feed_cutting": 10000,
        "max_travel_x": 1000.0,
        "max_travel_y": 600.0,
        "max_travel_z": 600.0,
        "program_number_format": "O{:04d}",
        "requires_percent": True,
        "gcode_format": "default",
        "supported_m_codes": set(),
        "supported_g_codes": set(),
    },
}


class GCodePostProcessor:
    """G-code 后处理器。"""

    def __init__(self, machine_config: dict[str, Any] | None = None) -> None:
        """初始化后处理器。

        Args:
            machine_config: 机床配置参数
        """
        self._machine_config = machine_config or {}
        self._gcode_lines: list[str] = []
        self._validation_errors: list[str] = []
        self._validation_warnings: list[str] = []

    def set_machine_config(self, config: dict[str, Any]) -> None:
        """设置机床配置。

        Args:
            config: 机床配置参数
        """
        self._machine_config = config
        logger.info("Machine configuration updated")

    def get_controller_constraints(self) -> dict[str, Any]:
        """获取当前控制器的约束配置。

        Returns:
            约束配置字典
        """
        controller = self._machine_config.get("controller", "default")
        return CONTROLLER_CONSTRAINTS.get(controller, CONTROLLER_CONSTRAINTS["default"])

    def validate_gcode_line(self, line: str, line_number: int) -> bool:
        """验证单行G代码是否符合机床约束。

        Args:
            line: G代码行
            line_number: 行号

        Returns:
            验证是否通过
        """
        constraints = self.get_controller_constraints()
        line = line.strip()

        if not line or line.startswith("%") or line.startswith("("):
            return True

        # 提取G代码和M代码
        import re
        g_codes = re.findall(r'G\d+', line)
        m_codes = re.findall(r'M\d+', line)

        # 验证G代码
        supported_g = constraints.get("supported_g_codes", set())
        if supported_g:
            for g_code in g_codes:
                if g_code not in supported_g:
                    error_msg = f"行{line_number}: 不支持的G代码 {g_code}"
                    self._validation_errors.append(error_msg)
                    logger.warning(error_msg)

        # 验证M代码
        supported_m = constraints.get("supported_m_codes", set())
        if supported_m:
            for m_code in m_codes:
                if m_code not in supported_m:
                    error_msg = f"行{line_number}: 不支持的M代码 {m_code}"
                    self._validation_errors.append(error_msg)
                    logger.warning(error_msg)

        # 验证主轴转速
        s_match = re.search(r'S(\d+)', line)
        if s_match:
            speed = int(s_match.group(1))
            max_speed = constraints.get("max_spindle_speed", 24000)
            min_speed = constraints.get("min_spindle_speed", 50)
            if speed > max_speed:
                error_msg = f"行{line_number}: 主轴转速{speed}RPM超过最大限制{max_speed}RPM"
                self._validation_errors.append(error_msg)
                logger.error(error_msg)
            elif speed < min_speed:
                warn_msg = f"行{line_number}: 主轴转速{speed}RPM低于最小推荐值{min_speed}RPM"
                self._validation_warnings.append(warn_msg)
                logger.warning(warn_msg)

        # 验证进给速度
        f_match = re.search(r'F(\d+\.?\d*)', line)
        if f_match:
            feed = float(f_match.group(1))
            max_feed = constraints.get("max_feed_cutting", 10000)
            if "G00" in line or "G0 " in line:
                max_feed = constraints.get("max_feed_rapid", 24000)
            if feed > max_feed:
                error_msg = f"行{line_number}: 进给速度{feed:.1f}mm/min超过最大限制{max_feed}mm/min"
                self._validation_errors.append(error_msg)
                logger.error(error_msg)

        # 验证坐标范围
        x_match = re.search(r'X([+-]?\d+\.?\d*)', line)
        y_match = re.search(r'Y([+-]?\d+\.?\d*)', line)
        z_match = re.search(r'Z([+-]?\d+\.?\d*)', line)

        max_x = constraints.get("max_travel_x", 1000.0)
        max_y = constraints.get("max_travel_y", 600.0)
        max_z = constraints.get("max_travel_z", 600.0)

        if x_match and abs(float(x_match.group(1))) > max_x:
            error_msg = f"行{line_number}: X坐标{x_match.group(1)}超出行程范围[{-max_x}, {max_x}]"
            self._validation_errors.append(error_msg)
            logger.error(error_msg)

        if y_match and abs(float(y_match.group(1))) > max_y:
            error_msg = f"行{line_number}: Y坐标{y_match.group(1)}超出行程范围[{-max_y}, {max_y}]"
            self._validation_errors.append(error_msg)
            logger.error(error_msg)

        if z_match and abs(float(z_match.group(1))) > max_z:
            error_msg = f"行{line_number}: Z坐标{z_match.group(1)}超出行程范围[{-max_z}, {max_z}]"
            self._validation_errors.append(error_msg)
            logger.error(error_msg)

        return len([e for e in self._validation_errors if f"行{line_number}:" in e]) == 0

    def validate_gcode(self, gcode: str) -> dict[str, Any]:
        """验证完整G代码程序。

        Args:
            gcode: 完整G代码字符串

        Returns:
            验证结果字典
        """
        self._validation_errors = []
        self._validation_warnings = []

        lines = gcode.split('\n')
        for i, line in enumerate(lines, 1):
            self.validate_gcode_line(line, i)

        return {
            "valid": len(self._validation_errors) == 0,
            "errors": self._validation_errors,
            "warnings": self._validation_warnings,
            "total_lines": len(lines),
        }

    def get_validation_report(self) -> str:
        """获取验证报告。

        Returns:
            验证报告字符串
        """
        report = []
        report.append("=" * 60)
        report.append("G代码验证报告")
        report.append("=" * 60)

        if self._validation_errors:
            report.append(f"\n错误 ({len(self._validation_errors)}):")
            for err in self._validation_errors:
                report.append(f"  ❌ {err}")
        else:
            report.append("\n✓ 无错误")

        if self._validation_warnings:
            report.append(f"\n警告 ({len(self._validation_warnings)}):")
            for warn in self._validation_warnings:
                report.append(f"  ⚠ {warn}")
        else:
            report.append("\n✓ 无警告")

        report.append("\n" + "=" * 60)
        return "\n".join(report)

    def generate_header(self) -> str:
        """生成 G-code 头部。

        Returns:
            G-code 头部字符串
        """
        lines = [
            "%",
            "O0001 (Generated by CAM system)",
            "(Units: MM)",
            "(Toolpath: Operation 1)",
        ]

        # Add machine-specific header
        if self._machine_config.get("controller") == "fanuc":
            lines.append("G90 G94 G17 G21")  # Absolute, feed/min, XY plane, metric
        elif self._machine_config.get("controller") == "siemens":
            lines.append("G90 G94 G71")  # Absolute, feed/min, metric

        return "\n".join(lines)

    def generate_footer(self) -> str:
        """生成 G-code 尾部。

        Returns:
            G-code 尾部字符串
        """
        lines = [
            "M5 (Spindle stop)",
            "M9 (Coolant off)",
            "G91 G28 Z0 (Return Z to home)",
            "G28 X0 Y0 (Return XY to home)",
            "M30 (Program end)",
            "%",
        ]
        return "\n".join(lines)

    def convert_toolpath(
        self,
        toolpath: Any,
        include_rapid: bool = True,
    ) -> str:
        """将刀具路径转换为 G-code。

        Args:
            toolpath: 刀具路径数据，支持以下格式：
                - dict: 包含 'moves' 列表，每个 move 包含 type/params
                - list: 直接包含移动指令的列表
                - object: 具有 to_gcode() 方法的对象
            include_rapid: 是否包含快速移动

        Returns:
            G-code 字符串
        """
        self._gcode_lines = []

        # Generate header
        self._gcode_lines.append(self.generate_header())

        # 处理不同类型的刀具路径数据
        if isinstance(toolpath, dict):
            moves = toolpath.get("moves", [])
            self._convert_moves(moves, include_rapid)
        elif isinstance(toolpath, list):
            self._convert_moves(toolpath, include_rapid)
        elif hasattr(toolpath, "to_gcode"):
            # 对象提供了 to_gcode 方法
            gcode_content = toolpath.to_gcode()
            if gcode_content:
                self._gcode_lines.append(gcode_content)
        elif hasattr(toolpath, "moves"):
            # 对象有 moves 属性
            moves = toolpath.moves
            if callable(moves):
                moves = moves()
            self._convert_moves(moves, include_rapid)
        else:
            logger.warning("无法识别的刀具路径格式: %s", type(toolpath).__name__)

        # Generate footer
        self._gcode_lines.append(self.generate_footer())

        return "\n".join(self._gcode_lines)

    def _convert_moves(self, moves: list, include_rapid: bool) -> None:
        """将移动指令列表转换为 G-code。

        Args:
            moves: 移动指令列表
            include_rapid: 是否包含快速移动
        """
        for move in moves:
            if not isinstance(move, dict):
                continue

            move_type = move.get("type", "").lower()
            params = move.get("params", {})

            if move_type == "rapid" and include_rapid:
                # 快速移动 G00
                x = params.get("x", 0)
                y = params.get("y", 0)
                z = params.get("z", 0)
                self._gcode_lines.append(f"G00 X{x:.3f} Y{y:.3f} Z{z:.3f}")

            elif move_type == "linear":
                # 直线插补 G01
                x = params.get("x", 0)
                y = params.get("y", 0)
                z = params.get("z", 0)
                feed = params.get("feed", 100)
                self._gcode_lines.append(f"G01 X{x:.3f} Y{y:.3f} Z{z:.3f} F{feed}")

            elif move_type == "arc_cw":
                # 顺时针圆弧 G02
                x = params.get("x", 0)
                y = params.get("y", 0)
                z = params.get("z", 0)
                i = params.get("i", 0)
                j = params.get("j", 0)
                feed = params.get("feed", 100)
                self._gcode_lines.append(f"G02 X{x:.3f} Y{y:.3f} Z{z:.3f} I{i:.3f} J{j:.3f} F{feed}")

            elif move_type == "arc_ccw":
                # 逆时针圆弧 G03
                x = params.get("x", 0)
                y = params.get("y", 0)
                z = params.get("z", 0)
                i = params.get("i", 0)
                j = params.get("j", 0)
                feed = params.get("feed", 100)
                self._gcode_lines.append(f"G03 X{x:.3f} Y{y:.3f} Z{z:.3f} I{i:.3f} J{j:.3f} F{feed}")

            elif move_type == "spindle_on":
                # 主轴开启
                speed = params.get("speed", 1000)
                self._gcode_lines.append(f"S{speed} M03")

            elif move_type == "spindle_off":
                # 主轴关闭
                self._gcode_lines.append("M05")

            elif move_type == "coolant_on":
                # 冷却液开启
                self._gcode_lines.append("M08")

            elif move_type == "coolant_off":
                # 冷却液关闭
                self._gcode_lines.append("M09")

            elif move_type == "tool_change":
                # 换刀
                tool_num = params.get("tool", 1)
                self._gcode_lines.append(f"T{tool_num:02d} M06")

            elif move_type == "comment":
                # 注释
                text = params.get("text", "")
                self._gcode_lines.append(f"({text})")

    def save_to_file(self, gcode: str, output_path: str) -> bool:
        """保存 G-code 到文件。

        Args:
            gcode: G-code 字符串
            output_path: 输出文件路径

        Returns:
            保存是否成功
        """
        try:
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(gcode)
            logger.info("G-code saved to: %s", output_path)
            return True
        except (OSError, TypeError, ValueError) as e:
            logger.error("Failed to save G-code: %s", e, exc_info=True)
            return False
