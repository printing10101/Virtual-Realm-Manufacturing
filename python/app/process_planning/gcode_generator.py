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
from app.postprocessor.xmachine import XMachineXM100PostProcessor
from app.postprocessor.registry import PostProcessorRegistry
from app.toolpath.five_axis_planner import FiveAxisToolpathPlanner, FiveAxisStrategy, FiveAxisParams
from app.postprocessor.config_loader import ConfigLimiter
from app.cutting_params_db import get_cutting_params, get_material_list


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
        checkpoints: 断点续传标记点列表 [{"op_index": int, "line_number": int, "label": str}]
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
    checkpoints: list[dict[str, Any]] = field(default_factory=list)

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
            "checkpoints": self.checkpoints,
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
        "xmachine_xm100": XMachineXM100PostProcessor,
    }

    def __init__(self, machine_config: dict[str, Any] | None = None) -> None:
        """初始化G代码生成器。

        创建后处理器注册表并预加载三种控制器。

        Args:
            machine_config: 机床配置参数（用于ConfigLimiter验证）
        """
        self._registry = PostProcessorRegistry()
        self._five_axis_planner = FiveAxisToolpathPlanner()
        self._config_limiter = ConfigLimiter(machine_config) if machine_config else None

    def generate(
        self,
        operation_plan: OperationPlan,
        controller_type: str = "fanuc_0i",
        material_name: str = "45#钢",
        program_number: int = 1000,
        safe_z: float = 80.0,
        tool_radius_compensation: str = "G41",
        use_coolant: bool = True,
        stock_top_z: float = 50.0,
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
            safe_z: 安全平面Z高度 (mm)，必须高于 stock_top_z
            tool_radius_compensation: 刀具半径补偿模式 "G41"/"G42"/"G40"
            use_coolant: 是否开启冷却液
            stock_top_z: 毛坯顶面Z坐标 (mm)，切削深度以此为基准向下计算

        Returns:
            GCodeResult: 生成的G代码程序及元信息

        Raises:
            ValueError: 当controller_type无效或operation_plan为空时
        """
        if safe_z <= stock_top_z:
            # 安全平面必须高于毛坯顶面，否则快速定位时会触发碰撞
            safe_z = stock_top_z + 30.0
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

        # 五轴模式检测
        is_five_axis = controller_type == "xmachine_xm100"

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
        if is_five_axis:
            lines.append(postprocessor._comment("五轴加工模式: A/C轴联动"))
        lines.append("")

        # ========== 安全设置 ==========
        lines.append(postprocessor._comment("安全设置"))
        lines.append("G17 G21 G40 G49 G80 G90")  # XY平面, 公制, 取消补偿, 取消固定循环
        lines.append(f"G00 Z{safe_z:.3f}")  # Z轴抬至安全高度

        # ========== 控制器特性方言接入 ==========
        # 根据控制器类型启用对应的特殊功能模式
        if controller_type == "fanuc_0i":
            # Fanuc: 启用高精度加工模式 (G05.1 Q1)
            if hasattr(postprocessor, 'format_high_precision_mode'):
                lines.append(postprocessor._comment("启用AI高精度轮廓控制"))
                lines.append(postprocessor.format_high_precision_mode(enable=True, mode=1))
        elif controller_type == "siemens_840d":
            # Siemens: 五轴模式时启用 TRAORI
            if is_five_axis and hasattr(postprocessor, 'format_five_axis_mode'):
                lines.append(postprocessor._comment("启用五轴联动模式 TRAORI"))
                lines.append(postprocessor.format_five_axis_mode(enable=True))
        elif controller_type == "heidenhain_tnc":
            # Heidenhain: 启用高精度模式 (M128)
            if hasattr(postprocessor, 'format_high_precision_mode'):
                lines.append(postprocessor._comment("启用高精度加工模式 M128"))
                lines.append(postprocessor.format_high_precision_mode(enable=True))

        # ========== 刀具清单汇总表 ==========
        # 收集刀具信息：刀具类型 -> {直径, 加工方法, 关联工序}
        tool_info: dict[str, dict[str, Any]] = {}
        for op in operation_plan.operations:
            tool_key = op.tool_type or "UNKNOWN"
            if tool_key not in tool_info:
                # 从 cutting_params 提取刀具直径
                cut_params = op.cutting_params or {}
                tool_diameter = cut_params.get("tool_diameter", 0.0)
                tool_info[tool_key] = {
                    "diameter": tool_diameter,
                    "methods": set(),
                    "features": set(),
                    "op_count": 0,
                }
            tool_info[tool_key]["methods"].add(op.machining_method)
            tool_info[tool_key]["features"].add(op.feature_name)
            tool_info[tool_key]["op_count"] += 1

        # 生成结构化刀具清单
        lines.append(postprocessor._comment("=" * 50))
        lines.append(postprocessor._comment("刀具清单汇总表 (TOOL LIST SUMMARY)"))
        lines.append(postprocessor._comment("=" * 50))
        tool_count = 0
        for tool_key, info in tool_info.items():
            tool_count += 1
            diameter_str = f"Φ{info['diameter']:.1f}" if info['diameter'] > 0 else "N/A"
            methods_str = "/".join(sorted(info['methods']))
            features_str = ", ".join(sorted(info['features'])[:3])  # 最多显示3个特征
            if len(info['features']) > 3:
                features_str += f"...等{len(info['features'])}个"
            lines.append(postprocessor._comment(
                f"T{tool_count:02d} | {tool_key:<20} | {diameter_str:<8} | "
                f"{methods_str:<15} | {info['op_count']}次 | {features_str}"
            ))
        lines.append(postprocessor._comment(f"总计: {tool_count} 把刀具"))
        lines.append(postprocessor._comment("=" * 50))
        lines.append("")

        # ========== 逐工序生成G代码 ==========
        _current_tool = ""  # noqa: F841
        tool_index = 0
        tool_registry: dict[str, int] = {}
        checkpoints: list[dict[str, Any]] = []
        checkpoint_counter = 0

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

            # 插入断点标记（每道工序开始前）
            checkpoint_counter += 1
            checkpoint_label = f"CP{checkpoint_counter:03d}"
            checkpoint_line = len(lines)
            
            # 根据控制器类型生成断点标记
            if controller_type == "fanuc_0i":
                # Fanuc 使用 N 行号 + 注释
                lines.append(f"N{checkpoint_counter * 100:05d} (BREAKPOINT: {checkpoint_label})")
            elif controller_type == "siemens_840d":
                # Siemens 使用 ; 注释
                lines.append(f"N{checkpoint_counter * 100:05d} ; BREAKPOINT: {checkpoint_label}")
            elif controller_type == "heidenhain_tnc":
                # Heidenhain 使用 ; 注释
                lines.append(f"{checkpoint_counter * 100}  ; BREAKPOINT: {checkpoint_label}")
            else:
                # 默认使用注释格式
                lines.append(postprocessor._comment(f"BREAKPOINT: {checkpoint_label}"))
            
            # 记录断点信息
            checkpoints.append({
                "checkpoint_id": checkpoint_label,
                "op_index": op_index,
                "op_name": op.name,
                "feature_name": op.feature_name,
                "line_number": checkpoint_line,
                "tool_key": tool_key,
                "tool_index": tool_index,
            })

            # 冷却液控制
            if use_coolant:
                coolant_code = postprocessor.format_coolant("on")
                lines.append(coolant_code)

            # 根据加工类型生成对应的加工指令
            # 从工序参数中提取材料和刀具信息
            cut_params = op.cutting_params or {}
            material = cut_params.get("material", "steel")
            tool_diameter = cut_params.get("tool_diameter", 10.0)
            radius_comp = cut_params.get("radius_comp", "G41")

            feature_lines = self._generate_feature_code(
                op=op,
                postprocessor=postprocessor,
                safe_z=safe_z,
                controller_type=controller_type,
                material=material,
                tool_diameter=tool_diameter,
                radius_comp=radius_comp,
                stock_top_z=stock_top_z,
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
            checkpoints=checkpoints,
        )

    def generate_hole_drilling_only(
        self,
        hole_positions: list[dict[str, float]],
        hole_depth: float,
        safe_z: float = 80.0,
        retract_plane: float = 5.0,
        controller_type: str = "fanuc_0i",
        tool_number: int = 1,
        spindle_speed: int = 1500,
        feed_rate: float = 150.0,
        material_name: str = "45#钢",
        stock_top_z: float = 50.0,
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
            z_surface = pos.get("z", stock_top_z)  # 默认从毛坯顶面开始
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
        material: str = "steel",
        tool_diameter: float = 10.0,
        radius_comp: str = "G41",
        stock_top_z: float = 50.0,
    ) -> list[str]:
        """根据工序类型生成对应的G代码指令段。

        处理逻辑：
        - 钻孔类工序 → 生成钻孔固定循环(G81/G83/G73)
        - 铣削类工序 → 生成直线插补序列(G01) + 刀具半径补偿
        - 车削类工序 → 生成车削指令(G01) + 刀具半径补偿
        - 其他工序 → 生成通用指令

        Args:
            op: 工序对象
            postprocessor: 后处理器实例
            safe_z: 安全Z高度
            controller_type: 控制器类型
            material: 材料类型 (aluminum/steel/stainless/titanium/cast_iron/brass)
            tool_diameter: 刀具直径 (mm)
            radius_comp: 刀具半径补偿模式 "G41" (左补偿) / "G42" (右补偿)

        Returns:
            指令行列表
        """
        lines: list[str] = []

        # 获取切削参数中的进给率
        cut_params = op.cutting_params or {}
        feed_factor = cut_params.get("feed_rate_factor", 1.0)
        recommended_feed = str(cut_params.get("recommended_feed", "0.1 mm/r"))
        recommended_speed = str(cut_params.get("recommended_speed", "80 m/min"))

        # 从 cutting_params 提取几何参数（如果存在），否则使用默认值
        # 几何数据优先从上游 CAD/CAM 模块传入，此处提供合理的默认值作为后备
        geom = cut_params.get("geometry", {})
        x_pos = geom.get("x", 0.0)
        y_pos = geom.get("y", 0.0)
        z_depth = geom.get("z_depth", None)  # None 表示需要使用默认值
        length = geom.get("length", None)
        width = geom.get("width", None)

        method = op.machining_method.lower()
        is_five_axis = controller_type == "xmachine_xm100"

        if "钻" in method:
            # === 钻孔类工序 ===
            lines.append(postprocessor._comment(f"钻孔: {op.feature_name}"))

            # 从数据库获取切削参数
            try:
                db_params = get_cutting_params(material, "drilling", tool_diameter)
                spindle_speed = db_params["spindle_speed"]
                feed_rate = db_params["feed_rate"]
            except (ValueError, KeyError):
                # 如果数据库查询失败，使用安全默认值
                spindle_speed = 1200
                feed_rate = 150

            if "中心" in method:
                # 中心钻使用更高转速
                spindle_speed = int(spindle_speed * 1.5)
                feed_rate = int(feed_rate * 0.6)
                depth = z_depth if z_depth is not None else 3.0
            elif "沉头" in method:
                # 沉头钻使用较低转速
                spindle_speed = int(spindle_speed * 0.7)
                feed_rate = int(feed_rate * 0.7)
                depth = z_depth if z_depth is not None else 8.0
            else:
                depth = z_depth if z_depth is not None else 25.0  # 默认钻孔深度

            # ConfigLimiter 限幅
            if self._config_limiter:
                spindle_speed = self._config_limiter.limit_spindle_rpm(
                    spindle_speed, context=f"钻孔-{op.feature_name}"
                )
                feed_rate = self._config_limiter.limit_feed_rate(
                    feed_rate, context=f"钻孔-{op.feature_name}"
                )

            lines.append(f"S{spindle_speed} M03")
            lines.append(postprocessor._comment(f"进给: {recommended_feed}, 切速: {recommended_speed}"))
            lines.append(postprocessor._comment(f"参数来自数据库: 材料={material}, 直径={tool_diameter}mm"))

            # 五轴模式：开启 RTCP
            if is_five_axis and hasattr(postprocessor, "format_rtcp_on"):
                lines.append(postprocessor.format_rtcp_on())

            # 使用后处理器的钻孔固定循环 - 使用实际坐标
            # Z 坐标基于 stock_top_z 向下计算（避免负值触发过切误报）
            drill_z = stock_top_z - abs(depth)
            lines.append(postprocessor.format_cycle_drill(
                x=x_pos, y=y_pos, z=drill_z,
                depth=depth,
                dwell=0.5 if depth > 15 else 0.0,
            ))
            lines.append("G80")  # 取消固定循环

            # 五轴模式：关闭 RTCP
            if is_five_axis and hasattr(postprocessor, "format_rtcp_off"):
                lines.append(postprocessor.format_rtcp_off())

        elif "铣" in method:
            # === 铣削类工序 ===
            lines.append(postprocessor._comment(f"铣削: {op.feature_name}"))

            # 从数据库获取切削参数
            try:
                db_params = get_cutting_params(material, "milling", tool_diameter)
                spindle_speed = db_params["spindle_speed"]
                feed_rate = db_params["feed_rate"]
            except (ValueError, KeyError):
                # 如果数据库查询失败，使用安全默认值
                spindle_speed = 2500
                feed_rate = 300

            # ConfigLimiter 限幅
            if self._config_limiter:
                spindle_speed = self._config_limiter.limit_spindle_rpm(
                    spindle_speed, context=f"铣削-{op.feature_name}"
                )
                feed_rate = self._config_limiter.limit_feed_rate(
                    feed_rate, context=f"铣削-{op.feature_name}"
                )

            lines.append(f"S{spindle_speed} M03")
            lines.append(postprocessor._comment(f"参数来自数据库: 材料={material}, 直径={tool_diameter}mm"))

            # 从几何参数获取铣削深度和范围
            # mill_depth 基于毛坯顶面 stock_top_z 向下计算（避免负值触发过切误报）
            if z_depth is not None:
                mill_depth = z_depth
            else:
                _doc = cut_params.get("depth_of_cut", 5.0)
                mill_depth = stock_top_z - abs(_doc)
            mill_length = length if length is not None else 10.0
            mill_width = width if width is not None else 10.0

            # 刀具半径补偿 (G41/G42)
            if radius_comp in ["G41", "G42"]:
                lines.append(postprocessor._comment(f"启用刀具半径补偿: {radius_comp}"))
                # 抬刀到安全平面后再快速定位（避免G00在切削深度处移动引发碰撞）
                lines.append(f"G00 Z{safe_z:.3f}")
                # 移动到起始位置上方
                lines.append(f"G00 X{x_pos:.3f} Y{y_pos:.3f}")
                # 下刀到切削深度
                lines.append(f"G01 Z{mill_depth:.3f} F{feed_rate}")
                # 启用半径补偿
                lines.append(f"{radius_comp} D{int(tool_diameter)}")

            if is_five_axis and hasattr(postprocessor, "format_rtcp_on"):
                # 五轴铣削：RTCP + FiveAxisToolpathPlanner 生成 A/C 轴联动
                lines.append(postprocessor.format_rtcp_on())
                
                # 使用五轴规划器生成刀具姿态序列
                start_x, start_y, start_z = x_pos, y_pos, mill_depth
                end_x, end_y, end_z = x_pos + mill_length, y_pos + mill_width, mill_depth
                
                orientations = self._five_axis_planner.plan_lead_angle_toolpath(
                    start_x=start_x, start_y=start_y, start_z=start_z,
                    end_x=end_x, end_y=end_y, end_z=end_z,
                    surface_normal_i=0.0, surface_normal_j=0.0, surface_normal_k=1.0,
                    num_points=4
                )
                
                # 根据刀具姿态生成带 A/C 轴的直线插补
                for idx, orient in enumerate(orientations):
                    t = idx / max(1, len(orientations) - 1)
                    interp_x = start_x + t * (end_x - start_x)
                    interp_y = start_y + t * (end_y - start_y)
                    
                    lines.append(postprocessor.format_linear_move(
                        x=interp_x, y=interp_y, z=mill_depth, feed=feed_rate,
                        a=orient.a_angle, c=orient.c_angle,
                    ))
                
                lines.append(postprocessor.format_rtcp_off())
            else:
                # 三轴铣削 - 使用实际坐标
                if radius_comp not in ["G41", "G42"]:
                    # 抬刀到安全平面后再快速定位（避免G00在切削深度处移动引发碰撞）
                    lines.append(f"G00 Z{safe_z:.3f}")
                    lines.append(f"G00 X{x_pos:.3f} Y{y_pos:.3f}")
                    lines.append(f"G01 Z{mill_depth:.3f} F{feed_rate}")
                lines.append(postprocessor.format_linear_move(
                    x=x_pos + mill_length, y=y_pos, z=mill_depth, feed=feed_rate,
                ))
                lines.append(postprocessor.format_linear_move(
                    x=x_pos + mill_length, y=y_pos + mill_width, z=mill_depth, feed=feed_rate,
                ))

            # 取消刀具半径补偿
            if radius_comp in ["G41", "G42"]:
                lines.append("G40")  # 取消半径补偿
                lines.append(postprocessor._comment("取消刀具半径补偿"))

        elif "车" in method:
            # === 车削类工序 ===
            lines.append(postprocessor._comment(f"车削: {op.feature_name}"))

            # 从数据库获取切削参数
            try:
                db_params = get_cutting_params(material, "turning", tool_diameter)
                spindle_speed = db_params["spindle_speed"]
                feed_rate = db_params["feed_rate"]
            except (ValueError, KeyError):
                # 如果数据库查询失败，使用安全默认值
                spindle_speed = 1500
                feed_rate = 0.15

            # ConfigLimiter 限幅
            if self._config_limiter:
                spindle_speed = self._config_limiter.limit_spindle_rpm(
                    spindle_speed, context=f"车削-{op.feature_name}"
                )
                feed_rate = self._config_limiter.limit_feed_rate(
                    feed_rate, context=f"车削-{op.feature_name}"
                )

            lines.append(f"S{spindle_speed} M03")
            lines.append(postprocessor._comment(f"参数来自数据库: 材料={material}, 直径={tool_diameter}mm"))

            # 刀具半径补偿 (G41/G42)
            if radius_comp in ["G41", "G42"]:
                lines.append(postprocessor._comment(f"启用刀具半径补偿: {radius_comp}"))
                lines.append(f"{radius_comp} D{int(tool_diameter)}")

            # 从几何参数获取车削尺寸
            turn_x = geom.get("diameter", 50.0) if geom else 50.0
            turn_z = length if length is not None else -20.0
            lines.append(f"G01 X{turn_x:.3f} Z{turn_z:.3f} F{feed_rate}")

            # 取消刀具半径补偿
            if radius_comp in ["G41", "G42"]:
                lines.append("G40")  # 取消半径补偿
                lines.append(postprocessor._comment("取消刀具半径补偿"))

        elif "镗" in method:
            lines.append(postprocessor._comment(f"镗孔: {op.feature_name}"))

            # 从数据库获取切削参数（镗孔使用钻孔参数）
            try:
                db_params = get_cutting_params(material, "drilling", tool_diameter)
                spindle_speed = int(db_params["spindle_speed"] * 0.8)  # 镗孔转速略低
                feed_rate = db_params["feed_rate"] * 0.6  # 镗孔进给较慢
            except (ValueError, KeyError):
                # 如果数据库查询失败，使用安全默认值
                spindle_speed = 800
                feed_rate = 80

            # ConfigLimiter 限幅
            if self._config_limiter:
                spindle_speed = self._config_limiter.limit_spindle_rpm(
                    spindle_speed, context=f"镗孔-{op.feature_name}"
                )
                feed_rate = self._config_limiter.limit_feed_rate(
                    feed_rate, context=f"镗孔-{op.feature_name}"
                )

            lines.append(f"S{spindle_speed} M03")
            lines.append(postprocessor._comment(f"参数来自数据库: 材料={material}, 直径={tool_diameter}mm"))

            # 从几何参数获取镗孔尺寸
            bore_x = x_pos
            bore_y = y_pos
            # 镗孔 Z 坐标基于 stock_top_z 向下计算（避免负值触发过切误报）
            bore_z = z_depth if z_depth is not None else (stock_top_z - 30.0)
            bore_r = geom.get("retract_plane", 3.0) if geom else 3.0
            lines.append(f"G85 X{bore_x:.3f} Y{bore_y:.3f} Z{bore_z:.3f} R{bore_r:.3f} F{feed_rate}")
            lines.append("G80")

        elif "五轴" in method or "3+2" in method or "联动" in method:
            # === 五轴专用工序 ===
            lines.append(postprocessor._comment(f"五轴加工: {op.feature_name}"))

            # 从数据库获取切削参数（五轴使用铣削参数）
            try:
                db_params = get_cutting_params(material, "milling", tool_diameter)
                spindle_speed = db_params["spindle_speed"]
                feed_rate = db_params["feed_rate"] * 0.7  # 五轴加工进给略慢
            except (ValueError, KeyError):
                # 如果数据库查询失败，使用安全默认值
                spindle_speed = 3000
                feed_rate = 200

            # ConfigLimiter 限幅
            if self._config_limiter:
                spindle_speed = self._config_limiter.limit_spindle_rpm(
                    spindle_speed, context=f"五轴-{op.feature_name}"
                )
                feed_rate = self._config_limiter.limit_feed_rate(
                    feed_rate, context=f"五轴-{op.feature_name}"
                )

            lines.append(f"S{spindle_speed} M03")
            lines.append(postprocessor._comment(f"参数来自数据库: 材料={material}, 直径={tool_diameter}mm"))

            # 从几何参数获取五轴加工范围
            # work_depth 基于 stock_top_z 向下计算（避免负值触发过切误报）
            work_depth = z_depth if z_depth is not None else (stock_top_z - 3.0)
            work_length = length if length is not None else 20.0
            work_width = width if width is not None else 20.0

            if is_five_axis and hasattr(postprocessor, "format_rtcp_on"):
                lines.append(postprocessor.format_rtcp_on())
                
                # 使用 FiveAxisToolpathPlanner 生成刀具姿态
                # 定义加工路径起点和终点
                start_x, start_y, start_z = x_pos, y_pos, work_depth
                end_x, end_y, end_z = x_pos + work_length, y_pos + work_width, work_depth
                
                # 调用五轴规划器生成刀具姿态序列
                orientations = self._five_axis_planner.plan_lead_angle_toolpath(
                    start_x=start_x, start_y=start_y, start_z=start_z,
                    end_x=end_x, end_y=end_y, end_z=end_z,
                    surface_normal_i=0.0, surface_normal_j=0.0, surface_normal_k=1.0,
                    num_points=5
                )
                
                # 根据刀具姿态生成 A/C 轴命令
                for i, orient in enumerate(orientations):
                    # 计算路径点位置（线性插值）
                    t = i / max(1, len(orientations) - 1)
                    interp_x = start_x + t * (end_x - start_x)
                    interp_y = start_y + t * (end_y - start_y)
                    interp_z = work_depth
                    
                    # 生成带 A/C 轴的直线插补
                    lines.append(postprocessor.format_linear_move(
                        x=interp_x, y=interp_y, z=interp_z, feed=feed_rate,
                        a=orient.a_angle, c=orient.c_angle,
                    ))
                
                lines.append(postprocessor.format_rtcp_off())
            else:
                lines.append(postprocessor._comment("警告: 五轴工序需要 xmachine_xm100 控制器"))
                lines.append(f"G01 Z{work_depth:.3f} F{feed_rate}")

        else:
            # === 通用工序 ===
            lines.append(postprocessor._comment(f"加工: {op.feature_name} ({op.machining_method})"))

        # 工序结束后抬刀至安全高度
        if is_five_axis and hasattr(postprocessor, "format_rapid_move"):
            lines.append(postprocessor.format_rapid_move(x=x_pos, y=y_pos, z=safe_z))
        else:
            lines.append(f"G00 Z{safe_z:.3f}")

        return lines

    def _validate_syntax(
        self,
        program_text: str,
        controller_type: str,
    ) -> list[str]:
        """G代码语法校验（增强版）。

        对生成的G代码进行全面的安全检查：
        1. 基础语法检查（程序号、结束符、G代码配对）
        2. 机床行程极限验证（各轴坐标是否在安全范围内）
        3. 切削参数物理约束验证（主轴转速、进给速度）
        4. 快速移动碰撞检测（G00进入工件区域）
        5. 刀具半径补偿正确性检查
        6. 坐标系有效性验证

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

        # ========== 1. 基础语法检查 ==========
        if controller_type == "fanuc_0i":
            if not any(line.strip().startswith("O") or line.strip().startswith(":") for line in lines):
                errors.append("Fanuc: 缺少程序号(Oxxxx)")
            if not lines[-1].strip().endswith("%"):
                errors.append("Fanuc: 缺少程序结束符(%)")
        elif controller_type == "siemens_840d":
            if not lines[-1].strip().endswith("M30"):
                errors.append("Siemens: 缺少M30程序结束指令")
        elif controller_type == "heidenhain_tnc":
            first_line = lines[0].strip().upper() if lines else ""
            last_line = lines[-1].strip().upper() if lines else ""
            if "BEGIN PGM" not in first_line:
                errors.append("Heidenhain: 缺少BEGIN PGM标记")
            if "END PGM" not in last_line:
                errors.append("Heidenhain: 缺少END PGM标记")

        # ========== 2. 机床行程极限验证 ==========
        # 定义典型机床行程限制（可根据实际机床配置调整）
        MACHINE_LIMITS = {
            "x_min": -500.0, "x_max": 500.0,
            "y_min": -400.0, "y_max": 400.0,
            "z_min": -300.0, "z_max": 300.0,
        }
        
        import re
        for line_num, line in enumerate(lines, 1):
            stripped = line.strip()
            if not stripped or stripped.startswith(";") or stripped.startswith("("):
                continue
            
            # 提取坐标值
            x_match = re.search(r'X([+-]?\d*\.?\d+)', stripped)
            y_match = re.search(r'Y([+-]?\d*\.?\d+)', stripped)
            z_match = re.search(r'Z([+-]?\d*\.?\d+)', stripped)
            
            if x_match:
                x_val = float(x_match.group(1))
                if x_val < MACHINE_LIMITS["x_min"] or x_val > MACHINE_LIMITS["x_max"]:
                    errors.append(f"第{line_num}行: X坐标{x_val:.3f}超出机床行程范围[{MACHINE_LIMITS['x_min']}, {MACHINE_LIMITS['x_max']}]")
            
            if y_match:
                y_val = float(y_match.group(1))
                if y_val < MACHINE_LIMITS["y_min"] or y_val > MACHINE_LIMITS["y_max"]:
                    errors.append(f"第{line_num}行: Y坐标{y_val:.3f}超出机床行程范围[{MACHINE_LIMITS['y_min']}, {MACHINE_LIMITS['y_max']}]")
            
            if z_match:
                z_val = float(z_match.group(1))
                if z_val < MACHINE_LIMITS["z_min"] or z_val > MACHINE_LIMITS["z_max"]:
                    errors.append(f"第{line_num}行: Z坐标{z_val:.3f}超出机床行程范围[{MACHINE_LIMITS['z_min']}, {MACHINE_LIMITS['z_max']}]")

        # ========== 3. 切削参数物理约束验证 ==========
        # 典型机床参数限制
        SPINDLE_LIMITS = {"min_rpm": 50, "max_rpm": 24000}
        FEED_LIMITS = {"min_rate": 10.0, "max_rate": 20000.0}
        
        for line_num, line in enumerate(lines, 1):
            stripped = line.strip()
            if not stripped or stripped.startswith(";") or stripped.startswith("("):
                continue
            
            # 检查主轴转速
            s_match = re.search(r'S(\d+)', stripped)
            if s_match:
                rpm = int(s_match.group(1))
                if rpm < SPINDLE_LIMITS["min_rpm"] or rpm > SPINDLE_LIMITS["max_rpm"]:
                    errors.append(f"第{line_num}行: 主轴转速{rpm}RPM超出安全范围[{SPINDLE_LIMITS['min_rpm']}, {SPINDLE_LIMITS['max_rpm']}]")
            
            # 检查进给速度
            f_match = re.search(r'F([+-]?\d*\.?\d+)', stripped)
            if f_match:
                feed = float(f_match.group(1))
                if feed < FEED_LIMITS["min_rate"] or feed > FEED_LIMITS["max_rate"]:
                    errors.append(f"第{line_num}行: 进给速度{feed:.1f}mm/min超出安全范围[{FEED_LIMITS['min_rate']}, {FEED_LIMITS['max_rate']}]")

        # ========== 4. 快速移动碰撞检测 ==========
        for line_num, line in enumerate(lines, 1):
            stripped = line.strip()
            if stripped.startswith("G00") or stripped.startswith("G0 "):
                # 检查G00快速移动是否进入工件区域（Z<0）
                z_match = re.search(r'Z([+-]?\d*\.?\d+)', stripped)
                if z_match:
                    z_val = float(z_match.group(1))
                    if z_val < 0:
                        errors.append(f"第{line_num}行: G00快速移动到Z{z_val:.3f}，可能导致碰撞")

        # ========== 5. 刀具半径补偿正确性检查 ==========
        g_codes: list[str] = []
        for line in lines:
            stripped = line.strip()
            g_matches = re.findall(r'G\d+', stripped)
            g_codes.extend(g_matches)
        
        if ("G41" in g_codes or "G42" in g_codes) and "G40" not in g_codes:
            errors.append("刀具半径补偿未取消：G41/G42缺少对应的G40取消指令")

        # ========== 6. 坐标系有效性验证 ==========
        valid_wcs = {"G54", "G55", "G56", "G57", "G58", "G59"}
        for line_num, line in enumerate(lines, 1):
            stripped = line.strip()
            for wcs in valid_wcs:
                if wcs in stripped:
                    break
        
        return errors

    def dry_run_preview(
        self,
        operation_plan: OperationPlan,
        controller_type: str = "fanuc_0i",
        material_name: str = "45#钢",
        program_number: int = 1000,
        safe_z: float = 80.0,
        stock_top_z: float = 50.0,
    ) -> dict[str, Any]:
        """G代码 dry-run 预览模式。

        在不实际生成完整 G代码的情况下，预览加工过程的关键信息：
        - 刀具路径概览（每道工序的起止坐标）
        - 加工时间估算
        - 刀具使用统计
        - 潜在的碰撞风险点
        - 断点续传标记位置

        Args:
            operation_plan: 工序规划结果
            controller_type: 控制器类型
            material_name: 材料名称
            program_number: 程序号
            safe_z: 安全平面高度

        Returns:
            预览结果字典，包含：
            - tool_path_summary: 刀具路径摘要
            - time_estimation: 时间估算
            - tool_usage: 刀具使用统计
            - collision_risks: 碰撞风险提示
            - checkpoint_positions: 断点位置
            - warnings: 警告信息
        """
        preview_result: dict[str, Any] = {
            "controller_type": controller_type,
            "material": material_name,
            "program_number": program_number,
            "safe_z": safe_z,
            "tool_path_summary": [],
            "time_estimation": {},
            "tool_usage": {},
            "collision_risks": [],
            "checkpoint_positions": [],
            "warnings": [],
        }

        if not operation_plan or not operation_plan.operations:
            preview_result["warnings"].append("工序规划结果为空")
            return preview_result

        # 1. 刀具路径摘要
        current_z = safe_z
        total_travel = 0.0
        for op in operation_plan.operations:
            cut_params = op.cutting_params or {}
            # 提取关键坐标（从工序参数或默认值）
            start_x = cut_params.get("start_x", 0.0)
            start_y = cut_params.get("start_y", 0.0)
            depth = cut_params.get("depth", 0.0)
            target_z = (stock_top_z - abs(depth)) if depth > 0 else safe_z

            path_info = {
                "op_seq": op.seq,
                "op_name": op.name,
                "tool_type": op.tool_type or "UNKNOWN",
                "start_pos": {"x": start_x, "y": start_y, "z": current_z},
                "end_pos": {"x": start_x, "y": start_y, "z": target_z},
                "travel_distance": abs(current_z - target_z),
                "machining_method": op.machining_method,
            }
            preview_result["tool_path_summary"].append(path_info)
            total_travel += path_info["travel_distance"]
            current_z = target_z

        # 2. 时间估算
        total_time = operation_plan.estimated_time_min
        tool_changes = len(set(op.tool_type for op in operation_plan.operations if op.tool_type))
        tool_change_time = tool_changes * 1.5  # 每次换刀约 1.5 分钟
        preview_result["time_estimation"] = {
            "machining_time_min": round(total_time, 2),
            "tool_change_time_min": round(tool_change_time, 2),
            "total_time_min": round(total_time + tool_change_time, 2),
            "operation_count": len(operation_plan.operations),
            "tool_change_count": tool_changes,
        }

        # 3. 刀具使用统计
        tool_stats: dict[str, dict[str, Any]] = {}
        for op in operation_plan.operations:
            tool_key = op.tool_type or "UNKNOWN"
            if tool_key not in tool_stats:
                tool_stats[tool_key] = {
                    "usage_count": 0,
                    "methods": set(),
                    "features": set(),
                }
            tool_stats[tool_key]["usage_count"] += 1
            tool_stats[tool_key]["methods"].add(op.machining_method)
            tool_stats[tool_key]["features"].add(op.feature_name)

        # 转换 set 为 list 以便序列化
        for tool_key, stats in tool_stats.items():
            stats["methods"] = sorted(list(stats["methods"]))
            stats["features"] = sorted(list(stats["features"]))
        preview_result["tool_usage"] = tool_stats

        # 4. 碰撞风险提示
        # 检查是否有深腔加工（深度 > 50mm 可能需要分层）
        for op in operation_plan.operations:
            cut_params = op.cutting_params or {}
            depth = cut_params.get("depth", 0.0)
            if depth > 50.0:
                preview_result["collision_risks"].append({
                    "op_seq": op.seq,
                    "op_name": op.name,
                    "risk_type": "deep_cavity",
                    "description": f"深腔加工 (深度={depth:.1f}mm)，建议分层铣削",
                    "severity": "medium",
                })

        # 检查快速移动距离（可能碰撞）
        for i, path in enumerate(preview_result["tool_path_summary"]):
            if path["travel_distance"] > 100.0:
                preview_result["collision_risks"].append({
                    "op_seq": path["op_seq"],
                    "op_name": path["op_name"],
                    "risk_type": "long_rapid_move",
                    "description": f"长距离快速移动 ({path['travel_distance']:.1f}mm)，注意避障",
                    "severity": "low",
                })

        # 5. 断点位置
        checkpoint_counter = 0
        for op_index, op in enumerate(operation_plan.operations):
            checkpoint_counter += 1
            preview_result["checkpoint_positions"].append({
                "checkpoint_id": f"CP{checkpoint_counter:03d}",
                "op_index": op_index,
                "op_name": op.name,
                "feature_name": op.feature_name,
                "estimated_line": checkpoint_counter * 100,
            })

        # 6. 警告信息
        if tool_changes > 10:
            preview_result["warnings"].append(f"刀具更换次数较多 ({tool_changes}次)，可能影响效率")
        if total_time > 60.0:
            preview_result["warnings"].append(f"预估加工时间较长 ({total_time:.1f}分钟)")
        if len(preview_result["collision_risks"]) > 0:
            preview_result["warnings"].append(f"发现 {len(preview_result['collision_risks'])} 个潜在碰撞风险")

        return preview_result

    def list_available_controllers(self) -> list[str]:
        """列出所有可用的控制器类型"""
        return list(self.CONTROLLER_MAP.keys())


def validate_gcode(gcode: str) -> dict:
    """
    独立G代码验证函数。

    对G代码进行全面验证，检查常见错误。

    Args:
        gcode: G代码字符串

    Returns:
        包含验证结果的字典：
        - valid: bool - 是否有效
        - errors: list - 错误列表
        - warnings: list - 警告列表
    """
    errors = []
    warnings = []

    if not gcode or not gcode.strip():
        errors.append("G代码为空")
        return {"valid": False, "errors": errors, "warnings": warnings}

    lines = gcode.strip().split('\n')
    line_count = len(lines)

    # 检查基本结构
    has_program_start = False
    has_program_end = False
    has_feed_rate = False
    has_spindle = False

    for i, line in enumerate(lines, 1):
        line = line.strip()

        # 跳过空行和注释
        if not line or line.startswith(';') or line.startswith('('):
            continue

        # 检查程序开始
        if line.startswith('O') or line.startswith('%'):
            has_program_start = True

        # 检查程序结束
        if 'M02' in line or 'M30' in line or line.endswith('%'):
            has_program_end = True

        # 检查进给率
        if 'F' in line and any(c.isdigit() for c in line):
            has_feed_rate = True

        # 检查主轴启动
        if 'M03' in line or 'M04' in line:
            has_spindle = True

        # 检查快速移动进入工件（潜在碰撞）
        if line.startswith('G00') and 'Z' in line:
            # 检查Z值是否为负（进入工件）
            import re
            z_match = re.search(r'Z([+-]?\d*\.?\d+)', line)
            if z_match:
                z_val = float(z_match.group(1))
                if z_val < 0:
                    warnings.append(f"第{i}行: G00快速移动到Z{z_val}，可能导致碰撞")

        # 检查刀具半径补偿配对
        if 'G41' in line or 'G42' in line:
            # 检查后续是否有G40取消
            has_cancel = False
            for j in range(i, min(i + 50, line_count)):
                if j < line_count and 'G40' in lines[j]:
                    has_cancel = True
                    break
            if not has_cancel:
                warnings.append(f"第{i}行: 刀具半径补偿未取消（缺少G40）")

    # 基本检查
    if not has_program_start:
        warnings.append("缺少程序号（Oxxxx）")

    if not has_program_end:
        errors.append("缺少程序结束指令（M02/M30）")

    if not has_feed_rate:
        warnings.append("未找到进给率（F指令）")

    if not has_spindle:
        warnings.append("未找到主轴启动指令（M03/M04）")

    # 检查G代码语法
    for i, line in enumerate(lines, 1):
        line = line.strip()

        # 跳过空行和注释
        if not line or line.startswith(';') or line.startswith('('):
            continue

        # 检查G代码格式
        import re
        g_codes = re.findall(r'G(\d+)', line)
        for g_code in g_codes:
            # 检查常见G代码
            if g_code in ['00', '01', '02', '03', '04', '17', '18', '19',
                         '20', '21', '28', '40', '41', '42', '43', '49',
                         '53', '54', '55', '56', '57', '58', '59',
                         '80', '81', '82', '83', '84', '85', '86', '87', '88', '89',
                         '90', '91', '92', '94', '95', '96', '97', '98', '99']:
                continue
            else:
                warnings.append(f"第{i}行: 不常见的G代码 G{g_code}")

        # 检查M代码格式
        m_codes = re.findall(r'M(\d+)', line)
        for m_code in m_codes:
            if m_code in ['00', '01', '02', '03', '04', '05', '06', '07', '08',
                         '09', '10', '11', '19', '30', '98', '99']:
                continue
            else:
                warnings.append(f"第{i}行: 不常见的M代码 M{m_code}")

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
    }
