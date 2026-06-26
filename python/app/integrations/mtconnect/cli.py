"""Command-line entry point for the MTConnect adapter.

Designed to be invoked as a Python module so it picks up the right
``sys.path`` and package context automatically::

    python -m app.integrations.mtconnect.cli \\
        --agent http://demo.mtconnect.org:80 \\
        --duration 20 \\
        --output tds://localhost:6030/test.mtconnect

Behaviour
---------
* **Connection probe** – the first thing the CLI does is call
  :meth:`MTConnectAdapter.probe` so a misconfigured agent URL fails
  fast and with a clear error message.
* **Live printing** – every successfully parsed sample is printed to
  stdout in a compact, fixed-width format so users can see the data
  stream flowing in real time.
* **TDengine persistence** – samples are buffered and flushed to the
  configured TDengine database in batches (see ``--batch-size``).
* **Graceful shutdown** – ``Ctrl-C`` cleanly stops the polling loop
  and flushes the final batch.

The module is fully covered by the test suite via
:func:`main` (which returns the exit code) and the individual
helpers.
"""

from __future__ import annotations

import argparse
import logging
import sys
from typing import List, Optional, Sequence

from app.integrations.mtconnect.adapter import (
    AdapterConfig,
    MTConnectAdapter,
    parse_tds_url,
)
from app.integrations.mtconnect.parser import Sample


# Default public MTConnect demo agent (per M0.3 task).
DEFAULT_AGENT_URL = "http://demo.mtconnect.org:80"
DEFAULT_OUTPUT = "tds://localhost:6030/test.mtconnect"


# ---------------------------------------------------------------------------
# Output formatting
# ---------------------------------------------------------------------------


def format_sample(sample: Sample) -> str:
    """Render a sample as a single line of text for CLI display.

    The format is intentionally compact and human-friendly so it can
    be eyeballed during a smoke test::

        [2026-06-11 10:23:45.123] speed=12000.0 load=42.5 feed=1500.0 exec=ACTIVE

    Missing values are rendered as ``-`` so columns stay aligned.
    """
    ts = (sample.observed_at.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
          if sample.observed_at else "-")
    speed = _fmt(sample.spindle_speed)
    load = _fmt(sample.spindle_load)
    feed = _fmt(sample.feedrate)
    exec_ = sample.execution if sample.execution is not None else "-"
    return f"[{ts}] speed={speed} load={load} feed={feed} exec={exec_}"


def _fmt(value: Optional[float]) -> str:
    """Format a float compactly; return ``-`` for ``None``."""
    if value is None:
        return "-"
    return f"{value:.2f}"


# ---------------------------------------------------------------------------
# TDengine wiring
# ---------------------------------------------------------------------------


def build_tdengine_client(output_url: str):
    """Construct a TDengine client from a ``tds://`` URL.

    The function is lazy: it imports :mod:`app.services.tdengine_client`
    only when actually needed so unit tests that don't care about
    storage can run in isolation.
    """
    host, port, database = parse_tds_url(output_url)
    # The TDengine client reads its connection parameters from
    # environment variables.  Set them on the fly so the same client
    # can be reused for any URL passed via the CLI.
    import os
    password = os.environ.get("TDENGINE_PASSWORD", "")
    if not password:
        logger.warning(
            "TDENGINE_PASSWORD not set. Please configure it in .env file."
        )
    os.environ["TDENGINE_URL"] = f"taos://root:{password}@{host}:{port}"
    os.environ["TDENGINE_DB"] = database

    try:
        from app.services import tdengine_client as tdc
    except ImportError as exc:  # pragma: no cover - import-time guard
        raise SystemExit(
            f"Cannot import TDengine client: {exc}\n"
            "Make sure the python/app directory is on PYTHONPATH "
            "and taospy is installed."
        )

    client = tdc.get_tdengine()
    return client, database, tdc


