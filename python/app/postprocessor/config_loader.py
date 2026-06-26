"""CNC后处理器配置加载与验证系统。

提供YAML配置文件解析、基础配置与控制器特定配置的深度合并、
配置完整性校验、参数类型及数值范围验证，以及配置缓存管理。
"""

from __future__ import annotations

import copy
import logging
import os
import time
from typing import Any, Dict, List, Optional, Tuple

import yaml

logger = logging.getLogger(__name__)

VALID_CONTROLLER_IDS = (
    "fanuc",
    "siemens",
    "heidenhain",
    "gsk",
    "hnc",
    "knd",
    "mitsubishi",
    "fagor",
    "xmachine",
)

# 顶层控制器全名 -> 控制器标识的映射（与 registry.py 保持一致）
CONTROLLER_FULL_ID_MAP = {
    "fanuc_0i": "fanuc",
    "siemens_840d": "siemens",
    "heidenhain_tnc": "heidenhain",
    "gsk_980_25i": "gsk",
    "hnc_848_22": "hnc",
    "knd_1000_2000_3000": "knd",
    "mitsubishi_m70_m80": "mitsubishi",
    "fagor_8055": "fagor",
    "xmachine_xm100": "xmachine",
}

# 控制器标识 -> 顶层控制器全名的映射（与 registry.py _register_builtin 保持一致）
CONTROLLER_ID_TO_FULL = {
    "fanuc": "fanuc_0i",
    "siemens": "siemens_840d",
    "heidenhain": "heidenhain_tnc",
    "gsk": "gsk_980_25i",
    "hnc": "hnc_848_22",
    "knd": "knd_1000_2000_3000",
    "mitsubishi": "mitsubishi_m70_m80",
    "fagor": "fagor_8055",
    "xmachine": "xmachine_xm100",
}

REQUIRED_TOP_KEYS = ("base", "controllers")
REQUIRED_BASE_KEYS = (
    "decimal_places",
    "safe_z_height",
    "rapid_feed",
    "spindle",
    "feed",
    "work_coordinate",
    "tool_offset",
    "fixed_cycles",
    "subprogram",
)
REQUIRED_SPINDLE_KEYS = ("min_rpm", "max_rpm", "default_rpm")
REQUIRED_FEED_KEYS = ("min_rate", "max_rate", "default_rate")
REQUIRED_WORK_COORD_KEYS = tuple(f"G{n}" for n in range(54, 60)) + (
    "default_coordinate_system",
)
REQUIRED_TOOL_OFFSET_KEYS = ("length_registers", "radius_registers")
REQUIRED_FIXED_CYCLE_GROUPS = ("drilling", "tapping", "boring", "threading")
REQUIRED_DRILLING_CYCLES = ("G81", "G83")
REQUIRED_TAPPING_CYCLES = ("G84")
REQUIRED_BORING_CYCLES = ("G86", "G89")
REQUIRED_THREADING_CYCLES = ("G76")
REQUIRED_SUBPROGRAM_KEYS = (
    "call_format",
    "end_code",
    "program_number",
    "repeat",
    "macro_variables",
)

COORD_SYSTEMS = tuple(f"G{n}" for n in range(54, 60))
VALID_RETRACT_MODES = ("G98", "G99")
VALID_RETRACT_TYPES = ("rapid", "feed", "oriented")
VALID_SPINDLE_DIRECTIONS = ("M03", "M04")
VALID_DECREMENT_TYPES = ("constant", "variable")
VALID_SHIFT_AXES = (None, "X", "Y")
VALID_INFEED_METHODS = ("compound", "radial", "flank")


class ConfigValidationError(Exception):
    """配置验证异常。"""


class ConfigLoadError(Exception):
    """配置加载异常。"""


def _deep_merge(base: dict, override: dict) -> dict:
    """深度合并两个字典，override中的值覆盖base中的同名键。

    嵌套字典递归合并，非字典值直接覆盖。
    不修改传入的字典，返回新字典。

    Args:
        base: 基础配置字典
        override: 覆盖配置字典

    Returns:
        合并后的新字典
    """
    result = copy.deepcopy(base)
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result


