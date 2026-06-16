"""OPC UA Adapter V1 – Subscription-based data acquisition + TDengine persistence.

The :class:`OPCUAAdapter` is the entry point used by both the CLI
and any future background workers.  Its responsibilities are deliberately
narrow:

1. **Connect to the OPC UA server** – establish a secure channel and session.
2. **Subscribe to data nodes** – use OPC UA subscription mechanism for
   real-time data updates.
3. **Parse the data** with :func:`app.integrations.opcua.parser.parse_opcua_data`.
4. **Buffer samples** until either a batch-size threshold or a flush
   interval is reached, then persist them with the project's TDengine
   client (M0.2 deliverable).
5. **Exponential back-off retry** on transient network errors so a
   momentary server hiccup does not derail the whole stream.

The class is intentionally **synchronous** in its public API so it can
be driven from both the CLI (``python -m``) and the FastAPI side
through ``run_in_executor`` – the underlying ``asyncua`` library is
asynchronous but we wrap it for ergonomic usage.
"""

from __future__ import annotations

import asyncio
import logging
import random
import re
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


# Table schema for TDengine.  Kept here (rather than in the TDengine
# client) because the column set is a property of the *OPC UA* contract,
# not of the storage backend.
DEFAULT_TABLE_DDL: Tuple[str, ...] = (
    "(ts TIMESTAMP, ",
    "spindle_speed DOUBLE, ",
    "spindle_load DOUBLE, ",
    "feedrate DOUBLE, ",
    "execution BINARY(32))",
)


@dataclass
class AdapterConfig:
    """Runtime configuration for :class:`OPCUAAdapter`."""

    # Network
    endpoint: str = "opc.tcp://localhost:4840"
    timeout: float = 10.0

    # Subscription
    interval: float = 1.0            # seconds between samples (1 Hz default)

    # Batching
    batch_size: int = 10             # flush after this many samples
    batch_interval: float = 5.0      # ...or after this many seconds

    # Retry
    max_retries: int = 5             # bounded – never spin forever
    initial_backoff: float = 0.5     # seconds for the first retry
    max_backoff: float = 16.0        # ...but capped so we don't sleep forever

    # Storage
    database: str = "test"           # TDengine DB (override per env)
    table: str = "opcua"             # TDengine super/sub-table name

    # Node configuration
    node_ids: Optional[List[str]] = None  # OPC UA node IDs to subscribe

    def __post_init__(self) -> None:
        # Normalize the endpoint URL
        self.endpoint = self.endpoint.strip()
        if not self.endpoint.lower().startswith("opc.tcp://"):
            raise ValueError(
                f"endpoint must be an opc.tcp:// URL, got: {self.endpoint!r}"
            )


# ---------------------------------------------------------------------------
# Adapter
# ---------------------------------------------------------------------------


# Callback type used by the adapter to publish "live" samples to the
# CLI or any other observer.  Receives a fully populated ``Sample``.
SampleCallback = Callable[[Any], None]


