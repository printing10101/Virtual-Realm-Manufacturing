"""Standalone worker process for plugin execution.

This script is spawned by PluginWorkerManager._run_worker() as an independent
subprocess. It loads the target plugin, initializes it, and runs an HTTP
health-check endpoint on the port assigned via the PLUGIN_PORT environment
variable.

Environment variables set by the parent:
    PLUGIN_ID     — unique plugin identifier
    PLUGIN_PORT   — port for the health-check HTTP server
    PLUGIN_PATH   — filesystem path to the plugin directory
"""
from __future__ import annotations

import http.server
import json
import logging
import os
import signal
import socketserver
import sys
import threading
import time
from typing import Any, Dict, Optional

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger("worker_process")


class _WorkerState:
    """Shared mutable state accessed by the HTTP handler and main loop."""

    plugin_id: str = ""
    plugin_path: str = ""
    plugin_instance: Optional[Any] = None
    started_at: float = 0.0
    running: bool = True


state = _WorkerState()


def _load_plugin() -> Any:
    """Dynamically import the plugin module from PLUGIN_PATH and return its instance."""
    plugin_dir = state.plugin_path
    if plugin_dir not in sys.path:
        sys.path.insert(0, plugin_dir)

    try:
        from plugin import create_plugin  # noqa: E402

        instance = create_plugin()
        logger.info("Plugin '%s' loaded from %s", state.plugin_id, plugin_dir)
        return instance
    except ImportError:
        logger.warning("No plugin.py found in %s, using stub", plugin_dir)
        return None


def _start_health_server(port: int) -> socketserver.TCPServer:
    """Start a minimal HTTP server that reports worker health status."""

    class HealthHandler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/health":
                payload = {
                    "status": "running",
                    "plugin_id": state.plugin_id,
                    "uptime": time.time() - state.started_at,
                }
                body = json.dumps(payload).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            else:
                self.send_response(404)
                self.end_headers()

        def log_message(self, format, *args):
            logger.debug(format, *args)

    server = socketserver.TCPServer(("0.0.0.0", port), HealthHandler)
    server.daemon_threads = True
    return server


def _signal_handler(signum: int, frame: Any) -> None:
    """Handle SIGTERM / SIGINT for graceful shutdown."""
    logger.info("Received signal %s, shutting down", signum)
    state.running = False


def main() -> None:
    # Read environment
    state.plugin_id = os.environ.get("PLUGIN_ID", "unknown")
    state.plugin_port = int(os.environ.get("PLUGIN_PORT", "8080"))
    state.plugin_path = os.environ.get("PLUGIN_PATH", ".")
    state.started_at = time.time()

    logger.info("Worker starting: id=%s, port=%s, path=%s",
                state.plugin_id, state.plugin_port, state.plugin_path)

    signal.signal(signal.SIGTERM, _signal_handler)
    signal.signal(signal.SIGINT, _signal_handler)

    plugin = _load_plugin()
    state.plugin_instance = plugin

    if plugin and hasattr(plugin, "initialize"):
        plugin.initialize({})

    server = _start_health_server(state.plugin_port)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()

    logger.info("Health server listening on port %s", state.plugin_port)

    try:
        while state.running:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        server.shutdown()
        if plugin and hasattr(plugin, "shutdown"):
            plugin.shutdown()
        logger.info("Worker stopped")


if __name__ == "__main__":
    main()
