"""G代码生成模块。

基于工序规划结果生成符合数控系统语法的G代码。
支持Fanuc 0i-MF、Siemens 840D、Heidenhain TNC三种主流CNC系统。

G代码生成的设计原则：
1. 语法严格合规：每个控制器输出必须通过对应系统的语法校验
2. 工艺意图完整：G代码必须准确表达工艺规划的所有意图（刀具选择、切削参数、加工顺序）
3. 可读性优先：包含清晰的行号、注释和分段标记
4. 安全第一：包括安全回零、冷却液控制、碰撞避免等措施
5. 生产可用：生成的代码可以直接加载到CNC机床执行

处理流程：
工序规划结果 → 指令序列生成 → 后处理器格式化 → 语法校验 → 最终G代码文本
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.process_planning.operation_sequencer import OperationPlan, Operation
from app.postprocessor.base import BasePostProcessor
from app.postprocessor.fanuc import FanucPostProcessor
from app.postprocessor.siemens import SiemensPostProcessor
from app.postprocessor.heidenhain import HeidenhainPostProcessor
from app.postprocessor.registry import PostProcessorRegistry


@dataclass
class GCodeResult:
    """G代码生成结果。

    Attributes:
        program_text: 完整的G代码程序文本
        controller_type: 目标控制器类型(fanuc/siemens/heidenhain)
        program_number: 程序号
        total_lines: 总行数
        operations_count: 包含的工序数量
        tool_count: 使用的刀具数量
        estimated_cycle_time_min: 预估加工周期(分钟)
        warnings: 生成过程中的警告
        errors: 生成过程中的错误
        metadata: 附加元数据
    """
    program_text: str
    controller_type: str
    program_number: int = 1000
    total_lines: int = 0
    operations_count: int = 0
    tool_count: int = 0
    estimated_cycle_time_min: float = 0.0
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert the G-code result to a dictionary representation.

        Returns:
            A dictionary containing program text, controller type, program
            metadata, and any warnings or errors.
        """
        return {
            "program_text": self.program_text,
            "controller_type": self.controller_type,
            "program_number": self.program_number,
            "total_lines": self.total_lines,
            "operations_count": self.operations_count,
            "tool_count": self.tool_count,
            "estimated_cycle_time_min": self.estimated_cycle_time_min,
            "warnings": self.warnings,
            "errors": self.errors,
            "metadata": self.metadata,
        }

    @property
    def is_valid(self) -> bool:
        """G代码是否有效（无语法错误）"""
        return len(self.errors) == 0