class ConfigValidator:
    """配置验证器。

    负责校验配置完整性、参数类型正确性及数值范围限制。
    """

    def __init__(self) -> None:
        self._errors: List[str] = []
        self._warnings: List[str] = []

    @property
    def errors(self) -> List[str]:
        return self._errors

    @property
    def warnings(self) -> List[str]:
        return self._warnings

    def _add_error(self, path: str, message: str) -> None:
        self._errors.append(f"[{path}] {message}")

    def _add_warning(self, path: str, message: str) -> None:
        self._warnings.append(f"[{path}] {message}")

    def _check_type(
        self,
        path: str,
        value: Any,
        expected_type: type,
        allow_none: bool = False,
    ) -> bool:
        if allow_none and value is None:
            return True
        if not isinstance(value, expected_type):
            self._add_error(
                path,
                f"类型错误: 期望 {expected_type.__name__}, 实际 {type(value).__name__}",
            )
            return False
        return True

    def _check_positive_int(self, path: str, value: Any) -> bool:
        if not self._check_type(path, value, int):
            return False
        if value < 0:
            self._add_error(path, f"值必须 >= 0, 当前: {value}")
            return False
        return True

    def _check_positive_float(self, path: str, value: Any) -> bool:
        if isinstance(value, int):
            value = float(value)
        if not self._check_type(path, value, float):
            return False
        if value < 0.0:
            self._add_error(path, f"值必须 >= 0, 当前: {value}")
            return False
        return True

    def _check_range(
        self,
        path: str,
        value: Any,
        min_val: float,
        max_val: float,
    ) -> bool:
        if isinstance(value, (int, float)):
            if value < min_val or value > max_val:
                self._add_error(
                    path,
                    f"值 {value} 超出范围 [{min_val}, {max_val}]",
                )
                return False
        return True

    def validate(self, config: dict) -> bool:
        """执行完整配置验证。

        Args:
            config: 合并后的最终配置字典

        Returns:
            True 表示验证通过，False 表示存在错误
        """
        self._errors.clear()
        self._warnings.clear()

        self._validate_top_level(config)
        self._validate_spindle(config.get("spindle", {}))
        self._validate_feed(config.get("feed", {}))
        self._validate_work_coordinate(config.get("work_coordinate", {}))
        self._validate_tool_offset(config.get("tool_offset", {}))
        self._validate_fixed_cycles(config.get("fixed_cycles", {}))
        self._validate_subprogram(config.get("subprogram", {}))

        if self._errors:
            logger.error(
                "配置验证失败 (%d 错误, %d 警告):\n%s",
                len(self._errors),
                len(self._warnings),
                "\n".join(self._errors),
            )
            return False

        if self._warnings:
            logger.warning(
                "配置验证通过 (%d 警告):\n%s",
                len(self._warnings),
                "\n".join(self._warnings),
            )
        return True

    def _validate_top_level(self, config: dict) -> None:
        path = "config"

        self._check_type(f"{path}.decimal_places", config.get("decimal_places"), int)
        dp = config.get("decimal_places", 3)
        if isinstance(dp, int) and dp < 0:
            self._add_error(f"{path}.decimal_places", f"不能为负数: {dp}")

        self._check_positive_float(f"{path}.safe_z_height", config.get("safe_z_height"))
        sh = config.get("safe_z_height", 50.0)
        if isinstance(sh, (int, float)) and sh <= 0:
            self._add_error(f"{path}.safe_z_height", f"必须大于0: {sh}")

        self._check_positive_float(f"{path}.rapid_feed", config.get("rapid_feed"))

    def _validate_spindle(self, spindle: dict) -> None:
        path = "spindle"
        for key in REQUIRED_SPINDLE_KEYS:
            if key not in spindle:
                self._add_error(path, f"缺少必需参数: {key}")
        for key in REQUIRED_SPINDLE_KEYS:
            if key in spindle:
                self._check_positive_int(f"{path}.{key}", spindle[key])

        min_rpm = spindle.get("min_rpm", 0)
        max_rpm = spindle.get("max_rpm", 0)
        default_rpm = spindle.get("default_rpm", 0)

        if isinstance(min_rpm, int) and isinstance(max_rpm, int):
            if min_rpm >= max_rpm:
                self._add_error(
                    path,
                    f"min_rpm ({min_rpm}) 必须小于 max_rpm ({max_rpm})",
                )
        if (
            isinstance(default_rpm, int)
            and isinstance(min_rpm, int)
            and isinstance(max_rpm, int)
        ):
            if not (min_rpm <= default_rpm <= max_rpm):
                self._add_warning(
                    path,
                    f"default_rpm ({default_rpm}) 不在 [{min_rpm}, {max_rpm}] 范围内",
                )

    def _validate_feed(self, feed: dict) -> None:
        path = "feed"
        for key in REQUIRED_FEED_KEYS:
            if key not in feed:
                self._add_error(path, f"缺少必需参数: {key}")

        min_rate = feed.get("min_rate", 0)
        max_rate = feed.get("max_rate", 0)
        default_rate = feed.get("default_rate", 0)

        self._check_positive_float(f"{path}.min_rate", min_rate)
        self._check_positive_float(f"{path}.max_rate", max_rate)
        self._check_positive_float(f"{path}.default_rate", default_rate)

        if isinstance(min_rate, (int, float)) and isinstance(max_rate, (int, float)):
            if min_rate >= max_rate:
                self._add_error(
                    path,
                    f"min_rate ({min_rate}) 必须小于 max_rate ({max_rate})",
                )

    def _validate_work_coordinate(self, wcs: dict) -> None:
        path = "work_coordinate"
        for key in COORD_SYSTEMS:
            if key not in wcs:
                self._add_error(path, f"缺少坐标系: {key}")
                continue
            coord = wcs[key]
            if not isinstance(coord, dict):
                self._add_error(f"{path}.{key}", "必须为字典类型")
                continue
            for axis in ("x_offset", "y_offset", "z_offset"):
                if axis in coord:
                    self._check_type(f"{path}.{key}.{axis}", coord[axis], (int, float))
            self._check_type(f"{path}.{key}.enabled", coord.get("enabled"), bool)

        default_cs = wcs.get("default_coordinate_system")
        if default_cs is None:
            self._add_error(path, "缺少 default_coordinate_system")
        elif default_cs not in COORD_SYSTEMS:
            self._add_error(
                path,
                f"default_coordinate_system 无效: {default_cs}, 有效值: {COORD_SYSTEMS}",
            )

    def _validate_tool_offset(self, tool_offset: dict) -> None:
        path = "tool_offset"
        for key in REQUIRED_TOOL_OFFSET_KEYS:
            if key not in tool_offset:
                self._add_error(path, f"缺少必需参数: {key}")
                continue

            reg = tool_offset[key]
            if not isinstance(reg, dict):
                self._add_error(f"{path}.{key}", "必须为字典类型")
                continue

            self._check_positive_int(f"{path}.{key}.start", reg.get("start"))
            self._check_positive_int(f"{path}.{key}.end", reg.get("end"))

            if (
                isinstance(reg.get("start"), int)
                and isinstance(reg.get("end"), int)
                and reg["start"] > reg["end"]
            ):
                self._add_error(
                    f"{path}.{key}",
                    f"start ({reg['start']}) 不能大于 end ({reg['end']})",
                )

            self._check_positive_float(
                f"{path}.{key}.default_offset", reg.get("default_offset")
            )

        self._validate_radius_compensation_types(tool_offset)

    def _validate_radius_compensation_types(self, tool_offset: dict) -> None:
        path = "tool_offset.radius_registers.compensation_types"
        radius_regs = tool_offset.get("radius_registers", {})
        if not isinstance(radius_regs, dict):
            return

        comp_types = radius_regs.get("compensation_types", {})
        if not isinstance(comp_types, dict):
            self._add_error(path, "必须为字典类型")
            return

        for comp_name in ("G41", "G42"):
            if comp_name not in comp_types:
                self._add_error(path, f"缺少补偿类型: {comp_name}")
                continue
            ct = comp_types[comp_name]
            if not isinstance(ct, dict):
                self._add_error(f"{path}.{comp_name}", "必须为字典类型")
                continue
            reg_range = ct.get("register_range")
            if reg_range is None:
                self._add_error(f"{path}.{comp_name}", "缺少 register_range")
            elif not isinstance(reg_range, list) or len(reg_range) != 2:
                self._add_error(
                    f"{path}.{comp_name}.register_range",
                    "必须为长度为2的列表 [min, max]",
                )
            else:
                if not all(isinstance(v, int) for v in reg_range):
                    self._add_error(
                        f"{path}.{comp_name}.register_range",
                        "元素必须为整数",
                    )
                elif reg_range[0] > reg_range[1]:
                    self._add_error(
                        f"{path}.{comp_name}.register_range",
                        f"起始值 {reg_range[0]} 不能大于结束值 {reg_range[1]}",
                    )

    def _validate_fixed_cycles(self, fixed_cycles: dict) -> None:
        path = "fixed_cycles"

        for group in REQUIRED_FIXED_CYCLE_GROUPS:
            if group not in fixed_cycles:
                self._add_error(path, f"缺少循环组: {group}")
            elif not isinstance(fixed_cycles[group], dict):
                self._add_error(f"{path}.{group}", "必须为字典类型")

        if isinstance(fixed_cycles.get("drilling"), dict):
            dr = fixed_cycles["drilling"]
            for cyc in REQUIRED_DRILLING_CYCLES:
                if cyc not in dr:
                    self._add_error(f"{path}.drilling", f"缺少钻孔循环: {cyc}")
                elif isinstance(dr[cyc], dict):
                    self._validate_drilling_cycle(f"{path}.drilling.{cyc}", dr[cyc])

        if isinstance(fixed_cycles.get("tapping"), dict):
            tp = fixed_cycles["tapping"]
            if REQUIRED_TAPPING_CYCLES not in tp:
                self._add_error(f"{path}.tapping", f"缺少攻丝循环: {REQUIRED_TAPPING_CYCLES}")
            elif isinstance(tp[REQUIRED_TAPPING_CYCLES], dict):
                self._validate_tapping_cycle(
                    f"{path}.tapping.{REQUIRED_TAPPING_CYCLES}",
                    tp[REQUIRED_TAPPING_CYCLES],
                )

        if isinstance(fixed_cycles.get("boring"), dict):
            br = fixed_cycles["boring"]
            for cyc in REQUIRED_BORING_CYCLES:
                if cyc not in br:
                    self._add_error(f"{path}.boring", f"缺少镗孔循环: {cyc}")
                elif isinstance(br[cyc], dict):
                    self._validate_boring_cycle(f"{path}.boring.{cyc}", br[cyc])

        if isinstance(fixed_cycles.get("threading"), dict):
            th = fixed_cycles["threading"]
            if REQUIRED_THREADING_CYCLES not in th:
                self._add_error(
                    f"{path}.threading",
                    f"缺少螺纹加工循环: {REQUIRED_THREADING_CYCLES}",
                )
            elif isinstance(th[REQUIRED_THREADING_CYCLES], dict):
                self._validate_threading_cycle(
                    f"{path}.threading.{REQUIRED_THREADING_CYCLES}",
                    th[REQUIRED_THREADING_CYCLES],
                )

    def _validate_drilling_cycle(self, path: str, cycle: dict) -> None:
        self._check_type(f"{path}.retract_mode", cycle.get("retract_mode"), str)
        if cycle.get("retract_mode") not in VALID_RETRACT_MODES:
            self._add_error(
                path,
                f"retract_mode 无效: {cycle.get('retract_mode')}, 有效值: {VALID_RETRACT_MODES}",
            )
        self._check_positive_float(f"{path}.peck_depth", cycle.get("peck_depth"))
        self._check_positive_float(f"{path}.retract_distance", cycle.get("retract_distance"))
        if "dwell_time" in cycle:
            self._check_positive_float(f"{path}.dwell_time", cycle.get("dwell_time"))
        if "decrement_type" in cycle:
            if cycle.get("decrement_type") not in VALID_DECREMENT_TYPES:
                self._add_error(
                    path,
                    f"decrement_type 无效: {cycle.get('decrement_type')}, "
                    f"有效值: {VALID_DECREMENT_TYPES}",
                )

    def _validate_tapping_cycle(self, path: str, cycle: dict) -> None:
        if cycle.get("spindle_direction") not in VALID_SPINDLE_DIRECTIONS:
            self._add_error(
                path,
                f"spindle_direction 无效: {cycle.get('spindle_direction')}, "
                f"有效值: {VALID_SPINDLE_DIRECTIONS}",
            )
        self._check_type(f"{path}.feed_per_rev", cycle.get("feed_per_rev"), bool)
        self._check_positive_float(f"{path}.dwell_time", cycle.get("dwell_time"))
        if cycle.get("retract_spindle_direction") not in VALID_SPINDLE_DIRECTIONS:
            self._add_error(
                path,
                f"retract_spindle_direction 无效: "
                f"{cycle.get('retract_spindle_direction')}",
            )

    def _validate_boring_cycle(self, path: str, cycle: dict) -> None:
        if cycle.get("retract_mode") not in VALID_RETRACT_MODES:
            self._add_error(
                path,
                f"retract_mode 无效: {cycle.get('retract_mode')}",
            )
        self._check_positive_float(f"{path}.dwell_time", cycle.get("dwell_time"))
        if cycle.get("retract_type") not in VALID_RETRACT_TYPES:
            self._add_error(
                path,
                f"retract_type 无效: {cycle.get('retract_type')}",
            )
        self._check_type(f"{path}.orient_spindle", cycle.get("orient_spindle"), bool)
        if cycle.get("shift_axis") not in VALID_SHIFT_AXES:
            self._add_error(
                path,
                f"shift_axis 无效: {cycle.get('shift_axis')}",
            )
        self._check_positive_float(f"{path}.shift_distance", cycle.get("shift_distance"))

    def _validate_threading_cycle(self, path: str, cycle: dict) -> None:
        if cycle.get("retract_mode") not in VALID_RETRACT_MODES:
            self._add_error(
                path,
                f"retract_mode 无效: {cycle.get('retract_mode')}",
            )
        self._check_positive_float(f"{path}.lead", cycle.get("lead"))
        self._check_positive_int(f"{path}.passes", cycle.get("passes"))
        self._check_positive_float(f"{path}.depth_cut_first", cycle.get("depth_cut_first"))
        self._check_positive_float(f"{path}.depth_cut_last", cycle.get("depth_cut_last"))
        self._check_positive_int(f"{path}.finishing_passes", cycle.get("finishing_passes"))
        self._check_positive_float(f"{path}.taper", cycle.get("taper"))
        self._check_positive_float(f"{path}.tool_angle", cycle.get("tool_angle"))
        if cycle.get("retract_type") not in VALID_RETRACT_TYPES:
            self._add_error(
                path,
                f"retract_type 无效: {cycle.get('retract_type')}",
            )
        if cycle.get("shift_axis") not in VALID_SHIFT_AXES:
            self._add_error(
                path,
                f"shift_axis 无效: {cycle.get('shift_axis')}",
            )
        self._check_positive_float(f"{path}.shift_distance", cycle.get("shift_distance"))
        if cycle.get("infeed_method") not in VALID_INFEED_METHODS:
            self._add_error(
                path,
                f"infeed_method 无效: {cycle.get('infeed_method')}, "
                f"有效值: {VALID_INFEED_METHODS}",
            )

    def _validate_subprogram(self, sub: dict) -> None:
        path = "subprogram"
        for key in ("call_format", "end_code"):
            if key not in sub:
                self._add_error(path, f"缺少必需参数: {key}")
            else:
                self._check_type(f"{path}.{key}", sub[key], str)

        prog_num = sub.get("program_number", {})
        if isinstance(prog_num, dict):
            self._check_positive_int(f"{path}.program_number.minimum", prog_num.get("minimum"))
            self._check_positive_int(f"{path}.program_number.maximum", prog_num.get("maximum"))
            self._check_type(f"{path}.program_number.format", prog_num.get("format"), str)

        repeat = sub.get("repeat", {})
        if isinstance(repeat, dict):
            self._check_positive_int(f"{path}.repeat.default", repeat.get("default"))
            self._check_positive_int(f"{path}.repeat.minimum", repeat.get("minimum"))
            self._check_positive_int(f"{path}.repeat.maximum", repeat.get("maximum"))

        macro = sub.get("macro_variables", {})
        if isinstance(macro, dict):
            for var_type in ("local", "common", "system"):
                if var_type not in macro:
                    self._add_error(path, f"缺少宏变量类型: {var_type}")
                elif isinstance(macro[var_type], dict):
                    rng = macro[var_type].get("range")
                    if not isinstance(rng, list) or len(rng) != 2:
                        self._add_error(
                            f"{path}.macro_variables.{var_type}",
                            "range 必须为长度为2的列表",
                        )
                    elif not all(isinstance(v, int) for v in rng):
                        self._add_error(
                            f"{path}.macro_variables.{var_type}.range",
                            "元素必须为整数",
                        )


