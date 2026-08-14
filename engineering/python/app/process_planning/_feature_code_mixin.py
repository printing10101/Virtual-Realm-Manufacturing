"""工序特征 G 代码生成 mixin（从 gcode_generator 拆出）。"""

from __future__ import annotations

from app.cutting_params_db import get_cutting_params
from app.postprocessor.base import BasePostProcessor
from app.process_planning.operation_sequencer import Operation


class _FeatureCodeMixin:
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
                spindle_speed = self._config_limiter.limit_spindle_rpm(spindle_speed, context=f"钻孔-{op.feature_name}")
                feed_rate = self._config_limiter.limit_feed_rate(feed_rate, context=f"钻孔-{op.feature_name}")

            lines.append(f"S{spindle_speed} M03")
            lines.append(postprocessor._comment(f"进给: {recommended_feed}, 切速: {recommended_speed}"))
            lines.append(postprocessor._comment(f"参数来自数据库: 材料={material}, 直径={tool_diameter}mm"))

            # 五轴模式：开启 RTCP
            if is_five_axis and hasattr(postprocessor, "format_rtcp_on"):
                lines.append(postprocessor.format_rtcp_on())

            # 使用后处理器的钻孔固定循环 - 使用实际坐标
            # Z 坐标基于 stock_top_z 向下计算（避免负值触发过切误报）
            drill_z = stock_top_z - abs(depth)
            lines.append(
                postprocessor.format_cycle_drill(
                    x=x_pos,
                    y=y_pos,
                    z=drill_z,
                    depth=depth,
                    dwell=0.5 if depth > 15 else 0.0,
                )
            )
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
                spindle_speed = self._config_limiter.limit_spindle_rpm(spindle_speed, context=f"铣削-{op.feature_name}")
                feed_rate = self._config_limiter.limit_feed_rate(feed_rate, context=f"铣削-{op.feature_name}")

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
                    start_x=start_x,
                    start_y=start_y,
                    start_z=start_z,
                    end_x=end_x,
                    end_y=end_y,
                    end_z=end_z,
                    surface_normal_i=0.0,
                    surface_normal_j=0.0,
                    surface_normal_k=1.0,
                    num_points=4,
                )

                # 根据刀具姿态生成带 A/C 轴的直线插补
                for idx, orient in enumerate(orientations):
                    t = idx / max(1, len(orientations) - 1)
                    interp_x = start_x + t * (end_x - start_x)
                    interp_y = start_y + t * (end_y - start_y)

                    lines.append(
                        postprocessor.format_linear_move(
                            x=interp_x,
                            y=interp_y,
                            z=mill_depth,
                            feed=feed_rate,
                            a=orient.a_angle,
                            c=orient.c_angle,
                        )
                    )

                lines.append(postprocessor.format_rtcp_off())
            else:
                # 三轴铣削 - 使用实际坐标
                if radius_comp not in ["G41", "G42"]:
                    # 抬刀到安全平面后再快速定位（避免G00在切削深度处移动引发碰撞）
                    lines.append(f"G00 Z{safe_z:.3f}")
                    lines.append(f"G00 X{x_pos:.3f} Y{y_pos:.3f}")
                    lines.append(f"G01 Z{mill_depth:.3f} F{feed_rate}")
                lines.append(
                    postprocessor.format_linear_move(
                        x=x_pos + mill_length,
                        y=y_pos,
                        z=mill_depth,
                        feed=feed_rate,
                    )
                )
                lines.append(
                    postprocessor.format_linear_move(
                        x=x_pos + mill_length,
                        y=y_pos + mill_width,
                        z=mill_depth,
                        feed=feed_rate,
                    )
                )

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
                spindle_speed = self._config_limiter.limit_spindle_rpm(spindle_speed, context=f"车削-{op.feature_name}")
                feed_rate = self._config_limiter.limit_feed_rate(feed_rate, context=f"车削-{op.feature_name}")

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
                spindle_speed = self._config_limiter.limit_spindle_rpm(spindle_speed, context=f"镗孔-{op.feature_name}")
                feed_rate = self._config_limiter.limit_feed_rate(feed_rate, context=f"镗孔-{op.feature_name}")

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
                spindle_speed = self._config_limiter.limit_spindle_rpm(spindle_speed, context=f"五轴-{op.feature_name}")
                feed_rate = self._config_limiter.limit_feed_rate(feed_rate, context=f"五轴-{op.feature_name}")

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
                    start_x=start_x,
                    start_y=start_y,
                    start_z=start_z,
                    end_x=end_x,
                    end_y=end_y,
                    end_z=end_z,
                    surface_normal_i=0.0,
                    surface_normal_j=0.0,
                    surface_normal_k=1.0,
                    num_points=5,
                )

                # 根据刀具姿态生成 A/C 轴命令
                for i, orient in enumerate(orientations):
                    # 计算路径点位置（线性插值）
                    t = i / max(1, len(orientations) - 1)
                    interp_x = start_x + t * (end_x - start_x)
                    interp_y = start_y + t * (end_y - start_y)
                    interp_z = work_depth

                    # 生成带 A/C 轴的直线插补
                    lines.append(
                        postprocessor.format_linear_move(
                            x=interp_x,
                            y=interp_y,
                            z=interp_z,
                            feed=feed_rate,
                            a=orient.a_angle,
                            c=orient.c_angle,
                        )
                    )

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