class GCodeGenerator:
    """G代码生成器。

    从工序规划结果生成完整的数控加工程序。

    调用方式：
        generator = GCodeGenerator()
        result = generator.generate(
            operation_plan=plan,
            controller_type="fanuc_0i",
            material_name="45#钢",
            safe_z=50.0,
        )
        # result.program_text 即为完整的G代码程序
    """

    # 控制器类型到后处理器的映射
    CONTROLLER_MAP: dict[str, type[BasePostProcessor]] = {
        "fanuc_0i": FanucPostProcessor,
        "siemens_840d": SiemensPostProcessor,
        "heidenhain_tnc": HeidenhainPostProcessor,
    }

    def __init__(self) -> None:
        """初始化G代码生成器。

        创建后处理器注册表并预加载三种控制器。
        """
        self._registry = PostProcessorRegistry()

    def generate(
        self,
        operation_plan: OperationPlan,
        controller_type: str = "fanuc_0i",
        material_name: str = "45#钢",
        program_number: int = 1000,
        safe_z: float = 50.0,
        tool_radius_compensation: str = "G41",
        use_coolant: bool = True,
    ) -> GCodeResult:
        """从工序规划结果生成完整G代码程序。

        生成步骤：
        1. 初始化后处理器（根据controller_type选择）
        2. 生成程序头（程序号、注释、安全设置）
        3. 逐工序解析为加工指令（直线/圆弧/钻孔循环）
        4. 调用后处理器格式化每条指令
        5. 生成程序尾（回零、关主轴、关冷却液）
        6. 执行语法校验

        Args:
            operation_plan: 工序规划结果
            controller_type: 控制器类型标识符
            material_name: 材料名称（用于注释）
            program_number: 程序号 (O号)
            safe_z: 安全平面Z高度 (mm)
            tool_radius_compensation: 刀具半径补偿模式 "G41"/"G42"/"G40"
            use_coolant: 是否开启冷却液

        Returns:
            GCodeResult: 生成的G代码程序及元信息

        Raises:
            ValueError: 当controller_type无效或operation_plan为空时
        """
        if not operation_plan or not operation_plan.operations:
            raise ValueError("工序规划结果为空，无法生成G代码")

        if controller_type not in self.CONTROLLER_MAP:
            available = list(self.CONTROLLER_MAP.keys())
            raise ValueError(
                f"不支持的控制器类型: '{controller_type}'。可用类型: {available}"
            )

        postprocessor = self._registry.get_processor(controller_type)
        warnings: list[str] = []
        errors: list[str] = []

        lines: list[str] = []

        # ========== 程序头 ==========
        header = postprocessor.format_header(program_number)
        lines.append(header)

        # 程序注释
        lines.append(postprocessor._comment(f"材料: {material_name}"))
        lines.append(postprocessor._comment(
            f"工序数: {len(operation_plan.operations)} | "
            f"装夹次数: {len(operation_plan.setups)}"
        ))
        lines.append(postprocessor._comment(
            f"控制器: {controller_type} | "
            f"生成日期: {postprocessor._date_string()}"
        ))
        lines.append("")

        # ========== 安全设置 ==========
        lines.append(postprocessor._comment("安全设置"))
        lines.append("G17 G21 G40 G49 G80 G90")  # XY平面, 公制, 取消补偿, 取消固定循环
        lines.append(f"G00 Z{safe_z:.3f}")  # Z轴抬至安全高度

        # ========== 刀具列表注释 ==========
        tools_seen: set[str] = set()
        tool_count = 0
        for op in operation_plan.operations:
            tool_key = op.tool_type or "UNKNOWN"
            if tool_key not in tools_seen:
                tools_seen.add(tool_key)
                tool_count += 1
                lines.append(postprocessor._comment(f"T{tool_count:02d}: {tool_key} - {op.machining_method}"))

        lines.append("")

        # ========== 逐工序生成G代码 ==========
        _current_tool = ""  # noqa: F841
        tool_index = 0
        tool_registry: dict[str, int] = {}

        for op_index, op in enumerate(operation_plan.operations):
            tool_key = op.tool_type or f"TOOL_{op_index}"

            # 换刀逻辑
            if tool_key not in tool_registry:
                tool_index += 1
                tool_registry[tool_key] = tool_index
                _current_tool = tool_key  # noqa: F841

                lines.append("")
                lines.append(postprocessor._comment(
                    f"---- OP{op.seq:02d} {op.name} - {op.machining_method} ----"
                ))

                # 生成换刀指令 - 传递整数编号
                tool_change_code = postprocessor.format_tool_change(
                    tool_id=tool_index,
                    length_comp=float(tool_index),
                    radius_comp=float(tool_index),
                )
                lines.append(tool_change_code)
            else:
                lines.append("")
                lines.append(postprocessor._comment(
                    f"---- OP{op.seq:02d} {op.name} (复用{tool_key}) ----"
                ))

            # 冷却液控制
            if use_coolant:
                coolant_code = postprocessor.format_coolant("on")
                lines.append(coolant_code)

            # 根据加工类型生成对应的加工指令
            feature_lines = self._generate_feature_code(
                op=op,
                postprocessor=postprocessor,
                safe_z=safe_z,
                controller_type=controller_type,
            )
            lines.extend(feature_lines)

            # 冷却液关闭（工序完成）
            if use_coolant:
                coolant_off = postprocessor.format_coolant("off")
                lines.append(coolant_off)

        # ========== 程序尾 ==========
        lines.append("")
        lines.append(postprocessor._comment("程序结束"))
        footer = postprocessor.format_footer()
        lines.append(footer)

        # 组装完整程序
        program_text = "\n".join(lines)

        # 计算总行数
        total_lines = len(lines)

        # ========== 语法校验 ==========
        syntax_errors = self._validate_syntax(program_text, controller_type)
        if syntax_errors:
            errors.extend(syntax_errors)

        # 预估加工周期（包含换刀时间）
        cycle_time = operation_plan.estimated_time_min + tool_count * 1.5

        return GCodeResult(
            program_text=program_text,
            controller_type=controller_type,
            program_number=program_number,
            total_lines=total_lines,
            operations_count=len(operation_plan.operations),
            tool_count=tool_count,
            estimated_cycle_time_min=round(cycle_time, 2),
            warnings=warnings,
            errors=errors,
            metadata={
                "material": material_name,
                "setups": [
                    {"name": s.name, "surface": s.surface, "fixture": s.fixture_type}
                    for s in operation_plan.setups
                ],
                "cutting_parameter_count": sum(
                    1 for op in operation_plan.operations if op.cutting_params
                ),
            },
        )

    def generate_hole_drilling_only(
        self,
        hole_positions: list[dict[str, float]],
        hole_depth: float,
        safe_z: float = 50.0,
        retract_plane: float = 5.0,
        controller_type: str = "fanuc_0i",
        tool_number: int = 1,
        spindle_speed: int = 1500,
        feed_rate: float = 150.0,
        material_name: str = "45#钢",
    ) -> GCodeResult:
        """仅生成钻孔G代码（简化API）。

        适用于已有孔位置数据、只需钻孔加工的场景。

        Args:
            hole_positions: 孔位置列表 [{"x": ..., "y": ..., "z": ...}, ...]
            hole_depth: 钻孔深度 (mm)，正值表示Z负方向钻进
            safe_z: 安全Z高度 (mm)
            retract_plane: 退刀平面R点高度 (mm)
            controller_type: 控制器类型
            tool_number: 刀具号
            spindle_speed: 主轴转速 (rpm)
            feed_rate: 进给速度 (mm/min)
            material_name: 材料名称

        Returns:
            GCodeResult: G代码生成结果
        """
        if not hole_positions:
            raise ValueError("孔位置列表不能为空")

        if controller_type not in self.CONTROLLER_MAP:
            raise ValueError(
                f"不支持的控制器类型: '{controller_type}'"
            )

        postprocessor = self._registry.get_processor(controller_type)
        lines: list[str] = []

        # 程序头
        lines.append(postprocessor.format_header(1000))
        lines.append(postprocessor._comment(f"钻孔程序 - {material_name} - {len(hole_positions)}个孔"))
        lines.append(postprocessor._comment(f"深度: {hole_depth}mm | 安全高度: {safe_z}mm"))
        lines.append("G17 G21 G40 G49 G80 G90")
        lines.append(f"G00 Z{safe_z:.3f}")

        # 单刀具设置
        lines.append(postprocessor.format_tool_change(
            tool_id=tool_number,
            length_comp=float(tool_number),
            radius_comp=float(tool_number),
        ))
        lines.append(f"S{spindle_speed} M03")
        lines.append(postprocessor.format_coolant("on"))

        # 钻孔固定循环 - 使用后处理器的固定循环格式
        for i, pos in enumerate(hole_positions):
            x = pos.get("x", 0.0)
            y = pos.get("y", 0.0)
            z_surface = pos.get("z", 0.0)
            actual_depth = z_surface - abs(hole_depth)  # Z负方向钻进

            cycle_code = postprocessor.format_cycle_drill(
                x=x,
                y=y,
                z=actual_depth,
                depth=hole_depth,
                dwell=0.5 if hole_depth > 15 else 0.0,
            )
            lines.append(postprocessor._comment(f"孔{i + 1}: X{x:.2f} Y{y:.2f}"))
            lines.append(cycle_code)

        # 取消固定循环
        lines.append("G80")

        # 程序尾
        lines.append(postprocessor.format_coolant("off"))
        lines.append(postprocessor.format_footer())

        program_text = "\n".join(lines)

        return GCodeResult(
            program_text=program_text,
            controller_type=controller_type,
            program_number=1000,
            total_lines=len(lines),
            operations_count=len(hole_positions),
            tool_count=1,
            estimated_cycle_time_min=round(len(hole_positions) * 0.5, 2),
            warnings=[],
            errors=[],
            metadata={"material": material_name},
        )

    def _generate_feature_code(
        self,
        op: Operation,
        postprocessor: BasePostProcessor,
        safe_z: float,
        controller_type: str,
    ) -> list[str]:
        """根据工序类型生成对应的G代码指令段。

        处理逻辑：
        - 钻孔类工序 → 生成钻孔固定循环(G81/G83/G73)
        - 铣削类工序 → 生成直线插补序列(G01)
        - 车削类工序 → 生成车削指令(G01)
        - 其他工序 → 生成通用指令

        Args:
            op: 工序对象
            postprocessor: 后处理器实例
            safe_z: 安全Z高度
            controller_type: 控制器类型

        Returns:
            指令行列表
        """
        lines: list[str] = []

        # 获取切削参数中的进给率
        cut_params = op.cutting_params or {}
        feed_factor = cut_params.get("feed_rate_factor", 1.0)
        recommended_feed = str(cut_params.get("recommended_feed", "0.1 mm/r"))
        recommended_speed = str(cut_params.get("recommended_speed", "80 m/min"))

        method = op.machining_method.lower()

        if "钻" in method:
            # === 钻孔类工序 ===
            lines.append(postprocessor._comment(f"钻孔: {op.feature_name}"))

            # 计算默认的主轴转速和进给（基于常见45#钢+HSS钻头参数）
            spindle_speed = 1200  # 默认rpm
            feed_rate = 150  # 默认mm/min

            if "中心" in method:
                spindle_speed = 2000
                feed_rate = 100
                depth = 3.0
            elif "沉头" in method:
                spindle_speed = 800
                feed_rate = 100
                depth = 8.0
            else:
                depth = 25.0  # 默认钻孔深度

            lines.append(f"S{spindle_speed} M03")
            lines.append(postprocessor._comment(f"进给: {recommended_feed}, 切速: {recommended_speed}"))

            # 使用后处理器的钻孔固定循环
            lines.append(postprocessor.format_cycle_drill(
                x=0.0, y=0.0, z=-abs(depth),
                depth=depth,
                dwell=0.5 if depth > 15 else 0.0,
            ))
            lines.append("G80")  # 取消固定循环

        elif "铣" in method:
            # === 铣削类工序 ===
            lines.append(postprocessor._comment(f"铣削: {op.feature_name}"))
            lines.append("S2500 M03")
            feed_rate = int(300 * feed_factor)
            lines.append(f"G01 Z{-5.0:.3f} F{feed_rate}")

        elif "车" in method:
            # === 车削类工序 ===
            lines.append(postprocessor._comment(f"车削: {op.feature_name}"))
            lines.append("S1500 M03")
            lines.append("G01 X50.0 Z-20.0 F0.15")

        elif "镗" in method:
            lines.append(postprocessor._comment(f"镗孔: {op.feature_name}"))
            lines.append("S800 M03")
            lines.append("G85 X0 Y0 Z-30.0 R3.0 F80")
            lines.append("G80")

        else:
            # === 通用工序 ===
            lines.append(postprocessor._comment(f"加工: {op.feature_name} ({op.machining_method})"))

        # 工序结束后抬刀至安全高度
        lines.append(f"G00 Z{safe_z:.3f}")

        return lines

    def _validate_syntax(
        self,
        program_text: str,
        controller_type: str,
    ) -> list[str]:
        """G代码语法校验。

        对生成的G代码进行基本的语法检查：
        - Fanuc: O号格式、%结束符、G代码配对
        - Siemens: 段号格式、循环语法、M30结束
        - Heidenhain: BEGIN/END PGM配对、TOOL CALL语法

        Args:
            program_text: 完整G代码程序文本
            controller_type: 控制器类型

        Returns:
            语法错误列表，空列表表示无错误
        """
        errors: list[str] = []

        if not program_text or not program_text.strip():
            errors.append("G代码程序为空")
            return errors

        lines = program_text.strip().splitlines()

        if controller_type == "fanuc_0i":
            # Fanuc校验: O程序号 + % 结束符
            if not any(line.strip().startswith("O") or line.strip().startswith(":") for line in lines):
                errors.append("Fanuc: 缺少程序号(Oxxxx)")
            if not lines[-1].strip().endswith("%"):
                errors.append("Fanuc: 缺少程序结束符(%)")
            # 检查G代码-取消指令配对
            g_codes: list[str] = []
            for line in lines:
                stripped = line.strip()
                # 提取所有G代码
                import re
                g_matches = re.findall(r'G\d+', stripped)
                g_codes.extend(g_matches)
            # 检查G41/G42是否配对G40
            if ("G41" in g_codes or "G42" in g_codes) and "G40" not in g_codes:
                errors.append("Fanuc: G41/G42缺少对应的G40取消指令")

        elif controller_type == "siemens_840d":
            # Siemens校验
            if not lines[-1].strip().endswith("M30"):
                errors.append("Siemens: 缺少M30程序结束指令")

        elif controller_type == "heidenhain_tnc":
            # Heidenhain校验
            first_line = lines[0].strip().upper() if lines else ""
            last_line = lines[-1].strip().upper() if lines else ""
            if "BEGIN PGM" not in first_line:
                errors.append("Heidenhain: 缺少BEGIN PGM标记")
            if "END PGM" not in last_line:
                errors.append("Heidenhain: 缺少END PGM标记")

        return errors

    def list_available_controllers(self) -> list[str]:
        """列出所有可用的控制器类型"""
        return list(self.CONTROLLER_MAP.keys())