class ConfigLimiter:
    """配置参数限幅器。

    当进给速度、主轴转速或坐标轴位置超出配置范围时，自动限制在最大/最小值，
    并记录超限日志。坐标轴软限位是安全关键功能，防止机床超程碰撞。
    """

    def __init__(self, config: dict | None = None) -> None:
        config = config or {}
        self._spindle_min = config.get("spindle", {}).get("min_rpm", 50)
        self._spindle_max = config.get("spindle", {}).get("max_rpm", 24000)
        self._spindle_default = config.get("spindle", {}).get("default_rpm", 1000)

        self._feed_min = config.get("feed", {}).get("min_rate", 10.0)
        self._feed_max = config.get("feed", {}).get("max_rate", 20000.0)
        self._feed_default = config.get("feed", {}).get("default_rate", 1000.0)

        # 坐标轴软限位配置（安全关键）
        axis_limits = config.get("axis_limits", {})
        self._axis_limits_enabled = axis_limits.get("enabled", False)
        self._x_min = axis_limits.get("x_min", -1000.0)
        self._x_max = axis_limits.get("x_max", 1000.0)
        self._y_min = axis_limits.get("y_min", -1000.0)
        self._y_max = axis_limits.get("y_max", 1000.0)
        self._z_min = axis_limits.get("z_min", -500.0)
        self._z_max = axis_limits.get("z_max", 500.0)

    def limit_spindle_rpm(self, rpm: float, context: str = "") -> float:
        """限制主轴转速在允许范围内。

        Args:
            rpm: 请求的主轴转速 (RPM)
            context: 调用上下文（用于日志记录）

        Returns:
            限制后的主轴转速
        """
        original = rpm
        if rpm < self._spindle_min:
            rpm = float(self._spindle_min)
            logger.warning(
                "主轴转速超下限 [%s]: 原始值 %.1f RPM -> 限制值 %.1f RPM (min: %d)",
                context, original, rpm, self._spindle_min,
            )
        elif rpm > self._spindle_max:
            rpm = float(self._spindle_max)
            logger.warning(
                "主轴转速超上限 [%s]: 原始值 %.1f RPM -> 限制值 %.1f RPM (max: %d)",
                context, original, rpm, self._spindle_max,
            )
        return rpm

    def limit_feed_rate(self, feed: float, context: str = "") -> float:
        """限制进给速度在允许范围内。

        Args:
            feed: 请求的进给速度 (mm/min)
            context: 调用上下文（用于日志记录）

        Returns:
            限制后的进给速度
        """
        original = feed
        if feed < self._feed_min:
            feed = self._feed_min
            logger.warning(
                "进给速度超下限 [%s]: 原始值 %.2f mm/min -> 限制值 %.2f mm/min (min: %.2f)",
                context, original, feed, self._feed_min,
            )
        elif feed > self._feed_max:
            feed = self._feed_max
            logger.warning(
                "进给速度超上限 [%s]: 原始值 %.2f mm/min -> 限制值 %.2f mm/min (max: %.2f)",
                context, original, feed, self._feed_max,
            )
        return feed

    def limit_axis_position(self, axis: str, position: float, context: str = "") -> float:
        """限制坐标轴位置在软限位范围内。

        安全关键功能：防止机床超程碰撞。当坐标轴位置超出配置的软限位范围时，
        自动限制在最大/最小值，并记录超限日志。

        Args:
            axis: 坐标轴名称 ("X", "Y", 或 "Z")
            position: 请求的坐标轴位置 (mm)
            context: 调用上下文（用于日志记录）

        Returns:
            限制后的坐标轴位置

        Raises:
            ValueError: 当坐标轴名称无效时
        """
        if not self._axis_limits_enabled:
            return position

        axis = axis.upper()
        original = position

        if axis == "X":
            min_val, max_val = self._x_min, self._x_max
        elif axis == "Y":
            min_val, max_val = self._y_min, self._y_max
        elif axis == "Z":
            min_val, max_val = self._z_min, self._z_max
        else:
            raise ValueError(f"无效的坐标轴: {axis}，有效值: X, Y, Z")

        if position < min_val:
            position = min_val
            logger.warning(
                "坐标轴软限位超下限 [%s]: %s轴 原始值 %.3f mm -> 限制值 %.3f mm (min: %.3f)",
                context, axis, original, position, min_val,
            )
        elif position > max_val:
            position = max_val
            logger.warning(
                "坐标轴软限位超上限 [%s]: %s轴 原始值 %.3f mm -> 限制值 %.3f mm (max: %.3f)",
                context, axis, original, position, max_val,
            )

        return position

    def get_spindle_default(self) -> float:
        return float(self._spindle_default)

    def get_feed_default(self) -> float:
        return float(self._feed_default)


