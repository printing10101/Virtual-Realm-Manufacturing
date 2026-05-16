"""Unit tests for audit_log module."""

from __future__ import annotations

import pytest
from app.core.audit_log import AuditLog, AIModule, UserDecision, OperationStatus


class TestAIModuleEnum:
    def test_all_modules_defined(self):
        modules = [
            AIModule.LNN_PREDICT,
            AIModule.LNN_TRAIN,
            AIModule.PROCESS_OPTIMIZE,
            AIModule.TOOL_WEAR_ANALYZE,
            AIModule.CAD_GENERATE,
        ]
        for m in modules:
            assert isinstance(m.value, str)
            assert len(m.value) > 0


class TestUserDecisionEnum:
    def test_all_decisions_defined(self):
        decisions = [
            UserDecision.ACCEPT,
            UserDecision.MODIFY,
            UserDecision.REJECT,
            UserDecision.AUTO_EXECUTED,
        ]
        for d in decisions:
            assert isinstance(d.value, str)


class TestOperationStatusEnum:
    def test_all_statuses_defined(self):
        statuses = [
            OperationStatus.SUCCESS,
            OperationStatus.FAILED,
            OperationStatus.CANCELLED,
            OperationStatus.PENDING,
        ]
        for s in statuses:
            assert isinstance(s.value, str)


class TestAuditLog:
    def test_create_audit_log_instance(self):
        audit = AuditLog()
        assert audit is not None

    def test_log_decision_returns_entry(self):
        audit = AuditLog()
        entry = audit.log_decision(
            ai_module=AIModule.LNN_PREDICT,
            ai_recommendation={"value": 0.95},
            user_decision=UserDecision.ACCEPT,
            final_execution={"result": "success"},
            operation_status=OperationStatus.SUCCESS,
            confidence=0.95,
        )
        assert entry is not None
        assert entry.timestamp_ms > 0

    def test_get_logs_returns_list(self):
        audit = AuditLog()
        logs = audit.get_logs(limit=10, offset=0)
        assert isinstance(logs, list)

    def test_get_statistics_returns_dict(self):
        audit = AuditLog()
        stats = audit.get_statistics()
        assert isinstance(stats, dict)

    def test_clear_logs_returns_count(self):
        audit = AuditLog()
        count = audit.clear_logs()
        assert isinstance(count, int)
        assert count >= 0

    def test_search_logs_returns_list(self):
        audit = AuditLog()
        logs = audit.search_logs(keyword="test", limit=10)
        assert isinstance(logs, list)

    def test_export_logs_csv_format(self):
        audit = AuditLog()
        result = audit.export_logs(format="csv")
        assert isinstance(result, str)

    def test_export_logs_json_format(self):
        audit = AuditLog()
        result = audit.export_logs(format="json")
        assert isinstance(result, str)

    def test_get_logs_with_filters(self):
        audit = AuditLog()
        logs = audit.get_logs(
            limit=5,
            offset=0,
            ai_module="lnn_predict",
            user_decision="accept",
        )
        assert isinstance(logs, list)
