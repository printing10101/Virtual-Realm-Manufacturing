import os
import json
import time
import pytest
import tempfile
from pathlib import Path

from app.core.audit_log import AuditLog, AIModule, UserDecision, OperationStatus, AuditLogEntry


@pytest.fixture
def temp_audit_log():
    with tempfile.TemporaryDirectory() as tmpdir:
        log = AuditLog(log_dir=tmpdir, max_entries=1000)
        yield log


class TestAuditLogEntry:
    def test_entry_creation(self):
        entry = AuditLogEntry(
            timestamp_ms=1234567890123,
            ai_module="lnn_predict",
            ai_recommendation={"value": 0.85},
            user_decision="accept",
            final_execution={"value": 0.85},
            operation_status="success",
            confidence=0.92,
            reasoning="Test reasoning",
        )

        assert entry.timestamp_ms == 1234567890123
        assert entry.ai_module == "lnn_predict"
        assert entry.confidence == 0.92

    def test_entry_creation_with_new_fields(self):
        entry = AuditLogEntry(
            timestamp_ms=1234567890123,
            ai_module="lnn_predict",
            ai_recommendation={"value": 0.85},
            user_decision="accept",
            final_execution={"value": 0.85},
            operation_status="success",
            user_id="user-001",
            username="张三",
            input_parameters={"model_name": "test_model", "input_data": [1.0, 2.0]},
            confidence=0.92,
            reasoning="Test reasoning",
        )

        assert entry.user_id == "user-001"
        assert entry.username == "张三"
        assert entry.input_parameters == {"model_name": "test_model", "input_data": [1.0, 2.0]}

    def test_entry_default_input_parameters(self):
        entry = AuditLogEntry(
            timestamp_ms=1234567890123,
            ai_module="lnn_predict",
            ai_recommendation={"value": 0.85},
            user_decision="accept",
            final_execution={"value": 0.85},
            operation_status="success",
        )

        assert entry.input_parameters == {}

    def test_entry_to_dict(self):
        entry = AuditLogEntry(
            timestamp_ms=1234567890123,
            ai_module="lnn_train",
            ai_recommendation={"model": "test"},
            user_decision="modify",
            final_execution={"model": "test-v2"},
            operation_status="success",
            user_modifications={"model": "test-v2"},
        )

        d = entry.to_dict()
        assert d["timestamp_ms"] == 1234567890123
        assert d["ai_module"] == "lnn_train"
        assert d["user_modifications"] == {"model": "test-v2"}
        assert d["user_id"] is None
        assert d["username"] is None
        assert d["input_parameters"] == {}

    def test_entry_to_dict_with_new_fields(self):
        entry = AuditLogEntry(
            timestamp_ms=1234567890123,
            ai_module="lnn_train",
            ai_recommendation={"model": "test"},
            user_decision="modify",
            final_execution={"model": "test-v2"},
            operation_status="success",
            user_id="user-002",
            username="李四",
            input_parameters={"param1": "value1"},
            user_modifications={"model": "test-v2"},
        )

        d = entry.to_dict()
        assert d["user_id"] == "user-002"
        assert d["username"] == "李四"
        assert d["input_parameters"] == {"param1": "value1"}

    def test_entry_from_dict(self):
        data = {
            "timestamp_ms": 9876543210987,
            "ai_module": "process_optimize",
            "ai_recommendation": {"params": [1, 2, 3]},
            "user_decision": "reject",
            "final_execution": {},
            "operation_status": "cancelled",
            "confidence": 0.75,
        }

        entry = AuditLogEntry.from_dict(data)
        assert entry.timestamp_ms == 9876543210987
        assert entry.confidence == 0.75
        assert entry.ai_recommendation == {"params": [1, 2, 3]}

    def test_entry_from_dict_with_new_fields(self):
        data = {
            "timestamp_ms": 9876543210987,
            "ai_module": "process_optimize",
            "ai_recommendation": {"params": [1, 2, 3]},
            "user_decision": "reject",
            "final_execution": {},
            "operation_status": "cancelled",
            "user_id": "user-003",
            "username": "王五",
            "input_parameters": {"key": "val"},
            "confidence": 0.75,
        }

        entry = AuditLogEntry.from_dict(data)
        assert entry.user_id == "user-003"
        assert entry.username == "王五"
        assert entry.input_parameters == {"key": "val"}

    def test_entry_from_dict_backward_compat(self):
        data = {
            "timestamp_ms": 1111111111111,
            "ai_module": "cad_generate",
            "ai_recommendation": {"script": "test.gcode"},
            "user_decision": "auto_executed",
            "final_execution": {"script": "test.gcode"},
            "operation_status": "success",
        }

        entry = AuditLogEntry.from_dict(data)
        assert entry.timestamp_ms == 1111111111111
        assert entry.user_id is None
        assert entry.username is None
        assert entry.input_parameters == {}

    def test_entry_from_dict_missing_optional_fields(self):
        data = {
            "timestamp_ms": 2222222222222,
            "ai_module": "tool_wear_analyze",
            "ai_recommendation": {"wear": 0.5},
            "user_decision": "accept",
            "final_execution": {"wear": 0.5},
            "operation_status": "success",
            "confidence": None,
        }

        entry = AuditLogEntry.from_dict(data)
        assert entry.user_id is None
        assert entry.username is None
        assert entry.input_parameters == {}
        assert entry.confidence is None


