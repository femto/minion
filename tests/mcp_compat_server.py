"""Minimal MCP server for tests/test_mcp_compat.py; runs on MCP SDK 1.x and 2.x.

Usage: python mcp_compat_server.py stdio
       python mcp_compat_server.py http <port>
"""

import sys

import anyio

try:
    from mcp.server.mcpserver import MCPServer  # MCP 2.x

    server = MCPServer("minion-compat-test")

    def run(transport: str, port: int = 0) -> None:
        if transport == "stdio":
            server.run("stdio")
        else:
            server.run("streamable-http", host="127.0.0.1", port=port)

except ImportError:
    from mcp.server.fastmcp import FastMCP  # MCP 1.x

    server = FastMCP("minion-compat-test")

    def run(transport: str, port: int = 0) -> None:
        if transport == "stdio":
            server.run("stdio")
        else:
            server.settings.host = "127.0.0.1"
            server.settings.port = port
            server.run("streamable-http")


@server.tool()
def echo(text: str) -> str:
    """Echo the given text back."""
    return text


@server.tool()
def add(a: int, b: int) -> dict:
    """Add two integers."""
    return {"sum": a + b}


@server.tool()
async def sleep(seconds: float) -> str:
    """Sleep for the given number of seconds."""
    await anyio.sleep(seconds)
    return "done"


if __name__ == "__main__":
    run(sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 0)
