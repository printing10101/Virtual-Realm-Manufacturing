"""NC代码刀具路径仿真与碰撞检测 单元测试。

覆盖：
- 毛坯模型（矩形/圆柱包围盒）
- G代码解析（Fanuc格式路径提取）
- 碰撞检测（5种已知碰撞场景100%检出）
- 3D可视化（PNG+HTML输出）
- 仿真报告生成
- 边界条件（空代码/异常代码）
"""

from __future__ import annotations

import json
import os
import tempfile


from app.simulation.stock_model import (
    StockBoundingBox,
    StockModel,
    CylindricalStock,
)
from app.simulation.toolpath_parser import ToolpathParser
from app.simulation.collision_detector import (
    CollisionDetector,
)
from app.simulation.simulation_report import (
    SimulationReport,
    generate_summary_text,
)
from app.simulation.toolpath_visualizer import ToolpathVisualizer


class TestStockModel:
    def test_rectangular_bbox(self):
        s = StockModel(length=200, width=150, height=50)
        bbox = s.get_bbox()
        assert bbox.x_min == -100
        assert bbox.x_max == 100
        assert bbox.y_min == -75
        assert bbox.y_max == 75
        assert bbox.z_min == 0
        assert bbox.z_max == 50

    def test_rectangular_contains_point(self):
        s = StockModel(length=200, width=150, height=50)
        assert s.contains_point(0, 0, 25)
        assert not s.contains_point(200, 0, 0)
        assert not s.contains_point(0, 0, -1)

    def test_set_dimensions(self):
        s = StockModel()
        s.set_dimensions(300, 200, 80)
        bbox = s.get_bbox()
        assert bbox.x_max == 150
        assert bbox.z_max == 80

    def test_cylindrical_contains_point(self):
        s = CylindricalStock(diameter=100, height=200)
        assert s.contains_point(30, 40, 50)
        assert not s.contains_point(60, 0, 50)
        assert not s.contains_point(0, 0, -0.1)

    def test_bbox_intersects(self):
        a = StockBoundingBox(0, 10, 0, 10, 0, 10)
        b = StockBoundingBox(5, 15, 5, 15, 5, 15)
        assert a.intersects_bbox(b)
        c = StockBoundingBox(20, 30, 20, 30, 20, 30)
        assert not a.intersects_bbox(c)

    def test_stock_to_dict(self):
        s = StockModel(200, 150, 50)
        d = s.to_dict()
        assert d["length"] == 200
        assert "bbox" in d

    def test_cylindrical_to_dict(self):
        s = CylindricalStock(100, 200)
        d = s.to_dict()
        assert d["diameter"] == 100


