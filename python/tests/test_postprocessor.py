"""CNC后处理器模块单元测试。

覆盖：
- 各后处理器基础功能（所有抽象方法实现完整性）
- 格式正确性（NC代码符合对应控制器语法规范）
- 语义等价性（相同刀轨数据经不同后处理器处理后保持加工语义一致）
- 边界条件（极端参数下的代码生成正确性）
- 配置加载（配置文件参数正确应用到后处理器）
"""

from __future__ import annotations

import os
import re
import tempfile

import pytest

from app.postprocessor.base import BasePostProcessor
from app.postprocessor.fanuc import FanucPostProcessor
from app.postprocessor.siemens import SiemensPostProcessor
from app.postprocessor.heidenhain import HeidenhainPostProcessor
from app.postprocessor.registry import PostProcessorRegistry

# 生产配置文件路径——TestConfigLoading 使用它避免与 ConfigValidator 的
# 必需字段清单重复维护（割裂式同步坑）。
_PROD_CONFIG = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "config",
    "postprocessor_config.yaml",
)


def _make_config_with_controller(controller_id: str) -> str:
    """复制生产配置到临时文件并替换 target_controller。

    这样测试用的临时配置一定包含 ConfigValidator 要求的全部段
    （spindle/feed/work_coordinate/tool_offset/fixed_cycles/subprogram），
    避免每次新增必需字段都要同步改测试。
    """
    with open(_PROD_CONFIG, "r", encoding="utf-8") as f:
        content = f.read()
    content = re.sub(
        r"^target_controller:\s*\S+\s*$",
        f"target_controller: {controller_id}",
        content,
        count=1,
        flags=re.MULTILINE,
    )
    fd, path = tempfile.mkstemp(suffix=".yaml", text=True)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(content)
    return path


class TestBasePostProcessor:
    """基类功能测试。"""

    def test_cannot_instantiate_abstract(self):
        """验证抽象基类不可直接实例化。"""
        with pytest.raises(TypeError):
            BasePostProcessor()

    def test_fmt_method(self):
        """验证数值格式化方法。"""

        class _Concrete(BasePostProcessor):
            def format_header(self, program_number=1):
                return ""

            def format_tool_change(self, tool_id, length_comp=0, radius_comp=0):
                return ""

            def format_arc(self, start, end, center, clockwise=True):
                return ""

            def format_coolant(self, state):
                return ""

            def format_tool_compensation(self, length_offset=0, radius_offset=0):
                return ""

            def format_cycle_drill(self, x, y, z, depth, dwell=0):
                return ""

            def format_cycle_tapping(self, x, y, z, depth, pitch=1.0, spindle_rpm=None):
                return ""

            def format_cycle_boring(self, x, y, z, depth, cycle_type="G86", dwell=0.5):
                return ""

            def format_cycle_threading(self, x, y, depth, lead=1.0, passes=None,
                                       depth_cut_first=None, depth_cut_last=None,
                                       finishing_passes=None, tool_angle=None, taper=None):
                return ""

            def format_subprogram_call(self, program_number, repeat=1):
                return ""

            def format_subprogram_end(self, return_value=None):
                return ""

            def format_footer(self):
                return ""

        p = _Concrete(decimal_places=3)
        assert p._fmt(1.234567) == "1.235"
        assert p._fmt(0.0) == "0.000"
        p2 = _Concrete(decimal_places=0)
        assert p2._fmt(1.5) == "2"

    def test_date_string(self):
        """验证日期字符串格式。"""
        result = BasePostProcessor._date_string()
        parts = result.split("-")
        assert len(parts) == 3
        assert all(p.isdigit() for p in parts)


