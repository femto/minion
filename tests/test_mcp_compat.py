"""End-to-end MCP client tests that run against whichever MCP SDK (1.x or 2.x) is installed."""

import socket
import subprocess
import sys
import time
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest

from minion.tools.mcp._compat import MCP_V2, get_field, session_read_timeout
from minion.tools.mcp.mcp_integration import MCPBrainClient
from minion.tools.mcp.mcp_toolset import (
    MCPToolset,
    StdioServerParameters,
    StreamableHTTPServerParameters,
)

SERVER = str(Path(__file__).with_name("mcp_compat_server.py"))


def test_session_read_timeout_matches_sdk():
    converted = session_read_timeout(timedelta(seconds=7))
    if MCP_V2:
        assert converted == 7.0
    else:
        assert converted == timedelta(seconds=7)
    assert session_read_timeout(None) is None


def test_get_field_reads_snake_and_camel_case():
    assert get_field(SimpleNamespace(input_schema={"a": 1}), "input_schema", "inputSchema") == {"a": 1}
    assert get_field(SimpleNamespace(inputSchema={"b": 2}), "input_schema", "inputSchema") == {"b": 2}
    assert get_field(SimpleNamespace(), "mime_type", "mimeType", "unknown") == "unknown"


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


@pytest.fixture
def http_server_url():
    port = _free_port()
    proc = subprocess.Popen(
        [sys.executable, SERVER, "http", str(port)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        for _ in range(100):
            if proc.poll() is not None:
                pytest.fail("MCP test server exited early")
            try:
                with socket.create_connection(("127.0.0.1", port), timeout=0.1):
                    break
            except OSError:
                time.sleep(0.1)
        else:
            pytest.fail("MCP test server did not start")
        yield f"http://127.0.0.1:{port}/mcp"
    finally:
        proc.terminate()
        proc.wait(timeout=10)


async def _check_toolset(toolset: MCPToolset):
    try:
        await toolset.ensure_setup()
        tools = {tool.name: tool for tool in toolset.get_tools()}
        assert set(tools) >= {"echo", "add"}
        assert "text" in tools["echo"].inputs
        # FastMCP/MCPServer wrap non-dict return values as {"result": ...} structured content
        assert await tools["echo"].forward(text="hello") == {"result": "hello"}
        assert await tools["add"].forward(a=1, b=2) == {"sum": 3}
    finally:
        await toolset.close()


async def test_toolset_stdio():
    toolset = MCPToolset(
        StdioServerParameters(command=sys.executable, args=[SERVER, "stdio"]),
        setup_timeout=30,
    )
    await _check_toolset(toolset)


async def test_toolset_streamable_http(http_server_url):
    toolset = MCPToolset(
        StreamableHTTPServerParameters(url=http_server_url, headers={"User-Agent": "minion-test"}),
        setup_timeout=30,
    )
    await _check_toolset(toolset)


async def test_brain_client_streamable_http(http_server_url):
    async with MCPBrainClient() as client:
        await client.add_mcp_server("http", url=http_server_url)
        tools = client.get_tool_functions()
        assert {"echo", "add"} <= set(tools)
        assert tools["echo"].parameters["properties"]["text"]["type"] == "string"
        assert "hello" in await tools["echo"].forward(text="hello")


async def test_toolset_session_timeout_applies_to_tool_calls(http_server_url):
    toolset = MCPToolset(
        StdioServerParameters(command=sys.executable, args=[SERVER, "stdio"]),
        setup_timeout=30,
        session_timeout=30,
    )
    try:
        await toolset.ensure_setup()
        tools = {tool.name: tool for tool in toolset.get_tools()}
        # AsyncMcpTool previously ignored session_timeout and capped every call at 10s
        assert tools["sleep"].timeout == 30
    finally:
        await toolset.close()

    # Use the already-running HTTP server so a short timeout doesn't hit server startup
    toolset = MCPToolset(
        StreamableHTTPServerParameters(url=http_server_url),
        setup_timeout=30,
        session_timeout=1,
    )
    try:
        await toolset.ensure_setup()
        tools = {tool.name: tool for tool in toolset.get_tools()}
        assert (await tools["sleep"].forward(seconds=3)).startswith("Error:")
        assert await tools["sleep"].forward(seconds=0) == {"result": "done"}
    finally:
        await toolset.close()


async def test_tool_execution_error_is_reported(http_server_url):
    toolset = MCPToolset(StreamableHTTPServerParameters(url=http_server_url), setup_timeout=30)
    try:
        await toolset.ensure_setup()
        tools = {tool.name: tool for tool in toolset.get_tools()}
        result = await tools["fail"].forward(reason="Request limit reached")
        assert result.startswith("Error: MCP tool fail failed: ")
        assert "Request limit reached" in result
    finally:
        await toolset.close()

    async with MCPBrainClient() as client:
        await client.add_mcp_server("http", url=http_server_url)
        result = await client.get_tool_functions()["fail"].forward(reason="Request limit reached")
        assert result.startswith("Error: MCP tool fail failed: ")
        assert "Request limit reached" in result


async def test_hyphenated_tool_is_called_by_original_name(http_server_url):
    toolset = MCPToolset(StreamableHTTPServerParameters(url=http_server_url), setup_timeout=30)
    try:
        await toolset.ensure_setup()
        tools = {tool.name: tool for tool in toolset.get_tools()}
        # Exposed under a Python-safe name, but the server must be called with "echo-hyphen"
        assert await tools["echo_hyphen"].forward(text="hello") == {"result": "hello"}
    finally:
        await toolset.close()