class TestAuditLogDecision:
    def test_log_decision(self, temp_audit_log):
        entry = temp_audit_log.log_decision(
            ai_module=AIModule.LNN_PREDICT,
            ai_recommendation={"prediction": 0.5},
            user_decision=UserDecision.ACCEPT,
            final_execution={"prediction": 0.5},
            operation_status=OperationStatus.SUCCESS,
            confidence=0.9,
            reasoning="High confidence prediction",
        )

        assert entry.timestamp_ms > 0
        assert entry.ai_module == "lnn_predict"
        assert entry.user_decision == "accept"
        assert entry.confidence == 0.9

    def test_log_decision_with_user_info(self, temp_audit_log):
        entry = temp_audit_log.log_decision(
            ai_module=AIModule.LNN_PREDICT,
            ai_recommendation={"prediction": 0.5},
            user_decision=UserDecision.ACCEPT,
            final_execution={"prediction": 0.5},
            operation_status=OperationStatus.SUCCESS,
            user_id="user-001",
            username="测试用户",
            input_parameters={"model_name": "test", "input_data": [1, 2, 3]},
            confidence=0.9,
            reasoning="High confidence prediction",
        )

        assert entry.user_id == "user-001"
        assert entry.username == "测试用户"
        assert entry.input_parameters == {"model_name": "test", "input_data": [1, 2, 3]}

    def test_log_multiple_decisions(self, temp_audit_log):
        temp_audit_log.log_decision(
            ai_module=AIModule.LNN_PREDICT,
            ai_recommendation={"v": 1},
            user_decision=UserDecision.ACCEPT,
            final_execution={"v": 1},
            operation_status=OperationStatus.SUCCESS,
        )

        temp_audit_log.log_decision(
            ai_module=AIModule.LNN_TRAIN,
            ai_recommendation={"epochs": 100},
            user_decision=UserDecision.MODIFY,
            final_execution={"epochs": 50},
            operation_status=OperationStatus.SUCCESS,
            user_modifications={"epochs": 50},
        )

        temp_audit_log.log_decision(
            ai_module=AIModule.LNN_PREDICT,
            ai_recommendation={"v": 2},
            user_decision=UserDecision.REJECT,
            final_execution={},
            operation_status=OperationStatus.CANCELLED,
        )

        logs = temp_audit_log.get_logs()
        assert len(logs) == 3

    def test_log_file_created(self, temp_audit_log):
        temp_audit_log.log_decision(
            ai_module=AIModule.CAD_GENERATE,
            ai_recommendation={"script": "test"},
            user_decision=UserDecision.AUTO_EXECUTED,
            final_execution={"script": "test"},
            operation_status=OperationStatus.SUCCESS,
        )

        log_file = temp_audit_log._get_current_log_file()
        assert os.path.exists(log_file)
        with open(log_file, "r", encoding="utf-8") as f:
            lines = f.readlines()
        assert len(lines) == 1