async def ensure_table(database: str, table: str) -> bool:
    """Make sure the destination table exists; create it on first run.

    Best-effort: failure is logged but does **not** abort the CLI – we
    still want to print data even if the table can't be created right
    now (TDengine might come up a few seconds after the script).
    """
    try:
        from app.services import tdengine_client as tdc
    except ImportError:  # pragma: no cover
        return False
    try:
        ok = await tdc.ensure_database(database)
        if not ok:
            return False
        # Use the canonical DDL defined by the adapter.
        from app.integrations.mtconnect.adapter import build_table_ddl
        return await tdc.create_table_if_not_exists(
            table_name=table,
            columns=list(build_table_ddl()),
            database=database,
        )
    except (ConnectionError, TimeoutError, OSError, RuntimeError, ValueError) as exc:  # pragma: no cover - defensive
        logging.getLogger(__name__).warning(
            "ensure_table(%s.%s) failed: %s", database, table, exc
        )
        return False


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    """Construct the argparse parser.  Kept separate for testability."""
    parser = argparse.ArgumentParser(
        prog="python -m app.integrations.mtconnect.cli",
        description=(
            "Poll a MTConnect Agent, parse spindle/feedrate/execution "
            "data items and persist them to TDengine."
        ),
    )
    parser.add_argument(
        "--agent",
        default=DEFAULT_AGENT_URL,
        help=(
            "Base URL of the MTConnect Agent "
            f"(default: {DEFAULT_AGENT_URL})"
        ),
    )
    parser.add_argument(
        "--duration",
        type=float,
        default=None,
        help=(
            "How long to run the polling loop, in seconds. "
            "Omit to run until Ctrl-C."
        ),
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=1.0,
        help="Polling interval in seconds (default: 1.0 → 1 Hz).",
    )
    parser.add_argument(
        "--output",
        default=DEFAULT_OUTPUT,
        help=(
            "TDengine connection string of the form "
            "``tds://host:port/database`` (default: "
            f"{DEFAULT_OUTPUT})."
        ),
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=10,
        help="Flush to TDengine after this many samples (default: 10).",
    )
    parser.add_argument(
        "--batch-interval",
        type=float,
        default=5.0,
        help=(
            "Maximum age of buffered samples before forcing a flush, "
            "in seconds (default: 5.0)."
        ),
    )
    parser.add_argument(
        "--max-retries",
        type=int,
        default=5,
        help="Maximum retries per polling cycle (default: 5).",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=10.0,
        help="HTTP request timeout in seconds (default: 10.0).",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging verbosity (default: INFO).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help=(
            "Skip the TDengine wiring – useful for smoke-testing the "
            "network/probe path without a database."
        ),
    )
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    """CLI main entry point.  Returns the process exit code."""
    parser = build_parser()
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    log = logging.getLogger("mtconnect.cli")

    config = AdapterConfig(
        agent_url=args.agent,
        timeout=args.timeout,
        interval=args.interval,
        batch_size=args.batch_size,
        batch_interval=args.batch_interval,
        max_retries=args.max_retries,
    )

    # Resolve database / table from the TDS URL.  We do this *before*
    # wiring the TDengine client so the table-creation step uses the
    # right name.
    host, port, database = parse_tds_url(args.output)
    config.database = database

    tdengine = None
    if not args.dry_run:
        tdengine, _db, _tdc = build_tdengine_client(args.output)
        if tdengine is None:
            log.warning(
                "TDengine client could not be initialised; continuing "
                "in read-only mode (no rows will be persisted)."
            )
        else:
            # Ensure table exists.  This is a best-effort step.
            import asyncio
            try:
                asyncio.run(ensure_table(database, config.table))
            except (ConnectionError, TimeoutError, OSError, RuntimeError, ValueError) as exc:  # pragma: no cover
                log.warning("ensure_table raised: %s", exc)

    adapter = MTConnectAdapter(config=config, tdengine_client=tdengine)

    # 1) Probe – fail fast on agent / network problems.
    try:
        identity = adapter.probe()
        log.info("Agent identity: %s", identity)
    except (ConnectionError, TimeoutError, OSError, RuntimeError, ValueError) as exc:
        # We deliberately route the human-readable failure message to
        # ``sys.stderr`` (and *not* to ``logging``) so that callers
        # using ``capsys`` / ``subprocess`` can reliably capture the
        # failure reason without needing to plumb a logging handler.
        log.error("Probe failed: %s", exc)
        sys.stderr.write(f"Probe failed: {exc}\n")
        sys.stderr.flush()
        return 2

    # 2) Run the polling loop.  ``format_sample`` is the live printer.
    ingested: int = 0
    try:
        ingested = adapter.run(duration=args.duration, on_sample=_print_sample)
    except KeyboardInterrupt:
        log.info("Interrupted by user, flushing...")
        adapter.stop()
        ingested = adapter.flush()
    except (ConnectionError, TimeoutError, OSError, RuntimeError, ValueError) as exc:  # pragma: no cover - defensive
        # We never want an unexpected runtime failure (e.g. a flaky
        # network that raises something we did not anticipate) to
        # leave the user staring at a stack trace with no summary.
        # Log it, count it on the adapter and fall through to the
        # normal summary print below.
        log.exception("Polling loop raised: %s", exc)
        adapter.stop()
        try:
            ingested = adapter.flush()
        except (ConnectionError, TimeoutError, OSError, RuntimeError, ValueError):  # pragma: no cover - defensive
            pass
    finally:
        # Always print the final summary, even after errors.
        _print_summary(adapter, ingested)

    return 0


def _print_sample(sample: Sample) -> None:
    """Default CLI callback that prints the sample to stdout."""
    sys.stdout.write(format_sample(sample) + "\n")
    sys.stdout.flush()


def _print_summary(adapter: MTConnectAdapter, ingested: int) -> None:
    """Print the final tally so the user gets immediate feedback."""
    sys.stdout.write(
        f"已写入 {ingested} 条 "
        f"(errors={adapter.error_count}, "
        f"buffer_left={adapter.buffer_size})\n"
    )
    sys.stdout.flush()


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
