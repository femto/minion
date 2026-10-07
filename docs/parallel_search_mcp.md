# Parallel Search MCP example

Use Minion's existing `MCPToolset` with Parallel's anonymous Streamable HTTP
endpoint to search the web and fetch page excerpts. No Parallel API key or local
MCP server is required. This example calls the tools directly, so it also needs no
LLM configuration or model API key.

From a source checkout:

```bash
pip install -e .
python -m examples.mcp.parallel_search_example
```

Supply an objective, keyword queries, and optional URLs to read:

```bash
python -m examples.mcp.parallel_search_example \
  --objective "Find how Python asyncio TaskGroup handles exceptions." \
  --query "Python asyncio TaskGroup exception handling" \
  --url https://docs.python.org/3/library/asyncio-task.html
```

`--query` and `--url` can be repeated. Fetch accepts up to 20 URLs per call.
The output contains the search result and, when URLs are supplied, fetched page
content. URLs are supplied explicitly rather than automatically opened from the
search results.

The example connects to `https://search.parallel.ai/mcp`, discovers `web_search`
and `web_fetch` through `MCPToolset.get_tools()`, and executes Minion's
`AsyncMcpTool` adapters. It sends a Minion User-Agent, reuses one session ID for
related calls, and closes the toolset in a `finally` block. It does not read or
send a Parallel key. Existing provider defaults and configuration are unchanged.

To use these tools with an agent, pass `toolset.get_tools()` to
`await CodeAgent.create(tools=..., llm=...)` after setup, and keep the toolset
open until the agent finishes. Agent model inference requires its own configured
provider and may incur charges. See the [MCP agent example](../examples/mcp/mcp_agent_example.py).

Parallel's [Search MCP documentation](https://docs.parallel.ai/integrations/mcp/search-mcp)
describes the current schemas and limits. Anonymous access is free for exploration
and light use, with rate limits and server-managed `fast` search settings. Tool
excerpts are capped to roughly 25,000 characters per call. The example keeps
Minion's existing MCP timeouts; a slow request may report a timeout. Free access
does not include model inference.
