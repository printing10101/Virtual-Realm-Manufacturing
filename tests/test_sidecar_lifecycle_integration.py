import os
import json
import time
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from app.core.sidecar_lifecycle import IdleAutoShutdownMiddleware, GracefulShutdownHandler


class TestSidecarLifecycleIntegration:
    def test_full_lifecycle_startup_to_idle_shutdown(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = os.path.join(tmpdir, "sidecar.json")
            with open(state_file, "w") as f:
                json.dump({"pid": 99999, "port": 8000, "token": "test-token", "startedAt": "2024-01-01T00:00:00", "version": "1.0.0", "status": "running"}, f)

            mock_app = MagicMock()
            handler = GracefulShutdownHandler(app=mock_app, state_file_path=state_file)

            with patch("signal.signal"):
                handler.setup()

            middleware = IdleAutoShutdownMiddleware(
                app=mock_app,
                idle_timeout=1,
                state_file_path=state_file,
            )

            middleware.last_activity_time = time.time() - 2

            with patch.object(middleware, '_send_shutdown_signal', return_value=None):
                middleware.check_idle_and_shutdown()
                assert middleware._shutdown_initiated is True

    def test_state_file_status_transitions(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = os.path.join(tmpdir, "sidecar.json")
            with open(state_file, "w") as f:
                json.dump({"pid": 12345, "status": "running", "port": 8000, "token": "test", "startedAt": "2024-01-01T00:00:00", "version": "1.0.0"}, f)

            handler = GracefulShutdownHandler(app=MagicMock(), state_file_path=state_file)

            handler._update_status_file("shutting_down")
            with open(state_file, "r") as f:
                state = json.load(f)
            assert state["status"] == "shutting_down"

            handler._update_status_file("stopped")
            with open(state_file, "r") as f:
                state = json.load(f)
            assert state["status"] == "stopped"

    def test_cleanup_all_resources_no_errors(self):
        handler = GracefulShutdownHandler(app=MagicMock())

        with patch("app.core.sidecar_lifecycle.logger"):
            handler._cleanup_all_resources()

    def test_health_endpoint_excluded_from_idle_tracking(self):
        mock_app = MagicMock()
        middleware = IdleAutoShutdownMiddleware(app=mock_app, idle_timeout=1800)

        initial_time = middleware.last_activity_time

        async def call_next(req):
            return MagicMock()

        import asyncio
        request = MagicMock()
        request.url.path = "/health"

        asyncio.run(middleware.dispatch(request, call_next))

        assert middleware.last_activity_time == initial_time
