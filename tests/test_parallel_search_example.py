"""Offline checks for example cleanup and transport error reporting."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from examples.mcp import parallel_search_example as example


@pytest.fixture
def toolset(monkeypatch):
    search = SimpleNamespace(
        name="web_search", forward=AsyncMock(return_value="sources")
    )
    fetch = SimpleNamespace(
        name="web_fetch", forward=AsyncMock(return_value="excerpts")
    )
    toolset = SimpleNamespace(
        ensure_setup=AsyncMock(),
        get_tools=lambda: [search, fetch],
        close=AsyncMock(),
        search=search,
        fetch=fetch,
    )
    monkeypatch.setattr(example, "MCPToolset", lambda **kwargs: toolset)
    return toolset


async def test_related_calls_share_session_and_close(toolset):
    result = await example.search_and_fetch(
        "Find docs", ["Python asyncio docs"], ["https://docs.python.org"]
    )
    assert result == {"search": "sources", "fetch": "excerpts"}
    search_args = toolset.search.forward.call_args.kwargs
    fetch_args = toolset.fetch.forward.call_args.kwargs
    assert search_args["session_id"] == fetch_args["session_id"]
    toolset.close.assert_awaited_once()


@pytest.mark.parametrize("operation", ["setup", "search", "fetch"])
async def test_errors_close_toolset(toolset, operation):
    if operation == "setup":
        toolset.ensure_setup.side_effect = RuntimeError("connection failed")
    else:
        getattr(toolset, operation).forward.return_value = "Error: request timed out"
    with pytest.raises(RuntimeError):
        await example.search_and_fetch(
            "Find docs", ["Python asyncio docs"], ["https://docs.python.org"]
        )
    toolset.close.assert_awaited_once()
    if operation in ("setup", "search"):
        toolset.fetch.forward.assert_not_awaited()


async def test_search_only(toolset):
    assert await example.search_and_fetch("Find docs", ["Python asyncio docs"], []) == {
        "search": "sources"
    }
    toolset.fetch.forward.assert_not_awaited()
    toolset.close.assert_awaited_once()