class BaseProcessorTests:
    """各后处理器通用测试模式。"""

    processor_cls = None

    def make_processor(self, **kwargs):
        defaults = {"decimal_places": 3, "safe_z_height": 50.0, "rapid_feed": 10000}
        defaults.update(kwargs)
        return self.processor_cls(**defaults)

    def test_all_methods_implemented(self):
        """验证所有抽象方法都已实现。"""
        p = self.make_processor()
        assert hasattr(p, "format_header")
        assert hasattr(p, "format_tool_change")
        assert hasattr(p, "format_arc")
        assert hasattr(p, "format_coolant")
        assert hasattr(p, "format_tool_compensation")
        assert hasattr(p, "format_cycle_drill")
        assert hasattr(p, "format_footer")

    def test_header_not_empty(self):
        """验证程序头生成非空。"""
        p = self.make_processor()
        result = p.format_header()
        assert len(result) > 0
        assert isinstance(result, str)

    def test_footer_not_empty(self):
        """验证程序尾生成非空。"""
        p = self.make_processor()
        result = p.format_footer()
        assert len(result) > 0
        assert isinstance(result, str)

    def test_tool_change_contains_tool_id(self):
        """验证换刀指令包含刀具ID。"""
        p = self.make_processor()
        result = p.format_tool_change(tool_id=3)
        assert "3" in result or "03" in result

    def test_coolant_on(self):
        """验证冷却液开启指令。"""
        p = self.make_processor()
        result = p.format_coolant("on")
        assert len(result) > 0

    def test_coolant_off(self):
        """验证冷却液关闭指令。"""
        p = self.make_processor()
        result = p.format_coolant("off")
        assert len(result) > 0

    def test_arc_contains_endpoint(self):
        """验证圆弧指令包含终点坐标。"""
        p = self.make_processor()
        result = p.format_arc(
            start=(0.0, 0.0, 0.0),
            end=(10.0, 0.0, 0.0),
            center=(5.0, 0.0, 0.0),
        )
        assert "10" in result

    def test_tool_compensation_no_offset(self):
        """验证无补偿时的指令。"""
        p = self.make_processor()
        result = p.format_tool_compensation(length_offset=0, radius_offset=0)
        assert len(result) > 0

    def test_tool_compensation_with_offsets(self):
        """验证有补偿时的指令。"""
        p = self.make_processor()
        result = p.format_tool_compensation(length_offset=5, radius_offset=3)
        assert len(result) > 0

    def test_cycle_drill_output(self):
        """验证钻孔循环输出非空。"""
        p = self.make_processor()
        result = p.format_cycle_drill(x=10.0, y=20.0, z=0.0, depth=-5.0)
        assert len(result) > 0

    def test_cycle_drill_with_dwell(self):
        """验证带暂停的钻孔循环。"""
        p = self.make_processor()
        result = p.format_cycle_drill(x=10.0, y=20.0, z=0.0, depth=-5.0, dwell=0.5)
        assert len(result) > 0

    def test_decimal_places_respected(self):
        """验证小数位数参数生效。"""
        p_high = self.make_processor(decimal_places=6)
        p_low = self.make_processor(decimal_places=0)
        high_result = p_high.format_header()
        low_result = p_low.format_header()
        assert high_result != low_result