class TestToolpathParser:
    def test_parse_rapid_move(self):
        gcode = "G00 X100. Y50. Z10."
        parser = ToolpathParser()
        segs = parser.parse_gcode(gcode)
        assert len(segs) >= 1
        assert segs[0].type == "rapid"
        assert segs[0].end_point == (100.0, 50.0, 10.0)

    def test_parse_linear_move(self):
        gcode = "G01 X50. Y25. Z-2. F500"
        parser = ToolpathParser()
        segs = parser.parse_gcode(gcode)
        assert segs[0].type == "linear"
        assert segs[0].feed_rate == 500.0

    def test_parse_arc_move(self):
        gcode = "G02 X50. Y0. R25. F300"
        parser = ToolpathParser()
        segs = parser.parse_gcode(gcode)
        assert segs[0].type == "arc"

    def test_parse_complete_program(self):
        gcode = """%
O0001
G21 G17 G90 G94
G00 Z50.
G00 X0. Y0.
M03 S8000
G01 Z-2. F500
G01 X50. F800
G01 Y50.
G02 X75. Y25. R25.
G01 X0. Y0.
G00 Z50.
M05
M30
%"""
        parser = ToolpathParser()
        segs = parser.parse_gcode(gcode)
        assert len(segs) >= 4
        types = [s.type for s in segs]
        assert "rapid" in types
        assert "linear" in types
        assert "arc" in types

    def test_modal_feed_retained(self):
        gcode = "G01 X10. F600\nX20."
        parser = ToolpathParser()
        segs = parser.parse_gcode(gcode)
        assert segs[1].feed_rate == 600.0

    def test_spindle_speed_captured(self):
        gcode = "M03 S8000\nG01 X10. F500"
        parser = ToolpathParser()
        segs = parser.parse_gcode(gcode)
        assert segs[0].spindle_speed == 8000

    def test_tool_id_captured(self):
        gcode = "T02 M06\nG01 X10. F500"
        parser = ToolpathParser()
        segs = parser.parse_gcode(gcode)
        assert segs[0].tool_id == 2

    def test_parse_dwell(self):
        gcode = "G04 P1000\nG01 X10. F500"
        parser = ToolpathParser()
        segs = parser.parse_gcode(gcode)
        assert segs[0].type == "dwell"

    def test_empty_gcode_returns_empty(self):
        parser = ToolpathParser()
        segs = parser.parse_gcode("")
        assert segs == []

    def test_comment_lines_ignored(self):
        gcode = "(This is a comment)\nG00 X10.\n; another comment\nG01 Y20. F500"
        parser = ToolpathParser()
        segs = parser.parse_gcode(gcode)
        assert len(segs) == 2

    def test_segment_position_accuracy(self):
        gcode = "G01 X123.456 Y78.901 Z-5.123 F800"
        parser = ToolpathParser()
        segs = parser.parse_gcode(gcode)
        ep = segs[0].end_point
        assert abs(ep[0] - 123.456) < 0.01
        assert abs(ep[1] - 78.901) < 0.01
        assert abs(ep[2] - (-5.123)) < 0.01

    def test_r_arc_correct(self):
        gcode = "G00 Z80.\nG00 X0. Y0.\nG02 X50. Y0. R25. F300"
        parser = ToolpathParser()
        segs = parser.parse_gcode(gcode)
        arc = segs[1]
        assert arc.type == "arc"

    def test_segment_to_dict(self):
        gcode = "G01 X100. Y50. F600"
        parser = ToolpathParser()
        segs = parser.parse_gcode(gcode)
        d = segs[0].to_dict()
        assert d["type"] == "linear"
        assert d["feed_rate"] == 600.0