class TestAuditLogQuery:
    def test_get_logs_empty(self, temp_audit_log):
        logs = temp_audit_log.get_logs()
        assert logs == []

    def test_get_logs_with_entries(self, temp_audit_log):
        for i in range(5):
            temp_audit_log.log_decision(
                ai_module=AIModule.LNN_PREDICT,
                ai_recommendation={"i": i},
                user_decision=UserDecision.ACCEPT,
                final_execution={"i": i},
                operation_status=OperationStatus.SUCCESS,
            )

        logs = temp_audit_log.get_logs()
        assert len(logs) == 5

    def test_get_logs_with_limit(self, temp_audit_log):
        for i in range(10):
            temp_audit_log.log_decision(
                ai_module=AIModule.LNN_PREDICT,
                ai_recommendation={"i": i},
                user_decision=UserDecision.ACCEPT,
                final_execution={"i": i},
                operation_status=OperationStatus.SUCCESS,
            )

        logs = temp_audit_log.get_logs(limit=3)
        assert len(logs) == 3

    def test_get_logs_with_offset(self, temp_audit_log):
        for i in range(10):
            temp_audit_log.log_decision(
                ai_module=AIModule.LNN_PREDICT,
                ai_recommendation={"i": i},
                user_decision=UserDecision.ACCEPT,
                final_execution={"i": i},
                operation_status=OperationStatus.SUCCESS,
            )

        logs = temp_audit_log.get_logs(limit=5, offset=5)
        assert len(logs) == 5

    def test_get_logs_filter_by_module(self, temp_audit_log):
        temp_audit_log.log_decision(
            ai_module=AIModule.LNN_PREDICT,
            ai_recommendation={"m": "predict"},
            user_decision=UserDecision.ACCEPT,
            final_execution={"m": "predict"},
            operation_status=OperationStatus.SUCCESS,
        )

        temp_audit_log.log_decision(
            ai_module=AIModule.LNN_TRAIN,
            ai_recommendation={"m": "train"},
            user_decision=UserDecision.ACCEPT,
            final_execution={"m": "train"},
            operation_status=OperationStatus.SUCCESS,
        )

        logs = temp_audit_log.get_logs(ai_module="lnn_predict")
        assert len(logs) == 1
        assert logs[0].ai_module == "lnn_predict"

    def test_get_logs_filter_by_decision(self, temp_audit_log):
        temp_audit_log.log_decision(
            ai_module=AIModule.LNN_PREDICT,
            ai_recommendation={"d": "accept"},
            user_decision=UserDecision.ACCEPT,
            final_execution={"d": "accept"},
            operation_status=OperationStatus.SUCCESS,
        )

        temp_audit_log.log_decision(
            ai_module=AIModule.LNN_PREDICT,
            ai_recommendation={"d": "reject"},
            user_decision=UserDecision.REJECT,
            final_execution={},
            operation_status=OperationStatus.CANCELLED,
        )

        logs = temp_audit_log.get_logs(user_decision="reject")
        assert len(logs) == 1
        assert logs[0].user_decision == "reject"

    def test_get_logs_filter_by_user_id(self, temp_audit_log):
        temp_audit_log.log_decision(
            ai_module=AIModule.LNN_PREDICT,
            ai_recommendation={"uid": "u1"},
            user_decision=UserDecision.ACCEPT,
            final_execution={"uid": "u1"},
            operation_status=OperationStatus.SUCCESS,
            user_id="user-001",
            username="Alice",
        )

        temp_audit_log.log_decision(
            ai_module=AIModule.LNN_PREDICT,
            ai_recommendation={"uid": "u2"},
            user_decision=UserDecision.ACCEPT,
            final_execution={"uid": "u2"},
            operation_status=OperationStatus.SUCCESS,
            user_id="user-002",
            username="Bob",
        )

        temp_audit_log.log_decision(
            ai_module=AIModule.LNN_PREDICT,
            ai_recommendation={"uid": "u3"},
            user_decision=UserDecision.ACCEPT,
            final_execution={"uid": "u3"},
            operation_status=OperationStatus.SUCCESS,
        )

        logs_u1 = temp_audit_log.get_logs(user_id="user-001")
        assert len(logs_u1) == 1
        assert logs_u1[0].user_id == "user-001"
        assert logs_u1[0].username == "Alice"

        logs_u2 = temp_audit_log.get_logs(user_id="user-002")
        assert len(logs_u2) == 1
        assert logs_u2[0].user_id == "user-002"

        logs_none = temp_audit_log.get_logs(user_id="nonexistent")
        assert len(logs_none) == 0

    def test_get_logs_filter_by_time(self, temp_audit_log):
        t1 = int(time.time() * 1000) - 10000
        t2 = int(time.time() * 1000) + 10000

        temp_audit_log.log_decision(
            ai_module=AIModule.LNN_PREDICT,
            ai_recommendation={"t": 1},
            user_decision=UserDecision.ACCEPT,
            final_execution={"t": 1},
            operation_status=OperationStatus.SUCCESS,
        )

        logs = temp_audit_log.get_logs(start_time=t1)
        assert len(logs) >= 1

        logs = temp_audit_log.get_logs(end_time=t2)
        assert len(logs) >= 1