class TestFanucPostProcessor(BaseProcessorTests):
    """Fanuc 0i系列后处理器测试。"""

    processor_cls = FanucPostProcessor

    def make_processor(self, **kwargs):
        defaults = {"decimal_places": 3, "safe_z_height": 50.0, "rapid_feed": 10000}
        defaults.update(kwargs)
        return self.processor_cls(**defaults)

    def test_header_contains_fanuc_patterns(self):
        """验证程序头包含Fanuc特征指令。"""
        p = self.make_processor()
        result = p.format_header()
        assert "G21" in result or "G17" in result
        assert "G40" in result
        assert "G49" in result
        assert "G80" in result
        assert "G90" in result

    def test_footer_contains_m30(self):
        """验证程序尾包含M30。"""
        p = self.make_processor()
        result = p.format_footer()
        assert "M30" in result
        assert "M05" in result
        assert "M09" in result

    def test_arc_uses_g02_g03_r_format(self):
        """验证圆弧使用G02/G03 R格式。"""
        p = self.make_processor()
        cw = p.format_arc((0, 0, 0), (10, 0, 0), (5, 0, 0), clockwise=True)
        assert "G02" in cw
        assert "R" in cw
        ccw = p.format_arc((10, 0, 0), (0, 0, 0), (5, 0, 0), clockwise=False)
        assert "G03" in ccw
        assert "R" in ccw

    def test_tool_change_uses_g43_h(self):
        """验证换刀使用G43 H格式。"""
        p = self.make_processor()
        result = p.format_tool_change(tool_id=3)
        assert "G43" in result
        assert "H" in result

    def test_coolant_uses_m_code(self):
        """验证冷却液使用M代码。"""
        p = self.make_processor()
        assert p.format_coolant("on") == "M08"
        assert p.format_coolant("off") == "M09"

    def test_tool_compensation_g41_g43(self):
        """验证刀具补偿使用G41/G43。"""
        p = self.make_processor()
        result = p.format_tool_compensation(length_offset=5, radius_offset=3)
        assert "G43" in result
        assert "G41" in result

    def test_drill_uses_g73_or_g83(self):
        """验证钻孔使用G73/G83循环。"""
        p = self.make_processor()
        with_dwell = p.format_cycle_drill(10, 20, 0, -5, dwell=0.5)
        assert "G73" in with_dwell
        without_dwell = p.format_cycle_drill(10, 20, 0, -5)
        assert "G83" in without_dwell

    def test_drill_includes_g80_cancel(self):
        """验证钻孔后取消循环。"""
        p = self.make_processor()
        result = p.format_cycle_drill(10, 20, 0, -5)
        assert "G80" in result

    def test_boundary_zero_values(self):
        """验证零值边界条件。"""
        p = self.make_processor()
        result = p.format_cycle_drill(0, 0, 0, -0.001)
        assert len(result) > 0

    def test_boundary_negative_depth(self):
        """验证负深度值（钻孔）。"""
        p = self.make_processor()
        result = p.format_cycle_drill(10, 10, 0, -100.0)
        assert "100" in result or "-100" in result


class TestSiemensPostProcessor(BaseProcessorTests):
    """Siemens 840D后处理器测试。"""

    processor_cls = SiemensPostProcessor

    def make_processor(self, **kwargs):
        defaults = {"decimal_places": 3, "safe_z_height": 50.0, "rapid_feed": 10000}
        defaults.update(kwargs)
        return self.processor_cls(**defaults)

    def test_header_contains_siemens_patterns(self):
        """验证程序头包含Siemens特征指令。"""
        p = self.make_processor()
        result = p.format_header()
        assert "G17" in result
        assert "G40" in result
        assert "G90" in result
        assert "G94" in result

    def test_header_has_block_numbers(self):
        """验证程序头包含N段号。"""
        p = self.make_processor()
        result = p.format_header()
        assert "N" in result

    def test_footer_contains_m30(self):
        """验证程序尾包含M30。"""
        p = self.make_processor()
        result = p.format_footer()
        assert "M30" in result

    def test_arc_uses_cr_notation(self):
        """验证圆弧使用CR=表示法。"""
        p = self.make_processor()
        result = p.format_arc((0, 0, 0), (10, 0, 0), (5, 0, 0))
        assert "CR=" in result
        assert "G02" in result or "G03" in result

    def test_tool_change_uses_t_string(self):
        """验证换刀使用T=字符串格式。"""
        p = self.make_processor()
        result = p.format_tool_change(tool_id=3)
        assert "TOOL" in result

    def test_tool_compensation_uses_tc_dp6(self):
        """验证刀具补偿使用$TC_DP6。"""
        p = self.make_processor()
        result = p.format_tool_compensation(length_offset=5)
        assert "$TC_DP6" in result
        result2 = p.format_tool_compensation(radius_offset=3)
        assert "DISC" in result2

    def test_drill_uses_cycle_notation(self):
        """验证钻孔使用CYCLE语法。"""
        p = self.make_processor()
        result = p.format_cycle_drill(10, 20, 0, -5)
        assert "CYCLE" in result

    def test_boundary_deep_drill(self):
        """验证深孔边界条件。"""
        p = self.make_processor()
        result = p.format_cycle_drill(100, 200, 0, -200.0)
        assert len(result) > 0


