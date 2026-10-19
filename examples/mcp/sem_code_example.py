"""Look up code in a local Git checkout through Minion's MCP tool adapters."""

import argparse
import asyncio
import json
from pathlib import Path

from minion.tools.mcp.mcp_toolset import MCPToolset, StdioServerParameters


async def lookup(repo: Path, query: str, command: str = "sem"):
    repo = repo.resolve(strict=True)
    if not repo.is_dir():
        raise ValueError("Repository path must be a directory")
    toolset = MCPToolset(
        connection_params=StdioServerParameters(
            command=command, args=["mcp"], env={"SEM_REPO": str(repo)}, cwd=str(repo)
        ),
        name="sem_code",
    )
    try:
        await toolset.ensure_setup()
        tools = {tool.name: tool for tool in toolset.get_tools()}
        if "sem_find" not in tools:
            raise RuntimeError("Server did not expose sem_find")
        result = await tools["sem_find"].forward(
            query=query, mode="context", token_budget=1200
        )
        if isinstance(result, str) and result.startswith("Error:"):
            raise RuntimeError(result)
        return result
    finally:
        await toolset.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("query", help="An existing symbol, e.g. parse_config")
    parser.add_argument("--repo", required=True, type=Path)
    parser.add_argument("--sem", default="sem", help="Sem executable or absolute path")
    args = parser.parse_args()
    result = asyncio.run(lookup(args.repo, args.query, args.sem))
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
