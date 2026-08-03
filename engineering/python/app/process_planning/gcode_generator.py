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

import logging
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

logger = logging.getLogger(__name__)

from app.process_planning._schemas import GCodeResult
from app.process_planning._validation import (
    validate_gcode,
    validate_gcode_syntax,
    build_dry_run_preview,
)

logger = logging.getLogger(__name__)


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

        # 五轴机床 Z 行程通常较小（XM-100 仅 ±50mm），
        # 默认 safe_z=80.0 会超出物理限制导致后处理器校验失败。
        # 此处自动 clamp 到机床行程上限的 90%（留 10% 余量）。
        if is_five_axis:
            travel_z = getattr(postprocessor, "XM100_TRAVEL_Z", None)
            if travel_z is not None:
                max_safe_z = travel_z / 2 * 0.9
                if safe_z > max_safe_z:
                    logger.warning(
                        "safe_z=%.1f 超过 XM-100 Z 行程上限 ±%.0fmm，自动 clamp 到 %.1fmm",
                        safe_z, travel_z / 2, max_safe_z,
                    )
                    safe_z = max_safe_z

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
        _current_tool = ""
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
                _current_tool = tool_key

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
        """G代码语法校验（增强版）。委托 _validation.validate_gcode_syntax。"""
        return validate_gcode_syntax(program_text, controller_type)

    def dry_run_preview(
        self,
        operation_plan: OperationPlan,
        controller_type: str = "fanuc_0i",
        material_name: str = "45#钢",
        program_number: int = 1000,
        safe_z: float = 80.0,
        stock_top_z: float = 50.0,
    ) -> dict[str, Any]:
        """G代码 dry-run 预览模式。委托 _validation.build_dry_run_preview。"""
        return build_dry_run_preview(
            operation_plan,
            controller_type=controller_type,
            material_name=material_name,
            program_number=program_number,
            safe_z=safe_z,
            stock_top_z=stock_top_z,
        )


    def list_available_controllers(self) -> list[str]:
        """列出所有可用的控制器类型"""
        return list(self.CONTROLLER_MAP.keys())