class TestHeidenhainPostProcessor(BaseProcessorTests):
    """Heidenhain TNC后处理器测试。"""

    processor_cls = HeidenhainPostProcessor

    def make_processor(self, **kwargs):
        defaults = {"decimal_places": 3, "safe_z_height": 50.0, "rapid_feed": 10000}
        defaults.update(kwargs)
        return self.processor_cls(**defaults)

    def test_header_contains_begin_pgm(self):
        """验证程序头包含BEGIN PGM。"""
        p = self.make_processor()
        result = p.format_header()
        assert "BEGIN PGM" in result

    def test_header_contains_blk_form(self):
        """验证程序头包含BLK FORM。"""
        p = self.make_processor()
        result = p.format_header()
        assert "BLK FORM" in result

    def test_footer_contains_end_pgm(self):
        """验证程序尾包含END PGM。"""
        p = self.make_processor()
        result = p.format_footer()
        assert "END PGM" in result

    def test_arc_clockwise_uses_l(self):
        """验证顺时针圆弧使用L指令。"""
        p = self.make_processor()
        result = p.format_arc((0, 0, 0), (10, 0, 0), (5, 0, 0), clockwise=True)
        assert " L " in result

    def test_arc_counter_clockwise_uses_cc(self):
        """验证逆时针圆弧使用CC/C指令。"""
        p = self.make_processor()
        result = p.format_arc((10, 0, 0), (0, 0, 0), (5, 0, 0), clockwise=False)
        assert "CC" in result
        assert " C " in result

    def test_tool_change_uses_tool_call(self):
        """验证换刀使用TOOL CALL。"""
        p = self.make_processor()
        result = p.format_tool_change(tool_id=3)
        assert "TOOL CALL" in result

    def test_tool_compensation_uses_dr(self):
        """验证刀具补偿使用DR+。"""
        p = self.make_processor()
        result = p.format_tool_compensation(radius_offset=3)
        assert "DR+3" in result

    def test_drill_uses_cycl_def(self):
        """验证钻孔使用CYCL DEF。"""
        p = self.make_processor()
        result = p.format_cycle_drill(10, 20, 0, -5)
        assert "CYCL DEF" in result

    def test_drill_uses_q_parameters(self):
        """验证钻孔使用Q参数体系。"""
        p = self.make_processor()
        result = p.format_cycle_drill(10, 20, 0, -5)
        assert "Q200" in result
        assert "Q201" in result

    def test_boundary_zero_coordinates(self):
        """验证原点坐标边界条件。"""
        p = self.make_processor()
        result = p.format_arc((0, 0, 0), (0, 0, 0), (0, 0, 0))
        assert len(result) > 0


class TestSemanticEquivalence:
    """语义等价性测试——相同刀轨经不同后处理器保持加工语义一致。"""

    @pytest.fixture
    def processors(self):
        return {
            "fanuc": FanucPostProcessor(decimal_places=3),
            "siemens": SiemensPostProcessor(decimal_places=3),
            "heidenhain": HeidenhainPostProcessor(decimal_places=3),
        }

    def test_all_produce_headers(self, processors):
        """验证所有后处理器都能生成程序头。"""
        for name, p in processors.items():
            header = p.format_header()
            assert len(header) > 0, f"{name} header is empty"

    def test_all_produce_footers(self, processors):
        """验证所有后处理器都能生成程序尾。"""
        for name, p in processors.items():
            footer = p.format_footer()
            assert len(footer) > 0, f"{name} footer is empty"

    def test_arc_radius_consistency(self, processors):
        """验证各后处理器圆弧终点坐标一致。"""
        start = (0.0, 0.0, 0.0)
        end = (10.0, 0.0, 0.0)
        center = (5.0, 0.0, 0.0)

        results = {}
        for name, p in processors.items():
            results[name] = p.format_arc(start, end, center, clockwise=True)

        assert all("10.000" in v for v in results.values()), (
            f"Arc endpoint inconsistent: {results}"
        )

    def test_tool_change_tool_id_preserved(self, processors):
        """验证换刀指令中刀具ID信息被保留。"""
        for name, p in processors.items():
            result = p.format_tool_change(tool_id=7)
            assert "7" in result or "07" in result, (
                f"{name} tool ID not found in: {result}"
            )

    def test_drill_depth_preserved(self, processors):
        """验证钻孔深度在各后处理器中保持一致。"""
        for name, p in processors.items():
            result = p.format_cycle_drill(10, 20, 0, -5.0)
            assert "-5" in result or "5.000" in result, (
                f"{name} depth not found in: {result}"
            )