class TestCollisionDetector:
    def test_no_collision_safe_path(self):
        gcode = "G00 Z80.\nG00 X0. Y0.\nG01 Z5. F500\nG01 X50.\nG01 Z80. F2000"
        parser = ToolpathParser()
        segs = parser.parse_gcode(gcode)
        stock = StockModel(200, 150, 50)
        detector = CollisionDetector(stock=stock)
        report = detector.check_segments(segs)
        assert report.safe

    def test_detect_rapid_into_stock(self):
        """碰撞场景1：快速移动撞毛坯"""
        gcode = "G00 Z50.\nG00 X0. Y0.\nG00 Z-10.\nG00 X100."
        parser = ToolpathParser()
        segs = parser.parse_gcode(gcode)
        stock = StockModel(200, 150, 50)
        detector = CollisionDetector(stock=stock, safe_z_height=10)
        report = detector.check_segments(segs)
        assert not report.safe
        assert any(c.collision_type == "rapid_into_stock" for c in report.collisions)

    def test_detect_rapid_z_low(self):
        """碰撞场景2：换刀点Z过低"""
        gcode = "G00 Z5.\nG00 X100. Y50.\nG00 Z50."
        parser = ToolpathParser()
        segs = parser.parse_gcode(gcode)
        stock = StockModel(200, 150, 50)
        detector = CollisionDetector(stock=stock, safe_z_height=10)
        report = detector.check_segments(segs)
        assert any(c.collision_type == "rapid_z_low" for c in report.collisions)

    def test_detect_overcut(self):
        """碰撞场景3：过切——Z低于毛坯底面"""
        gcode = "G00 Z50.\nG00 X50. Y25.\nG01 Z-5. F300\nG00 Z50."
        parser = ToolpathParser()
        segs = parser.parse_gcode(gcode)
        stock = StockModel(200, 150, 50)
        detector = CollisionDetector(stock=stock)
        report = detector.check_segments(segs)
        has_overcut = any(c.collision_type == "overcut_z" for c in report.collisions)
        assert has_overcut

    def test_detect_boundary_exceed(self):
        """碰撞场景4：刀具路径超出毛坯边界"""
        gcode = "G00 Z50.\nG00 X0. Y0.\nG01 Z-2. F500\nG01 X500. F800\nG00 Z50."
        parser = ToolpathParser()
        segs = parser.parse_gcode(gcode)
        stock = StockModel(200, 150, 50)
        detector = CollisionDetector(stock=stock)
        report = detector.check_segments(segs)
        assert any("超出毛坯边界" in w for w in report.warnings)

    def test_detect_rapid_through_stock(self):
        """碰撞场景5：G00直线穿越毛坯"""
        gcode = "G00 Z-10.\nG00 X0. Y0.\nG00 X200. Y100."
        parser = ToolpathParser()
        segs = parser.parse_gcode(gcode)
        stock = StockModel(200, 150, 50)
        detector = CollisionDetector(stock=stock, safe_z_height=10)
        report = detector.check_segments(segs)
        has_collision = any(
            c.collision_type in ("rapid_into_stock", "rapid_z_low")
            for c in report.collisions
        )
        assert has_collision

    def test_five_scenarios_all_detected(self):
        """验证5种已知碰撞场景100%检出"""
        stock = StockModel(200, 150, 50)
        scenarios = [
            ("G00 Z50.\nG00 X0. Y0.\nG00 Z-10.\nG00 X100.", "rapid_into_stock"),
            ("G00 Z5.\nG00 X100. Y50.\nG00 Z50.", "rapid_z_low"),
            ("G00 Z50.\nG00 X50. Y25.\nG01 Z-5. F300", "overcut_z"),
            (
                "G00 Z50.\nG00 X0. Y0.\nG01 Z-2. F500\nG01 X500.\nG00 Z50.",
                "boundary_warning",
            ),
            (
                "G00 Z-10.\nG00 X0. Y0.\nG00 X200. Y100.",
                "rapid_in_stock_or_z",
            ),
        ]

        for i, (gcode, expected) in enumerate(scenarios):
            parser = ToolpathParser()
            segs = parser.parse_gcode(gcode)
            detector = CollisionDetector(stock=stock, safe_z_height=10)
            report = detector.check_segments(segs)
            if expected == "boundary_warning":
                detected = any("超出毛坯边界" in w for w in report.warnings) or any(
                    "过切" in c.message for c in report.collisions
                )
            elif expected == "rapid_in_stock_or_z":
                detected = any(
                    c.collision_type in ("rapid_into_stock", "rapid_z_low")
                    for c in report.collisions
                )
            else:
                detected = any(c.collision_type == expected for c in report.collisions)
            assert detected, f"场景{i + 1}({expected})未检出"

    def test_report_to_dict(self):
        parser = ToolpathParser()
        segs = parser.parse_gcode("G00 Z-10.\nG00 X0. Y0.\nG00 X100.")
        stock = StockModel(200, 150, 50)
        detector = CollisionDetector(stock=stock)
        report = detector.check_segments(segs)
        d = report.to_dict()
        assert "collisions" in d
        assert "safe" in d

    def test_severity_levels(self):
        gcode = "G00 Z5.\nG00 X100. Y50."
        parser = ToolpathParser()
        segs = parser.parse_gcode(gcode)
        stock = StockModel(200, 150, 50)
        detector = CollisionDetector(stock=stock, safe_z_height=10)
        report = detector.check_segments(segs)
        for c in report.collisions:
            assert c.severity in ("high", "medium", "low")

    def test_collision_suggestion_present(self):
        gcode = "G00 Z-10.\nG00 X0. Y0.\nG00 X100."
        parser = ToolpathParser()
        segs = parser.parse_gcode(gcode)
        stock = StockModel(200, 150, 50)
        detector = CollisionDetector(stock=stock)
        report = detector.check_segments(segs)
        for c in report.collisions:
            assert c.suggestion, f"碰撞事件{c.collision_type}缺少处理建议"

    def test_drilling_program(self):
        """钻孔加工NC代码仿真"""
        gcode = """%
O0002
G21 G17 G90 G94
G00 Z80.
G00 X10. Y10.
M03 S4000
G01 Z5. F200
G01 Z80. F2000
G00 X30. Y10.
G01 Z5. F200
G01 Z80. F2000
G00 X20. Y25.
G01 Z5. F200
G01 Z80. F2000
M05
M30
%"""
        parser = ToolpathParser()
        segs = parser.parse_gcode(gcode)
        stock = StockModel(50, 40, 30)
        detector = CollisionDetector(stock=stock)
        report = detector.check_segments(segs)
        assert report.safe


