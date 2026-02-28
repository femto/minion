# Tool Search Tool (TST): Dynamic Tool Discovery

## Overview

Based on Anthropic's [Advanced Tool Use](https://www.anthropic.com/engineering/advanced-tool-use) article, the **Tool Search Tool (TST)** enables dynamic tool discovery for large tool libraries.

**Key Benefits:**
- **85% token reduction** compared to loading all tools upfront
- **Better tool selection accuracy** (49% -> 74% for Opus 4)
- **Dynamic discovery** instead of loading all definitions at startup

## The Problem

When you have many tools (50+), loading all tool definitions into the context window:
- Consumes thousands of tokens before any task begins
- Degrades model performance with information overload
- Increases API costs unnecessarily

## The Solution

Instead of loading all tools upfront, provide a **search tool** that lets the agent discover relevant tools on-demand:

```
Traditional:       [Tool1] [Tool2] [Tool3] ... [Tool50] + Task
With TST:          [ToolSearch] + Task
                   Agent: "Search for tools related to GitHub"
                   → [github.create_pr, github.list_issues, ...]
```

## Quick Start

### Basic Usage

```python
from minion.tools import ToolRegistry, ToolSearchTool, LoadToolTool

# 1. Create registry and register all your tools
registry = ToolRegistry()
registry.register_many([tool1, tool2, ...], defer_loading=True)

# 2. Create search tool
search_tool = ToolSearchTool(registry)

# 3. Give agent ONLY the search tool (not all 50 tools)
agent = await CodeAgent.create(
    llm="gpt-4o",
    tools=[search_tool]
)
```

### With Dynamic Loading

```python
# Enable agents to load discovered tools at runtime
search_tool = ToolSearchTool(registry)
load_tool = LoadToolTool(registry, agent=agent)

agent = await CodeAgent.create(
    llm="gpt-4o",
    tools=[search_tool, load_tool]
)

# Now agent can:
# 1. Search: results = tool_search("github pull request")
# 2. Load: load_tool("github.create_pull_request")
# 3. Use: github_create_pull_request(repo="owner/repo", ...)
```

## Search Strategies

### Keyword Search (Default)
Fast, simple keyword matching. Best for quick searches.

```python
results = search_tool.forward("pull request", strategy="keyword")
```

### Regex Search
Pattern-based matching for precise searches.

```python
results = search_tool.forward(r"github\.", strategy="regex")
```

### BM25 Search
Relevance-ranked search using BM25 algorithm. Best for natural language queries.

```python
# Requires: pip install rank_bm25
results = search_tool.forward(
    "I want to create a new task in project management",
    strategy="bm25"
)
```

## Components

### ToolRegistry

Central registry for managing tools with deferred loading:

```python
from minion.tools import ToolRegistry

registry = ToolRegistry()

# Register individual tools
registry.register(my_tool, defer_loading=True, category="github")

# Register multiple tools
registry.register_many([tool1, tool2], defer_loading=True, category="slack")

# Register factory for lazy instantiation
registry.register_factory(
    name="expensive_tool",
    factory=lambda: ExpensiveTool(),
    description="Tool that's expensive to create",
    category="heavy"
)

# Get statistics
print(registry.get_stats())
# {'total_registered': 50, 'total_loaded': 2, 'categories': ['github', 'slack', ...]}
```

### ToolSearchTool

Search for tools without loading them:

```python
from minion.tools import ToolSearchTool

search_tool = ToolSearchTool(registry)

# Search with various strategies
results = search_tool.forward(
    query="create pull request",
    strategy="keyword",  # or "regex", "bm25"
    top_k=5,
    category="github"    # optional filter
)

# Results are lightweight summaries, not full tool definitions
for r in results:
    print(f"{r['name']}: {r['description']}")
```

### LoadToolTool

Load discovered tools for use:

```python
from minion.tools import LoadToolTool

load_tool = LoadToolTool(registry, agent=agent)

# Load a tool by name
result = load_tool.forward("github.create_pull_request")
# {'success': True, 'tool_name': '...', 'function_name': 'github_create_pull_request', ...}

# Tool is now available in agent's tool list
```

## Category Filtering

Organize tools by category for faster searches:

```python
# Register with categories
registry.register(github_tool, category="github")
registry.register(slack_tool, category="slack")

# Search within category
results = search_tool.forward("create", category="github")

# List all categories
categories = search_tool.list_categories()
# ['github', 'slack', 'jira', ...]
```

## Complete Example

```python
import asyncio
from minion.agents import CodeAgent
from minion.tools import ToolRegistry, ToolSearchTool, LoadToolTool

async def main():
    # Create registry with many tools (but don't load them all)
    registry = ToolRegistry()
    registry.register_many(github_tools, category="github")
    registry.register_many(slack_tools, category="slack")
    registry.register_many(jira_tools, category="jira")
    # ... 50+ tools total

    # Create search tool
    search_tool = ToolSearchTool(registry)

    # Create agent with ONLY search tool
    agent = await CodeAgent.create(
        llm="gpt-4o",
        tools=[search_tool]
    )

    # Add load tool with agent reference
    load_tool = LoadToolTool(registry, agent=agent)
    agent.add_tool(load_tool)

    # Agent now discovers and loads tools as needed
    result = await agent.run_async("""
        Create a pull request for the bug fix.
        First, search for available GitHub tools,
        then load and use the appropriate one.
    """)

asyncio.run(main())
```

## Token Savings Analysis

| Approach | Tokens | Notes |
|----------|--------|-------|
| Load all 50 tools | ~5,000+ | All definitions in context |
| Tool Search Tool | ~500 | Only search tool definition |
| **Savings** | **~85%** | Significant cost reduction |

## Best Practices

### 1. Use Categories
Organize tools by service/domain for faster, more accurate searches:
```python
registry.register_many(github_tools, category="github")
registry.register_many(aws_tools, category="aws")
```

### 2. Write Good Descriptions
Tool descriptions are indexed for search. Make them descriptive:
```python
# Good
description = "Create a pull request on GitHub. Specify the repository, base branch, head branch, title, and body."

# Less good
description = "Creates PRs"
```

### 3. Use Appropriate Search Strategy
- **keyword**: Fast, for simple searches
- **regex**: For pattern matching (e.g., `github\..*`)
- **bm25**: For natural language queries (requires `rank_bm25`)

### 4. Consider Factory Registration
For expensive tools, use factory registration:
```python
registry.register_factory(
    name="browser_tool",
    factory=lambda: BrowserTool(),  # Only created when loaded
    description="Browser automation tool"
)
```

## Installation

```bash
# Basic
pip install minionx

# With BM25 support for better natural language search
pip install minionx rank_bm25
```

## Related Documentation

- [Anthropic's Advanced Tool Use Article](https://www.anthropic.com/engineering/advanced-tool-use)
- [CodeAgent Documentation](merged_code_agent.md)
- [Example: tool_search_example.py](../examples/tool_search_example.py)
