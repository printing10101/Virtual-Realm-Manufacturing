"""Unit tests for MTConnect → cutting_experience bridge (数据飞轮闭环)."""

from __future__ import annotations

import pytest

from app.contracts.cutting_experience import MachiningResult
from app.integrations.mtconnect.experience_bridge import (
    MTConnectExperienceBridge,
    _MIN_SPINDLE_RPM,
)
from app.integrations.mtconnect.parser import Sample


def _sample(
    spindle_speed: float | None = 8000.0,
    spindle_load: float | None = 50.0,
    feedrate: float | None = 500.0,
    execution: str | None = "ACTIVE",
) -> Sample:
    return Sample(
        spindle_speed=spindle_speed,
        spindle_load=spindle_load,
        feedrate=feedrate,
        execution=execution,
    )


class TestSampleToExperience:
    def test_valid_sample_converts(self) -> None:
        bridge = MTConnectExperienceBridge(machine_id="VM-001", tool_id="T-12")
        exp = bridge.sample_to_experience(_sample())
        assert exp is not None
        assert exp.machine_id == "VM-001"
        assert exp.tool_id == "T-12"
        assert exp.source == "mtconnect"
        assert exp.parameters.spindle_rpm == 8000.0
        assert exp.parameters.feed_mm_per_rev == 0.0625  # 500 mm/min ÷ 8000 rpm
        assert exp.results.result == MachiningResult.OK
        assert exp.anomalies == []

    def test_empty_sample_discarded(self) -> None:
        bridge = MTConnectExperienceBridge(machine_id="VM-001")
        assert bridge.sample_to_experience(Sample()) is None
        assert bridge.discarded_count == 1

    def test_none_sample_discarded(self) -> None:
        bridge = MTConnectExperienceBridge(machine_id="VM-001")
        assert bridge.sample_to_experience(None) is None
        assert bridge.discarded_count == 1

    def test_stopped_spindle_discarded(self) -> None:
        bridge = MTConnectExperienceBridge(machine_id="VM-001")
        # 转速低于阈值（接近停机）
        assert bridge.sample_to_experience(_sample(spindle_speed=0.5)) is None

    def test_zero_feedrate_discarded(self) -> None:
        bridge = MTConnectExperienceBridge(machine_id="VM-001")
        assert bridge.sample_to_experience(_sample(feedrate=0.0)) is None
        assert bridge.sample_to_experience(_sample(feedrate=None)) is None

    def test_high_load_creates_anomaly(self) -> None:
        bridge = MTConnectExperienceBridge(machine_id="VM-001")
        exp = bridge.sample_to_experience(_sample(spindle_load=95.0))
        assert exp is not None
        assert len(exp.anomalies) == 1
        assert exp.anomalies[0].anomaly_type == "spindle_overload"
        assert exp.anomalies[0].measured_value == 95.0
        assert exp.results.result == MachiningResult.REWORK

    def test_normal_load_no_anomaly(self) -> None:
        bridge = MTConnectExperienceBridge(machine_id="VM-001")
        exp = bridge.sample_to_experience(_sample(spindle_load=60.0))
        assert exp is not None
        assert exp.anomalies == []

    def test_anomaly_severity_capped(self) -> None:
        bridge = MTConnectExperienceBridge(machine_id="VM-001")
        exp = bridge.sample_to_experience(_sample(spindle_load=200.0))
        assert exp is not None
        assert exp.anomalies[0].severity == 10  # min(int(200/10), 10)

    def test_stats_after_conversions(self) -> None:
        bridge = MTConnectExperienceBridge(machine_id="VM-001")
        bridge.sample_to_experience(_sample())
        bridge.sample_to_experience(Sample())
        assert bridge.ingested_count == 0
        assert bridge.discarded_count == 1
        stats = bridge.stats()
        assert stats["machine_id"] == "VM-001"
        assert stats["discarded"] == 1


class TestIngest:
    @pytest.mark.asyncio
    async def test_ingest_sample_db_unconfigured(self, monkeypatch) -> None:
        """数据库未配置时 ingest 优雅降级（返回 False 不抛错）。"""

        async def _boom(_record):
            raise RuntimeError("数据库未配置")

        monkeypatch.setattr(
            "app.integrations.mtconnect.experience_bridge.create_cutting_experience",
            _boom,
        )
        bridge = MTConnectExperienceBridge(machine_id="VM-001")
        ok = await bridge.ingest_sample(_sample())
        assert ok is False

    @pytest.mark.asyncio
    async def test_ingest_batch_db_unconfigured(self, monkeypatch) -> None:
        async def _boom(_records):
            raise RuntimeError("数据库未配置")

        monkeypatch.setattr(
            "app.integrations.mtconnect.experience_bridge.create_many_cutting_experiences",
            _boom,
        )
        bridge = MTConnectExperienceBridge(machine_id="VM-001")
        result = await bridge.ingest_batch([_sample(), _sample()])
        # 2 条全部丢弃（DB 不可用）
        assert result["ingested"] == 0
        assert result["discarded"] == 2

    @pytest.mark.asyncio
    async def test_ingest_batch_success(self, monkeypatch) -> None:
        async def _fake_create(records):
            return len(records)

        monkeypatch.setattr(
            "app.integrations.mtconnect.experience_bridge.create_many_cutting_experiences",
            _fake_create,
        )
        bridge = MTConnectExperienceBridge(machine_id="VM-001")
        result = await bridge.ingest_batch([_sample(), _sample(), Sample()])
        assert result["ingested"] == 2
        assert result["discarded"] == 1
        assert bridge.ingested_count == 2
        assert bridge.discarded_count == 1