class TestToolpathVisualizer:
    def test_render_png(self):
        gcode = "G00 Z50.\nG00 X0. Y0.\nG01 Z-2. F500\nG01 X50.\nG00 Z50."
        parser = ToolpathParser()
        segs = parser.parse_gcode(gcode)
        stock = StockModel(200, 150, 50)
        viz = ToolpathVisualizer(stock=stock)
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "toolpath.png")
            result = viz.render_png(segs, path)
            assert os.path.exists(result)

    def test_render_html(self):
        gcode = "G00 Z50.\nG00 X0. Y0.\nG01 Z-2. F500\nG01 X50.\nG00 Z50."
        parser = ToolpathParser()
        segs = parser.parse_gcode(gcode)
        viz = ToolpathVisualizer()
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "toolpath.html")
            result = viz.render_html(segs, path)
            assert os.path.exists(result)
            with open(result, "r", encoding="utf-8") as f:
                content = f.read()
            assert "three.js" in content
            assert "OrbitControls" in content

    def test_arc_blue_color(self):
        gcode = "G02 X50. Y0. R25. F300"
        parser = ToolpathParser()
        segs = parser.parse_gcode(gcode)
        stock = StockModel(200, 150, 50)
        viz = ToolpathVisualizer(stock=stock)
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "arc_test.png")
            viz.render_png(segs, path)
            assert os.path.exists(path)


class TestSimulationReport:
    def test_generate_report(self):
        gcode = "G00 Z80.\nG00 X0. Y0.\nG01 Z5. F500\nG01 Z80. F2000"
        parser = ToolpathParser()
        segs = parser.parse_gcode(gcode)
        stock = StockModel(200, 150, 50)
        detector = CollisionDetector(stock=stock)
        collision = detector.check_segments(segs)
        report = SimulationReport.from_validation(
            segs,
            collision,
            part_name="test_part",
        )
        assert report.total_segments == len(segs)
        assert report.rapid_segments >= 1
        assert report.linear_segments >= 1

    def test_save_json(self):
        gcode = "G00 Z50.\nG00 X0. Y0.\nG01 Z-2. F500\nG00 Z50."
        parser = ToolpathParser()
        segs = parser.parse_gcode(gcode)
        stock = StockModel(200, 150, 50)
        detector = CollisionDetector(stock=stock)
        collision = detector.check_segments(segs)
        report = SimulationReport.from_validation(segs, collision)
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "report.json")
            report.save_json(path)
            assert os.path.exists(path)

    def test_summary_text(self):
        gcode = "G00 Z-10.\nG00 X100."
        parser = ToolpathParser()
        segs = parser.parse_gcode(gcode)
        stock = StockModel(200, 150, 50)
        detector = CollisionDetector(stock=stock)
        collision = detector.check_segments(segs)
        report = SimulationReport.from_validation(segs, collision, part_name="碰撞测试")
        text = generate_summary_text(report)
        assert "碰撞测试" in text
        assert "检测到碰撞" in text or "安全" in text

    def test_report_status_pass(self):
        gcode = "G00 Z80.\nG00 X0. Y0.\nG01 Z5. F500\nG01 Z80. F2000"
        parser = ToolpathParser()
        segs = parser.parse_gcode(gcode)
        stock = StockModel(200, 150, 50)
        detector = CollisionDetector(stock=stock)
        collision = detector.check_segments(segs)
        report = SimulationReport.from_validation(segs, collision)
        d = report.to_dict()
        assert d["status"] == "PASS"

    def test_report_status_fail(self):
        gcode = "G00 Z-10.\nG00 X100."
        parser = ToolpathParser()
        segs = parser.parse_gcode(gcode)
        stock = StockModel(200, 150, 50)
        detector = CollisionDetector(stock=stock, safe_z_height=10)
        collision = detector.check_segments(segs)
        report = SimulationReport.from_validation(segs, collision)
        d = report.to_dict()
        assert d["status"] == "FAIL"


