"""lingjing-mcp server entry point."""
from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys

logger = logging.getLogger("lingjing-mcp")


def run_stdio():
    """Run MCP server in stdio mode (for Cursor, Claude Code local calls)."""
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError:
        print("Error: mcp package not installed. Run: pip install mcp", file=sys.stderr)
        sys.exit(1)

    from mcp_server.tools import register_tools

    server = FastMCP("lingjing-mcp")
    register_tools(server)

    logger.info("Starting lingjing-mcp server in stdio mode")
    server.run()


async def run_http(host: str = "0.0.0.0", port: int = 8080):
    """Run MCP server in HTTP SSE mode (for remote AI agents)."""
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError:
        print("Error: mcp package not installed. Run: pip install mcp", file=sys.stderr)
        sys.exit(1)

    from mcp_server.tools import register_tools

    server = FastMCP("lingjing-mcp")
    register_tools(server)

    logger.info("Starting lingjing-mcp server in HTTP SSE mode on %s:%d", host, port)
    # Note: FastMCP may have different HTTP setup depending on version
    # Fallback: use FastMCP's built-in HTTP transport
    server.run(transport="sse", host=host, port=port)


def main():
    parser = argparse.ArgumentParser(description="lingjing-mcp server")
    parser.add_argument(
        "--transport",
        choices=["stdio", "sse"],
        default="stdio",
        help="Transport mode: stdio for local, sse for remote",
    )
    parser.add_argument("--host", default="0.0.0.0", help="HTTP host (for sse mode)")
    parser.add_argument("--port", type=int, default=8080, help="HTTP port (for sse mode)")
    parser.add_argument("--log-level", default="INFO", help="Logging level")

    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    token = os.environ.get("LINGJING_AGENT_TOKEN", "")
    if not token:
        logger.warning("LINGJING_AGENT_TOKEN not set. MCP tools will fail authentication.")

    if args.transport == "stdio":
        run_stdio()
    else:
        asyncio.run(run_http(args.host, args.port))


if __name__ == "__main__":
    main()
