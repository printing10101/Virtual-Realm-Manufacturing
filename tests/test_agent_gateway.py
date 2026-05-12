"""Tests for Agent Gateway auth, middleware, and API."""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "python"))

import pytest
from unittest.mock import patch, MagicMock


class TestAgentTokenAuth:
    def test_generate_token_format(self):
        from app.agent.auth import agent_token_store
        raw, token = agent_token_store.create_token(scopes=["R", "W"])
        assert raw.startswith("lj_agent_")
        assert len(raw) == 9 + 32
        assert token.agent_id
        assert token.scopes == ["R", "W"]
        assert token.paper_only is True
        agent_token_store.revoke_token(token.agent_id)

    def test_token_hash_storage(self):
        from app.agent.auth import agent_token_store
        raw, token = agent_token_store.create_token(scopes=["R"])
        assert len(token.token_hash) == 64
        agent_token_store.revoke_token(token.agent_id)

    def test_token_validation(self):
        from app.agent.auth import agent_token_store
        raw, token = agent_token_store.create_token(scopes=["R", "B"])
        validated = agent_token_store.validate_token(raw)
        assert validated is not None
        assert validated.agent_id == token.agent_id
        agent_token_store.revoke_token(token.agent_id)

    def test_invalid_token_returns_none(self):
        from app.agent.auth import agent_token_store
        result = agent_token_store.validate_token("lj_agent_invalidtoken")
        assert result is None

    def test_revoked_token_returns_none(self):
        from app.agent.auth import agent_token_store
        raw, token = agent_token_store.create_token(scopes=["R"])
        agent_token_store.revoke_token(token.agent_id)
        result = agent_token_store.validate_token(raw)
        assert result is None

    def test_token_expiry(self):
        from app.agent.auth import agent_token_store
        raw, token = agent_token_store.create_token(scopes=["R"], expires_in=1)
        validated = agent_token_store.validate_token(raw)
        assert validated is not None
        time.sleep(1.5)
        expired = agent_token_store.validate_token(raw)
        assert expired is None

    def test_list_tokens(self):
        from app.agent.auth import agent_token_store
        raw1, t1 = agent_token_store.create_token(scopes=["R"])
        raw2, t2 = agent_token_store.create_token(scopes=["R", "T"])
        tokens = agent_token_store.list_tokens()
        assert len(tokens) >= 2
        agent_token_store.revoke_token(t1.agent_id)
        agent_token_store.revoke_token(t2.agent_id)

    def test_revoke_t_tokens(self):
        from app.agent.auth import agent_token_store
        _, t1 = agent_token_store.create_token(scopes=["R"])
        _, t2 = agent_token_store.create_token(scopes=["T"])
        _, t3 = agent_token_store.create_token(scopes=["R", "T"])
        count = agent_token_store.revoke_t_tokens()
        assert count >= 2
        agent_token_store.revoke_token(t1.agent_id)


class TestAgentAuditLog:
    def test_log_entry(self):
        from app.agent.middleware import agent_audit_log
        agent_audit_log.log(
            agent_id="test-agent",
            route="/api/agent/v1/predict",
            permission_class="R",
            status_code=200,
            latency_ms=15.5,
        )
        entries = agent_audit_log.get_entries(agent_id="test-agent")
        assert len(entries) > 0
        assert entries[0]["route"] == "/api/agent/v1/predict"

    def test_filter_by_permission_class(self):
        from app.agent.middleware import agent_audit_log
        agent_audit_log.log(
            agent_id="test-agent-2",
            route="/api/agent/v1/execute",
            permission_class="T",
            status_code=200,
            latency_ms=10.0,
        )
        entries = agent_audit_log.get_entries(permission_class="T")
        assert any(e["permission_class"] == "T" for e in entries)


class TestAgentRateLimiter:
    def test_within_limit(self):
        from app.agent.middleware import agent_rate_limiter
        agent_id = "test-rate-1"
        assert agent_rate_limiter.check_rate_limit(agent_id) is True
        agent_rate_limiter._request_log[agent_id] = []

    def test_rate_limit_exceeded(self):
        from app.agent.middleware import agent_rate_limiter
        agent_id = "test-rate-2"
        old_max = agent_rate_limiter._max_rpm
        agent_rate_limiter._max_rpm = 2
        agent_rate_limiter.check_rate_limit(agent_id)
        agent_rate_limiter.check_rate_limit(agent_id)
        result = agent_rate_limiter.check_rate_limit(agent_id)
        assert result is False
        agent_rate_limiter._max_rpm = old_max
        agent_rate_limiter._request_log[agent_id] = []


class TestIdempotencyStore:
    def test_store_and_retrieve(self):
        from app.agent.middleware import idempotency_store
        key = "idem-test-1"
        agent_id = "agent-1"
        result = idempotency_store.check_and_set(key, agent_id)
        assert result is None
        idempotency_store.store(key, agent_id, {"status": "success"})
        result = idempotency_store.check_and_set(key, agent_id)
        assert result == {"status": "success"}

    def test_different_agent_returns_none(self):
        from app.agent.middleware import idempotency_store
        key = "idem-test-2"
        idempotency_store.store(key, "agent-1", {"data": "a"})
        result = idempotency_store.check_and_set(key, "agent-2")
        assert result is None


class TestAgentEndpointPermissions:
    def test_health_is_r(self):
        from app.agent.middleware import AGENT_ENDPOINT_PERMISSIONS, PermissionLevel
        assert AGENT_ENDPOINT_PERMISSIONS["GET /api/agent/v1/health"] == PermissionLevel.R

    def test_train_is_b(self):
        from app.agent.middleware import AGENT_ENDPOINT_PERMISSIONS, PermissionLevel
        assert AGENT_ENDPOINT_PERMISSIONS["POST /api/agent/v1/train"] == PermissionLevel.B

    def test_execute_is_t(self):
        from app.agent.middleware import AGENT_ENDPOINT_PERMISSIONS, PermissionLevel
        assert AGENT_ENDPOINT_PERMISSIONS["POST /api/agent/v1/execute"] == PermissionLevel.T

    def test_audit_log_is_c(self):
        from app.agent.middleware import AGENT_ENDPOINT_PERMISSIONS, PermissionLevel
        assert AGENT_ENDPOINT_PERMISSIONS["GET /api/agent/v1/audit-log"] == PermissionLevel.C


class TestScopeChecking:
    def test_r_scope_allows_r(self):
        from app.agent.middleware import check_scope, PermissionLevel
        assert check_scope(["R"], PermissionLevel.R) is True

    def test_r_scope_denies_b(self):
        from app.agent.middleware import check_scope, PermissionLevel
        assert check_scope(["R"], PermissionLevel.B) is False

    def test_t_scope_allows_all(self):
        from app.agent.middleware import check_scope, PermissionLevel
        for level in PermissionLevel:
            assert check_scope(["T"], level) is True


class TestPaperOnlyGuard:
    def test_simulate_operation(self):
        from app.core.permissions import paper_only_guard
        result = paper_only_guard.simulate_t_operation({"machine_id": "m1", "params": {}})
        assert result["status"] == "simulated"

    def test_live_execution_default_false(self):
        from app.core.permissions import paper_only_guard
        assert paper_only_guard.is_live_execution_allowed() is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