class TestAuditLogSearch:
    def test_search_logs(self, temp_audit_log):
        temp_audit_log.log_decision(
            ai_module=AIModule.LNN_PREDICT,
            ai_recommendation={"value": 0.5},
            user_decision=UserDecision.ACCEPT,
            final_execution={"value": 0.5},
            operation_status=OperationStatus.SUCCESS,
            reasoning="High confidence prediction",
        )

        temp_audit_log.log_decision(
            ai_module=AIModule.LNN_TRAIN,
            ai_recommendation={"epochs": 100},
            user_decision=UserDecision.MODIFY,
            final_execution={"epochs": 50},
            operation_status=OperationStatus.SUCCESS,
            reasoning="Adjusted epochs",
        )

        results = temp_audit_log.search_logs("prediction")
        assert len(results) == 1
        assert "prediction" in results[0].reasoning.lower() or "prediction" in json.dumps(results[0].ai_recommendation).lower()

    def test_search_logs_no_match(self, temp_audit_log):
        temp_audit_log.log_decision(
            ai_module=AIModule.LNN_PREDICT,
            ai_recommendation={"value": 0.5},
            user_decision=UserDecision.ACCEPT,
            final_execution={"value": 0.5},
            operation_status=OperationStatus.SUCCESS,
        )

        results = temp_audit_log.search_logs("nonexistent_keyword_xyz")
        assert len(results) == 0


class TestAuditLogExport:
    def test_export_json(self, temp_audit_log):
        temp_audit_log.log_decision(
            ai_module=AIModule.LNN_PREDICT,
            ai_recommendation={"v": 1},
            user_decision=UserDecision.ACCEPT,
            final_execution={"v": 1},
            operation_status=OperationStatus.SUCCESS,
        )

        exported = temp_audit_log.export_logs(format="json")
        data = json.loads(exported)
        assert isinstance(data, list)
        assert len(data) >= 1

    def test_export_csv(self, temp_audit_log):
        temp_audit_log.log_decision(
            ai_module=AIModule.LNN_TRAIN,
            ai_recommendation={"epochs": 100},
            user_decision=UserDecision.ACCEPT,
            final_execution={"epochs": 100},
            operation_status=OperationStatus.SUCCESS,
            reasoning="Training plan accepted",
        )

        exported = temp_audit_log.export_logs(format="csv")
        lines = exported.strip().split("\n")
        assert len(lines) >= 2
        assert "timestamp_ms" in lines[0]
        assert "lnn_train" in exported

    def test_export_csv_with_user_fields(self, temp_audit_log):
        temp_audit_log.log_decision(
            ai_module=AIModule.LNN_PREDICT,
            ai_recommendation={"v": 1},
            user_decision=UserDecision.ACCEPT,
            final_execution={"v": 1},
            operation_status=OperationStatus.SUCCESS,
            user_id="user-001",
            username="测试用户",
            reasoning="Test",
        )

        exported = temp_audit_log.export_logs(format="csv")
        lines = exported.strip().split("\n")
        assert "user_id" in lines[0]
        assert "username" in lines[0]
        assert "user-001" in exported
        assert "测试用户" in exported

    def test_export_unsupported_format(self, temp_audit_log):
        with pytest.raises(ValueError, match="Unsupported export format"):
            temp_audit_log.export_logs(format="xml")


class TestAuditLogStatistics:
    def test_statistics_empty(self, temp_audit_log):
        stats = temp_audit_log.get_statistics()
        assert stats["total_entries"] == 0
        assert stats["avg_confidence"] == 0.0

    def test_statistics_with_entries(self, temp_audit_log):
        temp_audit_log.log_decision(
            ai_module=AIModule.LNN_PREDICT,
            ai_recommendation={"v": 1},
            user_decision=UserDecision.ACCEPT,
            final_execution={"v": 1},
            operation_status=OperationStatus.SUCCESS,
            confidence=0.9,
        )

        temp_audit_log.log_decision(
            ai_module=AIModule.LNN_TRAIN,
            ai_recommendation={"v": 2},
            user_decision=UserDecision.MODIFY,
            final_execution={"v": 2},
            operation_status=OperationStatus.SUCCESS,
            confidence=0.7,
        )

        stats = temp_audit_log.get_statistics()
        assert stats["total_entries"] == 2
        assert abs(stats["avg_confidence"] - 0.8) < 0.01
        assert stats["by_module"]["lnn_predict"] == 1
        assert stats["by_module"]["lnn_train"] == 1
        assert stats["by_decision"]["accept"] == 1
        assert stats["by_decision"]["modify"] == 1


