# Local code lookup with Sem

[Sem](https://github.com/Ataraxy-Labs/sem) exposes symbol lookup and source search
over stdio MCP. Install Sem using its upstream instructions and check
`sem --version`. From a Minion source checkout:

```bash
pip install -e .
python -m examples.mcp.sem_code_example --repo /absolute/path/to/repo parse_config
```

Replace the path and symbol with an existing Git checkout and a symbol in it.
Use `--sem /absolute/path/to/sem` if the executable is not on PATH.

The example discovers `sem_find` with `MCPToolset`, calls its `AsyncMcpTool`
adapter with a 1,200-token context budget, and closes the toolset even on failure.
It needs no model or provider credentials. The first query may build an index;
an empty lookup can mean the symbol was not found, rather than a transport error.
This is a direct tool example, not an agent benchmark.

For an agent, pass only the desired tools (for example `sem_find` and `sem_grep`)
from `toolset.get_tools()` to `await CodeAgent.create(tools=..., llm=...)`, and
keep the toolset open until the agent finishes. Model inference requires your
usual provider configuration. See the [MCP agent example](../examples/mcp/mcp_agent_example.py).

Lookup does not edit source, but Sem may write its index. The full stdio server
also exposes validation tools that can execute commands. Filtering agent tools
is not a server sandbox; use a trusted checkout and appropriate host permissions.
`SEM_REPO` selects a repository, not a security boundary.
