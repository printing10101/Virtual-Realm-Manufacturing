import os
import json
import time
import tempfile
import signal
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from app.core.sidecar_lifecycle import (
    IdleAutoShutdownMiddleware,
    GracefulShutdownHandler,
)


class TestIdleAutoShutdownMiddleware:
    @pytest.fixture
    def mock_app(self):
        app = MagicMock()
        return app

    def test_middleware_initialization(self, mock_app):
        middleware = IdleAutoShutdownMiddleware(
            app=mock_app,
            idle_timeout=1800,
            state_file_path="/tmp/test_state.json",
        )

        assert middleware.idle_timeout == 1800
        assert middleware.last_activity_time > 0
        assert middleware.state_file_path == "/tmp/test_state.json"
        assert middleware._shutdown_initiated is False

    def test_non_health_request_updates_activity_time(self, mock_app):
        middleware = IdleAutoShutdownMiddleware(app=mock_app, idle_timeout=1800)
        initial_time = middleware.last_activity_time

        time.sleep(0.1)

        request = MagicMock()
        request.url.path = "/api/v1/lnn/predict"

        async def call_next(req):
            return MagicMock()

        import asyncio
        asyncio.run(middleware.dispatch(request, call_next))

        assert middleware.last_activity_time > initial_time

    def test_health_request_does_not_update_activity_time(self, mock_app):
        middleware = IdleAutoShutdownMiddleware(app=mock_app, idle_timeout=1800)
        initial_time = middleware.last_activity_time

        time.sleep(0.1)

        request = MagicMock()
        request.url.path = "/health"

        async def call_next(req):
            return MagicMock()

        import asyncio
        asyncio.run(middleware.dispatch(request, call_next))

        assert middleware.last_activity_time == initial_time

    def test_idle_timeout_triggers_shutdown(self, mock_app):
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = os.path.join(tmpdir, "sidecar.json")
            with open(state_file, "w") as f:
                json.dump({"pid": 12345, "port": 8765, "token": "test", "startedAt": "2024-01-01T00:00:00", "version": "1.0.0"}, f)

            middleware = IdleAutoShutdownMiddleware(
                app=mock_app,
                idle_timeout=1,
                state_file_path=state_file,
            )

            middleware.last_activity_time = time.time() - 2

            with patch.object(middleware, '_send_shutdown_signal', return_value=None):
                middleware.check_idle_and_shutdown()
                assert middleware._shutdown_initiated is True

    def test_no_idle_timeout_when_active(self, mock_app):
        middleware = IdleAutoShutdownMiddleware(app=mock_app, idle_timeout=1800)
        middleware.check_idle_and_shutdown()
        assert middleware._shutdown_initiated is False

    def test_cleanup_resources(self, mock_app):
        middleware = IdleAutoShutdownMiddleware(app=mock_app)

        with patch("app.core.sidecar_lifecycle.logger"):
            middleware._cleanup_resources()

    def test_remove_state_file(self, mock_app):
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = os.path.join(tmpdir, "sidecar.json")
            with open(state_file, "w") as f:
                json.dump({"pid": 12345}, f)

            middleware = IdleAutoShutdownMiddleware(
                app=mock_app,
                state_file_path=state_file,
            )

            middleware._remove_state_file()
            assert not os.path.exists(state_file)

    def test_remove_nonexistent_state_file(self, mock_app):
        middleware = IdleAutoShutdownMiddleware(
            app=mock_app,
            state_file_path="/nonexistent/path/state.json",
        )

        middleware._remove_state_file()


class TestGracefulShutdownHandler:
    @pytest.fixture
    def handler(self, mock_app):
        handler = GracefulShutdownHandler(
            app=mock_app,
            state_file_path="/tmp/test_state.json",
        )
        return handler

    def test_handler_initialization(self, mock_app):
        handler = GracefulShutdownHandler(app=mock_app)
        assert handler.app == mock_app
        assert handler._shutting_down is False

    def test_setup_registers_signal_handlers(self, mock_app):
        handler = GracefulShutdownHandler(app=mock_app)

        with patch("signal.signal") as mock_signal:
            handler.setup()
            assert mock_signal.call_count >= 2

    def test_update_status_file(self, mock_app):
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = os.path.join(tmpdir, "sidecar.json")
            with open(state_file, "w") as f:
                json.dump({"pid": 12345, "status": "running"}, f)

            handler = GracefulShutdownHandler(app=mock_app, state_file_path=state_file)
            handler._update_status_file("shutting_down")

            with open(state_file, "r") as f:
                state = json.load(f)

            assert state["status"] == "shutting_down"

    def test_remove_state_file(self, mock_app):
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = os.path.join(tmpdir, "sidecar.json")
            with open(state_file, "w") as f:
                json.dump({"pid": 12345}, f)

            handler = GracefulShutdownHandler(app=mock_app, state_file_path=state_file)
            handler._remove_state_file()
            assert not os.path.exists(state_file)

    def test_shutdown_signal_idempotency(self, mock_app):
        handler = GracefulShutdownHandler(app=mock_app)
        handler._shutting_down = True

        with patch("asyncio.get_event_loop") as mock_loop:
            loop = MagicMock()
            loop.is_running.return_value = True
            mock_loop.return_value = loop

            handler._handle_shutdown_signal(signal.SIGTERM, None)

    def test_atexit_handler_triggers_cleanup(self, mock_app):
        handler = GracefulShutdownHandler(app=mock_app)

        with patch.object(handler, '_cleanup_all_resources') as mock_cleanup:
            handler._handle_atexit()
            mock_cleanup.assert_called_once()


@pytest.fixture
def mock_app():
    return MagicMock()