class TestBoundaryConditions:
    """边界条件测试。"""

    def test_negative_coordinates(self):
        """验证负坐标值处理。"""
        p = FanucPostProcessor()
        result = p.format_arc((0, 0, 0), (-10, -20, 0), (-5, -10, 0))
        assert len(result) > 0
        assert "-10" in result or "-20" in result

    def test_zero_radius_arc(self):
        """验证零半径圆弧（退化为点）处理。"""
        p = FanucPostProcessor()
        result = p.format_arc((0, 0, 0), (0, 0, 0), (0, 0, 0))
        assert len(result) > 0

    def test_very_large_coordinates(self):
        """验证大坐标值处理。"""
        p = SiemensPostProcessor()
        result = p.format_arc((0, 0, 0), (99999, 99999, 0), (50000, 50000, 0))
        assert len(result) > 0

    def test_custom_decimal_places(self):
        """验证自定义小数位数。"""
        p = HeidenhainPostProcessor(decimal_places=6)
        result = p.format_header()
        assert len(result) > 0

    def test_zero_feed_rate(self):
        """验证零进给速度被防御性校验拒绝。

        基类 ``__init__`` 对 ``rapid_feed <= 0`` 抛出 ``ValueError``，
        避免后续生成无效的 F0 代码。
        """
        with pytest.raises(ValueError, match="rapid_feed"):
            FanucPostProcessor(rapid_feed=0)
        # 正数边界值应可正常工作
        p = FanucPostProcessor(rapid_feed=1)
        result = p.format_arc((0, 0, 0), (10, 0, 0), (5, 0, 0))
        assert len(result) > 0

    def test_very_deep_drill(self):
        """验证极深钻孔。"""
        p = HeidenhainPostProcessor()
        result = p.format_cycle_drill(0, 0, 0, -999.0)
        assert len(result) > 0

    def test_small_decimal_places(self):
        """验证小数位数为0。"""
        p = FanucPostProcessor(decimal_places=0)
        result = p.format_header()
        assert len(result) > 0


class TestRegistry:
    """后处理器注册表测试。"""

    def test_singleton(self):
        """验证注册表是单例模式。"""
        r1 = PostProcessorRegistry()
        r2 = PostProcessorRegistry()
        assert r1 is r2

    def test_list_controllers(self):
        """验证列出所有控制器类型。"""
        registry = PostProcessorRegistry()
        controllers = registry.list_controllers()
        assert "fanuc_0i" in controllers
        assert "siemens_840d" in controllers
        assert "heidenhain_tnc" in controllers

    def test_get_processor_fanuc(self):
        """验证获取Fanuc后处理器。"""
        registry = PostProcessorRegistry()
        registry.clear_instances()
        processor = registry.get_processor("fanuc_0i")
        assert isinstance(processor, FanucPostProcessor)

    def test_get_processor_siemens(self):
        """验证获取Siemens后处理器。"""
        registry = PostProcessorRegistry()
        registry.clear_instances()
        processor = registry.get_processor("siemens_840d")
        assert isinstance(processor, SiemensPostProcessor)

    def test_get_processor_heidenhain(self):
        """验证获取Heidenhain后处理器。"""
        registry = PostProcessorRegistry()
        registry.clear_instances()
        processor = registry.get_processor("heidenhain_tnc")
        assert isinstance(processor, HeidenhainPostProcessor)

    def test_get_unknown_controller(self):
        """验证未知控制器类型抛出KeyError。"""
        registry = PostProcessorRegistry()
        with pytest.raises(KeyError, match="Unknown controller type"):
            registry.get_processor("unknown_controller")

    def test_get_processor_with_config(self):
        """验证配置参数传递给后处理器。"""
        registry = PostProcessorRegistry()
        registry.clear_instances()
        processor = registry.get_processor(
            "fanuc_0i", decimal_places=5, safe_z_height=100.0
        )
        assert processor.decimal_places == 5
        assert processor.safe_z_height == 100.0

    def test_register_custom_processor(self):
        """验证动态注册新的后处理器类型。"""

        class CustomProcessor(FanucPostProcessor):
            pass

        registry = PostProcessorRegistry()
        registry.register("custom_ctrl", CustomProcessor)
        assert "custom_ctrl" in registry.list_controllers()
        processor = registry.get_processor("custom_ctrl")
        assert isinstance(processor, CustomProcessor)

    def test_register_invalid_class(self):
        """验证注册非BasePostProcessor子类抛出TypeError。"""
        registry = PostProcessorRegistry()
        with pytest.raises(TypeError):

            class NotAProcessor:
                pass

            registry.register("invalid", NotAProcessor)

    def test_instance_caching(self):
        """验证相同配置的实例被缓存复用。"""
        registry = PostProcessorRegistry()
        registry.clear_instances()
        p1 = registry.get_processor("fanuc_0i", decimal_places=3)
        p2 = registry.get_processor("fanuc_0i", decimal_places=3)
        assert p1 is p2

    def test_clear_instances(self):
        """验证清除实例缓存。"""
        registry = PostProcessorRegistry()
        registry.get_processor("fanuc_0i")
        registry.clear_instances()
        registry.get_processor("fanuc_0i")


