"""铣削切深调试脚本"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.simulation.toolpath_parser import ToolpathParser
from app.simulation.collision_detector import CollisionDetector
from app.simulation.stock_model import StockModel
from app.postprocessor.fanuc import FanucPostProcessor

stock = StockModel(length=200, width=150, height=50)
bbox = stock.get_bbox()
print(f"毛坯 bbox: ({bbox.x_min},{bbox.y_min},{bbox.z_min}) -> ({bbox.x_max},{bbox.y_max},{bbox.z_max})")

for depth in [0.5, 1.5, 5]:
    fanuc = FanucPostProcessor(safe_z_height=80.0)
    mill_gcode = fanuc.format_header(1000)
    mill_gcode += f"\nG00 Z80.000"
    mill_gcode += f"\nG00 X50.000 Y50.000"
    mill_gcode += f"\nG01 Z{-depth} F500"
    mill_gcode += f"\nG01 X100.000 F1000"
    mill_gcode += f"\nG00 Z80.000"
    mill_gcode += "\n" + fanuc.format_footer()

    parser = ToolpathParser(controller_type="fanuc")
    segments = parser.parse_gcode(mill_gcode)
    
    print(f"\n=== 铣削切深 {depth}mm ===")
    print(f"段数: {len(segments)}")
    for seg in segments:
        print(f"  N{seg.block_number}: {seg.type} {seg.start_point} -> {seg.end_point}")
    
    detector = CollisionDetector(stock=stock, safe_z_height=10.0)
    report = detector.check_segments(segments)
    print(f"碰撞: {len(report.collisions)}")
    for c in report.collisions:
        print(f"  [{c.severity}] N{c.block_number}: {c.collision_type} at {c.position} - {c.message}")
