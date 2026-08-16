"""后处理器黄金文件回归测试。

针对 9 种 CNC 控制器，用一套标准加工序列（程序头 → 换刀 → 刀具补偿 → 冷却开 →
快移 → 直线 → 圆弧 → 钻孔循环 → 冷却关 → 程序尾）生成 NC 输出，与
``tests/golden/postprocessor/`` 下的黄金文件逐字节比对，防止后处理器重构或配置
调整引入意外的输出漂移（这是「G 代码能否上机床」的回归护栏）。

黄金文件更新：审阅输出变更后执行 ``UPDATE_GOLDEN=1 pytest <本文件>`` 重新生成。

设计说明：
- 通过 monkeypatch 固定 ``BasePostProcessor._date_string``，消除 header 中的日期
  导致的天级不确定输出。
- ``_block_counter`` 为实例级状态，fresh 实例输出确定。
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Callable, Type

import pytest

from app.postprocessor.base import BasePostProcessor
from app.postprocessor.fagor import FagorPostProcessor
from app.postprocessor.fanuc import FanucPostProcessor
from app.postprocessor.gsk import GSKPostProcessor
from app.postprocessor.heidenhain import HeidenhainPostProcessor
from app.postprocessor.hnc import HNCPostProcessor
from app.postprocessor.knd import KNDPostProcessor
from app.postprocessor.mitsubishi import MitsubishiPostProcessor
from app.postprocessor.siemens import SiemensPostProcessor
from app.postprocessor.xmachine import XMachineXM100PostProcessor


CONTROLLERS: dict[str, Type[BasePostProcessor]] = {
    "fanuc_0i": FanucPostProcessor,
    "siemens_840d": SiemensPostProcessor,
    "heidenhain_tnc": HeidenhainPostProcessor,
    "fagor_8055": FagorPostProcessor,
    "gsk_980_25i": GSKPostProcessor,
    "hnc_848_22": HNCPostProcessor,
    "knd_1000_2000_3000": KNDPostProcessor,
    "mitsubishi_m70_m80": MitsubishiPostProcessor,
    "xmachine_xm100": XMachineXM100PostProcessor,
}

GOLDEN_DIR = Path(__file__).resolve().parent.parent / "golden" / "postprocessor"
FIXED_DATE = "2026-01-01"


def build_standard_program(processor: BasePostProcessor) -> str:
    """用一套确定性加工序列生成完整 NC 程序文本。"""
    # 坐标统一控制在 ±50mm 内：XM100 桌面五轴机行程仅 ±50mm，需兼容所有控制器。
    lines = [
        processor.format_header(program_number=1000),
        processor.format_tool_change(tool_id=1, length_comp=50.0, radius_comp=5.0),
        processor.format_tool_compensation(length_offset=1, radius_offset=1),
        processor.format_coolant("on"),
        processor.format_rapid_move(0.0, 0.0, 30.0),
        processor.format_linear_move(10.0, 20.0, 25.0, feed=500.0),
        processor.format_arc(
            (10.0, 20.0, 25.0), (20.0, 30.0, 25.0), (15.0, 25.0, 25.0), clockwise=True
        ),
        processor.format_cycle_drill(x=20.0, y=30.0, z=25.0, depth=8.0, dwell=0.5),
        processor.format_coolant("off"),
        processor.format_footer(),
    ]
    return "\n".join(lines) + "\n"


@pytest.mark.regression
@pytest.mark.parametrize("controller_id", list(CONTROLLERS.keys()))
def test_golden_output_matches(controller_id: str, monkeypatch):
    monkeypatch.setattr(
        BasePostProcessor, "_date_string", staticmethod(lambda: FIXED_DATE)
    )
    processor = CONTROLLERS[controller_id]()
    output = build_standard_program(processor)
    golden_path = GOLDEN_DIR / f"{controller_id}.nc"

    if os.environ.get("UPDATE_GOLDEN") == "1":
        golden_path.parent.mkdir(parents=True, exist_ok=True)
        golden_path.write_text(output, encoding="utf-8")
        pytest.skip("UPDATE_GOLDEN=1：已重新生成黄金文件")

    if not golden_path.exists():
        pytest.fail(
            f"黄金文件缺失: {golden_path}。建议操作：审阅当前输出后执行 "
            f"UPDATE_GOLDEN=1 pytest tests/regression/test_postprocessor_golden.py 生成。"
        )

    golden = golden_path.read_text(encoding="utf-8")
    assert output == golden, (
        f"{controller_id} 后处理器输出与黄金文件不一致。建议操作：若变更为预期，执行 "
        f"UPDATE_GOLDEN=1 更新黄金文件；否则回退后处理器改动。"
    )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