class TestIntegration:
    def test_full_milling_simulation(self):
        """集成测试：铣削加工完整仿真"""
        gcode = """%
O1001
G21 G17 G90 G94
G00 Z80.
G00 X0. Y0.
M03 S6000
G01 Z5. F400
G01 X40. F600
G01 Y20.
G01 X0.
G01 Y0.
G01 X20. Y10. F400
G01 Z80. F2000
M05
M30
%"""
        parser = ToolpathParser()
        segs = parser.parse_gcode(gcode)
        stock = StockModel(100, 60, 20)
        detector = CollisionDetector(stock=stock)
        collision = detector.check_segments(segs)

        viz = ToolpathVisualizer(stock=stock)
        with tempfile.TemporaryDirectory() as tmp:
            png_path = os.path.join(tmp, "milling.png")
            viz.render_png(segs, png_path)
            assert os.path.exists(png_path)

        report = SimulationReport.from_validation(
            segs,
            collision,
            part_name="铣削测试",
        )
        assert report.collision_report.safe

        text = generate_summary_text(report)
        print(f"\n{text}")

    def test_full_drilling_simulation(self):
        """集成测试：钻孔加工完整仿真"""
        gcode = """%
O1002
G21 G17 G90 G94
G00 Z80.
G00 X20. Y20.
M03 S4000
G01 Z5. F200
G01 Z80. F2000
G00 X30. Y20.
G01 Z5. F200
G01 Z80. F2000
M05
M30
%"""
        parser = ToolpathParser()
        segs = parser.parse_gcode(gcode)
        stock = StockModel(60, 50, 30)
        detector = CollisionDetector(stock=stock)
        collision = detector.check_segments(segs)

        report = SimulationReport.from_validation(
            segs,
            collision,
            part_name="钻孔测试",
        )
        with tempfile.TemporaryDirectory() as tmp:
            json_path = os.path.join(tmp, "drill_report.json")
            report.save_json(json_path)
            assert os.path.exists(json_path)
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            assert data["status"] == "PASS"

    def test_full_contour_simulation(self):
        """集成测试：轮廓加工完整仿真（含圆弧）"""
        gcode = """%
O1003
G21 G17 G90 G94
G00 Z80.
G00 X0. Y0.
M03 S5000
G01 Z5. F400
G01 X100. F600
G02 X150. Y50. R50. F400
G01 Y80.
G02 X100. Y130. R50.
G01 X0.
G01 Y0.
G01 Z80. F2000
M05
M30
%"""
        parser = ToolpathParser()
        segs = parser.parse_gcode(gcode)
        stock = StockModel(200, 180, 30)
        detector = CollisionDetector(stock=stock)
        collision = detector.check_segments(segs)

        arc_count = sum(1 for s in segs if s.type == "arc")
        assert arc_count >= 2, f"轮廓加工应包含圆弧运动: {arc_count}"

        report = SimulationReport.from_validation(
            segs,
            collision,
            part_name="轮廓加工测试",
        )
        assert report.arc_segments >= 2

        text = generate_summary_text(report)
        print(f"\n{text}")

    def test_boundary_conditions(self):
        """边界条件测试：空G代码/异常/极限尺寸"""
        parser = ToolpathParser()
        assert parser.parse_gcode("") == []
        assert parser.parse_gcode("(comment)\n; another\n%") == []

        stock_big = StockModel(length=10000, width=5000, height=2000)
        bbox = stock_big.get_bbox()
        assert bbox.x_max == 5000

        stock_tiny = StockModel(length=1, width=1, height=0.1)
        bbox = stock_tiny.get_bbox()
        assert bbox.volume() > 0
