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


async def run_http(host: str = "127.0.0.1", port: int = 8080):
    """Run MCP server in HTTP SSE mode (for remote AI agents).

    S2 修复：默认绑定 127.0.0.1 而非 0.0.0.0。
    SSE 端点本身不内置入站鉴权（token 仅用于后端 Bearer 校验），
    因此默认仅监听回环地址。如需远程访问，应通过 nginx 反向代理
    前置鉴权中间件，而非直接暴露 0.0.0.0。
    显式指定 --host 0.0.0.0 时会记录 WARNING 并要求环境变量
    LNN_MCP_ALLOW_REMOTE=1 确认。
    """
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError:
        print("Error: mcp package not installed. Run: pip install mcp", file=sys.stderr)
        sys.exit(1)

    from mcp_server.tools import register_tools

    # S2 修复：0.0.0.0 远程暴露需显式确认
    if host in ("0.0.0.0", "::", ""):
        if os.environ.get("LNN_MCP_ALLOW_REMOTE", "") != "1":
            raise RuntimeError(
                "Refusing to bind MCP SSE to %r without ingress auth. "
                "SSE endpoint has no built-in inbound authentication. "
                "Either (a) use default 127.0.0.1 + reverse proxy with auth, "
                "or (b) set LNN_MCP_ALLOW_REMOTE=1 to acknowledge the risk." % host
            )
        logger.warning(
            "MCP SSE bound to %s:%d WITHOUT ingress auth - remote clients "
            "can invoke tools. Ensure network isolation or front-proxy auth.",
            host,
            port,
        )

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
    # S2 修复：默认 127.0.0.1，需显式 --host 0.0.0.0 + LNN_MCP_ALLOW_REMOTE=1 才远程暴露
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="HTTP host (for sse mode, default 127.0.0.1; use 0.0.0.0 only behind auth proxy)",
    )
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