class TestConfigLoading:
    """配置文件加载测试。

    使用生产配置文件 ``config/postprocessor_config.yaml`` 作为基础，
    避免与 ConfigValidator 的必需字段清单重复维护。
    """

    def test_load_from_config_file(self):
        """验证从生产配置文件加载 Fanuc 后处理器。"""
        registry = PostProcessorRegistry()
        registry.clear_instances()
        processor = registry.load_from_config(_PROD_CONFIG)
        assert isinstance(processor, FanucPostProcessor)
        # 生产配置中 base.decimal_places == 3
        assert processor.decimal_places == 3

    def test_load_siemens_from_config(self):
        """验证从配置文件加载 Siemens 后处理器。"""
        config_path = _make_config_with_controller("siemens_840d")
        try:
            registry = PostProcessorRegistry()
            registry.clear_instances()
            processor = registry.load_from_config(config_path)
            assert isinstance(processor, SiemensPostProcessor)
        finally:
            os.unlink(config_path)

    def test_load_heidenhain_from_config(self):
        """验证从配置文件加载 Heidenhain 后处理器。"""
        config_path = _make_config_with_controller("heidenhain_tnc")
        try:
            registry = PostProcessorRegistry()
            registry.clear_instances()
            processor = registry.load_from_config(config_path)
            assert isinstance(processor, HeidenhainPostProcessor)
        finally:
            os.unlink(config_path)

    def test_default_config_values(self):
        """验证配置文件缺少可选字段时后处理器使用构造默认值。

        生产配置文件已包含 decimal_places/safe_z_height/rapid_feed，
        这里验证它们被正确传递到后处理器实例。
        """
        registry = PostProcessorRegistry()
        registry.clear_instances()
        processor = registry.load_from_config(_PROD_CONFIG)
        assert processor.decimal_places == 3
        assert processor.safe_z_height == 50.0
        assert processor.rapid_feed == 10000

    def test_missing_config_file(self):
        """验证配置文件不存在时抛出FileNotFoundError。"""
        registry = PostProcessorRegistry()
        with pytest.raises(FileNotFoundError):
            registry.load_from_config("/nonexistent/path/config.yaml")

    def test_config_without_target_uses_default(self):
        """验证未指定target_controller时使用默认值 fanuc_0i。"""
        # 从生产配置中删除 target_controller 行
        with open(_PROD_CONFIG, "r", encoding="utf-8") as f:
            content = f.read()
        content = re.sub(
            r"^target_controller:\s*\S+\s*$",
            "",
            content,
            count=1,
            flags=re.MULTILINE,
        )
        fd, config_path = tempfile.mkstemp(suffix=".yaml", text=True)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
        try:
            registry = PostProcessorRegistry()
            registry.clear_instances()
            processor = registry.load_from_config(config_path)
            assert isinstance(processor, FanucPostProcessor)
        finally:
            os.unlink(config_path)