class OPCUAAdapter:
    """Subscription + persistence orchestrator for a single OPC UA server.

    Typical usage::

        cfg = AdapterConfig(endpoint="opc.tcp://localhost:4840", interval=1.0)
        adapter = OPCUAAdapter(cfg)
        adapter.connect()                              # fail fast on misconfig
        adapter.run(duration=20.0, on_sample=print)  # blocks for 20 s

    Or, in a long-running service, drain the batch buffer on a timer.
    """

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def __init__(
        self,
        config: Optional[AdapterConfig] = None,
        tdengine_client: Optional[Any] = None,
    ) -> None:
        self.config = config or AdapterConfig()
        # Same trick for the TDengine client – the dependency is
        # imported lazily so unit tests don't need a running TDengine.
        self._tdengine = tdengine_client
        # Internal state
        self._buffer: List[Any] = []
        self._buffer_lock = threading.Lock()
        self._stop_event = threading.Event()
        self._last_flush = time.monotonic()
        self._ingested_count = 0
        self._error_count = 0
        self._client = None
        self._subscription = None
        self._connected = False
        self._loop = None  # Persistent event loop for asyncua operations

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def connect(self) -> Dict[str, str]:
        """Connect to the OPC UA server and create a subscription.

        Returns a dict with the server's identity information:

        * ``endpoint``
        * ``server_uri``
        * ``server_name``

        Raises:
            RuntimeError: on connection errors
        """
        try:
            # Import asyncua lazily to avoid hard dependency
            from asyncua import ua, Client

            logger.info("Connecting to OPC UA server at %s", self.config.endpoint)

            # Create event loop and run it in a background thread so that
            # asyncua's internal publish_loop and other coroutines keep
            # processing while the main thread is blocked in run().
            if self._loop is None:
                self._loop = asyncio.new_event_loop()
                self._loop_thread = threading.Thread(
                    target=self._run_loop,
                    daemon=True,
                    name="opcua-event-loop",
                )
                self._loop_thread.start()

            try:
                # Connect to server
                self._client = Client(self.config.endpoint)
                self._client.session_timeout = int(self.config.timeout * 1000)

                # Schedule connection on the background loop
                self._run_coro(self._client.connect())

                # Get server info
                server_uri = self._run_coro(
                    self._client.get_node(ua.ObjectIds.Server_ServerArray).get_value()
                )
                server_name = self._run_coro(
                    self._client.get_node(ua.ObjectIds.Server_ServerStatus).get_value()
                )

                # Create subscription
                handler = SubHandler(self)
                self._subscription = self._run_coro(
                    self._client.create_subscription(
                        self.config.interval * 1000, handler
                    )
                )

                # Subscribe to nodes
                nodes_to_subscribe = self.config.node_ids
                if not nodes_to_subscribe:
                    # Auto-discover nodes: look for common CNC data items
                    nodes_to_subscribe = self._discover_cnc_nodes()
                    logger.info("Auto-discovered %d CNC nodes: %s",
                              len(nodes_to_subscribe), nodes_to_subscribe)

                if nodes_to_subscribe:
                    nodes = [self._client.get_node(node_id) for node_id in nodes_to_subscribe]
                    
                    # Cache node names for use in the sync callback
                    for node in nodes:
                        try:
                            browse_name = self._run_coro(node.read_browse_name())
                            handler._node_names[node.nodeid.to_string()] = browse_name.Name
                        except Exception as exc:
                            logger.warning("Failed to cache node name for %s: %s", 
                                         node.nodeid.to_string(), exc)
                    
                    self._run_coro(self._subscription.subscribe_data_change(nodes))
                    logger.info("Subscribed to %d nodes", len(nodes))

                self._connected = True
                result = {
                    "endpoint": self.config.endpoint,
                    "server_uri": str(server_uri[0] if server_uri else "unknown"),
                    "server_name": str(server_name),
                }
                logger.info("Connection established: %s", result)
                return result

            except Exception as exc:
                # Clean up on connection failure
                if self._client:
                    try:
                        self._run_coro(self._client.disconnect())
                    except Exception:
                        pass
                raise

        except ImportError as exc:
            raise RuntimeError(
                f"OPC UA client library 'asyncua' not installed: {exc}\n"
                "Install with: pip install asyncua"
            )
        except Exception as exc:
            logger.error("Failed to connect to OPC UA server: %s", exc)
            raise RuntimeError(f"Connection failed: {exc}")

    def _run_loop(self) -> None:
        """Run the event loop in a background thread."""
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_forever()
        finally:
            # Clean up any remaining tasks
            pending = asyncio.all_tasks(self._loop)
            for task in pending:
                task.cancel()
            if pending:
                self._loop.run_until_complete(
                    asyncio.gather(*pending, return_exceptions=True)
                )
            self._loop.run_until_complete(self._loop.shutdown_asyncgens())
            self._loop.close()

    def _run_coro(self, coro: Any) -> Any:
        """Submit a coroutine to the background event loop and wait for result."""
        if self._loop is None or not self._loop.is_running():
            raise RuntimeError("Event loop is not running")
        future = asyncio.run_coroutine_threadsafe(coro, self._loop)
        return future.result(timeout=self.config.timeout)

    def _discover_cnc_nodes(self) -> List[str]:
        """Auto-discover common CNC data nodes from the OPC UA server.

        Looks for nodes with browse names matching common CNC data items:
        SpindleSpeed, SpindleLoad, FeedRate, Execution, etc.

        Returns a list of node IDs (as strings) that can be subscribed to.
        """
        if not self._client or not self._loop:
            return []

        discovered_nodes = []
        target_names = {
            "spindlespeed", "spindleload", "feedrate", "execution",
            "spindle_speed", "spindle_load", "feed_rate",
        }

        try:
            # Browse the objects node to find our data nodes
            objects_node = self._client.nodes.objects
            children = self._run_coro(objects_node.get_children())

            for child in children:
                try:
                    # Get browse name (asyncua 2.0 uses read_browse_name)
                    browse_name = self._run_coro(child.read_browse_name())
                    name_lower = browse_name.Name.lower()

                    # Check if this is a CNC-related object
                    if any(keyword in name_lower for keyword in ["cnc", "machine", "spindle", "feed"]):
                        # Get children of this object
                        sub_children = self._run_coro(child.get_children())
                        for sub_child in sub_children:
                            try:
                                sub_browse = self._run_coro(sub_child.read_browse_name())
                                if sub_browse.Name.lower() in target_names:
                                    node_id = sub_child.nodeid.to_string()
                                    discovered_nodes.append(node_id)
                            except Exception:
                                continue

                    # Also check if the child itself matches
                    if name_lower in target_names:
                        node_id = child.nodeid.to_string()
                        discovered_nodes.append(node_id)

                except Exception:
                    continue

        except Exception as exc:
            logger.warning("Node auto-discovery failed: %s", exc)

        return discovered_nodes

    def disconnect(self) -> None:
        """Disconnect from the OPC UA server."""
        if self._client and self._connected and self._loop:
            try:
                # Cancel all pending tasks before disconnecting
                pending_tasks = [t for t in asyncio.all_tasks(self._loop) if not t.done()]
                if pending_tasks:
                    logger.debug("Cancelling %d pending async tasks", len(pending_tasks))
                    for task in pending_tasks:
                        task.cancel()
                    # Wait briefly for tasks to cancel
                    self._run_coro(asyncio.gather(*pending_tasks, return_exceptions=True))

                if self._subscription:
                    self._run_coro(self._subscription.delete())
                self._run_coro(self._client.disconnect())
            except Exception as exc:
                logger.warning("Error during disconnect: %s", exc)
            finally:
                self._connected = False
                self._client = None
                self._subscription = None
                # Stop the background event loop
                if self._loop and self._loop.is_running():
                    self._loop.call_soon_threadsafe(self._loop.stop)
                if hasattr(self, '_loop_thread') and self._loop_thread.is_alive():
                    self._loop_thread.join(timeout=2.0)
                self._loop = None

    def run(
        self,
        duration: Optional[float] = None,
        on_sample: Optional[SampleCallback] = None,
    ) -> int:
        """Subscribe to data until ``duration`` seconds elapse or :meth:`stop`.

        Args:
            duration: Maximum wall-clock time to run, in seconds.
                ``None`` means run until :meth:`stop` is called.
            on_sample: Optional callback invoked synchronously for every
                successfully parsed sample.  Used by the CLI to print
                the live data stream.

        Returns:
            Number of samples ingested (i.e. successfully written to
            TDengine or accepted by the on_sample callback).
        """
        if not self._connected:
            raise RuntimeError("Adapter not connected. Call connect() first.")

        deadline = (time.monotonic() + duration) if duration else None
        logger.info(
            "Starting OPC UA subscription (endpoint=%s, interval=%.2fs, duration=%s)",
            self.config.endpoint,
            self.config.interval,
            f"{duration}s" if duration else "indefinite",
        )

        # Store callback for use in subscription handler
        self._on_sample_callback = on_sample

        # Main loop - just wait and flush periodically
        while not self._stop_event.is_set():
            if deadline is not None and time.monotonic() >= deadline:
                logger.info("Reached duration deadline, stopping")
                break

            # Sleep for a short interval, checking for stop event
            if self._stop_event.wait(self.config.interval):
                break

            # Flush buffer if needed
            self._maybe_flush()

        # Always flush at the end so the last partial batch is not lost.
        self.flush()
        logger.info(
            "Subscription stopped. ingested=%d, errors=%d",
            self.ingested_count,
            self.error_count,
        )
        return self.ingested_count

    def stop(self) -> None:
        """Request the subscription loop to exit at the next opportunity."""
        self._stop_event.set()

    def flush(self) -> int:
        """Persist any samples currently buffered in TDengine.

        Returns the number of rows written.  Safe to call from a
        background thread – the buffer is guarded by a lock.
        """
        with self._buffer_lock:
            if not self._buffer:
                return 0
            batch = self._buffer
            self._buffer = []
            self._last_flush = time.monotonic()

        if self._tdengine is None:
            # No storage configured – drop the batch but count it.
            # The CLI uses this mode for "dry-run" / smoke testing.
            logger.debug("No TDengine client wired; dropping %d samples", len(batch))
            self._ingested_count += len(batch)
            return len(batch)

        rows = [self._row_for_storage(s) for s in batch]
        written = self._persist_rows(rows)
        if written > 0:
            self._ingested_count += written
            logger.info("Flushed batch of %d samples to TDengine", written)
        return written

    # ------------------------------------------------------------------
    # Public, read-only state
    # ------------------------------------------------------------------

    @property
    def ingested_count(self) -> int:
        return self._ingested_count

    @property
    def error_count(self) -> int:
        return self._error_count

    @property
    def buffer_size(self) -> int:
        return len(self._buffer)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _enqueue(self, sample: Any) -> None:
        """Add a sample to the buffer (called from subscription handler)."""
        with self._buffer_lock:
            self._buffer.append(sample)

    def _maybe_flush(self) -> None:
        """Flush if either the size or the age threshold is met."""
        with self._buffer_lock:
            too_many = len(self._buffer) >= self.config.batch_size
            too_old = (
                time.monotonic() - self._last_flush
            ) >= self.config.batch_interval and bool(self._buffer)
        if too_many or too_old:
            self.flush()

    def _row_for_storage(self, sample: Any) -> List[Any]:
        """Convert a :class:`Sample` into a row matching ``DEFAULT_TABLE_DDL``.

        Column order must stay in lockstep with the DDL constant
        declared at module top.
        """
        ts = sample.observed_at or datetime.now(timezone.utc)
        return [
            ts.strftime("%Y-%m-%d %H:%M:%S.%f"),
            sample.spindle_speed,
            sample.spindle_load,
            sample.feedrate,
            sample.execution,
        ]

    def _persist_rows(self, rows: List[List[Any]]) -> int:
        """Persist a batch of rows through the TDengine client."""
        if not rows:
            return 0
        client = self._tdengine
        if client is None:
            return 0

        # If the injected client exposes a ``insert_rows`` coroutine
        # we drive it from an event loop; otherwise we look for a
        # synchronous ``insert_rows_sync`` for ergonomic test stubs.
        insert = getattr(client, "insert_rows", None)
        if insert is None:
            logger.error("TDengine client does not expose insert_rows; aborting flush")
            return 0

        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # We're inside an event loop – schedule and wait.
                return loop.run_until_complete(
                    self._insert_async(client, insert, rows)
                )
            return loop.run_until_complete(
                self._insert_async(client, insert, rows)
            )
        except RuntimeError:
            # No event loop in this thread (typical CLI scenario).
            return asyncio.run(self._insert_async(client, insert, rows))

    async def _insert_async(self, client: Any, insert: Callable, rows: List[Any]) -> int:
        result = await insert(
            table_name=self.config.table,
            rows=rows,
            database=self.config.database,
        )
        if result is None or result < 0:
            logger.error("TDengine insert returned %r (rows=%d)", result, len(rows))
            return 0
        return int(result)