class ConfigLoader:
    """CNC后处理器配置加载器。

    负责YAML文件加载、基础配置与控制器特定配置的合并、
    配置验证、以及配置缓存管理。
    """

    _cache: Dict[str, Tuple[dict, float]] = {}
    _cache_ttl: float = 300.0

    def __init__(self, cache_ttl: float = 300.0) -> None:
        """初始化配置加载器。

        Args:
            cache_ttl: 缓存有效期（秒），默认300秒
        """
        self._cache_ttl = cache_ttl

    @classmethod
    def clear_cache(cls, controller_id: Optional[str] = None) -> None:
        """清除配置缓存。

        Args:
            controller_id: 指定控制器清除，None 则清除全部
        """
        if controller_id is None:
            cls._cache.clear()
            logger.info("已清除全部配置缓存")
        elif controller_id in cls._cache:
            del cls._cache[controller_id]
            logger.info("已清除控制器 %s 的配置缓存", controller_id)

    def _resolve_path(self, config_path: Optional[str]) -> str:
        """解析配置文件路径。

        支持相对路径（相对于项目根目录）和绝对路径。

        Args:
            config_path: 配置文件路径

        Returns:
            解析后的绝对路径
        """
        if config_path is None:
            project_root = os.path.dirname(
                os.path.dirname(
                    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                )
            )
            return os.path.join(project_root, "config", "postprocessor_config.yaml")

        if os.path.isabs(config_path):
            return config_path

        project_root = os.path.dirname(
            os.path.dirname(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            )
        )
        return os.path.join(project_root, config_path)

    def load(
        self,
        config_path: Optional[str] = None,
        controller_id: Optional[str] = None,
        use_cache: bool = True,
    ) -> dict:
        """加载并合并配置。

        加载顺序：
        1. 解析YAML文件
        2. 提取基础配置（base段）
        3. 提取控制器特定配置并深度合并到基础配置
        4. 验证最终配置

        Args:
            config_path: 配置文件路径，None 使用默认路径
            controller_id: 控制器标识 (fanuc/siemens/heidenhain)，
                           None 则从配置中读取 target_controller
            use_cache: 是否使用缓存

        Returns:
            合并后的完整配置字典

        Raises:
            FileNotFoundError: 配置文件不存在
            ConfigLoadError: YAML解析失败
            ConfigValidationError: 配置验证失败
        """
        resolved_path = self._resolve_path(config_path)
        cache_key = f"{resolved_path}:{controller_id or 'auto'}"

        if use_cache and cache_key in self._cache:
            cached_config, cached_time = self._cache[cache_key]
            if time.time() - cached_time < self._cache_ttl:
                logger.debug("使用缓存配置: %s", cache_key)
                return copy.deepcopy(cached_config)
            del self._cache[cache_key]

        raw_config = self._load_yaml(resolved_path)

        base_config = raw_config.get("base", {})
        if not base_config:
            raise ConfigLoadError("配置文件中缺少 'base' 段")

        if controller_id is None:
            controller_id = self._resolve_controller_id(raw_config, base_config)

        if controller_id not in VALID_CONTROLLER_IDS:
            raise ConfigLoadError(
                f"无效的控制器标识: '{controller_id}', "
                f"有效值: {VALID_CONTROLLER_IDS}"
            )

        controller_specific = (
            raw_config.get("controllers", {}).get(controller_id, {})
        )

        merged_config = _deep_merge(base_config, controller_specific)

        merged_config["_controller_id"] = controller_id
        merged_config["_config_path"] = resolved_path

        validator = ConfigValidator()
        if not validator.validate(merged_config):
            error_details = "\n".join(validator.errors)
            raise ConfigValidationError(
                f"配置验证失败 ({len(validator.errors)} 错误):\n{error_details}"
            )

        self._cache[cache_key] = (copy.deepcopy(merged_config), time.time())
        logger.info(
            "配置加载成功: 控制器=%s, 路径=%s", controller_id, resolved_path
        )

        return merged_config

    def _load_yaml(self, file_path: str) -> dict:
        """加载并解析YAML文件。

        Args:
            file_path: YAML文件绝对路径

        Returns:
            解析后的字典

        Raises:
            FileNotFoundError: 文件不存在
            ConfigLoadError: YAML解析失败
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"配置文件不存在: {file_path}")

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
        except yaml.YAMLError as e:
            raise ConfigLoadError(f"YAML解析失败 ({file_path}): {e}") from e

        if data is None:
            raise ConfigLoadError(f"配置文件为空: {file_path}")

        if not isinstance(data, dict):
            raise ConfigLoadError(
                f"配置文件格式错误: 期望字典类型, 实际 {type(data).__name__}"
            )

        return data

    def _resolve_controller_id(self, raw_config: dict, base_config: dict) -> str:
        """从配置中解析控制器标识。

        优先级：控制器特定配置的 target_controller > 顶层 target_controller > fanuc

        Args:
            raw_config: 原始YAML配置
            base_config: 基础配置

        Returns:
            控制器标识字符串
        """
        top_controller = raw_config.get("target_controller", "")
        if top_controller in CONTROLLER_FULL_ID_MAP:
            return CONTROLLER_FULL_ID_MAP[top_controller]

        for cid, full_name in CONTROLLER_ID_TO_FULL.items():
            ctrl = raw_config.get("controllers", {}).get(cid, {})
            if ctrl.get("target_controller") == full_name:
                return cid

        logger.warning(
            "无法确定控制器类型，使用默认: fanuc"
        )
        return "fanuc"

    def load_for_controller(
        self,
        controller_id: str,
        config_path: Optional[str] = None,
    ) -> dict:
        """加载指定控制器的配置。

        Args:
            controller_id: 控制器标识 (fanuc/siemens/heidenhain)
            config_path: 配置文件路径

        Returns:
            合并后的控制器配置字典

        Raises:
            ConfigLoadError: 无效的控制器标识
            ConfigValidationError: 配置验证失败
        """
        return self.load(config_path=config_path, controller_id=controller_id)

    def reload(self, config_path: Optional[str] = None) -> dict:
        """强制重新加载配置（忽略缓存）。

        Args:
            config_path: 配置文件路径

        Returns:
            合并后的完整配置字典
        """
        self.clear_cache()
        return self.load(config_path=config_path, use_cache=False)


def create_limiter(config: dict) -> ConfigLimiter:
    """从配置字典创建限幅器实例。

    Args:
        config: 合并后的配置字典

    Returns:
        ConfigLimiter 实例
    """
    return ConfigLimiter(config)
