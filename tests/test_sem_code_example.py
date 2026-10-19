"""Offline checks for the local code example's adapter use and cleanup."""
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from examples.mcp import sem_code_example as example


@pytest.fixture
def toolset(monkeypatch):
    tool = SimpleNamespace(name="sem_find", forward=AsyncMock(return_value="context"))
    instance = SimpleNamespace(
        ensure_setup=AsyncMock(), get_tools=lambda: [tool], close=AsyncMock(), tool=tool
    )
    instance.constructor = Mock(return_value=instance)
    monkeypatch.setattr(example, "MCPToolset", instance.constructor)
    return instance


@pytest.mark.asyncio
async def test_lookup_uses_explicit_checkout_and_closes(toolset, tmp_path):
    assert await example.lookup(tmp_path, "parse_config") == "context"
    params = toolset.constructor.call_args.kwargs["connection_params"]
    assert params.command == "sem"
    assert params.args == ["mcp"]
    assert params.env["SEM_REPO"] == str(tmp_path.resolve())
    toolset.tool.forward.assert_awaited_once_with(
        query="parse_config", mode="context", token_budget=1200
    )
    toolset.close.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["setup", "missing", "call"])
async def test_failure_closes_toolset(toolset, tmp_path, failure):
    if failure == "setup":
        toolset.ensure_setup.side_effect = RuntimeError("connection failed")
    elif failure == "missing":
        toolset.get_tools = lambda: []
    else:
        toolset.tool.forward.return_value = "Error: lookup failed"
    with pytest.raises(RuntimeError):
        await example.lookup(tmp_path, "parse_config")
    toolset.close.assert_awaited_once()