# ---------------------------------------------------------------------------
# Subscription handler
# ---------------------------------------------------------------------------


class SubHandler:
    """OPC UA subscription handler that receives data change notifications."""

    def __init__(self, adapter: OPCUAAdapter):
        self.adapter = adapter
        self._node_names = {}  # Cache: node_id_str -> browse_name

    def datachange_notification(self, node, val, data):
        """Called when a subscribed node's value changes."""
        try:
            from app.integrations.opcua.parser import parse_opcua_data

            # Get cached node name (avoid async call in sync callback)
            node_id_str = node.nodeid.to_string()
            node_name = self._node_names.get(node_id_str)
            
            if node_name is None:
                # Fallback: try to get from node (shouldn't happen normally)
                logger.warning("Node name not cached for %s, using node_id", node_id_str)
                node_name = node_id_str

            # Build data dict
            data_dict = {node_name: val}

            # Parse into Sample
            sample = parse_opcua_data(data_dict)

            # Enqueue sample
            self.adapter._enqueue(sample)

            # Call callback if registered
            if hasattr(self.adapter, "_on_sample_callback") and self.adapter._on_sample_callback:
                try:
                    self.adapter._on_sample_callback(sample)
                except Exception:
                    logger.exception("on_sample callback raised")

        except Exception as exc:
            logger.error("Error processing data change: %s", exc)
            self.adapter._error_count += 1


# ---------------------------------------------------------------------------
# Convenience: CLI / one-shot helper
# ---------------------------------------------------------------------------


def build_table_ddl() -> Tuple[str, ...]:
    """Return the canonical TDengine DDL column list for the table."""
    return DEFAULT_TABLE_DDL


# Regex used by the CLI to translate ``tds://host:port/db`` shorthand
# into the (host, port, database) tuple the TDengine client expects.
_TDS_URL_RE = re.compile(r"^tds://([^:/]+):(\d+)/(.+)$")


def parse_tds_url(url: str) -> Tuple[str, int, str]:
    """Parse a ``tds://host:port/database`` URL.

    Args:
        url: Connection string of the form ``tds://localhost:6030/test``.

    Returns:
        ``(host, port, database)`` tuple.

    Raises:
        ValueError: if the URL does not match the expected format.
    """
    match = _TDS_URL_RE.match(url)
    if not match:
        raise ValueError(
            f"Invalid TDS URL: {url!r}. Expected tds://host:port/database"
        )
    host, port, database = match.group(1), int(match.group(2)), match.group(3)
    return host, port, database


__all__ = [
    "AdapterConfig",
    "OPCUAAdapter",
    "build_table_ddl",
    "parse_tds_url",
]