class TestAuditLogRotation:
    def test_rotation(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            log = AuditLog(log_dir=tmpdir, max_entries=10)

            for i in range(20):
                log.log_decision(
                    ai_module=AIModule.LNN_PREDICT,
                    ai_recommendation={"i": i},
                    user_decision=UserDecision.ACCEPT,
                    final_execution={"i": i},
                    operation_status=OperationStatus.SUCCESS,
                )

            logs = log.get_logs(limit=100)
            assert len(logs) <= 10


class TestAuditLogClear:
    def test_clear_logs(self, temp_audit_log):
        for i in range(5):
            temp_audit_log.log_decision(
                ai_module=AIModule.LNN_PREDICT,
                ai_recommendation={"i": i},
                user_decision=UserDecision.ACCEPT,
                final_execution={"i": i},
                operation_status=OperationStatus.SUCCESS,
            )

        count = temp_audit_log.clear_logs()
        assert count == 5

        logs = temp_audit_log.get_logs()
        assert len(logs) == 0


class TestAuditLogBackwardCompat:
    """测试旧格式 JSONL 日志文件的兼容性"""

    def test_load_old_format_jsonl(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            log = AuditLog(log_dir=tmpdir, max_entries=1000)

            log_file = log._get_current_log_file()
            old_entry = json.dumps({
                "timestamp_ms": 1234567890000,
                "ai_module": "lnn_predict",
                "ai_recommendation": {"prediction": 0.8},
                "user_decision": "accept",
                "final_execution": {"prediction": 0.8},
                "operation_status": "success",
                "confidence": 0.95,
                "reasoning": "Old format reasoning",
            }, ensure_ascii=False)

            with open(log_file, "a", encoding="utf-8") as f:
                f.write(old_entry + "\n")

            logs = log.get_logs()
            assert len(logs) == 1
            entry = logs[0]
            assert entry.timestamp_ms == 1234567890000
            assert entry.user_id is None
            assert entry.username is None
            assert entry.input_parameters == {}
            assert entry.confidence == 0.95
            assert entry.reasoning == "Old format reasoning"

    def test_load_mixed_format_jsonl(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            log = AuditLog(log_dir=tmpdir, max_entries=1000)

            log_file = log._get_current_log_file()

            old_entry = json.dumps({
                "timestamp_ms": 1234567890000,
                "ai_module": "lnn_predict",
                "ai_recommendation": {"prediction": 0.8},
                "user_decision": "accept",
                "final_execution": {"prediction": 0.8},
                "operation_status": "success",
            }, ensure_ascii=False)

            new_entry = json.dumps({
                "timestamp_ms": 1234567890001,
                "ai_module": "lnn_train",
                "ai_recommendation": {"epochs": 100},
                "user_decision": "modify",
                "final_execution": {"epochs": 50},
                "operation_status": "success",
                "user_id": "user-001",
                "username": "张三",
                "input_parameters": {"model_name": "test"},
            }, ensure_ascii=False)

            with open(log_file, "a", encoding="utf-8") as f:
                f.write(old_entry + "\n")
                f.write(new_entry + "\n")

            logs = log.get_logs()
            assert len(logs) == 2

            old_log = [l for l in logs if l.timestamp_ms == 1234567890000][0]
            assert old_log.user_id is None
            assert old_log.username is None
            assert old_log.input_parameters == {}

            new_log = [l for l in logs if l.timestamp_ms == 1234567890001][0]
            assert new_log.user_id == "user-001"
            assert new_log.username == "张三"
            assert new_log.input_parameters == {"model_name": "test"}


class TestEnums:
    def test_user_decision_values(self):
        assert UserDecision.ACCEPT.value == "accept"
        assert UserDecision.MODIFY.value == "modify"
        assert UserDecision.REJECT.value == "reject"
        assert UserDecision.AUTO_EXECUTED.value == "auto_executed"

    def test_operation_status_values(self):
        assert OperationStatus.SUCCESS.value == "success"
        assert OperationStatus.FAILED.value == "failed"
        assert OperationStatus.CANCELLED.value == "cancelled"
        assert OperationStatus.PENDING.value == "pending"

    def test_ai_module_values(self):
        assert AIModule.LNN_PREDICT.value == "lnn_predict"
        assert AIModule.LNN_TRAIN.value == "lnn_train"
        assert AIModule.PROCESS_OPTIMIZE.value == "process_optimize"
        assert AIModule.TOOL_WEAR_ANALYZE.value == "tool_wear_analyze"
        assert AIModule.CAD_GENERATE.value == "cad_generate"
