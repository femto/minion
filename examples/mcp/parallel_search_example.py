#!/usr/bin/env python3
"""Search and fetch with Parallel's anonymous Streamable HTTP MCP endpoint."""

import argparse
import asyncio
import json
import uuid

from minion.tools.mcp.mcp_toolset import MCPToolset, StreamableHTTPServerParameters

PARALLEL_MCP_URL = "https://search.parallel.ai/mcp"
USER_AGENT = "minion/parallel-search-example (https://github.com/femto/minion)"


async def search_and_fetch(objective: str, queries: list[str], urls: list[str]):
    """Use Minion's discovered tools directly, without model inference or API keys."""
    toolset = MCPToolset(
        connection_params=StreamableHTTPServerParameters(
            url=PARALLEL_MCP_URL,
            headers={"User-Agent": USER_AGENT},
        ),
        name="parallel_search",
    )
    try:
        await toolset.ensure_setup()
        tools = {tool.name: tool for tool in toolset.get_tools()}
        session_id = uuid.uuid4().hex
        search = await tools["web_search"].forward(
            objective=objective,
            search_queries=queries,
            session_id=session_id,
        )
        # AsyncMcpTool reports transport errors as strings. Surface them to the CLI.
        if isinstance(search, str) and search.startswith("Error:"):
            raise RuntimeError(search)
        results = {"search": search}
        if urls:
            fetched = await tools["web_fetch"].forward(
                urls=urls,
                search_queries=queries,
                session_id=session_id,
            )
            if isinstance(fetched, str) and fetched.startswith("Error:"):
                raise RuntimeError(fetched)
            results["fetch"] = fetched
        return results
    finally:
        await toolset.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--objective", default="Find Python asyncio documentation and examples."
    )
    parser.add_argument(
        "--query", action="append", help="Search query; repeat for multiple angles."
    )
    parser.add_argument(
        "--url",
        action="append",
        help="URL to fetch; repeat for multiple pages (up to 20).",
    )
    args = parser.parse_args()
    if args.url and len(args.url) > 20:
        parser.error("--url accepts at most 20 pages per call")
    results = asyncio.run(
        search_and_fetch(
            args.objective,
            args.query or ["Python asyncio documentation examples"],
            args.url or [],
        )
    )
    print(json.dumps(results, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
